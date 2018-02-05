#!/bin/sh

docker run --rm -t -i --net=host -v /etc/letsencrypt/:/etc/letsencrypt lea bash
letsencrypt-auto renew
cd /home/
cd letsencrypt/
service nginx stop
./letsencrypt-auto renew
service nginx start


