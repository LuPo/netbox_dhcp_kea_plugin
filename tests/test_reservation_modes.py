#!/usr/bin/env python
"""Tests for reservation mode flags: reservations-global, reservations-in-subnet,
reservations-out-of-pool, and reservations_only on Subnet and DHCPServer."""

from unittest.mock import MagicMock, PropertyMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_ip(ip_str, mac_address="aa:bb:cc:dd:ee:ff", hostname="test-device", dns_name="",
                  is_primary=True, is_oob=False):
    """Build a mock IPAddress with interface, parent, and MAC."""
    mock_interface = MagicMock()
    mock_interface.name = "eth0"
    if mac_address:
        mock_primary_mac = MagicMock()
        mock_primary_mac.mac_address = mac_address
        mock_interface.primary_mac_address = mock_primary_mac
    else:
        mock_interface.primary_mac_address = None
    mock_interface.mac_address = None

    mock_device = MagicMock()
    mock_device.name = hostname
    mock_interface.parent_object = mock_device

    mock_ip_address = MagicMock()
    mock_ip_address.ip = ip_str

    mock_ip = MagicMock()
    mock_ip.assigned_object_type = MagicMock()
    mock_ip.assigned_object_type_id = 999
    mock_ip.is_primary_ip = is_primary
    mock_ip.is_oob_ip = is_oob
    mock_ip.assigned_object = mock_interface
    mock_ip.address = mock_ip_address
    mock_ip.dns_name = dns_name

    return mock_ip


def _make_mock_server(reservations_global=False, reservations_in_subnet=True, reservations_out_of_pool=True):
    """Build a mock DHCPServer with reservation flags."""
    server = MagicMock()
    server.reservations_global = reservations_global
    server.reservations_in_subnet = reservations_in_subnet
    server.reservations_out_of_pool = reservations_out_of_pool
    return server


def _subnet_to_kea(config, reservations=None, pools=None, mock_server=None):
    """Call to_kea_dict() on a Subnet with common mocks in place."""
    from netbox_dhcp_kea_plugin.models import Subnet

    mock_prefix = MagicMock()
    mock_prefix.prefix = MagicMock()
    mock_prefix.prefix.__str__ = MagicMock(return_value="10.0.0.0/24")
    mock_prefix.prefix.version = 4

    # Provide a mock server for effective_* property resolution
    if mock_server is None:
        mock_server = _make_mock_server()

    with patch.object(Subnet, "prefix", new_callable=PropertyMock, return_value=mock_prefix):
        with patch.object(Subnet, "server", new_callable=PropertyMock, return_value=mock_server):
            with patch.object(config, "get_pools", return_value=pools or []):
                mock_option_data = MagicMock()
                mock_option_data.all.return_value = []
                with patch.object(Subnet, "option_data", new_callable=PropertyMock, return_value=mock_option_data):
                    mock_eval = MagicMock()
                    mock_eval.all.return_value = []
                    with patch.object(Subnet, "evaluate_additional_classes", new_callable=PropertyMock, return_value=mock_eval):
                        with patch.object(Subnet, "client_class", new_callable=PropertyMock, return_value=None):
                            config.client_class_id = None
                            with patch.object(config, "get_router_ip", return_value=None):
                                with patch.object(config, "get_kea_reservations", return_value=reservations or []):
                                    return config.to_kea_dict()


SAMPLE_RESERVATIONS = [
    {"ip-address": "10.0.0.10", "hw-address": "aa:bb:cc:dd:ee:ff", "hostname": "host1"},
    {"ip-address": "10.0.0.20", "hw-address": "11:22:33:44:55:66", "hostname": "host2"},
]


# ===========================================================================
# Subnet-level reservation mode flags in to_kea_dict()
# ===========================================================================

class TestSubnetReservationModeFlags:
    """Verify that per-subnet reservation mode flags appear in KEA output
    only when explicitly set (not None)."""

    def test_default_none_flags_omitted_from_output(self):
        """Subnet with None (default) flags should NOT emit them — KEA inherits from Dhcp4."""
        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet(valid_lifetime=3600, max_lifetime=7200)
        result = _subnet_to_kea(config)

        assert "reservations-global" not in result
        assert "reservations-in-subnet" not in result
        assert "reservations-out-of-pool" not in result

    def test_explicit_flags_emitted(self):
        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet(
            valid_lifetime=3600, max_lifetime=7200,
            reservations_global=True,
            reservations_in_subnet=False,
            reservations_out_of_pool=False,
        )
        result = _subnet_to_kea(config)

        assert result["reservations-global"] is True
        assert result["reservations-in-subnet"] is False
        assert result["reservations-out-of-pool"] is False

    def test_flags_all_false(self):
        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet(
            valid_lifetime=3600, max_lifetime=7200,
            reservations_global=False,
            reservations_in_subnet=False,
            reservations_out_of_pool=False,
        )
        result = _subnet_to_kea(config)

        assert result["reservations-global"] is False
        assert result["reservations-in-subnet"] is False
        assert result["reservations-out-of-pool"] is False

    def test_flags_all_true(self):
        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet(
            valid_lifetime=3600, max_lifetime=7200,
            reservations_global=True,
            reservations_in_subnet=True,
            reservations_out_of_pool=True,
        )
        result = _subnet_to_kea(config)

        assert result["reservations-global"] is True
        assert result["reservations-in-subnet"] is True
        assert result["reservations-out-of-pool"] is True

    def test_partial_override_only_emits_set_flags(self):
        """Only the explicitly set flag appears; None flags are omitted."""
        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet(
            valid_lifetime=3600, max_lifetime=7200,
            reservations_global=True,
            reservations_in_subnet=None,
            reservations_out_of_pool=None,
        )
        result = _subnet_to_kea(config)

        assert result["reservations-global"] is True
        assert "reservations-in-subnet" not in result
        assert "reservations-out-of-pool" not in result


