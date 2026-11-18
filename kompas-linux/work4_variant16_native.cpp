#include <KsAPI.h>
#include <ksConstants.h>

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <string>
#include <vector>

using namespace ksapi;
namespace fs = std::filesystem;

static const fs::path OUTDIR{"/tmp/work4_v16_native"};
static const fs::path LOG{"/tmp/work4_v16_native/work4.log"};

static std::ofstream lg;
static void log(const std::string& s) {
  lg << s << std::endl;
  lg.flush();
}
static void require(bool v, const std::string& msg) {
  if (!v) {
    log("FAIL " + msg);
    throw std::runtime_error(msg);
  }
}
template <class T>
static T require_ptr(const T& v, const std::string& msg) {
  if (!v) {
    log("FAIL " + msg);
    throw std::runtime_error(msg);
  }
  return v;
}

struct Params {
  double D=120.0, d=70.0, T=40.0, C=40.0, B=20.0, R=2.0;
  double brol=12.0, drol=12.0, S=0.6, z=47.5, alpha=15.0;
  int n=13;
  double D1=102.0, D2=91.0, cageH=6.6, cellD=13.2;
  double rivetPitch=96.5, rivetOffset=360.0/(2.0*13.0), rivetD=1.6;
  double innerOD=85.4, outerID=104.6, rollerDraft=5.0;
  double testT=44.0;
};
static const Params P{};

static fs::path inner_path(){ return OUTDIR/"Work4_V16_InnerDoubleRing.m3d"; }
static fs::path cup_l_path(){ return OUTDIR/"Work4_V16_OuterCup_L.m3d"; }
static fs::path cup_r_path(){ return OUTDIR/"Work4_V16_OuterCup_R.m3d"; }
static fs::path roller_path(){ return OUTDIR/"Work4_V16_TaperRoller.m3d"; }
static fs::path cage_path(){ return OUTDIR/"Work4_V16_CageHalf.m3d"; }
static fs::path rivet_path(){ return OUTDIR/"Work4_V16_Rivet.m3d"; }
static fs::path asm_path(){ return OUTDIR/"Work4_V16_Bearing.a3d"; }

static IDrawingContainerPtr drawing_container(const IFragmentDocumentPtr& frag) {
  auto vm = require_ptr(frag->GetViewsAndLayersManager(), "fragment views manager");
  auto views = require_ptr(vm->GetViews(), "fragment views");
  auto view = require_ptr(views->GetActiveView(), "fragment active view");
  IDrawingContainerPtr dc = view;
  return require_ptr(dc, "fragment drawing container");
}
static void add_circle(const IFragmentDocumentPtr& frag, double x, double y, double r) {
  auto dc = drawing_container(frag);
  auto circles = require_ptr(dc->GetCircles(), "circle collection");
  auto c = require_ptr(circles->Add(), "circle Add");
  c->SetXc(x); c->SetYc(y); c->SetRadius(r);
  c->SetStyle(ksCSNormal);
  require(c->Update(), "circle Update");
}
static void add_line(const IFragmentDocumentPtr& frag, double x1,double y1,double x2,double y2, int style=ksCSNormal) {
  auto dc = drawing_container(frag);
  auto lines = require_ptr(dc->GetLineSegments(), "line collection");
  auto s = require_ptr(lines->Add(), "line Add");
  s->SetX1(x1); s->SetY1(y1); s->SetX2(x2); s->SetY2(y2);
  s->SetStyle(style);
  require(s->Update(), "line Update");
}

