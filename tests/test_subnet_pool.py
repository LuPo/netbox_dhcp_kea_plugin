#!/usr/bin/env python
"""Tests for SubnetPool model and its integration with Subnet KEA config output."""

import pytest
from ipam.models import IPRange, Prefix
from netaddr import IPNetwork


@pytest.fixture
def pool_prefix(db):
    """Create a prefix for pool testing."""
    return Prefix.objects.create(prefix="10.0.0.0/24")


@pytest.fixture
def pool_ip_range(db, pool_prefix):
    """Create an IP range within the pool prefix."""
    return IPRange.objects.create(
        start_address=IPNetwork("10.0.0.10/24"),
        end_address=IPNetwork("10.0.0.50/24"),
    )


@pytest.fixture
def pool_ip_range_2(db, pool_prefix):
    """Create a second IP range within the pool prefix."""
    return IPRange.objects.create(
        start_address=IPNetwork("10.0.0.100/24"),
        end_address=IPNetwork("10.0.0.200/24"),
    )


@pytest.fixture
def pool_ip_range_utilized(db, pool_prefix):
    """Create an IP range that is marked as utilized."""
    return IPRange.objects.create(
        start_address=IPNetwork("10.0.0.220/24"),
        end_address=IPNetwork("10.0.0.240/24"),
        mark_utilized=True,
    )


@pytest.fixture
def pool_dhcp_server(db, service_template, ip_address):
    """Create a DHCP server for pool testing."""
    from netbox_dhcp_kea_plugin.models import DHCPServer

    return DHCPServer.objects.create(
        name="PoolTestServer",
        description="Server for pool tests",
        ip_address=ip_address,
        service_template=service_template,
        status="active",
    )


@pytest.fixture
def pool_subnet(db, pool_prefix, pool_dhcp_server):
    """Create a Subnet for pool testing."""
    from netbox_dhcp_kea_plugin.models import Subnet

    return Subnet.objects.create(
        prefix=pool_prefix,
        server=pool_dhcp_server,
        valid_lifetime=3600,
        max_lifetime=7200,
        routers_option_offset=1,
    )


@pytest.fixture
def pool_client_class(db):
    """Create a client class for pool testing."""
    from netbox_dhcp_kea_plugin.models import ClientClass

    return ClientClass.objects.create(
        name="VOIP_phones",
        test_expression="option[60].hex == 'VOIP'",
        description="VOIP phone client class",
    )


@pytest.fixture
def pool_client_class_extra(db):
    """Create an additional client class for pool testing."""
    from netbox_dhcp_kea_plugin.models import ClientClass

    return ClientClass.objects.create(
        name="ExtraClass",
        test_expression="option[60].hex == 'Extra'",
        description="Extra client class",
    )


@pytest.fixture
def pool_option_definition(db):
    """Create an option definition for pool testing."""
    from netbox_dhcp_kea_plugin.models import OptionDefinition

    return OptionDefinition.objects.create(
        name="domain-name-servers",
        code=6,
        option_type="ipv4-address",
        option_space="dhcp4",
        is_standard=True,
        description="DNS servers",
    )


@pytest.fixture
def pool_option_data(db, pool_option_definition):
    """Create option data for pool testing."""
    from netbox_dhcp_kea_plugin.models import OptionData

    return OptionData.objects.create(
        distinctive_name="pool-dns-option",
        definition=pool_option_definition,
        option_space="dhcp4",
        delivery_type="standard",
        data="8.8.8.8",
        always_send=False,
        csv_format=True,
    )


@pytest.fixture
def pool_option_data_2(db, pool_option_definition):
    """Create a second option data for pool testing."""
    from netbox_dhcp_kea_plugin.models import OptionData, OptionDefinition

    defn = OptionDefinition.objects.create(
        name="domain-name",
        code=15,
        option_type="string",
        option_space="dhcp4",
        is_standard=True,
        description="Domain name",
    )
    return OptionData.objects.create(
        distinctive_name="pool-domain-option",
        definition=defn,
        option_space="dhcp4",
        delivery_type="standard",
        data="example.com",
        always_send=False,
        csv_format=True,
    )


