"""Tests for OptionData IP source linking and resolution."""

import pytest
from django.contrib.contenttypes.models import ContentType


@pytest.fixture
def ipv4_definition(db):
    """Create an ipv4-address OptionDefinition."""
    from netbox_dhcp_kea_plugin.models import OptionDefinition

    return OptionDefinition.objects.create(
        name="routers",
        code=3,
        option_type="ipv4-address",
        option_space="dhcp4",
        is_standard=True,
        is_array=False,
    )


@pytest.fixture
def ipv4_array_definition(db):
    """Create an ipv4-address array OptionDefinition (e.g. ntp-servers)."""
    from netbox_dhcp_kea_plugin.models import OptionDefinition

    return OptionDefinition.objects.create(
        name="ntp-servers",
        code=42,
        option_type="ipv4-address",
        option_space="dhcp4",
        is_standard=True,
        is_array=True,
    )


@pytest.fixture
def ip_address_factory(db):
    """Factory to create IPAM IPAddress objects."""
    from ipam.models import IPAddress

    counter = [0]

    def create(address=None):
        counter[0] += 1
        addr = address or f"10.0.0.{counter[0]}/24"
        return IPAddress.objects.create(address=addr)

    return create


@pytest.fixture
def ipam_content_type(db):
    """Return the ContentType for ipam.IPAddress."""
    return ContentType.objects.get(app_label="ipam", model="ipaddress")


class TestResolveIP:
    """Test OptionData._resolve_ip() static method."""

    def test_resolve_ipam_ip_address(self, ip_address_factory):
        from netbox_dhcp_kea_plugin.models import OptionData

        ip = ip_address_factory("192.168.1.100/24")
        result = OptionData._resolve_ip(ip)
        assert result == "192.168.1.100"

    def test_resolve_none_returns_none(self):
        from netbox_dhcp_kea_plugin.models import OptionData

        assert OptionData._resolve_ip(None) is None

    def test_resolve_unknown_type_returns_none(self):
        from netbox_dhcp_kea_plugin.models import OptionData

        class FakeObject:
            pass

        assert OptionData._resolve_ip(FakeObject()) is None


class TestOptionDataIPSource:
    """Test OptionDataIPSource model and its integration with OptionData."""

    def test_create_ip_source(self, ipv4_definition, ip_address_factory, ipam_content_type):
        from netbox_dhcp_kea_plugin.models import OptionData, OptionDataIPSource

        ip = ip_address_factory("10.1.1.1/24")
        opt = OptionData.objects.create(
            distinctive_name="test-src",
            definition=ipv4_definition,
            option_space="dhcp4",
            delivery_type="standard",
            data="",
            csv_format=True,
        )
        source = OptionDataIPSource.objects.create(
            option_data=opt,
            content_type=ipam_content_type,
            object_id=ip.pk,
            ordinal=0,
        )
        assert source.ip_source == ip
        assert source.ordinal == 0

    def test_ip_sources_ordered_by_ordinal(self, ipv4_array_definition, ip_address_factory, ipam_content_type):
        from netbox_dhcp_kea_plugin.models import OptionData, OptionDataIPSource

        ip1 = ip_address_factory("10.1.1.1/24")
        ip2 = ip_address_factory("10.1.1.2/24")
        ip3 = ip_address_factory("10.1.1.3/24")

        opt = OptionData.objects.create(
            distinctive_name="test-ordered",
            definition=ipv4_array_definition,
            option_space="dhcp4",
            delivery_type="standard",
            data="",
            csv_format=True,
        )
        # Create out of order
        OptionDataIPSource.objects.create(option_data=opt, content_type=ipam_content_type, object_id=ip3.pk, ordinal=2)
        OptionDataIPSource.objects.create(option_data=opt, content_type=ipam_content_type, object_id=ip1.pk, ordinal=0)
        OptionDataIPSource.objects.create(option_data=opt, content_type=ipam_content_type, object_id=ip2.pk, ordinal=1)

        sources = list(opt.ip_sources.order_by("ordinal"))
        assert sources[0].object_id == ip1.pk
        assert sources[1].object_id == ip2.pk
        assert sources[2].object_id == ip3.pk

    def test_cascade_delete_with_option_data(self, ipv4_definition, ip_address_factory, ipam_content_type):
        from netbox_dhcp_kea_plugin.models import OptionData, OptionDataIPSource

        ip = ip_address_factory()
        opt = OptionData.objects.create(
            distinctive_name="test-cascade",
            definition=ipv4_definition,
            option_space="dhcp4",
            delivery_type="standard",
            data="",
            csv_format=True,
        )
        OptionDataIPSource.objects.create(option_data=opt, content_type=ipam_content_type, object_id=ip.pk, ordinal=0)
        assert OptionDataIPSource.objects.count() == 1
        opt.delete()
        assert OptionDataIPSource.objects.count() == 0


