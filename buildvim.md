    sudo apt-get install libncurses5-dev libgnome2-dev libgnomeui-dev \
        libgtk2.0-dev libatk1.0-dev libbonoboui2-dev \
        libcairo2-dev libx11-dev libxpm-dev libxt-dev python-dev \
        python3-dev ruby-dev lua5.1 lua5.1-dev libperl-dev git
    On Ubuntu 16.04, liblua5.1-dev is the lua dev package name not lua5.1-dev.

(If you know what languages you'll be using, feel free to leave out packages you won't need, e.g. Python2 python-dev or Ruby ruby-dev. This principle heavily applies to the whole page.)

For Fedora 20, that would be the following:

    sudo yum install -y ruby ruby-devel lua lua-devel luajit \
        luajit-devel ctags git python python-devel \
        python3 python3-devel tcl-devel \
        perl perl-devel perl-ExtUtils-ParseXS \
        perl-ExtUtils-XSpp perl-ExtUtils-CBuilder \
        perl-ExtUtils-Embed
This step is needed to rectify an issue with how Fedora 20 installs XSubPP:

# symlink xsubpp (perl) from /usr/bin to the perl dir
`sudo ln -s /usr/bin/xsubpp /usr/share/perl5/ExtUtils/xsubpp 
Remove vim if you have it already.

`sudo apt-get remove vim vim-runtime gvim
On Ubuntu 12.04.2 you probably have to remove these packages as well:

    sudo apt-get remove vim-tiny vim-common vim-gui-common vim-nox
    Once everything is installed, getting the source is easy.

Note: If you are using Python, your config directory might have a machine-specific name (e.g. config-3.5m-x86_64-linux-gnu). Check in /usr/lib/python[2/3/3.5] to find yours, and change the python-config-dir and/or python3-config-dir arguments accordingly.

Note for Ubuntu 14.04 (Trusty) users: You can only use Python 2 or Python 3. If you try to compile vim with both python-config-dir and python3-config-dir, it will give you an error YouCompleteMe unavailable: requires Vim compiled with Python (2.6+ or 3.3+) support.

Add/remove the flags below to fit your setup. For example, you can leave out enable-luainterp if you don't plan on writing any Lua.

Also, if you're not using vim 8.0, make sure to set the VIMRUNTIMEDIR variable correctly below (for instance, with vim 8.0a, use /usr/share/vim/vim80a). Keep in mind that some vim installations are located directly inside /usr/share/vim; adjust to fit your system:

`cd ~
git clone https://github.com/vim/vim.git
cd vim
./configure --with-features=huge \
            --enable-multibyte \
            --enable-rubyinterp=yes \
            --enable-pythoninterp=yes \
            --with-python-config-dir=/usr/lib/python2.7/config \
            --enable-python3interp=yes \
            --with-python3-config-dir=/usr/lib/python3.5/config \
            --enable-perlinterp=yes \
            --enable-luainterp=yes \
            --enable-gui=gtk2 --enable-cscope --prefix=/usr

make VIMRUNTIMEDIR=/usr/share/vim/vim80
