#include <stdio.h>
#include <string.h>
#include <regex.h>

int main ()
{
  char * source = ("INVITE sip:sip@13.2.2.2 SIP/2.0 \r\n\
Via: SIP/2.0/UDP 10.208.135.82:5060;rport;branch=z9hG4bK1737632929\
From: <sip:root@10.208.135.82>;tag=1964403804\
To: <sip:sip@13.2.2.2> \r\n\
Call-ID: 1255714136\r\n\
CSeq: 20 INVITE\
Contact: <sip:root@10.208.135.82>\
Content-Type: application/sdp\
Allow: INVITE, ACK, CANCEL, OPTIONS, BYE, REFER, NOTIFY, MESSAGE, SUBSCRIBE, INFO\
Max-Forwards: 70\
User-Agent: Linphone/3.6.1 (eXosip2/4.1.0)\
Subject: Phone call\
Content-Length:   326\
\
v=0\
o=root 3217 98 IN IP4 10.208.135.82\
s=Talk\
c=IN IP4 10.208.135.82\
t=0 0\
m=audio 7078 RTP/AVP 124 111 110 0 8 101\
a=rtpmap:124 opus/48000\
a=fmtp:124 useinbandfec=1; usedtx=1\
a=rtpmap:111 speex/16000\
a=fmtp:111 vbr=on\
a=rtpmap:110 speex/8000\
a=fmtp:110 vbr=on\
a=rtpmap:101 telephone-event/8000\
a=fmtp:101 0-11");
  char * regexString = "Call-ID: (.*)\r\n";
  size_t maxMatches = 2;
  size_t maxGroups = 3;

  regex_t regexCompiled;
  regmatch_t groupArray[maxGroups];
  unsigned int m;
  char * cursor;

  if (regcomp(&regexCompiled, regexString, REG_EXTENDED))
    {
      printf("Could not compile regular expression.\n");
      return 1;
    };

  m = 0;
  cursor = source;
  for (m = 0; m < maxMatches; m ++)
    {
      if (regexec(&regexCompiled, cursor, maxGroups, groupArray, 0))
        break;  // No more matches

      unsigned int g = 0;
      unsigned int offset = 0;
      for (g = 0; g < maxGroups; g++)
        {
          if (groupArray[g].rm_so == (size_t)-1)
            break;  // No more groups

          if (g == 0)
            offset = groupArray[g].rm_eo;

          char cursorCopy[strlen(cursor) + 1];
          strcpy(cursorCopy, cursor);
          cursorCopy[groupArray[g].rm_eo] = 0;
          printf("Match %u, Group %u: [%2u-%2u]: %s\n",
                 m, g, groupArray[g].rm_so, groupArray[g].rm_eo,
                 cursorCopy + groupArray[g].rm_so);
        }
      cursor += offset;
    }

  regfree(&regexCompiled);

  return 0;
}

