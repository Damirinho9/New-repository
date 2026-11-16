#include <KsAPI.h>
#include <ksConstants.h>
#include <chrono>
#include <thread>
#include <fstream>
#include <cmath>
#include <vector>
#include <string>
#include <unistd.h>

using namespace ksapi;

static std::ofstream logstream("/tmp/work1_inject.log", std::ios::out | std::ios::app);

static void log(const std::string& s) {
  logstream << s << std::endl;
  logstream.flush();
}

struct P { double x, y; };

static constexpr double PI = 3.14159265358979323846;
static constexpr double L1 = 15.0;
static constexpr double L2 = 55.0;
static constexpr double L3 = 80.0;
static constexpr double BASE = 75.0;
static constexpr double N_RPM = 100.0;

static bool state(double deg, P& B, P& C, P& E, double& r, double& theta) {
  double ph = deg * PI / 180.0;
  B = {L1*std::cos(ph), L1*std::sin(ph)};
  double qx=B.x-BASE, qy=B.y;
  double d=std::hypot(qx,qy);
  double t=d*d-L2*L2;
  if(t <= 0) return false;
  r=std::sqrt(t);
  double tq=std::atan2(qy,qx);
  double ca=r/d;
  if(ca<-1 || ca>1) return false;
  double a=std::acos(ca);
  theta=tq-a;
  C={BASE+r*std::cos(theta), r*std::sin(theta)};
  E={BASE+L3*std::cos(theta), L3*std::sin(theta)};
  return true;
}

static ILayerPtr make_layer(const IViewPtr& view, int num, const std::wstring& name) {
  auto layers=view->GetLayers();
  if(!layers) return {};
  auto l=layers->GetLayerByNumber(num);
  if(!l) l=layers->Add();
  if(!l) return {};
  l->SetLayerNumber(num);
  l->SetName(name);
  l->SetVisible(true);
  l->SetBackground(false);
  l->SetPrintable(true);
  l->SetCurrent();
  if(!l->Update()) return {};
  return l;
}

static ILineSegmentPtr make_line(const IDrawingContainerPtr& dc, P a, P b, int layer, int style) {
  auto col=dc->GetLineSegments();
  if(!col) return {};
  auto s=col->Add();
  if(!s) return {};
  s->SetX1(a.x); s->SetY1(a.y); s->SetX2(b.x); s->SetY2(b.y);
  s->SetLayerNumber(layer);
  s->SetStyle(style);
  if(!s->Update()) return {};
  return s;
}

static bool constraint(const IDrawingObjectPtr& obj, ksConstraintTypeEnum typ,
                       int idx=-1, const IDrawingObjectPtr& partner={},
                       int partnerIdx=-1) {
  auto c=obj->NewConstraint();
  if(!c) return false;
  c->SetConstraintType(typ);
  if(idx>=0) c->SetIndex(idx);
  if(partner) c->SetPartners({partner});
  if(partnerIdx>=0) c->SetPartnerIndex(partnerIdx);
  bool ok=c->Create();
  if(!ok) c->Delete();
  return ok;
}

static ILineDimensionPtr make_linear_dim(const ISymbols2DContainerPtr& sc,
                                         const ILineSegmentPtr& seg,
                                         const std::wstring& var,
                                         double value, int layer, double offset) {
  auto dims=sc->GetLineDimensions();
  if(!dims) return {};
  auto d=dims->Add();
  if(!d) return {};
  double x1=seg->GetX1(), y1=seg->GetY1(), x2=seg->GetX2(), y2=seg->GetY2();
  double dx=x2-x1, dy=y2-y1, len=std::hypot(dx,dy);
  double nx = len ? -dy/len : 0.0;
  double ny = len ? dx/len : 1.0;
  d->SetX1(x1); d->SetY1(y1); d->SetX2(x2); d->SetY2(y2);
  d->SetX3((x1+x2)/2.0 + nx*offset);
  d->SetY3((y1+y2)/2.0 + ny*offset);
  d->SetOrientation(ksLinDParallel);
  d->SetLayerNumber(layer);
  if(!d->Update()) return {};
  d->Associate();

  auto f=d->NewConstraint();
  if(!f) return {};
  f->SetConstraintType(ksCFixedDim);
  if(!f->Create()) return {};

  auto v=d->NewConstraint();
  if(!v) return {};
  v->SetConstraintType(ksCDimWithVariable);
  v->SetConstraintValue(value);
  v->SetVariable(var);
  v->SetComment(L"Управляющий размер");
  if(!v->Create()) return {};
  return d;
}

