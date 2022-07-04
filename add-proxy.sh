#!/usr/bin/env bash
pip install shadowsocks
apt-get install python-openssl
#ssh -D 8080 -fqN root@fugfw.com
sslocal -s fugfw.com -p 8558 -l 8080 -k Log1tech -m aes-256-cfb &

git config --global http.proxy 'socks5://127.0.0.1:8080'
git config --global https.proxy 'socks5://127.0.0.1:8080'

sudo echo 'proxy=socks5://127.0.0.1:9909' >> /etc/yum.conf
export http_proxy=socks5://127.0.0.1:9909
export https_proxy=socks5://127.0.0.1:9909

