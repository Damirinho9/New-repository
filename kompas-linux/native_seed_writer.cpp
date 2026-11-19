#include <KsAPI.h>
#include <ksConstants.h>
#include <filesystem>
#include <fstream>
#include <string>

using namespace ksapi;
namespace fs=std::filesystem;

static const fs::path OUT{"/tmp/native_seed"};
static std::ofstream lg;
static void log(const std::string& s){ lg<<s<<std::endl; lg.flush(); }
template<class T> static T req(const T& v,const std::string& m){ if(!v){log("FAIL "+m); throw std::runtime_error(m);} return v; }

static fs::path native_template(const std::string& ext){
  const fs::path dir{"/opt/ascon/kompas3d-v25/Utils/KLibEditor/Templates"};
  if(!fs::exists(dir)) throw std::runtime_error("template directory missing");
  for(const auto& e:fs::directory_iterator(dir))
    if(e.is_regular_file() && e.path().extension()==ext) return e.path();
  throw std::runtime_error("template missing "+ext);
}
static void close_doc(const IKompasDocumentPtr& d){ try{d->Close(kdDoNotSaveChanges);}catch(...){} }

extern "C" int run_variant06_writer(){
  static bool done=false;
  if(done) return 0;
  try{
    fs::remove_all(OUT); fs::create_directories(OUT);
    lg.open(OUT/"seed.log",std::ios::out|std::ios::app);
    IApplication& app=GetKompasApplication();
    app.SetHideMessage(ksHideMessageYes);
    int ma=0,mi=0,re=0,bu=0; app.GetSystemVersion(ma,mi,re,bu);
    log("KOMPAS_VERSION="+std::to_string(ma)+"."+std::to_string(mi)+"."+std::to_string(re)+" build="+std::to_string(bu));
    auto docs=req(app.GetDocuments(),"Application Documents");

    auto pt=native_template(".m3d");
    log("PART_TEMPLATE="+pt.string());
    auto pb=req(docs->AddNewDocumentFromTemplate(pt.wstring(),false),"AddNewDocumentFromTemplate part");
    IKompasDocument3DPtr pd=pb;
    req(pd,"part cast");
    req(pd->GetTopPart(),"part TopPart");
    req(pb->SaveAs((OUT/"BlankPart.m3d").wstring()),"BlankPart SaveAs");
    close_doc(pb);
    req(fs::exists(OUT/"BlankPart.m3d")&&fs::file_size(OUT/"BlankPart.m3d")>1024,"BlankPart missing");
    log("BLANK_PART_NATIVE_PASS");

    auto at=native_template(".a3d");
    log("ASSEMBLY_TEMPLATE="+at.string());
    auto ab=req(docs->AddNewDocumentFromTemplate(at.wstring(),false),"AddNewDocumentFromTemplate assembly");
    IKompasDocument3DPtr ad=ab;
    req(ad,"assembly cast");
    req(ad->GetTopPart(),"assembly TopPart");
    req(ab->SaveAs((OUT/"BlankAssembly.a3d").wstring()),"BlankAssembly SaveAs");
    close_doc(ab);
    req(fs::exists(OUT/"BlankAssembly.a3d")&&fs::file_size(OUT/"BlankAssembly.a3d")>1024,"BlankAssembly missing");
    log("BLANK_ASSEMBLY_NATIVE_PASS");

    log("RESULT=PASS_NATIVE_SEED_ALT");
    done=true;
    return 0;
  }catch(const std::exception& e){
    if(!lg.is_open()){fs::create_directories(OUT);lg.open(OUT/"seed.log",std::ios::out|std::ios::app);}
    log(std::string("EXCEPTION=")+e.what());
    log("RESULT=FAIL_NATIVE_SEED_ALT");
  }catch(...){
    if(!lg.is_open()){fs::create_directories(OUT);lg.open(OUT/"seed.log",std::ios::out|std::ios::app);}
    log("EXCEPTION=unknown");
    log("RESULT=FAIL_NATIVE_SEED_ALT");
  }
  return 2;
}
