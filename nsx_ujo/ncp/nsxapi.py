#******************************************************************************
# Copyright (c) 2016-2017 VMware, Inc. All rights reserved.VMware Confidential.
#******************************************************************************

import collections
import copy
import functools
import json
import os

import netaddr
from oslo_concurrency import lockutils
from oslo_config import cfg
from oslo_log import log as logging
import six
from vmware_nsxlib.v3 import exceptions as nsxlib_exc
from vmware_nsxlib.v3 import nsx_constants as nsxlib_const
from vmware_nsxlib.v3 import resources
from vmware_nsxlib.v3 import router
from vmware_nsxlib.v3 import utils as nsxlib_utils

from nsx_ujo.common import constants as const
from nsx_ujo.common import exceptions as ncp_exc
from nsx_ujo.common import utils
from nsx_ujo.ncp import allocators
from nsx_ujo.ncp import cache
from nsx_ujo.ncp import main as ncp_main
from nsx_ujo.ncp import utils as ncp_utils

LOG = logging.getLogger(__name__)


@six.add_metaclass(ncp_utils.Singleton)
class NSXAPI(object):

    def __init__(self):
        self._mapping = cache.CoeNSXMapping()
        self._nsx_client = ncp_utils.NSXLibHolder.get_nsx_client()
        self._nsxlib = ncp_utils.NSXLibHolder.get_nsxlib()
        self._coe = ncp_main.get_coe_adaptor().driver
        self._port_client = self._get_port_client(self._nsx_client)
        self._router_client = self._get_router_client(self._nsx_client)
        self._router_port_client = \
            self._get_router_port_client(self._nsx_client)
        self._ip_pool_client = self._get_ip_pool_client(self._nsx_client)
        self._routerlib = router.RouterLib(
            self._router_client, self._router_port_client, self._nsxlib)
        self._overlay_tz = utils.get_overlay_tz_id()
        self._tier0_router = utils.get_tier0_router_id()
        self._fw_section_marker = utils.get_fw_section_marker_id()
        self._no_snat_ip_block_exists = False
        self._sync_ip_blocks()
        self._ncp_initialize_done()

    def _get_port_client(self, nsx_client):
        return resources.LogicalPort(nsx_client)

    def _get_router_client(self, nsx_client):
        return resources.LogicalRouter(nsx_client)

    def _get_router_port_client(self, nsx_client):
        return resources.LogicalRouterPort(nsx_client)

    def _get_ip_pool_client(self, nsx_client):
        return resources.IpPool(nsx_client)

    def _build_tags(self, project, pod=None, nsgroup_labels={},
                    ingress_controller=None, network_policy=None):
        # TODO(gangila): Adapt the utils functions for this
        # Add tags common to namespaces and pods
        tags = [{const.SCOPE: const.TAG_PROJECT,
                 const.TAG: project},
                {const.SCOPE: const.TAG_VERSION,
                 const.TAG: ncp_utils.NCP_VERSION},
                {const.SCOPE: const.TAG_COE,
                 const.TAG: cfg.CONF.coe.adaptor},
                {const.SCOPE: const.TAG_CLUSTER,
                 const.TAG: cfg.CONF.coe.cluster}]
        if pod:
            # Add pod specific tags
            tags.append({const.SCOPE: const.TAG_POD, const.TAG: pod})
            if ingress_controller is not None:
                tags.append({const.SCOPE: const.TAG_ING_CTRL,
                             const.TAG: ingress_controller})
            for key, value in six.iteritems(nsgroup_labels):
                tags.append({const.SCOPE: key, const.TAG: value})
        if network_policy:
            # TODO(abhiraut): Consider merging tags
            # Add network policy specific tags
            tags.append({const.SCOPE: const.TAG_NP,
                         const.TAG: network_policy['name']})
            tags.append({const.SCOPE: const.TAG_FW_SECTION_TYPE,
                         const.TAG: const.NETWORK_POLICIES})
            tags.append({const.SCOPE: const.TAG_FW_SECTION_ENABLED,
                         const.TAG: str(network_policy['is_enabled'])})
        return tags

    def _ncp_initialize_done(self):
        try:
            os.remove(const.READINESS_PROBE_FILE)
        except OSError:
            LOG.info('No existing cache ready file found')
        # Create the file which indicates NCP is ready to serve requests
        # governed by the readiness probe in NCP yaml spec
        try:
            open(const.READINESS_PROBE_FILE, 'a').close()
        except OSError:
            LOG.error('failed to open a cache ready file')

    def _format_nsgroup_labels(self, old_labels, new_labels):
        # This method formats labels such that labels which are removed
        # from resources will have their values set to None so that backend
        # can delete those tags.
        formatted_labels = new_labels
        deleted_keys = set(old_labels.keys()) - set(new_labels.keys())
        for key in deleted_keys:
            formatted_labels[key] = None
        return formatted_labels

    def _create_ip_pool(self, ip_block_id, ip_network, display_name=None,
                        reserve_gateway_address=True, tags=None):
        # TODO(dantingl): NSX IPAM should provide API to create IP pool
        # based on IP block subnet, refer to bug 1757498.
        # Leverage the fact that int(True) == 1 and int(False) == 0
        allocation_ranges = [
            {'start': str(ip_network[int(reserve_gateway_address) + 1]),
             'end': str(ip_network[-2])}
        ]
        ip_pool = self._ip_pool_client.create(
            cidr=str(ip_network.cidr),
            display_name=display_name,
            allocation_ranges=allocation_ranges,
            tags=tags or [])
        LOG.debug('Created ip pool %s with range %s', ip_pool['id'],
                  ip_pool['subnets'][0]['allocation_ranges'])
        return ip_pool

    @utils.retry_if_exception_raise(max_retries=1)
    @utils.rollback_if_exception_raise
    def _create_pool_from_ip_block(self, ip_block_getter, subnet_size,
                                   display_name=None,
                                   reserve_gateway_address=True, tags=None,
                                   rollback_callbacks=[]):
        selected_ip_block = None
        for ip_block in ip_block_getter():
            try:
                ip_block_subnet = self._nsxlib.ip_block_subnet.create(
                    ip_block['id'], subnet_size)
                LOG.debug('Allocated subnet %s from IP block %s',
                          ip_block_subnet['id'], ip_block['id'])
                selected_ip_block = ip_block
                break
            except nsxlib_exc.ManagerError as e:
                LOG.warning('Failed to allocate subnet from IP block %s: %s',
                            ip_block['id'], str(e), security=True)
                # set the IP block as full when specified exception is raised
                if e.error_code == ncp_exc.IP_BLOCK_ALLOCATION_ERROR_CODE:
                    self._set_ip_block_status(ip_block['id'],
                                              const.IP_ALLOCATION_FULL)
        else:
            # Resync ip blocks with MP to see if there's new ip block, the
            # retry_if_exception_raise decorator will ensure it getting retried
            self._sync_ip_blocks()
            raise ncp_exc.ManagerError(
                manager=cfg.CONF.nsx_v3.nsx_api_managers,
                operation='Allocate subnet from IP block')

        selected_ip_block['subnets'].add(ip_block_subnet['id'])
        self._mapping.insert(selected_ip_block['id'], selected_ip_block,
                             parent_key=const.IP_BLOCK)
        rollback_callbacks.append(functools.partial(
            self._release_subnet_to_ip_block, ip_block_subnet['id']))
        LOG.debug('Created ip block subnet %s with ranges %s and cidr %s',
                  ip_block_subnet['id'],
                  ip_block_subnet['allocation_ranges'],
                  ip_block_subnet['cidr'])
        # Convert subnet range to IP pool range, the first one is network
        # address, the second one is gateway address, and the last one
        # is broadcast address. Here to remove them from range of IP pool.
        ip_network = netaddr.IPNetwork(ip_block_subnet['cidr'])
        ip_pool = self._create_ip_pool(selected_ip_block['id'], ip_network,
                                       display_name, reserve_gateway_address,
                                       tags)
        return ip_block_subnet, ip_pool

    def _find_external_ip_pools(self):
        query_tags = [
            {'scope': ncp_utils.escape_data(const.TAG_EXTERNAL_POOL),
             'tag': const.TAG_TRUE},
            {'scope': ncp_utils.escape_data(const.TAG_CLUSTER),
             'tag': ncp_utils.escape_data(cfg.CONF.coe.cluster)}
        ]
        try:
            ip_pools = self._nsxlib.search_by_tags(
                resource_type=const.IP_POOL, tags=query_tags)
            if ip_pools['result_count']:
                ip_pools_free = [
                    {'status': const.IP_ALLOCATION_FREE, 'id': ip_pool['id']}
                    for ip_pool in ip_pools['results']
                ]
                return ip_pools_free
        except nsxlib_exc.ManagerError as e:
            LOG.error("Unable to execute external ip pools search query "
                      "for cluster %s: %s", cfg.CONF.coe.cluster, str(e))

    def _create_external_ip_pools(self):
        external_subnet_prefix = (cfg.CONF.nsx_v3.external_subnet_prefix or
                                  cfg.CONF.nsx_v3.subnet_prefix)
        subnet_size = 2 ** (32 - external_subnet_prefix)
        pool_tags = [
            {'scope': const.TAG_EXTERNAL_POOL, 'tag': const.TAG_TRUE},
            {'scope': const.TAG_CLUSTER, 'tag': cfg.CONF.coe.cluster}
        ]
        _, ip_pool = self._create_pool_from_ip_block(
            self._get_available_external_ip_block, subnet_size,
            display_name=utils.generate_display_name('ext'),
            reserve_gateway_address=False, tags=pool_tags)
        # This method is supposed to return a list
        LOG.debug("Created an external IP pool %s for cluster %s",
                  ip_pool['id'], cfg.CONF.coe.cluster)
        return [ip_pool]

    def _allocate_external_ip(self, external_ip_pools):
        for ip_pool in external_ip_pools:
            try:
                allocation = self._ip_pool_client.allocate(ip_pool['id'])
                return {
                    'allocation_id': allocation['allocation_id'],
                    'ip_pool_id': ip_pool['id']
                }
            except nsxlib_exc.ManagerError as e:
                # Something went wrong while allocating IP, try again with
                # next pool
                LOG.warning("Unable to allocate IP address from pool %s: %s",
                            ip_pool['id'], str(e))
                if e.error_code == ncp_exc.IP_ALLOCATION_ERROR_CODE:
                    ip_pool['status'] = const.IP_ALLOCATION_FULL
                continue
            except KeyError:
                # The response body does not have an allocation_id
                # attribute (if this happens it is a symptom of some
                # deeper problem in NSX mgr)
                LOG.warning("Allocation response from pool %s did not "
                            "return an IP address", ip_pool['id'])
                continue
            else:
                raise ncp_exc.ManagerError(
                    manager=cfg.CONF.nsx_v3.nsx_api_managers,
                    operation='External IP allocation',
                    details=('Unable to allocate external IP')
                )

    def _get_external_ip_pools(self):
        ip_pools = (
            self._mapping.get_all(parent_key=const.EXTERNAL_POOL).values()
        )
        if not ip_pools:
            # cache miss
            ip_pools = self._find_external_ip_pools()
            if not ip_pools:
                LOG.error("Fail to find external IP pool in cluster %s",
                          cfg.CONF.coe.cluster)
        ip_pool_free = [ip_pool for ip_pool in ip_pools or []
                if ip_pool['status'] == 'free']
        if not ip_pool_free:
            ip_pools = self._create_external_ip_pools()
            if ip_pools:
                LOG.debug(
                    "Found external IP pools (%s) for cluster %s",
                    ",".join(ip_pool['id'] for ip_pool in ip_pools),
                    cfg.CONF.coe.cluster
                )
                ip_pool_free = [
                    {'status': const.IP_ALLOCATION_FREE, 'id': ip_pool['id']}
                    for ip_pool in ip_pools
                ]
            else:
                ip_pool_free = []
        for ip_pool in ip_pool_free:
            self._mapping.insert(
                ip_pool['id'], ip_pool, parent_key=const.EXTERNAL_POOL
            )
        return ip_pool_free

    def _allocate_snat_ip(self, project, nsx_router_id):
        LOG.debug("Allocating SNAT IP for project %s in cluster %s",
                  project, cfg.CONF.coe.cluster)
        ip_pools = self._get_external_ip_pools()
        if not ip_pools:
            LOG.error("Unable to configure SNAT rule as no external "
                      "IP pool is available for project %s in cluster %s",
                      project, cfg.CONF.coe.cluster)
            return None

        # Allocate SNAT IP from one of the external IP Pools
        while ip_pools:
            result = self._allocate_external_ip(ip_pools)
            if result:
                snat_ip = result['allocation_id']
                ip_pool_id = result['ip_pool_id']
                LOG.debug("Allocated SNAT IP %s from external IP pool %s in "
                          "project %s in cluster %s", snat_ip, ip_pool_id,
                          project, cfg.CONF.coe.cluster)
                snat_tags = [
                    {'scope': const.TAG_SNAT_IP, 'tag': snat_ip},
                    {'scope': const.TAG_EXTERNAL_POOL_ID, 'tag': ip_pool_id}
                ]
                # Update the project Tier-1 logical router with the snat tags
                self._update_project_router(
                    project, router_id=nsx_router_id, tags_update=snat_tags
                )
                return result
            else:
                # reallocate the pools
                LOG.debug("try re-allocate ip pools for project %s "
                          "in cluster %s", project, cfg.CONF.coe.cluster)
                ip_pools = self._get_external_ip_pools()
                if not ip_pools:
                    LOG.error("Failed re-allocating ip pools for project %s "
                          "in cluster %s", project, cfg.CONF.coe.cluster)
                    break

    def _configure_snat_rule(self, project, subnet):
        # Retrieve SNAT IP from project mappings. There should never be a
        # cache miss
        project_nsx_mapping = self._mapping.get(
            project, parent_key=const.PROJECT)
        snat_ip = project_nsx_mapping[const.SNAT_IP]

        # Add a SNAT rule for the subnet using the project's SNAT IP
        try:
            self._nsxlib.logical_router.add_nat_rule(
                self._tier0_router, 'SNAT', snat_ip, source_net=subnet)
        except nsxlib_exc.ManagerError:
            raise ncp_exc.ManagerError(
                manager=cfg.CONF.nsx_v3.nsx_api_managers,
                operation='SNAT Rule configuration',
                details=('Unable to create SNAT rule for subnet %s on '
                         'logical router %s' % (subnet, self._tier0_router)))

        # SNAT rule successfully configured
        LOG.debug("Configured SNAT on router %s via IP %s for project %s "
                  "and subnet %s in cluster %s", self._tier0_router,
                  snat_ip, project, subnet, cfg.CONF.coe.cluster)

    def _unconfigure_snat_rule(self, project, subnet):
        self._nsxlib.logical_router.delete_nat_rule_by_values(
            self._tier0_router, match_source_network=subnet)
        LOG.debug("Removed SNAT rule on router %s for project %s "
                  "and subnet %s in cluster %s", self._tier0_router,
                  project, subnet, cfg.CONF.coe.cluster)

    def get_health(self):
        LOG.debug('CLI is enquiring about NSX Manager health')
        err = const.CLI_ERR_CODE['SUCCESS']
        try:
            zones = self._nsx_client.get('transport-zones', silent=True)
            LOG.info('NSX manager is reachable for transport-zones %s', zones)
            return (const.HEALTHY, err['code'], err['desc'])
        except nsxlib_exc.ManagerError:
            return (const.UNHEALTHY, err['code'], err['desc'])

    def create_project(self, project, do_snat=True, nsgroup_labels=None):
        lock_name = 'project-lock-%s' % project
        with lockutils.lock(lock_name):
            return self._create_project(project, do_snat, nsgroup_labels)

    @utils.rollback_if_exception_raise
    def _create_project(self, project, do_snat=True, nsgroup_labels=None,
                        rollback_callbacks=[]):
        # NOTE(gangila): Each project maps to a logical router and multiple
        # logical switches. First create logical router and one logical switch
        # and update the mapping in the cache if it doesn't exist else return
        # the existing mapping. Other logical switches will be created when
        # existing IP pool is exhausted.
        LOG.info('Creating logical network for project %s', project,
                 security=True)

        # NOTE(gangila): We need to check this because when we start NCP,
        # we get events for namepsace's and pods' which already exist.
        project_nsx_mapping = self._mapping.get(
            project, parent_key=const.PROJECT) or {}
        if const.LR not in project_nsx_mapping:
            # Create logical router for the project
            tags = self._build_tags(project)
            try:
                router_name = utils.generate_display_name(project)
                router = self._router_client.create(router_name, tags)
                rollback_callbacks.append(functools.partial(
                    self._router_client.delete, router['id']))
                LOG.debug('Created logical router %s for project %s',
                          router['id'], project)
                project_nsx_mapping[const.LR] = router['id']
                # Attach the tier-1 router to the tier0 router if a tier0
                # router uuid is specified in ncp.ini and update the edge
                # cluster.
                LOG.debug('Linking tier-1 router %s to tier-0 router %s',
                          router['id'], self._tier0_router)
                self._routerlib.add_router_link_port(
                    router['id'], self._tier0_router, tags)
                rollback_callbacks.append(functools.partial(
                    self._routerlib.remove_router_link_port, router['id'],
                    self._tier0_router))
                router_info = {}
                self._routerlib.validate_tier0(
                    router_info, self._tier0_router)
                # Enable route advertisement
                # REVISIT(gangila): Setting all flags to True for now.
                advertise_route_nat_flag = True
                advertise_route_connected_flag = True
                advertise_route_static_flag = True
                self._routerlib.update_advertisement(
                    router['id'],
                    advertise_route_nat_flag,
                    advertise_route_connected_flag,
                    advertise_route_static_flag)
                # Allocate a SNAT IP, if required
                # NOTE(salv-orlando): The code currently will only log
                # errors when there is a failure allocating SNAT IP.
                # This will probably need to be reassessed as we might
                # want to make this failure fatal for project creation
                if do_snat:
                    result = self._allocate_snat_ip(
                        project, router['id'])
                    if result:
                        snat_ip = result['allocation_id']
                        pool_id = result['ip_pool_id']
                        rollback_callbacks.append(functools.partial(
                            self._ip_pool_client.release, pool_id, snat_ip))
                        rollback_callbacks.append(
                            functools.partial(
                                self._set_ip_pool_status,
                                pool_id, const.IP_ALLOCATION_FREE)
                        )
                        project_nsx_mapping[const.SNAT_IP] = snat_ip
                        project_nsx_mapping[const.EXTERNAL_POOL_ID] = pool_id
                # IF both ls and lr creation succeeds then add it to the cache.
                self._mapping.insert(
                    project, project_nsx_mapping, parent_key=const.PROJECT)
                rollback_callbacks.append(functools.partial(
                    self._mapping.delete, project, parent_key=const.PROJECT))
            except nsxlib_exc.ManagerError as e:
                _msg = ('Failed to create mapping for tier-1 logical router %s'
                        'to project %s: %s') % (router['id'], project, str(e))
                LOG.exception(_msg)
                raise ncp_exc.ManagerError(
                    manager=cfg.CONF.nsx_v3.nsx_api_managers,
                    operation='Logical router creation',
                    details=_msg)
        else:
            LOG.debug('Project %s already has mapped logical router', project)

        if const.LS not in project_nsx_mapping:
            # Create logical switch for the project
            self._create_logical_switch(project, nsgroup_labels, do_snat)
            project_nsx_mapping = self._mapping.get(
                project, parent_key=const.PROJECT)
        else:
            LOG.debug('Project %s already has mapped logical switch', project)

        LOG.debug('Project %s has mapping: %s', project, project_nsx_mapping)
        return project_nsx_mapping

    def update_project(self, project, nsgroup_labels=None):
        LOG.debug('Updating logical network for project %s', project)
        proj_nsx_mapping = self._mapping.get(project,
                                             parent_key=const.PROJECT)
        if not proj_nsx_mapping:
            LOG.warning('No logical switch is mapped to project %s', project)
            return

        # Update logical switches associated with the project
        nsgroup_labels = nsgroup_labels or {}
        old_labels = proj_nsx_mapping.get('labels')
        if not (old_labels is None or
                ncp_utils.is_modified(old_labels, nsgroup_labels)):
            return

        # Update LogicalSwitch tags with namespace labels
        tags = self._build_tags(project)
        for key, value in six.iteritems(nsgroup_labels):
            tags.append({const.SCOPE: key, const.TAG: value})
        tags = [ncp_utils.validate_tag(tag) for tag in tags]
        for ls in proj_nsx_mapping[const.LS]:
            cidr = ls[const.SUBNET]
            subnet_id = ls[const.SUBNET_ID]
            ip_pool_id = ls[const.IP_POOL_ID]
            ls_tags = tags + [{const.SCOPE: const.TAG_SUBNET,
                               const.TAG: cidr},
                              {const.SCOPE: const.TAG_SUBNET_ID,
                               const.TAG: subnet_id},
                              {const.SCOPE: const.TAG_IP_POOL_ID,
                               const.TAG: ip_pool_id}]
            try:
                self._nsxlib.logical_switch.update(
                    lswitch_id=ls['id'],
                    admin_state=True, tags=ls_tags)
            except nsxlib_exc.ResourceNotFound:
                # Do not raise in this case as this condition could:
                # 1 - not be necessarily harmful as the project might
                # be about to be deleted or no pods might be deployed
                # on the logical switch
                # 2 - be recoverable by reconfiguring logical ports
                # for affected pods on another logical swtich (todo)
                # In any case log the condition as warning
                LOG.warning("Logical switch %s for project %s not "
                            "found on NSX backend. Unable to update "
                            "labels", ls['id'], project)
            except nsxlib_exc.ManagerError as e:
                _msg = ('Failed to update tags on logical switch %s '
                        'for project %s: %s') % (ls, project, str(e))
                LOG.exception(_msg)
                raise ncp_exc.ManagerError(
                    manager=cfg.CONF.nsx_v3.nsx_api_managers,
                    operation='Logical switch update',
                    details=_msg)
        # Update project cache mappings based on updated logical
        # switch from the backend.
        proj_nsx_mapping['labels'] = nsgroup_labels
        self._mapping.insert(
            project, proj_nsx_mapping, parent_key=const.PROJECT)

    def delete_project(self, project):
        LOG.info('Deleting logical network for project %s', project,
                 security=True)
        # Delete the logical switch associated with the project
        proj_nsx_mapping = self._mapping.get(project,
                                             parent_key=const.PROJECT)
        LOG.debug('Deleting mapping of project %s: %s', project,
                  proj_nsx_mapping, security=True)
        if proj_nsx_mapping:
            # Delete logical switches
            snat_ip = proj_nsx_mapping.get(const.SNAT_IP)
            pool_id = proj_nsx_mapping.get(const.EXTERNAL_POOL_ID)
            for ls in proj_nsx_mapping[const.LS]:
                try:
                    self._router_port_client.delete_by_lswitch_id(ls['id'])
                    self._nsxlib.logical_switch.delete(ls['id'])
                    LOG.debug('Deleted logical switch %s for project %s',
                              ls['id'], project, security=True)
                    # Unconfiguring SNAT rule for subnet
                    if snat_ip:
                        self._unconfigure_snat_rule(project, ls[const.SUBNET])

                    # Delete IP Pool and IP block subnet
                    self._delete_project_subnet(
                        ls[const.SUBNET_ID], ls[const.IP_POOL_ID])
                except nsxlib_exc.ManagerError as e:
                    # Continue to delete other logical switches if there is
                    # an exception
                    LOG.error("Failed to delete Logical switch %s for "
                              "project %s: %s", ls['id'], project, str(e),
                              security=True)

            try:
                # Release SNAT IP allocated for the project
                if snat_ip and pool_id:
                    self._ip_pool_client.release(pool_id, snat_ip)
                    self._set_ip_pool_status(pool_id, const.IP_ALLOCATION_FREE)
                else:
                    # This is not necessarily troubling, as it is ok for
                    # no-nat projects
                    LOG.info("Unable to release SNAT IP %s for router %s "
                             "in project %s in cluster %s", snat_ip,
                             proj_nsx_mapping[const.LR], project,
                             cfg.CONF.coe.cluster, security=True)

                # Remove the tier0 router link port if present
                # Else this just throws a ResourceNotFound warning
                if self._tier0_router:
                    self._routerlib.remove_router_link_port(
                        proj_nsx_mapping[const.LR],
                        self._tier0_router)
                self._router_client.delete(proj_nsx_mapping[const.LR])
                LOG.debug('Deleted logical router %s for project %s',
                          proj_nsx_mapping[const.LR], project, security=True)

                # Delete the mapping in the cache
                self._mapping.delete(project, parent_key=const.PROJECT)
            except nsxlib_exc.ManagerError as e:
                _msg = ('Failed to delete mapping to project %s for '
                        'tier-1 logical router %s: %s') % (
                    project, proj_nsx_mapping[const.LR], str(e))
                LOG.exception(_msg, security=True)
                raise ncp_exc.ManagerError(
                    manager=cfg.CONF.nsx_v3.nsx_api_managers,
                    operation='Logical router deletion',
                    details=_msg)
        else:
            LOG.warning('No logical switch is mapped to project %s', project)

    @utils.rollback_if_exception_raise
    def _create_logical_switch(self, project,
                               nsgroup_labels=None, do_snat=True,
                               rollback_callbacks=[]):
        LOG.debug("Creating logical switch for project %s", project,
                  security=True)
        project_nsx_mapping = self._mapping.get(
            project, parent_key=const.PROJECT)
        if const.LS not in project_nsx_mapping:
            project_nsx_mapping[const.LS] = []
        tags = self._build_tags(project)
        try:
            # Use Logical Switch count in creating logical switches and
            # IP Pools with a unique display name.
            ls_count = len(project_nsx_mapping[const.LS])
            ip_pool_name = utils.generate_display_name(project, count=ls_count)
            # Allocate IP block subnet and IP pool for this project
            ip_block_subnet, ip_pool = self._create_project_subnet(
                do_snat, ip_pool_name=ip_pool_name)
            rollback_callbacks.append(functools.partial(
                self._delete_project_subnet, ip_block_subnet['id'],
                ip_pool['id']))
            tags.append({const.SCOPE: const.TAG_SUBNET,
                         const.TAG: ip_block_subnet['cidr']})
            # Create SNAT rule for the subnet, if needed
            if do_snat:
                self._configure_snat_rule(project, ip_block_subnet['cidr'])
                # Add an action to undo the SNAT rule upon failures
                rollback_callbacks.append(functools.partial(
                    self._unconfigure_snat_rule,
                    project,
                    ip_block_subnet['cidr']))
            ls_tags = copy.copy(tags)
            # Add logical switch specific tags
            ls_tags.append({const.SCOPE: const.TAG_SUBNET_ID,
                            const.TAG: ip_block_subnet['id']})
            ls_tags.append({const.SCOPE: const.TAG_IP_POOL_ID,
                            const.TAG: ip_pool['id']})
            # Update LogicalSwitch tags with namespace labels
            nsgroup_labels = nsgroup_labels or {}
            for key, value in six.iteritems(nsgroup_labels):
                ls_tags.append({const.SCOPE: key, const.TAG: value})
            #TODO(abhiraut): Tags must also be validated for maximum
            #                number of tags allowed on the backend.
            ls_tags = [ncp_utils.validate_tag(tag) for tag in ls_tags]
            ls_name = utils.generate_display_name(project, count=ls_count)
            ls = self._nsxlib.logical_switch.create(
                ls_name, self._overlay_tz, ls_tags,
                ip_pool_id=ip_pool['id'])
            rollback_callbacks.append(functools.partial(
                self._nsxlib.logical_switch.delete, ls['id']))
            logical_switch = {
                'id': ls['id'],
                const.SUBNET: ip_block_subnet['cidr'],
                const.SUBNET_ID: ip_block_subnet['id'],
                const.IP_POOL_ID: ip_pool['id'],
            }

            # Attach logical switch to logical router
            self._attach_switch_to_router(
                project, project_nsx_mapping[const.LR],
                ls['id'], ip_block_subnet['cidr'], tags)

            LOG.debug('Created logical switch %s for project %s',
                      ls['id'], project, security=True)
        except nsxlib_exc.ManagerError as e:
            # TODO(dantingl): clean up created resource if there is a failure
            _msg = ('Failed to create logical switch for project %s: %s' %
                    (project, str(e)))
            LOG.exception(_msg, security=True)
            raise nsxlib_exc.ManagerError(
                operation='Logical switch creation', details=_msg)

        # Add to cache if the ls and subnet creation succeeds
        project_nsx_mapping[const.LS].append(logical_switch)
        # Add the labels to the LS level in cache since it is a property of
        # project instead of a single logical switch.
        project_nsx_mapping['labels'] = nsgroup_labels
        self._mapping.insert(
            project, project_nsx_mapping, parent_key=const.PROJECT)
        return logical_switch

    @utils.rollback_if_exception_raise
    def _attach_switch_to_router(self, project, router_id,
                                 switch_id, subnet, tags,
                                 rollback_callbacks=[]):
        try:
            ip_network = netaddr.IPNetwork(subnet)
            lr_inf_ip_addr = str(ip_network[1])
            address_groups = {}
            address_groups['ip_addresses'] = [lr_inf_ip_addr]
            address_groups['prefix_length'] = cfg.CONF.nsx_v3.subnet_prefix

            lr_port = 'lrp-%s' % project
            lif_id = 'LR-%s' % project
            # Create logical switch port
            # NOTE(gangila): We just create a logical switch port
            # with attachment_type as None, when we attach the router
            # to this logical switch port, MP sets the port attachment type
            # to LR.
            # TODO(gangila): Handle the case where user deletes the ls
            # from NSX backend, so that the project_nsx_mapping won't
            # have the 'ls' key, hence this would fail
            # TODO(gangila): Handle these cases too:
            # The LR was deleted but the LS port which connected to
            # LR is there.
            # The LR was not deleted but the LS port connecting
            # to the LR was.
            link_port_id = self._port_client.create(
                switch_id,
                lif_id,
                attachment_type=None)
            rollback_callbacks.append(functools.partial(
                self._port_client.delete, link_port_id['id']))
            # NOTE(gangila): urpf mode is set to NONE for tier-1 logical
            # router ports, this is to enable kubelet health checks ie.
            # the src port and destination port for the packets are the
            # same.
            LOG.debug('Attaching logical switch %s to logical router %s with '
                      'address %s via link port %s', switch_id, router_id,
                      lr_inf_ip_addr, link_port_id['id'], security=True)
            self._routerlib.create_logical_router_intf_port_by_ls_id(
                logical_router_id=router_id,
                display_name=lr_port,
                tags=tags,
                ls_id=switch_id,
                logical_switch_port_id=link_port_id['id'],
                address_groups=[address_groups],
                urpf_mode='NONE')
        except nsxlib_exc.ManagerError as e:
            _msg = ('Failed to attach logical switch %s to logical '
                    'router %s: %s') % (switch_id, router_id, str(e))
            LOG.exception(_msg, security=True)
            raise nsxlib_exc.ManagerError(
                operation='Logical switch attachment', details=_msg)

    def _allocate_ingress_ip(self, project):
        ip_pools = self._get_external_ip_pools()
        if not ip_pools:
            LOG.error("Unable to configure SNAT rule as no external IP "
                      "pool is available for project %s in cluster %s",
                      project, cfg.CONF.coe.cluster)
            raise ncp_exc.ExternalIPAllocationFailure(
                error_message=("No suitable external IP pool found for "
                               "project %s" % project))
        # Allocate ingress IP from one of the external IP Pools
        return self._allocate_external_ip(ip_pools)

    def _release_ingress_ip(self, external_ip, pool_id):
            self._ip_pool_client.release(
                pool_id=pool_id, ip_addr=external_ip)

    def _set_ip_pool_status(self, pool_id, status):
        ip_pool = self._mapping.get(pool_id, const.EXTERNAL_POOL)
        if ip_pool['id'] == pool_id:
            ip_pool['status'] = status

    def _build_container_spoofguard_profile(self):
        switch_profile = collections.namedtuple('switch_profile',
                                                ['profile_type',
                                                 'profile_id'])
        switch_profile.profile_type = 'SpoofGuardSwitchingProfile'
        switch_profile.profile_id = \
            self._mapping.get('spoofguard-profile')
        LOG.info('Container spoofguard profile is %s',
                 switch_profile.profile_id, security=True)
        return switch_profile

    def _create_project_upon_cache_miss(self, project):
        project_nsx_mapping = self._mapping.get(
            project, parent_key=const.PROJECT)
        LOG.debug('Project %s has mapping: %s', project, project_nsx_mapping)
        # NOTE(qtian): Due to the implementation of create_project, there
        # is a mid state that the mapping has the LS key but the value is
        # empty.
        if (not project_nsx_mapping or
                not project_nsx_mapping.get(const.LS)):
            LOG.warning('Missing Logical switch in project %s', project)
            ls_name, ns_labels, ns_ann = self._coe.get_namespace(project)
            no_snat = ns_ann.get(const.NOSNAT_ANNOTATION)
            self.create_project(
                ls_name,
                do_snat=not utils.is_str_true(no_snat),
                nsgroup_labels=ns_labels)
            LOG.info('Created project %s after other resource '
                     'detected it is missing', project)

            # need to check/enable project isolation
            lock_name = 'project-np-lock-%s' % project
            with lockutils.lock(lock_name):
                project_nsx_mapping = self._mapping.get(
                    project, parent_key=const.PROJECT)
                project_nsx_mapping['isolation'] = {'is_isolated': False}
                is_proj_isolated = self._coe.is_namespace_isolated(project)
                if is_proj_isolated:
                    self.enable_project_isolation(project)

            project_nsx_mapping = self._mapping.get(
                project, parent_key=const.PROJECT)

        return project_nsx_mapping

    def create_pod(self, pod, project, node_ip, host_vif_id,
                   nsgroup_labels={}, cluster_id='',
                   create_ingress_rules=False, health_check_ports=None):
        LOG.debug('Creating port for pod %s in project %s', pod, project)
        pod_key = utils.get_resource_key(project, pod)
        pod_info = {}
        cached_pod = self._mapping.get(pod_key, const.POD)
        original_pod = cached_pod.copy() if cached_pod else None

        # NOTE(gangila): Prevent topology replication when we restart NCP.
        if not cached_pod:
            project_nsx_mapping = self._create_project_upon_cache_miss(project)

            cif_id = allocators.CifAllocator.get_cif_id()
            pod_info['attachment_id'] = cif_id

            # NOTE(salv-orlando): The ingress_controller attribute is
            # specific to kubernetes and therefore constitutes a potential
            # violation of NSXAPI adaptor independency principle
            pod_info['ingress_controller'] = create_ingress_rules
            try:
                pod_info['vlan'] = allocators.VlanAllocator().get_node_vlan(
                    host_vif_id)
            except ncp_exc.IdPoolExhausted:
                _msg = ("Exhausted VLAN-ID on host VIF %s for "
                        "creating project-pod: %s-%s"
                        % (host_vif_id, project, pod))
                LOG.error(_msg)
                raise ncp_exc.ManagerError(
                        manager=cfg.CONF.nsx_v3.nsx_api_managers,
                        operation='Pod creation',
                        details=_msg)

            tags = self._build_tags(
                project=project, pod=pod,
                nsgroup_labels=nsgroup_labels,
                ingress_controller=create_ingress_rules)
            tags = [ncp_utils.validate_tag(tag) for tag in tags]

            switch_profile = self._build_container_spoofguard_profile()

            # Create port in a loop until it succeeds. Use next logical switch
            # if there is IP pool exhausted exception. Create a new logical
            # switch if no available one in cache.
            ls_list = project_nsx_mapping[const.LS]
            idx = 0
            while True:
                if idx < len(ls_list):
                    ls = ls_list[idx]
                else:
                    # Retrieve labels from coe
                    ns_labels = self._coe.get_namespace(project)[1]
                    ls = self._create_logical_switch(project,
                                                     nsgroup_labels=ns_labels)
                ip_network = netaddr.IPNetwork(ls['subnet'])
                pod_info['gateway_ip'] = str(ip_network[1])
                try:
                    # Create the CIF port
                    port = self._port_client.create(
                        ls['id'], cif_id, tags=tags,
                        parent_vif_id=host_vif_id,
                        traffic_tag=pod_info['vlan'],
                        switch_profile_ids=[switch_profile],
                        vif_type=const.CIF_TYPE, app_id=pod_key,
                        allocate_addresses=const.CIF_ALLOCATE_ADDRESSES)
                    break
                except nsxlib_exc.ManagerError as e:
                    # create new logical switch for IP exhaustion case
                    if e.error_code == ncp_exc.IP_ALLOCATION_ERROR_CODE:
                        idx += 1
                        LOG.debug('Failed to allocate ip for pod %s: %s',
                                  pod, str(e))
                        continue
                    _msg = 'Failed to create port for pod %s: %s' % (
                        pod, str(e))
                    LOG.exception(_msg)
                    raise ncp_exc.ManagerError(
                        manager=cfg.CONF.nsx_v3.nsx_api_managers,
                        operation='Logical Port creation',
                        details=_msg)

            pod_info['port_id'] = port['id']
            pod_info['ip'] = '%s/%s' % (
                port['address_bindings'][0]['ip_address'],
                ip_network.prefixlen)
            pod_info['mac'] = port['address_bindings'][0]['mac_address']
            pod_info['cif_id'] = cif_id
            pod_info['labels'] = nsgroup_labels

            self._mapping.insert(pod_key, pod_info, parent_key=const.POD)
            LOG.info('Created port %s with ip %s and mac %s',
                     port['id'], pod_info['ip'], pod_info['mac'])

        else:
            # No need to create a logical port for the pod as it was created
            # earlier. Update the logical port if the pod attrs were modified.
            LOG.debug("Logical switch port for pod %s in project %s "
                      "already configured", pod, project)
            old_labels = cached_pod.get('labels', {})
            if ncp_utils.is_modified(old_labels, nsgroup_labels):
                formatted_labels = self._format_nsgroup_labels(
                    old_labels, nsgroup_labels)
                self.update_pod(pod, project, host_vif_id,
                                formatted_labels,
                                cached_pod['ingress_controller'])

        if create_ingress_rules and pod_info.get('ip'):
            # TODO(salv-orlando): Optimize this operation. You know you can do
            # it. Don't be lazy.
            # Project mapping should exist at this stage
            project_nsx_mapping = self._mapping.get(
                project, parent_key=const.PROJECT)
            pod_ip = utils.remove_ip_prefix(pod_info['ip'])
            try:
                # Allocate an ingress IP address
                result = self._allocate_ingress_ip(project)
                if result:
                    ingress_ip = result['allocation_id']
                    pool_id = result['ip_pool_id']
                    LOG.debug("Updating NAT rules for external IP address %s "
                        "in pod %s in project %s", ingress_ip, pod, project)
                    self._routerlib.delete_fip_nat_rules(
                        self._tier0_router, ingress_ip, pod_ip)
                    self._routerlib.add_fip_nat_rules(
                        self._tier0_router, ingress_ip, pod_ip,
                        match_ports=[80, 443])
                    self._mapping.insert(
                        pod_key,
                        {'ip': ingress_ip, 'pool_id': pool_id},
                        parent_key=const.EXT_IP
                    )
            except ncp_exc.ExternalIPAllocationFailure as e:
                # TODO(salv-orlando): Consider making this error fatal for
                # successful pod configuration. This will imply destroying
                # the pods' logical port
                LOG.error("Failure while allocation external IP address "
                          "for pod %s in project %s: %s",
                          pod, project, str(e))

        # Set firewall rule for health check
        # TODO(dantingl): Integrate with update_pod to avoid extra NSX API call
        # Also need to confirm if health check configuration update is possible
        pod_info = self._mapping.get(pod_key, parent_key=const.POD)
        if 'hc_section' not in pod_info and node_ip and health_check_ports:
            pod_ip = utils.remove_ip_prefix(pod_info['ip'])
            hc_section = self._add_health_check_rule_to_port(
                pod_ip, pod_info['port_id'], node_ip, health_check_ports)
            pod_info[const.HC_SECTION] = hc_section
            # TODO(danting): add a wrapper method to update data cache value
            self._mapping.insert(
                pod_key, pod_info, parent_key=const.POD)
            # Add health check firewall section id in tag
            try:
                hc_tag = [{const.SCOPE: const.TAG_HC_SECTION_ID,
                           const.TAG: hc_section}]
                switch_profile = self._build_container_spoofguard_profile()
                self._port_client.update(
                    lport_id=pod_info['port_id'],
                    vif_uuid=pod_info['cif_id'],
                    admin_state=True,
                    switch_profile_ids=[switch_profile],
                    parent_vif_id=host_vif_id,
                    traffic_tag=pod_info['vlan'],
                    tags_update=hc_tag,
                    vif_type=const.CIF_TYPE, app_id=pod_key,
                    allocate_addresses=const.CIF_ALLOCATE_ADDRESSES)
            except nsxlib_exc.ManagerError as e:
                _msg = ('Failed to update tag for firewall section on '
                        'logical port %s: %s') % (pod_info['port_id'], str(e))
                LOG.exception(_msg, security=True)
                raise ncp_exc.ManagerError(
                    manager=cfg.CONF.nsx_v3.nsx_api_managers,
                    operation='Health check firewall section tag update',
                    details=_msg)

        current_pod = self._mapping.get(pod_key, parent_key=const.POD)
        updated = ncp_utils.is_modified(original_pod, current_pod)
        return updated, {pod_key: json.dumps(current_pod)}

    def update_pod(self, pod, project, host_vif_id, nsgroup_labels={},
                   create_ingress_rules=False):
        LOG.debug('Updating port for pod %s in project %s', pod, project,
                  security=True)
        pod_key = utils.get_resource_key(project, pod)
        pod_info = self._mapping.get(pod_key, parent_key=const.POD)
        if pod_info:
            switch_profile = self._build_container_spoofguard_profile()
            tags = self._build_tags(
                project=project, pod=pod,
                nsgroup_labels=nsgroup_labels,
                ingress_controller=create_ingress_rules)
            tags = [ncp_utils.validate_tag(tag) for tag in tags]
            try:
                # Update the port
                self._port_client.update(
                    lport_id=pod_info['port_id'],
                    vif_uuid=pod_info['cif_id'],
                    admin_state=True,
                    switch_profile_ids=[switch_profile],
                    parent_vif_id=host_vif_id,
                    traffic_tag=pod_info['vlan'],
                    tags_update=tags,
                    vif_type=const.CIF_TYPE, app_id=pod_key,
                    allocate_addresses=const.CIF_ALLOCATE_ADDRESSES)
            except nsxlib_exc.ManagerError as e:
                _msg = 'Failed to update logical port %s for pod %s: %s' % (
                    pod_info['port_id'], pod, str(e))
                LOG.exception(_msg, security=True)
                raise ncp_exc.ManagerError(
                    manager=cfg.CONF.nsx_v3.nsx_api_managers,
                    operation='Logical Port update',
                    details=_msg)
            # Update the cache with new labels
            # As of now pod update is called to update labels only
            pod_info['labels'] = nsgroup_labels
            self._mapping.insert(
                pod_key, pod_info, parent_key=const.POD)
        else:
            LOG.warning('Pod %s has no port on NSX', pod, security=True)

    def delete_pod(self, pod, project, host_vif_id):
        LOG.debug('Deleting pod %s in project %s', pod, project,
                  security=True)
        pod_key = utils.get_resource_key(project, pod)
        pod_info = self._mapping.get(pod_key, parent_key=const.POD)
        if pod_info:
            try:
                # Delete health check firewall for the port
                if pod_info.get('hc_section'):
                    self._delete_health_check_rule(pod_info[const.HC_SECTION])
                # Delete the port
                LOG.info('Deleting logical port %s for pod %s in project %s',
                         pod_info['port_id'], pod, project, security=True)
                self._port_client.delete(pod_info['port_id'])
            except nsxlib_exc.ManagerError as e:
                _msg = 'Failed to delete logical port %s for pod %s: %s' % (
                    pod_info['port_id'], pod, str(e))
                LOG.exception(_msg, security=True)
                raise ncp_exc.ManagerError(
                    manager=cfg.CONF.nsx_v3.nsx_api_managers,
                    operation='Logical Port deletion',
                    details=_msg)

            allocators.VlanAllocator().release_node_vlan(host_vif_id,
                                                         pod_info['vlan'])
            # Remove the mapping from cache
            self._mapping.delete(pod_key, parent_key=const.POD)

            if pod_info.get('ingress_controller'):
                # We need to destroy all NAT mappings. The check will be
                # performed even if ingress mode is not NAT (pod in
                # hostnetwork mode are not processed by NCP anyway)
                LOG.debug("Deleting NAT rules for pod %s", pod, security=True)
                pod_ip = utils.remove_ip_prefix(pod_info['ip'])
                ext_ip_data = self._mapping.get(pod_key,
                                                parent_key=const.EXT_IP)
                if not ext_ip_data:
                    LOG.warning("No external IP configured for pod:%s", pod)
                    return
                # Remove NAT rules and IP allocation for ingress IP
                self._routerlib.delete_fip_nat_rules(self._tier0_router,
                                                     ext_ip_data['ip'],
                                                     pod_ip)
                self._release_ingress_ip(ext_ip_data['ip'],
                                         ext_ip_data['pool_id'])
                self._set_ip_pool_status(ext_ip_data['pool_id'],
                                         const.IP_ALLOCATION_FREE)
                # Remove the external IP mapping from cache
                self._mapping.delete(pod_key, parent_key=const.EXT_IP)
        else:
            LOG.warning('Pod %s has no port on NSX', pod)

    def get_pod(self, pod, project):
        LOG.debug('Retrieving info from cache for pod %s in project %s',
                  pod, project)
        pod_key = utils.get_resource_key(project, pod)
        return self._mapping.get(pod_key, parent_key=const.POD)

    def _create_project_subnet(self, do_snat=True, ip_pool_name=None):
        # Convert prefix to size of subnet, NSX API uses size to
        # create subnet.
        subnet_size = 2 ** (32 - cfg.CONF.nsx_v3.subnet_prefix)
        assert subnet_size > 2, "Invalid subnet size %d" % subnet_size
        ip_block_getter = functools.partial(
            self._get_available_internal_ip_block, do_snat=do_snat)
        return self._create_pool_from_ip_block(ip_block_getter, subnet_size,
                                               display_name=ip_pool_name)

    def _delete_project_subnet(self, subnet_id, ip_pool_id):
        try:
            self._ip_pool_client.delete(ip_pool_id)
            LOG.debug("Deleted IP pool %s", ip_pool_id, security=True)
            self._release_subnet_to_ip_block(subnet_id)
            LOG.debug("Deleted IP block subnet %s", subnet_id, security=True)
            # NOTE(salv-orlando): There is no need to remove NAT/No-NAT rules
            # for the subnet as the router is going to be removed anyway
        except nsxlib_exc.ManagerError as e:
            _msg = 'Failed to delete project subnet %s: %s' % (
                subnet_id, str(e))
            LOG.exception(_msg, security=True)
            raise nsxlib_exc.ManagerError(
                manager=cfg.CONF.nsx_v3.nsx_api_managers,
                operation='Project subnet deletion', details=_msg)

    def _update_project_router(self, project, router_id=None,
                               tags_update=None):
        if not router_id:
            router_id = self.get_ns_mapping(project).get(const.LR)
        if not router_id:
            LOG.warning("No logical router found under project %s", project)
            return
        # Retrieve logical router from backend
        l_router = self._router_client.get(router_id)
        tags = l_router.get('tags', [])
        # Update logical router tags
        if tags_update is not None:
            tags = nsxlib_utils.update_v3_tags(tags, tags_update)
        # TODO(abhiraut): If no updated name is provided for the router,
        #                 retrieve the original display name from the
        #                 backend so that name is not reset. Move this
        #                 logic to vmware-nsxlib.
        name = l_router.get('display_name')
        try:
            # Update logical router on the backend
            self._router_client.update(router_id, tags=tags,
                                       display_name=name)
        except nsxlib_exc.ManagerError as e:
            _msg = ('Failed to update logical router %s in project %s: %s'
                    % (router_id, project, str(e)))
            LOG.exception(_msg, security=True)
            raise ncp_exc.ManagerError(
                manager=cfg.CONF.nsx_v3.nsx_api_managers,
                operation='Project router update', details=_msg)

    def get_external_ip(self, project, pod):
        pod_key = utils.get_resource_key(project, pod)
        try:
            ext_ip_data = self._mapping.get(pod_key, parent_key=const.EXT_IP)
            if ext_ip_data:
                return ext_ip_data['ip']
        except KeyError:
            # The cache is a default dict, therefore we should not worry about
            # ext_ip_data being None thus raising a TypeError
            LOG.warning("Unexpected entry without IP address for "
                        "pod %s:%s", pod_key, ext_ip_data)

    def add_external_ip(self, project, pod, external_ip):
        # Set external IP in cache. NCP will also put external IP in cache even
        # if ingress controller pod is in host network mode.
        pod_key = utils.get_resource_key(project, pod)
        self._mapping.insert(pod_key, {'ip': external_ip,
                                       'pool_id': None},
                             parent_key=const.EXT_IP)
        LOG.debug("Added external IP %s in cache for pod %s in "
                  "project %s", external_ip, pod, project, security=True)

    def del_external_ip(self, project, pod):
        # Delete pod from cache, this is used only when ingress controller pod
        # is in host network mode.
        pod_key = utils.get_resource_key(project, pod)
        if self._mapping.get(pod_key, parent_key=const.EXT_IP):
            self._mapping.delete(pod_key, parent_key=const.EXT_IP)
            LOG.debug("Removed external IP from cache for pod %s in "
                      "project %s", pod, project, security=True)

    def get_external_ips(self):
        """Return external IPs in NCP cache."""
        ext_ips = self._mapping.get_all(const.EXT_IP)
        # Misplaced tags on the NSX logical ports might cause duplicated
        # entries in the NCP cache - use a set
        result = set()
        for pod_key, ext_ip in ext_ips.items():
            try:
                result.add(ext_ip['ip'])
            except TypeError as e:
                # Because the cache has a default dict generator, a defaultdict
                # might be found in place of an external IP if no external IP
                # is present in the cache for a given ingress controller pod.
                # This exception handler ensures this condition does not
                # generate failures.
                LOG.debug("Invalid external IP %s for pod %s: %s",
                          ext_ip, pod_key, str(e))
            except KeyError:
                LOG.warning("Unexpected entry without IP address for "
                            "pod %s:%s", pod_key, ext_ip)
        return result

    def add_host_network_pod(self, pod, project, pod_ip, event_type,
                             labels=None):
        pod_key = utils.get_resource_key(project, pod)
        pod_mappings = self._mapping.get(pod_key,
                                         parent_key=const.HOST_NETWORK_POD)
        if (pod_mappings and pod_mappings['pod_ip']
            and event_type != const.MODIFIED):
            LOG.debug("Mappings for host network pod %s for project %s "
                      "already exists", pod, project)
            return
        labels = labels or {}
        host_network_pod = {'pod_ip': pod_ip, 'labels': labels,
                            'project': project}
        self._mapping.insert(pod_key, host_network_pod,
                             parent_key=const.HOST_NETWORK_POD)
        LOG.debug("Added host network pod %s for project %s in cache.",
                  pod, project, security=True)

    def delete_host_network_pod(self, project, pod):
        pod_key = utils.get_resource_key(project, pod)
        if self._mapping.get(pod_key, parent_key=const.HOST_NETWORK_POD):
            self._mapping.delete(pod_key, parent_key=const.HOST_NETWORK_POD)
            LOG.debug("Deleted host network pod %s for project %s from cache.",
                      pod, project, security=True)

    def _get_host_network_pods(self, project, labels=None):
        """Retrieve pod IPs for host network pods."""
        pods = self._mapping.get_all(const.HOST_NETWORK_POD)
        pod_keys = []
        pod_ips = []
        for pod_key, pod in six.iteritems(pods):
            if pod['project'] == project and pod['pod_ip']:
                if labels and not utils.match_labels(
                    pod_labels=pod['labels'], policy_labels=labels):
                    # Do not append the pod to the lists if labels are
                    # specified and they do not match.
                    continue
                pod_keys.append(pod_key)
                pod_ips.append(pod['pod_ip'])
        return pod_keys, pod_ips

    def get_host_network_pods_by_ip(self, project, ip):
        """Retrieve pods with the same host IP for given project."""
        pods = self._mapping.get_all(const.HOST_NETWORK_POD)
        matched_pods = []
        for pod_key, pod in six.iteritems(pods):
            if (pod['project'] == project and
                pod['pod_ip'] == ip):
                matched_pods.append(pod)
        return matched_pods

    def _add_ip_block_cache(self, ip_block, external=False, no_snat=False):
        ip_block_info = {
            'id': ip_block['id'],
            'data': ip_block,
            'status': const.IP_ALLOCATION_FREE,
            'external': external,
            'no_snat': no_snat
        }
        subnets = self._nsxlib.ip_block_subnet.list(ip_block['id'])['results']
        ip_block_info['subnets'] = set(subnet['id'] for subnet in subnets)
        self._mapping.insert(ip_block['id'], ip_block_info,
                             parent_key=const.IP_BLOCK)

    def _get_available_ip_block(self, filter_fn):
        ip_blocks = self._mapping.get_all(const.IP_BLOCK).values()
        for ip_block in ip_blocks:
            if (ip_block['status'] == const.IP_ALLOCATION_FREE
                and filter_fn(ip_block)):
                yield ip_block

    def _get_available_internal_ip_block(self, do_snat=True):
        def ip_block_filter(ip_block):
            if ip_block['external']:
                return False
            if self._no_snat_ip_block_exists:
                return ip_block['no_snat'] != do_snat
            return True
        return self._get_available_ip_block(ip_block_filter)

    def _get_available_external_ip_block(self):
        return self._get_available_ip_block(
            lambda ip_block: ip_block['external'])

    def _sync_ip_blocks(self):
        LOG.info('Sync ip blocks for cluster %s', cfg.CONF.coe.cluster)
        current_ip_blocks = self._mapping.get_all(const.IP_BLOCK) or {}
        new_ip_blocks = self._nsxlib.ip_block.list()['results']
        for ip_block in new_ip_blocks:
            if ip_block['id'] in current_ip_blocks:
                continue
            external = any(tag['scope'] == const.TAG_EXTERNAL_POOL
                           for tag in ip_block['tags'])
            no_snat = any(tag['scope'] == const.TAG_NO_SNAT and
                          tag['tag'] == cfg.CONF.coe.cluster
                          for tag in ip_block['tags'])
            owned = any(tag['scope'] == const.TAG_CLUSTER and
                        tag['tag'] == cfg.CONF.coe.cluster
                        for tag in ip_block['tags'])
            if not external and not owned:
                continue
            LOG.info('Found new ip block %s for cluster %s', ip_block['id'],
                     cfg.CONF.coe.cluster)
            self._add_ip_block_cache(ip_block, external=external,
                                     no_snat=no_snat)
            if no_snat:
                LOG.info('Found no_snat ip block %s for cluster %s',
                         ip_block['id'], cfg.CONF.coe.cluster)
                self._no_snat_ip_block_exists = True

    def _release_subnet_to_ip_block(self, subnet_id):
        self._nsxlib.ip_block_subnet.delete(subnet_id)
        for ip_block in self._mapping.get_all(const.IP_BLOCK).values():
            if subnet_id in ip_block['subnets']:
                ip_block['status'] = const.IP_ALLOCATION_FREE
                ip_block['subnets'].remove(subnet_id)
                return

    def _set_ip_block_status(self, ip_block_id, status):
        ip_block = self._mapping.get(ip_block_id, parent_key=const.IP_BLOCK)
        ip_block['status'] = status
        self._mapping.insert(ip_block_id, ip_block, parent_key=const.IP_BLOCK)

    def get_ns_mapping(self, ns):
        """Return namespace mappings from the cache."""
        return self._mapping.get(ns, parent_key=const.PROJECT) or {}

    #NOTE(abhiraut): Move this method to nsxlib
    def _get_switch_tag_expression(self, scope, tag):
        return {'resource_type': nsxlib_const.NSGROUP_TAG_EXP,
                'target_type': nsxlib_const.TARGET_TYPE_LOGICAL_SWITCH,
                const.SCOPE: scope,
                const.TAG: tag}

    def _build_isolation_tags(self, isolation_section, is_isolated):
        return [{const.SCOPE: const.TAG_ISOLATION_SECTION,
                 const.TAG: isolation_section},
                {const.SCOPE: const.TAG_ISOLATED,
                 const.TAG: str(is_isolated)}]

    def _add_isolation_rules(self, project, section_id):
        egress_name = utils.generate_display_name(project, prefix='er')
        egress_rule = self._nsxlib.firewall_section.get_rule_dict(
            display_name=egress_name, direction=nsxlib_const.OUT)
        ingress_name = utils.generate_display_name(project, prefix='ir')
        ingress_rule = self._nsxlib.firewall_section.get_rule_dict(
            display_name=ingress_name, direction=nsxlib_const.IN,
            action=nsxlib_const.FW_ACTION_DROP)
        rules = [ingress_rule, egress_rule]
        try:
            self._nsxlib.firewall_section.add_rules(
                rules=rules, section_id=section_id)
        except nsxlib_exc.ManagerError as e:
            _msg = 'Failed to create isolation rules for project %s: %s' % (
                project, str(e))
            LOG.exception(_msg, security=True)
            raise ncp_exc.ManagerError(
                manager=cfg.CONF.nsx_v3.nsx_api_managers,
                operation='Isolation rules creation', details=_msg)
        # Update projects Logical Router tag to reflect isolation is enabled
        tags = self._build_isolation_tags(section_id,
                                          is_isolated=True)
        self._update_project_router(project, tags_update=tags)

    def _delete_isolation_rules(self, section_id):
        # Retrieve egress and ingress rules for isolation
        rules = self._nsxlib.firewall_section.get_rules(section_id)['results']
        try:
            for rule in rules:
                self._nsxlib.firewall_section.delete_rule(
                    section_id=section_id, rule_id=rule['id'])
        except nsxlib_exc.ManagerError as e:
            _msg = 'Failed to delete isolation rule for section %s: %s' % (
                section_id, str(e))
            LOG.exception(_msg, security=True)
            raise ncp_exc.ManagerError(
                manager=cfg.CONF.nsx_v3.nsx_api_managers,
                operation='Isolation rule deletion', details=_msg)

    def _create_isolation_section(self, project):
        # Create membership criteria for NSGroup to dynamically group all
        # logical switches belonging to project.
        mem_tags = {const.TAG_PROJECT: project,
                    const.TAG_CLUSTER: cfg.CONF.coe.cluster}
        exp = [self._nsxlib.ns_group.get_switch_tag_expression(k, v)
               for k, v in six.iteritems(mem_tags)]
        membership_criteria = (self._nsxlib.ns_group.
                               get_nsgroup_complex_expression(exp))
        # Create NSGroup for project logical switches
        try:
            nsg_name = utils.generate_display_name(project, prefix='ig')
            nsg_tags = self._build_tags(project)
            nsg_project = self._nsxlib.ns_group.create(
                display_name=nsg_name, description='',
                tags=nsg_tags, membership_criteria=membership_criteria)
        except nsxlib_exc.ManagerError as e:
            _msg = 'Failed to create NSGroup for project %s: %s' % (
                project, str(e))
            LOG.exception(_msg, security=True)
            raise ncp_exc.ManagerError(
                manager=cfg.CONF.nsx_v3.nsx_api_managers,
                operation='Isolation section creation', details=_msg)
        # Create Firewall section for isolation and add rules to open
        # egress traffic and block ingress traffic.
        try:
            section_name = utils.generate_display_name(project, prefix='is')
            section_tags = self._build_tags(project)
            # Set default operation to INSERT_BOTTOM to insert the FW section
            # at the bottom of the list if no marker is provided.
            operation = nsxlib_const.FW_INSERT_BOTTOM
            if self._fw_section_marker:
                operation = nsxlib_const.FW_INSERT_BEFORE
            isolation_section = self._nsxlib.firewall_section.create_empty(
                display_name=section_name, description='',
                operation=operation, other_section=self._fw_section_marker,
                applied_tos=[nsg_project['id']], tags=section_tags)
        except nsxlib_exc.ManagerError as e:
            _msg = 'Failed to create isolation section for project %s: %s' % (
                project, str(e))
            LOG.exception(_msg, security=True)
            raise ncp_exc.ManagerError(
                manager=cfg.CONF.nsx_v3.nsx_api_managers,
                operation='Isolation section creation', details=_msg)
        return isolation_section

    def _get_nsg_from_firewall_section(self, section_id):
        fw_section = self._nsxlib.firewall_section.read(
            section_id=section_id)
        applied_to_list = fw_section.get('applied_tos', [])
        # Return list of NSGroup IDs from the firewall section.
        return [nsg['target_id'] for nsg in applied_to_list]

    def _create_dest_grp(self, pod_labels, project, np_name):
        name = utils.generate_display_name(np_name, prefix='dg')
        nsg_tags = self._build_tags(project)
        # Append network policy name to the NSGroup tags
        nsg_tags.append({const.SCOPE: const.TAG_NP,
                         const.TAG: np_name})
        if pod_labels:
            # Add project label to pod expressions
            pod_labels_copy = copy.copy(pod_labels)
            pod_labels_copy[const.TAG_PROJECT] = project
            exp = [self._nsxlib.ns_group.get_port_tag_expression(k, v)
                   for k, v in six.iteritems(pod_labels_copy)]
            mem_criteria = [{'resource_type': const.NSGROUP_COMPLEX_EXP,
                             'expressions': exp}]
        else:
            # Policy should apply to pods in this namespace
            mem_criteria = [self._get_switch_tag_expression(
                const.TAG_PROJECT, project)]
        try:
            dest_nsg = self._nsxlib.ns_group.create(
                display_name=name, description='',
                tags=nsg_tags, membership_criteria=mem_criteria)
        except nsxlib_exc.ManagerError as e:
            _msg = ('Failed to create destination NSGroup for network policy '
                    '%s: %s') % (np_name, str(e))
            LOG.exception(_msg, security=True)
            raise ncp_exc.ManagerError(
                manager=cfg.CONF.nsx_v3.nsx_api_managers,
                operation='Network Policy creation', details=_msg)
        return dest_nsg['id']

    def enable_project_isolation(self, project):
        """Create namespace isolation rules."""
        project_nsx_mapping = self._mapping.get(
            project, parent_key=const.PROJECT) or {}
        if not project_nsx_mapping:
            LOG.warning('No logical switch is mapped to project %s', project)
            return
        project_isolation = project_nsx_mapping.get('isolation')
        isolation_section_id = project_isolation.get(
            'isolation_section_id')
        if not isolation_section_id:
            # If isolation firewall section does no exist for this
            # project, create new firewall sections and update the cache.
            isolation_section = self._create_isolation_section(project)
            isolation_section_id = isolation_section['id']
        # Build isolation rules which comprise of a ALLOW egress rule and
        # a DENY ingress rule.
        self._add_isolation_rules(project, isolation_section_id)
        # Tag Tier-1 Logical router for this project with the isolation
        # section ID and isolation status in order to be able to rebuild
        # cache.
        tags = self._build_isolation_tags(isolation_section_id,
                                          is_isolated=True)
        self._update_project_router(project, tags_update=tags)
        # Update cache
        project_isolation['isolation_section_id'] = isolation_section_id
        project_isolation['is_isolated'] = True
        self._mapping.insert(project, project_nsx_mapping,
                             parent_key=const.PROJECT)

    def disable_project_isolation(self, project):
        """Disable namespace isolation rules."""
        project_nsx_mapping = self._mapping.get(
            project, parent_key=const.PROJECT) or {}
        if not project_nsx_mapping:
            LOG.warning('No logical switch is mapped to project %s', project)
            return
        project_isolation = project_nsx_mapping.get('isolation')
        isolation_section_id = project_isolation.get(
            'isolation_section_id')
        self._delete_isolation_rules(isolation_section_id)
        # Tag Tier-1 Logical router for this project with the isolation
        # section ID and isolation status in order to be able to rebuild
        # cache.
        tags = self._build_isolation_tags(isolation_section_id,
                                          is_isolated=False)
        self._update_project_router(project, tags_update=tags)
        # Update cache
        project_isolation['is_isolated'] = False
        self._mapping.insert(project, project_nsx_mapping,
                             parent_key=const.PROJECT)

    def delete_project_isolation(self, project):
        """Delete namespace isolation rules."""
        project_nsx_mapping = self._mapping.get(
            project, parent_key=const.PROJECT) or {}
        if not project_nsx_mapping:
            LOG.warning('No logical switch is mapped to project %s', project)
            return
        project_isolation = project_nsx_mapping.get('isolation')
        isolation_section_id = project_isolation.get('isolation_section_id')
        if not isolation_section_id:
            LOG.warning('No isolation section is mapped to project %s',
                        project)
            return
        try:
            # Retrieve isolation section from backend to delete
            # associated NSGroups.
            nsg_project_list = self._get_nsg_from_firewall_section(
                isolation_section_id)
            # Delete firewall section
            self._nsxlib.firewall_section.delete(isolation_section_id)
        except nsxlib_exc.ManagerError as e:
            _msg = ('Failed to delete isolation section %s for project %s: %s'
                    ) % (isolation_section_id, project, str(e))
            LOG.exception(_msg, security=True)
            raise ncp_exc.ManagerError(
                 manager=cfg.CONF.nsx_v3.nsx_api_managers,
                 operation='Isolation section deletion', details=_msg)
        # There must be only one isolation related NSGroup for each project
        if len(nsg_project_list) != 1:
            _msg = "%d NSGroups found for project %s" % (
                len(nsg_project_list), project)
            raise ncp_exc.ManagerError(
                manager=cfg.CONF.nsx_v3.nsx_api_managers,
                operation='Isolation section deletion',
                details=_msg)
        nsg_id = nsg_project_list[0]
        # Delete NSGroups associated with this project.
        try:
            self._nsxlib.ns_group.delete(nsg_id)
        except nsxlib_exc.ManagerError as e:
            _msg = 'Failed to delete NSGroup %s for project %s: %s' % (
                nsg_id, project, str(e))
            LOG.exception(_msg, security=True)
            raise ncp_exc.ManagerError(
                manager=cfg.CONF.nsx_v3.nsx_api_managers,
                operation='Isolation section deletion',
                details=_msg)

    def _build_ns_service_body(self, protocol=None, port=None):
        dest_ports = [port] if port else []
        return self._nsxlib.firewall_section.get_nsservice(
            nsxlib_const.L4_PORT_SET_NSSERVICE,
            l4_protocol=protocol,
            source_ports=[],
            destination_ports=dest_ports)

    def _build_membership_criteria(self, label_selector, project):
        if const.POD_SELECTOR in label_selector:
            labels = copy.copy(label_selector[const.POD_SELECTOR].
                               get('matchLabels'))
            if labels:
                # Add cluster and project labels to pod expressions
                labels[const.TAG_PROJECT] = project
                exp = [self._nsxlib.ns_group.get_port_tag_expression(k, v)
                       for k, v in six.iteritems(labels)]
                return [{'resource_type': const.NSGROUP_COMPLEX_EXP,
                         'expressions': exp}]
            # Empty podSelector criteria must select all pods belonging
            # to this project.
            return [self._get_switch_tag_expression(const.TAG_PROJECT,
                                                    project)]
        if const.NS_SELECTOR in label_selector:
            labels = copy.copy(label_selector[const.NS_SELECTOR].
                               get('matchLabels'))
            if not labels:
                # Empty namespaceSelector must select all namespaces
                return []
            return [self._nsxlib.ns_group.get_switch_tag_expression(k, v)
                    for k, v in six.iteritems(labels)]

    def _build_ip_set_tags(self, tags, rule_from):
        for label_selector in rule_from:
            if const.POD_SELECTOR in label_selector:
                labels = label_selector[const.POD_SELECTOR].get('matchLabels',
                                                                {})
                for key, value in six.iteritems(labels):
                    tags.append({const.SCOPE: key, const.TAG: value})
        return tags

    def _build_src_pod_ips(self, project, rule_from, np_name):
        np_key = utils.get_resource_key(project, np_name)
        np_mapping = self._mapping.get(
            np_key, parent_key=const.NETWORK_POLICY)
        if not np_mapping:
            _msg = ("Network policy %s cache not found for project "
                    "%s. Failed to update cache for source host "
                    "network pods.") % (np_name, project)
            raise ncp_exc.NsxPluginException(err_msg=_msg)
        pods = []
        for label_selector in rule_from:
            if const.POD_SELECTOR in label_selector:
                labels = label_selector[const.POD_SELECTOR].get('matchLabels',
                                                                {})
                pod_keys, pod_ips = self._get_host_network_pods(
                    project, labels)
                np_mapping['src_pods'] += pod_keys
                pods += pod_ips
        # Update network policy cache to reflect affected source
        # host network pods.
        self._mapping.insert(np_key, np_mapping,
                             parent_key=const.NETWORK_POLICY)
        return pods

    def _build_firewall_rule(self, np_name, project, rule, dest_nsg,
                             rule_enabled, rule_count):
        nsg_tags = self._build_tags(project)
        # Append network policy name to the NSGroup tags
        nsg_tags.append({const.SCOPE: const.TAG_NP,
                         const.TAG: np_name})
        # Build list of Firewall Services for each <port, protocol> pair
        # specified in ingress rules.
        rule_ports = rule.get('ports', [])
        ns_services = []
        for rule_port in rule_ports:
            # Default protocol assumed by k8s network policies is TCP
            protocol = rule_port.get('protocol', nsxlib_const.TCP)
            # Retrieve protocol name for NSX backend request
            nsx_protocol = const.NSX_PROTOCOL_MAP.get(str(protocol).lower())
            if not nsx_protocol:
                _msg = ("Failed to create firewall rule for network policy %s "
                        ". Unsupported protocol %s") % (np_name, protocol)
                raise ncp_exc.InvalidInput(error_message=_msg)
            port = rule_port.get('port')
            ns_services.append(self._build_ns_service_body(
                protocol=nsx_protocol,
                port=port))
        # Build Source NSGroups for each pod/namespace selector specified
        # in ingress rules.
        rule_from = rule.get('from', [])
        mem_criterias = []
        source = []
        for label_selector in rule_from:
            mem_criterias += self._build_membership_criteria(label_selector,
                                                             project)
        if mem_criterias:
            # Create source NSGroup
            name = utils.generate_display_name(np_name, count=rule_count,
                                               prefix='sg')
            try:
                src_nsg = self._nsxlib.ns_group.create(
                    display_name=name, description='',
                    tags=nsg_tags, membership_criteria=mem_criterias)
            except nsxlib_exc.ManagerError as e:
                _msg = ('Failed to create source NSGroup for network policy '
                        '%s: %s') % (np_name, str(e))
                LOG.exception(_msg, security=True)
                raise ncp_exc.ManagerError(
                    manager=cfg.CONF.nsx_v3.nsx_api_managers,
                    operation='Network Policy creation', details=_msg)
            source = [(self._nsxlib.firewall_section.
                       get_nsgroup_reference(src_nsg['id']))]
            ip_set_name = utils.generate_display_name(
                np_name, count=rule_count, prefix='si')
            src_pod_ips = self._build_src_pod_ips(project, rule_from, np_name)
            ip_set_tags = self._build_ip_set_tags(nsg_tags, rule_from)
            try:
                src_ip_set = self._nsxlib.ip_set.create(
                    display_name=ip_set_name,
                    ip_addresses=list(set(src_pod_ips)),
                    tags=ip_set_tags)
            except nsxlib_exc.ManagerError as e:
                _msg = ('Source IPSet creation for network policy '
                        '%s failed: %s ') % (np_name, str(e))
                LOG.exception(_msg)
                raise ncp_exc.ManagerError(
                    manager=cfg.CONF.nsx_v3.nsx_api_managers,
                    operation='Network Policy creation', details=_msg)
            # Add IPSet to source for host network pods
            source.append(self._nsxlib.ip_set.
                          get_ipset_reference(src_ip_set['id']))
        rule_name = utils.generate_display_name(np_name, count=rule_count,
                                                prefix='r')
        disabled = not rule_enabled
        # Build destination NSGroup target
        destination = [(self._nsxlib.firewall_section.
                        get_nsgroup_reference(dest_nsg))]
        return self._nsxlib.firewall_section.get_rule_dict(
            display_name=rule_name, sources=source,
            destinations=destination, direction=nsxlib_const.IN,
            services=ns_services, disabled=disabled,
            applied_tos=destination)

    def _create_firewall_rules(self, np_name, project, section, dest_nsg,
                               rules, rules_enabled):
        if rules is None:
            LOG.debug("No rules specified for network policy %s", np_name)
            return
        fw_rules = []
        # Use count for rule and NSGroup name
        count = 1
        for rule in rules:
            fw_rule = self._build_firewall_rule(
                np_name=np_name, project=project, dest_nsg=dest_nsg, rule=rule,
                rule_enabled=rules_enabled, rule_count=count)
            fw_rules.append(fw_rule)
            count += 1
        try:
            return self._nsxlib.firewall_section.add_rules(fw_rules, section)
        except nsxlib_exc.ManagerError as e:
            _msg = ('Failed to create firewall rules for network policy '
                    '%s: %s') % (np_name, str(e))
            LOG.exception(_msg, security=True)
            raise ncp_exc.ManagerError(
                manager=cfg.CONF.nsx_v3.nsx_api_managers,
                operation='Firewall rules creation', details=_msg)

    def _search_fw_section(self, np_name, project):
        # Search backend to retrieve the firewall section ID associated
        # with this network policy
        tags = nsxlib_utils.add_v3_tag(
            [],
            ncp_utils.escape_data(const.TAG_CLUSTER),
            ncp_utils.escape_data(cfg.CONF.coe.cluster))
        tags = nsxlib_utils.add_v3_tag(
            tags,
            ncp_utils.escape_data(const.TAG_NP),
            ncp_utils.escape_data(np_name))
        tags = nsxlib_utils.add_v3_tag(
            tags,
            ncp_utils.escape_data(const.TAG_PROJECT),
            ncp_utils.escape_data(project))
        # Restrict query scope to resources of type FirewallSection
        firewall_sections = self._nsxlib.search_by_tags(
            resource_type=const.FIREWALL_SECTION, tags=tags)
        if firewall_sections['result_count'] != 1:
            # More than one firewall section found for a given network policy
            LOG.error("%s firewall section(s) found for given network policy "
                      "%s", str(firewall_sections['result_count']), np_name,
                      security=True)
            return
        return firewall_sections['results'][0]

    def _search_ip_sets(self, np_name, project, labels=None):
        # Build query tags
        tags = nsxlib_utils.add_v3_tag(
            [], ncp_utils.escape_data(const.TAG_CLUSTER),
            ncp_utils.escape_data(cfg.CONF.coe.cluster))
        tags = nsxlib_utils.add_v3_tag(
            tags,
            ncp_utils.escape_data(const.TAG_NP),
            ncp_utils.escape_data(np_name))
        tags = nsxlib_utils.add_v3_tag(
            tags,
            ncp_utils.escape_data(const.TAG_PROJECT),
            ncp_utils.escape_data(project))
        labels = labels or {}
        for key, value in six.iteritems(labels):
            tags.append({const.SCOPE: key, const.TAG: value})
        # Search backend to retrieve the IPSet associated
        # with this network policy and tags.
        ip_sets = self._nsxlib.search_by_tags(
            resource_type=nsxlib_const.IP_SET, tags=tags)
        if not ip_sets['result_count']:
            # No IPSet found for a given network policy
            LOG.warning("No IPSet found for network policy %s under "
                        "project %s", np_name, project)
            return []
        return ip_sets['results']

    def _update_rules_status(self, section_id, disabled, tags):
        rules = self._nsxlib.firewall_section.get_rules(section_id)['results']
        # Update section tag to the new status of rules
        tags_update = [{const.SCOPE: const.TAG_FW_SECTION_ENABLED,
                        const.TAG: str(not disabled)}]
        disabled = str(disabled)
        for rule in rules:
            rule['disabled'] = disabled
        return self._nsxlib.firewall_section.update(
            section_id, rules=rules, tags_update=tags_update)

    def get_network_policies_cache(self, project):
        np_cache = self._mapping.get_all(parent_key=const.NETWORK_POLICY)
        return [np for np in np_cache.values() if np['ns_name'] == project]

    def get_network_policy_cache(self, project, np_name):
        np_key = utils.get_resource_key(project, np_name)
        np_mapping = self._mapping.get(np_key, parent_key=const.NETWORK_POLICY)
        if not np_mapping:
            LOG.debug("Network policy %s not found for project %s in cache.",
                      np_name, project)
        return np_mapping

    def _add_network_policy_cache(self, project, np_name, dest_pod_labels,
                                  rules):
        np_mapping = self.get_network_policy_cache(project, np_name)
        if np_mapping:
            LOG.debug("Network policy %s for project %s is already added "
                      "in cache.", np_name, project)
            return
        np_key = utils.get_resource_key(project, np_name)
        np_info = {}
        np_info['dest_labels'] = dest_pod_labels
        np_info['src_rules'] = rules
        np_info['ns_name'] = project
        np_info['name'] = np_name
        # Source pods shall store only affected host network pod names
        # for now.
        np_info['src_pods'] = []
        self._mapping.insert(np_key, np_info,
                             parent_key=const.NETWORK_POLICY)
        LOG.debug("Network policy %s for project %s inserted in cache.",
                  np_name, project)

    def _update_network_policy_cache(self, project, np_name, pod, action):
        np_mapping = self.get_network_policy_cache(project, np_name)
        if not np_mapping:
            _msg = ("Network policy %s cache not found for project "
                    "%s. Failed to update cache for source host "
                    "network pod %s.") % (np_name, project, pod)
            raise ncp_exc.NsxPluginException(err_msg=_msg)
        np_key = utils.get_resource_key(project, np_name)
        pod_key = utils.get_resource_key(project, pod)
        if action in [const.ADDED, const.MODIFIED]:
            np_mapping['src_pods'].append(pod_key)
        else:
            try:
                np_mapping['src_pods'].remove(pod_key)
            except ValueError:
                LOG.error("Missing pod key %s from network policy %s "
                          "under project %s", pod_key, np_name, project)
                return
        # Make sure to eliminate duplicates src pods before updating cache
        np_mapping['src_pods'] = list(set(np_mapping['src_pods']))
        self._mapping.insert(np_key, np_mapping,
                             parent_key=const.NETWORK_POLICY)
        LOG.debug("Network policy %s for project %s updated for pod %s.",
                  np_name, project, pod)

    def _delete_network_policy_cache(self, project, np_name):
        np_key = utils.get_resource_key(project, np_name)
        np_mapping = self._mapping.get(
            np_key, parent_key=const.NETWORK_POLICY)
        if not np_mapping:
            LOG.error("Network policy %s for project %s not found in "
                      "cache.", np_name, project)
            return
        self._mapping.delete(np_key, parent_key=const.NETWORK_POLICY)
        LOG.debug("Network policy %s for project %s deleted from cache.",
                  np_name, project)

    def create_network_policy(self, np_name, project, rules=None,
                              dest_pod_labels=None):
        """Create network policy and rules for a given namespace."""
        proj_nsx_mapping = self._create_project_upon_cache_miss(project)

        # Update network policy cache
        self._add_network_policy_cache(
            project=project, np_name=np_name,
            dest_pod_labels=dest_pod_labels, rules=rules)
        np_enabled = proj_nsx_mapping.get(np_name)
        # Since we store a boolean value is_enabled in cache, verify whether
        # the value retrieved from cache is of type bool. If yes, do nothing
        # as network policy was already created.
        if isinstance(np_enabled, bool):
            LOG.debug('Network policy %s for project %s already exists on '
                      'the backend', np_name, project)
            return
        # Retrieve isolation section ID for the namespace to create the
        # network policy section on top of it.
        project_isolation = proj_nsx_mapping.get('isolation')
        if not project_isolation:
            LOG.error('Failed to create network policy %s because isolation '
                      'section for project %s is missing', np_name, project,
                      security=True)
            # Clean up cache since network policy failed to create
            self._delete_network_policy_cache(project=project,
                                              np_name=np_name)
            return
        isolation_section_id = project_isolation.get(
            'isolation_section_id')
        # Create corresponding firewall section for network policy on
        # top of project's isolation section.
        try:
            section_name = utils.generate_display_name(np_name)
            np_tag_dict = {'name': np_name, 'is_enabled': True}
            section_tags = self._build_tags(
                project, network_policy=np_tag_dict)
            np_section = self._nsxlib.firewall_section.create_empty(
                display_name=section_name, description='',
                applied_tos=[], operation=nsxlib_const.FW_INSERT_BEFORE,
                other_section=isolation_section_id,
                tags=section_tags)
        except nsxlib_exc.ManagerError as e:
            _msg = ('Failed to create firewall section for network policy %s '
                    'in project %s: %s') % (np_name, project, str(e))
            LOG.exception(_msg, security=True)
            self._delete_network_policy_cache(project=project,
                                              np_name=np_name)
            raise ncp_exc.ManagerError(
                manager=cfg.CONF.nsx_v3.nsx_api_managers,
                operation='Network policy creation', details=_msg)
        dest_pod_labels = dest_pod_labels or {}
        # TODO(abhiraut): Make use of @rollback_if_exception for network
        #                 policy CRUD operations.
        # Create destination NSGroup and IPSet based on podLabelSelector
        dest_nsg = self._create_dest_grp(
            project=project, pod_labels=dest_pod_labels, np_name=np_name)
        # Create firewall rules for the network policy
        try:
            self._create_firewall_rules(np_name=np_name, rules=rules,
                                        section=np_section['id'],
                                        rules_enabled=True,
                                        project=project, dest_nsg=dest_nsg)
        except (nsxlib_exc.ManagerError, ncp_exc.InvalidInput) as e:
            _msg = ('Failed to create firewall rules for network policy %s '
                    'in project %s: %s') % (np_name, project, str(e))
            LOG.exception(_msg, security=True)
            # Clean up resources
            self._nsxlib.firewall_section.delete(np_section['id'])
            self._nsxlib.ns_group.delete(dest_nsg)
            self._delete_network_policy_cache(project=project,
                                              np_name=np_name)
            raise ncp_exc.ManagerError(
                manager=cfg.CONF.nsx_v3.nsx_api_managers,
                operation='Network policy creation', details=_msg)
        # Update cache
        proj_nsx_mapping[np_name] = True
        self._mapping.insert(project, proj_nsx_mapping,
                             parent_key=const.PROJECT)

    def set_network_policy(self, np_name, project, rules_enabled):
        # Retrieve project cache
        proj_nsx_mapping = self._mapping.get(project, parent_key=const.PROJECT)
        if not proj_nsx_mapping:
            LOG.error('Failed to update rule status for network policy %s '
                      'due to no mapping found for project %s', np_name,
                      project, security=True)
            return
        # Retrieve network policy's previous rule_enabled status
        old_rules_enabled = proj_nsx_mapping.get(np_name)
        # Return if there is no change in rule status.
        if old_rules_enabled == rules_enabled:
            LOG.debug('Rule status unchanged in network policy %s for project '
                      '%s', np_name, project)
            return
        np_section = self._search_fw_section(np_name, project)
        if not np_section:
            # Multiple or no section were found for the given network policy
            # Return since error has been logged.
            return
        # Update firewall section DFW rules status
        try:
            self._update_rules_status(np_section['id'],
                                      disabled=(not rules_enabled),
                                      tags=np_section['tags'])
        except nsxlib_exc.ManagerError as e:
            _msg = ('Failed to update rule status in firewall section %s '
                    'for network policy %s in project %s: %s') % (
                np_section['id'], np_name, project, str(e))
            LOG.exception(_msg, security=True)
            raise ncp_exc.ManagerError(
                 manager=cfg.CONF.nsx_v3.nsx_api_managers,
                 operation='Set network policy', details=_msg)
        # Update cache
        proj_nsx_mapping[np_name] = rules_enabled
        self._mapping.insert(project, proj_nsx_mapping,
                             parent_key=const.PROJECT)

    def delete_network_policy(self, np_name, project):
        """Delete network policy related sections and rules."""
        section = self._search_fw_section(np_name, project)
        if not section:
            # Multiple or no section were found for the given network policy
            # Return since error has been logged.
            return
        try:
            self._nsxlib.firewall_section.delete(section['id'])
        except nsxlib_exc.ManagerError as e:
            _msg = ('Failed to delete firewall section %s for project '
                    '%s: %s') % (section['id'], project, str(e))
            LOG.exception(_msg, security=True)
            raise ncp_exc.ManagerError(
                 manager=cfg.CONF.nsx_v3.nsx_api_managers,
                 operation='Network policy section deletion', details=_msg)
        # Search backend to retrieve NSGroups associated with this network
        # policy
        nsg_tags = nsxlib_utils.add_v3_tag(
            [],
            ncp_utils.escape_data(const.TAG_NP),
            ncp_utils.escape_data(np_name))
        nsg_tags = nsxlib_utils.add_v3_tag(
            nsg_tags,
            ncp_utils.escape_data(const.TAG_PROJECT),
            ncp_utils.escape_data(project))
        # Restrict query scope to resources of type NSGroup
        ns_groups = self._nsxlib.search_by_tags(
            resource_type=nsxlib_const.NSGROUP, tags=nsg_tags)['results']
        for nsg in ns_groups:
            try:
                self._nsxlib.ns_group.delete(nsg['id'])
            except nsxlib_exc.ManagerError as e:
                _msg = 'Failed to delete NSGroup %s for project %s: %s' % (
                    nsg['id'], project, str(e))
                LOG.exception(_msg, security=True)
                raise ncp_exc.ManagerError(
                     manager=cfg.CONF.nsx_v3.nsx_api_managers,
                     operation='Network policy NSGroup deletion', details=_msg)
        # Search backend to retrieve IPSets associated with this network
        # policy
        # Restrict query scope to resources of type NSGroup
        ip_sets = self._nsxlib.search_by_tags(
            resource_type=nsxlib_const.IP_SET, tags=nsg_tags)['results']
        for ip_set in ip_sets:
            try:
                self._nsxlib.ip_set.delete(ip_set['id'])
            except nsxlib_exc.ManagerError as e:
                _msg = ('IPSet: %s delete failed for the project %s. '
                        'Reason: %s ') % (ip_set['id'], project, str(e))
                LOG.exception(_msg)
                raise ncp_exc.ManagerError(
                     manager=cfg.CONF.nsx_v3.nsx_api_managers,
                     operation='Network policy IPSet deletion', details=_msg)
        proj_nsx_mapping = self._mapping.get(project, parent_key=const.PROJECT)
        if not proj_nsx_mapping:
            LOG.error('Failed to delete network policy %s due to no mapping '
                      'found for project %s', np_name, project, security=True)
            return
        # Remove network policy info from cache and update project cache
        proj_nsx_mapping.pop(np_name)
        self._mapping.insert(project, proj_nsx_mapping,
                             parent_key=const.PROJECT)
        self._delete_network_policy_cache(project=project,
                                          np_name=np_name)

    def update_ip_set_for_np(self, np_name, project, pod_ip, action, labels,
                             pod):
        # Search IPSets matching policy with required labels.
        ip_sets = self._search_ip_sets(np_name, project, labels)
        for ip_set in ip_sets:
            ip_addresses = ip_set.get('ip_addresses', [])
            if action in [const.ADDED, const.MODIFIED]:
                if pod_ip in ip_addresses:
                    # Pods IP is already in IPSet. Move to next IPSet.
                    continue
                ip_addresses.append(pod_ip)
                self._update_ip_set(ip_set['id'], ip_addresses,
                                    np_name, project)
            elif action == const.DELETED:
                if pod_ip not in ip_addresses:
                    # Pods IP is already not in IPSet. Move to next IPSet,
                    continue
                ip_addresses.remove(pod_ip)
                self._update_ip_set(ip_set['id'], ip_addresses,
                                    np_name, project)
        # Update network policy cache
        self._update_network_policy_cache(project, np_name, pod, action)

    def _update_ip_set(self, ip_set_id, ip_addresses, np_name, project):
        try:
            return self._nsxlib.ip_set.update(
                ip_set_id, ip_addresses=ip_addresses)
        except nsxlib_exc.ManagerError as e:
            _msg = ('IPSet: %s update failed for the network policy '
                    '%s under project %s. Reason: %s ') % (
                       ip_set_id, np_name, project, str(e))
            LOG.exception(_msg)
            raise ncp_exc.ManagerError(
                manager=cfg.CONF.nsx_v3.nsx_api_managers,
                operation='_update_ip_set', details=_msg)

    def _decremental_search_by_tags(self, resource_type, tags):
        """Search resource by reducing tag one at a time until found."""
        tag_list = tags[:]  # make a copy
        while tag_list:
            results = self._nsxlib.search_by_tags(
                resource_type=resource_type, tags=tag_list)
            if results['result_count']:
                return results['results']
            tag = tag_list.pop()
            LOG.debug("Dropping tag (%s: %s) while searching %s",
                      tag['scope'], tag['tag'], resource_type)

    def get_node_logical_port(self, node_name):
        """Retrieve the logical port for a node

        This method assumes that a node's logical port has been tagged with
        the name of the node itself. For instance:

            ncp/node_name: kubelet-node-99

        and an optional tag for the cluster, such as:

            ncp/cluster: k8scluster

        :param node_name: Container orchestrator specific name for the node
        :type node_name: String
        :return: the logical port with a ncp/node_name tag whose
                 value matches the node_name parameter

        :raises: nsx_ujo.common.exceptions.ManagerError if the backend
                 query fails;
                 nsx_ujo.common.exceptions.ResourceNotFound if not logical
                 port matched the tag;
                 nsx_ujo.common.exceptions.MultipleResources if multiple
                 logical ports matched the tag.
        """
        desired_tags = [{'scope': ncp_utils.escape_data(const.TAG_NODE_NAME),
                         'tag': ncp_utils.escape_data(node_name)},
                        {'scope': ncp_utils.escape_data(const.TAG_CLUSTER),
                         'tag': ncp_utils.escape_data(cfg.CONF.coe.cluster)}]
        try:
            logical_ports = self._decremental_search_by_tags(
                resource_type=const.LOGICAL_PORT, tags=desired_tags)
        except nsxlib_exc.ManagerError as e:
            msg = ("Unable to execute search query for node %s on NSX "
                   "backend: %s") % (node_name, str(e))
            LOG.error(msg)
            raise ncp_exc.ManagerError(
                operation='get_node_logical_ports',
                details=msg)

        if not logical_ports:
            LOG.warning("No logical port found for node %s", node_name)
            raise ncp_exc.ResourceNotFound(
                manager='', operation='search LogicalPort')
        elif len(logical_ports) > 1:
            LOG.warning("Found %d logical ports for node %s",
                        len(logical_ports), node_name)
            raise ncp_exc.MultipleResourcesFound(
                manager='', operation='search LogicalPort')
        return logical_ports[0]

    def add_node_vif_cache(self, node_name, vif):
        self._mapping.insert(node_name, vif, parent_key=const.VIF)

    def delete_node_vif_cache(self, node_name):
        if self._mapping.get(node_name, parent_key=const.VIF):
            self._mapping.delete(node_name, parent_key=const.VIF)

    def get_node_vif_id(self, node_name):
        """Get the VIF id for a node

        :param node_name: Container orchestrator specific name for the node
        :type node_name: String
        :return: the vif id for the logical port with a ncp/node_name tag
                 whose value matches the node_name parameter
        """
        vif_id = self._mapping.get(node_name, parent_key=const.VIF)
        if not vif_id:
            vif_id = self._get_node_vif_id(node_name)
            self.add_node_vif_cache(node_name, vif_id)
        return vif_id

    def _get_node_vif_id(self, node_name):
        logical_port = self.get_node_logical_port(node_name)

        attachment = logical_port[const.ATTACHMENT]
        if not attachment:
            msg = ("Missing attachment on logical port %s for node %s. "
                   "Verify NSX configuration" %
                   (logical_port['id'], node_name))
            LOG.error(msg)
            raise ncp_exc.ManagerError(
                operation='get_node_vif_id', details='msg')

        if attachment[const.ATTACHMENT_TYPE] != const.ATTACHMENT_VIF:
            msg = ("Invalid attachment type (%s vs VIF) on logical port %s "
                   "for node %s. Verify NSX configuration") % (
                attachment[const.ATTACHMENT_TYPE], logical_port['id'],
                node_name)
            LOG.error(msg)
            raise ncp_exc.ManagerError(
                operation='get_node_vif_id', details='msg')

        # VIF ID is good, return it
        LOG.debug("Found VIF %s for node %s", attachment['id'], node_name,
                  security=True)
        return attachment['id']

    def _add_health_check_rule_to_port(self, pod_ip, port_uuid, node_ip,
                                       hc_ports):
        # Generate firewall rules
        node_address = self._nsxlib.firewall_section.get_rule_address(
            node_ip, display_name=node_ip)
        pod_address = self._nsxlib.firewall_section.get_rule_address(
            pod_ip, display_name=pod_ip)
        services = []
        for port_dict in hc_ports:
            host_port = port_dict.get('host_port')
            service = self._nsxlib.firewall_section.get_l4portset_nsservice(
                sources=[host_port] if host_port else [],
                destinations=[port_dict['container_port']])
            services.append(service)
        rule = self._nsxlib.firewall_section.get_rule_dict(
            display_name=utils.generate_display_name(port_uuid,
                                                     prefix='ir'),
            sources=[node_address],
            destinations=[pod_address], direction=nsxlib_const.IN_OUT,
            services=services)

        # Create firewall section with rules
        section_name = utils.generate_display_name(port_uuid, prefix='hc-lp')
        applied_tos = [self._nsxlib.firewall_section.get_logicalport_reference(
                       port_uuid)]
        try:
            # Health check rule need higher priority than network policy rules
            hc_section = self._nsxlib.firewall_section.create_with_rules(
                section_name, 'Health Check Section', applied_tos,
                operation=nsxlib_const.FW_INSERT_TOP, rules=[rule])
            LOG.info("Created health check firewall section %s for port %s",
                     hc_section['id'], port_uuid, security=True)
            return hc_section['id']
        except nsxlib_exc.ManagerError as e:
            _msg = 'Failed to create health check section for port %s: %s' % (
                port_uuid, str(e))
            LOG.exception(_msg, security=True)
            raise ncp_exc.ManagerError(
                manager=cfg.CONF.nsx_v3.nsx_api_managers,
                operation='Health check section creation', details=_msg)

    def _delete_health_check_rule(self, section_id):
        try:
            self._nsxlib.firewall_section.delete(section_id)
            LOG.info("Deleted health check firewall section %s", section_id,
                     security=True)
        except nsxlib_exc.ManagerError as e:
            _msg = 'Failed to delete health check firewall section %s: %s' % (
                section_id, str(e))
            LOG.exception(_msg, security=True)
            raise nsxlib_exc.ManagerError(
                manager=cfg.CONF.nsx_v3.nsx_api_managers,
                operation='Health check firewall section deletion',
                details=_msg)
