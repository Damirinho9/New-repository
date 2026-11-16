#include <KsAPI.h>
#include <ksConstants.h>
#include <chrono>
#include <thread>
#include <fstream>
#include <cmath>
#include <vector>
#include <string>
#include <algorithm>
#include <fcntl.h>
#include <unistd.h>

using namespace ksapi;

static std::ofstream logstream("/tmp/work1_v6_inject.log", std::ios::out | std::ios::app);
static void log(const std::string& s){ logstream << s << std::endl; logstream.flush(); }

static IKompasDocumentPtr g_pending_doc{};
static int g_pending_age=0;
static bool g_waiting_for_document=false;
static bool g_writer_done=false;

struct P { double x,y; };
static constexpr double PI=3.14159265358979323846;
static constexpr double L1=20.0;
static constexpr double BASE=25.0;
static constexpr double L2=50.0; // l2 = 2L
static constexpr double L3=60.0;
static constexpr double DX=20.0;
static constexpr double N_RPM=250.0;
static constexpr double FI0=90.0;

static bool state(double deg,P& B,P& C,P& D,P& E,P& X){
  const double ph=deg*PI/180.0;
  P A{0,0}; C={0,-BASE};
  B={L1*std::cos(ph),L1*std::sin(ph)};
  double vx=B.x-C.x, vy=B.y-C.y;
  double d=std::hypot(vx,vy);
  if(d<1e-9) return false;
  double ux=vx/d, uy=vy/d;
  D={C.x+L2*ux,C.y+L2*uy};
  double q=L3*L3-D.y*D.y;
  if(q<0) return false;
  E={D.x+std::sqrt(q),0.0};
  X={D.x+(DX/L3)*(E.x-D.x),D.y+(DX/L3)*(E.y-D.y)};
  return true;
}

static ILayerPtr layer(const IViewPtr& view,int n,const std::wstring& name){
  auto ls=view->GetLayers();
  if(!ls){ log("layer: GetLayers failed"); return {}; }
  auto x=ls->GetLayerByNumber(n);
  if(!x){
    x=ls->Add();
    if(!x){ log("layer: Add failed n="+std::to_string(n)); return {}; }
    x->SetLayerNumber(n);
    x->SetName(name);
    if(!x->Update()){
      log("layer: Update failed n="+std::to_string(n));
      return {};
    }
  }
  log("layer OK n="+std::to_string(n));
  return x;
}

static ILineSegmentPtr line(const IDrawingContainerPtr& dc,P a,P b,int lay,int style){
  auto col=dc->GetLineSegments(); if(!col){ log("line FAIL GetLineSegments"); return {}; }
  auto s=col->Add(); if(!s){ log("line FAIL Add"); return {}; }
  s->SetX1(a.x); s->SetY1(a.y); s->SetX2(b.x); s->SetY2(b.y);
  if(lay>0) s->SetLayerNumber(lay);
  s->SetStyle(style);
  if(!s->Update()){
    log("line Update FAIL x1="+std::to_string(a.x)+" y1="+std::to_string(a.y)+
        " x2="+std::to_string(b.x)+" y2="+std::to_string(b.y)+
        " style="+std::to_string(style)+" layer="+std::to_string(lay));
    return {};
  }
  return s;
}

static bool constr(const IDrawingObjectPtr& o,ksConstraintTypeEnum t,int idx=-1,
                   const IDrawingObjectPtr& p={},int pidx=-1){
  auto c=o->NewConstraint(); if(!c) return false;
  c->SetConstraintType(t);
  if(idx>=0)c->SetIndex(idx);
  if(p)c->SetPartners({p});
  if(pidx>=0)c->SetPartnerIndex(pidx);
  bool ok=c->Create(); if(!ok)c->Delete();
  return ok;
}

