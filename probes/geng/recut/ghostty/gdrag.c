// Times libghostty-vt on core-bench's drag: 160x50, 100,000 lines of
// scrollback, the file fed, then N resizes to COLS x ROWS and back.
// usage: gdrag FILE N COLS ROWS [LINES [BYTES]]: a LINES or BYTES limit
// of 0 is none; both given replace the 100,000 lines.
#include <ghostty/vt.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec*1e3+t.tv_nsec/1e6;}
int main(int argc,char**argv){
  FILE*f=fopen(argv[1],"rb");fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);
  unsigned char*b=malloc(n);fread(b,1,n,f);fclose(f);
  int N=atoi(argv[2]),C=atoi(argv[3]),R=atoi(argv[4]);
  GhosttyTerminal term; ghostty_terminal_new(NULL,&term,160,50);
  size_t lines=argc>5?strtoul(argv[5],0,10):100000;
  size_t bytes=argc>6?strtoul(argv[6],0,10):0;
  ghostty_terminal_set(term,GHOSTTY_TERMINAL_OPT_SCROLLBACK_MAX_BYTES,bytes?&bytes:NULL);
  ghostty_terminal_set(term,GHOSTTY_TERMINAL_OPT_SCROLLBACK_MAX_LINES,lines?&lines:NULL);
  double t0=now();
  for(long i=0;i<n;i+=65536) ghostty_terminal_vt_write(term,b+i,(n-i<65536)?n-i:65536);
  double t1=now();
  for(int i=0;i<N;i++){ if(i%2==0) ghostty_terminal_resize(term,C,R,10,20); else ghostty_terminal_resize(term,160,50,10,20);}
  double t2=now();
  size_t hist=0; ghostty_terminal_get(term,GHOSTTY_TERMINAL_DATA_SCROLLBACK_ROWS,&hist);
  printf("feed %.0f ms; %d resizes in %.1f ms; history %zu\n",t1-t0,N,t2-t1,hist);
}
