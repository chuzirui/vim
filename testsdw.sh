#!/usr/bin/env bash
sudo apt -y install httping
tail -f /var/log/ss.log > sydney.txt
for add in $(egrep  -o '[a-z][a-z0-9.-]+:[0-9]+' sydney.txt  | sort |uniq -d); \
do (httping https://$add -c 1 || httping http://$add -c 1) ; done \
    | egrep 'statistics|failed'

