#include <KsAPI.h>
#include <ksConstants.h>

#include <array>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <stdexcept>
#include <string>
#include <vector>

using namespace ksapi;
namespace fs=std::filesystem;

static const fs::path OUT{"/tmp/work1_v06_native"};
static const fs::path LOG=OUT/"work1.log";
static const fs::path FRW=OUT/"Work1_V06_ParametricMechanism.frw";
static std::ofstream lg;

static constexpr double L1=15.0,L2=55.0,L3=80.0,BASE=75.0,FI0=90.0;

static void log(const std::string&s){lg<<s<<std::endl;lg.flush();}
static void require(bool v,const std::string&m){if(!v){log("FAIL "+m);throw std::runtime_error(m);}}
template<class T> static T req(const T&v,const std::string&m){if(!v){log("FAIL "+m);throw std::runtime_error(m);}return v;}

struct Pt{double x,y;};
static std::array<Pt,5> geometry(double fi){
  const double ph=fi*M_PI/180.0;
  Pt A{0,0},D{BASE,0},B{L1*std::cos(ph),L1*std::sin(ph)};
  double qx=B.x-D.x,qy=B.y-D.y,d=std::hypot(qx,qy);
  require(d>L2,"geometry closure");
  double r=std::sqrt(d*d-L2*L2), tq=std::atan2(qy,qx), al=std::acos(r/d), th=tq-al;
  Pt C{D.x+r*std::cos(th),D.y+r*std::sin(th)};
  Pt E{D.x+L3*std::cos(th),D.y+L3*std::sin(th)};
  return {A,B,C,D,E};
}
static IDrawingContainerPtr drawing(const IFragmentDocumentPtr& doc){
  auto vm=req(doc->GetViewsAndLayersManager(),"ViewsAndLayersManager");
  auto vs=req(vm->GetViews(),"Views");
  IViewPtr v=req(vs->GetActiveView(),"ActiveView");
  IDrawingContainerPtr d=v; return req(d,"DrawingContainer");
}
static ISymbols2DContainerPtr symbols(const IFragmentDocumentPtr& doc){
  auto vm=req(doc->GetViewsAndLayersManager(),"ViewsAndLayersManager");
  auto vs=req(vm->GetViews(),"Views");
  IViewPtr v=req(vs->GetActiveView(),"ActiveView");
  ISymbols2DContainerPtr s=v; return req(s,"Symbols2DContainer");
}
static IViewPtr view(const IFragmentDocumentPtr& doc){
  return req(req(doc->GetViewsAndLayersManager(),"ViewsAndLayersManager")->GetViews()->GetActiveView(),"ActiveView");
}
static ILayerPtr layer(const IViewPtr& v,const std::wstring& name){
  auto ls=req(v->GetLayers(),"Layers");
  auto x=ls->Add();
  if(!x) x=ls->GetLayerByName(name);
  x=req(x,"Layer Add");
  x->SetName(name); x->SetVisible(true); x->SetBackground(false); x->SetPrintable(true);
  x->SetCurrent(); require(x->Update(),"Layer Update");
  return x;
}
static ILineSegmentPtr line(const IDrawingContainerPtr& d,Pt a,Pt b,int style=ksCSNormal){
  auto s=req(req(d->GetLineSegments(),"LineSegments")->Add(),"Line Add");
  s->SetX1(a.x);s->SetY1(a.y);s->SetX2(b.x);s->SetY2(b.y);s->SetStyle(style);
  require(s->Update(),"Line Update"); return s;
}
static IParametricConstraintPtr constraint(const IDrawingObjectPtr& obj,ksConstraintTypeEnum type,int idx=0,
                                            const IDrawingObjectPtr& partner={},int pidx=0,
                                            const std::wstring& variable=L"",double value=NAN){
  auto c=req(obj->NewConstraint(),"NewConstraint");
  c->SetConstraintType(type); c->SetIndex(idx);
  if(partner){c->SetPartners({partner});c->SetPartnerIndex(pidx);}
  if(!variable.empty()){c->SetVariable(variable);c->SetConstraintValue(value);c->SetComment(L"Управляющий размер "+variable);}
  require(c->Create(),"Constraint Create"); require(c->IsValid(),"Constraint invalid");
  return c;
}
static ILineDimensionPtr linear_dim(const ISymbols2DContainerPtr& sy,const ILineSegmentPtr& seg,
                                    const std::wstring& var,double value,double off){
  double x1=seg->GetX1(),y1=seg->GetY1(),x2=seg->GetX2(),y2=seg->GetY2();
  double dx=x2-x1,dy=y2-y1,L=std::hypot(dx,dy); require(L>0,"dimension line length");
  double nx=-dy/L,ny=dx/L;
  auto dim=req(req(sy->GetLineDimensions(),"LineDimensions")->Add(),"LineDimension Add");
  dim->SetX1(x1);dim->SetY1(y1);dim->SetX2(x2);dim->SetY2(y2);
  dim->SetX3((x1+x2)/2+nx*off);dim->SetY3((y1+y2)/2+ny*off);
  dim->SetAngle(std::atan2(dy,dx)*180.0/M_PI);dim->SetOrientation(ksLinDParallel);
  require(dim->Update(),"LineDimension Update");
  IDrawingObjectPtr dobj=dim, sobj=seg;
  constraint(dobj,ksCMergePoints,0,sobj,0);
  constraint(dobj,ksCMergePoints,1,sobj,1);
  constraint(dobj,ksCFixedDim);
  constraint(dobj,ksCDimWithVariable,0,{},0,var,value);
  return dim;
}
static IAngleDimensionPtr angle_dim(const ISymbols2DContainerPtr& sy,const ILineSegmentPtr& base,
                                    const ILineSegmentPtr& crank,double value){
  auto dim=req(req(sy->GetAngleDimensions(),"AngleDimensions")->Add(ksDrADimension),"AngleDimension Add");
  dim->SetBaseObject1(IDrawingObjectPtr(base)); dim->SetBaseObject2(IDrawingObjectPtr(crank));
  dim->SetRadius(22.0); dim->SetDirection(false); dim->SetDimensionType(ksDrADimension);
  require(dim->Update(),"AngleDimension Update");
  IDrawingObjectPtr dobj=dim;
  constraint(dobj,ksCFixedDim);
  constraint(dobj,ksCDimWithVariable,0,{},0,L"fi",value);
  return dim;
}
static Pt end1(const ILineSegmentPtr&s){return {s->GetX2(),s->GetY2()};}
static double distance(Pt a,Pt b){return std::hypot(a.x-b.x,a.y-b.y);}

