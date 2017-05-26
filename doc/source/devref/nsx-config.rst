===================================================
Initializing NSX resources for a Kubernetes cluster
===================================================

This document describes NSX side configuration for a new k8s cluster, and
VNIC/VIF configuration for a new k8s Node VM.

NSX Management Plane preparation for Kubernetes Cluster
-------------------------------------------------------
In Dropkick, NSX entity UUID have been removed from ncp.ini.
NSX resources which will be used by Kubernetes clusters will have tags applied.

The migration from ncp.ini is almost complete. Only the IP pool for Ingress
Controllers in NAT mode still needs to be specified in nsx.ini. Its removal is
however still planned for Dropkick.


Resource Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~

1. Overlay Transport Zone

The overlay Transport Zone for a cluster is identified by the tag
``{'ncp/cluster': '<cluster_name>'}``. Go to NSX Manager and find the Overlay Transport Zone under
'Fabric' -> 'Transport Zones'. Find the overlay transport zone that shall be
used for container networking, or create a new transport zone and tag it with
the name of the cluster being configured.
Specifically ``<cluster_name>`` must match the value of the ``cluster`` option in the
ncp.ini ``[coe]`` section. Please note that we can add more than one tags to the
Overlay Transport Zone to make it shared.

2. T0 Logical Router

The T0 Logical Router for a cluster is identified by the tag
``{'ncp/cluster': '<cluster_name>'}``.
Go to NSX Manager and find the T0 LR under 'Routing' -> 'ROUTERS'.
You can either create a new T0 LR for the k8s cluster, or use an existing one.
Once the logical router has been identified, tag it as specified.

Specifically ``<cluster_name>`` must match the value of the ``cluster`` option in the
ncp.ini ``[coe]`` section. Please note that we can add more than one tags to the T0
Logical Router to make it shared.

3. IP Blocks for Kubernetes Pods

One or more IP Blocks should be created on NSX Manager for Pod IP allocation,
which is under 'DDI' -> 'IPAM'. CIDR in the form of <ip>/<prefix> (e.g. 192.168.0.0/16)
should be specified when creating an IP Block. The ``ncp/cluster`` tag should be set to
indicate these IP Blocks are used by the k8s cluster. The value of tag should match
the cluster's name in ``[coe]`` section of ncp.ini

By default, projects share IP Blocks above, unless explicitly specifying dedicated
IP Blocks to no-NAT projects by adding the tag ``{'ncp/no_snat': '<cluster_name>'}``
to IP Blocks, in addition to the ``ncp/cluster`` tag. Then no-NAT projects will use
the specific IP Blocks ONLY.

By default, subnet prefix 24 will be used for all subnets allocated from the IP
Blocks for the Pod LS's. If you like to use a different subnet size, update the
``subnet_prefix`` option in the ncp.ini ``[nsx_v3]`` section.

4. IP Block or IP Pool for SNAT

These resources will be used for allocating IP addresses which will be used for
translating Pod IPs via SNAT rules, and for exposing ingress controllers via
SNAT/DNAT rules - just like Openstack floating IPs. In this guide, these IP
addresses are also referred to  as *external IPs*.

Users can either configure a *global* external IP block or a cluster specific
external IP pool.

For setting up an external IP block go to NSX Manager and create an IP Block
under 'DDI' -> 'IPAM'. The CIDR value inputted should contain a network address,
as opposed to a host address (the latter may cause a downstream error from NSX).
For example, input 4.3.0.0/16 instead of 4.3.2.1/16. Then tag this IP block as
follows::

  {'ncp/external': 'true'}

This will indicate that the IP Block is meant for external IP allocation.
If multiple Kubernetes cluster consume the NSX manager instance, they will all
use the same external IP pool. Then each NCP instance will create a pool from
this block specific for the Kubernetes cluster it manages.

By default, the same subnet prefix for pod subnets will be use.
If you like to use a different subnet size for external subnets, set the
``external_subnet_prefix`` option in the ncp.ini ``[nsx_v3]`` section.

Instead, in order to use a cluster-specific IP pool for allocating external IPs,
go to NSX Manager and create IP Pools under 'Inventory' -> 'Groups' -> 'IP POOLs'.
Similarly as for IP blocks, the selected IP Pool should be tagged with
``'ncp/cluster'`` and ``'ncp/external'``.

**NOTE**: *NCP currently does not support managing multiple external IP pools.
The system will fail when an external IP pool or block becomes exhausted. This
is currently being treated as a defect and will be fixed for Dropkick release*

5. [Optional]: DFW marker section for Admin Rules

