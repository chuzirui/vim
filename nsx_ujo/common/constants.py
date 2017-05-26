#******************************************************************************
# Copyright (c) 2016-2017 VMware, Inc. All rights reserved.VMware Confidential.
#******************************************************************************

########################
# Kubernetes constants #
########################

# Resources
K8S_NAMESPACE = 'k8s_namespace'
K8S_POD = 'k8s_pod'
K8S_SERVICE = 'k8s_service'

# Events
ADDED = 'ADDED'
MODIFIED = 'MODIFIED'
DELETED = 'DELETED'

NAMESPACES = 'namespaces'
SERVICES = 'services'
PODS = 'pods'
RCS = 'replicationcontrollers'
NODES = 'nodes'
ENDPOINTS = 'endpoints'
INGRESSES = 'ingresses'
# Set ingress to RULES to avoid confusion with L7 ingress
RULES = 'ingress'
NETWORK_POLICIES = 'networkpolicies'
POD_SELECTOR = 'podSelector'
NS_SELECTOR = 'namespaceSelector'
SECRETS = 'secrets'
DEFAULT_PORT_NAME = 'ep_port'

K8S_API_VERSION = 'v1'
K8S_EXTAPI_VERSION = 'v1beta1'

K8S_ISOLATION_ANNOTATION = "net.beta.kubernetes.io/network-policy"

# k8s API server IP/port env variables passed to Pods
K8S_SERVICE_HOST_ENV = "KUBERNETES_SERVICE_HOST"
K8S_SERVICE_PORT_ENV = "KUBERNETES_SERVICE_PORT"

INGRESS_ANNOTATION = 'ncp-nsx/ingress-controller'
NOSNAT_ANNOTATION = 'ncp-nsx/no-snat'
CREATEDBY_ANNOTATION = 'kubernetes.io/created-by'

INGRESS_HOSTNETWORK = 'hostnetwork'
INGRESS_NAT = 'nat'

# Admin statuses
ADMIN_STATE_UP = "UP"
ADMIN_STATE_DOWN = "DOWN"

ADMIN_STATUSES = [ADMIN_STATE_UP, ADMIN_STATE_DOWN]

#################
# CNI constants #
#################

CNI_SOCKET = "/var/run/nsx-ujo/cni.sock"
NSX_CNI_VERSION_MAJOR = '1'
NSX_CNI_VERSION_MINOR = '0'
NSX_CNI_VERSION_MAINTENANCE = '0'

# Annotations
ANN_IP = 'ip'
ANN_GW = 'gateway_ip'
ANN_MAC = 'mac'
ANN_VLANID = 'vlan'
ANN_ATTACHMENT_ID = 'attachment_id'

########################
# Kube-proxy constants #
########################
MIN_KERNEL_VERSION_REQUIRED = {
    'Ubuntu': '4.6.0',
    'Red Hat Enterprise Linux Server': '3.10.0',
}
MIN_OVS_VERSION_REQUIRED = '2.5.9'

############################
# NSX_NODE_AGENT constants #
############################

AGENT_IFACE = 'agent0'
AGENT_NS = 'nsx-node-agent'
AGENT_VERSION_MAJOR = 1
AGENT_VERSION_MINOR = 0
AGENT_VERSION_MAINTENANCE = 0
AGENT_VERSION_PATCH = 0
AGENT_VERSION_SUFFIX = '0'
AGENT_VERSION_BUILD_NUMBER = 0
AGENT_VERSION_CHECK_PERIOD = 5
AGENT_KEEPALIVE_INTERVAL = 3

#################
# NCP constants #
#################

SCOPE = 'scope'
TAG = 'tag'
PROJECT = 'project'
EXT_IP = 'ext_ip'
POD = 'pod'
NETWORK_POLICY = 'network_policy'
KUBERNETES = 'kubernetes'
HOST_NETWORK_POD = 'host_network_pod'
ISOLATION_SECTION = 'isolation_section_id'
IS_ISOLATED = 'is_isolated'
EXTERNAL_POOL = 'ext_pool'
EXTERNAL_POOL_ID = 'ext_pool_id'
SNAT_IP = 'snat_ip'
HC_SECTION = 'hc_section'
OPENSHIFT = 'openshift'
VIF = 'vif'


#################
# CLI constants #
#################
NSX_ISSUE_FILE = '/etc/nsx_issue'

HEALTHY = 'Heathy'
UNHEALTHY = 'Unhealthy'

CLI_STATS_WINDOW = 3600  # stats processing window in seconds
CLI_LOG_WINDOW = 86400   # logs collection window in seconds

# Can define more error codes here as we evolve
CLI_ERR_CODE = {
    'SUCCESS': {'code': '0', 'desc': 'success'},
}

###########################
# IP Allocator Constants#
###########################
IP_BLOCKS = 'ip_blocks'
IP_BLOCKS_ROUTE = 'ip_blocks_route'
SUBNET = 'subnet'
SUBNET_ID = 'subnet_id'
IP_POOL_ID = 'ip_pool_id'
GATEWAY = 'gateway'
LR_INTERFACE = 'lr-intf'
IP_ALLOCATION_FREE = 'free'
IP_ALLOCATION_FULL = 'full'

#################
# OVS constants #
#################

OVS_BRIDGE = "br-int"
MTU = 1450
VETH_OUT_NAME_END = 15
VETH_IN_NAME_END = 13

########################
# NSX constants #
########################

