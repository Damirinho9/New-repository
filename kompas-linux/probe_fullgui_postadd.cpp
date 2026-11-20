#include <KsAPI.h>
#include <ksConstants.h>
#include <fstream>
#include <string>

using namespace ksapi;
static std::ofstream lg("/tmp/fullgui_postadd_probe.log",std::ios::out|std::ios::app);
static void log(const std::string&s){lg<<s<<std::endl;lg.flush();}

extern "C" int run_variant06_writer(){
  static bool done=false; if(done) return 0;
  try{
    IApplication& app=GetKompasApplication();
    app.SetHideMessage(ksHideMessageYes);
    int a=0,b=0,c=0,d=0;app.GetSystemVersion(a,b,c,d);
    log("KOMPAS_VERSION="+std::to_string(a)+"."+std::to_string(b)+"."+std::to_string(c));
    auto lm=app.GetApplicationLicenseManager();
    if(lm) log(std::string("LICENSE_BEFORE_ADD=")+(lm->IsKompasModuleActive(ksKompasModule3D)?"1":"0"));
    auto docs=app.GetDocuments(); if(!docs){log("FAIL documents");return 2;}
    auto base=docs->Add(ksDocumentPart,true); if(!base){log("FAIL Documents.Add");return 2;}
    log("DOCUMENT_ADD_PASS");
    if(!app.SetActiveDocument(base)){log("WARN SetActiveDocument false");}
    log("SET_ACTIVE_DOCUMENT_DONE");
    if(lm){
      bool x=lm->IsKompasModuleActive(ksKompasModule3D);
      log(std::string("LICENSE_AFTER_ADD_BEFORE_SET=")+(x?"1":"0"));
      if(!x) lm->SetKompasModuleActive(ksKompasModule3D,true);
      x=lm->IsKompasModuleActive(ksKompasModule3D);
      log(std::string("LICENSE_AFTER_ADD_AFTER_SET=")+(x?"1":"0"));
    }
    IKompasDocument3DPtr doc=base; if(!doc){log("FAIL cast3d");return 2;}
    auto top=doc->GetTopPart(); if(!top){log("FAIL top");return 2;}
    auto mc=top->GetModelContainer(); if(!mc){log("FAIL mc");return 2;}
    auto ss=mc->GetSketchs(); if(!ss){log("FAIL sketches");return 2;}
    auto sk=ss->Add(); if(!sk){log("FAIL sketch Add");return 2;}
    auto pl=top->GetDefaultObject(o3d_planeXOY); if(!pl){log("FAIL plane");return 2;}
    sk->SetPlane(pl); log("SKETCH_PLANE_PASS");
    auto frag=sk->BeginEdit(false);
    if(!frag){log("FAIL sketch BeginEdit");return 2;}
    log("SKETCH_BEGIN_EDIT_PASS");
    sk->EndEdit(); sk->Update();
    log("RESULT=FULLGUI_POSTADD_BEGINEDIT_PASS");
    done=true;return 0;
  }catch(const std::exception&e){log(std::string("EXCEPTION=")+e.what());}
   catch(...){log("EXCEPTION=unknown");}
  return 2;
}