In order to allow admin to create firewall rules and not have them interfere
with NCP created DFW sections based on network policies, create an empty
DFW section in NSX manager under 'Firewall' -> 'General'. This firewall
section should be tagged as follows::

  ``{'ncp/fw_sect_marker': 'true'}``

After this configuration, all DFW sections created by NCP for network policies
and namespace isolation, will be created above this marker DFW section, while
admin configured firewall rules must be placed below this marker DFW section.
In case this marker section is not created, all isolation rules will be
created at the bottom. NCP does not support multiple marker DFW sections per
cluster and shall error out on such misconfigurations.

Tier-0 router configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. On NSX manager Web UI, go to "Routing" -> "Routers" -> "Add" -> "Tier-0 router".
2. Specify a name and optionally enter a description
3. Make sure an edge cluster is associated with the router
4. Leave HA mode as Active-Active unless you plan to configure NAT rules on the
   Tier-0 router, in which case select Active-Standby
5. Click the *ADD* button, and then select the router from the list.
6. Enable Route redistribution. ("Routing" -> "Route redistribution")
7. Create a public logical switch on a VLAN transport zone. Configure it on the VLAN
   you are planning to use for external traffic. In most deployments VLAN 0 will be
   good enough.
8. Add the VLAN transport zone to the edge transport node(s).
9. Add a host switch for the VLAN transport zone to the edge transport node(s).
   Make sure you noted the name of the host switch for the VLAN transport zone, and the
   interface on the edge node you plan to use for the host switch.
10. Create an uplink port on the Tier-0 router. To this aim select the router and then
    go to "Configuration" -> "Router Port", and select "Add". Then add a port of type
    "Uplink", attached to the logical switch created at step #7. Give the newly created
    port an IP address in your external network, and don't forget to specify the subnet
    prefix as well.

Logical networking for Kubernetes nodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This section provides basic information for configuring logical NSX networking for
Kubernetes nodes (master & minions). In the following we assume that every node has
2 network interfaces, the first one being a management interface which might or might
not be on the NSX fabric; the second interface is instead supposed to be on the NSX
fabric, and connected to a logical switch which we will refer as *node logical switch*

1. Create the node logical switch (e.g.: 'node-ls')
2. Create a Tier-1 logical router for nodes (e.g.: 'node-lr'). Connect this router to
   the cluster's Tier-0 router.
3. Enable route advertisement for the router. Advertisement should be enabled at least
   for *NSX Connected*, and *Nat* routes.
4. Connect the node logical router to the node logical switch. Make sure the IP address
   chosen for the router logical port does not conflict with node IP addresses.
5. For each node VM, ensure the vNIC which was designated for container networking is
   attached to the logical switch *node-ls*

The VIF ID of the VNIC used for container traffic in each Node must be known to NCP.
The corresponding Logical Switch port needs to be tagged in the following way::

  {'ncp/node_name':  '<node_name>'}
  {'ncp/cluster': '<cluster_name>'}

You should add the tags to the Node's VNIC LSP and use the right 'node_name'
and 'cluster_name' values.

In order to identify the right LSP for a given Node VM, it possible to leverage the NSX
API. The NSX API can indeed be used for retrieving data about virtual machines and VIF.
To retrieve VM data::

  curl -ku '<user>:<pw>' https://<nsx_mgr_endpoint>/api/v1/fabric/virtual-machines

In the response look for the Node VM and retrieve the value for the ``external_id``
attribute. Alternatively, using the search API::

 curl -ku '<user>:<pw>' https://<nsx_mgr_endpoint>/api/v1/search -G --data-urlencode \
 "query=(resource_type:VirtualMachine AND display_name:<node_vm_name>)"

Once the external ID has been retrieved, it can be used to retrieve VIFs for the
VM. Note: VIFs won't be populated in NSX API unless the VM was started.
The search API can again be used to this purpose::

 curl -ku '<user>:<pw>' https://<nsx_mgr_endpoint>/api/v1/search -G --data-urlencode \
 "query=(resource_type:VirtualNetworkInterface AND external_id:<node_vm_ext_id> AND \
 _exists_:lport_attachment_id)"

The ``lport_attachment_id`` attribute is the VIF ID for the node VM. It is then
straightforward to find the logical port for this VIF and add the required tags.

NSX connectivity configuration
-------------------------------
1. ``nsx_api_managers`` is a comma separated list of endpoints where NSX
manager instances are listening. While this parameters accept URL specifications
compliant with RFC3896 (scheme, host, port, etc.), in general it is sufficient
to specify just the IP address of the NSX manager to open an https connection
on port 443 (which is the default NSX setting).
Example::

  nsx_api_managers = 192.168.1.180, 192.168.1.181

