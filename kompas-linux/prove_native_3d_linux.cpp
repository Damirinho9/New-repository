#include <KsAPI.h>
#include <ksConstants.h>
#include <fstream>
#include <string>
#include <filesystem>
#include <cmath>

using namespace ksapi;

static std::ofstream lg("/tmp/work4_3d_probe.log", std::ios::out | std::ios::app);
static void log(const std::string& s){ lg << s << std::endl; lg.flush(); }

static bool add_rect(const IFragmentDocumentPtr& frag, double w, double h){
  auto vm = frag->GetViewsAndLayersManager();
  if(!vm){ log("FAIL views manager"); return false; }
  auto views = vm->GetViews();
  if(!views){ log("FAIL views"); return false; }
  auto view = views->GetActiveView();
  if(!view){ log("FAIL active view"); return false; }
  IDrawingContainerPtr dc = view;
  if(!dc){ log("FAIL drawing container"); return false; }
  auto lines = dc->GetLineSegments();
  if(!lines){ log("FAIL line segments"); return false; }
  const double x0=-w/2.0, x1=w/2.0, y0=-h/2.0, y1=h/2.0;
  const double xy[4][4]={{x0,y0,x1,y0},{x1,y0,x1,y1},{x1,y1,x0,y1},{x0,y1,x0,y0}};
  for(int i=0;i<4;i++){
    auto s=lines->Add();
    if(!s){ log("FAIL line Add"); return false; }
    s->SetX1(xy[i][0]); s->SetY1(xy[i][1]);
    s->SetX2(xy[i][2]); s->SetY2(xy[i][3]);
    s->SetStyle(ksCSNormal);
    if(!s->Update()){ log("FAIL line Update"); return false; }
  }
  return true;
}

