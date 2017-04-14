# MANO from zero ground

## 0. Please have Cent-OS 7.2 installed. 
Minimal Installation is OK

## 1. Install openstack


#### 1.1 preinstall of openstack (to avoid sudo, assuming you are THE root )
wget -O /etc/yum.repos.d/CentOS-Base.repo http://mirrors.aliyun.com/repo/Centos-7.repo
yum -y update
yum install -y ntp openssh-server wget
to fix erlang

sed -i 's/enabled=0/enabled=1/' /etc/yum.repos.d/CentOS-OpenStack-*.repo
yum deplist erlang-wx | awk '/provider:/ {print $2}'| sort -u | xargs yum -y install
yum install erlang --skip-broken -y

#### 1.2 install openstack via packstack (with heat )
yum install -y centos-release-openstack-liberty
yum update -y
yum install -y openstack-packstack

please change the ethernet card's name and the ovs bridge according to your system

packstack --allinone --provision-demo=n --os-neutron-ovs-bridge-mappings=extnet:br-ex,mgmt:br-int --os-neutron-ovs-bridge-interfaces=br-ex:em3,br-int:em1 --os-neutron-ml2-type-drivers=vxlan,flat,vlan --os-neutron-ml2-flat-networks=extnet,mgmt  --os-neutron-lbaas-install=y --os-heat-install=y --os-cinder-install=n

packstack --install-hosts=172.24.103.207,172.24.103.206 --provision-demo=n --os-neutron-ovs-bridge-mappings=extnet:br-ex --os-neutron-ovs-bridge-interfaces=br-ex:em4 --os-neutron-ml2-type-drivers=vxlan,flat,vlan --os-neutron-ml2-flat-networks=*  --os-neutron-lbaas-install=y --os-heat-install=y --os-cinder-install=n

systemctl disable NetworkManager.service
systemctl stop NetworkManager.service
chkconfig network
sudo systemctl restart network
neutron net-create external_network --provider:network_type flat --provider:physical_network extnet  --router:external --shared 

neutron subnet-create --name ex_net --enable_dhcp=False --allocation-pool=start=192.168.23.130,end=192.168.23.170   --gateway=192.168.23.1 external_network 192.168.23.0/24 
neutron router-create router1
neutron router-gateway-set router1 external_network
neutron net-create private_network 
neutron subnet-create --name private_subnet private_network 192.168.100.0/24 --dns-nameserver 119.29.29.29
neutron router-interface-add router1 private_subnet  


#### 1.3.install tacker
login to openstack controller

source ~/keystone_admin

copy and unzip the tack.tar file

tar xf tack.tar 
run the installation script

cd tacker-deployment/
./tacker-deployment.sh
#### 1.4 create tacker vnfd for vyatta  
upload 5600 vrouter image to openstack 

glance image-create --name 'vyatta' --container-format bare --disk-format qcow2 --file vyatta_vrouter.qcow2
nova flavor-create vrouter auto 2048 8 2
openstack user set --password nottacker tacker


upload vnfd from tosca-nfv/tacker/vnfd directory vrouter-vnfd-cloudify.yaml

cp /root/cloudify/tosca-nfv/tacker/vnfd/vrouter-vnfd-cloudify.yaml /root/

need to make sure you’ve got a valid mgmt interface, needs to be reachable by openstack controller for ssh config

tacker vnfd-create --vnfd-file vrouter-vnfd-cloudify.yaml --name vrouter
#### 1.5 upload centos/ubuntu images to openstack
wget https://cloud-images.ubuntu.com/trusty/20160906/trusty-server-cloudimg-amd64-disk1.img
wget http://cloud.centos.org/centos/7/images/CentOS-7-x86_64-GenericCloud-20140929_01.qcow2
glance image-create --name "centos" --disk-format qcow2 --container-format bare --file CentOS-7-x86_64-GenericCloud-20140929_01.qcow2
glance image-create --name "ubuntu" --disk-format qcow2 --container-format bare --file trusty-server-cloudimg-amd64-disk1.img
#### 1.6 cinder volume message
modify /etc/cinder/cinder.ini accoring to contoller's IP

[keystone_authtoken]
auth_uri=http://<controller-ip>:5000/v2.0
identity_uri = https://<controller-ip>>:35357/

Boot test host

nova boot --flavor host --image trusty --security-groups default --key-name manager-kp --nic net-id=e36fbedb-0191-460c-843d-459cb35e7ef1 --nic net-id=8287decf-c04b-49e4-960a-4ac072393efe south
nova boot --flavor host --image trusty --security-groups default --key-name manager-kp --nic net-id=ceb1002c-120f-4111-9746-a30155d4f100 --nic net-id=8287decf-c04b-49e4-960a-4ac072393efe north


## 2. Install Cloudify
#### 2.1 install cloudify client

Install cli using get-cloudily.py script

mkdir cloudify && cd cloudify
wget http://gigaspaces-repository-eu.s3.amazonaws.com/org/cloudify3/get-cloudify.py
sudo python get-cloudify.py -e venv --install-virtualenv
source venv/bin/activate
Or install from rpm

