#include <KsAPI.h>
#include <ksConstants.h>
#include <filesystem>
#include <fstream>
#include <string>
#include <cmath>

using namespace ksapi;
namespace fs=std::filesystem;

static std::ofstream lg("/tmp/active3d_seed_probe.log",std::ios::out|std::ios::app);
static void log(const std::string&s){lg<<s<<std::endl;lg.flush();}

static bool rect(const IFragmentDocumentPtr& frag){
  auto vm=frag->GetViewsAndLayersManager(); if(!vm){log("FAIL views manager");return false;}
  auto views=vm->GetViews(); if(!views){log("FAIL views");return false;}
  auto view=views->GetActiveView(); if(!view){log("FAIL active view");return false;}
  IDrawingContainerPtr dc=view; if(!dc){log("FAIL drawing container");return false;}
  auto lines=dc->GetLineSegments(); if(!lines){log("FAIL lines");return false;}
  const double p[4][4]={{-10,-6,10,-6},{10,-6,10,6},{10,6,-10,6},{-10,6,-10,-6}};
  for(int i=0;i<4;i++){
    auto s=lines->Add(); if(!s){log("FAIL line Add");return false;}
    s->SetX1(p[i][0]);s->SetY1(p[i][1]);s->SetX2(p[i][2]);s->SetY2(p[i][3]);s->SetStyle(ksCSNormal);
    if(!s->Update()){log("FAIL line Update");return false;}
  }
  return true;
}

extern "C" int run_variant06_writer(){
  static bool done=false;
  if(done) return 0;
  try{
    log("ACTIVE3D_SEED_BEGIN");
    IApplication& app=GetKompasApplication();
    app.SetHideMessage(ksHideMessageYes);
    int a=0,b=0,c=0,d=0; app.GetSystemVersion(a,b,c,d);
    log("KOMPAS_VERSION="+std::to_string(a)+"."+std::to_string(b)+"."+std::to_string(c));
    auto lm=app.GetApplicationLicenseManager();
    if(lm){
      bool x=lm->IsKompasModuleActive(ksKompasModule3D);
      log(std::string("LICENSE_3D_ACTIVE=")+(x?"1":"0"));
    }
    auto base=app.GetActiveDocument();
    if(!base){log("FAIL GetActiveDocument");return 2;}
    log("ACTIVE_DOCUMENT_PASS");
    IKompasDocument3DPtr doc=base;
    if(!doc){log("FAIL active cast 3D");return 2;}
    auto top=doc->GetTopPart();
    if(!top){log("FAIL active GetTopPart");return 2;}
    log("ACTIVE_TOP_PART_PASS");
    auto mc=top->GetModelContainer(); if(!mc){log("FAIL model container");return 2;}
    auto sketches=mc->GetSketchs(); if(!sketches){log("FAIL sketches");return 2;}
    auto sk=sketches->Add(); if(!sk){log("FAIL sketch Add");return 2;}
    auto plane=top->GetDefaultObject(o3d_planeXOY); if(!plane){log("FAIL plane");return 2;}
    sk->SetPlane(plane);
    log("SKETCH_PLANE_SET_PASS");
    auto frag=sk->BeginEdit(false);
    if(!frag){log("FAIL sketch BeginEdit");return 2;}
    log("SKETCH_BEGIN_EDIT_PASS");
    if(!rect(frag)) return 2;
    if(!sk->EndEdit()){log("FAIL EndEdit");return 2;}
    if(!sk->Update()){log("FAIL sketch Update");return 2;}
    log("SKETCH_GEOMETRY_PASS");
    auto exts=mc->GetExtrusions(); if(!exts){log("FAIL extrusions");return 2;}
    auto ext=exts->Add(o3d_baseExtrusion); if(!ext){log("FAIL extrusion Add");return 2;}
    ext->SetProfiles({IModelObjectPtr(sk)});
    if(!ext->SetSideParameters(true,etBlind,10.0,0.0,false,IModelObjectPtr{})){log("FAIL side params");return 2;}
    if(!ext->Update()){log("FAIL extrusion Update");return 2;}
    if(!top->RebuildModel(false)){log("FAIL RebuildModel");return 2;}
    if(!doc->RebuildDocument()){log("FAIL RebuildDocument");return 2;}
    double m=top->GetMass();
    log("MASS="+std::to_string(m));
    if(!(m>0)){log("FAIL mass");return 2;}
    fs::path out="/tmp/active3d_seed_result.m3d";
    fs::remove(out);
    if(!base->SaveAs(out.wstring())){log("FAIL SaveAs");return 2;}
    if(!fs::exists(out)||fs::file_size(out)<1024){log("FAIL output missing");return 2;}
    log("SAVE_AS_PASS bytes="+std::to_string(fs::file_size(out)));
    log("RESULT=ACTIVE3D_SEED_NATIVE_MUTATION_PASS");
    done=true;
    return 0;
  }catch(const std::exception&e){log(std::string("EXCEPTION=")+e.what());}
   catch(...){log("EXCEPTION=unknown");}
  return 2;
}
