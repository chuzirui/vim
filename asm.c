#include "stdio.h"
int sum(int x, int y)
{
    return x*2+y;
}
int convert_dir (int dir)

{
    return !dir + 1;
}

#define A 1000000
int main(void)
{
    int foo = 10, bar = 15;
    volatile unsigned int b = -2;
    __asm__ __volatile__("addl  %%ebx,%%eax"
            :"=a"(foo)
            :"a"(foo), "b"(bar)
            );
    printf("foo+bar=%d\n", foo);
    printf("foo*2+bar=%d\n", sum(foo,bar));
    printf("%d\n",b > A);
    printf("%d\n",convert_dir(1));
    printf("%d\n",convert_dir(0));
    return 0;
}