static ILineDimensionPtr lin_dim(const ISymbols2DContainerPtr& sc,const ILineSegmentPtr& seg,
                                 const std::wstring& var,double val,int lay,double off){
  const std::string vn(var.begin(),var.end());
  log("lin_dim "+vn+" begin");
  auto col=sc->GetLineDimensions();
  if(!col){ log("lin_dim "+vn+" FAIL GetLineDimensions"); return {}; }
  auto d=col->Add();
  if(!d){ log("lin_dim "+vn+" FAIL Add"); return {}; }

  double x1=seg->GetX1(),y1=seg->GetY1(),x2=seg->GetX2(),y2=seg->GetY2();
  double dx=x2-x1,dy=y2-y1,le=std::hypot(dx,dy);
  if(le<1e-9){ log("lin_dim "+vn+" FAIL zero length"); return {}; }
  double nx=-dy/le,ny=dx/le;

  d->SetX1(x1);d->SetY1(y1);d->SetX2(x2);d->SetY2(y2);
  d->SetX3((x1+x2)/2+nx*off); d->SetY3((y1+y2)/2+ny*off);
  d->SetAngle(std::atan2(dy,dx)*180.0/PI);
  d->SetOrientation(ksLinDParallel);
  if(lay>0) d->SetLayerNumber(lay);

  if(!d->Update()){ log("lin_dim "+vn+" FAIL Update"); return {}; }
  log("lin_dim "+vn+" dimension Update PASS");

  // Native v25 route: let the dimension create its witness-point
  // associations itself, then make it driving.
  if(!d->Associate()){
    log("lin_dim "+vn+" FAIL Associate");
    return {};
  }
  log("lin_dim "+vn+" Associate PASS");

  if(!constr(d,ksCFixedDim)){
    log("lin_dim "+vn+" FAIL ksCFixedDim");
    return {};
  }
  log("lin_dim "+vn+" fixed-dim PASS");

  auto v=d->NewConstraint();
  if(!v){ log("lin_dim "+vn+" FAIL NewConstraint variable"); return {}; }
  v->SetConstraintType(ksCDimWithVariable);
  v->SetConstraintValue(val);
  v->SetVariable(var);
  v->SetComment(L"Управляющий размер");
  if(!v->Create()){
    log("lin_dim "+vn+" FAIL ksCDimWithVariable Create");
    v->Delete();
    return {};
  }
  log("lin_dim "+vn+" variable PASS");
  return d;
}

static IAngleDimensionPtr angle_dim(const ISymbols2DContainerPtr& sc,
                                    const ILineSegmentPtr& ref,const ILineSegmentPtr& crank,
                                    int lay,double value){
  auto col=sc->GetAngleDimensions(); if(!col)return {};
  auto d=col->Add(ksDrADimension); if(!d)return {};
  d->SetXc(0);d->SetYc(0);
  d->SetX1(ref->GetX2());d->SetY1(ref->GetY2());
  d->SetX2(crank->GetX2());d->SetY2(crank->GetY2());
  d->SetBaseObject1(ref); d->SetBaseObject2(crank);
  d->SetRadius(12.0); d->SetDimensionType(ksADMinAngle);
  d->SetDirection(false); if(lay>0) d->SetLayerNumber(lay);
  if(!d->Update())return {};
  if(!d->Associate()) log("WARN angle Associate false");
  if(!constr(d,ksCFixedDim))return {};
  auto v=d->NewConstraint(); if(!v)return {};
  v->SetConstraintType(ksCDimWithVariable); v->SetConstraintValue(value);
  v->SetVariable(L"fi"); v->SetComment(L"Угол поворота кривошипа");
  if(!v->Create())return {};
  return d;
}