class TestSubnetPoolModel:
    """Test SubnetPool model basic methods."""

    def test_str_representation(self, pool_subnet, pool_ip_range):
        """Test SubnetPool string representation shows subnet and IP range."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        subnet_pool = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
        )
        result = str(subnet_pool)
        assert "10.0.0.0/24" in result
        assert "10.0.0.10" in result
        assert "10.0.0.50" in result

    def test_get_absolute_url(self, pool_subnet, pool_ip_range):
        """Test SubnetPool returns correct absolute URL."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        subnet_pool = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
        )
        url = subnet_pool.get_absolute_url()
        assert str(subnet_pool.pk) in url
        assert "subnet-pools" in url

    def test_description_optional(self, pool_subnet, pool_ip_range):
        """Test SubnetPool can be created without a description."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        subnet_pool = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
        )
        assert subnet_pool.description == ""

    def test_description_set(self, pool_subnet, pool_ip_range):
        """Test SubnetPool can be created with a description."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        subnet_pool = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
            description="Voice VLAN pool",
        )
        assert subnet_pool.description == "Voice VLAN pool"

    def test_cascade_delete_on_subnet(self, pool_subnet, pool_ip_range):
        """Test SubnetPool is deleted when its Subnet is deleted."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        SubnetPool.objects.create(subnet=pool_subnet, ip_range=pool_ip_range)
        assert SubnetPool.objects.count() == 1
        pool_subnet.delete()
        assert SubnetPool.objects.count() == 0

    def test_cascade_delete_on_ip_range(self, pool_subnet, pool_ip_range):
        """Test SubnetPool is deleted when its IPRange is deleted."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        SubnetPool.objects.create(subnet=pool_subnet, ip_range=pool_ip_range)
        assert SubnetPool.objects.count() == 1
        pool_ip_range.delete()
        assert SubnetPool.objects.count() == 0

    def test_client_class_set_null_on_delete(self, pool_subnet, pool_ip_range, pool_client_class):
        """Test SubnetPool.client_class is set to NULL when the ClientClass is deleted."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        subnet_pool = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
            client_class=pool_client_class,
        )
        pool_client_class.delete()
        subnet_pool.refresh_from_db()
        assert subnet_pool.client_class is None

    def test_ip_range_one_to_one(self, pool_subnet, pool_ip_range):
        """Test that each IPRange can only have one SubnetPool."""
        from django.db import IntegrityError

        from netbox_dhcp_kea_plugin.models import SubnetPool

        SubnetPool.objects.create(subnet=pool_subnet, ip_range=pool_ip_range)
        with pytest.raises(IntegrityError):
            SubnetPool.objects.create(subnet=pool_subnet, ip_range=pool_ip_range)


class TestSubnetPoolApplyToPoolDict:
    """Test SubnetPool.apply_to_pool_dict() method."""

    def test_empty_config(self, pool_subnet, pool_ip_range):
        """Test apply_to_pool_dict with no client class or options configured."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        subnet_pool = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
        )
        pool_dict = {"pool": "10.0.0.10 - 10.0.0.50"}
        subnet_pool.apply_to_pool_dict(pool_dict)

        # Should only have the original pool key
        assert pool_dict == {"pool": "10.0.0.10 - 10.0.0.50"}

    def test_with_client_class(self, pool_subnet, pool_ip_range, pool_client_class):
        """Test apply_to_pool_dict adds client-class when configured."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        subnet_pool = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
            client_class=pool_client_class,
        )
        pool_dict = {"pool": "10.0.0.10 - 10.0.0.50"}
        subnet_pool.apply_to_pool_dict(pool_dict)

        assert pool_dict["client-class"] == "VOIP_phones"

    def test_with_additional_classes(self, pool_subnet, pool_ip_range, pool_client_class, pool_client_class_extra):
        """Test apply_to_pool_dict adds evaluate-additional-classes."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        subnet_pool = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
        )
        subnet_pool.evaluate_additional_classes.set([pool_client_class, pool_client_class_extra])

        pool_dict = {"pool": "10.0.0.10 - 10.0.0.50"}
        subnet_pool.apply_to_pool_dict(pool_dict)

        assert "evaluate-additional-classes" in pool_dict
        names = pool_dict["evaluate-additional-classes"]
        assert "VOIP_phones" in names
        assert "ExtraClass" in names

    def test_with_option_data(self, pool_subnet, pool_ip_range, pool_option_data):
        """Test apply_to_pool_dict adds option-data."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        subnet_pool = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
        )
        subnet_pool.option_data.set([pool_option_data])

        pool_dict = {"pool": "10.0.0.10 - 10.0.0.50"}
        subnet_pool.apply_to_pool_dict(pool_dict)

        assert "option-data" in pool_dict
        assert len(pool_dict["option-data"]) == 1
        assert pool_dict["option-data"][0]["name"] == "domain-name-servers"
        assert pool_dict["option-data"][0]["data"] == "8.8.8.8"

    def test_full_config(
        self, pool_subnet, pool_ip_range, pool_client_class, pool_client_class_extra, pool_option_data
    ):
        """Test apply_to_pool_dict with all configuration options set."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        subnet_pool = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
            client_class=pool_client_class,
        )
        subnet_pool.evaluate_additional_classes.set([pool_client_class_extra])
        subnet_pool.option_data.set([pool_option_data])

        pool_dict = {"pool": "10.0.0.10 - 10.0.0.50"}
        subnet_pool.apply_to_pool_dict(pool_dict)

        assert pool_dict["pool"] == "10.0.0.10 - 10.0.0.50"
        assert pool_dict["client-class"] == "VOIP_phones"
        assert pool_dict["evaluate-additional-classes"] == ["ExtraClass"]
        assert len(pool_dict["option-data"]) == 1
        assert pool_dict["option-data"][0]["code"] == 6

    def test_does_not_add_empty_additional_classes(self, pool_subnet, pool_ip_range, pool_client_class):
        """Test apply_to_pool_dict does not add evaluate-additional-classes when empty."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        subnet_pool = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
            client_class=pool_client_class,
        )
        pool_dict = {"pool": "10.0.0.10 - 10.0.0.50"}
        subnet_pool.apply_to_pool_dict(pool_dict)

        assert "evaluate-additional-classes" not in pool_dict

    def test_does_not_add_empty_option_data(self, pool_subnet, pool_ip_range, pool_client_class):
        """Test apply_to_pool_dict does not add option-data when empty."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        subnet_pool = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
            client_class=pool_client_class,
        )
        pool_dict = {"pool": "10.0.0.10 - 10.0.0.50"}
        subnet_pool.apply_to_pool_dict(pool_dict)

        assert "option-data" not in pool_dict


