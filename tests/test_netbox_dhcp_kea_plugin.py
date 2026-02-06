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
        """Test ClientClass.to_kea_dict() includes option-data for option43 (option-def moved to server level)."""
        client_class.option_data.add(option_data)
        kea_dict = client_class.to_kea_dict()

        # Client class should NOT have option-def (moved to server level per KEA 2.3+ architecture)
        assert "option-def" not in kea_dict

        # Should have option-data with vendor-encapsulated-options entry
        assert "option-data" in kea_dict
        veo_data = next((d for d in kea_dict["option-data"] if d.get("name") == "vendor-encapsulated-options"), None)
        assert veo_data is not None
        assert veo_data["code"] == 43

        # Should also include the actual option data in vendor space
        actual_data = next((d for d in kea_dict["option-data"] if d.get("name") == "test-option"), None)
        assert actual_data is not None
        assert actual_data["data"] == "test-value"
        assert actual_data["space"] == "TestVendor"

    def test_get_kea_option_defs_with_option43(self, client_class, option_data):
        """Test ClientClass.get_kea_option_defs() returns option definitions for option43."""
        client_class.option_data.add(option_data)
        option_defs = client_class.get_kea_option_defs()

        # Should have vendor-encapsulated-options definition
        veo_def = next((d for d in option_defs if d["name"] == "vendor-encapsulated-options"), None)
        assert veo_def is not None
        assert veo_def["code"] == 43
        assert veo_def["type"] == "empty"
        assert veo_def["encapsulate"] == "TestVendor"

        # Should have the custom option definition in vendor space
        custom_def = next((d for d in option_defs if d.get("name") == "test-option"), None)
        assert custom_def is not None
        assert custom_def["code"] == 1
        assert custom_def["type"] == "string"
        assert custom_def["space"] == "TestVendor"

    def test_to_kea_dict_empty_test_expression(self, db):
        """Test ClientClass.to_kea_dict() omits test field when test_expression is empty."""
        from netbox_dhcp_kea_plugin.models import ClientClass

        client_class = ClientClass.objects.create(
            name="UnconditionalClass",
            test_expression="",  # Empty = unconditional class
            description="Always matches when evaluated",
        )
        kea_dict = client_class.to_kea_dict()

        assert kea_dict["name"] == "UnconditionalClass"
        assert "test" not in kea_dict  # Should NOT have test field

    def test_to_kea_dict_only_in_additional_list(self, db):
        """Test ClientClass.to_kea_dict() includes only-in-additional-list flag when set."""
        from netbox_dhcp_kea_plugin.models import ClientClass

        client_class = ClientClass.objects.create(
            name="SubnetScopedClass",
            test_expression="option[60].hex == 'scoped'",
            description="Only evaluated in specific subnets",
            only_in_additional_list=True,
        )
        kea_dict = client_class.to_kea_dict()

        assert kea_dict["name"] == "SubnetScopedClass"
        assert kea_dict["test"] == "option[60].hex == 'scoped'"
        assert kea_dict["only-in-additional-list"] is True

    def test_to_kea_dict_only_in_additional_list_false(self, client_class):
        """Test ClientClass.to_kea_dict() omits only-in-additional-list when False."""
        kea_dict = client_class.to_kea_dict()

        assert "only-in-additional-list" not in kea_dict

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
        assert dhcp_server.status == "active"

    def test_to_kea_dict_basic(self, dhcp_server):
        """Test DHCPServer.to_kea_dict() basic structure."""
        kea_dict = dhcp_server.to_kea_dict()
        assert "Dhcp4" in kea_dict
        assert "interfaces-config" in kea_dict["Dhcp4"]

    def test_to_kea_dict_includes_only_in_additional_list_classes(self, dhcp_server, prefix_factory, db):
        """Test DHCPServer.to_kea_dict() includes all classes in global client-classes, with only-in-additional-list flag set appropriately."""
        from netbox_dhcp_kea_plugin.models import ClientClass, Subnet

        prefix = prefix_factory()

        # Create a class with only_in_additional_list=True
        scoped_class = ClientClass.objects.create(
            name="ScopedClass",
            test_expression="option[60].hex == 'scoped'",
            description="Should appear in global client-classes with only-in-additional-list flag",
            only_in_additional_list=True,
        )

        # Create a normal class
        normal_class = ClientClass.objects.create(
            name="NormalClass",
            test_expression="option[60].hex == 'normal'",
            description="Should appear in global client-classes without flag",
            only_in_additional_list=False,
        )

        # Create a prefix config and add both classes to it
        prefix_config = Subnet.objects.create(
            prefix=prefix,
            server=dhcp_server,
            valid_lifetime=3600,
        )
        prefix_config.evaluate_additional_classes.add(scoped_class)
        prefix_config.evaluate_additional_classes.add(normal_class)

        kea_dict = dhcp_server.to_kea_dict()
        dhcp4 = kea_dict["Dhcp4"]

        client_classes = dhcp4.get("client-classes", [])
        class_names = [cc["name"] for cc in client_classes]

        # Both classes should be included in global client-classes
        assert "NormalClass" in class_names, "Normal class should appear in global client-classes"
        assert "ScopedClass" in class_names, "Scoped class should also appear in global client-classes"

        # Check that scoped class has the only-in-additional-list flag
        scoped_class_config = next((cc for cc in client_classes if cc["name"] == "ScopedClass"), None)
        assert scoped_class_config is not None
        assert scoped_class_config.get("only-in-additional-list") is True, (
            "Scoped class should have only-in-additional-list=true"
        )

        # Check that normal class does NOT have the flag
        normal_class_config = next((cc for cc in client_classes if cc["name"] == "NormalClass"), None)
        assert normal_class_config is not None
        assert "only-in-additional-list" not in normal_class_config, (
            "Normal class should not have only-in-additional-list flag"
        )

        # All classes in evaluate_additional_classes should appear in subnet's evaluate-additional-classes
        subnets = dhcp4.get("subnet4", [])
        assert len(subnets) == 1
        subnet = subnets[0]

        # Verify subnet has id field from database primary key
        assert "id" in subnet, "Subnet should have 'id' field"
        assert subnet["id"] == prefix_config.pk, "Subnet id should match Subnet primary key"

        eval_classes = subnet.get("evaluate-additional-classes", [])
        assert "ScopedClass" in eval_classes, "Scoped class should appear in subnet's evaluate-additional-classes"
        assert "NormalClass" in eval_classes, (
            "Normal class should appear in subnet's evaluate-additional-classes (it was added to the M2M)"
        )