static bool build(){
  log("writer start");
  IApplication& app=GetKompasApplication();
  log("GetKompasApplication ok");
  int ma=0,mi=0,re=0,bu=0; app.GetSystemVersion(ma,mi,re,bu);
  log("version="+std::to_string(ma)+"."+std::to_string(mi)+" build="+std::to_string(bu));
  app.SetHideMessage(ksHideMessageYes);

  auto docs=app.GetDocuments(); if(!docs){log("FAIL docs");return false;}
  const std::wstring templatePath=L"/opt/ascon/kompas3d-v25/Utils/KLibEditor/Templates/Фрагмент.frw";

  IKompasDocumentPtr base{};
  IKompasDocument2DPtr doc{};
  IViewPtr view{};
  IDrawingContainerPtr dc{};
  ISymbols2DContainerPtr sc{};


  g_waiting_for_document=false;

  // A document created from inside the GUI callback may not have its 2D
  // editing context until the Qt event loop gets control back. Reuse the
  // same document on the next timer tick instead of creating another one.
  if(g_pending_doc){
    log("pending fragment retry age="+std::to_string(g_pending_age));
    auto cand=g_pending_doc;
    try{
      app.SetActiveDocument(cand);
      cand->SetActive();
      IKompasDocument2DPtr d2=cand;
      if(d2){
        d2->SetParametricMode(true);
        auto vm=d2->GetViewsAndLayersManager();
        auto views=vm?vm->GetViews():IViewsPtr{};
        auto v=views?views->GetActiveView():IViewPtr{};
        IDrawingContainerPtr dcont=v;
        ISymbols2DContainerPtr scont=v;
        auto lines=dcont?dcont->GetLineSegments():ILineSegmentsPtr{};
        auto probe=lines?lines->Add():ILineSegmentPtr{};
        if(probe){
          probe->SetX1(-5);probe->SetY1(-5);probe->SetX2(-1);probe->SetY2(-5);
          probe->SetStyle(ksCSConstruction);
          if(probe->Update()){
            probe->Delete();
            base=cand; doc=d2; view=v; dc=dcont; sc=scont;
            g_pending_doc={};
            g_pending_age=0;
            log("pending fragment PASS editable");
          }else{
            probe->Delete();
          }
        }
      }
    }catch(...){
      log("pending fragment retry EXCEPTION");
    }
    if(!base){
      g_pending_age++;
      if(g_pending_age>20){
        log("FAIL pending fragment never became editable");
        try{cand->Close(kdDoNotSaveChanges);}catch(...){}
        g_pending_doc={};
        g_pending_age=0;
        return false;
      }
      g_waiting_for_document=true;
      log("pending fragment still initializing");
      return false;
    }
  }

  auto adopt=[&](const std::string& label,const IKompasDocumentPtr& cand)->bool{
    log("candidate "+label+" doc="+(cand?"1":"0"));
    if(!cand) return false;
    try{
      app.SetActiveDocument(cand);
      cand->SetActive();
      IKompasDocument2DPtr d2=cand;
      if(!d2){log("candidate "+label+" FAIL cast"); cand->Close(kdDoNotSaveChanges); return false;}
      d2->SetParametricMode(true);
      auto vm=d2->GetViewsAndLayersManager();
      if(!vm){log("candidate "+label+" FAIL manager"); cand->Close(kdDoNotSaveChanges); return false;}
      auto views=vm->GetViews();
      if(!views){log("candidate "+label+" FAIL views"); cand->Close(kdDoNotSaveChanges); return false;}
      auto v=views->GetActiveView();
      if(!v){log("candidate "+label+" FAIL active view"); cand->Close(kdDoNotSaveChanges); return false;}
      v->SetBackground(false);
      v->SetVisible(true);
      v->SetCurrent(true);
      if(!v->Update()) log("candidate "+label+" WARN view Update false");
      log("candidate "+label+" view current="+std::to_string(v->IsCurrent())+
          " background="+std::to_string(v->IsBackground())+
          " visible="+std::to_string(v->IsVisible()));
      IDrawingContainerPtr dcont=v;
      ISymbols2DContainerPtr scont=v;
      if(!dcont||!scont){log("candidate "+label+" FAIL containers"); cand->Close(kdDoNotSaveChanges); return false;}
      auto lines=dcont->GetLineSegments();
      if(!lines){log("candidate "+label+" FAIL line collection"); cand->Close(kdDoNotSaveChanges); return false;}
      auto probe=lines->Add();
      if(!probe){
        log("candidate "+label+" probe Add pending");
        g_pending_doc=cand;
        g_pending_age=0;
        g_waiting_for_document=true;
        return false;
      }
      probe->SetX1(-5);probe->SetY1(-5);probe->SetX2(-1);probe->SetY2(-5);
      probe->SetStyle(ksCSConstruction);
      if(!probe->Update()){log("candidate "+label+" FAIL probe Update"); probe->Delete(); cand->Close(kdDoNotSaveChanges); return false;}
      probe->Delete();
      base=cand; doc=d2; view=v; dc=dcont; sc=scont;
      log("candidate "+label+" PASS editable");
      return true;
    }catch(...){
      log("candidate "+label+" EXCEPTION");
      try{cand->Close(kdDoNotSaveChanges);}catch(...){}
      return false;
    }
  };

  bool acquired=(bool)base;
  if(!acquired) acquired=adopt("AddDefault-visible", docs->AddWithDefaultSettings(ksDocumentFragment,true));
  if(!acquired) acquired=adopt("AddDefault-invisible", docs->AddWithDefaultSettings(ksDocumentFragment,false));
  if(g_waiting_for_document) return false;
  if(!acquired) acquired=adopt("Add-visible", docs->Add(ksDocumentFragment,true));
  if(!acquired) acquired=adopt("Add-invisible", docs->Add(ksDocumentFragment,false));
  if(!acquired) acquired=adopt("Template-visible", docs->AddNewDocumentFromTemplate(templatePath,true));
  if(!acquired) acquired=adopt("Template-invisible", docs->AddNewDocumentFromTemplate(templatePath,false));
  if(!acquired) acquired=adopt("Open-template-visible", docs->Open(templatePath,true,false));
  if(!acquired) acquired=adopt("Open-template-invisible", docs->Open(templatePath,false,false));
  if(!acquired){log("FAIL no editable fragment route");return false;}

  log("using native editable fragment route");
  log("variables will be created by driving dimensions");


  P B,C,D,E,X;
  if(!state(FI0,B,C,D,E,X)){log("FAIL initial state");return false;}
  P A{0,0};

  auto crank=line(dc,A,B,0,ksCSNormal);
  auto rocker=line(dc,C,D,0,ksCSNormal);
  auto rod=line(dc,D,E,0,ksCSNormal);
  auto baseAC=line(dc,A,C,0,ksCSConstruction);
  auto href=line(dc,A,{20,0},0,ksCSConstruction);
  if(!crank||!rocker||!rod||!baseAC||!href){log("FAIL geometry");return false;}

  if(!constr(crank,ksCFixedPoint,0)){log("FAIL fixed A");return false;}
  if(!constr(baseAC,ksCVertical)){log("FAIL vertical AC");return false;}
  if(!constr(href,ksCHorizontal)){log("FAIL horizontal ref");return false;}
  if(!constr(baseAC,ksCMergePoints,0,crank,0)){log("FAIL merge A base-crank");return false;}
  if(!constr(href,ksCMergePoints,0,crank,0)){log("FAIL merge A ref");return false;}
  if(!constr(baseAC,ksCMergePoints,1,rocker,0)){log("FAIL merge C");return false;}
  if(!constr(crank,ksCPointOnCurve,1,rocker,0)){log("FAIL B on CD");return false;}
  if(!constr(rocker,ksCMergePoints,1,rod,0)){log("FAIL merge D");return false;}
  if(!constr(crank,ksCHAlignPoints,0,rod,1)){log("FAIL E horizontal A");return false;}
  log("geometric constraints created");

  log("name-valid l1="+std::to_string(doc->IsVariableNameValid(L"l1"))+
      " l2="+std::to_string(doc->IsVariableNameValid(L"l2"))+
      " l3="+std::to_string(doc->IsVariableNameValid(L"l3"))+
      " L="+std::to_string(doc->IsVariableNameValid(L"L"))+
      " fi="+std::to_string(doc->IsVariableNameValid(L"fi")));

  if(!lin_dim(sc,crank,L"l1",L1,0,7)){log("FAIL dim l1");return false;}
  if(!lin_dim(sc,rocker,L"l2",L2,0,-7)){log("FAIL dim l2");return false;}
  if(!lin_dim(sc,rod,L"l3",L3,0,7)){log("FAIL dim l3");return false;}
  if(!lin_dim(sc,baseAC,L"L",BASE,0,-8)){log("FAIL dim L");return false;}
  if(!angle_dim(sc,href,crank,0,FI0)){log("FAIL dim fi");return false;}
  log("driving dimensions created; variables="+std::to_string(doc->GetVariablesCount(false)));

  auto vl1=doc->GetVariableByName(false,L"l1");
  auto vl2=doc->GetVariableByName(false,L"l2");
  auto vl3=doc->GetVariableByName(false,L"l3");
  auto vL=doc->GetVariableByName(false,L"L");
  auto vfi=doc->GetVariableByName(false,L"fi");
  log(std::string("lookup vars l1=")+(vl1?"1":"0")+
      " l2="+(vl2?"1":"0")+" l3="+(vl3?"1":"0")+
      " L="+(vL?"1":"0")+" fi="+(vfi?"1":"0"));
  if(!vl1||!vl2||!vl3||!vL||!vfi){log("FAIL variables after dimensions");return false;}
  vl1->SetNote(L"Длина кривошипа AB");
  vl2->SetNote(L"Длина звена CD = 2L");
  vl3->SetNote(L"Длина звена DE");
  vL->SetNote(L"Расстояние AC");
  vfi->SetNote(L"Угол поворота кривошипа");
  vl2->SetExpression(L"2*L");
  log("variable expression l2=2*L set");

  if(!doc->UpdateVariables())log("WARN UpdateVariables false");
  if(!doc->CompleteRebuildDocument()){log("FAIL initial complete rebuild");return false;}
  log("initial rebuild PASS");

  // Static study layer, generated from the exact variant-6 kinematics.
  // Trajectory X over one full turn.
  P prev{}; bool have=false;
  for(int deg=0;deg<=360;deg+=5){
    P b,c,d,e,x;
    if(!state(deg==0?0.001:(double)deg,b,c,d,e,x))continue;
    if(have && !line(dc,prev,x,0,ksCSNormal))return false;
    prev=x;have=true;
  }

  // x_E(fi) graph: zero at minimum travel.
  double emin=1e100,emax=-1e100;
  std::vector<std::pair<double,double>> ex;
  for(int deg=0;deg<=360;deg+=5){
    P b,c,d,e,x; if(!state(deg==0?0.001:(double)deg,b,c,d,e,x))continue;
    ex.push_back({(double)deg,e.x}); emin=std::min(emin,e.x);emax=std::max(emax,e.x);
  }
  const double gx=110.0,gy=-10.0,sx=0.20,sy=0.55;
  line(dc,{gx,gy},{gx+360*sx,gy},0,ksCSConstruction);
  line(dc,{gx,gy},{gx,gy+50},0,ksCSConstruction);
  have=false;
  for(auto [deg,e]:ex){
    P p{gx+deg*sx,gy+(e-emin)*sy};
    if(have && !line(dc,prev,p,0,ksCSNormal))return false;
    prev=p;have=true;
  }

  // v_E(t) graph using centered difference, in mm/s.
  const double omega=2*PI*N_RPM/60.0;
  const double period=60.0/N_RPM;
  const double vgY=-70.0, st=280.0, sv=0.005;
  line(dc,{gx,vgY},{gx+period*st,vgY},0,ksCSConstruction);
  line(dc,{gx,vgY-35},{gx,vgY+35},0,ksCSConstruction);
  have=false; double vmax=0;
  for(int deg=5;deg<360;deg+=5){
    P b0,c0,d0,e0,x0,b1,c1,d1,e1,x1;
    state(deg-5,b0,c0,d0,e0,x0); state(deg+5,b1,c1,d1,e1,x1);
    double dphi=10.0*PI/180.0;
    double vel=(e1.x-e0.x)/dphi*omega;
    vmax=std::max(vmax,std::abs(vel));
    double t=deg/360.0*period;
    P p{gx+t*st,vgY+vel*sv};
    if(have && !line(dc,prev,p,0,ksCSNormal))return false;
    prev=p;have=true;
  }

  // Extreme CD positions as construction segments.
  double tmin=1e100,tmax=-1e100,phiMin=0,phiMax=0;
  for(int deg=0;deg<360;deg++){
    P b,c,d,e,x; state(deg==0?0.001:(double)deg,b,c,d,e,x);
    double th=std::atan2(d.y-c.y,d.x-c.x);
    if(th<tmin){tmin=th;phiMin=deg;}
    if(th>tmax){tmax=th;phiMax=deg;}
  }
  line(dc,C,{C.x+L2*std::cos(tmin),C.y+L2*std::sin(tmin)},0,ksCSConstruction);
  line(dc,C,{C.x+L2*std::cos(tmax),C.y+L2*std::sin(tmax)},0,ksCSConstruction);

  log("study layer built; E travel="+std::to_string(emax-emin)+
      " mm; CD swing="+std::to_string((tmax-tmin)*180.0/PI)+
      " deg; vmax~"+std::to_string(vmax)+" mm/s");

  // Real parametric rebuild test.
  auto fi=doc->GetVariableByName(false,L"fi"); if(!fi){log("FAIL fi lookup");return false;}
  auto test=[&](double a,P& Bout)->bool{
    fi->SetValue(a);
    if(!doc->UpdateVariables())log("WARN UpdateVariables at "+std::to_string(a));
    if(!doc->CompleteRebuildDocument())return false;
    Bout={crank->GetX2(),crank->GetY2()};
    log("fi="+std::to_string(a)+" B="+std::to_string(Bout.x)+","+std::to_string(Bout.y));
    return true;
  };
  P b45,b90,b135;
  if(!test(45,b45)){log("FAIL rebuild 45");return false;}
  if(!test(135,b135)){log("FAIL rebuild 135");return false;}
  double moved=std::hypot(b45.x-b135.x,b45.y-b135.y);
  if(moved<5.0){log("FAIL geometry did not move");return false;}
  if(!test(90,b90)){log("FAIL rebuild 90");return false;}

  // Expected crank positions for the two test angles.
  P ec45,cc,dd,ee,xx,ec135;
  state(45,ec45,cc,dd,ee,xx); state(135,ec135,cc,dd,ee,xx);
  if(std::hypot(b45.x-ec45.x,b45.y-ec45.y)>0.5){log("FAIL B45 mismatch");return false;}
  if(std::hypot(b135.x-ec135.x,b135.y-ec135.y)>0.5){log("FAIL B135 mismatch");return false;}

  const std::wstring out=L"/tmp/01_Mekhanizm_Variant_06_PARAMETRIC.frw";
  if(!base->SaveAs(out)){log("FAIL SaveAs");return false;}
  log("SAVE_PASS moved="+std::to_string(moved));
  log("RESULT=PASS_NATIVE_PARAMETRIC_VARIANT06");
  return true;
}


extern "C" __attribute__((visibility("default")))
int run_variant06_writer(){
  if(g_writer_done){
    return 0;
  }
  log("run_variant06_writer entry");
  bool ok=false;
  g_waiting_for_document=false;
  try{ok=build();}
  catch(const std::exception& e){log(std::string("EXCEPTION ")+e.what());}
  catch(...){log("EXCEPTION unknown");}
  if(ok){
    g_writer_done=true;
    log("RUN_WRITER_PASS");
    return 0;
  }
  if(g_waiting_for_document){
    log("RUN_WRITER_PENDING");
    return 3;
  }
  log("RUN_WRITER_FAIL");
  return 1;
}