# ===========================================================================
# Subnet reservations placement: subnet-level vs global
# ===========================================================================

class TestSubnetReservationPlacement:
    """When reservations_global is False, reservations go into the subnet dict.
    When True, they are omitted (DHCPServer collects them globally)."""

    def test_reservations_in_subnet_dict_when_global_false(self):
        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet(
            valid_lifetime=3600, max_lifetime=7200,
            reservations_global=False,
            reservations_in_subnet=True,
        )
        result = _subnet_to_kea(config, reservations=SAMPLE_RESERVATIONS)

        assert "reservations" in result
        assert len(result["reservations"]) == 2
        assert result["reservations"][0]["ip-address"] == "10.0.0.10"

    def test_reservations_omitted_from_subnet_when_global_true(self):
        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet(
            valid_lifetime=3600, max_lifetime=7200,
            reservations_global=True,
            reservations_in_subnet=False,
        )
        result = _subnet_to_kea(config, reservations=SAMPLE_RESERVATIONS)

        assert "reservations" not in result

    def test_reservations_omitted_when_global_true_and_in_subnet_true(self):
        """Even when both flags are True, subnet-level reservations are omitted
        because they will be placed at global level by DHCPServer."""
        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet(
            valid_lifetime=3600, max_lifetime=7200,
            reservations_global=True,
            reservations_in_subnet=True,
        )
        result = _subnet_to_kea(config, reservations=SAMPLE_RESERVATIONS)

        assert "reservations" not in result

    def test_no_reservations_key_when_empty_and_global_false(self):
        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet(
            valid_lifetime=3600, max_lifetime=7200,
            reservations_global=False,
        )
        result = _subnet_to_kea(config, reservations=[])

        assert "reservations" not in result

    def test_none_global_inherits_false_from_server_includes_reservations(self):
        """When subnet.reservations_global is None and server has global=False,
        effective is False, so reservations go into the subnet dict."""
        from netbox_dhcp_kea_plugin.models import Subnet

        server = _make_mock_server(reservations_global=False)
        config = Subnet(
            valid_lifetime=3600, max_lifetime=7200,
            reservations_global=None,
        )
        result = _subnet_to_kea(config, reservations=SAMPLE_RESERVATIONS, mock_server=server)

        assert "reservations" in result
        assert len(result["reservations"]) == 2

    def test_none_global_inherits_true_from_server_omits_reservations(self):
        """When subnet.reservations_global is None and server has global=True,
        effective is True, so subnet-level reservations are omitted."""
        from netbox_dhcp_kea_plugin.models import Subnet

        server = _make_mock_server(reservations_global=True)
        config = Subnet(
            valid_lifetime=3600, max_lifetime=7200,
            reservations_global=None,
        )
        result = _subnet_to_kea(config, reservations=SAMPLE_RESERVATIONS, mock_server=server)

        assert "reservations" not in result


# ===========================================================================
# Global reservations: get_kea_global_reservations()
# ===========================================================================

class TestSubnetGetKeaGlobalReservations:
    """get_kea_global_reservations() strips ip-address from each reservation."""

    def test_global_reservations_exclude_ip_address(self):
        from django.contrib.contenttypes.models import ContentType

        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet()
        mock_prefix = MagicMock()
        mock_prefix.get_child_ips.return_value = [
            _make_mock_ip("10.0.0.10", mac_address="aa:bb:cc:dd:ee:ff", hostname="host1"),
            _make_mock_ip("10.0.0.20", mac_address="11:22:33:44:55:66", hostname="host2"),
        ]

        with patch.object(Subnet, "prefix", new_callable=PropertyMock, return_value=mock_prefix):
            with patch("netbox_dhcp_kea_plugin.models.ContentType") as mock_ct:
                mock_ct.DoesNotExist = ContentType.DoesNotExist
                mock_ct.objects.get.side_effect = ContentType.DoesNotExist("Not found")
                result = config.get_kea_global_reservations()

        assert len(result) == 2
        for res in result:
            assert "ip-address" not in res
            assert "hw-address" in res
            assert "hostname" in res

    def test_global_reservations_preserves_hw_address_and_hostname(self):
        from django.contrib.contenttypes.models import ContentType

        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet()
        mock_prefix = MagicMock()
        mock_prefix.get_child_ips.return_value = [
            _make_mock_ip("10.0.0.10", mac_address="aa:bb:cc:dd:ee:ff", hostname="host1"),
        ]

        with patch.object(Subnet, "prefix", new_callable=PropertyMock, return_value=mock_prefix):
            with patch("netbox_dhcp_kea_plugin.models.ContentType") as mock_ct:
                mock_ct.DoesNotExist = ContentType.DoesNotExist
                mock_ct.objects.get.side_effect = ContentType.DoesNotExist("Not found")
                result = config.get_kea_global_reservations()

        assert result[0]["hw-address"] == "aa:bb:cc:dd:ee:ff"
        assert result[0]["hostname"] == "host1"

    def test_global_reservations_excludes_entries_without_mac(self):
        from django.contrib.contenttypes.models import ContentType

        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet()
        mock_prefix = MagicMock()
        mock_prefix.get_child_ips.return_value = [
            _make_mock_ip("10.0.0.10", mac_address="aa:bb:cc:dd:ee:ff", hostname="host1"),
            _make_mock_ip("10.0.0.20", mac_address=None, hostname="no-mac-host"),
        ]

        with patch.object(Subnet, "prefix", new_callable=PropertyMock, return_value=mock_prefix):
            with patch("netbox_dhcp_kea_plugin.models.ContentType") as mock_ct:
                mock_ct.DoesNotExist = ContentType.DoesNotExist
                mock_ct.objects.get.side_effect = ContentType.DoesNotExist("Not found")
                result = config.get_kea_global_reservations()

        assert len(result) == 1
        assert result[0]["hw-address"] == "aa:bb:cc:dd:ee:ff"

    def test_global_reservations_empty_when_no_reservations(self):
        from django.contrib.contenttypes.models import ContentType

        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet()
        mock_prefix = MagicMock()
        mock_prefix.get_child_ips.return_value = []

        with patch.object(Subnet, "prefix", new_callable=PropertyMock, return_value=mock_prefix):
            with patch("netbox_dhcp_kea_plugin.models.ContentType") as mock_ct:
                mock_ct.DoesNotExist = ContentType.DoesNotExist
                mock_ct.objects.get.side_effect = ContentType.DoesNotExist("Not found")
                result = config.get_kea_global_reservations()

        assert result == []


