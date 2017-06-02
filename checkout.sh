#!/bin/sh
mkdir -p ~/.ssh
scp root@10.39.1.2:/root/.ssh/id_rsa ~/.ssh/
scp root@10.39.1.2:/root/.ssh/id_rsa.pub ~/.ssh/
git clone ssh://git@git.eng.vmware.com/nsx-ujo.git
git config --global user.email "chul@vmware.com"
git config --global user.name "Leo Chu"

cd nsx-ujo
find . -name "*.py" >> cscope.files
find . -name "nsx" >> cscope.files
find "nsx_ujo/bin" -name "nsx" >> cscope.files
cscope -Rk

