"""Tests for OptionData type-based validation."""

import pytest
from django.core.exceptions import ValidationError


class TestValidateTypedValue:
    """Test OptionData._validate_typed_value() static method directly."""

    @staticmethod
    def _validate(value, option_type):
        from netbox_dhcp_kea_plugin.models import OptionData

        OptionData._validate_typed_value(value, option_type)

    # -- IPv4 --

    def test_ipv4_valid(self):
        self._validate("192.168.1.1", "ipv4-address")
        self._validate("0.0.0.0", "ipv4-address")
        self._validate("255.255.255.255", "ipv4-address")

    def test_ipv4_invalid(self):
        with pytest.raises(ValidationError):
            self._validate("not-an-ip", "ipv4-address")

    def test_ipv4_invalid_octet(self):
        with pytest.raises(ValidationError):
            self._validate("256.1.1.1", "ipv4-address")

    def test_ipv4_rejects_cidr(self):
        with pytest.raises(ValidationError):
            self._validate("192.168.1.0/24", "ipv4-address")

    # -- IPv6 --

    def test_ipv6_valid(self):
        self._validate("2001:db8::1", "ipv6-address")
        self._validate("::1", "ipv6-address")
        self._validate("fe80::1%eth0", "ipv6-address")

    def test_ipv6_invalid(self):
        with pytest.raises(ValidationError):
            self._validate("not-ipv6", "ipv6-address")

    # -- IPv6 prefix --

    def test_ipv6_prefix_valid(self):
        self._validate("2001:db8::/32", "ipv6-prefix")

    def test_ipv6_prefix_invalid(self):
        with pytest.raises(ValidationError):
            self._validate("not-a-prefix", "ipv6-prefix")

    # -- Boolean --

    def test_boolean_valid(self):
        for val in ("true", "false", "True", "False", "0", "1"):
            self._validate(val, "boolean")

    def test_boolean_invalid(self):
        with pytest.raises(ValidationError):
            self._validate("yes", "boolean")

    # -- Unsigned integers --

    def test_uint8_valid(self):
        self._validate("0", "uint8")
        self._validate("255", "uint8")

    def test_uint8_too_large(self):
        with pytest.raises(ValidationError):
            self._validate("256", "uint8")

    def test_uint8_negative(self):
        with pytest.raises(ValidationError):
            self._validate("-1", "uint8")

    def test_uint16_valid(self):
        self._validate("65535", "uint16")

    def test_uint16_too_large(self):
        with pytest.raises(ValidationError):
            self._validate("65536", "uint16")

    def test_uint32_valid(self):
        self._validate("4294967295", "uint32")

    def test_uint32_too_large(self):
        with pytest.raises(ValidationError):
            self._validate("4294967296", "uint32")

    # -- Signed integers --

    def test_int8_valid(self):
        self._validate("-128", "int8")
        self._validate("127", "int8")

    def test_int8_too_large(self):
        with pytest.raises(ValidationError):
            self._validate("128", "int8")

    def test_int16_valid(self):
        self._validate("-32768", "int16")
        self._validate("32767", "int16")

    def test_int32_valid(self):
        self._validate("-2147483648", "int32")
        self._validate("2147483647", "int32")

    def test_int_not_a_number(self):
        with pytest.raises(ValidationError):
            self._validate("abc", "uint16")

    # -- FQDN --

    def test_fqdn_valid(self):
        self._validate("host.example.com", "fqdn")
        self._validate("host.example.com.", "fqdn")
        self._validate("single", "fqdn")

    def test_fqdn_invalid(self):
        with pytest.raises(ValidationError):
            self._validate("-invalid.com", "fqdn")

    # -- No-op types --

    def test_string_accepts_anything(self):
        self._validate("anything goes", "string")

    def test_empty_accepts_anything(self):
        self._validate("", "empty")

    def test_binary_accepts_anything(self):
        self._validate("some data", "binary")


