#include <KsAPI.h>
#include <ksConstants.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <string>
#include <vector>

using namespace ksapi;
namespace fs=std::filesystem;

static const fs::path OUT{"/tmp/work2_v19_native"};
static const fs::path LOG{"/tmp/work2_v19_native/work2.log"};
static const fs::path WORKPIECE=OUT/"Work2_V19_Workpiece.m3d";
static const fs::path CUTTER=OUT/"Work2_V19_FormCutter.m3d";
static const fs::path ASSEMBLY=OUT/"Work2_V19_TopDown.a3d";
static std::ofstream lg;

static void log(const std::string& s){ lg<<s<<std::endl; lg.flush(); }
static void require(bool v,const std::string& m){ if(!v){log("FAIL "+m); throw std::runtime_error(m);} }
template<class T> static T req(const T& v,const std::string& m){ if(!v){log("FAIL "+m); throw std::runtime_error(m);} return v; }

struct Calc {
  double D1=80,D2=70,D3=50,L=75,R=21;
  double l1=8,l2=22,l3=12,l4=14;
  double alpha=10,gamma=10,d=65,da=181,e=35,a=8;
  double axisY=115.5,axisZ=15.9576;
  double flangeD=100,flangeW=5,recessD=80,recessL=15,techD=67;
  double L0=89;
  int rifling=32;
};
static const Calc P{};

static IDrawingContainerPtr dc(const IFragmentDocumentPtr& f){
  auto vm=req(f->GetViewsAndLayersManager(),"views manager");
  auto views=req(vm->GetViews(),"views");
  auto view=req(views->GetActiveView(),"active view");
  IDrawingContainerPtr c=view;
  return req(c,"drawing container");
}
static void line(const IFragmentDocumentPtr& f,double x1,double y1,double x2,double y2){
  auto ls=req(dc(f)->GetLineSegments(),"lines");
  auto s=req(ls->Add(),"line Add");
  s->SetX1(x1); s->SetY1(y1); s->SetX2(x2); s->SetY2(y2); s->SetStyle(ksCSNormal);
  require(s->Update(),"line Update");
}
static void circle(const IFragmentDocumentPtr& f,double x,double y,double r){
  auto cs=req(dc(f)->GetCircles(),"circles");
  auto c=req(cs->Add(),"circle Add");
  c->SetXc(x); c->SetYc(y); c->SetRadius(r); c->SetStyle(ksCSNormal);
  require(c->Update(),"circle Update");
}
static std::array<double,2> arc_mid(std::array<double,2> p1,std::array<double,2> p2,double r){
  double dx=p2[0]-p1[0],dy=p2[1]-p1[1],ch=std::hypot(dx,dy);
  require(ch<2*r,"R21 chord invalid");
  double mx=(p1[0]+p2[0])/2,my=(p1[1]+p2[1])/2;
  double h=std::sqrt(r*r-(ch*ch)/4);
  double nx=-dy/ch,ny=dx/ch;
  std::array<double,2> c1{mx+h*nx,my+h*ny},c2{mx-h*nx,my-h*ny};
  auto midFor=[&](std::array<double,2> c){
    double a1=std::atan2(p1[1]-c[1],p1[0]-c[0]);
    double a2=std::atan2(p2[1]-c[1],p2[0]-c[0]);
    double delta=std::remainder(a2-a1,2*M_PI);
    double am=a1+delta/2;
    return std::array<double,2>{c[0]+r*std::cos(am),c[1]+r*std::sin(am)};
  };
  auto m1=midFor(c1),m2=midFor(c2);
  return m1[1]>m2[1]?m1:m2;
}
static void arc3(const IFragmentDocumentPtr& f,std::array<double,2> p1,std::array<double,2> pm,std::array<double,2> p2){
  auto as=req(dc(f)->GetArcs(),"arcs");
  auto a=req(as->Add(),"arc Add");
  a->SetX1(p1[0]); a->SetY1(p1[1]);
  a->SetX2(p2[0]); a->SetY2(p2[1]);
  a->SetX3(pm[0]); a->SetY3(pm[1]);
  a->SetStyle(ksCSNormal);
  require(a->Update(),"arc Update");
}