static IAngleDimensionPtr make_angle_dim(const ISymbols2DContainerPtr& sc,
                                         const ILineSegmentPtr& base,
                                         const ILineSegmentPtr& crank,
                                         int layer, double value) {
  auto col=sc->GetAngleDimensions();
  if(!col) return {};
  auto d=col->Add(ksDrADimension);
  if(!d) return {};
  d->SetXc(0); d->SetYc(0);
  d->SetX1(base->GetX2()); d->SetY1(base->GetY2());
  d->SetX2(crank->GetX2()); d->SetY2(crank->GetY2());
  d->SetAngle1(0); d->SetAngle2(0);
  d->SetRadius(24.0);
  d->SetDimensionType(ksADMinAngle);
  d->SetDirection(false);
  d->SetLayerNumber(layer);
  if(!d->Update()) return {};
  d->Associate();

  auto f=d->NewConstraint();
  if(!f) return {};
  f->SetConstraintType(ksCFixedDim);
  if(!f->Create()) return {};

  auto v=d->NewConstraint();
  if(!v) return {};
  v->SetConstraintType(ksCDimWithVariable);
  v->SetConstraintValue(value);
  v->SetVariable(L"fi");
  v->SetComment(L"Угол поворота кривошипа");
  if(!v->Create()) return {};
  return d;
}