# ===========================================================================
# DHCPServer.to_kea_dict() global reservation collection
# ===========================================================================

class TestDHCPServerGlobalReservations:
    """DHCPServer.to_kea_dict() must collect global reservations from subnets
    that have effective reservations_global=True (explicit or inherited) and
    place them in Dhcp4.reservations."""

    def _make_subnet(self, prefix_factory, dhcp_server, network, **kwargs):
        """Create a Subnet and refresh from DB so prefix.prefix is an IPNetwork."""
        from netbox_dhcp_kea_plugin.models import Subnet

        prefix = prefix_factory(network=network)
        subnet = Subnet.objects.create(
            prefix=prefix, server=dhcp_server,
            valid_lifetime=3600, max_lifetime=7200, routers_option_offset=1,
            **kwargs,
        )
        subnet.refresh_from_db()
        return subnet

    def test_server_collects_global_reservations(self, dhcp_server, prefix_factory):
        subnet = self._make_subnet(
            prefix_factory, dhcp_server, "10.0.0.0/24",
            reservations_global=True, reservations_in_subnet=False,
        )

        global_res = [{"hw-address": "aa:bb:cc:dd:ee:ff", "hostname": "host1"}]
        with patch.object(subnet, "get_kea_global_reservations", return_value=global_res):
            with patch.object(subnet, "get_kea_reservations", return_value=[]):
                with patch.object(dhcp_server, "get_effective_subnet_items", return_value=[subnet]):
                    with patch.object(dhcp_server, "get_effective_client_classes", return_value=[]):
                        with patch.object(dhcp_server, "get_effective_option_data", return_value=[]):
                            with patch.object(dhcp_server, "get_hooks_libraries", return_value=[]):
                                with patch.object(dhcp_server, "get_ha_config", return_value=None):
                                    result = dhcp_server.to_kea_dict()

        dhcp4 = result["Dhcp4"]
        assert "reservations" in dhcp4
        assert len(dhcp4["reservations"]) == 1
        assert dhcp4["reservations"][0]["hw-address"] == "aa:bb:cc:dd:ee:ff"
        assert "ip-address" not in dhcp4["reservations"][0]

    def test_server_no_global_reservations_when_all_subnets_in_subnet(self, dhcp_server, prefix_factory):
        subnet = self._make_subnet(
            prefix_factory, dhcp_server, "10.1.0.0/24",
            reservations_global=False, reservations_in_subnet=True,
        )

        with patch.object(subnet, "get_kea_reservations", return_value=[]):
            with patch.object(dhcp_server, "get_effective_subnet_items", return_value=[subnet]):
                with patch.object(dhcp_server, "get_effective_client_classes", return_value=[]):
                    with patch.object(dhcp_server, "get_effective_option_data", return_value=[]):
                        with patch.object(dhcp_server, "get_hooks_libraries", return_value=[]):
                            with patch.object(dhcp_server, "get_ha_config", return_value=None):
                                result = dhcp_server.to_kea_dict()

        dhcp4 = result["Dhcp4"]
        assert "reservations" not in dhcp4

    def test_server_mixes_global_and_in_subnet_reservations(self, dhcp_server, prefix_factory):
        """Some subnets use global reservations, others use in-subnet."""
        subnet_global = self._make_subnet(
            prefix_factory, dhcp_server, "10.0.0.0/24",
            reservations_global=True, reservations_in_subnet=False,
        )
        subnet_local = self._make_subnet(
            prefix_factory, dhcp_server, "10.1.0.0/24",
            reservations_global=False, reservations_in_subnet=True,
        )

        global_res = [{"hw-address": "aa:bb:cc:dd:ee:ff", "hostname": "global-host"}]
        local_res = [{"ip-address": "10.1.0.10", "hw-address": "11:22:33:44:55:66", "hostname": "local-host"}]

        with patch.object(subnet_global, "get_kea_global_reservations", return_value=global_res):
            with patch.object(subnet_global, "get_kea_reservations", return_value=[]):
                with patch.object(subnet_local, "get_kea_reservations", return_value=local_res):
                    with patch.object(dhcp_server, "get_effective_subnet_items", return_value=[subnet_global, subnet_local]):
                        with patch.object(dhcp_server, "get_effective_client_classes", return_value=[]):
                            with patch.object(dhcp_server, "get_effective_option_data", return_value=[]):
                                with patch.object(dhcp_server, "get_hooks_libraries", return_value=[]):
                                    with patch.object(dhcp_server, "get_ha_config", return_value=None):
                                        result = dhcp_server.to_kea_dict()

        dhcp4 = result["Dhcp4"]

        # Global reservations in Dhcp4
        assert "reservations" in dhcp4
        assert len(dhcp4["reservations"]) == 1
        assert dhcp4["reservations"][0]["hostname"] == "global-host"
        assert "ip-address" not in dhcp4["reservations"][0]

        # Local subnet keeps its own reservations
        local_subnet_dict = [s for s in dhcp4["subnet4"] if s["subnet"] == "10.1.0.0/24"][0]
        assert "reservations" in local_subnet_dict
        assert local_subnet_dict["reservations"][0]["ip-address"] == "10.1.0.10"

        # Global subnet must NOT have reservations in its subnet dict
        global_subnet_dict = [s for s in dhcp4["subnet4"] if s["subnet"] == "10.0.0.0/24"][0]
        assert "reservations" not in global_subnet_dict

    def test_server_aggregates_global_reservations_from_multiple_subnets(self, dhcp_server, prefix_factory):
        subnet1 = self._make_subnet(
            prefix_factory, dhcp_server, "10.0.0.0/24",
            reservations_global=True, reservations_in_subnet=False,
        )
        subnet2 = self._make_subnet(
            prefix_factory, dhcp_server, "10.0.1.0/24",
            reservations_global=True, reservations_in_subnet=False,
        )

        res1 = [{"hw-address": "aa:bb:cc:dd:ee:ff", "hostname": "host1"}]
        res2 = [{"hw-address": "11:22:33:44:55:66", "hostname": "host2"}]

        with patch.object(subnet1, "get_kea_global_reservations", return_value=res1):
            with patch.object(subnet1, "get_kea_reservations", return_value=[]):
                with patch.object(subnet2, "get_kea_global_reservations", return_value=res2):
                    with patch.object(subnet2, "get_kea_reservations", return_value=[]):
                        with patch.object(dhcp_server, "get_effective_subnet_items", return_value=[subnet1, subnet2]):
                            with patch.object(dhcp_server, "get_effective_client_classes", return_value=[]):
                                with patch.object(dhcp_server, "get_effective_option_data", return_value=[]):
                                    with patch.object(dhcp_server, "get_hooks_libraries", return_value=[]):
                                        with patch.object(dhcp_server, "get_ha_config", return_value=None):
                                            result = dhcp_server.to_kea_dict()

        dhcp4 = result["Dhcp4"]
        assert len(dhcp4["reservations"]) == 2
        hostnames = {r["hostname"] for r in dhcp4["reservations"]}
        assert hostnames == {"host1", "host2"}

    def test_server_collects_global_reservations_via_inheritance(self, dhcp_server, prefix_factory):
        """Subnet with reservations_global=None inherits from server with global=True."""
        dhcp_server.reservations_global = True
        dhcp_server.save()
        dhcp_server.refresh_from_db()

        subnet = self._make_subnet(
            prefix_factory, dhcp_server, "10.0.0.0/24",
            reservations_global=None,  # inherits True from server
        )

        global_res = [{"hw-address": "aa:bb:cc:dd:ee:ff", "hostname": "inherited-host"}]
        with patch.object(subnet, "get_kea_global_reservations", return_value=global_res):
            with patch.object(subnet, "get_kea_reservations", return_value=[]):
                with patch.object(dhcp_server, "get_effective_subnet_items", return_value=[subnet]):
                    with patch.object(dhcp_server, "get_effective_client_classes", return_value=[]):
                        with patch.object(dhcp_server, "get_effective_option_data", return_value=[]):
                            with patch.object(dhcp_server, "get_hooks_libraries", return_value=[]):
                                with patch.object(dhcp_server, "get_ha_config", return_value=None):
                                    result = dhcp_server.to_kea_dict()

        dhcp4 = result["Dhcp4"]
        assert "reservations" in dhcp4
        assert dhcp4["reservations"][0]["hostname"] == "inherited-host"

    def test_server_no_global_reservations_when_inherited_false(self, dhcp_server, prefix_factory):
        """Subnet with reservations_global=None inherits from server with global=False."""
        dhcp_server.reservations_global = False
        dhcp_server.save()
        dhcp_server.refresh_from_db()

        subnet = self._make_subnet(
            prefix_factory, dhcp_server, "10.0.0.0/24",
            reservations_global=None,  # inherits False from server
        )

        with patch.object(subnet, "get_kea_reservations", return_value=[]):
            with patch.object(dhcp_server, "get_effective_subnet_items", return_value=[subnet]):
                with patch.object(dhcp_server, "get_effective_client_classes", return_value=[]):
                    with patch.object(dhcp_server, "get_effective_option_data", return_value=[]):
                        with patch.object(dhcp_server, "get_hooks_libraries", return_value=[]):
                            with patch.object(dhcp_server, "get_ha_config", return_value=None):
                                result = dhcp_server.to_kea_dict()

        dhcp4 = result["Dhcp4"]
        assert "reservations" not in dhcp4


