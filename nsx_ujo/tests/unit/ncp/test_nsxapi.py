#******************************************************************************
# Copyright (c) 2016-2017 VMware, Inc. All rights reserved.VMware Confidential.
#******************************************************************************

import contextlib
import unittest

import mock
import netaddr
from oslo_config import cfg
from vmware_nsxlib.v3 import exceptions as nsxlib_exc

from nsx_ujo.common import constants as const
from nsx_ujo.common import exceptions as ncp_exc
from nsx_ujo.common import utils
from nsx_ujo.ncp import nsxapi
from nsx_ujo.ncp import utils as ncp_utils

FAKE_PROJECT = 'fake_proj'
FAKE_POD = 'fake_pod'
FAKE_OVERLAY_TZ_ID = 'fake_overlay_tz_id'
FAKE_EXTERNAL_IP_POOL_ID = 'fake_ext_ip_pool_id'
FAKE_TIER0_ROUTER_ID = 'fake_tier0_router_id'
FAKE_TIER1_ROUTER_ID = 'fake_tier1_router_id'
FAKE_EDGE_CLUSTER_ID = 'fake_edge_cluster_id'
FAKE_SWITCH_ID = 'fake_switch_id'
FAKE_CIDR = '192.168.0.0/24'
FAKE_SUBNET_ID = 'fake_subnet_id'
FAKE_PORT_ID = 'fake_port_id'
FAKE_IP_POOL_ID = 'fake_ip_pool_id'
FAKE_IP_BLOCK_ID = 'fake_ip_block_id'
FAKE_HC_SECTION_ID = 'fake_hc_section_id'
FAKE_VIF_ID = 'fake_vif_id'
FAKE_NODE_NAME = 'fake_node_name'


