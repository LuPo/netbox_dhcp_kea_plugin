#!/usr/bin/env python
"""Tests for netbox_dhcp_kea_plugin models."""

from unittest.mock import MagicMock, patch


class TestClientClassKeaOutput:
    """Test ClientClass KEA configuration output methods."""

    def test_has_option43_data_false_when_no_option_data(self):
        """Test has_option43_data returns False when no option data."""
        from netbox_dhcp_kea_plugin.models import ClientClass

        client_class = ClientClass(name="test", test_expression="test")
        mock_manager = MagicMock()
        mock_manager.filter.return_value.exists.return_value = False
        with patch.object(ClientClass, "option_data", mock_manager, create=True):
            assert not client_class.has_option43_data()

    def test_has_option43_data_true_when_option43_exists(self):
        """Test has_option43_data returns True when option43 delivery type exists."""
        from netbox_dhcp_kea_plugin.models import ClientClass

        client_class = ClientClass(name="test", test_expression="test")
        mock_manager = MagicMock()
        mock_manager.filter.return_value.exists.return_value = True
        with patch.object(ClientClass, "option_data", mock_manager, create=True):
            assert client_class.has_option43_data()

    def test_get_kea_option_defs_empty_when_no_option43(self):
        """Test get_kea_option_defs returns empty list when no option43 data."""
        from netbox_dhcp_kea_plugin.models import ClientClass

        client_class = ClientClass(name="test", test_expression="test")

        with patch.object(client_class, "has_option43_data", return_value=False):
            with patch.object(client_class, "has_vivso_data", return_value=False):
                with patch.object(client_class, "get_option_definitions", return_value=[]):
                    result = client_class.get_kea_option_defs()

        assert result == []

    def test_get_kea_option_defs_includes_vendor_encapsulated_options(self):
        """Test get_kea_option_defs includes vendor-encapsulated-options when has option43."""
        from netbox_dhcp_kea_plugin.models import ClientClass, OptionDefinition, VendorOptionSpace

        vendor_space = MagicMock(spec=VendorOptionSpace)
        vendor_space.name = "MSUCClient"

        client_class = ClientClass(name="test", test_expression="test")

        # Mock OptionDefinition.objects.filter to return empty queryset
        mock_queryset = MagicMock()
        mock_queryset.distinct.return_value = []

        # Mock the methods that access option_data
        with patch.object(client_class, "has_option43_data", return_value=True):
            with patch.object(client_class, "has_vivso_data", return_value=False):
                with patch.object(client_class, "get_option43_vendor_spaces", return_value=[vendor_space]):
                    with patch.object(OptionDefinition.objects, "filter", return_value=mock_queryset):
                        result = client_class.get_kea_option_defs()

        assert len(result) == 1
        assert result[0]["name"] == "vendor-encapsulated-options"
        assert result[0]["code"] == 43
        assert result[0]["type"] == "empty"
        assert result[0]["encapsulate"] == "MSUCClient"

    def test_to_kea_dict_basic_structure(self):
        """Test to_kea_dict returns correct basic structure."""
        from netbox_dhcp_kea_plugin.models import ClientClass

        client_class = ClientClass(name="MS-UC-Client", test_expression="option[60].hex == 'MS-UC-Client'")

        with patch.object(client_class, "get_kea_option_defs", return_value=[]):
            with patch.object(client_class, "get_kea_option_data", return_value=[]):
                result = client_class.to_kea_dict()

        assert result["name"] == "MS-UC-Client"
        assert result["test"] == "option[60].hex == 'MS-UC-Client'"
        assert "option-def" not in result
        assert "option-data" not in result

    def test_to_kea_dict_excludes_option_def(self):
        """Test to_kea_dict does NOT include option-def (now in global scope)."""
        from netbox_dhcp_kea_plugin.models import ClientClass

        option_defs = [
            {"name": "vendor-encapsulated-options", "code": 43, "type": "empty", "encapsulate": "MSUCClient"}
        ]

        client_class = ClientClass(name="MS-UC-Client", test_expression="option[60].hex == 'MS-UC-Client'")

        with patch.object(client_class, "get_kea_option_defs", return_value=option_defs):
            with patch.object(client_class, "get_kea_option_data", return_value=[]):
                result = client_class.to_kea_dict()

        # option-def should NOT be in client class output - it's in global Dhcp4.option-def
        assert "option-def" not in result

    def test_to_kea_dict_includes_option_data(self):
        """Test to_kea_dict includes option-data when present."""
        from netbox_dhcp_kea_plugin.models import ClientClass

        option_data = [{"name": "vendor-encapsulated-options", "code": 43}]

        client_class = ClientClass(name="MS-UC-Client", test_expression="option[60].hex == 'MS-UC-Client'")

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
        opt.csv_format = False

        client_class = ClientClass(name="test", test_expression="test")

        with patch.object(client_class, "has_option43_data", return_value=False):
            with patch.object(client_class, "has_vivso_data", return_value=False):
                with patch.object(client_class, "get_option_data_sorted", return_value=[opt]):
                    result = client_class.get_kea_option_data(ascii_format=False)

        assert len(result) == 1
        assert result[0]["data"] == "68:74:74:70:73"
        assert not result[0]["csv-format"]

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
        opt.csv_format = True

        client_class = ClientClass(name="test", test_expression="test")

        with patch.object(client_class, "has_option43_data", return_value=False):
            with patch.object(client_class, "has_vivso_data", return_value=False):
                with patch.object(client_class, "get_option_data_sorted", return_value=[opt]):
                    result = client_class.get_kea_option_data(ascii_format=True)

        assert len(result) == 1
        assert result[0]["data"] == "https"
        assert "csv-format" not in result[0]  # csv-format=true is KEA default, not included

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
        with patch.object(ClientClass, "option_data", create=True):
            mock_manager = MagicMock()
            mock_manager.filter.return_value.exists.return_value = False
            type(client_class).option_data = mock_manager

            assert not client_class.has_vivso_data()

    def test_has_vivso_data_true_when_vivso_exists(self):
        """Test has_vivso_data returns True when vivso delivery type exists."""
        from netbox_dhcp_kea_plugin.models import ClientClass

        client_class = ClientClass(name="test", test_expression="test")
        with patch.object(ClientClass, "option_data", create=True):
            mock_manager = MagicMock()
            mock_manager.filter.return_value.exists.return_value = True
            type(client_class).option_data = mock_manager

            assert client_class.has_vivso_data()

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


