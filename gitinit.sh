#!/usr/bin/env bash
echo "# md" >> README.md
git init
git add README.md
git commit -m "first commit"
git remote add origin https://github.com/chuzirui/md.git
git push -u origin master

