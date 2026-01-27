#!/usr/bin/env python
"""
Tests for netbox_dhcp_kea_plugin models.

Run with:
    cd /path/to/netbox-dhcp-kea-plugin
    source /path/to/netbox/venv/bin/activate
    pytest tests/ -v
"""



class TestVendorOptionSpace:
    """Tests for VendorOptionSpace model."""

    def test_create_vendor_option_space(self, vendor_option_space):
        """Test creating a VendorOptionSpace."""
        assert vendor_option_space.name == "TestVendor"
        assert vendor_option_space.enterprise_id == 12345
        assert str(vendor_option_space) == "TestVendor (Test Vendor Inc)"

    def test_vendor_option_space_absolute_url(self, vendor_option_space):
        """Test VendorOptionSpace.get_absolute_url()."""
        url = vendor_option_space.get_absolute_url()
        assert f"/plugins/netbox_dhcp_kea_plugin/vendor-option-spaces/{vendor_option_space.pk}/" in url


class TestOptionDefinition:
    """Tests for OptionDefinition model."""

    def test_create_option_definition(self, option_definition):
        """Test creating an OptionDefinition."""
        assert option_definition.name == "test-option"
        assert option_definition.code == 1
        assert option_definition.option_type == "string"
        assert option_definition.is_standard is False

    def test_option_definition_str(self, option_definition):
        """Test OptionDefinition.__str__()."""
        assert str(option_definition) == "test-option (code 1, TestVendor)"

    def test_space_name_property(self, option_definition):
        """Test OptionDefinition.space_name property."""
        assert option_definition.space_name == "TestVendor"

    def test_space_name_without_vendor(self, option_definition_no_vendor):
        """Test OptionDefinition.space_name property without vendor space."""
        assert option_definition_no_vendor.space_name == "dhcp4"

    def test_to_kea_dict(self, option_definition):
        """Test OptionDefinition.to_kea_dict()."""
        kea_dict = option_definition.to_kea_dict()
        assert kea_dict["name"] == "test-option"
        assert kea_dict["code"] == 1
        assert kea_dict["type"] == "string"
        assert kea_dict["space"] == "TestVendor"

    def test_to_kea_dict_with_array(self, db, vendor_option_space):
        """Test OptionDefinition.to_kea_dict() with is_array=True."""
        from netbox_dhcp_kea_plugin.models import OptionDefinition

        definition = OptionDefinition.objects.create(
            name="array-option",
            code=2,
            option_type="string",
            option_space="dhcp4",
            vendor_option_space=vendor_option_space,
            is_array=True,
            is_standard=False,
        )
        kea_dict = definition.to_kea_dict()
        assert kea_dict["array"] is True


class TestOptionData:
    """Tests for OptionData model."""

    def test_create_option_data(self, option_data):
        """Test creating an OptionData."""
        assert option_data.distinctive_name == "test-option-data"
        assert option_data.delivery_type == "option43"
        assert option_data.data == "test-value"

    def test_option_data_name_property(self, option_data):
        """Test OptionData.name property returns definition name."""
        assert option_data.name == "test-option"

    def test_option_data_code_property(self, option_data):
        """Test OptionData.code property returns definition code."""
        assert option_data.code == 1

    def test_to_kea_dict_option43(self, option_data):
        """Test OptionData.to_kea_dict() with option43 delivery."""
        kea_dict = option_data.to_kea_dict()
        assert kea_dict["name"] == "test-option"
        assert kea_dict["code"] == 1
        assert kea_dict["data"] == "test-value"
        assert kea_dict["space"] == "TestVendor"

    def test_to_kea_dict_standard(self, option_data_standard):
        """Test OptionData.to_kea_dict() with standard delivery."""
        kea_dict = option_data_standard.to_kea_dict()
        assert kea_dict["space"] == "dhcp4"
        assert "code" in kea_dict

    def test_ascii_data_passthrough(self, option_data):
        """Test ascii_data returns data as-is when csv_format=True."""
        assert option_data.ascii_data == option_data.data

    def test_ascii_data_hex_conversion(self, db, option_definition):
        """Test ascii_data converts hex to ASCII when csv_format=False."""
        from netbox_dhcp_kea_plugin.models import OptionData

        # 'hello' in hex
        option = OptionData.objects.create(
            distinctive_name="hex-option-data",
            definition=option_definition,
            option_space="dhcp4",
            vendor_option_space=option_definition.vendor_option_space,
            delivery_type="option43",
            data="68:65:6c:6c:6f",  # 'hello' in hex
            csv_format=False,
        )
        assert option.ascii_data == "hello"