class TestSubnetReservations:
    """Test Subnet reservation methods."""

    def test_get_reservations_returns_empty_list_when_no_ips(self):
        """Test get_reservations returns empty list when prefix has no child IPs."""
        from unittest.mock import MagicMock, PropertyMock, patch

        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet()
        mock_prefix = MagicMock()
        mock_prefix.get_child_ips.return_value = []

        with patch.object(Subnet, "prefix", new_callable=PropertyMock) as mock_prefix_prop:
            mock_prefix_prop.return_value = mock_prefix
            result = config.get_reservations()

        assert result == []

    def test_get_reservations_skips_ips_without_assigned_object(self):
        """Test get_reservations skips IPs without assigned_object_type."""
        from unittest.mock import MagicMock, PropertyMock, patch

        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet()
        mock_prefix = MagicMock()

        mock_ip = MagicMock()
        mock_ip.assigned_object_type = None

        mock_prefix.get_child_ips.return_value = [mock_ip]

        with patch.object(Subnet, "prefix", new_callable=PropertyMock) as mock_prefix_prop:
            mock_prefix_prop.return_value = mock_prefix
            result = config.get_reservations()

        assert result == []

    def test_get_reservations_skips_non_primary_non_oob_ips(self):
        """Test get_reservations skips IPs that are not primary or OOB."""
        from unittest.mock import MagicMock, PropertyMock, patch

        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet()
        mock_prefix = MagicMock()

        mock_ip = MagicMock()
        mock_ip.assigned_object_type = MagicMock()
        mock_ip.assigned_object_type_id = 999  # Not FHRP
        mock_ip.is_primary_ip = False
        mock_ip.is_oob_ip = False

        mock_prefix.get_child_ips.return_value = [mock_ip]

        with patch.object(Subnet, "prefix", new_callable=PropertyMock) as mock_prefix_prop:
            mock_prefix_prop.return_value = mock_prefix
            result = config.get_reservations()

        assert result == []

    def test_get_reservations_includes_primary_ip(self):
        """Test get_reservations includes IPs marked as primary."""
        from unittest.mock import MagicMock, PropertyMock, patch

        from django.contrib.contenttypes.models import ContentType

        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet()
        mock_prefix = MagicMock()

        mock_interface = MagicMock()
        mock_interface.name = "eth0"
        mock_primary_mac = MagicMock()
        mock_primary_mac.mac_address = "aa:bb:cc:dd:ee:ff"
        mock_interface.primary_mac_address = mock_primary_mac
        mock_interface.mac_address = None  # Fallback should not be used

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

        with patch.object(Subnet, "prefix", new_callable=PropertyMock) as mock_prefix_prop:
            mock_prefix_prop.return_value = mock_prefix
            with patch("netbox_dhcp_kea_plugin.models.ContentType") as mock_ct:
                mock_ct.DoesNotExist = ContentType.DoesNotExist
                mock_ct.objects.get.side_effect = ContentType.DoesNotExist("Not found")
                result = config.get_reservations()

        assert len(result) == 1
        kea_res, metadata = result[0]
        assert kea_res["ip-address"] == "192.168.1.10"
        assert kea_res["hw-address"] == "aa:bb:cc:dd:ee:ff"
        assert kea_res["hostname"] == "test-device"
        assert metadata["is_primary"] is True
        assert metadata["has_hw_address"] is True

    def test_get_reservations_includes_oob_ip_with_interface_name(self):
        """Test get_reservations includes OOB IPs with interface name in hostname."""
        from unittest.mock import MagicMock, PropertyMock, patch

        from django.contrib.contenttypes.models import ContentType

        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet()
        mock_prefix = MagicMock()

        mock_interface = MagicMock()
        mock_interface.name = "mgmt0/1"
        mock_primary_mac = MagicMock()
        mock_primary_mac.mac_address = "11:22:33:44:55:66"
        mock_interface.primary_mac_address = mock_primary_mac
        mock_interface.mac_address = None  # Fallback should not be used

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

        with patch.object(Subnet, "prefix", new_callable=PropertyMock) as mock_prefix_prop:
            mock_prefix_prop.return_value = mock_prefix
            with patch("netbox_dhcp_kea_plugin.models.ContentType") as mock_ct:
                mock_ct.DoesNotExist = ContentType.DoesNotExist
                mock_ct.objects.get.side_effect = ContentType.DoesNotExist("Not found")
                result = config.get_reservations()

        assert len(result) == 1
        kea_res, metadata = result[0]
        assert kea_res["ip-address"] == "10.0.0.5"
        assert kea_res["hostname"] == "oob-device_mgmt0-1"
        assert metadata["is_oob"] is True
        assert metadata["has_hw_address"] is True

    def test_get_reservations_uses_dns_name_for_hostname(self):
        """Test get_reservations uses first part of dns_name for hostname."""
        from unittest.mock import MagicMock, PropertyMock, patch

        from django.contrib.contenttypes.models import ContentType

        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet()
        mock_prefix = MagicMock()

        mock_interface = MagicMock()
        mock_interface.name = "eth0"
        mock_primary_mac = MagicMock()
        mock_primary_mac.mac_address = "aa:bb:cc:dd:ee:ff"
        mock_interface.primary_mac_address = mock_primary_mac
        mock_interface.mac_address = None  # Fallback should not be used

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

        with patch.object(Subnet, "prefix", new_callable=PropertyMock) as mock_prefix_prop:
            mock_prefix_prop.return_value = mock_prefix
            with patch("netbox_dhcp_kea_plugin.models.ContentType") as mock_ct:
                mock_ct.DoesNotExist = ContentType.DoesNotExist
                mock_ct.objects.get.side_effect = ContentType.DoesNotExist("Not found")
                result = config.get_reservations()

        assert len(result) == 1
        kea_res, _ = result[0]
        assert kea_res["hostname"] == "short"

    def test_get_kea_reservations_returns_only_kea_dicts(self):
        """Test get_kea_reservations returns only KEA dicts without metadata."""
        from unittest.mock import MagicMock, PropertyMock, patch

        from django.contrib.contenttypes.models import ContentType

        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet()
        mock_prefix = MagicMock()

        mock_interface = MagicMock()
        mock_interface.name = "eth0"
        mock_primary_mac = MagicMock()
        mock_primary_mac.mac_address = "aa:bb:cc:dd:ee:ff"
        mock_interface.primary_mac_address = mock_primary_mac
        mock_interface.mac_address = None  # Fallback should not be used

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

        with patch.object(Subnet, "prefix", new_callable=PropertyMock) as mock_prefix_prop:
            mock_prefix_prop.return_value = mock_prefix
            with patch("netbox_dhcp_kea_plugin.models.ContentType") as mock_ct:
                mock_ct.DoesNotExist = ContentType.DoesNotExist
                mock_ct.objects.get.side_effect = ContentType.DoesNotExist("Not found")
                result = config.get_kea_reservations()

        assert len(result) == 1
        assert isinstance(result[0], dict)
        assert "ip-address" in result[0]
        assert "hw-address" in result[0]
        # Should not contain metadata
        assert "is_primary" not in result[0]

    def test_to_kea_dict_includes_reservations(self):
        """Test to_kea_dict includes reservations in output."""
        from unittest.mock import MagicMock, PropertyMock, patch

        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet()
        config.valid_lifetime = 3600
        config.max_lifetime = 7200

        mock_prefix = MagicMock()
        mock_prefix.prefix = MagicMock()
        mock_prefix.prefix.__str__ = MagicMock(return_value="192.168.1.0/24")
        mock_prefix.prefix.version = 4

        with patch.object(Subnet, "prefix", new_callable=PropertyMock) as mock_prefix_prop:
            mock_prefix_prop.return_value = mock_prefix
            # Mock get_pools to return empty
            with patch.object(config, "get_pools", return_value=[]):
                # Mock option_data to return empty queryset
                mock_option_data = MagicMock()
                mock_option_data.all.return_value = []
                with patch.object(Subnet, "option_data", new_callable=PropertyMock) as mock_opt:
                    mock_opt.return_value = mock_option_data
                    # Mock evaluate_additional_classes to return empty queryset
                    mock_eval_classes = MagicMock()
                    mock_eval_classes.all.return_value = []
                    with patch.object(Subnet, "evaluate_additional_classes", new_callable=PropertyMock) as mock_ec:
                        mock_ec.return_value = mock_eval_classes
                        # Mock client_class to return None
                        with patch.object(Subnet, "client_class", new_callable=PropertyMock) as mock_cc:
                            mock_cc.return_value = None
                            # Ensure client_class_id is None so the FK check doesn't fire
                            config.client_class_id = None
                            # Mock get_router_ip to return None
                            with patch.object(config, "get_router_ip", return_value=None):
                                # Mock get_kea_reservations to return reservations
                                mock_reservations = [
                                    {
                                        "ip-address": "192.168.1.10",
                                        "hw-address": "aa:bb:cc:dd:ee:ff",
                                        "hostname": "host1",
                                    },
                                    {
                                        "ip-address": "192.168.1.20",
                                        "hw-address": "11:22:33:44:55:66",
                                        "hostname": "host2",
                                    },
                                ]
                                with patch.object(config, "get_kea_reservations", return_value=mock_reservations):
                                    result = config.to_kea_dict()

        assert "reservations" in result
        assert len(result["reservations"]) == 2
        assert result["reservations"][0]["ip-address"] == "192.168.1.10"
        assert result["reservations"][1]["hostname"] == "host2"

    def test_to_kea_dict_omits_reservations_when_empty(self):
        """Test to_kea_dict omits reservations key when no reservations exist."""
        from unittest.mock import MagicMock, PropertyMock, patch

        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet()
        config.valid_lifetime = 3600
        config.max_lifetime = 7200

        mock_prefix = MagicMock()
        mock_prefix.prefix = MagicMock()
        mock_prefix.prefix.__str__ = MagicMock(return_value="192.168.1.0/24")
        mock_prefix.prefix.version = 4

        with patch.object(Subnet, "prefix", new_callable=PropertyMock) as mock_prefix_prop:
            mock_prefix_prop.return_value = mock_prefix
            with patch.object(config, "get_pools", return_value=[]):
                mock_option_data = MagicMock()
                mock_option_data.all.return_value = []
                with patch.object(Subnet, "option_data", new_callable=PropertyMock) as mock_opt:
                    mock_opt.return_value = mock_option_data
                    mock_eval_classes = MagicMock()
                    mock_eval_classes.all.return_value = []
                    with patch.object(Subnet, "evaluate_additional_classes", new_callable=PropertyMock) as mock_ec:
                        mock_ec.return_value = mock_eval_classes
                        with patch.object(Subnet, "client_class", new_callable=PropertyMock) as mock_cc:
                            mock_cc.return_value = None
                            config.client_class_id = None
                            with patch.object(config, "get_router_ip", return_value=None):
                                with patch.object(config, "get_kea_reservations", return_value=[]):
                                    result = config.to_kea_dict()

        assert "reservations" not in result

    def test_get_reservations_includes_ip_without_mac(self):
        """Test get_reservations includes IPs without MAC address but marks them."""
        from unittest.mock import MagicMock, PropertyMock, patch

        from django.contrib.contenttypes.models import ContentType

        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet()
        mock_prefix = MagicMock()

        mock_interface = MagicMock()
        mock_interface.name = "eth0"
        mock_interface.primary_mac_address = None
        mock_interface.mac_address = None

        mock_device = MagicMock()
        mock_device.name = "no-mac-device"
        mock_interface.parent_object = mock_device

        mock_ip_address = MagicMock()
        mock_ip_address.ip = "192.168.1.50"

        mock_ip = MagicMock()
        mock_ip.assigned_object_type = MagicMock()
        mock_ip.assigned_object_type_id = 999
        mock_ip.is_primary_ip = True
        mock_ip.is_oob_ip = False
        mock_ip.assigned_object = mock_interface
        mock_ip.address = mock_ip_address
        mock_ip.dns_name = ""

        mock_prefix.get_child_ips.return_value = [mock_ip]

        with patch.object(Subnet, "prefix", new_callable=PropertyMock) as mock_prefix_prop:
            mock_prefix_prop.return_value = mock_prefix
            with patch("netbox_dhcp_kea_plugin.models.ContentType") as mock_ct:
                mock_ct.DoesNotExist = ContentType.DoesNotExist
                mock_ct.objects.get.side_effect = ContentType.DoesNotExist("Not found")
                result = config.get_reservations()

        assert len(result) == 1
        kea_res, metadata = result[0]
        assert kea_res["ip-address"] == "192.168.1.50"
        assert "hw-address" not in kea_res
        assert kea_res["hostname"] == "no-mac-device"
        assert metadata["has_hw_address"] is False

    def test_get_kea_reservations_excludes_entries_without_hw_address(self):
        """Test get_kea_reservations filters out reservations without hw-address.

        KEA requires either hw-address or duid for a valid reservation.
        Entries without either cause kea-dhcp4.service validation to fail.
        """
        from unittest.mock import MagicMock, PropertyMock, patch

        from django.contrib.contenttypes.models import ContentType

        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet()
        mock_prefix = MagicMock()

        # Interface WITH MAC
        mock_interface_with_mac = MagicMock()
        mock_interface_with_mac.name = "eth0"
        mock_primary_mac = MagicMock()
        mock_primary_mac.mac_address = "aa:bb:cc:dd:ee:ff"
        mock_interface_with_mac.primary_mac_address = mock_primary_mac
        mock_interface_with_mac.mac_address = None

        mock_device1 = MagicMock()
        mock_device1.name = "device-with-mac"
        mock_interface_with_mac.parent_object = mock_device1

        mock_ip_address1 = MagicMock()
        mock_ip_address1.ip = "192.168.1.10"

        mock_ip1 = MagicMock()
        mock_ip1.assigned_object_type = MagicMock()
        mock_ip1.assigned_object_type_id = 999
        mock_ip1.is_primary_ip = True
        mock_ip1.is_oob_ip = False
        mock_ip1.assigned_object = mock_interface_with_mac
        mock_ip1.address = mock_ip_address1
        mock_ip1.dns_name = ""

        # Interface WITHOUT MAC
        mock_interface_no_mac = MagicMock()
        mock_interface_no_mac.name = "eth1"
        mock_interface_no_mac.primary_mac_address = None
        mock_interface_no_mac.mac_address = None

        mock_device2 = MagicMock()
        mock_device2.name = "device-no-mac"
        mock_interface_no_mac.parent_object = mock_device2

        mock_ip_address2 = MagicMock()
        mock_ip_address2.ip = "192.168.1.20"

        mock_ip2 = MagicMock()
        mock_ip2.assigned_object_type = MagicMock()
        mock_ip2.assigned_object_type_id = 999
        mock_ip2.is_primary_ip = True
        mock_ip2.is_oob_ip = False
        mock_ip2.assigned_object = mock_interface_no_mac
        mock_ip2.address = mock_ip_address2
        mock_ip2.dns_name = ""

        mock_prefix.get_child_ips.return_value = [mock_ip1, mock_ip2]

        with patch.object(Subnet, "prefix", new_callable=PropertyMock) as mock_prefix_prop:
            mock_prefix_prop.return_value = mock_prefix
            with patch("netbox_dhcp_kea_plugin.models.ContentType") as mock_ct:
                mock_ct.DoesNotExist = ContentType.DoesNotExist
                mock_ct.objects.get.side_effect = ContentType.DoesNotExist("Not found")

                # get_reservations should return both
                all_reservations = config.get_reservations()
                assert len(all_reservations) == 2

                # get_kea_reservations should only return the one with hw-address
                kea_reservations = config.get_kea_reservations()

        assert len(kea_reservations) == 1
        assert kea_reservations[0]["ip-address"] == "192.168.1.10"
        assert kea_reservations[0]["hw-address"] == "aa:bb:cc:dd:ee:ff"