static fs::path template_frw(){
  fs::path dir{"/opt/ascon/kompas3d-v25/Utils/KLibEditor/Templates"};
  for(const auto&e:fs::directory_iterator(dir)) if(e.is_regular_file()&&e.path().extension()==".frw") return e.path();
  throw std::runtime_error("native FRW template not found");
}
static void native_file(const fs::path&p){require(fs::exists(p)&&fs::file_size(p)>1024,"FRW missing/small");}

static void run_test(const IFragmentDocumentPtr& doc,const ILineSegmentPtr& crank,const std::string& stage){
  auto fi=req(doc->GetVariableByName(false,L"fi"),"variable fi");
  std::vector<std::pair<double,Pt>> rows;
  for(double v:{45.0,135.0,90.0}){
    fi->SetValue(v);
    require(doc->CompleteRebuildDocument(),"CompleteRebuild fi="+std::to_string(v));
    Pt b=end1(crank); rows.push_back({v,b});
    log(stage+"_FI_"+std::to_string((int)v)+"_B="+std::to_string(b.x)+","+std::to_string(b.y));
  }
  require(distance(rows[0].second,rows[1].second)>1.0,stage+" physical movement");
  require(std::abs(rows[2].second.x)<1e-3&&std::abs(rows[2].second.y-L1)<1e-3,stage+" return fi90");
  log(stage+"_FI_45_135_90_PHYSICAL_MOVEMENT_PASS");
}

static ILineSegmentPtr find_crank(const IFragmentDocumentPtr& doc){
  auto objs=drawing(doc)->GetObjects({ksDrLineSeg});
  ILineSegmentPtr best;
  for(auto&o:objs){
    ILineSegmentPtr s=o;
    if(!s) continue;
    double len=std::hypot(s->GetX2()-s->GetX1(),s->GetY2()-s->GetY1());
    if(std::abs(len-L1)<1e-3 && std::hypot(s->GetX1(),s->GetY1())<1e-3){best=s;break;}
  }
  return req(best,"find crank after reopen");
}

