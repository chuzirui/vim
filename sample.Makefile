CC=gcc
CFLAGS=-I.
CFLAGS += -I./Metaresc/src `xml2-config --cflags`
LDLIBS += -ldl -lmetaresc  `xml2-config --libs`
DEPS = asm.h
OBJ = asm.o 

%.o: %.c $(DEPS)
	$(CC) -c -o $@ $< $(CFLAGS)

hello: $(OBJ)
	$(CC) -o $@ $^ $(CFLAGS) $(LDLIBS)

