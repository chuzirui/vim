#!/usr/bin/env bash
ip a add 10.75.205.142/24 dev ens3
ip link set dev ens3 up
ip link set dev ens10 up
ip link set dev ens10d1 up
ip link set dev ens9 up

ip r add 0.0.0.0/0 via 10.75.205.1
systemd-resolve --set-dns=10.75.68.106 --set-dns=10.75.68.102 --interface=ens3 --set-domain=mtbc.labs.mlnx. --set-domain=labs.mlnx. --set-domain=mlnx. --set-domain=lab.mtl.com. --set-domain=mtl.com.
hostname mtbc-sai-host1
sysctl -w net.ipv6.conf.all.disable_ipv6=1
sysctl -w net.ipv6.conf.default.disable_ipv6=1