static ISketchPtr sketch(const IPartPtr& top,const std::wstring& name,ksObj3dTypeEnum planeType,IFragmentDocumentPtr& frag){
  auto mc=req(top->GetModelContainer(),"model container");
  auto ss=req(mc->GetSketchs(),"sketches");
  auto s=req(ss->Add(),"sketch Add");
  s->SetName(name);
  s->SetPlane(req(top->GetDefaultObject(planeType),"default plane"));
  frag=req(s->BeginEdit(false),"sketch BeginEdit");
  return s;
}
static void end_sketch(const ISketchPtr& s){
  require(s->EndEdit(),"sketch EndEdit");
  require(s->Update(),"sketch Update");
}
static IRotatedPtr revolve(const IPartPtr& top,const IKompasDocument3DPtr& doc,const ISketchPtr& s,const std::wstring& name){
  auto mc=req(top->GetModelContainer(),"revolve model container");
  auto rs=req(mc->GetRotateds(),"rotateds");
  auto r=req(rs->Add(o3d_baseRotated),"base rotated Add");
  r->SetName(name);
  r->SetProfile(IModelObjectPtr(s));
  r->SetAxis(req(top->GetDefaultObject(o3d_axisOX),"default OX"));
  r->SetDirection(dtNormal);
  r->SetRotatedType(true,ksRTAngle);
  r->SetAngle(true,360.0);
  require(r->Update(),"rotated Update");
  require(top->RebuildModel(false),"revolve model rebuild");
  require(doc->RebuildDocument(),"revolve document rebuild");
  return r;
}
static IExtrusionPtr cut_extrusion(const IPartPtr& top,const IKompasDocument3DPtr& doc,const ISketchPtr& s,double depth,const std::wstring& name,bool normal){
  auto mc=req(top->GetModelContainer(),"cut model container");
  auto es=req(mc->GetExtrusions(),"extrusions");
  auto e=req(es->Add(o3d_cutExtrusion),"cut extrusion Add");
  e->SetName(name);
  e->SetProfiles({IModelObjectPtr(s)});
  require(e->SetSideParameters(normal,etBlind,depth,0.0,false,IModelObjectPtr{}),"cut SetSideParameters");
  require(e->Update(),"cut Update");
  require(top->RebuildModel(false),"cut model rebuild");
  require(doc->RebuildDocument(),"cut document rebuild");
  return e;
}
static IVariablePtr var(const IPartPtr& top,const std::wstring& name,double value,const std::wstring& note=L""){
  auto v=req(top->AddVariable(name,value,note),"AddVariable");
  v->SetExternal(true);
  return v;
}
static double mass(const IPartPtr& p){
  double m=p->GetMass();
  require(std::isfinite(m)&&m>0,"invalid mass");
  return m;
}
static void native_file(const fs::path& p){ require(fs::exists(p)&&fs::file_size(p)>1024,"native file missing/small "+p.string()); }

