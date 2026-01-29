#!/usr/bin/env python
"""Tests for netbox_dhcp_kea_plugin models."""

from unittest.mock import MagicMock, patch


class TestClientClassKeaOutput:
    """Test ClientClass KEA configuration output methods."""

    def test_has_option43_data_false_when_no_option_data(self):
        """Test has_option43_data returns False when no option data."""
        from netbox_dhcp_kea_plugin.models import ClientClass

        client_class = ClientClass(name="test", test_expression="test")
        # Mock the option_data manager's filter method
        with patch.object(ClientClass, "option_data", create=True) as mock_option_data:
            mock_manager = MagicMock()
            mock_manager.filter.return_value.exists.return_value = False
            type(client_class).option_data = mock_manager

            assert client_class.has_option43_data() == False

    def test_has_option43_data_true_when_option43_exists(self):
        """Test has_option43_data returns True when option43 delivery type exists."""
        from netbox_dhcp_kea_plugin.models import ClientClass

        client_class = ClientClass(name="test", test_expression="test")
        with patch.object(ClientClass, "option_data", create=True) as mock_option_data:
            mock_manager = MagicMock()
            mock_manager.filter.return_value.exists.return_value = True
            type(client_class).option_data = mock_manager

            assert client_class.has_option43_data() == True

    def test_get_kea_option_defs_empty_when_no_option43(self):
        """Test get_kea_option_defs returns empty list when no option43 data."""
        from netbox_dhcp_kea_plugin.models import ClientClass

        client_class = ClientClass(name="test", test_expression="test", local_definitions=False)

        with patch.object(client_class, "has_option43_data", return_value=False):
            with patch.object(client_class, "get_option_definitions", return_value=[]):
                result = client_class.get_kea_option_defs()

        assert result == []

    def test_get_kea_option_defs_includes_vendor_encapsulated_options(self):
        """Test get_kea_option_defs includes vendor-encapsulated-options when has option43."""
        from netbox_dhcp_kea_plugin.models import ClientClass, VendorOptionSpace

        vendor_space = MagicMock(spec=VendorOptionSpace)
        vendor_space.name = "MSUCClient"

        client_class = ClientClass(name="test", test_expression="test", local_definitions=False)

        # Mock the methods that access option_data
        with patch.object(client_class, "has_option43_data", return_value=True):
            with patch.object(client_class, "get_option43_vendor_spaces", return_value=[vendor_space]):
                with patch.object(client_class, "get_option_definitions", return_value=[]):
                    result = client_class.get_kea_option_defs()

        assert len(result) == 1
        assert result[0]["name"] == "vendor-encapsulated-options"
        assert result[0]["code"] == 43
        assert result[0]["type"] == "empty"
        assert result[0]["encapsulate"] == "MSUCClient"

    def test_get_kea_option_defs_includes_definitions_when_local(self):
        """Test get_kea_option_defs includes definitions when local_definitions=True."""
        from netbox_dhcp_kea_plugin.models import ClientClass, OptionDefinition

        definition = MagicMock(spec=OptionDefinition)
        definition.name = "UCIdentifier"
        definition.code = 1
        definition.option_type = "string"
        definition.is_array = False
        definition.encapsulate = None
        definition.record_types = None
        definition.vendor_option_space = MagicMock()
        definition.vendor_option_space.name = "MSUCClient"

        client_class = ClientClass(name="test", test_expression="test", local_definitions=True)

        with patch.object(client_class, "has_option43_data", return_value=False):
            with patch.object(client_class, "get_option43_vendor_spaces", return_value=[]):
                with patch.object(client_class, "get_option_definitions", return_value=[definition]):
                    result = client_class.get_kea_option_defs()

        assert len(result) == 1
        assert result[0]["name"] == "UCIdentifier"
        assert result[0]["code"] == 1
        assert result[0]["type"] == "string"
        assert result[0]["space"] == "MSUCClient"

    def test_to_kea_dict_basic_structure(self):
        """Test to_kea_dict returns correct basic structure."""
        from netbox_dhcp_kea_plugin.models import ClientClass

        client_class = ClientClass(
            name="MS-UC-Client", test_expression="option[60].hex == 'MS-UC-Client'", local_definitions=False
        )

        with patch.object(client_class, "get_kea_option_defs", return_value=[]):
            with patch.object(client_class, "get_kea_option_data", return_value=[]):
                result = client_class.to_kea_dict()

        assert result["name"] == "MS-UC-Client"
        assert result["test"] == "option[60].hex == 'MS-UC-Client'"
        assert "option-def" not in result
        assert "option-data" not in result

    def test_to_kea_dict_includes_option_def(self):
        """Test to_kea_dict includes option-def when present."""
        from netbox_dhcp_kea_plugin.models import ClientClass

        option_defs = [
            {"name": "vendor-encapsulated-options", "code": 43, "type": "empty", "encapsulate": "MSUCClient"}
        ]

        client_class = ClientClass(
            name="MS-UC-Client", test_expression="option[60].hex == 'MS-UC-Client'", local_definitions=True
        )

        with patch.object(client_class, "get_kea_option_defs", return_value=option_defs):
            with patch.object(client_class, "get_kea_option_data", return_value=[]):
                result = client_class.to_kea_dict()

        assert "option-def" in result
        assert result["option-def"] == option_defs

    def test_to_kea_dict_includes_option_data(self):
        """Test to_kea_dict includes option-data when present."""
        from netbox_dhcp_kea_plugin.models import ClientClass

        option_data = [{"name": "vendor-encapsulated-options", "code": 43}]

        client_class = ClientClass(
            name="MS-UC-Client", test_expression="option[60].hex == 'MS-UC-Client'", local_definitions=False
        )

        with patch.object(client_class, "get_kea_option_defs", return_value=[]):
            with patch.object(client_class, "get_kea_option_data", return_value=option_data):
                result = client_class.to_kea_dict()

        assert "option-data" in result
        assert result["option-data"] == option_data

    def test_to_kea_dict_includes_pxe_fields(self):
        """Test to_kea_dict includes PXE boot fields when set."""
        from netbox_dhcp_kea_plugin.models import ClientClass

        client_class = ClientClass(
            name="PXE-Client",
            test_expression="option[60].hex == 'PXEClient'",
            local_definitions=False,
            next_server="192.168.1.1",
            server_hostname="pxeserver",
            boot_file_name="pxelinux.0",
        )

        with patch.object(client_class, "get_kea_option_defs", return_value=[]):
            with patch.object(client_class, "get_kea_option_data", return_value=[]):
                result = client_class.to_kea_dict()

        assert result["next-server"] == "192.168.1.1"
        assert result["server-hostname"] == "pxeserver"
        assert result["boot-file-name"] == "pxelinux.0"

    def test_get_kea_option_data_hex_format(self):
        """Test get_kea_option_data returns hex format with csv-format=false."""
        from netbox_dhcp_kea_plugin.models import ClientClass, OptionData

        opt = MagicMock(spec=OptionData)
        opt.name = "UCIdentifier"
        opt.code = 1
        opt.data = "68:74:74:70:73"
        opt.ascii_data = "https"
        opt.delivery_type = "option43"
        opt.vendor_option_space = MagicMock()
        opt.vendor_option_space.name = "MSUCClient"
        opt.always_send = False

        client_class = ClientClass(name="test", test_expression="test")

        with patch.object(client_class, "has_option43_data", return_value=False):
            with patch.object(client_class, "has_vivso_data", return_value=False):
                with patch.object(client_class, "get_option_data_sorted", return_value=[opt]):
                    result = client_class.get_kea_option_data(ascii_format=False)

        assert len(result) == 1
        assert result[0]["data"] == "68:74:74:70:73"
        assert result[0]["csv-format"] == False

    def test_get_kea_option_data_ascii_format(self):
        """Test get_kea_option_data returns ascii format with csv-format=true."""
        from netbox_dhcp_kea_plugin.models import ClientClass, OptionData

        opt = MagicMock(spec=OptionData)
        opt.name = "UCIdentifier"
        opt.code = 1
        opt.data = "68:74:74:70:73"
        opt.ascii_data = "https"
        opt.delivery_type = "option43"
        opt.vendor_option_space = MagicMock()
        opt.vendor_option_space.name = "MSUCClient"
        opt.always_send = False

        client_class = ClientClass(name="test", test_expression="test")

        with patch.object(client_class, "has_option43_data", return_value=False):
            with patch.object(client_class, "has_vivso_data", return_value=False):
                with patch.object(client_class, "get_option_data_sorted", return_value=[opt]):
                    result = client_class.get_kea_option_data(ascii_format=True)

        assert len(result) == 1
        assert result[0]["data"] == "https"
        assert result[0]["csv-format"] == True

    def test_get_kea_option_data_prepends_vendor_encapsulated_options(self):
        """Test get_kea_option_data prepends vendor-encapsulated-options when has option43."""
        from netbox_dhcp_kea_plugin.models import ClientClass

        client_class = ClientClass(name="test", test_expression="test")

        with patch.object(client_class, "has_option43_data", return_value=True):
            with patch.object(client_class, "has_vivso_data", return_value=False):
                with patch.object(client_class, "get_option_data_sorted", return_value=[]):
                    result = client_class.get_kea_option_data()

        assert len(result) == 1
        assert result[0]["name"] == "vendor-encapsulated-options"
        assert result[0]["code"] == 43

    def test_has_vivso_data_false_when_no_vivso_option_data(self):
        """Test has_vivso_data returns False when no vivso delivery type option data."""
        from netbox_dhcp_kea_plugin.models import ClientClass

        client_class = ClientClass(name="test", test_expression="test")
        with patch.object(ClientClass, "option_data", create=True) as mock_option_data:
            mock_manager = MagicMock()
            mock_manager.filter.return_value.exists.return_value = False
            type(client_class).option_data = mock_manager

            assert client_class.has_vivso_data() == False

    def test_has_vivso_data_true_when_vivso_exists(self):
        """Test has_vivso_data returns True when vivso delivery type exists."""
        from netbox_dhcp_kea_plugin.models import ClientClass

        client_class = ClientClass(name="test", test_expression="test")
        with patch.object(ClientClass, "option_data", create=True) as mock_option_data:
            mock_manager = MagicMock()
            mock_manager.filter.return_value.exists.return_value = True
            type(client_class).option_data = mock_manager

            assert client_class.has_vivso_data() == True

    def test_get_kea_option_data_includes_vivso_suboptions(self):
        """Test get_kea_option_data includes vivso-suboptions when has vivso data."""
        from netbox_dhcp_kea_plugin.models import ClientClass, VendorOptionSpace

        vendor_space = MagicMock(spec=VendorOptionSpace)
        vendor_space.enterprise_id = 171

        client_class = ClientClass(name="test", test_expression="test")

        with patch.object(client_class, "has_option43_data", return_value=False):
            with patch.object(client_class, "has_vivso_data", return_value=True):
                with patch.object(client_class, "get_vivso_vendor_spaces", return_value=[vendor_space]):
                    with patch.object(client_class, "get_option_data_sorted", return_value=[]):
                        result = client_class.get_kea_option_data()

        assert len(result) == 1
        assert result[0]["name"] == "vivso-suboptions"
        assert result[0]["data"] == "171"

    def test_get_kea_option_data_includes_multiple_vivso_suboptions(self):
        """Test get_kea_option_data includes multiple vivso-suboptions for different enterprise IDs."""
        from netbox_dhcp_kea_plugin.models import ClientClass, VendorOptionSpace

        vendor_space1 = MagicMock(spec=VendorOptionSpace)
        vendor_space1.enterprise_id = 171

        vendor_space2 = MagicMock(spec=VendorOptionSpace)
        vendor_space2.enterprise_id = 9

        client_class = ClientClass(name="test", test_expression="test")

        with patch.object(client_class, "has_option43_data", return_value=False):
            with patch.object(client_class, "has_vivso_data", return_value=True):
                with patch.object(client_class, "get_vivso_vendor_spaces", return_value=[vendor_space1, vendor_space2]):
                    with patch.object(client_class, "get_option_data_sorted", return_value=[]):
                        result = client_class.get_kea_option_data()

        assert len(result) == 2
        assert result[0]["name"] == "vivso-suboptions"
        assert result[0]["data"] == "171"
        assert result[1]["name"] == "vivso-suboptions"
        assert result[1]["data"] == "9"

    def test_get_kea_option_data_skips_vivso_without_enterprise_id(self):
        """Test get_kea_option_data skips vivso-suboptions when vendor space has no enterprise ID."""
        from netbox_dhcp_kea_plugin.models import ClientClass, VendorOptionSpace

        vendor_space = MagicMock(spec=VendorOptionSpace)
        vendor_space.enterprise_id = None

        client_class = ClientClass(name="test", test_expression="test")

        with patch.object(client_class, "has_option43_data", return_value=False):
            with patch.object(client_class, "has_vivso_data", return_value=True):
                with patch.object(client_class, "get_vivso_vendor_spaces", return_value=[vendor_space]):
                    with patch.object(client_class, "get_option_data_sorted", return_value=[]):
                        result = client_class.get_kea_option_data()

        assert len(result) == 0

    def test_get_kea_option_data_vivso_option_uses_vendor_space(self):
        """Test get_kea_option_data sets correct space for vivso delivery type options."""
        from netbox_dhcp_kea_plugin.models import ClientClass, OptionData, VendorOptionSpace

        vendor_space = MagicMock(spec=VendorOptionSpace)
        vendor_space.enterprise_id = 171
        vendor_space.name = "polycom-options"

        opt = MagicMock(spec=OptionData)
        opt.name = "PolycomConfig"
        opt.code = 1
        opt.data = "http://server/config"
        opt.ascii_data = "http://server/config"
        opt.delivery_type = "vivso"
        opt.vendor_option_space = vendor_space
        opt.always_send = False

        client_class = ClientClass(name="test", test_expression="test")

        with patch.object(client_class, "has_option43_data", return_value=False):
            with patch.object(client_class, "has_vivso_data", return_value=True):
                with patch.object(client_class, "get_vivso_vendor_spaces", return_value=[vendor_space]):
                    with patch.object(client_class, "get_option_data_sorted", return_value=[opt]):
                        result = client_class.get_kea_option_data(ascii_format=False)

        # First entry is vivso-suboptions
        assert result[0]["name"] == "vivso-suboptions"
        assert result[0]["data"] == "171"

        # Second entry is the actual option with vendor-<enterprise_id> space
        assert result[1]["name"] == "PolycomConfig"
        assert result[1]["space"] == "vendor-171"
        assert result[1]["code"] == 1

    def test_to_kea_json_returns_valid_json(self):
        """Test to_kea_json returns valid JSON string."""
        import json

        from netbox_dhcp_kea_plugin.models import ClientClass

        client_class = ClientClass(name="MS-UC-Client", test_expression="option[60].hex == 'MS-UC-Client'")

        with patch.object(client_class, "get_kea_option_defs", return_value=[]):
            with patch.object(client_class, "get_kea_option_data", return_value=[]):
                result = client_class.to_kea_json()

        # Should not raise
        parsed = json.loads(result)
        assert parsed["name"] == "MS-UC-Client"


