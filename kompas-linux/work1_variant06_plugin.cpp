#include <KsAPI.h>
#include <KompasLibraryActions.h>
#include <cmath>
#include <fstream>
#include <string>
#include <vector>
#include <algorithm>
#include <filesystem>

using namespace ksapi;

static std::ofstream g("/tmp/work1_variant06_plugin.log", std::ios::out | std::ios::app);
static bool ran=false;
static void log(const std::string& s){ g<<s<<std::endl; g.flush(); }

struct P{double x,y;};
static constexpr double PI=3.14159265358979323846;
static constexpr double L1=20.0, LL=25.0, L2=50.0, L3=60.0, DX=20.0, N=250.0, FI0=90.0;

static bool state(double deg,P& A,P& B,P& C,P& D,P& E,P& X){
  double ph=deg*PI/180.0;
  A={0,0}; C={0,-LL};
  B={L1*std::cos(ph),L1*std::sin(ph)};
  double vx=B.x-C.x, vy=B.y-C.y, d=std::hypot(vx,vy);
  if(d<1e-9) return false;
  D={C.x+L2*vx/d,C.y+L2*vy/d};
  double q=L3*L3-D.y*D.y;
  if(q<0) return false;
  E={D.x+std::sqrt(q),0};
  X={D.x+(DX/L3)*(E.x-D.x),D.y+(DX/L3)*(E.y-D.y)};
  return true;
}

static ILayerPtr mkLayer(const IViewPtr& v,const std::wstring& name){
  auto ls=v->GetLayers(); if(!ls) return {};
  auto l=ls->Add(); if(!l) return {};
  l->SetName(name); l->SetBackground(false); l->SetVisible(true); l->SetPrintable(true); l->SetCurrent();
  if(!l->Update()) return {};
  log("layer created: "+std::to_string(l->GetLayerNumber()));
  return l;
}

static ILineSegmentPtr seg(const IDrawingContainerPtr& dc,P a,P b,int style,int layer){
  auto col=dc->GetLineSegments(); if(!col){log("FAIL GetLineSegments");return {};}
  auto s=col->Add(); if(!s){log("FAIL LineSegments.Add");return {};}
  s->SetX1(a.x);s->SetY1(a.y);s->SetX2(b.x);s->SetY2(b.y);s->SetStyle(style);
  if(layer>0)s->SetLayerNumber(layer);
  if(!s->Update()){log("FAIL segment Update");return {};}
  return s;
}

static bool con(const IDrawingObjectPtr& o, ksConstraintTypeEnum t,
                const std::vector<IDrawingObjectPtr>& partners={},
                int idx=-1,int pidx=-1,const std::wstring& name=L"",
                double value=0,bool hasValue=false,const std::wstring& expr=L""){
  auto c=o->NewConstraint(); if(!c){log("FAIL NewConstraint type="+std::to_string((int)t));return false;}
  c->SetConstraintType(t);
  if(idx>=0)c->SetIndex(idx);
  if(pidx>=0)c->SetPartnerIndex(pidx);
  if(!partners.empty())c->SetPartners(partners);
  if(!name.empty())c->SetVariable(name);
  if(hasValue)c->SetConstraintValue(value);
  if(!expr.empty())c->SetExpression(expr);
  bool ok=c->Create();
  log("constraint "+std::to_string((int)t)+" create="+std::to_string(ok)+" valid="+std::to_string(ok?c->IsValid():0));
  if(!ok)c->Delete();
  return ok && c->IsValid();
}

static ILineDimensionPtr ldim(const ISymbols2DContainerPtr& sc,
                              P a,P b,P text,
                              ksLineDimensionOrientationEnum orient,
                              const ILineSegmentPtr& measured,
                              const std::wstring& name,double value,int layer){
  auto ds=sc->GetLineDimensions(); if(!ds){log("FAIL GetLineDimensions");return {};}
  auto d=ds->Add(); if(!d){log("FAIL LineDimension.Add");return {};}
  d->SetX1(a.x);d->SetY1(a.y);d->SetX2(b.x);d->SetY2(b.y);d->SetX3(text.x);d->SetY3(text.y);
  d->SetOrientation(orient); if(layer>0)d->SetLayerNumber(layer);
  if(!d->Update()){log("FAIL line dim Update");return {};}
  if(!d->Associate()){log("FAIL line dim Associate");return {};}
  log("line dim Associate PASS");
  if(!con(d,ksCFixedDim)){log("FAIL fixed dim");return {};}
  if(!con(d,ksCDimWithVariable,{},-1,-1,name,value,true)){log("FAIL variable dim");return {};}
  return d;
}

static IAngleDimensionPtr adim(const ISymbols2DContainerPtr& sc,
                               const ILineSegmentPtr& base,const ILineSegmentPtr& crank,
                               P pos,const std::wstring& name,double value,int layer){
  auto ds=sc->GetAngleDimensions(); if(!ds){log("FAIL GetAngleDimensions");return {};}
  auto d=ds->Add(ksDrADimension); if(!d){log("FAIL AngleDimension.Add");return {};}
  d->SetBaseObject1(base); d->SetBaseObject2(crank); d->SetX3(pos.x); d->SetY3(pos.y);
  if(layer>0)d->SetLayerNumber(layer);
  if(!d->Update()){log("FAIL angle dim Update");return {};}
  if(!con(d,ksCFixedDim)){log("FAIL angle fixed");return {};}
  if(!con(d,ksCDimWithVariable,{},-1,-1,name,value,true)){log("FAIL angle variable");return {};}
  return d;
}

