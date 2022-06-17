#include "stdio.h"
#include "string.h"
#include "stdbool.h"
#include "asm.h"
#include <metaresc.h>
#include <rpc/rpc.h>


TYPEDEF_ENUM (union_discriminator_t,
        (UD_VOID_PTR, , "v_ptr"),
        (UD_UC_ARRAY, , "uc_array"),
        (UD_U32, , "u32"),
        (UD_FLOAT_VAL, , "float_val")
        )

TYPEDEF_UNION (union_t,
        (void *, v_ptr),
        (unsigned char, uc_array, [sizeof (float)]),
        (uint32_t, u32),
        (float, float_val)
        )

TYPEDEF_STRUCT (discriminated_union_t,
            (union_t, union_val, , "u_d"),
            (union_discriminator_t, u_d)
            )

TYPEDEF_STRUCT (typep,
        ( int, a),);

TYPEDEF_STRUCT (tree_node_t,
  (char * ,value),
  (typep, ttt),
  (struct tree_node_t *, left),
  (struct tree_node_t *, right),
  );

TYPEDEF_STRUCT (resizable_array_t,
		(typep *, array, /* suffix */, /* text metadata */, { .offset = offsetof (resizable_array_t, array_size) }, "offset"),
		VOID(ssize_t, array_size),
		);

typedef enum enumber{
    ALPHA,
    BETA
}enumber;

int sum(int x, int y)
{
    return x*2+y;
}

typedef int (*p_fn)(int x, int y);

#define MR_MODE DESC
typedef struct {
    int type;
    int value;
    union_discriminator_t ud;
    enumber enu;
}d;
TYPEDEF_ENUM (enumber);
TYPEDEF_STRUCT (data, BITFIELD(int, type, :6), BITFIELD(int , value, :26));
TYPEDEF_STRUCT (d, type, value, ud, enu);
TYPEDEF_FUNC (int, p_fn, (int, int));

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
    XDR xdr;
    FILE *fp;
    via_ptr test[10];
    int foo = 10, bar = 15;
    char *u = "cesi";
    char v[] = "kilo";
    char f0[20];
    int tmp;
    p_fn p;
    p = sum;
    d test_d = {1, 2, UD_U32, BETA};
    bool test_bool = 3;
    char tool = -2;
    data t = {1, 15};
    resizable_array_t ret = { .array = (typep[]){{9}, {1}} , .array_size = 2 * sizeof(typep)};

    fp = fopen ("test1.out", "w");
    xdrstdio_create (&xdr, fp, XDR_ENCODE);
    MR_SAVE_XDR(resizable_array_t, &xdr, &ret);
    xdr_destroy (&xdr);
    fclose (fp);

    int fkk = *(int *)&t;
    tmp=foo, foo=bar, bar=tmp;

    resizable_array_t sload;
    fp = fopen ("test1.out", "r");
    xdrstdio_create (&xdr, fp, XDR_DECODE);

    MR_LOAD_XDR(resizable_array_t, &xdr, &sload);
    MR_PRINT ("ret = ", (resizable_array_t, &ret));
    MR_PRINT ("load = ", (resizable_array_t, &sload));

    MR_PRINT ("ret[0] = ", (typep, &ret.array[0]));
    MR_PRINT ("sload[0] = ", (typep, &sload.array[0]));
    xdr_destroy (&xdr);
    fclose (fp);

    if ((printf("hello"), 8) > 3)
        printf ("world\n");

    sprintf(f0, "%s%d", u, ALPHA);

    printf ("stle %d\n",f0[strlen(f0)]);
    printf ("strlen f0 %d\n",strlen(f0));
    printf ("sizeof f0 %d\n",sizeof(f0));
    printf ("strlen v %d\n",strlen(v));
    printf ("sizeof u %d\n",sizeof(u));
    printf ("\n",g);
    printf ("world%p \n",g);
    printf ("world%p \n",&g);
    printf ("sizeof bool %d %d\n",sizeof(test_bool), tool);
    printf ("fkk%d \n",fkk);
    printf ("type:%u value:%u \n",t.type, t.value);
    printf ("world%d \n",p(1,2));
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
    printf("sizeofu %lu sizeofv %lu\n", sizeof(u), sizeof(v));
    printf("foo*2+bar=%d\n", sum(foo,bar));
    printf("k[1]=%d, k[2] %d\n", k[1], k[2]);
    printf("k[3]=%d, k[2] %d\n", k[3], k[2]);
    g(test);

    tree_node_t root = {
        "root",
        {6},
        (tree_node_t[]){ { "left" } },
        (tree_node_t[]){ { "right" } },
    };

    MR_PRINT ("p = ", (p_fn, &p));
    MR_PRINT ("ttt = ", (typep, &root.ttt));
    MR_PRINT ("t = ", (data, &t));

    MR_PRINT ("d = ", (d, &test_d));
    MR_PRINT ("tree = ", (tree_node_t, &root));
    union_t  union_1 = { .v_ptr = (void *)0x557bb40b790f };
    discriminated_union_t uu = {union_1, UD_UC_ARRAY};
    MR_PRINT ((discriminated_union_t, &uu));

    return (EXIT_SUCCESS);

}