# ===========================================================================
# DHCPServer global-level reservation mode defaults in Dhcp4
# ===========================================================================

class TestDHCPServerGlobalDefaults:
    """Verify that Dhcp4 block contains the global reservation mode defaults
    from the DHCPServer model fields (not hardcoded)."""

    def _get_dhcp4(self, server):
        """Helper to call to_kea_dict() with all side-effects mocked out."""
        with patch.object(server, "get_effective_subnet_items", return_value=[]):
            with patch.object(server, "get_effective_client_classes", return_value=[]):
                with patch.object(server, "get_effective_option_data", return_value=[]):
                    with patch.object(server, "get_hooks_libraries", return_value=[]):
                        with patch.object(server, "get_ha_config", return_value=None):
                            return server.to_kea_dict()["Dhcp4"]

    def test_server_kea_dict_has_global_reservation_defaults(self, dhcp_server):
        dhcp4 = self._get_dhcp4(dhcp_server)

        assert dhcp4["reservations-global"] is False
        assert dhcp4["reservations-in-subnet"] is True
        assert dhcp4["reservations-out-of-pool"] is True

    def test_server_kea_dict_reflects_custom_reservation_flags(self, dhcp_server):
        """When server reservation flags are changed, to_kea_dict() output follows."""
        dhcp_server.reservations_global = True
        dhcp_server.reservations_in_subnet = False
        dhcp_server.reservations_out_of_pool = False
        dhcp_server.save()
        dhcp_server.refresh_from_db()

        dhcp4 = self._get_dhcp4(dhcp_server)

        assert dhcp4["reservations-global"] is True
        assert dhcp4["reservations-in-subnet"] is False
        assert dhcp4["reservations-out-of-pool"] is False

    def test_server_kea_dict_all_flags_true(self, dhcp_server):
        dhcp_server.reservations_global = True
        dhcp_server.reservations_in_subnet = True
        dhcp_server.reservations_out_of_pool = True
        dhcp_server.save()
        dhcp_server.refresh_from_db()

        dhcp4 = self._get_dhcp4(dhcp_server)

        assert dhcp4["reservations-global"] is True
        assert dhcp4["reservations-in-subnet"] is True
        assert dhcp4["reservations-out-of-pool"] is True

    def test_server_kea_dict_all_flags_false(self, dhcp_server):
        dhcp_server.reservations_global = False
        dhcp_server.reservations_in_subnet = False
        dhcp_server.reservations_out_of_pool = False
        dhcp_server.save()
        dhcp_server.refresh_from_db()

        dhcp4 = self._get_dhcp4(dhcp_server)

        assert dhcp4["reservations-global"] is False
        assert dhcp4["reservations-in-subnet"] is False
        assert dhcp4["reservations-out-of-pool"] is False


