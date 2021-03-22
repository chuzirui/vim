alias t 'tail -f /var/log/sip.log'
alias mess  'tail -f /var/log/messages'
alias st "cli -c 'show interfaces terse'"
alias 5tuple "srx-cprod.sh -s spu -c 'set usp algs sip common_distribute disable'"
alias 6tuple "srx-cprod.sh -s spu -c 'set usp algs sip common_distribute enable'"
alias jsftrace  "srx-cprod.sh -s spu -c 'set jsf trace per-plugin disable'"
alias ss "cli -c 'show security flow session'"
alias sg "cli -c 'show security flow gate'"
alias up "cli -c "request system software add /tmp/`ls /tmp | grep junos` no-copy no-validate unlink reboot""
alias cl "cli -c 'clear log sip.log'"
alias showcore "cli -c 'show system core-dumps '"
alias showcall "srx-cprod.sh -s spu -c 'show usp alg sip call detail'"
alias conf "cli -c 'show config | display set'"

alias cpcore 'scp *.gz root@10.208.135.82:/root'
alias cplog 'scp /var/log/sip.log root@10.208.135.82:/root'
alias showjmpi "srx-cprod.sh -s spu -c 'show usp jsf counters mjmpi'"

alias sipc "srx-cprod.sh -s spu -c 'show usp alg sip counter'"
alias denyall " cli -c 'conf; set security policies default-policy deny-all; commit'"
alias showpst "cli -c 'show security nat source persistent-nat-table all'"




