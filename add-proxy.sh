#!/usr/bin/env bash
ssh -D 8080 -fqN root@fugfw.com
git config --global http.proxy 'socks5://127.0.0.1:8080'
git config --global https.proxy 'socks5://127.0.0.1:8080'

