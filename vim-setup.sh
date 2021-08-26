#!/usr/bin/env bash
export EDITOR=vim
cp -r .vim/ ~/
cp .vimrc.c ~/.vimrc
cp .bashrc ~/
 [ ! -d "$HOME/.vim/bundle"  ] && git clone https://github.com/VundleVim/Vundle.vim.git ~/.vim/bundle/Vundle.vim
vim +PluginInstall +qall
chmod 0400 id_rsa
cp id_rsa id_rsa.pub ~/.ssh
git remote set-url origin ssh://git@github.com/chuzirui/vim.git
curl -o- -L https://raw.githubusercontent.com/TakeshiTseng/vim-language-p4/master/install.sh | bash
git config --global user.email "lechu@nvidia.com"
git config --global user.name "Leo Chu"