# ===========================================================================
# Pool generation: reservations_out_of_pool interaction
# ===========================================================================

class TestPoolGenerationReservationModes:
    """get_pools() behaviour varies with reservations_out_of_pool and reservations_only."""

    def test_reservations_only_returns_empty_pools(self, dhcp_server, prefix_factory):
        from netbox_dhcp_kea_plugin.models import Subnet

        prefix = prefix_factory(network="10.0.0.0/24")
        subnet = Subnet.objects.create(
            prefix=prefix, server=dhcp_server,
            valid_lifetime=3600, max_lifetime=7200, routers_option_offset=1,
            reservations_only=True,
        )

        pools = subnet.get_pools()
        assert pools == []

    def test_out_of_pool_true_uses_available_ips(self, dhcp_server, prefix_factory):
        """reservations_out_of_pool=True uses get_available_ips() which excludes assigned IPs."""
        import netaddr

        from netbox_dhcp_kea_plugin.models import Subnet

        prefix = prefix_factory(network="10.0.0.0/24")
        subnet = Subnet.objects.create(
            prefix=prefix, server=dhcp_server,
            valid_lifetime=3600, max_lifetime=7200, routers_option_offset=1,
            reservations_out_of_pool=True,
            reservations_only=False,
        )

        # Simulate that prefix has no child IP ranges
        with patch.object(prefix, "get_child_ranges") as mock_ranges:
            mock_qs = MagicMock()
            mock_qs.filter.return_value = mock_qs
            mock_qs.exists.return_value = False
            mock_ranges.return_value = mock_qs

            # Mock available IPs — use real IPSet so gateway subtraction works
            available = netaddr.IPSet([
                netaddr.IPNetwork("10.0.0.1/32"),    # .1 (gateway — should be excluded)
                netaddr.IPNetwork("10.0.0.2/31"),    # .2-.3
                netaddr.IPNetwork("10.0.0.5/32"),    # .5 (gap at .4 = assigned)
            ])
            with patch.object(prefix, "get_available_ips", return_value=available):
                pools = subnet.get_pools()

        # Gateway .1 excluded, gap at .4 (assigned IP excluded)
        assert len(pools) == 2
        assert pools[0]["pool"] == "10.0.0.2 - 10.0.0.3"
        assert pools[1]["pool"] == "10.0.0.5 - 10.0.0.5"

    def test_out_of_pool_false_uses_full_usable_range(self, dhcp_server, prefix_factory):
        """reservations_out_of_pool=False generates pool from full usable range,
        excluding only network, broadcast, and gateway."""
        from netbox_dhcp_kea_plugin.models import Subnet

        prefix = prefix_factory(network="10.0.0.0/24")
        subnet = Subnet.objects.create(
            prefix=prefix, server=dhcp_server,
            valid_lifetime=3600, max_lifetime=7200,
            routers_option_offset=1,  # gateway at 10.0.0.1
            reservations_out_of_pool=False,
            reservations_only=False,
        )

        with patch.object(prefix, "get_child_ranges") as mock_ranges:
            mock_qs = MagicMock()
            mock_qs.filter.return_value = mock_qs
            mock_qs.exists.return_value = False
            mock_ranges.return_value = mock_qs

            pools = subnet.get_pools()

        # Full range minus network (.0), broadcast (.255), gateway (.1)
        # Should be split around gateway: .2-.254 (wait, no: .1 is gateway)
        # Actually: usable is .1-.254, gateway is .1, so split into:
        #   nothing before gateway (.1 is first usable)
        #   .2-.254 after gateway
        # But if gateway_int == pool_start, the "before" range is skipped
        assert len(pools) >= 1
        # The range after gateway
        assert any("10.0.0.2" in p["pool"] for p in pools)
        assert any("10.0.0.254" in p["pool"] for p in pools)
        # Gateway should NOT be in any pool
        for p in pools:
            start, end = p["pool"].split(" - ")
            assert start != "10.0.0.1"
            assert end != "10.0.0.1"

    def test_out_of_pool_false_gateway_in_middle(self, dhcp_server, prefix_factory):
        """Gateway in the middle of the range splits pool into two."""
        from netbox_dhcp_kea_plugin.models import Subnet

        prefix = prefix_factory(network="10.0.0.0/24")
        subnet = Subnet.objects.create(
            prefix=prefix, server=dhcp_server,
            valid_lifetime=3600, max_lifetime=7200,
            routers_option_offset=128,  # gateway at 10.0.0.128
            reservations_out_of_pool=False,
            reservations_only=False,
        )

        with patch.object(prefix, "get_child_ranges") as mock_ranges:
            mock_qs = MagicMock()
            mock_qs.filter.return_value = mock_qs
            mock_qs.exists.return_value = False
            mock_ranges.return_value = mock_qs

            pools = subnet.get_pools()

        assert len(pools) == 2
        assert pools[0]["pool"] == "10.0.0.1 - 10.0.0.127"
        assert pools[1]["pool"] == "10.0.0.129 - 10.0.0.254"

    def test_out_of_pool_false_gateway_at_end(self, dhcp_server, prefix_factory):
        """Gateway at the last usable address gives one pool before it."""
        from netbox_dhcp_kea_plugin.models import Subnet

        prefix = prefix_factory(network="10.0.0.0/24")
        subnet = Subnet.objects.create(
            prefix=prefix, server=dhcp_server,
            valid_lifetime=3600, max_lifetime=7200,
            routers_option_offset=254,  # gateway at 10.0.0.254
            reservations_out_of_pool=False,
            reservations_only=False,
        )

        with patch.object(prefix, "get_child_ranges") as mock_ranges:
            mock_qs = MagicMock()
            mock_qs.filter.return_value = mock_qs
            mock_qs.exists.return_value = False
            mock_ranges.return_value = mock_qs

            pools = subnet.get_pools()

        assert len(pools) == 1
        assert pools[0]["pool"] == "10.0.0.1 - 10.0.0.253"

    def test_out_of_pool_false_no_gateway(self, dhcp_server, prefix_factory):
        """No gateway (offset=0) gives one contiguous pool."""
        from netbox_dhcp_kea_plugin.models import Subnet

        prefix = prefix_factory(network="10.0.0.0/24")
        subnet = Subnet.objects.create(
            prefix=prefix, server=dhcp_server,
            valid_lifetime=3600, max_lifetime=7200,
            routers_option_offset=0,
            reservations_out_of_pool=False,
            reservations_only=False,
        )

        with patch.object(prefix, "get_child_ranges") as mock_ranges:
            mock_qs = MagicMock()
            mock_qs.filter.return_value = mock_qs
            mock_qs.exists.return_value = False
            mock_ranges.return_value = mock_qs

            pools = subnet.get_pools()

        assert len(pools) == 1
        assert pools[0]["pool"] == "10.0.0.1 - 10.0.0.254"

    def test_out_of_pool_false_is_pool_prefix(self, dhcp_server, prefix_factory):
        """When prefix.is_pool=True, network and broadcast are included."""
        from netbox_dhcp_kea_plugin.models import Subnet

        prefix = prefix_factory(network="10.0.0.0/24")
        prefix.is_pool = True
        prefix.save()

        subnet = Subnet.objects.create(
            prefix=prefix, server=dhcp_server,
            valid_lifetime=3600, max_lifetime=7200,
            routers_option_offset=1,  # gateway at .1
            reservations_out_of_pool=False,
            reservations_only=False,
        )

        with patch.object(prefix, "get_child_ranges") as mock_ranges:
            mock_qs = MagicMock()
            mock_qs.filter.return_value = mock_qs
            mock_qs.exists.return_value = False
            mock_ranges.return_value = mock_qs

            pools = subnet.get_pools()

        # is_pool includes .0 and .255, split around gateway .1
        assert len(pools) == 2
        assert pools[0]["pool"] == "10.0.0.0 - 10.0.0.0"
        assert pools[1]["pool"] == "10.0.0.2 - 10.0.0.255"

    def test_ip_ranges_take_priority_regardless_of_out_of_pool(self, dhcp_server, prefix_factory):
        """When IP ranges exist, they are always used as pools regardless of
        reservations_out_of_pool setting."""
        import netaddr

        from ipam.models import IPRange

        from netbox_dhcp_kea_plugin.models import Subnet

        prefix = prefix_factory(network="10.50.0.0/24")
        IPRange.objects.create(
            start_address=netaddr.IPNetwork("10.50.0.10/24"),
            end_address=netaddr.IPNetwork("10.50.0.50/24"),
        )

        subnet = Subnet.objects.create(
            prefix=prefix, server=dhcp_server,
            valid_lifetime=3600, max_lifetime=7200,
            routers_option_offset=1,
            reservations_out_of_pool=False,
            reservations_only=False,
        )

        pools = subnet.get_pools()
        assert len(pools) == 1
        assert pools[0]["pool"] == "10.50.0.10 - 10.50.0.50"


