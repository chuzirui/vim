#!/bin/bash
ips=`grep 'can not parse header' /var/log/shadowsocksr.log  | grep -o ffff.* | grep -o '[0-9].*:' | cut -f 1 -d ':' | sort -un`
for a in $ips
    do
        iptables -D INPUT  --protocol tcp --match tcp --dport $1 --source $a/32 --jump REJECT --reject-with icmp-port-unreachable
        iptables -A INPUT  --protocol tcp --match tcp --dport $1 --source $a/32 --jump REJECT --reject-with icmp-port-unreachable
    done

echo "" > /var/log/shadowsocksr.log