static bool build() {
  log("writer thread started");
  IApplication& app=GetKompasApplication();
  log("GetKompasApplication returned");

  int maj=0,min=0,rel=0,bld=0;
  app.GetSystemVersion(maj,min,rel,bld);
  log("KOMPAS version="+std::to_string(maj)+"."+std::to_string(min)+" build="+std::to_string(bld));
  app.SetHideMessage(ksHideMessageYes);

  auto docs=app.GetDocuments();
  if(!docs){ log("FAIL: no documents"); return false; }
  auto baseDoc=docs->Add(ksDocumentFragment, false);
  if(!baseDoc){ log("FAIL: add fragment"); return false; }
  IKompasDocument2DPtr doc=baseDoc;
  if(!doc){ log("FAIL: cast IKompasDocument2D"); return false; }
  app.SetActiveDocument(baseDoc);
  doc->SetParametricMode(true);
  log("fragment created");

  auto vlm=doc->GetViewsAndLayersManager();
  if(!vlm){ log("FAIL: views manager"); return false; }
  auto views=vlm->GetViews();
  if(!views){ log("FAIL: views"); return false; }
  auto view=views->GetActiveView();
  if(!view){ log("FAIL: active view"); return false; }
  IDrawingContainerPtr dc=view;
  ISymbols2DContainerPtr sc=view;
  if(!dc || !sc){ log("FAIL: containers"); return false; }

  auto lc=make_layer(view,1,L"Контуры");
  auto ld=make_layer(view,2,L"Размеры");
  auto la=make_layer(view,3,L"Вспомогательные построения");
  auto li=make_layer(view,4,L"Исследование");
  if(!lc||!ld||!la||!li){ log("FAIL: layers"); return false; }
  log("layers created");

  // User variables are explicit and visible in the document variable table.
  auto vl1=doc->AddVariable(L"l1",L1,L"Длина кривошипа");
  auto vl2=doc->AddVariable(L"l2",L2,L"Длина звена BC");
  auto vl3=doc->AddVariable(L"l3",L3,L"Длина коромысла");
  auto vL =doc->AddVariable(L"L",BASE,L"Межосевое расстояние AD");
  auto vfi=doc->AddVariable(L"fi",90.0,L"Угол поворота кривошипа");
  if(!vl1||!vl2||!vl3||!vL||!vfi){ log("FAIL: variables"); return false; }
  log("variables created");

  P B,C,E; double r,th;
  if(!state(90.0,B,C,E,r,th)){ log("FAIL: initial state"); return false; }
  P A{0,0}, D{BASE,0};

  auto crank=make_line(dc,A,B,1,ksCSNormal);
  auto coupler=make_line(dc,B,C,1,ksCSNormal);
  auto rocker=make_line(dc,D,E,1,ksCSNormal);
  auto base=make_line(dc,A,D,3,ksCSConstruction);
  if(!crank||!coupler||!rocker||!base){ log("FAIL: lines"); return false; }
  log("mechanism lines created");

  if(!constraint(crank,ksCFixedPoint,0)) { log("FAIL: fixed A"); return false; }
  if(!constraint(base,ksCHorizontal)) { log("FAIL: horizontal AD"); return false; }
  if(!constraint(base,ksCMergePoints,0,crank,0)) { log("FAIL: merge A"); return false; }
  if(!constraint(base,ksCMergePoints,1,rocker,0)) { log("FAIL: merge D"); return false; }
  if(!constraint(coupler,ksCMergePoints,0,crank,1)) { log("FAIL: merge B"); return false; }
  if(!constraint(coupler,ksCPointOnCurve,1,rocker,0)) { log("FAIL: C on rocker"); return false; }
  if(!constraint(coupler,ksCPerpendicular,-1,rocker,-1)) { log("FAIL: perpendicular"); return false; }
  log("geometric constraints created");

  if(!make_linear_dim(sc,crank,L"l1",L1,2,10)) { log("FAIL: dim l1"); return false; }
  if(!make_linear_dim(sc,coupler,L"l2",L2,2,10)) { log("FAIL: dim l2"); return false; }
  if(!make_linear_dim(sc,rocker,L"l3",L3,2,10)) { log("FAIL: dim l3"); return false; }
  if(!make_linear_dim(sc,base,L"L",BASE,2,-12)) { log("FAIL: dim L"); return false; }
  if(!make_angle_dim(sc,base,crank,2,90.0)) { log("FAIL: dim fi"); return false; }
  log("driving dimensions created");

  if(!doc->UpdateVariables()) log("WARN: UpdateVariables false");
  if(!doc->RebuildDocument()) { log("FAIL: initial rebuild"); return false; }
  log("initial rebuild PASS");

  // Study layer: trajectory C.
  P firstC{}, prevC{}; bool have=false;
  for(int deg=0; deg<=360; deg+=10){
    P b,c,e; double rr,tt;
    if(!state(deg==0?0.001:double(deg),b,c,e,rr,tt)) continue;
    if(!have){ firstC=c; prevC=c; have=true; }
    else { if(!make_line(dc,prevC,c,4,ksCSNormal)) return false; prevC=c; }
  }
  if(have) make_line(dc,prevC,firstC,4,ksCSNormal);

  // Displacement graph x(fi), shifted right.
  double rmin=std::sqrt((BASE-L1)*(BASE-L1)-L2*L2);
  P prevX{}; bool hx=false;
  for(int deg=0; deg<=360; deg+=5){
    double ph=deg*PI/180.0;
    double rr=std::sqrt(BASE*BASE+L1*L1-2*BASE*L1*std::cos(ph)-L2*L2);
    P p{130.0+deg*0.25, (rr-rmin)};
    if(hx) make_line(dc,prevX,p,4,ksCSNormal);
    prevX=p; hx=true;
  }
  make_line(dc,{130,0},{220,0},4,ksCSConstruction);
  make_line(dc,{130,0},{130,55},4,ksCSConstruction);

  // Velocity graph v(t), shifted lower.
  double omega=2*PI*N_RPM/60.0;
  double period=60.0/N_RPM;
  P prevV{}; bool hv=false;
  for(int deg=0; deg<=360; deg+=5){
    double ph=deg*PI/180.0;
    double rr=std::sqrt(BASE*BASE+L1*L1-2*BASE*L1*std::cos(ph)-L2*L2);
    double vel=(BASE*L1*std::sin(ph)/rr)*omega;
    double t=deg/360.0*period;
    P p{130.0+t*140.0, -80.0+vel*0.12};
    if(hv) make_line(dc,prevV,p,4,ksCSNormal);
    prevV=p; hv=true;
  }
  make_line(dc,{130,-80},{130+period*140,-80},4,ksCSConstruction);
  make_line(dc,{130,-115},{130,-45},4,ksCSConstruction);
  log("study curves created");

  // Real parametric rebuild check.
  auto fi=doc->GetVariableByName(false,L"fi");
  if(!fi){ log("FAIL: fi lookup"); return false; }

  fi->SetValue(45.0);
  doc->UpdateVariables();
  if(!doc->RebuildDocument()){ log("FAIL: rebuild 45"); return false; }
  P b45{crank->GetX2(),crank->GetY2()};
  log("B45="+std::to_string(b45.x)+","+std::to_string(b45.y));

  fi->SetValue(135.0);
  doc->UpdateVariables();
  if(!doc->RebuildDocument()){ log("FAIL: rebuild 135"); return false; }
  P b135{crank->GetX2(),crank->GetY2()};
  log("B135="+std::to_string(b135.x)+","+std::to_string(b135.y));

  double moved=std::hypot(b45.x-b135.x,b45.y-b135.y);
  if(moved < 1.0){ log("FAIL: geometry did not move"); return false; }

  fi->SetValue(90.0);
  doc->UpdateVariables();
  if(!doc->RebuildDocument()){ log("FAIL: rebuild 90"); return false; }

  const std::wstring out=L"/tmp/Work1_Parametric_Native.frw";
  if(!doc->SaveAs(out)){ log("FAIL: SaveAs"); return false; }
  log("SAVE_PASS moved="+std::to_string(moved));
  log("RESULT=PASS_NATIVE_PARAMETRIC_FRW");
  return true;
}

__attribute__((constructor))
static void entry() {
  log("preload constructor");
  std::thread([](){
    std::this_thread::sleep_for(std::chrono::seconds(18));
    bool ok=false;
    try { ok=build(); }
    catch(const std::exception& e){ log(std::string("EXCEPTION: ")+e.what()); }
    catch(...){ log("EXCEPTION: unknown"); }
    log(ok ? "THREAD_DONE_PASS" : "THREAD_DONE_FAIL");
    logstream.flush();
    // Give KOMPAS enough time to flush the file; workflow will terminate process.
  }).detach();
}

// relink-trigger