class TestToKeaDictIPSources:
    """Test OptionData.to_kea_dict() with IP sources linked."""

    def test_single_ip_source_overrides_data(self, ipv4_definition, ip_address_factory, ipam_content_type):
        from netbox_dhcp_kea_plugin.models import OptionData, OptionDataIPSource

        ip = ip_address_factory("172.16.0.1/24")
        opt = OptionData.objects.create(
            distinctive_name="test-kea-single",
            definition=ipv4_definition,
            option_space="dhcp4",
            delivery_type="standard",
            data="manual-fallback",
            csv_format=True,
        )
        OptionDataIPSource.objects.create(option_data=opt, content_type=ipam_content_type, object_id=ip.pk, ordinal=0)

        kea = opt.to_kea_dict()
        assert kea["data"] == "172.16.0.1"

    def test_multiple_ip_sources_comma_joined(self, ipv4_array_definition, ip_address_factory, ipam_content_type):
        from netbox_dhcp_kea_plugin.models import OptionData, OptionDataIPSource

        ip1 = ip_address_factory("8.8.8.8/32")
        ip2 = ip_address_factory("8.8.4.4/32")

        opt = OptionData.objects.create(
            distinctive_name="test-kea-array",
            definition=ipv4_array_definition,
            option_space="dhcp4",
            delivery_type="standard",
            data="",
            csv_format=True,
        )
        OptionDataIPSource.objects.create(option_data=opt, content_type=ipam_content_type, object_id=ip1.pk, ordinal=0)
        OptionDataIPSource.objects.create(option_data=opt, content_type=ipam_content_type, object_id=ip2.pk, ordinal=1)

        kea = opt.to_kea_dict()
        assert kea["data"] == "8.8.8.8, 8.8.4.4"

    def test_no_ip_sources_uses_data_field(self, ipv4_definition):
        from netbox_dhcp_kea_plugin.models import OptionData

        opt = OptionData.objects.create(
            distinctive_name="test-kea-manual",
            definition=ipv4_definition,
            option_space="dhcp4",
            delivery_type="standard",
            data="10.0.0.1",
            csv_format=True,
        )
        kea = opt.to_kea_dict()
        assert kea["data"] == "10.0.0.1"

    def test_deleted_source_falls_back_to_data(self, ipv4_definition, ip_address_factory, ipam_content_type):
        """When all IP sources are deleted objects, fall back to data field."""
        from netbox_dhcp_kea_plugin.models import OptionData, OptionDataIPSource

        ip = ip_address_factory("10.99.99.1/24")
        opt = OptionData.objects.create(
            distinctive_name="test-kea-deleted",
            definition=ipv4_definition,
            option_space="dhcp4",
            delivery_type="standard",
            data="fallback-value",
            csv_format=True,
        )
        OptionDataIPSource.objects.create(option_data=opt, content_type=ipam_content_type, object_id=ip.pk, ordinal=0)

        # Delete the IP, making the GFK resolve to None
        ip.delete()

        # Refresh to clear cached GFK
        opt.refresh_from_db()
        kea = opt.to_kea_dict()
        assert kea["data"] == "fallback-value"

    def test_ip_source_respects_ordinal_in_output(self, ipv4_array_definition, ip_address_factory, ipam_content_type):
        """Ensure ordinal determines the position in comma-separated output."""
        from netbox_dhcp_kea_plugin.models import OptionData, OptionDataIPSource

        ip_first = ip_address_factory("1.1.1.1/32")
        ip_second = ip_address_factory("2.2.2.2/32")

        opt = OptionData.objects.create(
            distinctive_name="test-kea-order",
            definition=ipv4_array_definition,
            option_space="dhcp4",
            delivery_type="standard",
            data="",
            csv_format=True,
        )
        # Create in reverse ordinal order
        OptionDataIPSource.objects.create(option_data=opt, content_type=ipam_content_type, object_id=ip_second.pk, ordinal=1)
        OptionDataIPSource.objects.create(option_data=opt, content_type=ipam_content_type, object_id=ip_first.pk, ordinal=0)

        kea = opt.to_kea_dict()
        assert kea["data"] == "1.1.1.1, 2.2.2.2"

    def test_ip_source_with_always_send_and_csv_format(self, ipv4_definition, ip_address_factory, ipam_content_type):
        """IP sources work correctly with always_send and csv_format flags."""
        from netbox_dhcp_kea_plugin.models import OptionData, OptionDataIPSource

        ip = ip_address_factory("192.168.50.1/24")
        opt = OptionData.objects.create(
            distinctive_name="test-kea-flags",
            definition=ipv4_definition,
            option_space="dhcp4",
            delivery_type="standard",
            data="",
            always_send=True,
            csv_format=True,
        )
        OptionDataIPSource.objects.create(option_data=opt, content_type=ipam_content_type, object_id=ip.pk, ordinal=0)

        kea = opt.to_kea_dict()
        assert kea["data"] == "192.168.50.1"
        assert kea["always-send"] is True
        assert "csv-format" not in kea  # csv_format=True means no override needed

    def test_ip_changed_reflected_in_to_kea_dict(self, ipv4_definition, ip_address_factory, ipam_content_type):
        """When the linked IP address changes, to_kea_dict() picks up the new value."""
        from ipam.models import IPAddress

        from netbox_dhcp_kea_plugin.models import OptionData, OptionDataIPSource

        ip = ip_address_factory("10.0.0.50/24")
        opt = OptionData.objects.create(
            distinctive_name="test-kea-change",
            definition=ipv4_definition,
            option_space="dhcp4",
            delivery_type="standard",
            data="",
            csv_format=True,
        )
        OptionDataIPSource.objects.create(option_data=opt, content_type=ipam_content_type, object_id=ip.pk, ordinal=0)

        assert opt.to_kea_dict()["data"] == "10.0.0.50"

        # Update the IP address
        ip.address = "10.0.0.99/24"
        ip.save()

        # to_kea_dict should resolve the new IP without any signal
        kea = opt.to_kea_dict()
        assert kea["data"] == "10.0.0.99"
