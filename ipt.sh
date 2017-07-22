#!/bin/sh
iptables -A INPUT  -s 49.5.6.114 -j REJECT --reject-with icmp-port-unreachable
for a in $(grep 'can not parse header' /var/log/ss.log | egrep '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}'   -o| sort|uniq);do iptables -A INPUT  -s $a -j REJECT --reject-with icmp-port-unreachable; done

iptables -A INPUT  -s 103.77.56.144 -j REJECT --reject-with icmp-port-unreachable
iptables -A INPUT  -s 104.194.76.13 -j REJECT --reject-with icmp-port-unreachable
iptables -A INPUT  -s 49.4.171.225 -j REJECT --reject-with icmp-port-unreachable
iptables -A INPUT  -s 49.4.171.226 -j REJECT --reject-with icmp-port-unreachable
grep 'can not parse header' ss.log | egrep '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}'   -o| sort|uniq