struct DocPart {
  IKompasDocumentPtr base;
  IKompasDocument3DPtr doc;
  IPartPtr top;
};
static DocPart new_part(const IDocumentsPtr& docs, const std::wstring& name) {
  log("NEW_PART_BEFORE_DOCUMENTS_ADD");
  auto base = require_ptr(docs->Add(ksDocumentPart, true), "Documents.Add part");
  log("NEW_PART_AFTER_DOCUMENTS_ADD");
  IKompasDocument3DPtr doc = base;
  require_ptr(doc, "cast part document 3D");
  auto top = require_ptr(doc->GetTopPart(), "part TopPart");
  top->SetName(name);
  return {base,doc,top};
}
static DocPart new_assembly(const IDocumentsPtr& docs, const std::wstring& name) {
  log("NEW_ASSEMBLY_BEFORE_DOCUMENTS_ADD");
  auto base = require_ptr(docs->Add(ksDocumentAssembly, true), "Documents.Add assembly");
  log("NEW_ASSEMBLY_AFTER_DOCUMENTS_ADD");
  IKompasDocument3DPtr doc = base;
  require_ptr(doc, "cast assembly document 3D");
  auto top = require_ptr(doc->GetTopPart(), "assembly TopPart");
  top->SetName(name);
  return {base,doc,top};
}
static ISketchPtr new_sketch(const IPartPtr& top, const std::wstring& name, IFragmentDocumentPtr& frag) {
  auto mc = require_ptr(top->GetModelContainer(), "GetModelContainer");
  auto sketches = require_ptr(mc->GetSketchs(), "GetSketchs");
  auto sk = require_ptr(sketches->Add(), "sketch Add");
  sk->SetName(name);
  auto plane = require_ptr(top->GetDefaultObject(o3d_planeXOY), "default XOY");
  sk->SetPlane(plane);
  require(sk->Update(), "sketch plane Update");
  frag = require_ptr(sk->BeginEdit(false), "sketch BeginEdit");
  return sk;
}
static void finish_sketch(const ISketchPtr& sk) {
  require(sk->EndEdit(), "sketch EndEdit");
  require(sk->Update(), "sketch final Update");
}
static IVariablePtr add_var(const IPartPtr& top, const std::wstring& name, double value,
                            const std::wstring& expr=L"", bool external=true,
                            const std::wstring& note=L"") {
  auto v = require_ptr(top->AddVariable(name,value,note), "AddVariable");
  if (!expr.empty()) v->SetExpression(expr);
  if (external) v->SetExternal(true);
  return v;
}
static IVariablePtr feature_var_by_name(const IFeaturePtr& feat, const std::wstring& name) {
  for (bool external : {false,true}) {
    for (bool source : {false,true}) {
      try {
        auto v=feat->GetVariableByName(external,source,name);
        if (v) return v;
      } catch (...) {}
    }
  }
  for (bool external : {false,true}) {
    for (bool source : {false,true}) {
      try {
        for (auto &v : feat->GetVariables(external,source)) {
          if (v && v->GetName()==name) return v;
        }
      } catch (...) {}
    }
  }
  return {};
}
static IVariablePtr part_var(const IPartPtr& part,const std::wstring& name) {
  IFeaturePtr feat = part;
  require_ptr(feat,"part feature QI");
  return require_ptr(feature_var_by_name(feat,name),"part variable missing");
}
static std::vector<std::wstring> bind_feature_value(const IFeaturePtr& feat,double target,
                                                    const std::wstring& expression) {
  std::vector<std::wstring> hits;
  std::ostringstream dump;
  for (auto &v : feat->GetVariables(false,false)) {
    if(!v) continue;
    double val=0;
    try { val=v->GetValue(); } catch (...) { continue; }
    dump << "[" << std::string(v->GetName().begin(),v->GetName().end()) << "=" << val << "]";
    if (std::abs(val-target)<=std::max(1e-7,std::abs(target)*1e-9)) {
      v->SetExpression(expression);
      hits.push_back(v->GetName());
    }
  }
  require(!hits.empty(),"operation variable not found for expression");
  return hits;
}
static IExtrusionPtr make_extrusion(const IPartPtr& top,const IKompasDocument3DPtr& doc,
                                    const ISketchPtr& sk,double depth,const std::wstring& name,
                                    double draft=0.0,const std::wstring& bind=L"",
                                    ksObj3dTypeEnum type=o3d_baseExtrusion) {
  auto mc=require_ptr(top->GetModelContainer(),"extrusion model container");
  auto exts=require_ptr(mc->GetExtrusions(),"extrusions");
  auto ext=require_ptr(exts->Add(type),"extrusion Add");
  ext->SetName(name);
  ext->SetProfiles({IModelObjectPtr(sk)});
  require(ext->SetSideParameters(true,etBlind,depth,draft,false,IModelObjectPtr{}),"SetSideParameters");
  require(ext->Update(),"extrusion Update");
  require(top->RebuildModel(false),"part RebuildModel after extrusion");
  require(doc->RebuildDocument(),"doc RebuildDocument after extrusion");
  if(!bind.empty()) {
    IFeaturePtr feat=ext;
    require_ptr(feat,"extrusion feature QI");
    auto hits=bind_feature_value(feat,depth,bind);
    require(top->RebuildModel(false),"RebuildModel after variable bind");
    require(doc->RebuildDocument(),"RebuildDocument after variable bind");
  }
  return ext;
}
static double mass(const IPartPtr& p) {
  double m=p->GetMass();
  require(std::isfinite(m)&&m>0.0,"invalid part mass");
  return m;
}
static void close_doc(const IKompasDocumentPtr& base) {
  try { base->Close(kdDoNotSaveChanges); } catch (...) {}
}
static void verify_native_file(const fs::path& p) {
  require(fs::exists(p)&&fs::file_size(p)>1024,"native file missing/small "+p.string());
}
static void physical_var_probe(const IPartPtr& top,const IKompasDocument3DPtr& doc,
                               const IVariablePtr& v,double nominal,double changed,
                               const std::string& tag) {
  double m0=mass(top);
  v->SetValue(changed);
  require(top->RebuildModel(false),tag+" changed RebuildModel");
  require(doc->RebuildDocument(),tag+" changed RebuildDocument");
  double m1=mass(top);
  require(std::abs(m1-m0)>1e-7,tag+" variable did not change physical mass");
  v->SetValue(nominal);
  require(top->RebuildModel(false),tag+" restore RebuildModel");
  require(doc->RebuildDocument(),tag+" restore RebuildDocument");
  double mr=mass(top);
  require(std::abs(mr-m0)<=std::max(1e-7,m0*1e-6),tag+" mass did not restore");
  log(tag+"_VARIABLE_PHYSICAL_PASS");
}
static double build_annulus(const IDocumentsPtr& docs,const fs::path& path,const std::wstring& name,
                            double od,double id,double width) {
  auto d=new_part(docs,name);
  auto W=add_var(d.top,L"W",width,L"",true,L"axial width");
  add_var(d.top,L"D_OUT",od,L"",true,L"outer diameter");
  add_var(d.top,L"D_IN",id,L"",true,L"inner diameter");
  IFragmentDocumentPtr frag;
  auto sk=new_sketch(d.top,name+L"_PROFILE",frag);
  add_circle(frag,0,0,od/2); add_circle(frag,0,0,id/2);
  finish_sketch(sk);
  make_extrusion(d.top,d.doc,sk,width,name+L"_EXTRUSION",0.0,L"W");
  d.top->SetMaterial(L"ШХ15",0.00785);
  physical_var_probe(d.top,d.doc,W,width,width+2.0,"ANNULUS");
  double m=mass(d.top);
  require(d.base->SaveAs(path.wstring()),"annulus SaveAs");
  close_doc(d.base); verify_native_file(path);
  return m;
}
static double build_roller(const IDocumentsPtr& docs) {
  auto d=new_part(docs,L"TAPER_ROLLER_V16");
  auto W=add_var(d.top,L"W",P.brol,L"",true,L"roller axial length");
  add_var(d.top,L"DR",P.drol,L"",true,L"roller nominal diameter");
  add_var(d.top,L"DRAFT",P.rollerDraft,L"",true,L"taper draft");
  IFragmentDocumentPtr frag;
  auto sk=new_sketch(d.top,L"ROLLER_PROFILE",frag);
  add_circle(frag,0,0,P.drol/2);
  finish_sketch(sk);
  make_extrusion(d.top,d.doc,sk,P.brol,L"ROLLER_TAPER",P.rollerDraft,L"W");
  d.top->SetMaterial(L"ШХ15",0.00785);
  physical_var_probe(d.top,d.doc,W,P.brol,P.brol+2.0,"ROLLER");
  double m=mass(d.top);
  require(d.base->SaveAs(roller_path().wstring()),"roller SaveAs");
  close_doc(d.base); verify_native_file(roller_path());
  return m;
}
static double build_cage(const IDocumentsPtr& docs) {
  auto d=new_part(docs,L"CAGE_HALF_V16");
  auto H=add_var(d.top,L"H",P.cageH,L"",true,L"half-cage axial depth");
  add_var(d.top,L"S",P.S,L"",true,L"backing thickness");
  add_var(d.top,L"D1",P.D1,L"",true,L"cage outer diameter");
  add_var(d.top,L"D2",P.D2,L"",true,L"cage inner diameter");
  add_var(d.top,L"N_ROL",P.n,L"",true,L"roller cells");
  IFragmentDocumentPtr frag;
  auto sk=new_sketch(d.top,L"CAGE_BASE_PROFILE",frag);
  add_circle(frag,0,0,P.D1/2); add_circle(frag,0,0,P.D2/2);
  finish_sketch(sk);
  make_extrusion(d.top,d.doc,sk,P.cageH,L"CAGE_BASE",0.0,L"H");

  IFragmentDocumentPtr pfrag;
  auto psk=new_sketch(d.top,L"CAGE_CELLS_13",pfrag);
  for(int i=0;i<P.n;i++){
    double a=2.0*M_PI*i/P.n;
    add_circle(pfrag,P.z*std::cos(a),P.z*std::sin(a),P.cellD/2);
  }
  finish_sketch(psk);
  make_extrusion(d.top,d.doc,psk,P.brol/2,L"CAGE_CELLS_NATIVE_13",0.0,L"",o3d_cutExtrusion);
  d.top->SetMaterial(L"Сталь 20",0.00785);
  physical_var_probe(d.top,d.doc,H,P.cageH,P.cageH+1.0,"CAGE");
  double m=mass(d.top);
  require(d.base->SaveAs(cage_path().wstring()),"cage SaveAs");
  close_doc(d.base); verify_native_file(cage_path());
  return m;
}
static double build_rivet(const IDocumentsPtr& docs) {
  const double L=2*P.S+1.0;
  auto d=new_part(docs,L"RIVET_V16");
  auto W=add_var(d.top,L"W",L,L"",true,L"rivet length");
  add_var(d.top,L"DRIVET",P.rivetD,L"",true,L"rivet diameter");
  IFragmentDocumentPtr frag;
  auto sk=new_sketch(d.top,L"RIVET_PROFILE",frag);
  add_circle(frag,0,0,P.rivetD/2);
  finish_sketch(sk);
  make_extrusion(d.top,d.doc,sk,L,L"RIVET_SHAFT",0.0,L"W");
  d.top->SetMaterial(L"Сталь 20",0.00785);
  physical_var_probe(d.top,d.doc,W,L,L+1.0,"RIVET");
  double m=mass(d.top);
  require(d.base->SaveAs(rivet_path().wstring()),"rivet SaveAs");
  close_doc(d.base); verify_native_file(rivet_path());
  return m;
}
static void build_master(const IPartPtr& top) {
  IFragmentDocumentPtr frag;
  auto sk=new_sketch(top,L"MASTER_GEOMETRY_V16",frag);
  add_circle(frag,0,0,P.D/2);
  add_circle(frag,0,0,P.d/2);
  add_circle(frag,0,0,P.z);
  add_line(frag,-P.D/2,0,P.D/2,0);
  add_line(frag,0,-P.D/2,0,P.D/2);
  add_line(frag,-P.T/4,-4,-P.T/4,4);
  add_line(frag, P.T/4,-4, P.T/4,4);
  finish_sketch(sk);
}
static void assembly_vars(const IPartPtr& top) {
  add_var(top,L"D",P.D);
  add_var(top,L"d",P.d);
  add_var(top,L"T",P.T);
  add_var(top,L"C",P.C,L"T");
  add_var(top,L"B",P.B,L"T/2");
  add_var(top,L"R",P.R);
  add_var(top,L"b_rol",P.brol);
  add_var(top,L"d_rol",P.drol);
  add_var(top,L"N_rol",P.n);
  add_var(top,L"S",P.S);
  add_var(top,L"z",P.z,L"(d+D)/4");
  add_var(top,L"alpha",P.alpha);
  add_var(top,L"D1",P.D1,L"ROUND((d+D)/2+0.6*d_rol)");
  add_var(top,L"D2",P.D2,L"ROUND((d+D)/2-0.3*d_rol)");
  add_var(top,L"cage_h",P.cageH,L"S+b_rol/2");
  add_var(top,L"cage_cell_d",P.cellD,L"d_rol+2*S");
  add_var(top,L"rivet_pitch_d",P.rivetPitch,L"(D1+D2)/2");
  add_var(top,L"rivet_angle_offset",P.rivetOffset,L"360/(2*N_rol)");
  add_var(top,L"rivet_d",P.rivetD,L"ROUND((ROUND(D1)-ROUND(D2))/6)*0.8");
  require(top->RebuildModel(false),"assembly variable RebuildModel");
}
static void set_place(const IPartPtr& comp,double ox,double oy,double oz,
                      const std::array<double,3>& x={1,0,0},
                      const std::array<double,3>& y={0,1,0},
                      const std::array<double,3>& z={0,0,1}) {
  auto pl=require_ptr(comp->GetPlacement(),"component placement");
  require(pl->SetOrigin(ox,oy,oz),"placement SetOrigin");
  require(pl->SetVector(o3d_axisOX,x[0],x[1],x[2]),"placement X");
  require(pl->SetVector(o3d_axisOY,y[0],y[1],y[2]),"placement Y");
  require(pl->SetVector(o3d_axisOZ,z[0],z[1],z[2]),"placement Z");
  require(comp->UpdatePlacement(false),"component UpdatePlacement");
}
static IVariablePtr source_var(const IPartPtr& comp,const std::wstring& name) {
  IFeaturePtr feat=comp;
  require_ptr(feat,"component feature QI");
  for(bool ext : {true,false}) for(bool src : {true,false}) {
    try {
      auto v=feat->GetVariableByName(ext,src,name);
      if(v) return v;
    } catch(...) {}
  }
  return {};
}
static void link_component(const IPartPtr& comp,const std::wstring& var,const std::wstring& expr) {
  auto v=require_ptr(source_var(comp,var),"component source variable");
  v->SetExpression(expr);
  require(comp->RebuildModel(false),"component rebuild after external expression");
}
static IPartPtr add_component(const IPartsPtr& parts,const fs::path& p,const std::wstring& name) {
  auto cpt=require_ptr(parts->AddFromFile(p.wstring(),true,false),"AddFromFile "+p.string());
  cpt->SetName(name);
  return cpt;
}
static std::vector<IPartPtr> components_by_file(const IPartPtr& top,const fs::path& p) {
  std::vector<IPartPtr> out;
  auto parts=require_ptr(top->GetParts(),"GetParts");
  for(int i=0;i<parts->GetCount();i++){
    auto x=parts->GetPart(i);
    if(x && fs::path(x->GetFileName()).filename()==p.filename()) out.push_back(x);
  }
  return out;
}
struct State {
  double T,B,C,im,clm,crm,iW,lW,rW;
};
static State assembly_state(const IPartPtr& top) {
  auto iv=components_by_file(top,inner_path());
  auto lv=components_by_file(top,cup_l_path());
  auto rv=components_by_file(top,cup_r_path());
  require(iv.size()==1,"assembly one inner ring");
  require(lv.size()==1&&rv.size()==1,"assembly two cups");
  require(components_by_file(top,roller_path()).size()==26,"assembly 26 rollers");
  require(components_by_file(top,cage_path()).size()==4,"assembly 4 cage halves");
  require(components_by_file(top,rivet_path()).size()==26,"assembly 26 rivets");
  auto T=part_var(top,L"T"), B=part_var(top,L"B"), C=part_var(top,L"C");
  auto iW=require_ptr(source_var(iv[0],L"W"),"inner W");
  auto lW=require_ptr(source_var(lv[0],L"W"),"cup L W");
  auto rW=require_ptr(source_var(rv[0],L"W"),"cup R W");
  return {T->GetValue(),B->GetValue(),C->GetValue(),
          mass(iv[0]),mass(lv[0]),mass(rv[0]),
          iW->GetValue(),lW->GetValue(),rW->GetValue()};
}
static bool near(double a,double b,double rel=1e-6){
  return std::abs(a-b)<=std::max(1e-7,rel*std::max({std::abs(a),std::abs(b),1.0}));
}
static void assert_state_nominal(const State& s) {
  require(near(s.T,40)&&near(s.B,20)&&near(s.C,40),"nominal assembly variables");
  require(near(s.iW,40)&&near(s.lW,20)&&near(s.rW,20),"nominal component variables");
}
static void assert_state_changed(const State& s) {
  require(near(s.T,44)&&near(s.B,22)&&near(s.C,44),"changed assembly variables");
  require(near(s.iW,44)&&near(s.lW,22)&&near(s.rW,22),"changed component variables");
}
static void verify_master(const IPartPtr& top) {
  auto mc=require_ptr(top->GetModelContainer(),"assembly model container");
  auto sks=require_ptr(mc->GetSketchs(),"assembly sketches");
  require_ptr(sks->GetSketchByName(L"MASTER_GEOMETRY_V16"),"MASTER_GEOMETRY_V16 missing");
}
static void write_manifest(const std::string& stage) {
  std::ofstream f(OUTDIR/"native-manifest.json");
  f << "{\n"
    << "  \"work\":4,\n"
    << "  \"variant\":16,\n"
    << "  \"type\":\"double-row angular-contact tapered roller bearing with tapered rollers and double inner ring\",\n"
    << "  \"topology\":{\"double_inner_ring\":1,\"outer_cups\":2,\"roller_rows\":2,\"rollers_per_row\":13,\"cage_halves\":4,\"rivets\":26},\n"
    << "  \"master_geometry\":\"MASTER_GEOMETRY_V16\",\n"
    << "  \"main_rebuild_variable\":{\"name\":\"T\",\"nominal\":40,\"test\":44},\n"
    << "  \"stage\":\"" << stage << "\"\n"
    << "}\n";
}
static void build_assembly(const IDocumentsPtr& docs) {
  auto a=new_assembly(docs,L"BEARING_V16");
  build_master(a.top);
  assembly_vars(a.top);
  auto parts=require_ptr(a.top->GetParts(),"assembly parts");

  auto inner=add_component(parts,inner_path(),L"INNER_DOUBLE_RING");
  set_place(inner,0,0,-P.T/2);
  link_component(inner,L"W",L"T");

  auto cl=add_component(parts,cup_l_path(),L"OUTER_CUP_L");
  set_place(cl,0,0,-P.T/2);
  link_component(cl,L"W",L"T/2");

  auto cr=add_component(parts,cup_r_path(),L"OUTER_CUP_R");
  set_place(cr,0,0,0);
  link_component(cr,L"W",L"T/2");

  for(int row=0;row<2;row++){
    double sign=row==0?-1.0:1.0;
    double zc=sign*P.T/4.0;
    for(int i=0;i<P.n;i++){
      double th=2*M_PI*i/P.n;
      double cy=P.z*std::cos(th), cx=P.z*std::sin(th);
      double ca=std::cos(P.alpha*M_PI/180.0), sa=std::sin(P.alpha*M_PI/180.0);
      std::array<double,3> Z={sign*sa*std::sin(th),sign*sa*std::cos(th),ca};
      std::array<double,3> Y={std::cos(th),-std::sin(th),0};
      std::array<double,3> X={Y[1]*Z[2]-Y[2]*Z[1],Y[2]*Z[0]-Y[0]*Z[2],Y[0]*Z[1]-Y[1]*Z[0]};
      auto r=add_component(parts,roller_path(),L"ROLLER");
      set_place(r,cx-Z[0]*P.brol/2,cy-Z[1]*P.brol/2,zc-Z[2]*P.brol/2,X,Y,Z);
    }
    auto ca1=add_component(parts,cage_path(),L"CAGE_HALF");
    set_place(ca1,0,0,zc-P.brol/2-P.S);
    auto ca2=add_component(parts,cage_path(),L"CAGE_HALF");
    set_place(ca2,0,0,zc+P.brol/2);
    for(int i=0;i<P.n;i++){
      double th=2*M_PI*i/P.n+P.rivetOffset*M_PI/180.0;
      auto rv=add_component(parts,rivet_path(),L"RIVET");
      set_place(rv,(P.rivetPitch/2)*std::cos(th),(P.rivetPitch/2)*std::sin(th),zc-(2*P.S+1)/2);
    }
  }
  require(a.top->RebuildModel(false),"final assembly RebuildModel");
  require(a.doc->RebuildDocument(),"final assembly RebuildDocument");
  require(a.base->SaveAs(asm_path().wstring()),"assembly SaveAs");
  close_doc(a.base);
  verify_native_file(asm_path());
}
static void acceptance(const IDocumentsPtr& docs) {
  for(auto p : {inner_path(),cup_l_path(),cup_r_path(),roller_path(),cage_path(),rivet_path()}) {
    auto base=require_ptr(docs->Open(p.wstring(),true,false),"detail reopen "+p.string());
    IKompasDocument3DPtr d=base;
    auto top=require_ptr(d->GetTopPart(),"detail reopened top");
    require(d->RebuildDocument(),"detail reopen doc rebuild");
    require(top->RebuildModel(false),"detail reopen model rebuild");
    require_ptr(d->GetLastFeature(),"detail persisted feature");
    require(mass(top)>0,"detail mass after reopen");
    close_doc(base);
  }
  log("ALL_DETAILS_REOPEN_REBUILD_PASS");

  auto base=require_ptr(docs->Open(asm_path().wstring(),true,false),"assembly reopen nominal");
  IKompasDocument3DPtr doc=base;
  auto top=require_ptr(doc->GetTopPart(),"reopened assembly top");
  require(doc->RebuildDocument(),"nominal assembly doc rebuild");
  require(top->RebuildModel(false),"nominal assembly model rebuild");
  verify_master(top);
  State s0=assembly_state(top);
  assert_state_nominal(s0);
  log("MASTER_GEOMETRY_REOPEN_PASS");
  log("VARIANT16_COMPONENT_COUNTS_PASS");

  auto T=part_var(top,L"T");
  T->SetValue(P.testT);
  require(top->RebuildModel(false),"T44 top rebuild");
  require(doc->RebuildDocument(),"T44 document rebuild");
  State s1=assembly_state(top);
  assert_state_changed(s1);
  require(std::abs(s1.im-s0.im)>1e-7&&std::abs(s1.clm-s0.clm)>1e-7&&std::abs(s1.crm-s0.crm)>1e-7,
          "T44 did not physically change ring masses");
  log("MAIN_VARIABLE_T_44_PASS");
  log("PHYSICAL_GEOMETRY_CHANGE_PASS");
  {
    std::ostringstream ss;
    ss<<std::setprecision(15)<<"MASS_DELTA inner="<<(s1.im-s0.im)
      <<" cupL="<<(s1.clm-s0.clm)<<" cupR="<<(s1.crm-s0.crm);
    log(ss.str());
  }
  require(base->Save(),"save changed assembly");
  close_doc(base);

  auto cb=require_ptr(docs->Open(asm_path().wstring(),true,false),"assembly reopen changed");
  IKompasDocument3DPtr cd=cb;
  auto ct=require_ptr(cd->GetTopPart(),"changed assembly top");
  require(cd->RebuildDocument(),"changed reopen doc rebuild");
  require(ct->RebuildModel(false),"changed reopen model rebuild");
  State sc=assembly_state(ct);
  assert_state_changed(sc);
  require(!near(sc.im,s0.im,1e-8),"changed mass lost after reopen");
  log("CHANGED_SAVE_CLOSE_REOPEN_PASS");

  auto Tc=part_var(ct,L"T");
  Tc->SetValue(P.T);
  require(ct->RebuildModel(false),"restore T40 model rebuild");
  require(cd->RebuildDocument(),"restore T40 doc rebuild");
  State sr=assembly_state(ct);
  assert_state_nominal(sr);
  require(near(sr.im,s0.im)&&near(sr.clm,s0.clm)&&near(sr.crm,s0.crm),"nominal masses did not restore");
  log("MAIN_VARIABLE_T_RESTORE_40_PASS");
  log("PHYSICAL_GEOMETRY_RESTORE_PASS");
  require(cb->Save(),"save restored nominal");
  close_doc(cb);

  auto fb=require_ptr(docs->Open(asm_path().wstring(),true,false),"final assembly reopen");
  IKompasDocument3DPtr fd=fb;
  auto ft=require_ptr(fd->GetTopPart(),"final top");
  require(fd->RebuildDocument(),"final doc rebuild");
  require(ft->RebuildModel(false),"final model rebuild");
  verify_master(ft);
  State sf=assembly_state(ft);
  assert_state_nominal(sf);
  require(near(sf.im,s0.im)&&near(sf.clm,s0.clm)&&near(sf.crm,s0.crm),"final nominal mass drift");
  close_doc(fb);
  log("FINAL_NOMINAL_REOPEN_PASS");
}