wget http://repository.cloudifysource.org/org/cloudify3/LatestRelease/cloudify-3.4.0~2.ga-402.el6.x86_64.rpm
rpm -i cloudify-3.4.0~2.ga-402.el6.x86_64.rpm


#### 2.2 install cloudify manager
Create a cloudify flavour for CM minimum (2 vcpus, 5 GB RAM, 20GB HDD)

    nova flavor-create cloudify auto 5120 20 2

    Clone the cloudify blueprints:

    git clone https://github.com/cloudify-cosmo/cloudify-manager-blueprints
    cd cloudify-manager-blueprints
    git checkout 3.4

    you can try this

    sed -i "s/keystone_username: ''/keystone_username: '$OS_USERNAME'/g" openstack-manager-blueprint-inputs.yaml
    sed -i "s/keystone_password: ''/keystone_password: '$OS_PASSWORD'/g" openstack-manager-blueprint-inputs.yaml
    sed -i "s/keystone_tenant_name: ''/keystone_tenant_name: '$OS_TENANT_NAME'/g" openstack-manager-blueprint-inputs.yaml
    sed -i "s,keystone_url: '',keystone_url: '$OS_AUTH_URL',g" openstack-manager-blueprint-inputs.yaml

    imageid=`glance image-list | grep centos | cut -d '|'  -f 2|tr -d ' '`
    flavid=`nova flavor-list| grep cloudify| cut -d '|' -f 2|tr -d ' '`

    sed -i "s,image_id: '',image_id: '$imageid',g" openstack-manager-blueprint-inputs.yaml
    sed -i "s,flavor_id: '',flavor_id: '$flavid',g" openstack-manager-blueprint-inputs.yaml

    exnet=`neutron net-external-list | grep / | cut -f 3 -d '|'|tr -d ' '`
    sed -i "s,external_network_name: '',external_network_name: '$exnet',g" openstack-manager-blueprint-inputs.yaml

    Or Modify the openstack manager blueprints:

    vi openstack-manager-blueprint-inputs.yaml
    important properties to set are:
    Credentials and identification in order to connect to openstack

    keystone_username: 'admin'
    keystone_password: 'your-admin-pwd-here'
    keystone_tenant_name: 'admin'
    keystone_url: 'http://<openstack-controller-ip>:5000/v2.0'
    region: ''

    set these to false to create new key pairs for certs

    use_existing_manager_keypair: false
    use_existing_agent_keypair: false

    CentOS image id from the first step & flavour id to use

    image_id: 'centos-image-id'
    flavor_id: 'cloudify-fla-id'

Name of the external openstack network (needed to access the internet to grab all components, see neutron net-list)

    external_network_name: 'external_network '

SSH user used to connect to the manager (typical centos)        

    ssh_user: centos

    DNS entries to add to subnet. Defaults to none. 
    IMPORTANT! in brocade network you may fail with 8.8.8.8, 114.114.114.114, etc

    management_subnet_dns_nameservers: [172.24.11.12]

    alternative to this setting is to add dnsmasq_dns_server in the /etc/neutron/dhcp_agent.ini file

    management_subnet_dns_nameservers: [10.0.0.1]
Optional prefix for each openstack component (used to prefix all the node names)

    resources_prefix: 'cloudify'
    Boot strap the cloudify manager:

    cfy init
    cfy bootstrap --install-plugins -p openstack-manager-blueprint.yaml -i openstack-manager-blueprint-inputs.yaml

    Once complete you should get the following message:
    bootstrapping complete
    management server is up at <YOUR cfy-MANAGER-IP ADDRESS>

    You can verify the install using the following command:

    cfy status

    If bootstrap fails, the bootstrap process will automatically do the cleanup, which will make it difficult to debug. you can stop the bootstrap then ssh into the cloudify manager with manager-kp. like this.  

    ssh -i ~/.ssh/cloudify-manager-kp.pem centos@<cloudify-manager-ip>

    After doing so, you must manually cleanup.
    -  remove all network, router, key pairs, security groups, floating ips
    -  issue nova keypair-delete to make sure key pairs are gone
    -   rm ~/.ssh/cloud…. key pairs