extern "C" int run_variant06_writer(){
  static bool done=false;if(done)return 0;
  try{
    if(lg.is_open())lg.close();lg.clear();fs::remove_all(OUT);fs::create_directories(OUT);lg.open(LOG);
    log("WORK1_VARIANT06_BEGIN");
    IApplication& app=GetKompasApplication(); app.SetHideMessage(ksHideMessageYes);
    int ma=0,mi=0,re=0,bu=0;app.GetSystemVersion(ma,mi,re,bu);
    log("KOMPAS_VERSION="+std::to_string(ma)+"."+std::to_string(mi)+"."+std::to_string(re)+" build="+std::to_string(bu));
    auto docs=req(app.GetDocuments(),"Documents");
    auto tpl=template_frw();log("FRW_TEMPLATE="+tpl.string());
    auto base=req(docs->Open(tpl.wstring(),true,false),"Open native FRW template");
    IFragmentDocumentPtr doc=base; req(doc,"cast FragmentDocument");
    doc->SetParametricMode(true);

    auto v=view(doc);auto d=drawing(doc);auto sy=symbols(doc);
    layer(v,L"Контуры");
    auto g=geometry(FI0);Pt A=g[0],B=g[1],C=g[2],D=g[3],E=g[4];
    auto crank=line(d,A,B),coupler=line(d,B,C),rocker=line(d,D,E);

    constraint(IDrawingObjectPtr(crank),ksCFixedPoint,0);
    constraint(IDrawingObjectPtr(coupler),ksCMergePoints,0,IDrawingObjectPtr(crank),1);
    constraint(IDrawingObjectPtr(coupler),ksCPointOnCurve,1,IDrawingObjectPtr(rocker),0);
    constraint(IDrawingObjectPtr(coupler),ksCPerpendicular,0,IDrawingObjectPtr(rocker),0);
    constraint(IDrawingObjectPtr(crank),ksCHAlignPoints,0,IDrawingObjectPtr(rocker),0);

    layer(v,L"Вспомогательные построения");
    auto baseLine=line(d,A,D,ksCSConstruction);
    constraint(IDrawingObjectPtr(baseLine),ksCMergePoints,0,IDrawingObjectPtr(crank),0);
    constraint(IDrawingObjectPtr(baseLine),ksCMergePoints,1,IDrawingObjectPtr(rocker),0);

    layer(v,L"Размеры");
    linear_dim(sy,crank,L"l1",L1,10);
    linear_dim(sy,coupler,L"l2",L2,10);
    linear_dim(sy,rocker,L"l3",L3,10);
    linear_dim(sy,baseLine,L"L",BASE,-12);
    angle_dim(sy,baseLine,crank,FI0);

    require(doc->CompleteRebuildDocument(),"initial CompleteRebuildDocument");
    for(const auto&n:{L"l1",L"l2",L"l3",L"L",L"fi"}) req(doc->GetVariableByName(false,n),"required variable");
    log("VARIABLES_l1_l2_l3_L_fi_PASS");
    run_test(doc,crank,"PRE_SAVE");

    layer(v,L"Исследование");
    require(base->SaveAs(FRW.wstring()),"FRW SaveAs");
    native_file(FRW);
    require(base->Close(kdDoNotSaveChanges),"FRW Close");
    log("SAVE_CLOSE_PASS");

    auto b2=req(docs->Open(FRW.wstring(),true,false),"FRW Reopen");
    IFragmentDocumentPtr doc2=b2; req(doc2,"cast reopened FragmentDocument");
    doc2->SetParametricMode(true);
    require(doc2->CompleteRebuildDocument(),"reopen CompleteRebuildDocument");
    auto crank2=find_crank(doc2);
    run_test(doc2,crank2,"POST_REOPEN");
    auto fi=req(doc2->GetVariableByName(false,L"fi"),"reopen fi");fi->SetValue(90);
    require(doc2->CompleteRebuildDocument(),"final fi90 rebuild");
    require(b2->Save(),"final FRW Save");
    require(b2->Close(kdDoNotSaveChanges),"final FRW Close");

    native_file(FRW);
    log("FINAL_SAVE_CLOSE_REOPEN_REBUILD_PASS");
    log("RESULT=PASS_NATIVE_PARAMETRIC_VARIANT06");
    done=true;return 0;
  }catch(const std::exception&e){
    if(!lg.is_open()){fs::create_directories(OUT);lg.open(LOG,std::ios::app);}
    log(std::string("EXCEPTION=")+e.what());log("RESULT=FAIL_NATIVE_PARAMETRIC_VARIANT06");
  }catch(...){
    if(!lg.is_open()){fs::create_directories(OUT);lg.open(LOG,std::ios::app);}
    log("EXCEPTION=unknown");log("RESULT=FAIL_NATIVE_PARAMETRIC_VARIANT06");
  }
  return 2;
}
