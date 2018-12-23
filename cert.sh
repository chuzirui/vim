#!/bin/sh

#docker run --rm -it -v "/root/letsencrypt/log:/var/log/letsencrypt" -v "/var/www/html/shared:/var/www/" -v "/etc/letsencrypt:/etc/letsencrypt" -v "/root/letsencrypt/lib:/var/lib/letsencrypt" lojzik/letsencrypt certonly --webroot --webroot-path /var/www --email EMAIL -d domain
cd /home/
cd letsencrypt/
service nginx stop
./letsencrypt-auto renew
service nginx start


