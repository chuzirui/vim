#!/usr/bin/env bash
sudo apt-get remove vim vim-runtime gvim
git clone https://github.com/vim/vim.git
cd vim
./configure --with-features=huge \
            --enable-multibyte \
            --enable-rubyinterp=yes \
            --enable-pythoninterp=yes \
            --with-python-config-dir=/usr/lib/python2.7/config \
            --enable-python3interp=yes \
            --with-python3-config-dir=/usr/lib/python3/config \
            --enable-perlinterp=yes \
            --enable-luainterp=yes \
                --enable-gui=gtk2 --enable-cscope --prefix=/usr
make -j
make install