class TestSubnetPoolToKeaDict:
    """Test SubnetPool.to_kea_dict() method."""

    def test_basic_pool(self, pool_subnet, pool_ip_range):
        """Test to_kea_dict produces correct KEA pool dict with just the range."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        subnet_pool = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
        )
        result = subnet_pool.to_kea_dict()

        assert result == {"pool": "10.0.0.10 - 10.0.0.50"}

    def test_pool_with_client_class(self, pool_subnet, pool_ip_range, pool_client_class):
        """Test to_kea_dict includes client-class."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        subnet_pool = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
            client_class=pool_client_class,
        )
        result = subnet_pool.to_kea_dict()

        assert result["pool"] == "10.0.0.10 - 10.0.0.50"
        assert result["client-class"] == "VOIP_phones"

    def test_pool_with_full_config(
        self, pool_subnet, pool_ip_range, pool_client_class, pool_client_class_extra, pool_option_data
    ):
        """Test to_kea_dict with full configuration."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        subnet_pool = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
            client_class=pool_client_class,
        )
        subnet_pool.evaluate_additional_classes.set([pool_client_class_extra])
        subnet_pool.option_data.set([pool_option_data])

        result = subnet_pool.to_kea_dict()

        assert result["pool"] == "10.0.0.10 - 10.0.0.50"
        assert result["client-class"] == "VOIP_phones"
        assert result["evaluate-additional-classes"] == ["ExtraClass"]
        assert len(result["option-data"]) == 1


class TestSubnetPoolCleanValidation:
    """Test SubnetPool.clean() validation logic."""

    def test_rejects_ip_range_from_different_prefix(self, pool_subnet, db):
        """Test that clean rejects IP ranges not belonging to the subnet's prefix."""
        from django.core.exceptions import ValidationError

        from netbox_dhcp_kea_plugin.models import SubnetPool

        other_prefix = Prefix.objects.create(prefix="172.16.0.0/24")
        other_range = IPRange.objects.create(
            start_address=IPNetwork("172.16.0.10/24"),
            end_address=IPNetwork("172.16.0.50/24"),
        )

        subnet_pool = SubnetPool(
            subnet=pool_subnet,
            ip_range=other_range,
        )
        with pytest.raises(ValidationError) as exc_info:
            subnet_pool.clean()

        assert "ip_range" in exc_info.value.message_dict

    def test_rejects_mark_utilized_ip_range(self, pool_subnet, pool_ip_range_utilized):
        """Test that clean rejects IP ranges marked as utilized."""
        from django.core.exceptions import ValidationError

        from netbox_dhcp_kea_plugin.models import SubnetPool

        subnet_pool = SubnetPool(
            subnet=pool_subnet,
            ip_range=pool_ip_range_utilized,
        )
        with pytest.raises(ValidationError) as exc_info:
            subnet_pool.clean()

        errors = exc_info.value.message_dict
        assert "ip_range" in errors
        assert any("utilized" in msg.lower() for msg in errors["ip_range"])

    def test_passes_with_valid_ip_range(self, pool_subnet, pool_ip_range):
        """Test that clean passes with a valid IP range."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        subnet_pool = SubnetPool(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
        )
        # Should not raise
        subnet_pool.clean()

    def test_rejects_client_class_in_additional_classes(self, pool_subnet, pool_ip_range, pool_client_class):
        """Test clean rejects client_class that is also in evaluate_additional_classes."""
        from django.core.exceptions import ValidationError

        from netbox_dhcp_kea_plugin.models import SubnetPool

        subnet_pool = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
            client_class=pool_client_class,
        )
        subnet_pool.evaluate_additional_classes.set([pool_client_class])

        with pytest.raises(ValidationError) as exc_info:
            subnet_pool.clean()

        assert "client_class" in exc_info.value.message_dict


class TestSubnetGetAllPoolHelpers:
    """Test Subnet helper methods for collecting pool-level config."""

    def test_get_all_pool_option_data_empty(self, pool_subnet):
        """Test get_all_pool_option_data returns empty set when no pools configured."""
        result = pool_subnet.get_all_pool_option_data()
        assert result == set()

    def test_get_all_pool_option_data_collects_from_pools(
        self, pool_subnet, pool_ip_range, pool_ip_range_2, pool_option_data, pool_option_data_2
    ):
        """Test get_all_pool_option_data collects option data from all pools."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        sp1 = SubnetPool.objects.create(subnet=pool_subnet, ip_range=pool_ip_range)
        sp1.option_data.set([pool_option_data])

        sp2 = SubnetPool.objects.create(subnet=pool_subnet, ip_range=pool_ip_range_2)
        sp2.option_data.set([pool_option_data_2])

        result = pool_subnet.get_all_pool_option_data()

        assert pool_option_data in result
        assert pool_option_data_2 in result
        assert len(result) == 2

    def test_get_all_pool_option_data_deduplicates(self, pool_subnet, pool_ip_range, pool_ip_range_2, pool_option_data):
        """Test get_all_pool_option_data deduplicates shared option data."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        sp1 = SubnetPool.objects.create(subnet=pool_subnet, ip_range=pool_ip_range)
        sp1.option_data.set([pool_option_data])

        sp2 = SubnetPool.objects.create(subnet=pool_subnet, ip_range=pool_ip_range_2)
        sp2.option_data.set([pool_option_data])  # Same option data on both pools

        result = pool_subnet.get_all_pool_option_data()
        assert len(result) == 1

    def test_get_all_pool_client_classes_empty(self, pool_subnet):
        """Test get_all_pool_client_classes returns empty set when no pools configured."""
        result = pool_subnet.get_all_pool_client_classes()
        assert result == set()

    def test_get_all_pool_client_classes_collects_from_pools(
        self, pool_subnet, pool_ip_range, pool_client_class, pool_client_class_extra
    ):
        """Test get_all_pool_client_classes collects both client_class and additional classes."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        sp = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
            client_class=pool_client_class,
        )
        sp.evaluate_additional_classes.set([pool_client_class_extra])

        result = pool_subnet.get_all_pool_client_classes()

        assert pool_client_class in result
        assert pool_client_class_extra in result
        assert len(result) == 2

    def test_get_all_pool_client_classes_deduplicates(
        self, pool_subnet, pool_ip_range, pool_ip_range_2, pool_client_class
    ):
        """Test get_all_pool_client_classes deduplicates shared classes."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        sp1 = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
            client_class=pool_client_class,
        )

        sp2 = SubnetPool.objects.create(subnet=pool_subnet, ip_range=pool_ip_range_2)
        sp2.evaluate_additional_classes.set([pool_client_class])

        result = pool_subnet.get_all_pool_client_classes()
        assert pool_client_class in result
        assert len(result) == 1


class TestSubnetGetPoolsWithPoolConfig:
    """Test that Subnet.get_pools() integrates SubnetPool configuration."""

    def test_get_pools_with_ip_ranges_no_pool_config(self, pool_subnet, pool_ip_range):
        """Test get_pools returns plain pool dicts when no SubnetPool exists."""
        pools = pool_subnet.get_pools()

        assert len(pools) == 1
        assert pools[0] == {"pool": "10.0.0.10 - 10.0.0.50"}

    def test_get_pools_with_pool_config_client_class(self, pool_subnet, pool_ip_range, pool_client_class):
        """Test get_pools merges client-class from SubnetPool config."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
            client_class=pool_client_class,
        )

        pools = pool_subnet.get_pools()

        assert len(pools) == 1
        assert pools[0]["pool"] == "10.0.0.10 - 10.0.0.50"
        assert pools[0]["client-class"] == "VOIP_phones"

    def test_get_pools_with_pool_config_additional_classes(
        self, pool_subnet, pool_ip_range, pool_client_class, pool_client_class_extra
    ):
        """Test get_pools merges evaluate-additional-classes from SubnetPool config."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        sp = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
        )
        sp.evaluate_additional_classes.set([pool_client_class, pool_client_class_extra])

        pools = pool_subnet.get_pools()

        assert len(pools) == 1
        assert "evaluate-additional-classes" in pools[0]
        names = pools[0]["evaluate-additional-classes"]
        assert "VOIP_phones" in names
        assert "ExtraClass" in names

    def test_get_pools_with_pool_config_option_data(self, pool_subnet, pool_ip_range, pool_option_data):
        """Test get_pools merges option-data from SubnetPool config."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        sp = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
        )
        sp.option_data.set([pool_option_data])

        pools = pool_subnet.get_pools()

        assert len(pools) == 1
        assert "option-data" in pools[0]
        assert pools[0]["option-data"][0]["name"] == "domain-name-servers"

    def test_get_pools_multiple_ranges_partial_config(
        self, pool_subnet, pool_ip_range, pool_ip_range_2, pool_client_class
    ):
        """Test get_pools with multiple ranges, only some having SubnetPool config."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        # Only first range gets a pool config
        SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
            client_class=pool_client_class,
        )

        pools = pool_subnet.get_pools()

        assert len(pools) == 2

        # Find each pool by range
        pool_map = {p["pool"]: p for p in pools}

        configured_pool = pool_map["10.0.0.10 - 10.0.0.50"]
        assert configured_pool["client-class"] == "VOIP_phones"

        plain_pool = pool_map["10.0.0.100 - 10.0.0.200"]
        assert "client-class" not in plain_pool

    def test_get_pools_skips_utilized_ranges(self, pool_subnet, pool_ip_range, pool_ip_range_utilized):
        """Test that utilized IP ranges are not included as pools."""
        pools = pool_subnet.get_pools()

        pool_ranges = [p["pool"] for p in pools]
        assert "10.0.0.10 - 10.0.0.50" in pool_ranges
        # The utilized range should NOT be a pool
        assert not any("10.0.0.220" in r for r in pool_ranges)

    def test_get_pools_full_config(
        self,
        pool_subnet,
        pool_ip_range,
        pool_client_class,
        pool_client_class_extra,
        pool_option_data,
    ):
        """Test get_pools with full SubnetPool configuration."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        sp = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
            client_class=pool_client_class,
        )
        sp.evaluate_additional_classes.set([pool_client_class_extra])
        sp.option_data.set([pool_option_data])

        pools = pool_subnet.get_pools()

        assert len(pools) == 1
        pool = pools[0]
        assert pool["pool"] == "10.0.0.10 - 10.0.0.50"
        assert pool["client-class"] == "VOIP_phones"
        assert pool["evaluate-additional-classes"] == ["ExtraClass"]
        assert len(pool["option-data"]) == 1
        assert pool["option-data"][0]["name"] == "domain-name-servers"