extern "C" int run_variant06_writer(){
  static bool finished=false;
  if(finished) return 0;
  log("WORK4_3D_PROBE_BEGIN");
  try{
    IApplication& app = GetKompasApplication();
    app.SetHideMessage(ksHideMessageYes);
    int ma=0,mi=0,re=0,bu=0;
    app.GetSystemVersion(ma,mi,re,bu);
    log("KOMPAS_VERSION="+std::to_string(ma)+"."+std::to_string(mi)+"."+std::to_string(re)+" build="+std::to_string(bu));

    auto docs=app.GetDocuments();
    if(!docs){ log("FAIL documents"); return 2; }

    const std::wstring out=L"/tmp/work4_native3d_probe.m3d";
    std::filesystem::remove("/tmp/work4_native3d_probe.m3d");

    auto base=docs->AddWithDefaultSettings(ksDocumentPart, true);
    if(!base){ log("FAIL AddWithDefaultSettings part"); return 2; }
    app.SetActiveDocument(base);
    IKompasDocument3DPtr doc=base;
    if(!doc){ log("FAIL cast IKompasDocument3D"); return 2; }
    auto top=doc->GetTopPart();
    if(!top){ log("FAIL GetTopPart"); return 2; }
    log("CREATE_PART_PASS");

    auto sketches=top->GetSketchs();
    if(!sketches){ log("FAIL GetSketchs"); return 2; }
    auto sk=sketches->Add();
    if(!sk){ log("FAIL sketch Add"); return 2; }
    auto plane=top->GetDefaultObject(o3d_planeXOY);
    if(!plane){ log("FAIL default XOY"); return 2; }
    sk->SetPlane(plane);
    if(!sk->Update()){ log("FAIL sketch Update after SetPlane"); return 2; }
    auto frag=sk->BeginEdit(false);
    if(!frag){ log("FAIL sketch BeginEdit"); return 2; }
    if(!add_rect(frag,20.0,12.0)){ return 2; }
    if(!sk->EndEdit()){ log("FAIL sketch EndEdit"); return 2; }
    if(!sk->Update()){ log("FAIL sketch final Update"); return 2; }
    log("CREATE_SKETCH_PASS");

    auto exts=top->GetExtrusions();
    if(!exts){ log("FAIL GetExtrusions"); return 2; }
    auto ext=exts->Add(o3d_baseExtrusion);
    if(!ext){ log("FAIL extrusion Add"); return 2; }
    ext->SetSketch(sk);
    if(!ext->SetSideParameters(true, etBlind, 10.0, 0.0, false, IModelObjectPtr{})){
      log("FAIL SetSideParameters"); return 2;
    }
    if(!ext->Update()){ log("FAIL extrusion Update"); return 2; }
    if(!top->RebuildModel()){ log("FAIL top RebuildModel initial"); return 2; }
    if(!doc->RebuildDocument()){ log("FAIL doc RebuildDocument initial"); return 2; }
    const double m10=top->GetMass();
    log("MASS_DEPTH10="+std::to_string(m10));
    if(!(m10>0.0)){ log("FAIL initial mass"); return 2; }
    log("CREATE_EXTRUSION_PASS");

    if(!base->SaveAs(out)){ log("FAIL SaveAs"); return 2; }
    if(!std::filesystem::exists("/tmp/work4_native3d_probe.m3d") ||
       std::filesystem::file_size("/tmp/work4_native3d_probe.m3d")<1024){
      log("FAIL saved file absent/small"); return 2;
    }
    log("SAVE_AS_PASS bytes="+std::to_string(std::filesystem::file_size("/tmp/work4_native3d_probe.m3d")));

    if(!base->Close(kdDoNotSaveChanges)){ log("WARN first Close false"); }
    log("CLOSE_PASS");

    auto reopenedBase=docs->Open(out, true, false);
    if(!reopenedBase){ log("FAIL reopen"); return 2; }
    IKompasDocument3DPtr reopened=reopenedBase;
    if(!reopened){ log("FAIL reopened cast"); return 2; }
    auto rtop=reopened->GetTopPart();
    if(!rtop){ log("FAIL reopened top"); return 2; }
    if(!reopened->RebuildDocument()){ log("FAIL reopened RebuildDocument"); return 2; }
    if(!rtop->RebuildModel()){ log("FAIL reopened RebuildModel"); return 2; }
    auto rexts=rtop->GetExtrusions();
    if(!rexts || rexts->GetCount()<1){ log("FAIL persisted extrusion missing"); return 2; }
    auto rext=rexts->GetExtrusion(0);
    if(!rext){ log("FAIL GetExtrusion(0)"); return 2; }
    const double m10r=rtop->GetMass();
    log("MASS_REOPEN_DEPTH10="+std::to_string(m10r));
    if(std::abs(m10r-m10)>std::max(1e-6,m10*1e-6)){
      log("FAIL mass changed after reopen"); return 2;
    }
    log("REOPEN_REBUILD_PASS");

    if(!rext->SetSideParameters(true, etBlind, 14.0, 0.0, false, IModelObjectPtr{})){
      log("FAIL mutation SetSideParameters"); return 2;
    }
    if(!rext->Update()){ log("FAIL mutation extrusion Update"); return 2; }
    if(!rtop->RebuildModel()){ log("FAIL mutation RebuildModel"); return 2; }
    if(!reopened->RebuildDocument()){ log("FAIL mutation RebuildDocument"); return 2; }
    const double m14=rtop->GetMass();
    log("MASS_DEPTH14="+std::to_string(m14));
    if(!(m14>m10r*1.2)){ log("FAIL physical mutation mass unchanged"); return 2; }
    log("PHYSICAL_3D_MUTATION_PASS");

    if(!reopenedBase->Save()){ log("FAIL save mutated"); return 2; }
    if(!reopenedBase->Close(kdDoNotSaveChanges)){ log("WARN changed Close false"); }

    auto changedBase=docs->Open(out, true, false);
    if(!changedBase){ log("FAIL changed reopen"); return 2; }
    IKompasDocument3DPtr changed=changedBase;
    auto ctop=changed?changed->GetTopPart():IPartPtr{};
    if(!changed || !ctop){ log("FAIL changed reopened model"); return 2; }
    if(!changed->RebuildDocument() || !ctop->RebuildModel()){ log("FAIL changed reopen rebuild"); return 2; }
    const double m14r=ctop->GetMass();
    log("MASS_CHANGED_REOPEN="+std::to_string(m14r));
    if(std::abs(m14r-m14)>std::max(1e-6,m14*1e-6)){
      log("FAIL changed mass not persisted"); return 2;
    }
    log("MUTATED_SAVE_REOPEN_PASS");

    auto cexts=ctop->GetExtrusions();
    auto cext=cexts?cexts->GetExtrusion(0):IExtrusionPtr{};
    if(!cext){ log("FAIL changed extrusion lookup"); return 2; }
    if(!cext->SetSideParameters(true, etBlind, 10.0, 0.0, false, IModelObjectPtr{})){
      log("FAIL restore SetSideParameters"); return 2;
    }
    if(!cext->Update() || !ctop->RebuildModel() || !changed->RebuildDocument()){
      log("FAIL restore rebuild"); return 2;
    }
    const double m10restore=ctop->GetMass();
    log("MASS_RESTORED="+std::to_string(m10restore));
    if(std::abs(m10restore-m10)>std::max(1e-6,m10*1e-6)){
      log("FAIL physical restore mass"); return 2;
    }
    if(!changedBase->Save()){ log("FAIL save restored"); return 2; }
    changedBase->Close(kdDoNotSaveChanges);

    auto finalBase=docs->Open(out, true, false);
    IKompasDocument3DPtr finalDoc=finalBase;
    auto ftop=finalDoc?finalDoc->GetTopPart():IPartPtr{};
    if(!finalBase || !finalDoc || !ftop){ log("FAIL final reopen"); return 2; }
    if(!finalDoc->RebuildDocument() || !ftop->RebuildModel()){ log("FAIL final rebuild"); return 2; }
    const double mf=ftop->GetMass();
    log("MASS_FINAL="+std::to_string(mf));
    if(std::abs(mf-m10)>std::max(1e-6,m10*1e-6)){ log("FAIL final nominal mass"); return 2; }
    finalBase->Close(kdDoNotSaveChanges);

    log("FINAL_NOMINAL_REOPEN_PASS");
    log("RESULT=RUNTIME_NATIVE_3D_MUTATION_PASS");
    finished=true;
    return 0;
  }catch(const std::exception& e){
    log(std::string("EXCEPTION=")+e.what());
  }catch(...){
    log("EXCEPTION=unknown");
  }
  return 2;
}