static void build_workpiece(const IPartPtr& top,const IKompasDocument3DPtr& doc){
  var(top,L"D1",P.D1); var(top,L"D2",P.D2); var(top,L"D3",P.D3);
  var(top,L"L",P.L); var(top,L"R",P.R);
  double x0=-P.L,x1=x0+P.l1,x2=x0+P.l2,x3=x2+P.l3,x4=-P.l4,x5=0;
  double r1=P.D1/2,r2=P.D2/2,r3=P.D3/2;
  IFragmentDocumentPtr f;
  auto s=sketch(top,L"WORKPIECE_PROFILE_V19",o3d_planeXOY,f);
  line(f,x0,0,x0,r3);
  line(f,x0,r3,x1,r3);
  line(f,x1,r3,x2,r2);
  line(f,x2,r2,x3,r2);
  std::array<double,2> p1{x3,r2},p2{x4,r1};
  arc3(f,p1,arc_mid(p1,p2,P.R),p2);
  line(f,x4,r1,x5,r1);
  line(f,x5,r1,x5,0);
  line(f,x5,0,x0,0);
  end_sketch(s);
  revolve(top,doc,s,L"WORKPIECE_REVOLVE_V19");
  require(top->SetMaterial(L"Сталь 60",0.00785),"workpiece material");
  require(top->RebuildModel(false),"workpiece final rebuild");
  log("WORKPIECE_PROFILE_D1_D2_D3_R21_PASS");
}
static void build_cutter(const IPartPtr& top,const IKompasDocument3DPtr& doc){
  var(top,L"d",P.d); var(top,L"d_a",P.da); var(top,L"L0",P.L0);
  var(top,L"flange_d",P.flangeD); var(top,L"rifling_z",P.rifling);
  double rin=P.d/2,rout=P.da/2,rf=P.flangeD/2,rr=P.recessD/2,rt=P.techD/2;
  double left=-P.L0,recessEnd=left+P.recessL,mainRight=-P.flangeW,techStart=mainRight-15.0;
  IFragmentDocumentPtr f;
  auto s=sketch(top,L"CUTTER_MASTER_PROFILE_V19",o3d_planeXOY,f);
  std::vector<std::array<double,2>> q={
    {left,rr},{recessEnd,rr},{recessEnd,rin},{techStart,rin},{techStart,rt},
    {mainRight,rt},{mainRight,rin},{0,rin},{0,rf},{mainRight,rf},{mainRight,rout},{left,rout}
  };
  for(size_t i=0;i<q.size();i++) line(f,q[i][0],q[i][1],q[(i+1)%q.size()][0],q[(i+1)%q.size()][1]);
  end_sketch(s);
  revolve(top,doc,s,L"CUTTER_BLANK_REVOLVE_V19");

  // Native 32-notch end-face rifling approximation on the 100 mm belt.
  IFragmentDocumentPtr rfFrag;
  auto rs=sketch(top,L"RIFFLING_32_V19",o3d_planeYOZ,rfFrag);
  const double pitchR=48.0, notchR=0.65;
  for(int i=0;i<P.rifling;i++){
    double a=2*M_PI*i/P.rifling;
    circle(rfFrag,pitchR*std::cos(a),pitchR*std::sin(a),notchR);
  }
  end_sketch(rs);
  cut_extrusion(top,doc,rs,2.0,L"RIFFLING_32_NATIVE_CUT",false);
  require(top->SetMaterial(L"Быстрорежущая сталь",0.00830),"cutter material");
  require(top->RebuildModel(false),"cutter final rebuild");
  log("CUTTER_D65_DA181_L89_PASS");
  log("RIFFLING_32_NATIVE_PASS");
}
static void set_origin(const IPartPtr& p,double x,double y,double z){
  auto pl=req(p->GetPlacement(),"GetPlacement");
  require(pl->SetOrigin(x,y,z),"SetOrigin");
  require(p->UpdatePlacement(false),"UpdatePlacement");
}
static std::array<double,3> origin(const IPartPtr& p){
  double x=0,y=0,z=0;
  auto pl=req(p->GetPlacement(),"GetPlacement origin");
  require(pl->GetOrigin(x,y,z),"GetOrigin");
  return {x,y,z};
}

