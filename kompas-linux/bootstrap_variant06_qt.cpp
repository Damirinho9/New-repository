#define _GNU_SOURCE
#include <QCoreApplication>
#include <QMetaObject>
#include <QTimer>
#include <QObject>
#include <Qt>
#include <dlfcn.h>
#include <pthread.h>
#include <unistd.h>
#include <fcntl.h>
#include <cstdio>
#include <cstring>
#include <limits.h>

static void blog(const char* s){
  int fd=open("/tmp/work1_bootstrap.log",O_WRONLY|O_CREAT|O_APPEND,0644);
  if(fd>=0){
    write(fd,s,strlen(s));
    write(fd,"\n",1);
    close(fd);
  }
}

static void run_writer_main_thread(){
  static void* h=nullptr;
  static int (*fn)(void)=nullptr;
  static int attempts=0;

  blog("BOOTSTRAP_MAIN_THREAD_ENTER");
  if(!h){
    h=dlopen("/tmp/writer_variant06.so",RTLD_NOW|RTLD_GLOBAL);
    if(!h){
      const char* e=dlerror();
      blog(e?e:"dlopen failed without dlerror");
      return;
    }
    blog("BOOTSTRAP_WRITER_LOADED_MAIN");
    dlerror();
    fn=(int(*)(void))dlsym(h,"run_variant06_writer");
    const char* e=dlerror();
    if(e||!fn){
      blog(e?e:"dlsym run_variant06_writer failed");
      return;
    }
  }

  blog("BOOTSTRAP_CALL_WRITER_MAIN");
  int rc=fn();
  char buf[128];
  snprintf(buf,sizeof(buf),"BOOTSTRAP_WRITER_MAIN_RC=%d ATTEMPT=%d",rc,attempts);
  blog(buf);

  if(rc==0){
    blog("BOOTSTRAP_WRITER_DONE");
    return;
  }
  attempts++;
  // Keep retrying while the KOMPAS document subsystem finishes asynchronous
  // initialization in headless mode. The workflow's polling window is finite,
  // so this limit remains bounded but no longer truncates the document wait.
  if(attempts>=150){
    blog("BOOTSTRAP_RETRY_LIMIT");
    return;
  }

  QCoreApplication* app=QCoreApplication::instance();
  if(!app){
    blog("BOOTSTRAP_NO_APP_FOR_RETRY");
    return;
  }
  QTimer::singleShot(
    1500,
    app,
    [](){
      blog("BOOTSTRAP_RETRY_TIMER_FIRED");
      run_writer_main_thread();
    }
  );
}

static void* scheduler(void*){
  blog("BOOTSTRAP_SCHEDULER_START");
  QCoreApplication* app=nullptr;
  for(int i=0;i<300;i++){
    app=QCoreApplication::instance();
    if(app) break;
    usleep(100000);
  }
  if(!app){
    blog("BOOTSTRAP_NO_QCOREAPPLICATION");
    return nullptr;
  }
  blog("BOOTSTRAP_QCOREAPPLICATION_FOUND");

  bool queued=QMetaObject::invokeMethod(
    app,
    [app](){
      blog("BOOTSTRAP_IN_GUI_QUEUE");
      QTimer::singleShot(
        30000,
        app,
        [](){
          blog("BOOTSTRAP_TIMER_FIRED_GUI");
          run_writer_main_thread();
        }
      );
    },
    Qt::QueuedConnection
  );
  blog(queued ? "BOOTSTRAP_INVOKE_QUEUED" : "BOOTSTRAP_INVOKE_FAILED");
  return nullptr;
}

__attribute__((constructor))
static void bootstrap_init(){
  char exe[PATH_MAX]={0};
  ssize_t n=readlink("/proc/self/exe",exe,sizeof(exe)-1);
  if(n>0) exe[n]='\0';
  const char* base=strrchr(exe,'/');
  base=base?base+1:exe;
  if(strcmp(base,"kKompas")!=0 && strcmp(base,"ksinvisible")!=0) return;

  int lockfd=open("/tmp/work1_bootstrap_once.lock",O_WRONLY|O_CREAT|O_EXCL,0644);
  if(lockfd<0) return;
  close(lockfd);

  blog("BOOTSTRAP_CONSTRUCTOR_MAIN_KOMPAS");
  pthread_t t;
  if(pthread_create(&t,nullptr,scheduler,nullptr)==0){
    pthread_detach(t);
  }else{
    blog("BOOTSTRAP_PTHREAD_CREATE_FAIL");
  }
}
