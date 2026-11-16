#define _GNU_SOURCE
#include <dlfcn.h>
#include <pthread.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>

static void blog(const char* s){
  int fd=open("/tmp/work1_bootstrap.log",O_WRONLY|O_CREAT|O_APPEND,0644);
  if(fd>=0){
    write(fd,s,strlen(s));
    write(fd,"\n",1);
    close(fd);
  }
}

static void* worker(void* unused){
  (void)unused;
  blog("BOOTSTRAP_THREAD_START");
  sleep(15);
  blog("BOOTSTRAP_DLOPEN_WRITER");
  void* h=dlopen("/tmp/writer_variant06.so",RTLD_NOW|RTLD_GLOBAL);
  if(!h){
    const char* e=dlerror();
    blog(e?e:"dlopen failed without dlerror");
    return NULL;
  }
  blog("BOOTSTRAP_WRITER_LOADED");
  dlerror();
  int (*fn)(void)=(int(*)(void))dlsym(h,"run_variant06_writer");
  const char* e=dlerror();
  if(e||!fn){
    blog(e?e:"dlsym run_variant06_writer failed");
    return NULL;
  }
  blog("BOOTSTRAP_CALL_WRITER");
  int rc=fn();
  char buf[80];
  snprintf(buf,sizeof(buf),"BOOTSTRAP_WRITER_RC=%d",rc);
  blog(buf);
  return NULL;
}

__attribute__((constructor))
static void bootstrap_init(void){
  char exe[PATH_MAX]={0};
  ssize_t n=readlink("/proc/self/exe",exe,sizeof(exe)-1);
  if(n>0) exe[n]='\0';
  const char* base=strrchr(exe,'/');
  base=base?base+1:exe;
  if(strcmp(base,"kKompas")!=0){
    return;
  }
  blog("BOOTSTRAP_CONSTRUCTOR_MAIN_KOMPAS");
  pthread_t t;
  if(pthread_create(&t,NULL,worker,NULL)==0){
    pthread_detach(t);
  }else{
    blog("BOOTSTRAP_PTHREAD_CREATE_FAIL");
  }
}