static fs::path native_template(const std::string& ext){
  const fs::path dir{"/opt/ascon/kompas3d-v25/Utils/KLibEditor/Templates"};
  req(fs::exists(dir),"KOMPAS template directory");
  for(const auto& e:fs::directory_iterator(dir))
    if(e.is_regular_file() && e.path().extension()==ext) return e.path();
  throw std::runtime_error("native KOMPAS template missing: "+ext);
}
static IPartPtr insert_component(const IPartPtr& asmTop,const fs::path& file,const std::wstring& name){
  auto parts=req(asmTop->GetParts(),"assembly parts");
  auto c=req(parts->AddFromFile(file.wstring(),true,false),"AddFromFile "+file.string());
  c->SetName(name);
  return c;
}
static IKompasDocument3DPtr begin_edit(const IPartPtr& c){
  auto p=req(c->GetOpenDocumentParam(),"GetOpenDocumentParam");
  return req(c->BeginEdit(p),"component BeginEdit");
}
static void end_edit(const IPartPtr& c,const IKompasDocument3DPtr& d){
  require(d->RebuildDocument(),"edit document rebuild");
  require(d->Save(),"edit document Save");
  require(c->EndEdit(true),"component EndEdit");
}
static void add_mold_cavity(const IPartPtr& cutter,const IPartPtr& workpiece){
  auto d=begin_edit(cutter);
  auto top=req(d->GetTopPart(),"cutter edit top");
  auto mc=req(top->GetModelContainer(),"cutter edit model container");
  auto cavs=req(mc->GetMoldCavities(),"GetMoldCavities");
  auto cav=req(cavs->Add(),"MoldCavity Add");
  cav->SetName(L"TOP_DOWN_WORKPIECE_DEPENDENCY");
  cav->SetParts({IModelObjectPtr(workpiece)});
  cav->SetScale(0.0);
  require(cav->Update(),"MoldCavity Update");
  require(top->RebuildModel(false),"cutter rebuild after MoldCavity");
  require(d->RebuildDocument(),"cutter document rebuild after MoldCavity");
  end_edit(cutter,d);
}
static std::vector<IPartPtr> parts_by_file(const IPartPtr& top,const fs::path& file){
  std::vector<IPartPtr> v;
  auto ps=req(top->GetParts(),"GetParts");
  for(int i=0;i<ps->GetCount();i++){
    auto p=ps->GetPart(i);
    if(p && fs::path(p->GetFileName()).filename()==file.filename()) v.push_back(p);
  }
  return v;
}
static void close_doc(const IKompasDocumentPtr& d){ try{d->Close(kdDoNotSaveChanges);}catch(...){} }

static void build_top_down(const IDocumentsPtr& docs){
  // Assembly is created first from ASCON's own empty native A3D template.
  // This preserves the required top-down order while avoiding the broken
  // Documents.Add(3D) call in Linux ksinvisible.
  auto atpl=native_template(".a3d");
  auto base=req(docs->Open(atpl.wstring(),true,false),"Open native A3D template");
  IKompasDocument3DPtr asmDoc=base;
  auto top=req(asmDoc->GetTopPart(),"assembly top");
  top->SetName(L"WORK2_V19_TOP_DOWN");
  var(top,L"AXIS_Y",P.axisY,L"calculated cutter axis horizontal distance");
  var(top,L"AXIS_Z",P.axisZ,L"calculated cutter axis vertical offset");
  var(top,L"ALPHA",P.alpha); var(top,L"GAMMA",P.gamma);
  require(base->SaveAs(ASSEMBLY.wstring()),"initial A3D SaveAs");
  log("ASSEMBLY_FIRST_PASS");

  // Workpiece is created only after the assembly exists on disk.
  auto mtpl=native_template(".m3d");
  auto wb=req(docs->Open(mtpl.wstring(),true,false),"Open native M3D template for workpiece");
  IKompasDocument3DPtr wdoc=wb;
  auto wtop=req(wdoc->GetTopPart(),"workpiece template top");
  require(!wdoc->GetLastFeature(),"workpiece template not empty");
  wtop->SetName(L"WORKPIECE_V19");
  build_workpiece(wtop,wdoc);
  require(wb->SaveAs(WORKPIECE.wstring()),"workpiece SaveAs");
  close_doc(wb); native_file(WORKPIECE);
  auto wp=insert_component(top,WORKPIECE,L"WORKPIECE_V19");
  log("WORKPIECE_CREATED_AFTER_ASSEMBLY_PASS");

  // Cutter is also created after the assembly, then inserted and made dependent
  // on the already inserted workpiece through a real MoldCavity operation.
  auto cb=req(docs->Open(mtpl.wstring(),true,false),"Open native M3D template for cutter");
  IKompasDocument3DPtr cdoc=cb;
  auto ctop=req(cdoc->GetTopPart(),"cutter template top");
  require(!cdoc->GetLastFeature(),"cutter template not empty");
  ctop->SetName(L"FORM_CUTTER_V19");
  build_cutter(ctop,cdoc);
  require(cb->SaveAs(CUTTER.wstring()),"cutter SaveAs");
  close_doc(cb); native_file(CUTTER);
  auto cutter=insert_component(top,CUTTER,L"FORM_CUTTER_V19");
  log("CUTTER_CREATED_AFTER_ASSEMBLY_PASS");

  set_origin(cutter,0.0,P.axisY,P.axisZ);
  require(top->RebuildModel(false),"assembly rebuild after cutter placement");
  require(asmDoc->RebuildDocument(),"assembly document rebuild after cutter placement");

  add_mold_cavity(cutter,wp);
  require(top->RebuildModel(false),"assembly rebuild after MoldCavity");
  require(asmDoc->RebuildDocument(),"assembly doc rebuild after MoldCavity");
  log("TOP_DOWN_MOLD_CAVITY_DEPENDENCY_PASS");

  require(base->Save(),"final assembly Save");
  close_doc(base);
  native_file(ASSEMBLY);
}