class TestDHCPServerKeaOutput:
    """Test DHCPServer KEA configuration output methods."""

    def test_excludes_local_definitions_from_global_option_def(self):
        """Test that definitions with local_definitions=True are excluded from global option-def."""
        # This test would require more complex setup with database models
        # For now, we just document the expected behavior
        pass


class TestPrefixDHCPConfigReservations:
    """Test PrefixDHCPConfig reservation methods."""

    def test_get_reservations_returns_empty_list_when_no_ips(self):
        """Test get_reservations returns empty list when prefix has no child IPs."""
        from unittest.mock import MagicMock, PropertyMock

        from netbox_dhcp_kea_plugin.models import PrefixDHCPConfig

        config = PrefixDHCPConfig()
        mock_prefix = MagicMock()
        mock_prefix.get_child_ips.return_value = []
        config.prefix = mock_prefix

        result = config.get_reservations()

        assert result == []

    def test_get_reservations_skips_ips_without_assigned_object(self):
        """Test get_reservations skips IPs without assigned_object_type."""
        from unittest.mock import MagicMock

        from netbox_dhcp_kea_plugin.models import PrefixDHCPConfig

        config = PrefixDHCPConfig()
        mock_prefix = MagicMock()

        mock_ip = MagicMock()
        mock_ip.assigned_object_type = None

        mock_prefix.get_child_ips.return_value = [mock_ip]
        config.prefix = mock_prefix

        result = config.get_reservations()

        assert result == []

    def test_get_reservations_skips_non_primary_non_oob_ips(self):
        """Test get_reservations skips IPs that are not primary or OOB."""
        from unittest.mock import MagicMock

        from netbox_dhcp_kea_plugin.models import PrefixDHCPConfig

        config = PrefixDHCPConfig()
        mock_prefix = MagicMock()

        mock_ip = MagicMock()
        mock_ip.assigned_object_type = MagicMock()
        mock_ip.assigned_object_type_id = 999  # Not FHRP
        mock_ip.is_primary_ip = False
        mock_ip.is_oob_ip = False

        mock_prefix.get_child_ips.return_value = [mock_ip]
        config.prefix = mock_prefix

        result = config.get_reservations()

        assert result == []

    def test_get_reservations_includes_primary_ip(self):
        """Test get_reservations includes IPs marked as primary."""
        from unittest.mock import MagicMock, patch

        from netbox_dhcp_kea_plugin.models import PrefixDHCPConfig

        config = PrefixDHCPConfig()
        mock_prefix = MagicMock()

        mock_interface = MagicMock()
        mock_interface.name = "eth0"
        mock_interface.mac_address = "aa:bb:cc:dd:ee:ff"

        mock_device = MagicMock()
        mock_device.name = "test-device"
        mock_interface.parent_object = mock_device

        mock_ip_address = MagicMock()
        mock_ip_address.ip = "192.168.1.10"

        mock_ip = MagicMock()
        mock_ip.assigned_object_type = MagicMock()
        mock_ip.assigned_object_type_id = 999  # Not FHRP
        mock_ip.is_primary_ip = True
        mock_ip.is_oob_ip = False
        mock_ip.assigned_object = mock_interface
        mock_ip.address = mock_ip_address
        mock_ip.dns_name = ""

        mock_prefix.get_child_ips.return_value = [mock_ip]
        config.prefix = mock_prefix

        with patch("netbox_dhcp_kea_plugin.models.ContentType") as mock_ct:
            mock_ct.objects.get.side_effect = Exception("Not found")

            result = config.get_reservations()

        assert len(result) == 1
        kea_res, metadata = result[0]
        assert kea_res["ip-address"] == "192.168.1.10"
        assert kea_res["hw-address"] == "aa:bb:cc:dd:ee:ff"
        assert kea_res["hostname"] == "test-device"
        assert metadata["is_primary"] is True

    def test_get_reservations_includes_oob_ip_with_interface_name(self):
        """Test get_reservations includes OOB IPs with interface name in hostname."""
        from unittest.mock import MagicMock, patch

        from netbox_dhcp_kea_plugin.models import PrefixDHCPConfig

        config = PrefixDHCPConfig()
        mock_prefix = MagicMock()

        mock_interface = MagicMock()
        mock_interface.name = "mgmt0/1"
        mock_interface.mac_address = "11:22:33:44:55:66"

        mock_device = MagicMock()
        mock_device.name = "oob-device"
        mock_interface.parent_object = mock_device

        mock_ip_address = MagicMock()
        mock_ip_address.ip = "10.0.0.5"

        mock_ip = MagicMock()
        mock_ip.assigned_object_type = MagicMock()
        mock_ip.assigned_object_type_id = 999  # Not FHRP
        mock_ip.is_primary_ip = False
        mock_ip.is_oob_ip = True
        mock_ip.assigned_object = mock_interface
        mock_ip.address = mock_ip_address
        mock_ip.dns_name = ""

        mock_prefix.get_child_ips.return_value = [mock_ip]
        config.prefix = mock_prefix

        with patch("netbox_dhcp_kea_plugin.models.ContentType") as mock_ct:
            mock_ct.objects.get.side_effect = Exception("Not found")

            result = config.get_reservations()

        assert len(result) == 1
        kea_res, metadata = result[0]
        assert kea_res["ip-address"] == "10.0.0.5"
        # Interface name should be cleaned: / -> -, . -> -
        assert kea_res["hostname"] == "oob-device_mgmt0-1"
        assert metadata["is_oob"] is True

    def test_get_reservations_uses_dns_name_for_hostname(self):
        """Test get_reservations uses first part of dns_name for hostname."""
        from unittest.mock import MagicMock, patch

        from netbox_dhcp_kea_plugin.models import PrefixDHCPConfig

        config = PrefixDHCPConfig()
        mock_prefix = MagicMock()

        mock_interface = MagicMock()
        mock_interface.name = "eth0"
        mock_interface.mac_address = "aa:bb:cc:dd:ee:ff"

        mock_device = MagicMock()
        mock_device.name = "long-device-name"
        mock_interface.parent_object = mock_device

        mock_ip_address = MagicMock()
        mock_ip_address.ip = "192.168.1.20"

        mock_ip = MagicMock()
        mock_ip.assigned_object_type = MagicMock()
        mock_ip.assigned_object_type_id = 999
        mock_ip.is_primary_ip = True
        mock_ip.is_oob_ip = False
        mock_ip.assigned_object = mock_interface
        mock_ip.address = mock_ip_address
        mock_ip.dns_name = "short.subdomain.example.com"

        mock_prefix.get_child_ips.return_value = [mock_ip]
        config.prefix = mock_prefix

        with patch("netbox_dhcp_kea_plugin.models.ContentType") as mock_ct:
            mock_ct.objects.get.side_effect = Exception("Not found")

            result = config.get_reservations()

        assert len(result) == 1
        kea_res, _ = result[0]
        assert kea_res["hostname"] == "short"

    def test_get_kea_reservations_returns_only_kea_dicts(self):
        """Test get_kea_reservations returns only KEA dicts without metadata."""
        from unittest.mock import MagicMock, patch

        from netbox_dhcp_kea_plugin.models import PrefixDHCPConfig

        config = PrefixDHCPConfig()
        mock_prefix = MagicMock()

        mock_interface = MagicMock()
        mock_interface.name = "eth0"
        mock_interface.mac_address = "aa:bb:cc:dd:ee:ff"

        mock_device = MagicMock()
        mock_device.name = "test-device"
        mock_interface.parent_object = mock_device

        mock_ip_address = MagicMock()
        mock_ip_address.ip = "192.168.1.30"

        mock_ip = MagicMock()
        mock_ip.assigned_object_type = MagicMock()
        mock_ip.assigned_object_type_id = 999
        mock_ip.is_primary_ip = True
        mock_ip.is_oob_ip = False
        mock_ip.assigned_object = mock_interface
        mock_ip.address = mock_ip_address
        mock_ip.dns_name = ""

        mock_prefix.get_child_ips.return_value = [mock_ip]
        config.prefix = mock_prefix

        with patch("netbox_dhcp_kea_plugin.models.ContentType") as mock_ct:
            mock_ct.objects.get.side_effect = Exception("Not found")

            result = config.get_kea_reservations()

        assert len(result) == 1
        assert isinstance(result[0], dict)
        assert "ip-address" in result[0]
        # Should not contain metadata
        assert "is_primary" not in result[0]

    def test_to_kea_dict_includes_reservations(self):
        """Test to_kea_dict includes reservations in output."""
        from unittest.mock import MagicMock, patch

        from netbox_dhcp_kea_plugin.models import PrefixDHCPConfig

        config = PrefixDHCPConfig()
        config.valid_lifetime = 3600
        config.max_lifetime = 7200

        mock_prefix = MagicMock()
        mock_prefix.prefix = MagicMock()
        mock_prefix.prefix.__str__ = MagicMock(return_value="192.168.1.0/24")
        mock_prefix.prefix.version = 4
        config.prefix = mock_prefix

        # Mock get_pools to return empty
        with patch.object(config, "get_pools", return_value=[]):
            # Mock option_data to return empty queryset
            mock_option_data = MagicMock()
            mock_option_data.all.return_value = []
            config.option_data = mock_option_data

            # Mock client_classes to return empty queryset
            mock_client_classes = MagicMock()
            mock_client_classes.all.return_value = []
            config.client_classes = mock_client_classes

            # Mock get_router_ip to return None
            with patch.object(config, "get_router_ip", return_value=None):
                # Mock get_kea_reservations to return reservations
                mock_reservations = [
                    {"ip-address": "192.168.1.10", "hw-address": "aa:bb:cc:dd:ee:ff", "hostname": "host1"},
                    {"ip-address": "192.168.1.20", "hw-address": "11:22:33:44:55:66", "hostname": "host2"},
                ]
                with patch.object(config, "get_kea_reservations", return_value=mock_reservations):
                    result = config.to_kea_dict()

        assert "reservations" in result
        assert len(result["reservations"]) == 2
        assert result["reservations"][0]["ip-address"] == "192.168.1.10"
        assert result["reservations"][1]["hostname"] == "host2"

    def test_to_kea_dict_omits_reservations_when_empty(self):
        """Test to_kea_dict omits reservations key when no reservations exist."""
        from unittest.mock import MagicMock, patch

        from netbox_dhcp_kea_plugin.models import PrefixDHCPConfig

        config = PrefixDHCPConfig()
        config.valid_lifetime = 3600
        config.max_lifetime = 7200

        mock_prefix = MagicMock()
        mock_prefix.prefix = MagicMock()
        mock_prefix.prefix.__str__ = MagicMock(return_value="192.168.1.0/24")
        mock_prefix.prefix.version = 4
        config.prefix = mock_prefix

        with patch.object(config, "get_pools", return_value=[]):
            mock_option_data = MagicMock()
            mock_option_data.all.return_value = []
            config.option_data = mock_option_data

            mock_client_classes = MagicMock()
            mock_client_classes.all.return_value = []
            config.client_classes = mock_client_classes

            with patch.object(config, "get_router_ip", return_value=None):
                with patch.object(config, "get_kea_reservations", return_value=[]):
                    result = config.to_kea_dict()

        assert "reservations" not in result
