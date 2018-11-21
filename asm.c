#include "stdio.h"
int sum(int x, int y)
{
    return x*2+y;
}

int main(void)
{
        int foo = 10, bar = 15;
        __asm__ __volatile__("addl  %%ebx,%%eax"
                             :"=a"(foo)
                             :"a"(foo), "b"(bar)
                             );
        printf("foo+bar=%d\n", foo);
        printf("foo*2+bar=%d\n", sum(foo,bar));
        return 0;
}
