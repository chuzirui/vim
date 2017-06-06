#!/bin/sh

/usr/bin/python /usr/local/bin/ssserver -c /etc/shadowsocks.json --user nobody --workers 2 --log-file /var/log/ss.log -d start
exit 0