static void reopen_detail(const IDocumentsPtr& docs,const fs::path& p){
  auto base=req(docs->Open(p.wstring(),true,false),"detail Open "+p.string());
  IKompasDocument3DPtr d=base;
  auto top=req(d->GetTopPart(),"detail top");
  require(d->RebuildDocument(),"detail document rebuild");
  require(top->RebuildModel(false),"detail model rebuild");
  req(d->GetLastFeature(),"detail GetLastFeature");
  mass(top);
  require(base->Save(),"detail Save");
  close_doc(base);
  auto b2=req(docs->Open(p.wstring(),true,false),"detail Reopen "+p.string());
  IKompasDocument3DPtr d2=b2;
  require(d2->RebuildDocument(),"detail reopen document rebuild");
  require(req(d2->GetTopPart(),"detail reopen top")->RebuildModel(false),"detail reopen model rebuild");
  close_doc(b2);
}

static void acceptance(const IDocumentsPtr& docs){
  reopen_detail(docs,WORKPIECE); log("WORKPIECE_OPEN_REBUILD_SAVE_CLOSE_REOPEN_PASS");
  reopen_detail(docs,CUTTER); log("CUTTER_OPEN_REBUILD_SAVE_CLOSE_REOPEN_PASS");

  auto base=req(docs->Open(ASSEMBLY.wstring(),true,false),"assembly Open");
  IKompasDocument3DPtr d=base;
  auto top=req(d->GetTopPart(),"assembly top reopen");
  require(d->RebuildDocument(),"assembly RebuildDocument");
  require(top->RebuildModel(false),"assembly RebuildModel");
  auto wv=parts_by_file(top,WORKPIECE),cv=parts_by_file(top,CUTTER);
  require(wv.size()==1&&cv.size()==1,"component source links");
  auto wp=wv[0],cutter=cv[0];
  double m0=mass(cutter);
  log("CUTTER_MASS_BASELINE="+std::to_string(m0));

  // Same physical dependency test as the original Windows verifier.
  set_origin(wp,0.0,5.0,0.0);
  require(top->RebuildModel(false),"dependency changed model rebuild");
  require(d->RebuildDocument(),"dependency changed doc rebuild");
  double m1=mass(cutter);
  double delta=std::abs(m1-m0);
  log("CUTTER_MASS_DEPENDENCY_MUTATED="+std::to_string(m1));
  log("CUTTER_MASS_DELTA="+std::to_string(delta));
  require(delta>std::max(1e-6,m0*1e-7),"MoldCavity physical dependency did not change cutter mass");
  log("TOP_DOWN_DEPENDENCY_PHYSICAL_CHANGE_PASS");

  set_origin(wp,0.0,0.0,0.0);
  require(top->RebuildModel(false),"dependency restore model rebuild");
  require(d->RebuildDocument(),"dependency restore doc rebuild");
  double mr=mass(cutter);
  require(std::abs(mr-m0)<=std::max(1e-5,m0*1e-6),"dependency mass did not restore");
  set_origin(cutter,0.0,P.axisY,P.axisZ);
  require(top->RebuildModel(false),"nominal placement model rebuild");
  require(d->RebuildDocument(),"nominal placement doc rebuild");
  require(base->Save(),"assembly final Save");
  close_doc(base);
  log("TOP_DOWN_DEPENDENCY_RESTORE_PASS");

  auto b2=req(docs->Open(ASSEMBLY.wstring(),true,false),"assembly final Reopen");
  IKompasDocument3DPtr d2=b2;
  auto t2=req(d2->GetTopPart(),"assembly final top");
  require(d2->RebuildDocument(),"final RebuildDocument");
  require(t2->RebuildModel(false),"final RebuildModel");
  auto c2=parts_by_file(t2,CUTTER),w2=parts_by_file(t2,WORKPIECE);
  require(c2.size()==1&&w2.size()==1,"final source links");
  double mf=mass(c2[0]);
  require(std::abs(mf-m0)<=std::max(1e-5,m0*1e-6),"final cutter mass drift");
  auto o=origin(c2[0]);
  require(std::abs(o[0])<1e-6&&std::abs(o[1]-P.axisY)<1e-5&&std::abs(o[2]-P.axisZ)<1e-5,
          "final calculated cutter placement drift");
  close_doc(b2);
  log("FINAL_NOMINAL_REOPEN_PASS");
  log("RESULT=PASS_NATIVE_WORK2_VARIANT19_REOPEN_REBUILD_DEPENDENCY");
  log("RESULT=PASS_NATIVE_WORK2_VARIANT19");
}

