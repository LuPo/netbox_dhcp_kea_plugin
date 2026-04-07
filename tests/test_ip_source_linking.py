"""Tests for OptionData IP source linking and resolution."""

import pytest
from django import forms
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
        stale_pk = ip.pk
        source = OptionDataIPSource.objects.create(option_data=opt, content_type=ipam_content_type, object_id=stale_pk, ordinal=0)

        # Remove the IP source link first (ProtectedError prevents direct IP deletion),
        # then delete the IP. Re-create the source with the now-stale object_id
        # so the GFK resolves to None.
        source.delete()
        ip.delete()
        OptionDataIPSource.objects.create(option_data=opt, content_type=ipam_content_type, object_id=stale_pk, ordinal=0)

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
        OptionDataIPSource.objects.create(
            option_data=opt, content_type=ipam_content_type, object_id=ip_second.pk, ordinal=1
        )
        OptionDataIPSource.objects.create(
            option_data=opt, content_type=ipam_content_type, object_id=ip_first.pk, ordinal=0
        )

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


@pytest.fixture
def record_ipv4_definition(db):
    """Create a record(boolean, ipv4-address) OptionDefinition with is_array=True."""
    from netbox_dhcp_kea_plugin.models import OptionDefinition

    return OptionDefinition.objects.create(
        name="record-with-ip",
        code=200,
        option_type="record",
        record_types="boolean, ipv4-address",
        option_space="dhcp4",
        is_array=True,
    )


@pytest.fixture
def record_ipv4_single_definition(db):
    """Create a record(boolean, ipv4-address) OptionDefinition with is_array=False."""
    from netbox_dhcp_kea_plugin.models import OptionDefinition

    return OptionDefinition.objects.create(
        name="record-single-ip",
        code=201,
        option_type="record",
        record_types="boolean, ipv4-address",
        option_space="dhcp4",
        is_array=False,
    )


@pytest.fixture
def record_no_ip_definition(db):
    """Create a record(boolean, string) OptionDefinition without IP fields."""
    from netbox_dhcp_kea_plugin.models import OptionDefinition

    return OptionDefinition.objects.create(
        name="slp-service-scope",
        code=79,
        option_type="record",
        record_types="boolean, string",
        option_space="dhcp4",
        is_array=False,
    )


class TestOptionDefinitionRecordHelpers:
    """Tests for OptionDefinition record-type helper methods."""

    def test_parsed_record_types(self, record_ipv4_definition):
        assert record_ipv4_definition.parsed_record_types() == ["boolean", "ipv4-address"]

    def test_parsed_record_types_empty(self, ipv4_definition):
        assert ipv4_definition.parsed_record_types() == []

    def test_record_ip_field_index(self, record_ipv4_definition):
        assert record_ipv4_definition.record_ip_field_index() == 1

    def test_record_ip_field_index_none(self, record_no_ip_definition):
        assert record_no_ip_definition.record_ip_field_index() is None


