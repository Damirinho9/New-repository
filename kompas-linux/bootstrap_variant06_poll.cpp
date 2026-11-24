#define _GNU_SOURCE
#include <dlfcn.h>
#include <pthread.h>
#include <unistd.h>
#include <fcntl.h>
#include <poll.h>
#include <sys/epoll.h>
#include <signal.h>
#include <time.h>
#include <cstdio>
#include <cstring>
#include <limits.h>

static pthread_t g_main_thread;
static timespec g_start{};
static timespec g_next{};
static bool g_enabled=false;
static bool g_done=false;
static bool g_in_writer=false;
static int g_attempts=0;
static void* g_writer=nullptr;
static int (*g_fn)(void)=nullptr;

static void blog(const char* s){
  int fd=open("/tmp/work1_bootstrap.log",O_WRONLY|O_CREAT|O_APPEND,0644);
  if(fd>=0){ write(fd,s,strlen(s)); write(fd,"\n",1); close(fd); }
}
static long long ms(const timespec& t){ return (long long)t.tv_sec*1000LL+t.tv_nsec/1000000LL; }
static timespec nowts(){ timespec t{}; clock_gettime(CLOCK_MONOTONIC,&t); return t; }

static void maybe_run_writer(){
  if(!g_enabled||g_done||g_in_writer||!pthread_equal(pthread_self(),g_main_thread)) return;
  auto now=nowts();
  if(ms(now)-ms(g_start)<30000) return;
  if(g_attempts>0 && ms(now)<ms(g_next)) return;
  g_in_writer=true;
  blog("POLL_BOOTSTRAP_MAIN_THREAD_ENTER");
  if(!g_writer){
    g_writer=dlopen("/tmp/writer_variant06.so",RTLD_NOW|RTLD_GLOBAL);
    if(!g_writer){
      const char* e=dlerror(); blog(e?e:"dlopen writer failed"); g_done=true; g_in_writer=false; return;
    }
    dlerror();
    g_fn=(int(*)(void))dlsym(g_writer,"run_variant06_writer");
    const char* e=dlerror();
    if(e||!g_fn){ blog(e?e:"dlsym writer failed"); g_done=true; g_in_writer=false; return; }
    blog("POLL_BOOTSTRAP_WRITER_LOADED_MAIN");
  }
  int rc=g_fn();
  char b[128]; snprintf(b,sizeof(b),"POLL_BOOTSTRAP_WRITER_RC=%d ATTEMPT=%d",rc,g_attempts); blog(b);
  if(rc==0){ g_done=true; blog("POLL_BOOTSTRAP_WRITER_DONE"); }
  else{
    ++g_attempts;
    if(g_attempts>=20){ g_done=true; blog("POLL_BOOTSTRAP_RETRY_LIMIT"); }
    else{
      g_next=nowts();
      long long n=ms(g_next)+1500;
      g_next.tv_sec=n/1000; g_next.tv_nsec=(n%1000)*1000000LL;
    }
  }
  g_in_writer=false;
}

template<class F> static F nextsym(const char* n){
  static pthread_mutex_t mu=PTHREAD_MUTEX_INITIALIZER;
  pthread_mutex_lock(&mu);
  void* p=dlsym(RTLD_NEXT,n);
  pthread_mutex_unlock(&mu);
  return reinterpret_cast<F>(p);
}

extern "C" int poll(struct pollfd* fds,nfds_t nfds,int timeout){
  using Fn=int(*)(struct pollfd*,nfds_t,int);
  static Fn real=nextsym<Fn>("poll");
  maybe_run_writer();
  return real?real(fds,nfds,timeout):-1;
}
extern "C" int ppoll(struct pollfd* fds,nfds_t nfds,const struct timespec* timeout,const sigset_t* mask){
  using Fn=int(*)(struct pollfd*,nfds_t,const struct timespec*,const sigset_t*);
  static Fn real=nextsym<Fn>("ppoll");
  maybe_run_writer();
  return real?real(fds,nfds,timeout,mask):-1;
}
extern "C" int epoll_wait(int epfd,struct epoll_event* events,int maxevents,int timeout){
  using Fn=int(*)(int,struct epoll_event*,int,int);
  static Fn real=nextsym<Fn>("epoll_wait");
  maybe_run_writer();
  return real?real(epfd,events,maxevents,timeout):-1;
}
extern "C" int epoll_pwait(int epfd,struct epoll_event* events,int maxevents,int timeout,const sigset_t* mask){
  using Fn=int(*)(int,struct epoll_event*,int,int,const sigset_t*);
  static Fn real=nextsym<Fn>("epoll_pwait");
  maybe_run_writer();
  return real?real(epfd,events,maxevents,timeout,mask):-1;
}

__attribute__((constructor))
static void init(){
  char exe[PATH_MAX]={0};
  ssize_t n=readlink("/proc/self/exe",exe,sizeof(exe)-1);
  if(n>0) exe[n]='\0';
  const char* base=strrchr(exe,'/'); base=base?base+1:exe;
  if(strcmp(base,"kKompas")!=0 && strcmp(base,"ksinvisible")!=0) return;
  int fd=open("/tmp/work1_bootstrap_once.lock",O_WRONLY|O_CREAT|O_EXCL,0644);
  if(fd<0) return; close(fd);
  g_main_thread=pthread_self(); g_start=nowts(); g_next=g_start; g_enabled=true;
  blog("POLL_BOOTSTRAP_CONSTRUCTOR_MAIN_KOMPAS");
}
