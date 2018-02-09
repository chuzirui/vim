#! /bin/bash

sudo apt update -y
sudo apt install python python-pip -y
sudo pip install shadowsocks
a=`whereis ssserver | grep -o ' .*'`

/usr/bin/python $a -p 8558 -k Log1tech -m aes-256-cfb --user nobody --workers 2 --log-file /var/log/ss.log -d start
sudo pip install shadowsocks
sslocal -s fugfw.com -p 8558 -l 8964 -k Log1tech -m aes-256-cfb