class TestRecordTypeToKeaDict:
    """Tests for to_kea_dict() with record-type IP source linking."""

    def test_record_with_ip_sources_assembles_data(self, record_ipv4_definition, ip_address_factory, ipam_content_type):
        """Record(boolean, ipv4-address) with IP sources assembles 'true, 10.0.0.1, 10.0.0.2'."""
        from netbox_dhcp_kea_plugin.models import OptionData, OptionDataIPSource

        ip1 = ip_address_factory("10.0.0.1/24")
        ip2 = ip_address_factory("10.0.0.2/24")

        opt = OptionData.objects.create(
            distinctive_name="test-record-ip",
            definition=record_ipv4_definition,
            option_space="dhcp4",
            delivery_type="standard",
            data="",
            csv_format=True,
            record_manual_fields={"0": "true"},
        )
        OptionDataIPSource.objects.create(option_data=opt, content_type=ipam_content_type, object_id=ip1.pk, ordinal=0)
        OptionDataIPSource.objects.create(option_data=opt, content_type=ipam_content_type, object_id=ip2.pk, ordinal=1)

        kea = opt.to_kea_dict()
        assert kea["data"] == "true, 10.0.0.1, 10.0.0.2"

    def test_record_single_ip_assembles_data(
        self, record_ipv4_single_definition, ip_address_factory, ipam_content_type
    ):
        """Record(boolean, ipv4-address) non-array assembles 'true, 10.0.0.5'."""
        from netbox_dhcp_kea_plugin.models import OptionData, OptionDataIPSource

        ip = ip_address_factory("10.0.0.5/24")

        opt = OptionData.objects.create(
            distinctive_name="test-record-single-ip",
            definition=record_ipv4_single_definition,
            option_space="dhcp4",
            delivery_type="standard",
            data="",
            csv_format=True,
            record_manual_fields={"0": "false"},
        )
        OptionDataIPSource.objects.create(option_data=opt, content_type=ipam_content_type, object_id=ip.pk, ordinal=0)

        kea = opt.to_kea_dict()
        assert kea["data"] == "false, 10.0.0.5"

    def test_record_without_ip_fields_uses_data(self, record_no_ip_definition):
        """Record(boolean, string) without record_manual_fields falls back to plain data field."""
        from netbox_dhcp_kea_plugin.models import OptionData

        opt = OptionData.objects.create(
            distinctive_name="test-slp-scope",
            definition=record_no_ip_definition,
            option_space="dhcp4",
            delivery_type="standard",
            data="true, FPSLP, Unscoped",
            csv_format=True,
        )

        kea = opt.to_kea_dict()
        assert kea["data"] == "true, FPSLP, Unscoped"

    def test_record_without_ip_fields_assembles_from_manual_fields(self, record_no_ip_definition):
        """Record(boolean, string) with record_manual_fields assembles data from individual fields."""
        from netbox_dhcp_kea_plugin.models import OptionData

        opt = OptionData.objects.create(
            distinctive_name="test-slp-scope-manual",
            definition=record_no_ip_definition,
            option_space="dhcp4",
            delivery_type="standard",
            data="",
            csv_format=True,
            record_manual_fields={"0": "true", "1": "FPSLP, Unscoped"},
        )

        kea = opt.to_kea_dict()
        assert kea["data"] == "true, FPSLP, Unscoped"

    def test_record_deduplicates_ips(self, record_ipv4_definition, ip_address_factory, ipam_content_type):
        """Duplicate IPs from multiple sources are deduplicated."""
        from netbox_dhcp_kea_plugin.models import OptionData, OptionDataIPSource

        ip1 = ip_address_factory("10.0.0.1/24")
        ip2 = ip_address_factory("10.0.0.1/25")  # same IP, different prefix

        opt = OptionData.objects.create(
            distinctive_name="test-record-dedup",
            definition=record_ipv4_definition,
            option_space="dhcp4",
            delivery_type="standard",
            data="",
            csv_format=True,
            record_manual_fields={"0": "true"},
        )
        OptionDataIPSource.objects.create(option_data=opt, content_type=ipam_content_type, object_id=ip1.pk, ordinal=0)
        OptionDataIPSource.objects.create(option_data=opt, content_type=ipam_content_type, object_id=ip2.pk, ordinal=1)

        kea = opt.to_kea_dict()
        assert kea["data"] == "true, 10.0.0.1"