class TestClientClass:
    """Tests for ClientClass model."""

    def test_create_client_class(self, client_class):
        """Test creating a ClientClass."""
        assert client_class.name == "TestClass"
        assert client_class.local_definitions is False

    def test_has_option43_data_false(self, client_class):
        """Test has_option43_data() returns False when no option43 data."""
        assert client_class.has_option43_data() is False

    def test_has_option43_data_true(self, client_class, option_data):
        """Test has_option43_data() returns True when option43 data exists."""
        client_class.option_data.add(option_data)
        assert client_class.has_option43_data() is True

    def test_get_option43_vendor_spaces(self, client_class, option_data):
        """Test get_option43_vendor_spaces() returns correct vendor spaces."""
        client_class.option_data.add(option_data)
        vendor_spaces = list(client_class.get_option43_vendor_spaces())
        assert len(vendor_spaces) == 1
        assert vendor_spaces[0].name == "TestVendor"

    def test_get_option_definitions(self, client_class, option_data):
        """Test get_option_definitions() returns correct definitions."""
        client_class.option_data.add(option_data)
        definitions = list(client_class.get_option_definitions())
        assert len(definitions) == 1
        assert definitions[0].name == "test-option"

    def test_to_kea_dict_basic(self, client_class):
        """Test ClientClass.to_kea_dict() basic output."""
        kea_dict = client_class.to_kea_dict()
        assert kea_dict["name"] == "TestClass"
        assert kea_dict["test"] == "option[60].hex == 'test'"
        assert "option-def" not in kea_dict
        assert "option-data" not in kea_dict

    def test_to_kea_dict_with_option43(self, client_class, option_data):
        """Test ClientClass.to_kea_dict() includes vendor-encapsulated-options for option43."""
        client_class.option_data.add(option_data)
        kea_dict = client_class.to_kea_dict()

        # Should have option-def with vendor-encapsulated-options
        assert "option-def" in kea_dict
        veo_def = next((d for d in kea_dict["option-def"] if d["name"] == "vendor-encapsulated-options"), None)
        assert veo_def is not None
        assert veo_def["code"] == 43
        assert veo_def["type"] == "empty"
        assert veo_def["encapsulate"] == "TestVendor"

        # Should have option-data with vendor-encapsulated-options entry
        assert "option-data" in kea_dict
        veo_data = next((d for d in kea_dict["option-data"] if d.get("name") == "vendor-encapsulated-options"), None)
        assert veo_data is not None
        assert veo_data["code"] == 43

    def test_to_kea_dict_local_definitions(self, client_class_local_defs, option_data):
        """Test ClientClass.to_kea_dict() includes local definitions when local_definitions=True."""
        client_class_local_defs.option_data.add(option_data)
        kea_dict = client_class_local_defs.to_kea_dict()

        # Should have option-def with both vendor-encapsulated-options AND the option definition
        assert "option-def" in kea_dict
        assert len(kea_dict["option-def"]) >= 2

        # Check for the actual option definition
        opt_def = next((d for d in kea_dict["option-def"] if d["name"] == "test-option"), None)
        assert opt_def is not None
        assert opt_def["code"] == 1
        assert opt_def["type"] == "string"

    def test_to_kea_json(self, client_class, option_data):
        """Test to_kea_json() returns valid JSON."""
        import json

        client_class.option_data.add(option_data)

        # Test hex format
        hex_json = client_class.to_kea_json(ascii_format=False)
        hex_dict = json.loads(hex_json)
        assert hex_dict["name"] == "TestClass"

        # Test ascii format
        ascii_json = client_class.to_kea_json(ascii_format=True)
        ascii_dict = json.loads(ascii_json)
        assert ascii_dict["name"] == "TestClass"


class TestDHCPServer:
    """Tests for DHCPServer model."""

    def test_create_dhcp_server(self, dhcp_server):
        """Test creating a DHCPServer."""
        assert dhcp_server.name == "TestServer"
        assert dhcp_server.is_active is True

    def test_to_kea_dict_basic(self, dhcp_server):
        """Test DHCPServer.to_kea_dict() basic structure."""
        kea_dict = dhcp_server.to_kea_dict()
        assert "Dhcp4" in kea_dict
        assert "interfaces-config" in kea_dict["Dhcp4"]

    def test_to_kea_dict_excludes_local_definitions(self, dhcp_server, client_class_local_defs, option_data):
        """Test DHCPServer.to_kea_dict() excludes definitions from classes with local_definitions=True."""
        # Add option_data to client_class with local_definitions
        client_class_local_defs.option_data.add(option_data)

        # Add client_class to dhcp_server
        dhcp_server.client_classes.add(client_class_local_defs)

        kea_dict = dhcp_server.to_kea_dict()
        dhcp4 = kea_dict["Dhcp4"]

        # The option definition should NOT be in global option-def
        # because it's included locally in the client class
        global_option_defs = dhcp4.get("option-def", [])
        local_def = next((d for d in global_option_defs if d["name"] == "test-option"), None)
        assert local_def is None, "Local definition should not appear in global option-def"

    def test_to_kea_dict_includes_global_definitions(self, dhcp_server, client_class, option_data):
        """Test DHCPServer.to_kea_dict() includes definitions from classes without local_definitions."""
        # Add option_data to client_class without local_definitions
        client_class.option_data.add(option_data)

        # Add client_class to dhcp_server
        dhcp_server.client_classes.add(client_class)

        kea_dict = dhcp_server.to_kea_dict()
        dhcp4 = kea_dict["Dhcp4"]

        # The option definition SHOULD be in global option-def
        global_option_defs = dhcp4.get("option-def", [])
        global_def = next((d for d in global_option_defs if d["name"] == "test-option"), None)
        assert global_def is not None, "Global definition should appear in global option-def"