2. ``nsx_api_username`` and ``nsx_api_password`` are respectively username and
password and should be used when connecting to NSX using basic authentication.
This is not the recommended approach as it will imply that NSX credentials
are likely to not be stored securely.
Please also note that these options are ignored if NCP is configured for
authentication using client certificates.

3. ``fetch_cert_from_filesystem`` must be set to ``True`` if the client
certificate and private key are loaded in the filesystem of NCP.
In kubernetes, certificate and private key are loaded with the use of TLS
secrets and they are mounted in NCP's filesystem in the following locations::

  NSX PEM encoded certificate: /etc/nsx-ujo/nsx-cert/tls.cert
  NSX PEM encoded private key: /etc/nsx-ujo/nsx-cert/tls.key
Refer to section
``Mounting PEM encoded certificate and private key into NCP Pod`` for
detailed steps on how to create and mount TLS secrets.

4. ``nsx_api_cert_file`` is the full path to a client certificate file in PEM
format to be used for authentication with NSX. Authentication via client
certificates is prioritized over basic authentication. Therefore if this option
is specified ``nsx_api_username`` and ``nsx_api_password`` are ignored.
The contents of the certificate file will look like the following::
-----BEGIN PRIVATE KEY-----
<private_key_data_base64_encoded>
-----END PRIVATE KEY-----
-----BEGIN CERTIFICATE-----
<certificate_data_base64_encoded>
-----END CERTIFICATE-----

5. ``ca_file`` specifies a CA bundle file to us for verifying the server
certificate. This is for verifying the authenticity of the https endpoints,
and is independent from the client certificate settings.

6. The ``insecure`` option is set to ``False`` by default. Should it be set to
``True``, the genuinity of https connections will not be verified. The
``ca_file`` parameter, if supplied, will be ignored.

Mounting certificate file or ca_file into NCP Pod
-------------------------------------------------
Assuming you have a certificate file or a ca_file in the Node file system, you
could update the NCP Pod spec to mount the file into the NCP Pod.
Example::

  spec:
    ...
    containers:
    - name: nsx-ncp
      ...
      volumeMounts:
      ...
      - name: nsx-cert
        mountPath: /etc/nsx-ujo/nsx_cert
    volumes:
    ...
    - name: nsx-cert
      hostPath:
        path: <host-filesystem-path>

Mounting PEM encoded certificate and private key into NCP Pod
-------------------------------------------------------------
Assuming you have a PEM encoded certificate and a private key, you could
update the NCP Pod spec to mount the TLS secrets into the NCP Pod.
Example::

 1. Create TLS secret for certificate and private key
    kubectl create secret tls SECRET_NAME --cert=/path/to/tls.cert
        --key=/path/to/tls.key
    This creates a secret with data items tls.cert and tls.key
 2. Update NCP pod spec yaml to mount secret as files in NCP Pod
    spec:
      ...
      containers:
      - name: nsx-ncp
        ...
        volumeMounts:
      ...
      - name: nsx-cert
        mountPath: /etc/nsx-ujo/nsx-cert
        readOnly: true
    volumes:
    ...
    - name: nsx-cert
      secret:
        secretName: SECRET_NAME

Generating a self-signed client certificate for test purposes
-------------------------------------------------------------
For testing purposes it might be useful to generate a self-signed certificate,
and import it into NSX.

While this can be done manually, it is a rather time consuming process.
For this aim the convenience script ``create_nsx_cert.py`` is provided in the
``nsx_ujo/sample`` directory.

In its simplest form the script can be used in the following way::
  create_nsx_k8s_secret.py --config-file /etc/nsx-ujo/ncp.ini

This will create a self-signed certificate, store it into a file called
``nsx.secret`` and import the certificate in NSX.
The script also allows for specifying a custom name for the certificate file
with the ``--filename`` option.

Please note that to this aim the script must connect to NSX using basic
authentication only. Therefore ``nsx_api_username`` and ``nsx_api_password``
must specify the credentials of a user with administrative rights.

If a certificate already exist for the NCP principal identity (``com.vmware.nsx.ncp``)
the script will refuse to register a new certificate. This can be overridden specifying
the ``--force`` parameter on the command line.

The other command line options accepted by ``create_nsx_k8s_secret.py`` are::
 - ``--sig-alg``: Signature digest type. Defaults to ``sha256``
 - ``--key-size``: Private key size. Default to ``2048``
 - ``--valid-for-days``: Certificate validity. Default to ``365 days``
 - ``--country``, ``--state``, ``--org``, ``--hostname``: Override default
   settings for the certificate being created (normally one won't need to
   override any of these for devtest purposes)




(TBD: scripts to automate the NSX configurations.)
