#!/bin/sh
ips=`grep 'can not parse header' /var/log/ss.log| egrep '([0-9]{1,3}\.){3}[0-9]{1,3}' -o | sort| uniq`
oclok=`date`
port=6666
for a in $ips; do echo $a $oclok >> /var/log/ip.log; done
for a in $ips
    do
        iptables -D INPUT  -s $a -p tcp --dport $port -m string --string 'GET /' --algo bm -j REJECT --reject-with icmp-port-unreachable
        iptables -A INPUT  -s $a -p tcp --dport $port -m string --string 'GET /' --algo bm -j REJECT --reject-with icmp-port-unreachable
#       iptables -A INPUT  -s $a -j REJECT --reject-with icmp-port-unreachable
    done
