#include "stdio.h"
#include "string.h"
#include "asm.h"

int sum(int x, int y)
{
    return x*2+y;
}


#define A 1000000

void  g(via_ptr *v_array)
{
    printf ("%p\n", v_array);
    printf ("%s\n", *v_array);
    printf ("%p\n", v_array );
    printf ("%s\n", *(++v_array));
}
int main(void)
{
    via_ptr test[10];
    int foo = 10, bar = 15;
    char *u = "cesi";
    char v[] = "kilo";
    int tmp;

    tmp=foo, foo=bar, bar=tmp;


    if ((printf("hello"), 8) > 3)
	    printf ("world");

    int k[foo];
    k[1] = 1;
    strcpy(test[0], u);
    strcpy(test[1], v);
    k[3] = (printf ("%s,%d hello\n", __FUNCTION__, __LINE__), 6);
        __asm__ __volatile__("addl  %%ebx,%%eax"
                             :"=a"(foo)
                             :"a"(foo), "b"(bar)
                             );
        printf("foo+bar=%d, %s\n", foo, test[0]);
        printf("foo*2+bar=%d\n", sum(foo,bar));
        printf("k[1]=%d, k[2] %d\n", k[1], k[2]);
        printf("k[3]=%d, k[2] %d\n", k[3], k[2]);
        g(test);
        return 0;
}
