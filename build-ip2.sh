#!/usr/bin/env bash
git clone git://git.kernel.org/pub/scm/linux/kernel/git/shemminger/iproute2.git
cd iproute2
sudo apt -y install pkg-config libmnl-dev  libdb-dev  lyx bison flex
./configure
sudo  make install
