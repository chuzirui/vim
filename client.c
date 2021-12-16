
#include <stdio.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <string.h>
#define PORT 957

int main(int argc, char const *argv[])
{
	int sock = 0, valread, ii, pos;
	struct sockaddr_in serv_addr;
    char msg[128] = "";
    FILE* fileHandle;

    const uint32_t MagicMessageNumber = 0xfeed1966;
	char buffer[1024] = {0};
	if ((sock = socket(AF_INET, SOCK_STREAM, 0)) < 0) {
		printf("\n Socket creation error \n");
		return -1;
	}

	serv_addr.sin_family = AF_INET;
	serv_addr.sin_port = htons(PORT);

	// Convert IPv4 and IPv6 addresses from text to binary form
	if(inet_pton(AF_INET, "127.0.0.1", &serv_addr.sin_addr)<=0) {
		printf("\nInvalid address/ Address not supported \n");
		return -1;
	}

	if (connect(sock, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) < 0) {
		printf("\nConnection Failed \n");
		return -1;
	}

    *((uint32_t *)msg) = htonl(MagicMessageNumber);
    pos = sizeof(uint32_t);
    for (ii = 1; ii < argc; ii++) {
        strcpy(&msg[pos], argv[ii]);
        pos += strlen(argv[ii]) + 1;
    }
    msg[pos + 1] = 0;
	send(sock, msg, pos + 1, 0);

    fileHandle = fdopen(sock, "r");
    // Read until done
    while (fgets(buffer, 1024, fileHandle)) {
        printf("%s\n",buffer);
    }
    fclose(fileHandle);
	return 0;
}