# TODO(abhiraut): Clean up constants to use vmware-nsxlib constants
MAX_TAG_SCOPE_LEN = 20
MAX_TAG_VALUE_LEN = 40

NSGROUP_COMPLEX_EXP = 'NSGroupComplexExpression'

# Resource constants
LS = 'logical-switch'
LR = 'logical-router'
ATTACHMENT = 'attachment'
ATTACHMENT_TYPE = 'attachment_type'

# Resource type constants
FIREWALL_SECTION = 'Firewallsection'
IP_BLOCK = 'IpBlock'
IP_BLOCK_SUBNET = 'IpBlockSubnet'
IP_POOL = 'IpPool'
LOGICAL_PORT = 'LogicalPort'
LOGICAL_ROUTER = 'LogicalRouter'
LOGICAL_SWITCH = 'LogicalSwitch'
TRANSPORT_ZONE = 'TransportZone'
SPOOFGUARD_SWITCHING_PROFILE = 'SpoofGuardSwitchingProfile'

# Port attachment types
ATTACHMENT_VIF = "VIF"
ATTACHMENT_LR = "LOGICALROUTER"
ATTACHMENT_CIF = "CIF"
CIF_TYPE = "CHILD"
VIF_TYPE_PARENT = "PARENT"
CIF_ALLOCATE_ADDRESSES = "Both"

ATTACHMENT_TYPES = [ATTACHMENT_VIF, ATTACHMENT_LR]

PROTO_NAME_TCP = 'tcp'
PROTO_NAME_UDP = 'udp'

# NOTE(abhiraut): Although a map is not technically required at the moment,
#                 we may need this in future when more protocols are supported
#                 by k8s to map protocol names to NSX backend protocol names.
NSX_PROTOCOL_MAP = {PROTO_NAME_TCP: 'TCP',
                    PROTO_NAME_UDP: 'UDP'}

# Replication modes
MTEP = "MTEP"
SOURCE = "SOURCE"

REPLICATION_MODES = [MTEP, SOURCE]

# Router type
ROUTER_TYPE_TIER0 = "TIER0"
ROUTER_TYPE_TIER1 = "TIER1"

ROUTER_TYPES = [ROUTER_TYPE_TIER0, ROUTER_TYPE_TIER1]

LROUTERPORT_UPLINK = "LogicalRouterUplinkPort"
LROUTERPORT_DOWNLINK = "LogicalRouterDownLinkPort"
LROUTERPORT_LINKONTIER0 = "LogicalRouterLinkPortOnTIER0"
LROUTERPORT_LINKONTIER1 = "LogicalRouterLinkPortOnTIER1"

LROUTER_TYPES = [LROUTERPORT_UPLINK,
                 LROUTERPORT_DOWNLINK,
                 LROUTERPORT_LINKONTIER0,
                 LROUTERPORT_LINKONTIER1]

# This must be lower than the FIP priority used for ingress, but higher than
# the SNAT priority. SNAT and FIP priorities are defined in vmwware-nsxlib
NONAT_RULE_PRIORITY = 950
NONAT_ACTION = 'NO_NAT'

# L2 agent vif type
VIF_TYPE_DVS = 'dvs'

# NCP Certificate identity name
NCP_CERT_IDENTITY = "com.vmware.nsx.ncp"
# NSX Certificate file created by NCP
NSX_CERT_FILEPATH = '/tmp/nsx_cert.pem'
# NSX PEM encoded Certificate path
NSX_CERT_PEM_FILEPATH = '/etc/nsx-ujo/nsx-cert/tls.cert'
# NSX PEM encoded Private Key path
NSX_CERT_KEY_PEM_FILEPATH = '/etc/nsx-ujo/nsx-cert/tls.key'

NCP_INI_PATH = '/etc/nsx-ujo/ncp.ini'

# NSXv3 L2 Gateway constants
BRIDGE_ENDPOINT = "BRIDGEENDPOINT"

# tag scopes
TAG_CLUSTER = 'ncp/cluster'
TAG_COE = 'ncp/coe'
TAG_EXTERNAL_POOL = 'ncp/external'
TAG_EXTERNAL_POOL_ID = 'ncp/extpoolid'
TAG_FW_SECTION_TYPE = 'ncp/fw_sect_type'
TAG_FW_SECTION_ENABLED = 'ncp/fw_sect_enabled'
TAG_FW_SECTION_MARKER = 'ncp/fw_sect_marker'
TAG_HC_SECTION_ID = 'ncp/hc_sect_id'
TAG_ING_CTRL = 'ncp/ing_ctrl'
TAG_IP_POOL_ID = 'ncp/ip_pool_id'
TAG_ISOLATED = 'ncp/isolated'
TAG_ISOLATION_SECTION = 'ncp/isol_sect_id'
TAG_NODE_NAME = 'ncp/node_name'
TAG_NP = 'ncp/network_policy'
TAG_POD = 'ncp/pod'
TAG_PROJECT = 'ncp/project'
TAG_SNAT_IP = 'ncp/snat_ip'
TAG_SUBNET = 'ncp/subnet'
TAG_SUBNET_ID = 'ncp/subnet_id'
TAG_VERSION = 'ncp/version'
TAG_NO_SNAT = 'ncp/no_snat'
TAG_TRUE = 'true'
TAG_FALSE = 'false'

# NCP Readiness probe file
READINESS_PROBE_FILE = '/tmp/ncp_ready'
