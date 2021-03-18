set nocompatible              " be iMproved, required
filetype off                  " required


" set the runtime path to include Vundle and initialize
set rtp+=~/.vim/bundle/Vundle.vim
call vundle#begin()
" alternatively, pass a path where Vundle should install plugins
"call vundle#begin('~/some/path/here')

" let Vundle manage Vundle, required
Plugin 'VundleVim/Vundle.vim'

" The following are examples of different formats supported.
" Keep Plugin commands between vundle#begin/end.
" plugin on GitHub repo
" plugin from http://vim-scripts.org/vim/scripts.html
" Plugin 'L9'
" Git plugin not hosted on GitHub
Plugin 'ntpeters/vim-better-whitespace'
Plugin 'scrooloose/nerdcommenter'
Plugin 'scrooloose/syntastic'
Plugin 'scrooloose/nerdtree'
Plugin 'altercation/vim-colors-solarized'
Plugin 'tpope/vim-fugitive'
Plugin 'nathanaelkane/vim-indent-guides'
Plugin 'Yggdroot/indentLine'
Plugin 'spf13/vim-colors'
Plugin 'flazz/vim-colorschemes'
Plugin 'majutsushi/tagbar'
" Plugin 'majutsushi/tagbar', { 'commit': 'd4a08c33e516314f35c541b34fe7f909c2ff4381'  }
" Plugin 'jiangmiao/auto-pairs'
Plugin 'vim-airline/vim-airline'
Plugin 'vim-airline/vim-airline-themes'
Plugin 'easymotion/vim-easymotion'
Plugin 'dkprice/vim-easygrep'
Plugin 'mileszs/ack.vim'

" git repos on your local machine (i.e. when working on your own plugin)
Plugin 'rstacruz/sparkup', {'rtp': 'vim/'}
" Install L9 and avoid a Naming conflict if you've already installed a
" different version somewhere else.
" Plugin 'ascenator/L9', {'name': 'newL9'}

" All of your Plugins must be added before the following line
call vundle#end()            " required
filetype plugin indent on    " required
" To ignore plugin indent changes, instead use:
"filetype plugin on
set runtimepath^=~/.vim/bundle/ctrlp.vim
set encoding=utf-8
" set spelllang=en
" set spell
set fencs=utf-8,ucs-bom,shift-jis,gb18030,gbk,gb2312,cp936
set fileencodings=utf-8,ucs-bom,chinese

set wildmenu
set wildmode=longest:list,full

set langmenu=zh_CN.UTF-8
set backspace=indent,eol,start
syntax enable
syntax on
set background=dark
" set background=light
colorscheme seoul256
" colorscheme space-vim-dark
" colorscheme  monokai-phoenix
" colorscheme eclipse
" colorscheme wargrey

" colorscheme solarized
" colorscheme gotham
" colorscheme desert
" colorscheme google
" colorscheme watermark
" colorscheme seoul256
highlight LineNr ctermfg=blue
highlight LineNr ctermfg=darkred
" colorscheme radicalgoodspeed
" colorscheme monokain
let g:indentLine_char = "¦"
let g:indentLine_enabled = 0
let g:autopep8_disable_show_diff=1
let g:syntastic_c_no_include_search = 0
let g:syntastic_always_populate_loc_list = 1
let g:syntastic_auto_loc_list = 1
let g:syntastic_check_on_open = 1
let g:syntastic_check_on_wq = 1
let g:syntastic_c_remove_include_errors = 0
let g:syntastic_c_checkers=['gcc']
let g:syntastic_quiet_messages = { "regex": [  'No such file.* ' ] }
let g:syntastic_c_config_file = '.my_in_file_for_syn'
let g:indent_guides_enable_on_vim_startup = 1
let g:tagbar_ctags_bin = 'ctags'
let g:tagbar_width = 50
set statusline+=%#warningmsg#
set statusline+=%{SyntasticStatuslineFlag()}
set statusline+=%*
let g:airline_theme='violet'