extern "C" int run_variant06_writer() {
  static bool done=false;
  if(done) return 0;
  try {
    fs::remove_all(OUTDIR);
    fs::create_directories(OUTDIR);
    lg.open(LOG,std::ios::out|std::ios::app);
    log("WORK4_VARIANT16_BEGIN");
    IApplication& app=GetKompasApplication();
    app.SetHideMessage(ksHideMessageYes);
    int ma=0,mi=0,re=0,bu=0; app.GetSystemVersion(ma,mi,re,bu);
    log("KOMPAS_VERSION="+std::to_string(ma)+"."+std::to_string(mi)+"."+std::to_string(re)+" build="+std::to_string(bu));
    log("BEFORE_LICENSE_MANAGER");
    auto license=app.GetApplicationLicenseManager();
    if(license){
      log("LICENSE_MANAGER_PASS");
      log("KOMPAS_VARIANT="+std::to_string((int)license->GetKompasVariant()));
      bool active3d=license->IsKompasModuleActive(ksKompasModule3D);
      log(std::string("LICENSE_3D_ACTIVE_BEFORE=")+(active3d?"1":"0"));
      if(!active3d){
        log("LICENSE_3D_ACTIVATE_REQUEST");
        license->SetKompasModuleActive(ksKompasModule3D,true);
        active3d=license->IsKompasModuleActive(ksKompasModule3D);
        log(std::string("LICENSE_3D_ACTIVE_AFTER=")+(active3d?"1":"0"));
      }
    } else {
      log("LICENSE_MANAGER_NULL");
    }
    log("BEFORE_GET_DOCUMENTS");
    auto docs=require_ptr(app.GetDocuments(),"Application Documents");
    log("AFTER_GET_DOCUMENTS");
    log("BEFORE_FIRST_PART_BUILD");

    double im=build_annulus(docs,inner_path(),L"INNER_DOUBLE_RING_V16",P.innerOD,P.d,P.T);
    log("INNER_DOUBLE_RING_NATIVE_PASS");
    double lm=build_annulus(docs,cup_l_path(),L"OUTER_CUP_L_V16",P.D,P.outerID,P.B);
    double rm=build_annulus(docs,cup_r_path(),L"OUTER_CUP_R_V16",P.D,P.outerID,P.B);
    log("TWO_OUTER_CUPS_NATIVE_PASS");
    build_roller(docs); log("TAPER_ROLLER_NATIVE_PASS");
    build_cage(docs); log("CAGE_HALF_NATIVE_PASS");
    build_rivet(docs); log("RIVET_NATIVE_PASS");
    build_assembly(docs); log("ASSEMBLY_NATIVE_BUILD_PASS");

    write_manifest("built");
    acceptance(docs);
    write_manifest("accepted");
    log("RESULT=PASS_NATIVE_WORK4_VARIANT16_REOPEN_REBUILD_PARAMETRIC");
    log("RESULT=PASS_NATIVE_WORK4_VARIANT16");
    done=true;
    return 0;
  } catch(const std::exception& e) {
    if(!lg.is_open()) { fs::create_directories(OUTDIR); lg.open(LOG,std::ios::out|std::ios::app); }
    log(std::string("EXCEPTION=")+e.what());
    log("RESULT=FAIL_NATIVE_WORK4_VARIANT16");
  } catch(...) {
    if(!lg.is_open()) { fs::create_directories(OUTDIR); lg.open(LOG,std::ios::out|std::ios::app); }
    log("EXCEPTION=unknown");
    log("RESULT=FAIL_NATIVE_WORK4_VARIANT16");
  }
  return 2;
}
