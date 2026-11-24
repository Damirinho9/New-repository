#include <KsAPI.h>
#include <ksConstants.h>
#include <chrono>
#include <thread>
#include <fcntl.h>
#include <pthread.h>
#include <dlfcn.h>
#include <unistd.h>
#include <cmath>
#include <vector>
#include <string>
#include <algorithm>

using namespace ksapi;

static void log(const std::string& s){
  int fd=::open("/tmp/work1_v6_inject.log", O_CREAT|O_WRONLY|O_APPEND, 0644);
  if(fd>=0){
    ::write(fd,s.data(),s.size());
    ::write(fd,"\n",1);
    ::close(fd);
  }
}

using GetAppFn = ksapi::IApplication& (*)();

static ksapi::IApplication* lazy_app(){
  log("lazy_app: dlopen libksAPI");
  void* h=::dlopen("/opt/ascon/kompas3d-v25/Bin/libksAPI.so", RTLD_NOW|RTLD_GLOBAL);
  if(!h){ log(std::string("FAIL dlopen: ")+(::dlerror()?::dlerror():"unknown")); return nullptr; }
  ::dlerror();
  void* p=::dlsym(h,"_Z20GetKompasApplicationv");
  const char* e=::dlerror();
  if(e||!p){ log(std::string("FAIL dlsym: ")+(e?e:"null")); return nullptr; }
  auto fn=reinterpret_cast<GetAppFn>(p);
  log("lazy_app: calling GetKompasApplication");
  return &fn();
}

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
  if(!ls){ log("LAYER "+std::to_string(n)+" FAIL GetLayers"); return {}; }

  auto x=ls->GetLayerByNumber(n);
  bool created=false;
  if(!x){
    x=ls->Add();
    created=true;
  }
  if(!x){ log("LAYER "+std::to_string(n)+" FAIL Add"); return {}; }

  x->SetLayerNumber(n);
  x->SetName(name);
  x->SetVisible(true);
  x->SetBackground(false);
  x->SetPrintable(true);

  // ASCON SDK: a layer returned by ILayers::Add is created in the
  // document only after IDrawingObject::Update.
  if(!x->Update()){
    log("LAYER "+std::to_string(n)+" FAIL Update created="+std::to_string(created));
    return {};
  }

  x->SetCurrent();
  log("LAYER "+std::to_string(n)+" PASS name="+std::to_string((int)name.size()));
  return x;
}

