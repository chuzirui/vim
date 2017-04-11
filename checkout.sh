#!/bin/sh

git clone ssh://git@git.eng.vmware.com/nsx-ujo.git
cd nsx-ujo
find . -name "*.py" >> cscope.files
cscope -Rk

