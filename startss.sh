#!/bin/sh
apt -y install python-pip
pip install shadowsocks

/usr/bin/python /usr/local/bin/ssserver -c /etc/shadowsocks.json --user nobody --workers 2 --log-file /var/log/ss.log -d start
exit 0
sudo add-apt-repository ppa:hzwhuang/ss-qt5
sudo apt-get update
sudo apt-get install shadowsocks-qt5