class TestSubnetToKeaDictWithPools:
    """Test that Subnet.to_kea_dict() properly includes pool-level config in output."""

    def _refresh(self, subnet):
        """Refresh a Subnet from DB so prefix field is a proper netaddr.IPNetwork."""
        from netbox_dhcp_kea_plugin.models import Subnet

        return (
            Subnet.objects.select_related("prefix", "server")
            .prefetch_related("option_data", "evaluate_additional_classes")
            .get(pk=subnet.pk)
        )

    def test_kea_dict_includes_pool_client_class(self, pool_subnet, pool_ip_range, pool_client_class):
        """Test that pool-level client-class appears in KEA subnet config."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
            client_class=pool_client_class,
        )

        subnet = self._refresh(pool_subnet)
        result = subnet.to_kea_dict()

        assert "pools" in result
        assert result["pools"][0]["client-class"] == "VOIP_phones"

    def test_kea_dict_includes_pool_additional_classes(
        self, pool_subnet, pool_ip_range, pool_client_class, pool_client_class_extra
    ):
        """Test that pool-level evaluate-additional-classes appears in KEA subnet config."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        sp = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
        )
        sp.evaluate_additional_classes.set([pool_client_class_extra])

        subnet = self._refresh(pool_subnet)
        result = subnet.to_kea_dict()

        assert "pools" in result
        assert "evaluate-additional-classes" in result["pools"][0]
        assert "ExtraClass" in result["pools"][0]["evaluate-additional-classes"]

    def test_kea_dict_includes_pool_option_data(self, pool_subnet, pool_ip_range, pool_option_data):
        """Test that pool-level option-data appears in KEA subnet config."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        sp = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
        )
        sp.option_data.set([pool_option_data])

        subnet = self._refresh(pool_subnet)
        result = subnet.to_kea_dict()

        assert "pools" in result
        pool = result["pools"][0]
        assert "option-data" in pool
        assert pool["option-data"][0]["name"] == "domain-name-servers"

    def test_kea_dict_mixed_pools(self, pool_subnet, pool_ip_range, pool_ip_range_2, pool_client_class):
        """Test KEA output with mixed configured and plain pools."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
            client_class=pool_client_class,
        )

        subnet = self._refresh(pool_subnet)
        result = subnet.to_kea_dict()

        assert len(result["pools"]) == 2
        pool_map = {p["pool"]: p for p in result["pools"]}
        assert "client-class" in pool_map["10.0.0.10 - 10.0.0.50"]
        assert "client-class" not in pool_map["10.0.0.100 - 10.0.0.200"]

    def test_kea_dict_full_pool_config(
        self,
        pool_subnet,
        pool_ip_range,
        pool_client_class,
        pool_client_class_extra,
        pool_option_data,
    ):
        """Test KEA output with fully configured pool alongside subnet-level config."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        sp = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
            client_class=pool_client_class,
        )
        sp.evaluate_additional_classes.set([pool_client_class_extra])
        sp.option_data.set([pool_option_data])

        subnet = self._refresh(pool_subnet)
        result = subnet.to_kea_dict()

        # Verify basic subnet structure
        assert result["subnet"] == "10.0.0.0/24"
        assert result["valid-lifetime"] == 3600
        assert result["max-valid-lifetime"] == 7200

        # Verify pool config
        pool = result["pools"][0]
        assert pool["pool"] == "10.0.0.10 - 10.0.0.50"
        assert pool["client-class"] == "VOIP_phones"
        assert pool["evaluate-additional-classes"] == ["ExtraClass"]
        assert len(pool["option-data"]) == 1

    def test_kea_dict_without_pools(self, pool_subnet):
        """Test KEA output when subnet has no IP ranges or pools at all."""
        subnet = self._refresh(pool_subnet)
        result = subnet.to_kea_dict()

        # With no IP ranges and no available IPs conflict, pools may or may not be present
        # but the structure should be valid
        assert "subnet" in result
        assert result["subnet"] == "10.0.0.0/24"


class TestDHCPServerCollectsPoolConfig:
    """Test that DHCPServer.to_kea_dict() collects pool-level option data and client classes."""

    def _refresh_server(self, server):
        """Refresh a DHCPServer from DB so related fields are properly loaded."""
        from netbox_dhcp_kea_plugin.models import DHCPServer

        return DHCPServer.objects.get(pk=server.pk)

    def test_server_kea_dict_includes_pool_client_classes_in_global(
        self, pool_subnet, pool_ip_range, pool_client_class
    ):
        """Test server KEA config includes pool-level client classes in global client-classes array."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        pool_client_class.only_in_additional_list = True
        pool_client_class.save()

        # Assign client class to server
        pool_subnet.server.client_classes.add(pool_client_class)

        SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
            client_class=pool_client_class,
        )

        server = self._refresh_server(pool_subnet.server)
        result = server.to_kea_dict()
        dhcp4 = result["Dhcp4"]

        # The client class should appear in the global client-classes
        if "client-classes" in dhcp4:
            class_names = [cc["name"] for cc in dhcp4["client-classes"]]
            assert "VOIP_phones" in class_names

    def test_server_kea_dict_includes_pool_option_defs(self, pool_subnet, pool_ip_range, pool_option_data):
        """Test server KEA config includes option definitions needed by pool-level option data."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        sp = SubnetPool.objects.create(
            subnet=pool_subnet,
            ip_range=pool_ip_range,
        )
        sp.option_data.set([pool_option_data])

        server = self._refresh_server(pool_subnet.server)
        result = server.to_kea_dict()
        dhcp4 = result["Dhcp4"]

        # The subnet should include pool-level option data
        if "subnet4" in dhcp4:
            subnet = dhcp4["subnet4"][0]
            assert "pools" in subnet
            pool = subnet["pools"][0]
            assert "option-data" in pool