static void manifest(){
  std::ofstream f(OUT/"native-manifest.json");
  f<<"{\n"
   <<"  \"work\":2,\n"
   <<"  \"variant\":19,\n"
   <<"  \"architecture\":\"top-down\",\n"
   <<"  \"assembly_first\":true,\n"
   <<"  \"dependency\":\"MoldCavity cutter <- workpiece component\",\n"
   <<"  \"calculation\":{\"D1\":80,\"D2\":70,\"D3\":50,\"R\":21,\"d\":65,\"d_a\":181,\"L0\":89,\"axis_y\":115.5,\"axis_z\":15.9576,\"rifling\":32}\n"
   <<"}\n";
}

extern "C" int run_variant06_writer(){
  static bool done=false;
  if(done) return 0;
  try{
    if(lg.is_open()) lg.close();
    lg.clear();
    fs::remove_all(OUT); fs::create_directories(OUT);
    lg.open(LOG,std::ios::out|std::ios::app);
    log("WORK2_VARIANT19_BEGIN");
    IApplication& app=GetKompasApplication();
    app.SetHideMessage(ksHideMessageYes);
    int ma=0,mi=0,re=0,bu=0; app.GetSystemVersion(ma,mi,re,bu);
    log("KOMPAS_VERSION="+std::to_string(ma)+"."+std::to_string(mi)+"."+std::to_string(re)+" build="+std::to_string(bu));
    auto lm=app.GetApplicationLicenseManager();
    if(lm){
      bool active=lm->IsKompasModuleActive(ksKompasModule3D);
      log(std::string("LICENSE_3D_ACTIVE_BEFORE=")+(active?"1":"0"));
      if(!active){lm->SetKompasModuleActive(ksKompasModule3D,true); active=lm->IsKompasModuleActive(ksKompasModule3D);}
      log(std::string("LICENSE_3D_ACTIVE_AFTER=")+(active?"1":"0"));
    }
    auto docs=req(app.GetDocuments(),"Application Documents");
    build_top_down(docs);
    manifest();
    acceptance(docs);
    done=true;
    return 0;
  }catch(const std::exception& e){
    if(!lg.is_open()){fs::create_directories(OUT);lg.open(LOG,std::ios::out|std::ios::app);}
    log(std::string("EXCEPTION=")+e.what());
    log("RESULT=FAIL_NATIVE_WORK2_VARIANT19");
  }catch(...){
    if(!lg.is_open()){fs::create_directories(OUT);lg.open(LOG,std::ios::out|std::ios::app);}
    log("EXCEPTION=unknown");
    log("RESULT=FAIL_NATIVE_WORK2_VARIANT19");
  }
  return 2;
}