class TestSubnetLifetimeValidation:
    """Test that valid_lifetime cannot be greater than max_lifetime on Subnet."""

    def test_clean_rejects_valid_lifetime_greater_than_max_lifetime(self):
        """clean() must raise ValidationError when valid_lifetime > max_lifetime."""
        from django.core.exceptions import ValidationError

        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet(valid_lifetime=9000, max_lifetime=3600)
        # Provide a prefix_id=None so routers_option_offset check is skipped,
        # and client_class_id=None so client-class check is skipped.
        config.prefix_id = None
        config.client_class_id = None

        import pytest

        with pytest.raises(ValidationError) as exc_info:
            config.clean()

        assert "valid_lifetime" in exc_info.value.message_dict

    def test_clean_allows_valid_lifetime_equal_to_max_lifetime(self):
        """clean() must accept valid_lifetime == max_lifetime."""
        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet(valid_lifetime=3600, max_lifetime=3600)
        config.prefix_id = None
        config.client_class_id = None
        # Should not raise
        config.clean()

    def test_clean_allows_valid_lifetime_less_than_max_lifetime(self):
        """clean() must accept valid_lifetime < max_lifetime."""
        from netbox_dhcp_kea_plugin.models import Subnet

        config = Subnet(valid_lifetime=1800, max_lifetime=3600)
        config.prefix_id = None
        config.client_class_id = None
        # Should not raise
        config.clean()

    def test_save_rejects_valid_lifetime_greater_than_max_lifetime(self, subnet_factory):
        """save() must enforce that valid_lifetime <= max_lifetime."""
        import pytest
        from django.core.exceptions import ValidationError

        subnet = subnet_factory()
        subnet.valid_lifetime = 99999
        subnet.max_lifetime = 100

        with pytest.raises(ValidationError) as exc_info:
            subnet.save()

        assert "valid_lifetime" in exc_info.value.message_dict

    def test_save_accepts_valid_lifetime_equal_to_max_lifetime(self, subnet_factory):
        """save() must accept valid_lifetime == max_lifetime."""
        subnet = subnet_factory()
        subnet.valid_lifetime = 5000
        subnet.max_lifetime = 5000
        subnet.save()

        subnet.refresh_from_db()
        assert subnet.valid_lifetime == 5000
        assert subnet.max_lifetime == 5000

    def test_save_accepts_valid_lifetime_less_than_max_lifetime(self, subnet_factory):
        """save() must accept valid_lifetime < max_lifetime."""
        subnet = subnet_factory()
        subnet.valid_lifetime = 1800
        subnet.max_lifetime = 7200
        subnet.save()

        subnet.refresh_from_db()
        assert subnet.valid_lifetime == 1800
        assert subnet.max_lifetime == 7200