class TestNSXAPI(unittest.TestCase):

    def setUp(self):
        # NOTE(qtian): To avoid the effects of Singleton
        ncp_utils.Singleton._instances = {}

        get_nsx_client_p = mock.patch(
            'nsx_ujo.ncp.utils.NSXLibHolder.get_nsx_client')
        get_nsx_client_p.start()
        self.addCleanup(get_nsx_client_p.stop)

        logical_router_cls_p = mock.patch(
            'vmware_nsxlib.v3.resources.LogicalRouter')
        logical_router_cls = logical_router_cls_p.start()
        self.mock_router_client = mock.MagicMock()
        logical_router_cls.return_value = self.mock_router_client
        self.addCleanup(logical_router_cls_p.stop)

        logical_port_cls_p = mock.patch(
            'vmware_nsxlib.v3.resources.LogicalPort')
        logical_port_cls = logical_port_cls_p.start()
        self.mock_port_client = mock.MagicMock()
        logical_port_cls.return_value = self.mock_port_client
        self.addCleanup(logical_port_cls_p.stop)

        logical_router_port_cls_p = mock.patch(
            'vmware_nsxlib.v3.resources.LogicalRouterPort')
        logical_router_port_cls = logical_router_port_cls_p.start()
        self.mock_router_port_client = mock.MagicMock()
        logical_router_port_cls.return_value = self.mock_router_port_client
        self.addCleanup(logical_router_port_cls_p.stop)

        ip_pool_cls_p = mock.patch('vmware_nsxlib.v3.resources.IpPool')
        ip_pool_cls = ip_pool_cls_p.start()
        self.mock_ip_pool_client = mock.MagicMock()
        ip_pool_cls.return_value = self.mock_ip_pool_client
        self.addCleanup(ip_pool_cls_p.stop)

        nsx_lib_cls_p = mock.patch(
            'nsx_ujo.ncp.utils.NSXLibHolder.get_nsxlib')
        nsx_lib_cls = nsx_lib_cls_p.start()
        self.mock_nsx_lib = mock.MagicMock()
        nsx_lib_cls.return_value = self.mock_nsx_lib
        self.addCleanup(nsx_lib_cls_p.stop)

        mapping_init_p = mock.patch(
            'nsx_ujo.ncp.cache.CoeNSXMapping._initialize_cache')
        mapping_init_p.start()
        self.addCleanup(mapping_init_p.stop)

        router_lib_cls_p = mock.patch('vmware_nsxlib.v3.router.RouterLib')
        router_lib_cls = router_lib_cls_p.start()
        self.mock_router_lib = mock.MagicMock()
        router_lib_cls.return_value = self.mock_router_lib
        self.addCleanup(router_lib_cls_p.stop)

    @contextlib.contextmanager
    def _get_patched_nsx_api(self):
        with mock.patch.object(utils,
            'get_tier0_router_id') as mock_get_tier0_router_id,\
            mock.patch.object(utils,
                'get_overlay_tz_id') as mock_get_overlay_tz_id,\
            mock.patch.object(utils,
                'get_fw_section_marker_id') as mock_get_fw_marker:
            mock_get_tier0_router_id.return_value = FAKE_TIER0_ROUTER_ID
            mock_get_overlay_tz_id.return_value = FAKE_OVERLAY_TZ_ID
            mock_get_fw_marker.return_value = None
            yield nsxapi.NSXAPI()

    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._create_project')
    @mock.patch('oslo_concurrency.lockutils.lock')
    def test_create_project_grabs_lock(self, mock_lock,
                                       mock_create_project):
        with self._get_patched_nsx_api() as napi:
            napi.create_project(FAKE_PROJECT)
            lock_name = 'project-lock-%s' % FAKE_PROJECT
            mock_lock.assert_called_once_with(lock_name)

    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._allocate_snat_ip')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._create_logical_switch')
    def _test_create_project_if_not_exist(self,
                                          mock_create_logical_switch,
                                          mock_allocate_snat_ip,
                                          do_snat):
        mock_allocate_snat_ip.return_value = {
            'allocation_id': '10.10.10.10',
            'ip_pool_id': FAKE_EXTERNAL_IP_POOL_ID
        }
        self.mock_router_client.create.return_value = {
            'id': FAKE_TIER1_ROUTER_ID
        }

        def side_effect(router_info, router_id):
            router_info[router_id] = {
                'edge_cluster_uuid': FAKE_EDGE_CLUSTER_ID
            }

        self.mock_router_lib.validate_tier0.side_effect = side_effect

        with self._get_patched_nsx_api() as napi:
            napi._create_project(FAKE_PROJECT, do_snat)

        router_name = '%s-%s' % (cfg.CONF.coe.cluster, FAKE_PROJECT)
        self.mock_router_client.create.assert_called_once_with(
            router_name, mock.ANY)
        self.mock_router_lib.add_router_link_port.assert_called_once_with(
            FAKE_TIER1_ROUTER_ID, FAKE_TIER0_ROUTER_ID, mock.ANY)
        self.mock_router_lib.validate_tier0.assert_called_once_with(
            mock.ANY, FAKE_TIER0_ROUTER_ID)
        self.mock_router_lib.update_advertisement.assert_called_once_with(
            FAKE_TIER1_ROUTER_ID, True, True, True)
        mock_create_logical_switch.assert_called_once_with(FAKE_PROJECT,
                                                           None, do_snat)

    def test_create_snat_project_if_not_exist(self):
        self._test_create_project_if_not_exist(do_snat=True)

    def test_create_nosnat_project_if_not_exist(self):
        self._test_create_project_if_not_exist(do_snat=False)

    @mock.patch('nsx_ujo.ncp.cache.CoeNSXMapping.get')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._create_logical_switch')
    def test_create_project_if_exist(self, mock_create_logical_switch,
                                     mock_mapping_get):
        mock_mapping_get.return_value = {
            const.LR: FAKE_TIER1_ROUTER_ID,
            const.LS: [{'id': FAKE_SWITCH_ID}]}

        with self._get_patched_nsx_api() as napi:
            napi._create_project(FAKE_PROJECT)

        self.mock_router_client.create.assert_not_called()
        mock_create_logical_switch.assert_not_called()

    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._create_logical_switch')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._allocate_snat_ip')
    def _test_create_project_with_failure(self, mock_allocate_snat_ip,
                                          mock_create_logical_switch,
                                          do_snat):
        mock_allocate_snat_ip.return_value = {
            'allocation_id': '10.10.10.10',
            'ip_pool_id': FAKE_EXTERNAL_IP_POOL_ID
        }
        self.mock_router_client.create.return_value = {
            'id': FAKE_TIER1_ROUTER_ID
        }

        def side_effect(router_info, router_id):
            router_info[router_id] = {
                'edge_cluster_uuid': FAKE_EDGE_CLUSTER_ID
            }

        self.mock_router_lib.validate_tier0.side_effect = side_effect
        mock_create_logical_switch.side_effect = nsxlib_exc.ManagerError

        with self._get_patched_nsx_api() as napi:
            self.assertRaises(nsxlib_exc.ManagerError, napi._create_project,
                              FAKE_PROJECT, do_snat)

        router_name = '%s-%s' % (cfg.CONF.coe.cluster, FAKE_PROJECT)
        self.mock_router_client.create.assert_called_once_with(
            router_name, mock.ANY)
        self.mock_router_lib.add_router_link_port.assert_called_once_with(
            FAKE_TIER1_ROUTER_ID, FAKE_TIER0_ROUTER_ID, mock.ANY)
        self.mock_router_lib.validate_tier0.assert_called_once_with(
            mock.ANY, FAKE_TIER0_ROUTER_ID)
        self.mock_router_lib.update_advertisement.assert_called_once_with(
            FAKE_TIER1_ROUTER_ID, True, True, True)
        self.mock_router_client.delete.assert_called_once_with(
            FAKE_TIER1_ROUTER_ID)
        self.mock_router_lib.remove_router_link_port.assert_called_once_with(
            FAKE_TIER1_ROUTER_ID, FAKE_TIER0_ROUTER_ID)
        if do_snat:
            self.mock_ip_pool_client.release.assert_called_once_with(
                FAKE_EXTERNAL_IP_POOL_ID, '10.10.10.10')
        else:
            mock_allocate_snat_ip.assert_not_called()
            self.mock_ip_pool_client.release.assert_not_called()
        mock_create_logical_switch.assert_called_once_with(FAKE_PROJECT,
                                                           None, do_snat)

    def test_create_snat_project_with_failure(self):
        self._test_create_project_with_failure(do_snat=True)

    def test_create_nosnat_project_with_failure(self):
        self._test_create_project_with_failure(do_snat=False)

    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._attach_switch_to_router')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._create_project_subnet')
    @mock.patch('nsx_ujo.ncp.cache.CoeNSXMapping.get')
    def test_create_project_result(self, mock_mapping_get,
                                   mock_create_project_subnet,
                                   mock_attach_switch_to_router):
        mock_mapping_get.return_value = {'logical-router':
                                         FAKE_TIER1_ROUTER_ID}
        mock_create_project_subnet.return_value = (
            {'cidr': FAKE_CIDR, 'id': FAKE_SUBNET_ID},
            {'id': FAKE_IP_POOL_ID}
        )
        self.mock_nsx_lib.logical_switch.create.return_value = {
            'id': FAKE_SWITCH_ID
        }

        with self._get_patched_nsx_api() as napi:
            result = napi._create_project(FAKE_PROJECT, do_snat=False)
            annotations = {
                'labels': {},
                'logical-router': FAKE_TIER1_ROUTER_ID,
                'logical-switch': [{
                    'subnet_id': FAKE_SUBNET_ID,
                    'subnet': FAKE_CIDR,
                    'ip_pool_id': FAKE_IP_POOL_ID,
                    'id': FAKE_SWITCH_ID
                }]
            }
            self.assertEqual(annotations, result)

    @mock.patch('nsx_ujo.ncp.cache.CoeNSXMapping.get')
    def test_update_project(self, mock_mapping_get):
        mock_mapping_get.return_value = {
            const.LR: FAKE_TIER1_ROUTER_ID,
            const.LS: [{'id': 'fake_switch_id1',
                        const.SUBNET: '192.168.1.0/24',
                        const.SUBNET_ID: 'fake_subnet_id1',
                        const.IP_POOL_ID: 'fake_ip_pool_id1'},
                       {'id': 'fake_switch_id2',
                        const.SUBNET: '192.168.2.0/24',
                        const.SUBNET_ID: 'fake_subnet_id2',
                        const.IP_POOL_ID: 'fake_ip_pool_id2'}],
            'labels': [{'foo': 'foo_val'}]}
        with self._get_patched_nsx_api() as napi:
            nsgroup_labels = {'foo': 'new_foo_val'}
            napi.update_project(FAKE_PROJECT, nsgroup_labels)

        tags = [{const.SCOPE: const.TAG_PROJECT,
                 const.TAG: FAKE_PROJECT},
                {const.SCOPE: const.TAG_VERSION,
                 const.TAG: ncp_utils.NCP_VERSION},
                {const.SCOPE: const.TAG_COE,
                 const.TAG: cfg.CONF.coe.adaptor},
                {const.SCOPE: const.TAG_CLUSTER,
                 const.TAG: cfg.CONF.coe.cluster},
                {const.SCOPE: 'foo',
                 const.TAG: 'new_foo_val'}]
        ls_tags1 = tags + [{const.SCOPE: const.TAG_SUBNET,
                            const.TAG: '192.168.1.0/24'},
                           {const.SCOPE: const.TAG_SUBNET_ID,
                            const.TAG: 'fake_subnet_id1'},
                           {const.SCOPE: const.TAG_IP_POOL_ID,
                            const.TAG: 'fake_ip_pool_id1'}]
        ls_tags2 = tags + [{const.SCOPE: const.TAG_SUBNET,
                            const.TAG: '192.168.2.0/24'},
                           {const.SCOPE: const.TAG_SUBNET_ID,
                            const.TAG: 'fake_subnet_id2'},
                           {const.SCOPE: const.TAG_IP_POOL_ID,
                            const.TAG: 'fake_ip_pool_id2'}]
        self.mock_nsx_lib.logical_switch.update.assert_has_calls([
            mock.call(lswitch_id='fake_switch_id1', admin_state=True,
                      tags=ls_tags1),
            mock.call(lswitch_id='fake_switch_id2', admin_state=True,
                      tags=ls_tags2)])

    @mock.patch('nsx_ujo.ncp.nsxapi.LOG.warning')
    @mock.patch('nsx_ujo.ncp.cache.CoeNSXMapping.get')
    def test_update_non_existent_project(self, mock_mapping_get, mock_warning):
        mock_mapping_get.return_value = {}

        with self._get_patched_nsx_api() as napi:
            napi.update_project(FAKE_PROJECT)

        mock_warning.assert_called_once_with(
            'No logical switch is mapped to project %s', FAKE_PROJECT)
        self.mock_nsx_lib.logical_switch.update.assert_not_called()

    @mock.patch('nsx_ujo.ncp.cache.CoeNSXMapping.get')
    @mock.patch('nsx_ujo.ncp.nsxapi.cache.CoeNSXMapping.delete')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._delete_health_check_rule')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._delete_project_subnet')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._unconfigure_snat_rule')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._set_ip_pool_status')
    def test_delete_project(self, mock_set_ip_pool_status,
                            mock_unconfigure_snat_rule,
                            mock_delete_project_subnet,
                            mock_delete_health_check_rule,
                            mock_mapping_delete, mock_mapping_get):
        fake_project = {
            const.LR: FAKE_TIER1_ROUTER_ID,
            const.LS: [{'id': FAKE_SWITCH_ID,
                        const.SUBNET: FAKE_CIDR,
                        const.SUBNET_ID: FAKE_SUBNET_ID,
                        const.IP_POOL_ID: FAKE_IP_POOL_ID}],
            const.SNAT_IP: '10.10.10.10',
            const.EXTERNAL_POOL_ID: FAKE_EXTERNAL_IP_POOL_ID,
            const.HC_SECTION: FAKE_HC_SECTION_ID,
            'labels': [{'foo': 'foo_val'}]}

        fake_ext_ip_pool = {'id': FAKE_EXTERNAL_IP_POOL_ID,
                            'status': 'full'}
        mock_mapping_get.side_effect = [fake_project, fake_ext_ip_pool]
        with self._get_patched_nsx_api() as napi:
            napi.delete_project(FAKE_PROJECT)

        self.mock_router_port_client.delete_by_lswitch_id.\
            assert_called_once_with(FAKE_SWITCH_ID)
        self.mock_nsx_lib.logical_switch.delete.assert_called_once_with(
            FAKE_SWITCH_ID)
        mock_delete_project_subnet.assert_called_once_with(FAKE_SUBNET_ID,
            FAKE_IP_POOL_ID)
        mock_unconfigure_snat_rule.assert_called_once_with(
            FAKE_PROJECT, FAKE_CIDR)
        self.mock_ip_pool_client.release.assert_called_once_with(
            FAKE_EXTERNAL_IP_POOL_ID, '10.10.10.10')
        mock_set_ip_pool_status.assert_called_once_with(
            FAKE_EXTERNAL_IP_POOL_ID, 'free')
        mock_delete_health_check_rule(FAKE_HC_SECTION_ID)
        self.mock_router_lib.remove_router_link_port.\
            assert_called_once_with(FAKE_TIER1_ROUTER_ID,
                                    FAKE_TIER0_ROUTER_ID)
        self.mock_router_client.delete.assert_called_once_with(
            FAKE_TIER1_ROUTER_ID)
        mock_mapping_delete.assert_called_once_with(FAKE_PROJECT,
        parent_key=const.PROJECT)

    @mock.patch('nsx_ujo.ncp.nsxapi.LOG.warning')
    @mock.patch('nsx_ujo.ncp.cache.CoeNSXMapping.get')
    def test_delete_non_existent_project(self, mock_mapping_get, mock_warning):
        mock_mapping_get.return_value = {}

        with self._get_patched_nsx_api() as napi:
            napi.delete_project(FAKE_PROJECT)

        mock_warning.assert_called_once_with(
            'No logical switch is mapped to project %s', FAKE_PROJECT)

    def test_release_subnet_to_ip_block(self):
        with self._get_patched_nsx_api() as napi:
            ip_block = {
                'id': FAKE_IP_BLOCK_ID,
                'status': 'full',
                'subnets': set([FAKE_SUBNET_ID])
            }
            napi._mapping.insert(FAKE_IP_BLOCK_ID, ip_block,
                                 parent_key=const.IP_BLOCK)
            napi._release_subnet_to_ip_block(FAKE_SUBNET_ID)
            self.mock_nsx_lib.ip_block_subnet.delete.assert_called_once_with(
                FAKE_SUBNET_ID)
            self.assertEqual(ip_block['status'], 'free')
            self.assertNotIn(FAKE_SUBNET_ID, ip_block['subnets'])

    def test_set_ip_block_status(self):
        with self._get_patched_nsx_api() as napi:
            ip_block = {
                'id': FAKE_IP_BLOCK_ID,
                'status': 'free',
                'subnets': set([FAKE_SUBNET_ID])
            }
            napi._mapping.insert(FAKE_IP_BLOCK_ID, ip_block,
                                 parent_key=const.IP_BLOCK)
            napi._set_ip_block_status(FAKE_IP_BLOCK_ID, 'full')
            self.assertEqual(ip_block['status'], 'full')

    def _test_create_ip_pool(self, reserve_gateway_address):
        with self._get_patched_nsx_api() as napi:
            ip_network = netaddr.IPNetwork('192.168.0.0/16')
            display_name = 'fake_ip_pool_name'
            tags = mock.Mock()
            napi._create_ip_pool(FAKE_IP_BLOCK_ID, ip_network, display_name,
                reserve_gateway_address, tags)
            expected_allocation_ranges_param = [
                {'start': '192.168.0.2' if reserve_gateway_address else
                          '192.168.0.1',
                 'end': '192.168.255.254'}
            ]
            self.mock_ip_pool_client.create.assert_called_once_with(
                cidr='192.168.0.0/16', display_name=display_name,
                allocation_ranges=expected_allocation_ranges_param,
                tags=tags)

    def test_create_ip_pool_reserve_gateway_address(self):
        self._test_create_ip_pool(True)

    def test_create_ip_pool_not_reserve_gateway_address(self):
        self._test_create_ip_pool(False)

    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._create_ip_pool')
    def test_create_pool_from_ip_block(self, mock_create_ip_pool):
        self.mock_nsx_lib.ip_block_subnet.create.return_value = {
            'id': FAKE_SUBNET_ID,
            'allocation_ranges': mock.Mock(),
            'cidr': '192.168.0.0/24'
        }
        ip_blocks_getter = mock.Mock(return_value=[{'id': FAKE_IP_BLOCK_ID,
                                                    'subnets': set()}])
        with self._get_patched_nsx_api() as napi:
            napi._create_pool_from_ip_block(ip_blocks_getter, 24, 'fake_name',
                True, None)
        self.mock_nsx_lib.ip_block_subnet.create.assert_called_once_with(
            FAKE_IP_BLOCK_ID, 24)
        mock_create_ip_pool.assert_called_once_with(FAKE_IP_BLOCK_ID, mock.ANY,
            'fake_name', True, None)

    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._create_pool_from_ip_block')
    def _test_create_external_ip_pools(self, mock_create_pool_from_ip_block,
                                       expected_subnet_size):
        with self._get_patched_nsx_api() as napi:
            self.mock_nsx_lib.search_by_tags.return_value = {'result_count': 0}
            fake_subnet = {
                'id': FAKE_SUBNET_ID,
                'allocation_ranges': mock.Mock(),
                'cidr': '192.168.0.0/24'
            }
            mock_create_pool_from_ip_block.return_value = (mock.ANY,
                                                           fake_subnet)
            res_ip_pool = napi._create_external_ip_pools()
            mock_create_pool_from_ip_block.assert_called_once_with(
                napi._get_available_external_ip_block,
                expected_subnet_size,
                display_name=utils.generate_display_name('ext'),
                reserve_gateway_address=False,
                tags=mock.ANY)
            self.assertEqual(res_ip_pool, [fake_subnet])

    def test_create_external_ip_pools_with_subnet_prefix(self):
        cfg.CONF.set_override('external_subnet_prefix', None, 'nsx_v3')
        cfg.CONF.set_override('subnet_prefix', 24, 'nsx_v3')

        self._test_create_external_ip_pools(
            expected_subnet_size=2 ** (32 - 24))

    def test_create_external_ip_pools_with_external_subnet_prefix(self):
        cfg.CONF.set_override('external_subnet_prefix', 28, 'nsx_v3')
        cfg.CONF.set_override('subnet_prefix', 24, 'nsx_v3')

        self._test_create_external_ip_pools(
            expected_subnet_size=2 ** (32 - 28))

    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._create_pool_from_ip_block')
    def test_find_external_ip_pools(self, mock_create_pool_from_ip_block):
        self.mock_nsx_lib.search_by_tags.return_value = {
            'result_count': 1,
            'results': [
                {
                    'status': 'free',
                    'id': FAKE_EXTERNAL_IP_POOL_ID,
                }
            ]
        }
        with self._get_patched_nsx_api() as napi:
            observed_res = napi._find_external_ip_pools()
            self.assertEqual(
                [{'status': 'free',
                  'id': FAKE_EXTERNAL_IP_POOL_ID}],
                observed_res
            )
        tags = [
            {'scope': ncp_utils.escape_data(const.TAG_EXTERNAL_POOL),
             'tag': const.TAG_TRUE},
            {'scope': ncp_utils.escape_data(const.TAG_CLUSTER),
             'tag': cfg.CONF.coe.cluster}
        ]
        self.mock_nsx_lib.search_by_tags.assert_called_once_with(
            resource_type=const.IP_POOL, tags=tags)
        mock_create_pool_from_ip_block.assert_not_called()

    def test_allocate_external_ip(self):
        self.mock_ip_pool_client.allocate.return_value = {
            'allocation_id': 'fake_allocation_id'
        }
        external_ip_pools = [
            {'id': 'fake_id1'},
            {'id': 'fake_id2'}
        ]

        with self._get_patched_nsx_api() as napi:
            observed_res = napi._allocate_external_ip(external_ip_pools)

        self.mock_ip_pool_client.allocate.assert_called_once_with(
            'fake_id1')
        return_val = {
            'allocation_id': 'fake_allocation_id',
            'ip_pool_id': 'fake_id1'
        }
        self.assertEqual(return_val, observed_res)

    @mock.patch('nsx_ujo.ncp.nsxapi.LOG.warning')
    def test_allocate_external_ip_with_failure(self, mock_warning):
        self.mock_ip_pool_client.allocate.side_effect = [
            nsxlib_exc.ManagerError(),
            KeyError(),
            {'allocation_id': 'fake_allocation_id'}
        ]
        external_ip_pools = [
            {'id': 'fake_id1'},
            {'id': 'fake_id2'},
            {'id': 'fake_id3'}
        ]

        with self._get_patched_nsx_api() as napi:
            observed_res = napi._allocate_external_ip(external_ip_pools)

        self.mock_ip_pool_client.allocate.assert_has_calls([
            mock.call('fake_id1'), mock.call('fake_id2'),
            mock.call('fake_id3')])
        mock_warning.assert_has_calls([
            mock.call('Unable to allocate IP address from pool %s: %s',
                      'fake_id1', mock.ANY),
            mock.call('Allocation response from pool %s did not return an '
                      'IP address', 'fake_id2')])
        return_val = {
            'allocation_id': 'fake_allocation_id',
            'ip_pool_id': 'fake_id3'
        }
        self.assertEqual(return_val, observed_res)

    @mock.patch('nsx_ujo.ncp.cache.CoeNSXMapping.get')
    def test_configure_snat_rule(self, mock_mapping_get):
        mock_mapping_get.return_value = {const.SNAT_IP: '10.10.10.10'}
        with self._get_patched_nsx_api() as napi:
            napi._configure_snat_rule(FAKE_PROJECT, FAKE_CIDR)
        self.mock_nsx_lib.logical_router.add_nat_rule.assert_called_once_with(
            FAKE_TIER0_ROUTER_ID, 'SNAT', '10.10.10.10', source_net=FAKE_CIDR)

    def test_unconfigure_snat_rule(self):
        with self._get_patched_nsx_api() as napi:
            napi._unconfigure_snat_rule(FAKE_PROJECT, FAKE_CIDR)
        self.mock_nsx_lib.logical_router.delete_nat_rule_by_values.\
            assert_called_once_with(FAKE_TIER0_ROUTER_ID,
                                    match_source_network=FAKE_CIDR)

    @mock.patch('nsx_ujo.ncp.cache.CoeNSXMapping.get')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._find_external_ip_pools')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._update_project_router')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._allocate_external_ip')
    def test_allocate_snat_ip_if_ip_pools_not_exist(self,
            mock_allocate_external_ip, mock_update_project_router,
            mock_find_external_ip_pools, mock_mapping_get):
        mock_mapping_get.return_value = []
        mock_find_external_ip_pools.return_value = [
                {'status': 'free', 'id': FAKE_IP_POOL_ID}]

        mock_allocate_external_ip.side_effect = [
            None,
            {
                'allocation_id': '10.10.10.10',
                'ip_pool_id': FAKE_IP_POOL_ID
            }
        ]
        with self._get_patched_nsx_api() as napi:
            observed_res = napi._allocate_snat_ip(FAKE_PROJECT,
                                                  FAKE_TIER1_ROUTER_ID)

        mock_find_external_ip_pools.assert_called_once_with()
        mock_allocate_external_ip.assert_called_with(
                [{'status': 'free',
                  'id': FAKE_IP_POOL_ID}])
        mock_update_project_router.assert_called_once_with(
            FAKE_PROJECT,
            router_id=FAKE_TIER1_ROUTER_ID,
            tags_update=[
                {'scope': const.TAG_SNAT_IP, 'tag': '10.10.10.10'},
                {'scope': const.TAG_EXTERNAL_POOL_ID,
                 'tag': FAKE_IP_POOL_ID}]
        )
        self.assertEqual(
            {'allocation_id': '10.10.10.10',
             'ip_pool_id': FAKE_IP_POOL_ID},
            observed_res
        )

    @mock.patch('nsx_ujo.ncp.cache.CoeNSXMapping.get')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._find_external_ip_pools')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._update_project_router')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._allocate_external_ip')
    @mock.patch('nsx_ujo.ncp.nsxapi.LOG.error')
    def test_allocate_snat_ip_if_ip_pools_not_found(self, mock_error,
            mock_allocate_external_ip, mock_update_project_router,
            mock_find_external_ip_pools, mock_mapping_get):
        mock_mapping_get.return_value = []
        mock_find_external_ip_pools.return_value = None

        with self._get_patched_nsx_api() as napi:
            with self.assertRaises(ncp_exc.ManagerError):
                napi._allocate_snat_ip(FAKE_PROJECT, FAKE_TIER1_ROUTER_ID)

        mock_find_external_ip_pools.assert_called_once_with()
        mock_error.assert_called_with(
            'Fail to find external IP pool in cluster %s', 'k8scluster'
        )
        mock_allocate_external_ip.assert_not_called()
        mock_update_project_router.assert_not_called()

    @mock.patch('nsx_ujo.ncp.cache.CoeNSXMapping.get')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._delete_project_subnet')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._attach_switch_to_router')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._create_project_subnet')
    def test_create_logical_switch_with_failure(self,
                                                mock_create_project_subnet,
                                                mock_attach_switch_to_router,
                                                mock_delete_project_subnet,
                                                mock_mapping_get):
        project_nsx_mapping = {const.LR: FAKE_TIER1_ROUTER_ID,
                               const.SNAT_IP: '10.10.10.10'}
        mock_mapping_get.return_value = project_nsx_mapping
        self.mock_nsx_lib.logical_switch.create.return_value = {'id':
                                                                FAKE_SWITCH_ID}
        mock_create_project_subnet.return_value = (
            {'cidr': FAKE_CIDR, 'id': FAKE_SUBNET_ID},
            {'id': FAKE_IP_POOL_ID})
        mock_attach_switch_to_router.side_effect = nsxlib_exc.ManagerError
        nsgroup_labels = {'foo': 'new_foo_val'}
        with self._get_patched_nsx_api() as napi:
            self.assertRaises(nsxlib_exc.ManagerError,
                              napi._create_logical_switch,
                              FAKE_PROJECT, nsgroup_labels)

        ls_name = '%s-%s-%d' % (cfg.CONF.coe.cluster, FAKE_PROJECT, 0)
        mock_create_project_subnet.assert_called_once_with(
            True, ip_pool_name=ls_name)
        self.mock_nsx_lib.logical_switch.create.assert_called_once_with(
            ls_name, FAKE_OVERLAY_TZ_ID, mock.ANY, ip_pool_id=FAKE_IP_POOL_ID)
        mock_attach_switch_to_router.assert_called_once_with(FAKE_PROJECT,
            FAKE_TIER1_ROUTER_ID, FAKE_SWITCH_ID, FAKE_CIDR, mock.ANY)
        mock_delete_project_subnet.assert_called_once_with(FAKE_SUBNET_ID,
                                                           FAKE_IP_POOL_ID)
        self.mock_nsx_lib.logical_switch.delete.assert_called_once_with(
            FAKE_SWITCH_ID)

    @mock.patch('nsx_ujo.ncp.cache.CoeNSXMapping.get')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._configure_snat_rule')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._attach_switch_to_router')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._create_project_subnet')
    def _test_create_logical_switch(self, mock_create_project_subnet,
                                    mock_attach_switch_to_router,
                                    mock_configure_snat_rule,
                                    mock_mapping_get,
                                    do_snat):
        project_nsx_mapping = {const.LR: FAKE_TIER1_ROUTER_ID,
                               const.SNAT_IP: '10.10.10.10'}
        mock_mapping_get.return_value = project_nsx_mapping
        self.mock_nsx_lib.logical_switch.create.return_value = {'id':
                                                                FAKE_SWITCH_ID}
        mock_create_project_subnet.return_value = (
            {'cidr': FAKE_CIDR, 'id': FAKE_SUBNET_ID},
            {'id': FAKE_IP_POOL_ID})
        nsgroup_labels = {'foo': 'new_foo_val'}
        with self._get_patched_nsx_api() as napi:
            observed_res = napi._create_logical_switch(FAKE_PROJECT,
                                                       nsgroup_labels,
                                                       do_snat=do_snat)

        ls_name = '%s-%s-%d' % (cfg.CONF.coe.cluster, FAKE_PROJECT, 0)
        mock_create_project_subnet.assert_called_once_with(
            do_snat, ip_pool_name=ls_name)
        if do_snat:
            mock_configure_snat_rule.assert_called_once_with(
                FAKE_PROJECT, FAKE_CIDR)
        else:
            mock_configure_snat_rule.assert_not_called()

        self.mock_nsx_lib.logical_switch.create.assert_called_once_with(
            ls_name, FAKE_OVERLAY_TZ_ID, mock.ANY, ip_pool_id=FAKE_IP_POOL_ID)
        mock_attach_switch_to_router.assert_called_once_with(FAKE_PROJECT,
            FAKE_TIER1_ROUTER_ID, FAKE_SWITCH_ID, FAKE_CIDR, mock.ANY)
        self.assertEqual(observed_res, {
            'id': FAKE_SWITCH_ID,
            const.SUBNET: FAKE_CIDR,
            const.SUBNET_ID: FAKE_SUBNET_ID,
            const.IP_POOL_ID: FAKE_IP_POOL_ID})

    def test_create_logical_switch_snat(self):
        self._test_create_logical_switch(do_snat=True)

    def test_create_logical_switch_no_snat(self):
        self._test_create_logical_switch(do_snat=False)

    def _build_ip_blocks(self, standard_count=1, no_snat_count=1,
                         external_count=1):
        ip_blocks = []
        for i in range(standard_count):
            ip_blocks.append({
                'id': 'mock-ip-block-standard-id%d' % i,
                'cidr': '10.%d.0.0/16' % i,
                'tags': [{'scope': const.TAG_CLUSTER,
                          'tag': cfg.CONF.coe.cluster}]
            })
        for i in range(no_snat_count):
            ip_blocks.append({
                'id': 'mock-ip-block-no-snat-id%d' % i,
                'cidr': '11.%d.0.0/16' % i,
                'tags': [{'scope': const.TAG_NO_SNAT,
                          'tag': cfg.CONF.coe.cluster},
                         {'scope': const.TAG_CLUSTER,
                          'tag': cfg.CONF.coe.cluster}]
            })
        for i in range(external_count):
            ip_blocks.append({
                'id': 'mock-ip-block-external-id%d' % i,
                'cidr': '12.%d.0.0/16' % i,
                'tags': [{'scope': const.TAG_EXTERNAL_POOL,
                          'tag': 'true'}]
            })
        return ip_blocks

    def test_get_available_external_ip_block(self):
        self.mock_nsx_lib.ip_block.list.return_value = {
            'results': self._build_ip_blocks(external_count=2)}

        with self._get_patched_nsx_api() as napi:
            expected_ids = set(['mock-ip-block-external-id0',
                                'mock-ip-block-external-id1'])
            observed_ids = set(blk['id']
                for blk in napi._get_available_external_ip_block())
            self.assertEqual(observed_ids, expected_ids)

            for id in observed_ids:
                napi._set_ip_block_status(id, 'full')
            observed_ids = set(blk['id']
                for blk in napi._get_available_external_ip_block())
            self.assertEqual(observed_ids, set())

    def _test_get_available_internal_ip_block(self, do_snat, no_snat_count):
        self.mock_nsx_lib.ip_block.list.return_value = {
            'results': self._build_ip_blocks(no_snat_count=no_snat_count)}
        with self._get_patched_nsx_api() as napi:
            observed_ids = set(blk['id']
                for blk in napi._get_available_internal_ip_block(do_snat))
            if no_snat_count > 0:
                if do_snat:
                    expected_ids = set(['mock-ip-block-standard-id0'])
                else:
                    expected_ids = set(['mock-ip-block-no-snat-id0'])
            else:
                expected_ids = set(['mock-ip-block-standard-id0'])
            self.assertEqual(observed_ids, expected_ids)

    def test_get_available_internal_no_snat_ip_block_if_exists(self):
        self._test_get_available_internal_ip_block(do_snat=False,
                                                   no_snat_count=1)

    def test_get_available_internal_no_snat_ip_block_if_not_exists(self):
        self._test_get_available_internal_ip_block(do_snat=False,
                                                   no_snat_count=0)

    def test_get_available_internal_do_snat_ip_block(self):
        self._test_get_available_internal_ip_block(do_snat=True,
                                                   no_snat_count=1)

    def test_attach_switch_to_router(self):
        self.mock_port_client.create.return_value = {'id': 'fake_port_id'}
        tags = mock.Mock()
        with self._get_patched_nsx_api() as napi:
            napi._attach_switch_to_router(FAKE_PROJECT, FAKE_TIER1_ROUTER_ID,
                                          FAKE_SWITCH_ID, '192.168.0.0/24',
                                          tags)

        self.mock_port_client.create.assert_called_once_with(FAKE_SWITCH_ID,
            'LR-%s' % FAKE_PROJECT, attachment_type=None)
        self.mock_router_lib.create_logical_router_intf_port_by_ls_id.\
            assert_called_once_with(logical_router_id=FAKE_TIER1_ROUTER_ID,
                display_name='lrp-%s' % FAKE_PROJECT, tags=tags,
                ls_id=FAKE_SWITCH_ID, logical_switch_port_id='fake_port_id',
                address_groups=[
                    {'ip_addresses': ['192.168.0.1'],
                     'prefix_length': cfg.CONF.nsx_v3.subnet_prefix}],
                urpf_mode='NONE')

    def test_attach_switch_to_router_with_failure(self):
        self.mock_port_client.create.return_value = {'id': 'fake_port_id'}
        self.mock_router_lib.create_logical_router_intf_port_by_ls_id.\
            side_effect = nsxlib_exc.ManagerError
        tags = mock.Mock()
        with self._get_patched_nsx_api() as napi:
            self.assertRaises(nsxlib_exc.ManagerError,
                              napi._attach_switch_to_router,
                              FAKE_PROJECT, FAKE_TIER1_ROUTER_ID,
                              FAKE_SWITCH_ID, '192.168.0.0/24', tags)

        self.mock_port_client.create.assert_called_once_with(FAKE_SWITCH_ID,
            'LR-%s' % FAKE_PROJECT, attachment_type=None)
        self.mock_router_lib.create_logical_router_intf_port_by_ls_id.\
            assert_called_once_with(logical_router_id=FAKE_TIER1_ROUTER_ID,
                display_name='lrp-%s' % FAKE_PROJECT, tags=tags,
                ls_id=FAKE_SWITCH_ID, logical_switch_port_id='fake_port_id',
                address_groups=[
                    {'ip_addresses': ['192.168.0.1'],
                     'prefix_length': cfg.CONF.nsx_v3.subnet_prefix}],
                urpf_mode='NONE')
        self.mock_port_client.delete.assert_called_once_with('fake_port_id')

    def test_allocate_ingress_ip_from_pool(self):
        self.mock_ip_pool_client.allocate.return_value = {
            'allocation_id': '10.10.10.10'}
        with self._get_patched_nsx_api() as napi, \
            mock.patch.object(nsxapi.NSXAPI,
                              '_get_external_ip_pools') as mock_get_pools:
            mock_get_pools.return_value = [{'id': 'fake_id'}]
            observed_res = napi._allocate_ingress_ip(FAKE_PROJECT)
        self.mock_ip_pool_client.allocate.assert_called_once_with('fake_id')
        self.assertEqual(
                observed_res,
                {'allocation_id': '10.10.10.10', 'ip_pool_id': 'fake_id'}
        )

    def test_release_ingress_ip(self):
        with self._get_patched_nsx_api() as napi:
            napi._release_ingress_ip('10.10.10.10', 'fake_pool_id')

        self.mock_ip_pool_client.release.assert_called_once_with(
            pool_id='fake_pool_id', ip_addr='10.10.10.10')

    def _test_create_pod_if_exist(self, label_updated):
        nsgroup_labels = {'foo': 'foo_val'}
        pod_info = {'labels': nsgroup_labels.copy(),
                    'attachment_id': 'fake_attachment_id',
                    'cif_id': 'fake_cif_id',
                    'ip': '192.168.0.10/24',
                    'vlan': 1,
                    'mac': 'aa:aa:aa:aa:aa:aa',
                    'gateway_ip': '192.168.0.1',
                    'ingress_controller': False,
                    'port_id': FAKE_PORT_ID}
        pod_key = utils.get_resource_key(FAKE_PROJECT, FAKE_POD)
        if label_updated:
            nsgroup_labels['foo2'] = 'foo2_val'

        with self._get_patched_nsx_api() as napi:
            napi._mapping.insert(pod_key, pod_info, parent_key=const.POD)
            pod_updated, _ = napi.create_pod(FAKE_POD, FAKE_PROJECT,
                                             '192.168.0.10', FAKE_VIF_ID,
                                             nsgroup_labels, 'fake_cluster_id')
        if label_updated:
            self.mock_port_client.update.assert_called_once()
            self.assertTrue(pod_updated)
        else:
            self.mock_port_client.update.assert_not_called()
            self.assertFalse(pod_updated)

    def test_create_pod_if_exist_and_label_updated(self):
        self._test_create_pod_if_exist(label_updated=True)

    def test_create_pod_if_exist_and_label_not_updated(self):
        self._test_create_pod_if_exist(label_updated=False)

    @mock.patch('nsx_ujo.k8s.adaptor.Kubernetes.is_namespace_isolated')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI.create_project')
    @mock.patch('nsx_ujo.k8s.kubernetes.get_namespace')
    def test_create_project_and_get_mapping(self, mocked_get_namespace,
                                            mocked_create_project,
                                            mocked_isolated):
        with self._get_patched_nsx_api() as napi:
            project = 'test_project_1'
            project_nsx_mapping = {const.LS: 'switch'}
            napi._mapping.insert(
                    project, project_nsx_mapping, parent_key=const.PROJECT)
            mapping_obtained = napi._create_project_upon_cache_miss(project)
            mocked_create_project.assert_not_called()
            self.assertEqual(project_nsx_mapping, mapping_obtained)

        mocked_create_project.reset_mock()

        with self._get_patched_nsx_api() as napi:
            project = 'test_project_2'
            napi._mapping.insert(
                project, {}, parent_key=const.PROJECT)
            napi._create_project_upon_cache_miss(project)
            mocked_create_project.assert_called_once()

    @mock.patch('nsx_ujo.ncp.allocators.CifAllocator.get_cif_id')
    @mock.patch('nsx_ujo.ncp.allocators.VlanAllocator.get_node_vlan')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._allocate_ingress_ip')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._add_health_check_rule_to_port')
    @mock.patch(
        'nsx_ujo.ncp.nsxapi.NSXAPI._build_container_spoofguard_profile')
    def _test_create_pod(self, mock_build_container_spoofguard_profile,
                         mock_add_health_check_rule_to_port,
                         mock_allocate_ingress_ip,
                         mock_get_node_vlan,
                         mock_get_cif_id,
                         create_ingress_rules,
                         health_check_ports):
        mock_get_node_vlan.return_value = 1
        mock_get_cif_id.return_value = 'fake_cif_id'
        mock_allocate_ingress_ip.return_value = {
            'allocation_id': '10.10.10.10',
            'ip_pool_id': FAKE_EXTERNAL_IP_POOL_ID
        }
        mock_add_health_check_rule_to_port.return_value = FAKE_HC_SECTION_ID
        nsgroup_labels = {'foo': 'foo_val'}
        project_nsx_mapping = {
            const.LR: FAKE_TIER1_ROUTER_ID,
            const.LS: [{'subnet': '192.168.0.0/24',
                        'id': FAKE_SWITCH_ID}]
        }
        self.mock_port_client.create.return_value = {
            'id': FAKE_PORT_ID,
            'address_bindings': [{'ip_address': '192.168.0.10',
                                  'mac_address': 'aa:aa:aa:aa:aa:aa'}]
        }

        with self._get_patched_nsx_api() as napi:
            napi._mapping.insert(FAKE_PROJECT, project_nsx_mapping,
                parent_key=const.PROJECT)
            updated, _ = napi.create_pod(FAKE_POD, FAKE_PROJECT, '10.0.0.10',
                                         FAKE_VIF_ID, nsgroup_labels,
                                         'fake_cluster_id',
                                         create_ingress_rules,
                                         health_check_ports)

        pod_key = utils.get_resource_key(FAKE_PROJECT, FAKE_POD)
        self.assertTrue(updated)
        self.mock_port_client.create.assert_called_once_with(
            FAKE_SWITCH_ID, 'fake_cif_id', tags=mock.ANY,
            parent_vif_id=FAKE_VIF_ID, traffic_tag=1,
            switch_profile_ids=mock.ANY, vif_type=const.CIF_TYPE,
            app_id=pod_key,
            allocate_addresses=const.CIF_ALLOCATE_ADDRESSES)
        if create_ingress_rules:
            mock_allocate_ingress_ip.assert_called_once_with(FAKE_PROJECT)
            self.mock_router_lib.delete_fip_nat_rules.\
                assert_called_once_with(FAKE_TIER0_ROUTER_ID,
                                        '10.10.10.10', '192.168.0.10')
            self.mock_router_lib.add_fip_nat_rules.\
                assert_called_once_with(FAKE_TIER0_ROUTER_ID,
                                        '10.10.10.10', '192.168.0.10',
                                        match_ports=[80, 443])
        else:
            mock_allocate_ingress_ip.assert_not_called()
            self.mock_router_lib.delete_fip_nat_rules.assert_not_called()
            self.mock_router_lib.add_fip_nat_rules.assert_not_called()
        if health_check_ports:
            mock_add_health_check_rule_to_port.assert_called_once_with(
                '192.168.0.10', FAKE_PORT_ID, '10.0.0.10',
                health_check_ports)
            self.mock_port_client.update.assert_called_once_with(
                lport_id=FAKE_PORT_ID, vif_uuid='fake_cif_id',
                admin_state=True, switch_profile_ids=mock.ANY,
                parent_vif_id=FAKE_VIF_ID, traffic_tag=1,
                tags_update=[{const.SCOPE: const.TAG_HC_SECTION_ID,
                              const.TAG: FAKE_HC_SECTION_ID}],
                vif_type=const.CIF_TYPE, app_id=pod_key,
                allocate_addresses=const.CIF_ALLOCATE_ADDRESSES)

    def test_create_pod_not_create_ingress_rules_and_no_health_check(self):
        self._test_create_pod(create_ingress_rules=False,
                              health_check_ports=[])

    def test_create_pod_create_ingress_rules_and_no_health_check(self):
        self._test_create_pod(create_ingress_rules=True, health_check_ports=[])

    def test_create_pod_not_create_ingress_rules_and_health_check(self):
        self._test_create_pod(create_ingress_rules=False,
                              health_check_ports=[80, 443])

    def test_create_pod_create_ingress_rules_and_health_check(self):
        self._test_create_pod(create_ingress_rules=True,
                              health_check_ports=[80, 443])

    @mock.patch('nsx_ujo.ncp.cache.CoeNSXMapping.get')
    def test_update_pod(self, mock_mapping_get):
        nsgroup_labels = {'foo': 'foo_new_val'}
        pod_info = {
            'attachment_id': 'fake_cif_id',
            'ingress_controller': False,
            'vlan': 1,
            'gateway_ip': '192.168.0.1',
            'port_id': FAKE_PORT_ID,
            'ip': '192.168.0.10/24',
            'mac': 'aa:aa:aa:aa:aa:aa',
            'cif_id': 'fake_cif_id',
            'labels': {'foo': 'foo_val'}}
        mock_mapping_get.return_value = pod_info

        with self._get_patched_nsx_api() as napi:
            napi.update_pod(FAKE_POD, FAKE_PROJECT, FAKE_VIF_ID,
                            nsgroup_labels, True)

        pod_key = utils.get_resource_key(FAKE_PROJECT, FAKE_POD)
        self.mock_port_client.update.assert_called_once_with(
            lport_id=FAKE_PORT_ID, vif_uuid='fake_cif_id',
            admin_state=True, switch_profile_ids=mock.ANY,
            parent_vif_id=FAKE_VIF_ID, traffic_tag=1, tags_update=mock.ANY,
            vif_type=const.CIF_TYPE, app_id=pod_key,
            allocate_addresses=const.CIF_ALLOCATE_ADDRESSES)

    @mock.patch('nsx_ujo.ncp.nsxapi.LOG.warning')
    @mock.patch('nsx_ujo.ncp.cache.CoeNSXMapping.get')
    def test_update_non_existent_pod(self, mock_mapping_get, mock_warning):
        mock_mapping_get.return_value = {}

        with self._get_patched_nsx_api() as napi:
            napi.update_pod(FAKE_POD, FAKE_PROJECT, FAKE_VIF_ID)

        mock_warning.assert_called_once_with('Pod %s has no port on NSX',
                                             FAKE_POD, security=True)

    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._set_ip_pool_status')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._release_ingress_ip')
    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._delete_health_check_rule')
    @mock.patch('nsx_ujo.ncp.cache.CoeNSXMapping.delete')
    @mock.patch('nsx_ujo.ncp.cache.CoeNSXMapping.get')
    def test_delete_pod(self, mock_mapping_get, mock_mapping_delete,
                        mock_delete_health_check_rule,
                        mock_release_ingress_ip, mock_set_ip_pool_status):
        pod_info = {
            'attachment_id': 'fake_cif_id',
            'ingress_controller': True,
            'vlan': 1,
            'gateway_ip': '192.168.0.1',
            'port_id': FAKE_PORT_ID,
            'ip': '192.168.0.10/24',
            'mac': 'aa:aa:aa:aa:aa:aa',
            'cif_id': 'fake_cif_id',
            'hc_section': FAKE_HC_SECTION_ID,
            'labels': {'foo': 'foo_val'}
        }
        fake_ext_ip = {'ip': '10.10.10.10', 'pool_id': 'meh'}
        fake_ext_ip_pool = {'id': 'meh', 'status': 'full'}
        mock_mapping_get.side_effect = [
            pod_info, fake_ext_ip, fake_ext_ip_pool
        ]

        with self._get_patched_nsx_api() as napi:
            napi.delete_pod(FAKE_POD, FAKE_PROJECT, FAKE_VIF_ID)

            mock_delete_health_check_rule.assert_called_once_with(
                FAKE_HC_SECTION_ID)
            self.mock_port_client.delete.assert_called_once_with(FAKE_PORT_ID)
            self.mock_router_lib.delete_fip_nat_rules_by_internal_ip(
                FAKE_TIER0_ROUTER_ID, '192.168.0.10')
            mock_release_ingress_ip.assert_called_once_with(
                fake_ext_ip['ip'], fake_ext_ip['pool_id'])
            mock_set_ip_pool_status.assert_called_once_with(
                fake_ext_ip_pool['id'], 'free')
            pod_key = utils.get_resource_key(FAKE_PROJECT, FAKE_POD)
            mock_mapping_delete.assert_has_calls([
                mock.call(pod_key, parent_key=const.POD),
                mock.call(pod_key, parent_key=const.EXT_IP)])

    @mock.patch('nsx_ujo.ncp.nsxapi.LOG.warning')
    @mock.patch('nsx_ujo.ncp.cache.CoeNSXMapping.get')
    def test_delete_non_existent_pod(self, mock_mapping_get, mock_warning):
        mock_mapping_get.return_value = {}

        with self._get_patched_nsx_api() as napi:
            napi.delete_pod(FAKE_POD, FAKE_PROJECT, FAKE_VIF_ID)

            mock_warning.assert_called_once_with('Pod %s has no port on NSX',
                                                 FAKE_POD)

    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._get_node_vif_id')
    def test_get_node_vif_id(self, mock__get_node_vif_id):
        mock__get_node_vif_id.return_value = FAKE_VIF_ID

        with self._get_patched_nsx_api() as napi:
            self.assertEqual(FAKE_VIF_ID, napi.get_node_vif_id(FAKE_NODE_NAME))
            mock__get_node_vif_id.assert_called_once_with(FAKE_NODE_NAME)

            mock__get_node_vif_id.reset_mock()
            self.assertEqual(FAKE_VIF_ID, napi.get_node_vif_id(FAKE_NODE_NAME))
            mock__get_node_vif_id.assert_not_called()

    @mock.patch('nsx_ujo.ncp.nsxapi.NSXAPI._create_ip_pool')
    def _test_create_project_subnet_if_ip_blocks_exhausted(self,
            mock_create_ip_pool, do_snat):
        self.mock_nsx_lib.ip_block.list.return_value = {
            'results': self._build_ip_blocks()}
        self.mock_nsx_lib.ip_block_subnet.create.return_value = {
            'id': FAKE_SUBNET_ID,
            'allocation_ranges': mock.Mock(),
            'cidr': '192.168.0.0/24'
        }

        with self._get_patched_nsx_api() as napi:
            napi._create_project_subnet(do_snat=do_snat)

            expected_ip_block_id = (
                'mock-ip-block-standard-id0' if do_snat else
                'mock-ip-block-no-snat-id0')
            self.mock_nsx_lib.ip_block_subnet.create.assert_called_once_with(
                expected_ip_block_id, mock.ANY)
            mock_create_ip_pool.assert_called_once_with(expected_ip_block_id,
                netaddr.IPNetwork('192.168.0.0/24'), None, True, None)

    def test_create_nosnat_project_subnet_if_ip_blocks_exhausted(self):
        self._test_create_project_subnet_if_ip_blocks_exhausted(do_snat=False)

    def test_create_snat_project_subnet_if_ip_blocks_exhausted(self):
        self._test_create_project_subnet_if_ip_blocks_exhausted(do_snat=True)