" Add spaces after comment delimiters by default
let g:NERDSpaceDelims = 1
" " " Use compact syntax for prettified multi-line comments
let g:NERDCompactSexyComs = 1
"  Align line-wise comment delimiters flush left instead of following code indentation
let g:NERDDefaultAlign = 'left'
" " Set a language to use its alternate delimiters by default
let g:NERDAltDelims_java = 1
" " " Add your own custom formats or override the defaults
let g:NERDCustomDelimiters = { 'c': { 'left': '/**','right': '*/'   },
                             \ 'h': { 'left': '/**','right': '*/'   } }
"Allow commenting and inverting empty lines (useful when commenting a region)
let g:NERDCommentEmptyLines = 1
" " Enable trimming of trailing whitespace when uncommenting
let g:NERDTrimTrailingWhitespace = 1
" Enable NERDCommenterToggle to check all selected lines is commented or not
let g:NERDToggleCheckAllLines = 1

let g:ctrlp_map = '<c-l>'

set mouse-=a
set selection=exclusive
set selectmode=mouse,key

set showmatch
set number
set cursorline
set nocompatible

set tabstop=4
set scrolloff=8
set expandtab
set softtabstop=4
set shiftwidth=4
set autoindent
set cindent
set splitright
set hlsearch
set incsearch
set ruler
set rulerformat=%55(%{strftime('%a\ %b\ %e\ %I:%M\ %p')}\ %5l,%-6(%c%V%)\ %P%)
highlight ColorColumn ctermbg=magenta
call matchadd('ColorColumn', '\%81v', 100)

function HeaderPython()
    call setline(1, "#!/usr/bin/env python")
    call append(1, "# -*- coding: utf-8 -*-")
    normal G
    normal o
endf
function HeaderSh()
    call setline(1, "#!/usr/bin/env bash")
    normal G
    normal o
endf
autocmd bufnewfile *.py call HeaderPython()
autocmd bufnewfile *.sh call HeaderSh()
autocmd FileType c,cpp,python,ruby,java autocmd BufWritePre <buffer> :%s/\s\+$//e
" autocmd VimEnter * nested :call tagbar#autoopen(1)

if has("autocmd")
  au BufReadPost * if line("'\"") > 1 && line("'\"") <= line("$") | exe "normal! g'\"" | endif
endif

" disable arrow-keys
noremap <Up> gk
noremap <Down> gj

" disable ctrl-s
" noremap <silent> <C-S>          :update<CR>
" vnoremap <silent> <C-S>         <C-C>:update<CR>
" inoremap <silent> <C-S>         <C-O>:update<CR>
nmap <c-p> :TagbarToggle<CR>
nmap <F5>  :SyntasticCheck<CR>
nmap <F4>  zf%
nmap <F3>  :shell<CR>
nmap <c-s> :w<CR>
nmap <F1>  :n<CR>
nmap <F2>  :prev<CR>
inoremap <c-s> <Esc>:w<CR>
inoremap jj <Esc>^``
nnoremap gev :e $MYVIMRC<CR>
nnoremap gsv :so $MYVIMRC<CR>
" set relativenumber number
au FocusLost * :set norelativenumber number
au FocusGained * :set relativenumber
autocmd InsertEnter * :set norelativenumber number
autocmd InsertLeave * :set relativenumber
function! NumberToggle()
  if(&relativenumber == 1)
    set norelativenumber number
  else
    set relativenumber
  endif
endfunc

function! PasteToggle()
  if(&paste == 1)
    set nopaste
  else
    set paste
  endif
endfunc

set t_ti= t_te=

nnoremap <C-n> :call NumberToggle()<cr>
nnoremap <C-x> :qall!<CR>
" nnoremap <F6>  :set paste<CR>o
nnoremap <F7>  :only<CR>

nnoremap <F6>  :call PasteToggle()<cr>o
nnoremap <F9>  zf%
nnoremap <F10> zd

nnoremap <C-o> <C-o>zz
nnoremap <C-i> <C-i>zz
nnoremap <C-]> <C-]>zz
nnoremap p ]p
nnoremap gr gd[{V%::s/<C-R>///gc<left><left><left>}]
nmap pw :inoremap <lt>Space> <lt>Space><lt>Esc>:iunmap <lt>lt>Space><lt>CR><CR> cw

nmap p$ :inoremap <lt>CR> <lt>CR><lt>Esc>:iunmap <lt>lt>CR><lt>CR><CR> c$
nnoremap S diw"0P
map <C-q> :NERDTreeToggle<CR>

