#!/bin/sh
apt -y install python-pip
pip install shadowsocks

/usr/bin/python /usr/local/bin/ssserver -c /etc/shadowsocks.json --user nobody --workers 2 --log-file /var/log/ss.log -d start
sudo add-apt-repository ppa:hzwhuang/ss-qt5
sudo apt-get update
sudo apt-get install shadowsocks-qt5

sudo apt-get -y install --no-install-recommends build-essential autoconf libtool \
      libssl-dev gawk debhelper dh-systemd init-system-helpers pkg-config asciidoc \
      xmlto apg libpcre3-dev zlib1g-dev libev-dev libudns-dev libsodium-dev
git clone https://github.com/shadowsocks/shadowsocks-libev.git
cd shadowsocks-libev
git submodule update --init
./autogen.sh && ./configure && make
sudo make install
sudo pip install shadowsocks
sslocal -s fugfw.com -p 8558 -l 8964 -k Log1tech -m aes-256-cfb