class TestOptionDataCleanValidation:
    """Test type-based validation integrated in OptionData.clean()."""

    def test_valid_ipv4_passes_clean(self, db):
        from netbox_dhcp_kea_plugin.models import OptionData, OptionDefinition

        defn = OptionDefinition.objects.create(
            name="routers",
            code=3,
            option_type="ipv4-address",
            option_space="dhcp4",
            is_standard=True,
        )
        opt = OptionData(
            distinctive_name="test-routers",
            definition=defn,
            option_space="dhcp4",
            delivery_type="standard",
            data="192.168.1.1",
            csv_format=True,
        )
        opt.clean()  # should not raise

    def test_invalid_ipv4_fails_clean(self, db):
        from netbox_dhcp_kea_plugin.models import OptionData, OptionDefinition

        defn = OptionDefinition.objects.create(
            name="routers",
            code=3,
            option_type="ipv4-address",
            option_space="dhcp4",
            is_standard=True,
        )
        opt = OptionData(
            distinctive_name="test-bad-router",
            definition=defn,
            option_space="dhcp4",
            delivery_type="standard",
            data="not-an-ip",
            csv_format=True,
        )
        with pytest.raises(ValidationError, match="valid IPv4"):
            opt.clean()

    def test_array_ipv4_valid(self, db):
        from netbox_dhcp_kea_plugin.models import OptionData, OptionDefinition

        defn = OptionDefinition.objects.create(
            name="ntp-servers",
            code=42,
            option_type="ipv4-address",
            option_space="dhcp4",
            is_standard=True,
            is_array=True,
        )
        opt = OptionData(
            distinctive_name="test-ntp",
            definition=defn,
            option_space="dhcp4",
            delivery_type="standard",
            data="8.8.8.8, 8.8.4.4",
            csv_format=True,
        )
        opt.clean()  # should not raise

    def test_array_ipv4_one_invalid(self, db):
        from netbox_dhcp_kea_plugin.models import OptionData, OptionDefinition

        defn = OptionDefinition.objects.create(
            name="ntp-servers",
            code=42,
            option_type="ipv4-address",
            option_space="dhcp4",
            is_standard=True,
            is_array=True,
        )
        opt = OptionData(
            distinctive_name="test-ntp-bad",
            definition=defn,
            option_space="dhcp4",
            delivery_type="standard",
            data="8.8.8.8, not-an-ip",
            csv_format=True,
        )
        with pytest.raises(ValidationError, match="valid IPv4"):
            opt.clean()

    def test_single_value_rejects_comma_separated(self, db):
        from netbox_dhcp_kea_plugin.models import OptionData, OptionDefinition

        defn = OptionDefinition.objects.create(
            name="routers",
            code=3,
            option_type="ipv4-address",
            option_space="dhcp4",
            is_standard=True,
            is_array=False,
        )
        opt = OptionData(
            distinctive_name="test-multi-single",
            definition=defn,
            option_space="dhcp4",
            delivery_type="standard",
            data="192.168.1.1, 192.168.1.2",
            csv_format=True,
        )
        with pytest.raises(ValidationError, match="does not accept multiple values"):
            opt.clean()

    def test_hex_data_skips_type_validation(self, db):
        """When csv_format=False, type validation is skipped (hex validation applies instead)."""
        from netbox_dhcp_kea_plugin.models import OptionData, OptionDefinition

        defn = OptionDefinition.objects.create(
            name="custom-opt",
            code=100,
            option_type="ipv4-address",
            option_space="dhcp4",
            is_standard=False,
        )
        opt = OptionData(
            distinctive_name="test-hex",
            definition=defn,
            option_space="dhcp4",
            delivery_type="standard",
            data="C0A80101",
            csv_format=False,  # hex for 192.168.1.1
        )
        opt.clean()  # should not raise — hex validation only, not IP format

    def test_no_definition_skips_type_validation(self, db):
        """OptionData without a definition skips type validation."""
        from netbox_dhcp_kea_plugin.models import OptionData

        opt = OptionData(
            distinctive_name="test-no-def",
            definition=None,
            option_space="dhcp4",
            delivery_type="standard",
            data="anything",
            csv_format=True,
        )
        opt.clean()  # should not raise

    def test_empty_data_skips_type_validation(self, db):
        """Empty data field skips type validation."""
        from netbox_dhcp_kea_plugin.models import OptionData, OptionDefinition

        defn = OptionDefinition.objects.create(
            name="empty-opt",
            code=101,
            option_type="ipv4-address",
            option_space="dhcp4",
            is_standard=False,
        )
        opt = OptionData(
            distinctive_name="test-empty",
            definition=defn,
            option_space="dhcp4",
            delivery_type="standard",
            data="",
            csv_format=True,
        )
        opt.clean()  # should not raise

    def test_uint16_valid_in_clean(self, db):
        from netbox_dhcp_kea_plugin.models import OptionData, OptionDefinition

        defn = OptionDefinition.objects.create(
            name="mtu",
            code=26,
            option_type="uint16",
            option_space="dhcp4",
            is_standard=True,
        )
        opt = OptionData(
            distinctive_name="test-mtu",
            definition=defn,
            option_space="dhcp4",
            delivery_type="standard",
            data="1500",
            csv_format=True,
        )
        opt.clean()  # should not raise

    def test_uint16_invalid_in_clean(self, db):
        from netbox_dhcp_kea_plugin.models import OptionData, OptionDefinition

        defn = OptionDefinition.objects.create(
            name="mtu-bad",
            code=26,
            option_type="uint16",
            option_space="dhcp4",
            is_standard=True,
        )
        opt = OptionData(
            distinctive_name="test-mtu-bad",
            definition=defn,
            option_space="dhcp4",
            delivery_type="standard",
            data="70000",
            csv_format=True,
        )
        with pytest.raises(ValidationError, match="between 0 and 65535"):
            opt.clean()

    def test_boolean_valid_in_clean(self, db):
        from netbox_dhcp_kea_plugin.models import OptionData, OptionDefinition

        defn = OptionDefinition.objects.create(
            name="ip-forwarding",
            code=19,
            option_type="boolean",
            option_space="dhcp4",
            is_standard=True,
        )
        opt = OptionData(
            distinctive_name="test-fwd",
            definition=defn,
            option_space="dhcp4",
            delivery_type="standard",
            data="true",
            csv_format=True,
        )
        opt.clean()  # should not raise