static ILineSegmentPtr line(const IDrawingContainerPtr& dc,P a,P b,int lay,int style){
  auto col=dc->GetLineSegments(); if(!col) return {};
  auto s=col->Add(); if(!s) return {};
  s->SetX1(a.x); s->SetY1(a.y); s->SetX2(b.x); s->SetY2(b.y);
  s->SetLayerNumber(lay); s->SetStyle(style);
  if(!s->Update()) return {};
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
  auto col=sc->GetLineDimensions(); if(!col) return {};
  auto d=col->Add(); if(!d) return {};
  double x1=seg->GetX1(),y1=seg->GetY1(),x2=seg->GetX2(),y2=seg->GetY2();
  double dx=x2-x1,dy=y2-y1,le=std::hypot(dx,dy); if(le<1e-9)return {};
  double nx=-dy/le,ny=dx/le;
  d->SetX1(x1);d->SetY1(y1);d->SetX2(x2);d->SetY2(y2);
  d->SetX3((x1+x2)/2+nx*off); d->SetY3((y1+y2)/2+ny*off);
  d->SetAngle(std::atan2(dy,dx)*180.0/PI);
  d->SetOrientation(ksLinDParallel); d->SetLayerNumber(lay);
  if(!d->Update())return {};
  if(!constr(d,ksCMergePoints,0,seg,0))return {};
  if(!constr(d,ksCMergePoints,1,seg,1))return {};
  if(!constr(d,ksCFixedDim))return {};
  auto v=d->NewConstraint(); if(!v)return {};
  v->SetConstraintType(ksCDimWithVariable); v->SetConstraintValue(val);
  v->SetVariable(var); v->SetComment(L"Управляющий размер");
  if(!v->Create())return {};
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
  d->SetDirection(false); d->SetLayerNumber(lay);
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
  IApplication* appp=lazy_app();
  if(!appp){ log("FAIL lazy_app"); return false; }
  IApplication& app=*appp;
  log("GetKompasApplication ok");
  int ma=0,mi=0,re=0,bu=0; app.GetSystemVersion(ma,mi,re,bu);
  log("version="+std::to_string(ma)+"."+std::to_string(mi)+" build="+std::to_string(bu));
  app.SetHideMessage(ksHideMessageYes);

  auto docs=app.GetDocuments(); if(!docs){log("FAIL docs");return false;}
  auto base=docs->Add(ksDocumentFragment,false); if(!base){log("FAIL add");return false;}
  IKompasDocument2DPtr doc=base; if(!doc){log("FAIL cast");return false;}
  app.SetActiveDocument(base); doc->SetParametricMode(true);

  auto vm=doc->GetViewsAndLayersManager(); if(!vm)return false;
  auto views=vm->GetViews(); if(!views)return false;
  auto view=views->GetActiveView(); if(!view)return false;
  IDrawingContainerPtr dc=view; ISymbols2DContainerPtr sc=view;
  if(!dc||!sc){log("FAIL containers");return false;}

  if(!layer(view,1,L"Контуры механизма")||!layer(view,2,L"Размеры")||
     !layer(view,3,L"Вспомогательные построения")||!layer(view,4,L"Исследование")){
    log("FAIL layers");return false;
  }

  auto vl1=doc->AddVariable(L"l1",L1,L"Длина кривошипа AB");
  auto vl2=doc->AddVariable(L"l2",L2,L"Длина звена CD = 2L");
  auto vl3=doc->AddVariable(L"l3",L3,L"Длина звена DE");
  auto vL=doc->AddVariable(L"L",BASE,L"Расстояние AC");
  auto vfi=doc->AddVariable(L"fi",FI0,L"Угол поворота кривошипа");
  auto vdx=doc->AddVariable(L"DX",DX,L"Расстояние от D до исследуемой точки X");
  if(!vl1||!vl2||!vl3||!vL||!vfi||!vdx){log("FAIL variables");return false;}
  vl2->SetExpression(L"2*L");
  log("variables created");

  P B,C,D,E,X;
  if(!state(FI0,B,C,D,E,X)){log("FAIL initial state");return false;}
  P A{0,0};

  auto crank=line(dc,A,B,1,ksCSNormal);
  auto rocker=line(dc,C,D,1,ksCSNormal);
  auto rod=line(dc,D,E,1,ksCSNormal);
  auto baseAC=line(dc,A,C,3,ksCSConstruction);
  auto href=line(dc,A,{20,0},3,ksCSConstruction);
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

  if(!lin_dim(sc,crank,L"l1",L1,2,7)){log("FAIL dim l1");return false;}
  if(!lin_dim(sc,rocker,L"l2",L2,2,-7)){log("FAIL dim l2");return false;}
  if(!lin_dim(sc,rod,L"l3",L3,2,7)){log("FAIL dim l3");return false;}
  if(!lin_dim(sc,baseAC,L"L",BASE,2,-8)){log("FAIL dim L");return false;}
  if(!angle_dim(sc,href,crank,2,FI0)){log("FAIL dim fi");return false;}
  log("driving dimensions created");

  if(!doc->UpdateVariables())log("WARN UpdateVariables false");
  if(!doc->CompleteRebuildDocument()){log("FAIL initial complete rebuild");return false;}
  log("initial rebuild PASS");

  // Static study layer, generated from the exact variant-6 kinematics.
  // Trajectory X over one full turn.
  P prev{}; bool have=false;
  for(int deg=0;deg<=360;deg+=5){
    P b,c,d,e,x;
    if(!state(deg==0?0.001:(double)deg,b,c,d,e,x))continue;
    if(have && !line(dc,prev,x,4,ksCSNormal))return false;
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
  line(dc,{gx,gy},{gx+360*sx,gy},4,ksCSConstruction);
  line(dc,{gx,gy},{gx,gy+50},4,ksCSConstruction);
  have=false;
  for(auto [deg,e]:ex){
    P p{gx+deg*sx,gy+(e-emin)*sy};
    if(have && !line(dc,prev,p,4,ksCSNormal))return false;
    prev=p;have=true;
  }

  // v_E(t) graph using centered difference, in mm/s.
  const double omega=2*PI*N_RPM/60.0;
  const double period=60.0/N_RPM;
  const double vgY=-70.0, st=280.0, sv=0.005;
  line(dc,{gx,vgY},{gx+period*st,vgY},4,ksCSConstruction);
  line(dc,{gx,vgY-35},{gx,vgY+35},4,ksCSConstruction);
  have=false; double vmax=0;
  for(int deg=5;deg<360;deg+=5){
    P b0,c0,d0,e0,x0,b1,c1,d1,e1,x1;
    state(deg-5,b0,c0,d0,e0,x0); state(deg+5,b1,c1,d1,e1,x1);
    double dphi=10.0*PI/180.0;
    double vel=(e1.x-e0.x)/dphi*omega;
    vmax=std::max(vmax,std::abs(vel));
    double t=deg/360.0*period;
    P p{gx+t*st,vgY+vel*sv};
    if(have && !line(dc,prev,p,4,ksCSNormal))return false;
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
  line(dc,C,{C.x+L2*std::cos(tmin),C.y+L2*std::sin(tmin)},4,ksCSConstruction);
  line(dc,C,{C.x+L2*std::cos(tmax),C.y+L2*std::sin(tmax)},4,ksCSConstruction);

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

static void* worker(void*){
  ::sleep(18);
  bool ok=false;
  try{ ok=build(); }
  catch(const std::exception& e){ log(std::string("EXCEPTION ")+e.what()); }
  catch(...){ log("EXCEPTION unknown"); }
  log(ok?"THREAD_DONE_PASS":"THREAD_DONE_FAIL");
  return nullptr;
}

__attribute__((constructor))
static void entry(){
  log("preload constructor lazy");
  pthread_t t{};
  int rc=pthread_create(&t,nullptr,worker,nullptr);
  if(rc!=0){ log("FAIL pthread_create rc="+std::to_string(rc)); return; }
  pthread_detach(t);
}