static bool build(IApplication& app){
  log("BUILD_BEGIN");
  auto docs=app.GetDocuments(); if(!docs){log("FAIL documents");return false;}
  auto base=docs->AddWithDefaultSettings(ksDocumentFragment,true);
  log(std::string("AddWithDefaultSettings=")+(base?"non-null":"null"));
  if(!base) return false;
  app.SetActiveDocument(base);
  IKompasDocument2DPtr d2=base; if(!d2){log("FAIL cast 2D");return false;}
  d2->SetParametricMode(true);
  log("parametric="+std::to_string(d2->IsParametricMode()));
  auto vm=d2->GetViewsAndLayersManager(); if(!vm)return false;
  auto view=vm->GetViews()->GetActiveView(); if(!view){log("FAIL view");return false;}
  IDrawingContainerPtr dc(view); ISymbols2DContainerPtr sc(view);
  if(!dc||!sc){log("FAIL containers");return false;}

  auto lc=mkLayer(view,L"Контуры");
  auto ld=mkLayer(view,L"Размеры");
  auto la=mkLayer(view,L"Вспомогательные построения");
  auto li=mkLayer(view,L"Исследование");
  if(!lc||!ld||!la||!li){log("FAIL layers");return false;}
  int nC=lc->GetLayerNumber(),nD=ld->GetLayerNumber(),nA=la->GetLayerNumber(),nI=li->GetLayerNumber();

  P A,B,C,D,E,X; if(!state(FI0,A,B,C,D,E,X))return false;
  auto crank=seg(dc,A,B,ksCSNormal,nC);
  auto rocker=seg(dc,C,D,ksCSNormal,nC);
  auto rod=seg(dc,D,E,ksCSNormal,nC);
  auto ac=seg(dc,A,C,ksCSConstruction,nA);
  auto href=seg(dc,A,{20,0},ksCSConstruction,nA);
  if(!crank||!rocker||!rod||!ac||!href){log("FAIL base geometry");return false;}
  log("geometry PASS");

  if(!con(crank,ksCFixedPoint,{},0))return false;
  if(!con(ac,ksCVertical))return false;
  if(!con(href,ksCHorizontal))return false;
  if(!con(href,ksCFixedLenght))return false;
  if(!con(ac,ksCMergePoints,{crank},0,0))return false;
  if(!con(href,ksCMergePoints,{crank},0,0))return false;
  if(!con(ac,ksCMergePoints,{rocker},1,0))return false;
  if(!con(crank,ksCPointOnCurve,{rocker},1,0))return false;
  if(!con(rocker,ksCMergePoints,{rod},1,0))return false;
  if(!con(crank,ksCHAlignPoints,{rod},0,1))return false;
  log("geometric constraints PASS");

  auto dl1=ldim(sc,A,B,{-10,10},ksLinDParallel,crank,L"l1",L1,nD);
  auto dL=ldim(sc,A,C,{-12,-12},ksLinDParallel,ac,L"L",LL,nD);
  auto dl2=ldim(sc,C,D,{-10,20},ksLinDParallel,rocker,L"l2",L2,nD);
  auto dl3=ldim(sc,D,E,{45,25},ksLinDParallel,rod,L"l3",L3,nD);
  auto dfi=adim(sc,href,crank,{13,13},L"fi",FI0,nD);
  if(!dl1||!dL||!dl2||!dl3||!dfi){log("FAIL dimensions");return false;}
  log("dimensions PASS");

  auto vl1=view->GetDimensionVariable(dl1);
  auto vL=view->GetDimensionVariable(dL);
  auto vl2=view->GetDimensionVariable(dl2);
  auto vl3=view->GetDimensionVariable(dl3);
  auto vfi=view->GetDimensionVariable(dfi);
  if(!vl1||!vL||!vl2||!vl3||!vfi){log("FAIL GetDimensionVariable");return false;}
  log("vars l1="+std::to_string(vl1->GetValue())+" L="+std::to_string(vL->GetValue())+
      " l2="+std::to_string(vl2->GetValue())+" l3="+std::to_string(vl3->GetValue())+
      " fi="+std::to_string(vfi->GetValue()));

  // Symbolic relation required by variant statement l2=2L.
  vl2->SetExpression(L"2*L");
  if(!d2->CompleteRebuildDocument()){log("FAIL rebuild after l2 expression");return false;}
  log("l2 expr="+std::string(vl2->GetExpression().begin(),vl2->GetExpression().end()));

  auto test=[&](double a,P& out)->bool{
    vfi->SetExpression(std::to_wstring(a));
    vfi->SetValue(a);
    if(!d2->CompleteRebuildDocument()){log("FAIL rebuild fi="+std::to_string(a));return false;}
    out={crank->GetX2(),crank->GetY2()};
    log("fi="+std::to_string(a)+" B="+std::to_string(out.x)+","+std::to_string(out.y));
    P aa,bb,cc,dd,ee,xx; state(a,aa,bb,cc,dd,ee,xx);
    return std::hypot(out.x-bb.x,out.y-bb.y)<0.5;
  };
  P b45,b135,b90;
  if(!test(45,b45)||!test(135,b135)||!test(90,b90)){log("FAIL parametric test");return false;}
  double moved=std::hypot(b45.x-b135.x,b45.y-b135.y);
  if(moved<5){log("FAIL no movement");return false;}
  log("PARAMETRIC_REBUILD_PASS moved="+std::to_string(moved));

  // Study layer: trajectory X.
  P prev{}; bool have=false;
  for(int deg=0;deg<=360;deg+=5){
    P a,b,c,d,e,x; if(!state(deg==0?0.001:deg,a,b,c,d,e,x))continue;
    if(have && !seg(dc,prev,x,ksCSNormal,nI))return false;
    prev=x;have=true;
  }

  // Slider displacement.
  std::vector<std::pair<double,double>> es;
  double emin=1e100,emax=-1e100;
  for(int deg=0;deg<=360;deg+=5){
    P a,b,c,d,e,x;state(deg==0?0.001:deg,a,b,c,d,e,x);
    es.push_back({(double)deg,e.x});emin=std::min(emin,e.x);emax=std::max(emax,e.x);
  }
  double gx=110,gy=-10,sx=.20,sy=.55;
  seg(dc,{gx,gy},{gx+72,gy},ksCSConstruction,nI);seg(dc,{gx,gy},{gx,gy+50},ksCSConstruction,nI);
  have=false;
  for(auto [deg,ex]:es){P p{gx+deg*sx,gy+(ex-emin)*sy};if(have&&!seg(dc,prev,p,ksCSNormal,nI))return false;prev=p;have=true;}

  // Velocity.
  double omega=2*PI*N/60.0, period=60.0/N, vy0=-70, st=280, sv=.005, vmax=0;
  seg(dc,{gx,vy0},{gx+period*st,vy0},ksCSConstruction,nI);
  seg(dc,{gx,vy0-35},{gx,vy0+35},ksCSConstruction,nI);
  have=false;
  for(int deg=5;deg<360;deg+=5){
    P a,b,c,d,e0,x,e1;state(deg-5,a,b,c,d,e0,x);state(deg+5,a,b,c,d,e1,x);
    double vel=(e1.x-e0.x)/((10.0*PI/180.0))*omega;vmax=std::max(vmax,std::abs(vel));
    P p{gx+(deg/360.0*period)*st,vy0+vel*sv};if(have&&!seg(dc,prev,p,ksCSNormal,nI))return false;prev=p;have=true;
  }

  // Rocker angular swing.
  double amin=1e100,amax=-1e100;
  for(int deg=0;deg<360;++deg){P a,b,c,d,e,x;state(deg==0?0.001:deg,a,b,c,d,e,x);double th=std::atan2(d.y-c.y,d.x-c.x);amin=std::min(amin,th);amax=std::max(amax,th);}
  seg(dc,C,{C.x+L2*std::cos(amin),C.y+L2*std::sin(amin)},ksCSConstruction,nI);
  seg(dc,C,{C.x+L2*std::cos(amax),C.y+L2*std::sin(amax)},ksCSConstruction,nI);

  log("travel_E="+std::to_string(emax-emin));
  log("swing_CD_deg="+std::to_string((amax-amin)*180.0/PI));
  log("vmax_mm_s="+std::to_string(vmax));

  std::wstring out=L"/tmp/01_Mekhanizm_Variant_06_PARAMETRIC.frw";
  std::filesystem::remove("/tmp/01_Mekhanizm_Variant_06_PARAMETRIC.frw");
  if(!base->SaveAs(out)){log("FAIL SaveAs");return false;}
  if(!std::filesystem::exists("/tmp/01_Mekhanizm_Variant_06_PARAMETRIC.frw")){log("FAIL output missing");return false;}
  log("SAVE_PASS bytes="+std::to_string(std::filesystem::file_size("/tmp/01_Mekhanizm_Variant_06_PARAMETRIC.frw")));
  log("RESULT=PASS_NATIVE_PARAMETRIC_VARIANT06");
  return true;
}

void RunCommand(unsigned int, ksRunCommandModeEnum){}

APP_EXP_FUNC(bool) LoadKompasLibrary(IApplication& app, IKompasLibraryActions& actions){
  actions.AddRunCommandHandler(RunCommand);
  log("LoadKompasLibrary");
  if(!ran){
    ran=true;
    bool ok=false;
    try{ok=build(app);}catch(const std::exception& e){log(std::string("EXCEPTION ")+e.what());}
    catch(...){log("EXCEPTION unknown");}
    log(ok?"PLUGIN_DONE_PASS":"PLUGIN_DONE_FAIL");
  }
  return true;
}

APP_EXP_FUNC(void) UnloadKompasLibrary(){ log("UnloadKompasLibrary"); }