@pytest.mark.django_db
class TestRecordTypeForm:
    """Tests for OptionDataForm in record-type IP source mode."""

    def test_record_ip_form_shows_record_fields_and_ip_sources(self, record_ipv4_definition):
        """Record(boolean, ipv4-address) form shows boolean CharField + IP source selectors."""
        from netbox_dhcp_kea_plugin.forms import OptionDataForm

        form = OptionDataForm(data={"definition": record_ipv4_definition.pk})
        assert "record_field_0" in form.fields, "Should have boolean record field"
        assert "record_field_1" not in form.fields, "IP position should not have a text field"
        assert "ipam_ip_sources" in form.fields, "Should have IP source selector"
        assert "data" not in form.fields, "Data field should be hidden"

    def test_record_no_ip_form_shows_individual_fields(self, record_no_ip_definition):
        """Record(boolean, string) without IP fields shows individual record fields."""
        from netbox_dhcp_kea_plugin.forms import OptionDataForm

        form = OptionDataForm(data={"definition": record_no_ip_definition.pk})
        assert "data" not in form.fields, "Data field should be hidden for record types"
        assert "record_field_0" in form.fields, "Should have boolean field"
        assert "record_field_1" in form.fields, "Should have string field"
        assert "ipam_ip_sources" not in form.fields, "No IP sources for non-IP record"
        # Boolean field should be a ChoiceField
        assert isinstance(form.fields["record_field_0"], forms.ChoiceField)

    def test_record_ip_fieldsets_contain_record_fields(self, record_ipv4_definition):
        """Fieldsets include 'Record Fields' section with manual fields and IP sources."""
        from netbox_dhcp_kea_plugin.forms import OptionDataForm

        form = OptionDataForm(data={"definition": record_ipv4_definition.pk})
        fieldset_names = [fs.name for fs in form.fieldsets]
        assert "Record Fields" in fieldset_names

    def test_record_single_ip_uses_single_select(self, record_ipv4_single_definition):
        """Non-array record uses single-select for IP sources."""
        from netbox_dhcp_kea_plugin.forms import OptionDataForm

        form = OptionDataForm(data={"definition": record_ipv4_single_definition.pk})
        assert "ipam_ip_sources" in form.fields
        # Single-select is DynamicModelChoiceField, not DynamicModelMultipleChoiceField
        from utilities.forms.fields import DynamicModelChoiceField

        assert isinstance(form.fields["ipam_ip_sources"], DynamicModelChoiceField)


class TestOptionDataSerializerData:
    """Tests that the API serializer returns resolved data."""

    def test_serializer_resolves_record_ip_data(self, record_ipv4_definition, ip_address_factory, ipam_content_type):
        """API data field returns assembled record data with resolved IPs."""
        from netbox_dhcp_kea_plugin.api.serializers import OptionDataSerializer
        from netbox_dhcp_kea_plugin.models import OptionData, OptionDataIPSource

        ip = ip_address_factory("10.0.0.1/24")
        opt = OptionData.objects.create(
            distinctive_name="test-api-record",
            definition=record_ipv4_definition,
            option_space="dhcp4",
            delivery_type="standard",
            data="",
            csv_format=True,
            record_manual_fields={"0": "true"},
        )
        OptionDataIPSource.objects.create(option_data=opt, content_type=ipam_content_type, object_id=ip.pk, ordinal=0)

        serializer = OptionDataSerializer(opt, context={"request": None})
        assert serializer.data["data"] == "true, 10.0.0.1"

    def test_serializer_returns_plain_data_for_simple_option(self, ipv4_definition):
        """API data field returns plain data for non-record options without IP sources."""
        from netbox_dhcp_kea_plugin.api.serializers import OptionDataSerializer
        from netbox_dhcp_kea_plugin.models import OptionData

        opt = OptionData.objects.create(
            distinctive_name="test-api-simple",
            definition=ipv4_definition,
            option_space="dhcp4",
            delivery_type="standard",
            data="10.0.0.1",
            csv_format=True,
        )

        serializer = OptionDataSerializer(opt, context={"request": None})
        assert serializer.data["data"] == "10.0.0.1"

    def test_serializer_resolves_record_no_ip_data(self, record_no_ip_definition):
        """API data field returns assembled data for record types without IP fields."""
        from netbox_dhcp_kea_plugin.api.serializers import OptionDataSerializer
        from netbox_dhcp_kea_plugin.models import OptionData

        opt = OptionData.objects.create(
            distinctive_name="test-api-slp",
            definition=record_no_ip_definition,
            option_space="dhcp4",
            delivery_type="standard",
            data="true, FPSLP, Unscoped",
            csv_format=True,
        )

        serializer = OptionDataSerializer(opt, context={"request": None})
        assert serializer.data["data"] == "true, FPSLP, Unscoped"
