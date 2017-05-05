# Installing Kubernetes with Kubeadm

This document will guide you through the steps required for setting up
a Kubernetes Cluster with the *kubeadm* tool.
Upstream documentation for *kubeadm* can be found at
https://kubernetes.io/docs/getting-started-guides/kubeadm/


## Setting up the cluster


**NOTE**: Currently Kubeadm does not support Master redundancy

The recommended OVF templates (`<https://buildweb.eng.vmware.com/ob/?product=k8snode>`_ or
`<http://pa-dbc1116.eng.vmware.com/shenj/ujo/ubuntu-16_04-k8s.ovf>`_) already come with most of the
required software, including docker, kubeadm, and kubectl. If using a different template, add the
Google package repo, update apt and install Docker, Kubelet, etc.
	
	  curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add -
	
	  cat <<EOF > /etc/apt/sources.list.d/kubernetes.list
	  deb http://apt.kubernetes.io/ kubernetes-xenial main
	  EOF
	
	  apt-get update
	
	  apt-get install -y docker.io
	  apt-get install -y kubelet kubeadm kubectl kubernetes-cni
	
This doc assumes you use kubeadm 1.6.1 or above.
Now you can run the Kubeadm command that will initialize your Kubernetes Master.

	kubeadm init --apiserver-advertise-address <node_ip> --skip-preflight-checks

The <node_ip> above should be the IP address of the interface
on the NSX network of the k8s master node.

If not specified, kubeadm will bind the API server to the IP address of the
interface used as a default gateway. If that is your management interface, this
might imply that pods won't be able to resolve Kubernetes' service cluster IP.
Note down the API token shown at the End of the Init Process.
It is needed to join the Nodes later.

When using kubeadm 1.6.1 or above, chances are that kubectl will need
to authenticate even on the master node, as the insecure endpoint has been
disabled by default. In this case execute the following commands, which are
also printed at the end of kubeadm execution::
	
	  sudo cp /etc/kubernetes/admin.conf $HOME/
	  sudo chown $(id -u):$(id -g) $HOME/admin.conf
	  export KUBECONFIG=$HOME/admin.conf

You can now join any number of machines by running the following on each node::

	  kubeadm join --token=<token_as_in_output> <master_ip>:6443

Please note that ``kubeadm init`` also configures the master as a cluster node.
Therefore ``kubeadm join`` must not be executed on the master node.
Most of the pods started in the ``kube-system`` namespace will be deployed in
``hostNetwork`` mode. For these pods, NCP does not need to run.

Other pods instead might be either in *Pending* or *ContainerCreating* status.
In the first category there are pod which the scheduler won't run on master.
See the *running pods on master* section below.
In the second category there are pod which need to be deployed on the NSX
network. For this pods the CNI plugin will keep failing until NCP and the
nsx-node-agent are not up and running.


## Running pods on master node


If you just have a single node setup and your master node is same as worker node.
Run the following on the node to allow Kubernetes scheduler to place pods on master.

	 kubectl taint nodes --all node-role.kubernetes.io/master:NoSchedule-

More info available at: 
https://kubernetes.io/docs/getting-started-guides/kubeadm/

Alternatively a Pod can be configured to always run on the Master with
``nodeName=<master-node-name>``


##Changing the address for the Kubernetes service


**NOTE**: according to the kubeadm version you are running manifest files could
either be in JSON or YAML format.

If ``--apiserver-advertise-address`` was not specified when doing kubeadm init,
it is possible to change the IP address the API server will bind to by editing
``/etc/kubernetes/manifests/kube-apiserver.yaml``,
and setting ``--advertise-address`` to the IP address of the node interface
to be used for container networking.

**After editing restart the kubelet service for the change to take affect**

## Using the Kubernetes insecure API endpoint


**NOTE**: according to the kubeadm version you are running manifest files could
either be in JSON or YAML format.

When not using authentication, the Kubernetes API server insecure endpoint
must be enabled. Please note that with recent version of kubeadm (>=1.6.1)
the insecure endpoint is disabled by default.
To do so there are two options:

1. Change the params for insecure endpoints in kube-api-server Pod spec ``/etc/kubernetes/manifests/kube-apiserver.yaml``

		sed -i 's/--insecure-port=0/--insecure-port=8080\n    - --insecure-bind-address=0.0.0.0/'  /etc/kubernetes/manifests/kube-apiserver.yaml

2. Configure NCP to always run on the master. If deployed as a pod, use
   ``hostNetwork=True`` and ``nodeName=<master-node-name>`` in the pod
   specification. Configure it to use 127.0.0.1:8080 as the K8s API Endpoint,
   by adding or updating the following parameters::
			
			--insecure-bind-address=127.0.0.1
			--insecure-bind-port=8080

**Now restart the kubelet service via 'systemctl restart kubelet' for the change to take affect**
Kubeadm should detect the change and deploy the API server again, but ends up
in a kind of circular dependency problem with Kubelet not starting the API
Server because it can't contact the API Server.

The ncp.ini configuration file should look like the following:
	
	
	  [DEFAULT]
	  [coe]
	  cluster = <cluster_name>
	  [k8s]
	  apiserver_host_ip = 127.0.0.1
	  apiserver_host_port = 8080
	  use_https = False
	  [nsx_v3]
	  nsx_api_user = <user>
	  nsx_api_password = <pw>
	  nsx_api_managers = <nsx_endpoint>

**NOTE**: Please review the ncp.ini.in example in this repo for more details on each of these settings.


## RBAC Configuration for NCP


When the RBAC admission controller is enabled, the service account used by NCP
must be given administrative access rights over the cluster, as it needs to
access resources in all namespaces, as well as access cluster entities such
as nodes.

To do, the cluster role "cluster-admin" should be attributed to the service
account running NCP. In this example we assume this is the default service
account in the default namespace::
	
	   kubectl create clusterrolebinding default:default:clusteradmin \
	   --clusterrole cluster-admin --serviceaccount default:default

## Work with the Kubernetes Cluster from another machine



Copy the kubeclient config from the Master to your machine

	  scp root@<master ip>:/etc/kubernetes/admin.conf .

Now copy this config to ~/.kube/config

**NOTE**: This will overwrite your current kube client config, save it to an 'old' file before

	  mv admin.conf ~/.kube/config
