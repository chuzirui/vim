#include "stdio.h"
#include "string.h"
typedef char via_ptr[20];
int sum(int x, int y)
{
    return x*2+y;
}
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

    strcpy(test[0], u);
    strcpy(test[1], v);
        __asm__ __volatile__("addl  %%ebx,%%eax"
                             :"=a"(foo)
                             :"a"(foo), "b"(bar)
                             );
        printf("foo+bar=%d, %s\n", foo, test[0]);
        printf("foo*2+bar=%d\n", sum(foo,bar));
        g(test);
        return 0;
}
