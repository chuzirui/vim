#!/usr/bin/env bash
apt-get -y install sudo
sudo apt update -y
sudo apt install -y vim cscope xsel git-review exuberant-ctags || sudo dnf install -y vim cscope xsel git-review ctags
sudo apt install -y python3-pip autojump software-properties-common || sudo dnf install -y python-pip autojump
sudo apt install -y libssl-dev python-openssl silversearcher-ag curl || sudo dnf install -y openssl-devel the_silver_searcher
sudo apt install -y build-essential cmake python-dev python3-dev || sudo dnf -y install cmake python-devel python3-devel
sudo apt install -y libnss3 libgconf-2-4 gcc-multilib g++-multilib
sudo apt-get -y install libmnl-dev libelf-dev linux-headers-$(uname -r) pkg-config
sudo pip install flake8 tox thefuck
export EDITOR=vim
cp -r .vim/ ~/
cp .vimrc.c ~/.vimrc
#cp .bashrc ~/
 [ ! -d "$HOME/.vim/bundle"  ] && git clone https://github.com/VundleVim/Vundle.vim.git ~/.vim/bundle/Vundle.vim
vim +PluginInstall +qall
chmod 0400 id_rsa
cp id_rsa id_rsa.pub ~/.ssh
git remote set-url origin ssh://git@github.com/chuzirui/vim.git
curl -o- -L https://raw.githubusercontent.com/TakeshiTseng/vim-language-p4/master/install.sh | bash
git config --global user.email "chuzirui@gmail.com"
git config --global user.name "Leo Chu"