class TestModelDefaults:
    """Test plugin model_defaults configuration for Subnet default values."""

    def test_get_model_default_returns_configured_value(self, settings):
        """get_model_default returns the value from model_defaults config."""
        from netbox_dhcp_kea_plugin.models import get_model_default

        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "model_defaults": {
                    "Subnet": {
                        "valid_lifetime": 900,
                        "max_lifetime": 1800,
                    },
                },
            }
        }

        assert get_model_default("Subnet", "valid_lifetime") == 900
        assert get_model_default("Subnet", "max_lifetime") == 1800

    def test_get_model_default_returns_fallback_when_missing(self, settings):
        """get_model_default returns fallback when key is absent."""
        from netbox_dhcp_kea_plugin.models import get_model_default

        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "model_defaults": {},
            }
        }

        assert get_model_default("Subnet", "valid_lifetime", 3600) == 3600
        assert get_model_default("Subnet", "max_lifetime", 7200) == 7200

    def test_get_model_default_returns_fallback_when_no_model_defaults(self, settings):
        """get_model_default returns fallback when model_defaults is not set at all."""
        from netbox_dhcp_kea_plugin.models import get_model_default

        settings.PLUGINS_CONFIG = {"netbox_dhcp_kea_plugin": {}}

        assert get_model_default("Subnet", "valid_lifetime", 3600) == 3600

    def test_get_model_default_returns_none_without_fallback(self, settings):
        """get_model_default returns None when key is absent and no fallback given."""
        from netbox_dhcp_kea_plugin.models import get_model_default

        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "model_defaults": {},
            }
        }

        assert get_model_default("Subnet", "nonexistent") is None

    def test_get_model_default_unknown_model_returns_fallback(self, settings):
        """get_model_default returns fallback for an unconfigured model name."""
        from netbox_dhcp_kea_plugin.models import get_model_default

        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "model_defaults": {
                    "Subnet": {"valid_lifetime": 900},
                },
            }
        }

        assert get_model_default("UnknownModel", "some_field", 42) == 42

    def test_subnet_model_uses_configured_defaults(self, settings, prefix_factory, dhcp_server_factory):
        """Subnet.objects.create() without explicit lifetimes uses model_defaults."""
        from netbox_dhcp_kea_plugin.models import Subnet

        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "model_defaults": {
                    "Subnet": {
                        "valid_lifetime": 1200,
                        "max_lifetime": 2400,
                    },
                },
            }
        }

        subnet = Subnet.objects.create(
            prefix=prefix_factory(),
            server=dhcp_server_factory(),
            routers_option_offset=1,
        )

        assert subnet.valid_lifetime == 1200
        assert subnet.max_lifetime == 2400

    def test_subnet_model_explicit_values_override_defaults(self, settings, prefix_factory, dhcp_server_factory):
        """Explicit values passed to create() take precedence over model_defaults."""
        from netbox_dhcp_kea_plugin.models import Subnet

        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "model_defaults": {
                    "Subnet": {
                        "valid_lifetime": 1200,
                        "max_lifetime": 2400,
                    },
                },
            }
        }

        subnet = Subnet.objects.create(
            prefix=prefix_factory(),
            server=dhcp_server_factory(),
            valid_lifetime=5000,
            max_lifetime=10000,
            routers_option_offset=1,
        )

        assert subnet.valid_lifetime == 5000
        assert subnet.max_lifetime == 10000

    def test_subnet_form_initial_values_from_config(self, settings):
        """SubnetForm pre-populates lifetime fields from model_defaults for new objects."""
        from netbox_dhcp_kea_plugin.forms import SubnetForm

        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "model_defaults": {
                    "Subnet": {
                        "valid_lifetime": 600,
                        "max_lifetime": 1200,
                    },
                },
            }
        }

        form = SubnetForm()

        assert form.initial["valid_lifetime"] == 600
        assert form.initial["max_lifetime"] == 1200

    def test_subnet_form_no_override_on_existing_instance(self, settings, subnet_factory):
        """SubnetForm does not override lifetime fields for existing instances."""
        from netbox_dhcp_kea_plugin.forms import SubnetForm

        settings.PLUGINS_CONFIG = {
            "netbox_dhcp_kea_plugin": {
                "model_defaults": {
                    "Subnet": {
                        "valid_lifetime": 600,
                        "max_lifetime": 1200,
                    },
                },
            }
        }

        subnet = subnet_factory()
        form = SubnetForm(instance=subnet)

        # Existing instance values should be used, not the config defaults
        assert form.initial["valid_lifetime"] == subnet.valid_lifetime
        assert form.initial["max_lifetime"] == subnet.max_lifetime
