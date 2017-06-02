#!/bin/bash

read -e -p 'Enter Your NSX IP:'  IP

read -e -p 'Enter Your NSX account:' -i 'admin' USER
read -e -p 'Enter Your NSX pwd:' -i 'Admin!23Admin' PWD
read -e -p 'Enter Your cluster name:'  CLUSTER
read -e -p 'Enter Your overlay interface:'  -i 'eth1' ETH

cat <<EOF > /tmp/ncp.ini
[DEFAULT]
[coe]
cluster = $CLUSTER
[k8s]
apiserver_host_ip = 127.0.0.1
apiserver_host_port = 8080
use_https = False
ingress_mode = nat
[nsx_v3]
nsx_api_user = $USER
nsx_api_password = $PWD
nsx_api_managers = $IP:443
insecure = True
subnet_prefix = 24
external_ip_pool_id = acfe5a81-29eb-4b4a-877b-cae2a6794027
default_external_ip = 10.114.209.193
EOF

