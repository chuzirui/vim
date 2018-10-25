#! /bin/bash

sudo apt update -y
sudo apt install python python-pip -y
pip install shadowsocks --user
a=`whereis ssserver | grep -o ' .*'`

sudo /usr/bin/python $a -p 8558 -k Log1tech -m aes-256-cfb --user nobody --workers 2 --log-file /var/log/ss.log -d start
sslocal -s fugfw.com -p 8558 -l 8964 -k Log1tech -m aes-256-cfb

