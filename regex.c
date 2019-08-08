#include <stdio.h>
#include <regex.h>

int main(){
    regex_t reg;
    const char* pattern = "^\\w+([-+.]\\w+)*@\\w+([-.]\\w+)*.\\w+([-.]\\w+)*$";
    regcomp(&reg, pattern, REG_EXTENDED);

    char* buf = "david19842003@gmail.com";
    const size_t nmatch = 1;
    regmatch_t pmatch[1];
    int status = regexec(&reg, buf, nmatch, pmatch, 0);

    if (status == REG_NOMATCH){
        printf("No Match\n");
    }
    else if (status == 0){
        printf("Match\n");
        for (int i = pmatch[0].rm_so; i < pmatch[0].rm_eo; i++){
            printf("%c", buf[i]);
        }
        printf("\n");
    }
    regfree(&reg);
    return 0;
}

