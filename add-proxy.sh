#!/usr/bin/env bash
pip install shadowsocks
#ssh -D 8080 -fqN root@fugfw.com
sslocal -s 172.104.213.238 -p 8558 -l 8080 -k Qyff2011 -m aes-256-cfb &

git config --global http.proxy 'socks5://127.0.0.1:8080'
git config --global https.proxy 'socks5://127.0.0.1:8080'

