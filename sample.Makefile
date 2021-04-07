CC=gcc
CFLAGS=-I.
DEPS = asm.h
OBJ = asm.o 

%.o: %.c $(DEPS)
	$(CC) -c -o $@ $< $(CFLAGS)

hello: $(OBJ)
	$(CC) -o $@ $^ $(CFLAGS)