# ===========================================================================
# Combined scenarios: full KEA config output verification
# ===========================================================================

class TestReservationModeEndToEnd:
    """End-to-end tests verifying the full KEA config structure for various
    reservation mode combinations at both subnet and global level."""

    def _make_subnet(self, prefix_factory, dhcp_server, network, **kwargs):
        from netbox_dhcp_kea_plugin.models import Subnet

        prefix = prefix_factory(network=network)
        subnet = Subnet.objects.create(
            prefix=prefix, server=dhcp_server,
            valid_lifetime=3600, max_lifetime=7200, routers_option_offset=1,
            **kwargs,
        )
        subnet.refresh_from_db()
        return subnet

    def test_default_mode_reservations_in_subnet_with_out_of_pool(self, dhcp_server, prefix_factory):
        """Default: reservations_in_subnet=True, reservations_out_of_pool=True.
        Reservations in subnet4, excluded from pools, no global reservations."""
        subnet = self._make_subnet(
            prefix_factory, dhcp_server, "10.0.0.0/24",
            reservations_global=False, reservations_in_subnet=True, reservations_out_of_pool=True,
        )

        local_res = [{"ip-address": "10.0.0.10", "hw-address": "aa:bb:cc:dd:ee:ff", "hostname": "host1"}]

        with patch.object(subnet, "get_kea_reservations", return_value=local_res):
            with patch.object(dhcp_server, "get_effective_subnet_items", return_value=[subnet]):
                with patch.object(dhcp_server, "get_effective_client_classes", return_value=[]):
                    with patch.object(dhcp_server, "get_effective_option_data", return_value=[]):
                        with patch.object(dhcp_server, "get_hooks_libraries", return_value=[]):
                            with patch.object(dhcp_server, "get_ha_config", return_value=None):
                                result = dhcp_server.to_kea_dict()

        dhcp4 = result["Dhcp4"]

        # Global level: defaults
        assert dhcp4["reservations-global"] is False
        assert dhcp4["reservations-in-subnet"] is True
        assert dhcp4["reservations-out-of-pool"] is True
        assert "reservations" not in dhcp4  # No global reservations

        # Subnet level
        subnet_dict = dhcp4["subnet4"][0]
        assert subnet_dict["reservations-global"] is False
        assert subnet_dict["reservations-in-subnet"] is True
        assert subnet_dict["reservations-out-of-pool"] is True
        assert "reservations" in subnet_dict
        assert subnet_dict["reservations"][0]["ip-address"] == "10.0.0.10"

    def test_global_mode_reservations_at_dhcp4_level(self, dhcp_server, prefix_factory):
        """reservations_global=True: reservations at Dhcp4 level without ip-address,
        none at subnet level."""
        subnet = self._make_subnet(
            prefix_factory, dhcp_server, "10.0.0.0/24",
            reservations_global=True, reservations_in_subnet=False, reservations_out_of_pool=True,
        )

        global_res = [{"hw-address": "aa:bb:cc:dd:ee:ff", "hostname": "host1"}]

        with patch.object(subnet, "get_kea_global_reservations", return_value=global_res):
            with patch.object(subnet, "get_kea_reservations", return_value=[]):
                with patch.object(dhcp_server, "get_effective_subnet_items", return_value=[subnet]):
                    with patch.object(dhcp_server, "get_effective_client_classes", return_value=[]):
                        with patch.object(dhcp_server, "get_effective_option_data", return_value=[]):
                            with patch.object(dhcp_server, "get_hooks_libraries", return_value=[]):
                                with patch.object(dhcp_server, "get_ha_config", return_value=None):
                                    result = dhcp_server.to_kea_dict()

        dhcp4 = result["Dhcp4"]

        # Global reservations present
        assert "reservations" in dhcp4
        assert len(dhcp4["reservations"]) == 1
        assert "ip-address" not in dhcp4["reservations"][0]

        # Subnet has flags but no reservations
        subnet_dict = dhcp4["subnet4"][0]
        assert subnet_dict["reservations-global"] is True
        assert subnet_dict["reservations-in-subnet"] is False
        assert "reservations" not in subnet_dict

    def test_in_subnet_false_no_reservations_anywhere(self, dhcp_server, prefix_factory):
        """reservations_in_subnet=False, reservations_global=False:
        Reservations are ignored entirely — no reservations in output."""
        subnet = self._make_subnet(
            prefix_factory, dhcp_server, "10.0.0.0/24",
            reservations_global=False, reservations_in_subnet=False, reservations_out_of_pool=False,
        )

        # Even though we have reservations data, with global=False the subnet
        # to_kea_dict will include them (it only skips when global=True).
        # But KEA will ignore them at runtime due to in_subnet=False.
        # The flag is what controls KEA behaviour, not the data presence.
        local_res = [{"ip-address": "10.0.0.10", "hw-address": "aa:bb:cc:dd:ee:ff", "hostname": "host1"}]

        with patch.object(subnet, "get_kea_reservations", return_value=local_res):
            with patch.object(dhcp_server, "get_effective_subnet_items", return_value=[subnet]):
                with patch.object(dhcp_server, "get_effective_client_classes", return_value=[]):
                    with patch.object(dhcp_server, "get_effective_option_data", return_value=[]):
                        with patch.object(dhcp_server, "get_hooks_libraries", return_value=[]):
                            with patch.object(dhcp_server, "get_ha_config", return_value=None):
                                result = dhcp_server.to_kea_dict()

        dhcp4 = result["Dhcp4"]

        # No global reservations
        assert "reservations" not in dhcp4

        # Subnet still has reservations data (KEA ignores via flags)
        subnet_dict = dhcp4["subnet4"][0]
        assert subnet_dict["reservations-in-subnet"] is False
        assert subnet_dict["reservations-global"] is False
        assert "reservations" in subnet_dict  # data present, KEA ignores it

    def test_mixed_subnets_different_modes(self, dhcp_server, prefix_factory):
        """Server with one global-reservation subnet and one in-subnet reservation subnet.
        Verifies each subnet's flags and reservation placement are independent."""
        subnet_a = self._make_subnet(
            prefix_factory, dhcp_server, "10.0.0.0/24",
            reservations_global=True, reservations_in_subnet=False, reservations_out_of_pool=True,
        )
        subnet_b = self._make_subnet(
            prefix_factory, dhcp_server, "10.1.0.0/24",
            reservations_global=False, reservations_in_subnet=True, reservations_out_of_pool=False,
        )

        global_res = [{"hw-address": "aa:bb:cc:dd:ee:ff", "hostname": "global-host"}]
        local_res = [{"ip-address": "10.1.0.10", "hw-address": "11:22:33:44:55:66", "hostname": "local-host"}]

        with patch.object(subnet_a, "get_kea_global_reservations", return_value=global_res):
            with patch.object(subnet_a, "get_kea_reservations", return_value=[]):
                with patch.object(subnet_b, "get_kea_reservations", return_value=local_res):
                    with patch.object(dhcp_server, "get_effective_subnet_items", return_value=[subnet_a, subnet_b]):
                        with patch.object(dhcp_server, "get_effective_client_classes", return_value=[]):
                            with patch.object(dhcp_server, "get_effective_option_data", return_value=[]):
                                with patch.object(dhcp_server, "get_hooks_libraries", return_value=[]):
                                    with patch.object(dhcp_server, "get_ha_config", return_value=None):
                                        result = dhcp_server.to_kea_dict()

        dhcp4 = result["Dhcp4"]

        # Global level
        assert len(dhcp4["reservations"]) == 1
        assert dhcp4["reservations"][0]["hostname"] == "global-host"
        assert "ip-address" not in dhcp4["reservations"][0]

        # Subnet A: global mode, no subnet-level reservations
        sa = [s for s in dhcp4["subnet4"] if s["subnet"] == "10.0.0.0/24"][0]
        assert sa["reservations-global"] is True
        assert sa["reservations-in-subnet"] is False
        assert "reservations" not in sa

        # Subnet B: in-subnet mode, has reservations with ip-address
        sb = [s for s in dhcp4["subnet4"] if s["subnet"] == "10.1.0.0/24"][0]
        assert sb["reservations-global"] is False
        assert sb["reservations-in-subnet"] is True
        assert sb["reservations-out-of-pool"] is False
        assert "reservations" in sb
        assert sb["reservations"][0]["ip-address"] == "10.1.0.10"

    def test_server_level_flags_override_in_dhcp4_block(self, dhcp_server, prefix_factory):
        """Server-level reservation flags appear in the Dhcp4 global block,
        independent of subnet-level flags."""
        dhcp_server.reservations_global = True
        dhcp_server.reservations_in_subnet = False
        dhcp_server.reservations_out_of_pool = False
        dhcp_server.save()
        dhcp_server.refresh_from_db()

        # Subnet has different flags than server
        subnet = self._make_subnet(
            prefix_factory, dhcp_server, "10.0.0.0/24",
            reservations_global=False, reservations_in_subnet=True, reservations_out_of_pool=True,
        )

        local_res = [{"ip-address": "10.0.0.10", "hw-address": "aa:bb:cc:dd:ee:ff", "hostname": "host1"}]

        with patch.object(subnet, "get_kea_reservations", return_value=local_res):
            with patch.object(dhcp_server, "get_effective_subnet_items", return_value=[subnet]):
                with patch.object(dhcp_server, "get_effective_client_classes", return_value=[]):
                    with patch.object(dhcp_server, "get_effective_option_data", return_value=[]):
                        with patch.object(dhcp_server, "get_hooks_libraries", return_value=[]):
                            with patch.object(dhcp_server, "get_ha_config", return_value=None):
                                result = dhcp_server.to_kea_dict()

        dhcp4 = result["Dhcp4"]

        # Server-level flags in Dhcp4 block
        assert dhcp4["reservations-global"] is True
        assert dhcp4["reservations-in-subnet"] is False
        assert dhcp4["reservations-out-of-pool"] is False

        # Subnet-level flags are independent (per-subnet override)
        subnet_dict = dhcp4["subnet4"][0]
        assert subnet_dict["reservations-global"] is False
        assert subnet_dict["reservations-in-subnet"] is True
        assert subnet_dict["reservations-out-of-pool"] is True
        assert "reservations" in subnet_dict