##3. dancing in  cloudify 
    Install some pre-reqs onto the cloudify manager VM before loading plugins and blueprints

    ssh -i ~/.ssh/cloudify-manager-kp.pem centos@<cloudify-manager-ip>
    sudo yum -y install epel-release python-pip virtualenv
    sudo yum -y install autoconf gcc make python-devel 
    install the tosca templates , find the important .yaml files

    cd ~/cloudify
    git clone ssh://git@swnstash.brocade.com:7999/skyn/tosca-nfv.git
    cd tosca-nfv/tacker  # this is the main directory where all the templates are stored

    build and load the brocade plugin

    cd ~/cloudify
    git clone ssh://git@swnstash.brocade.com:7999/skyn/python-flowmanager-client.git
    cd python-flowmanager-client
    python setup.py sdist
    $ cd ~/cloudify
    git clone ssh://git@swnstash.brocade.com:7999/skyn/cloudify-brocade-plugin.git
    cd cloudify-brocade-plugin
    vi dev-requirements # modify the last line to point to the python-flowmanager-client distribution file
    make wagon
    cfy plugins upload -p cloudify_brocade_plugin-2.0-py27-none-linux_x86_64-centos-Core.wgn
    build and load the tacker plugin

    cd ~/cloudify
    git clone https://github.com/openstack/python-tackerclient.git
    cd python-tackerclient
    python setup.py sdist
    cd ~/cloudify
    git clone ssh://git@swnstash.brocade.com:7999/skyn/cloudify-tacker-plugin.git
    cd cloudify-tacker-plugin
    vi dev-requirements # modify the last line to point to the python-tackerclient distribution file
    make wagon
    cfy plugins upload -p cloudify_tacker_plugin-2.0-py27-none-linux_x86_64-centos-Core.wgn
    Some cloudify commands

    cd ~/cloudify/tosca-nfv/tacker
    cfy status            # Get the status of all the components on the Cloudify Manager
    cfy use -t <ip-addr>    # Change to use a different Cloudify Manager

    cfy blueprints commands

    cfy blueprints list   # List the blue prints on the Cloudify Manager
    cfy blueprints upload -b p2p -p p2p.yaml  # Create a new blueprint with the p2p.yaml blueprint
    cfy blueprints upload -b p2p-vnf-multi -p p2p-vnf-mult.yaml  # Create a new blueprint with the p2p.yaml blueprint
    cfy blueprints upload -b p2p-vnf -p p2p-vnf.yaml  # Create a new blueprint with the p2p.yaml blueprint

    cfy blueprint delete -b p2p   # Delete a blueprint


    cfy deployment commands

    cfy deployments list  # List all the customer deployments
# Create a new customer deployment
    cfy deployments create -d p2p-vnf-cust1 -b p2p-vnf -i p2p-vnf-cust1-inputs.yaml 
    cfy deployments delete -d p2p # Delete  customer deployment

    about p2p-vnf-cust1-inputs.yaml

    vyatta_image_id=`nova image-list | grep vrouter | cut -f 2 -d '|' | tr -d " "`
    sed -i "s/vm_image: ".*"/vm_image: \"$vyatta_image_id\"/g" p2p-vnf-cust1-inputs.yaml

    need to pay attention to these *-input.yaml files

    cd /root/cloudify/tosca-nfv/tacker
    cat p2p-input.yaml

    >cp01_switch_id: "openflow:101"
    cp01_switch_port: 3
    cp01_network_type: "vlan"
    cp01_vlan_id: 3101
    cp02_switch_id: "openflow:104"
    cp02_switch_port: 3
    cp02_network_type: "vlan"
    cp02_vlan_id: 3151
    vl1_waypoints: []
    sdn_config: 
ip: "sdn-controller-ip"                   
username: "admin"                       
password: "admin"                      

cat p2p-vnf-cust1-inputs.yaml

tacker part
>vnf1_vnfd_id: "c3df5004-21ab-4fbb-9caa-5681115ea387"
vnf1_vdu_params:
vm_image: "vyatta_vrouter"
flavor: "vrouter"
service: "firewall"
zone: "nova"
vnf1_vdu_config:
vdus:
vdu1:
config:
- "run show interfaces"
- "set system login user vyatta level superuser"
- "set interfaces dataplane dp0s4 address 10.31.102.1/24"
- "set interfaces dataplane dp0s5 address 10.31.152.1/24"
vnf1_tacker_config:
username: "admin"
password: "04484e9c6126453a"
auth_url: "http://openstack-ip:5000/v2.0"
tenant_name: "admin"

sdn part

>cp01_sdn_network:
switch_id: "openflow:101"
switch_port: "3"
network_type: "vlan"
segmentation_id: "3102"
cp11_sdn_network:
network_type: "vlan"
segmentation_id: "2000"
switch_id: "openflow:101"
switch_port: "3"
cp11_vnf_network:
tenant_id: "bfe8f745753b4cf1b827ea2262cc7f8c"
provider:physical_network: "openflow1"
provider:network_type: "vlan"
provider:segmentation_id: "2000"
cp11_subnet_cidr: "10.31.102.0/24"
cp12_vnf_network:
tenant_id: "bfe8f745753b4cf1b827ea2262cc7f8c"
provider:physical_network: "openflow1"
provider:network_type: "vlan"
provider:segmentation_id: "2001"
cp12_sdn_network:
network_type: "vlan"
segmentation_id: "2001"
switch_id: "openflow:101"
switch_port: "3"
cp12_subnet_cidr: "10.31.152.0/24"
cp02_sdn_network:
switch_id: "openflow:104"
switch_port: "3"
network_type: "vlan"
segmentation_id: "3152"
vl1_waypoints: []
vl2_waypoints: []
sdn_config:
ip: "contoller-ip"
username: "admin"
password: "admin"

openstack part

>cp_openstack_config:
username: "admin"
password: "04484e9c6126453a"
tenant_name: "admin"

cfy executions commands

cfy executions list           # List all executions
cfy events list -e <exec-id> -l # Get the log messages for an execution





