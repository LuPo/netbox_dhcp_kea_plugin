#!/usr/bin/env python
"""Tests for client class restriction validations between subnets, pools, and server.

Validates KEA semantics around:
- only_in_additional_list classes used as subnet/pool restricting client_class
- evaluate_additional_classes interactions between pools and subnets
- Server-level detection of unreachable subnet/pool restrictions
"""

import pytest
from django.core.exceptions import ValidationError
from ipam.models import IPRange, Prefix
from netaddr import IPNetwork

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def restriction_prefix(db):
    return Prefix.objects.create(prefix="10.50.0.0/24")


@pytest.fixture
def restriction_prefix_2(db):
    return Prefix.objects.create(prefix="10.51.0.0/24")


@pytest.fixture
def restriction_ip_range(db, restriction_prefix):
    return IPRange.objects.create(
        start_address=IPNetwork("10.50.0.10/24"),
        end_address=IPNetwork("10.50.0.50/24"),
    )


@pytest.fixture
def restriction_ip_range_2(db, restriction_prefix):
    return IPRange.objects.create(
        start_address=IPNetwork("10.50.0.100/24"),
        end_address=IPNetwork("10.50.0.150/24"),
    )


@pytest.fixture
def restriction_ip_range_prefix2(db, restriction_prefix_2):
    return IPRange.objects.create(
        start_address=IPNetwork("10.51.0.10/24"),
        end_address=IPNetwork("10.51.0.50/24"),
    )


@pytest.fixture
def restriction_server(db, service_template, ip_address):
    from netbox_dhcp_kea_plugin.models import DHCPServer

    return DHCPServer.objects.create(
        name="RestrictionTestServer",
        description="Server for restriction tests",
        ip_address=ip_address,
        service_template=service_template,
        status="active",
    )


@pytest.fixture
def restriction_subnet(db, restriction_prefix, restriction_server):
    from netbox_dhcp_kea_plugin.models import Subnet

    subnet = Subnet.objects.create(
        prefix=restriction_prefix,
        server=restriction_server,
        valid_lifetime=3600,
        max_lifetime=7200,
        routers_option_offset=1,
    )
    subnet.refresh_from_db()
    return subnet


@pytest.fixture
def restriction_subnet_2(db, restriction_prefix_2, restriction_server):
    from netbox_dhcp_kea_plugin.models import Subnet

    subnet = Subnet.objects.create(
        prefix=restriction_prefix_2,
        server=restriction_server,
        valid_lifetime=3600,
        max_lifetime=7200,
        routers_option_offset=1,
    )
    subnet.refresh_from_db()
    return subnet


@pytest.fixture
def only_additional_class(db):
    """A client class with only_in_additional_list=True."""
    from netbox_dhcp_kea_plugin.models import ClientClass

    return ClientClass.objects.create(
        name="OnlyAdditionalClass",
        test_expression="option[60].hex == 'special'",
        description="Class only evaluated when in evaluate-additional-classes",
        only_in_additional_list=True,
    )


@pytest.fixture
def normal_class(db):
    """A normal client class (only_in_additional_list=False)."""
    from netbox_dhcp_kea_plugin.models import ClientClass

    return ClientClass.objects.create(
        name="NormalClass",
        test_expression="option[60].hex == 'normal'",
        description="Globally evaluated class",
        only_in_additional_list=False,
    )


@pytest.fixture
def second_only_additional_class(db):
    """A second only_in_additional_list class."""
    from netbox_dhcp_kea_plugin.models import ClientClass

    return ClientClass.objects.create(
        name="SecondOnlyAdditional",
        test_expression="option[60].hex == 'special2'",
        description="Another class only in additional list",
        only_in_additional_list=True,
    )


@pytest.fixture
def normal_class_2(db):
    from netbox_dhcp_kea_plugin.models import ClientClass

    return ClientClass.objects.create(
        name="NormalClass2",
        test_expression="option[60].hex == 'normal2'",
        description="Another globally evaluated class",
        only_in_additional_list=False,
    )


# ===========================================================================
# Subnet-level restriction validations
# ===========================================================================


class TestSubnetClientClassOnlyInAdditionalList:
    """Subnet.clean() must reject a restricting client_class that has
    only_in_additional_list=True because there is no higher scope that
    can trigger its evaluation."""

    def test_rejects_only_in_additional_list_class_as_subnet_restriction(
        self, restriction_subnet, only_additional_class
    ):
        """A subnet's restricting client_class with only_in_additional_list
        should raise ValidationError."""
        restriction_subnet.client_class = only_additional_class
        with pytest.raises(ValidationError) as exc_info:
            restriction_subnet.clean()

        errors = exc_info.value.message_dict
        assert "client_class" in errors
        assert any("only in additional list" in msg.lower() for msg in errors["client_class"])
        assert any("unreachable" in msg.lower() for msg in errors["client_class"])

    def test_allows_normal_class_as_subnet_restriction(self, restriction_subnet, normal_class):
        """A subnet's restricting client_class without only_in_additional_list
        should pass validation."""
        restriction_subnet.client_class = normal_class
        # Should not raise
        restriction_subnet.clean()

    def test_allows_no_restricting_class_on_subnet(self, restriction_subnet):
        """A subnet without a restricting client_class should pass."""
        assert restriction_subnet.client_class is None
        restriction_subnet.clean()

    def test_only_in_additional_list_allowed_in_subnet_evaluate_additional(
        self, restriction_subnet, only_additional_class
    ):
        """An only_in_additional_list class in evaluate_additional_classes
        is valid — that is the intended usage."""
        restriction_subnet.evaluate_additional_classes.add(only_additional_class)
        # clean() should not raise for the evaluate_additional_classes entry
        restriction_subnet.clean()

    def test_normal_class_allowed_in_subnet_evaluate_additional(self, restriction_subnet, normal_class):
        """A normal class in evaluate_additional_classes is redundant but valid."""
        restriction_subnet.evaluate_additional_classes.add(normal_class)
        restriction_subnet.clean()


# ===========================================================================
# Pool-level restriction validations
# ===========================================================================


class TestSubnetPoolClientClassOnlyInAdditionalList:
    """SubnetPool.clean() must reject a restricting client_class that has
    only_in_additional_list=True unless the parent subnet explicitly lists
    that class in evaluate_additional_classes."""

    def test_rejects_only_additional_pool_restriction_without_subnet_eval(
        self, restriction_subnet, restriction_ip_range, only_additional_class
    ):
        """Pool restriction with only_in_additional_list class should fail
        when parent subnet does NOT list it in evaluate_additional_classes."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        pool = SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
            client_class=only_additional_class,
        )
        with pytest.raises(ValidationError) as exc_info:
            pool.clean()

        errors = exc_info.value.message_dict
        assert "client_class" in errors
        assert any("only in additional list" in msg.lower() for msg in errors["client_class"])

    def test_allows_only_additional_pool_restriction_when_subnet_evaluates_it(
        self, restriction_subnet, restriction_ip_range, only_additional_class
    ):
        """Pool restriction with only_in_additional_list class should pass
        when parent subnet lists it in evaluate_additional_classes."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        # Add the class to the subnet's evaluate_additional_classes
        restriction_subnet.evaluate_additional_classes.add(only_additional_class)

        pool = SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
            client_class=only_additional_class,
        )
        # Should not raise
        pool.clean()

    def test_allows_normal_class_as_pool_restriction(self, restriction_subnet, restriction_ip_range, normal_class):
        """A normal class as pool restriction should always pass
        (it's globally evaluated)."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        pool = SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
            client_class=normal_class,
        )
        pool.clean()

    def test_allows_pool_without_restriction(self, restriction_subnet, restriction_ip_range):
        """A pool without a restricting client_class should pass."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        pool = SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
        )
        pool.clean()

    def test_pool_only_additional_with_wrong_class_in_subnet_eval(
        self, restriction_subnet, restriction_ip_range, only_additional_class, second_only_additional_class
    ):
        """Pool restriction with class A should fail even if class B
        is in the subnet's evaluate_additional_classes."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        # Subnet evaluates the SECOND class, not the one used by the pool
        restriction_subnet.evaluate_additional_classes.add(second_only_additional_class)

        pool = SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
            client_class=only_additional_class,
        )
        with pytest.raises(ValidationError) as exc_info:
            pool.clean()

        assert "client_class" in exc_info.value.message_dict


class TestSubnetPoolEvaluateAdditionalClasses:
    """Test that evaluate_additional_classes on pools work correctly
    with only_in_additional_list classes."""

    def test_pool_evaluate_additional_with_only_in_additional_class(
        self, restriction_subnet, restriction_ip_range, only_additional_class
    ):
        """An only_in_additional_list class in pool's evaluate_additional_classes
        is valid — the pool explicitly triggers its evaluation."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        pool = SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
        )
        pool.evaluate_additional_classes.add(only_additional_class)
        pool.clean()

    def test_pool_client_class_not_in_own_evaluate_additional(
        self, restriction_subnet, restriction_ip_range, normal_class
    ):
        """A pool's client_class must not also be in its own
        evaluate_additional_classes."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        pool = SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
            client_class=normal_class,
        )
        pool.evaluate_additional_classes.add(normal_class)

        with pytest.raises(ValidationError) as exc_info:
            pool.clean()

        assert "client_class" in exc_info.value.message_dict
        assert any("evaluate-additional-classes" in msg.lower() for msg in exc_info.value.message_dict["client_class"])


# ===========================================================================
# Cross-level interaction tests
# ===========================================================================


class TestCrossLevelClientClassInteraction:
    """Test interactions between subnet-level and pool-level client class
    configurations."""

    def test_subnet_restriction_with_pool_restriction_both_normal(
        self, restriction_subnet, restriction_ip_range, normal_class, normal_class_2
    ):
        """Both subnet and pool having normal restricting classes is valid.
        Clients must match both to use the pool."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        restriction_subnet.client_class = normal_class
        restriction_subnet.save()
        restriction_subnet.refresh_from_db()
        restriction_subnet.clean()

        pool = SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
            client_class=normal_class_2,
        )
        pool.clean()

    def test_subnet_eval_additional_enables_pool_restriction(
        self, restriction_subnet, restriction_ip_range, only_additional_class
    ):
        """When subnet evaluates a class via evaluate_additional_classes,
        pools can use it as restriction."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        restriction_subnet.evaluate_additional_classes.add(only_additional_class)

        pool = SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
            client_class=only_additional_class,
        )
        # Should pass since subnet triggers evaluation
        pool.clean()

    def test_removing_class_from_subnet_eval_makes_pool_invalid(
        self, restriction_subnet, restriction_ip_range, only_additional_class
    ):
        """If the class is removed from subnet's evaluate_additional_classes,
        the pool restriction becomes unreachable."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        # First add so pool can be created
        restriction_subnet.evaluate_additional_classes.add(only_additional_class)
        pool = SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
            client_class=only_additional_class,
        )
        pool.clean()  # Should pass

        # Now remove from subnet
        restriction_subnet.evaluate_additional_classes.remove(only_additional_class)

        # Pool clean should now fail
        with pytest.raises(ValidationError) as exc_info:
            pool.clean()

        assert "client_class" in exc_info.value.message_dict

    def test_multiple_pools_different_restrictions(
        self, restriction_subnet, restriction_ip_range, restriction_ip_range_2, only_additional_class, normal_class
    ):
        """Different pools in the same subnet can have different restriction
        types."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        restriction_subnet.evaluate_additional_classes.add(only_additional_class)

        # Pool 1: only_in_additional_list class (valid because subnet evals it)
        pool1 = SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
            client_class=only_additional_class,
        )
        pool1.clean()

        # Pool 2: normal class (always valid)
        pool2 = SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range_2,
            client_class=normal_class,
        )
        pool2.clean()


# ===========================================================================
# Server-level detection methods
# ===========================================================================


class TestServerUnreachableSubnetRestrictions:
    """Test DHCPServer.get_unreachable_subnet_restrictions()."""

    def test_no_unreachable_when_no_subnets(self, restriction_server):
        assert restriction_server.get_unreachable_subnet_restrictions() == []

    def test_no_unreachable_with_normal_restriction(self, restriction_server, restriction_subnet, normal_class):
        restriction_subnet.client_class = normal_class
        restriction_subnet.save()

        assert restriction_server.get_unreachable_subnet_restrictions() == []

    def test_detects_unreachable_subnet(self, restriction_server, restriction_subnet, only_additional_class):
        """Server should detect a subnet with only_in_additional_list
        restricting class."""
        # Bypass model validation to simulate pre-existing bad data
        from netbox_dhcp_kea_plugin.models import Subnet

        Subnet.objects.filter(pk=restriction_subnet.pk).update(client_class=only_additional_class)
        restriction_subnet.refresh_from_db()

        unreachable = restriction_server.get_unreachable_subnet_restrictions()
        assert len(unreachable) == 1
        assert unreachable[0].pk == restriction_subnet.pk

    def test_detects_multiple_unreachable_subnets(
        self,
        restriction_server,
        restriction_subnet,
        restriction_subnet_2,
        only_additional_class,
        second_only_additional_class,
    ):
        """Server should detect multiple unreachable subnets."""
        from netbox_dhcp_kea_plugin.models import Subnet

        Subnet.objects.filter(pk=restriction_subnet.pk).update(client_class=only_additional_class)
        Subnet.objects.filter(pk=restriction_subnet_2.pk).update(client_class=second_only_additional_class)

        unreachable = restriction_server.get_unreachable_subnet_restrictions()
        assert len(unreachable) == 2

    def test_no_unreachable_without_restriction(self, restriction_server, restriction_subnet):
        """Subnets without a restricting class should not appear."""
        assert restriction_subnet.client_class is None
        assert restriction_server.get_unreachable_subnet_restrictions() == []


class TestServerUnreachablePoolRestrictions:
    """Test DHCPServer.get_unreachable_pool_restrictions()."""

    def test_no_unreachable_when_no_pools(self, restriction_server, restriction_subnet):
        assert restriction_server.get_unreachable_pool_restrictions() == []

    def test_no_unreachable_with_normal_pool_restriction(
        self, restriction_server, restriction_subnet, restriction_ip_range, normal_class
    ):
        from netbox_dhcp_kea_plugin.models import SubnetPool

        SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
            client_class=normal_class,
        )
        assert restriction_server.get_unreachable_pool_restrictions() == []

    def test_detects_unreachable_pool(
        self, restriction_server, restriction_subnet, restriction_ip_range, only_additional_class
    ):
        """Pool with only_in_additional_list restriction not in subnet's
        evaluate_additional_classes should be detected."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        pool = SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
            client_class=only_additional_class,
        )

        unreachable = restriction_server.get_unreachable_pool_restrictions()
        assert len(unreachable) == 1
        assert unreachable[0].pk == pool.pk

    def test_no_unreachable_when_subnet_evaluates_class(
        self, restriction_server, restriction_subnet, restriction_ip_range, only_additional_class
    ):
        """Pool should NOT be detected as unreachable when parent subnet
        lists the class in evaluate_additional_classes."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        restriction_subnet.evaluate_additional_classes.add(only_additional_class)

        SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
            client_class=only_additional_class,
        )

        assert restriction_server.get_unreachable_pool_restrictions() == []

    def test_pool_without_restriction_not_detected(self, restriction_server, restriction_subnet, restriction_ip_range):
        from netbox_dhcp_kea_plugin.models import SubnetPool

        SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
        )
        assert restriction_server.get_unreachable_pool_restrictions() == []

    def test_detects_pool_across_multiple_subnets(
        self,
        restriction_server,
        restriction_subnet,
        restriction_subnet_2,
        restriction_ip_range,
        restriction_ip_range_prefix2,
        only_additional_class,
        second_only_additional_class,
    ):
        """Pools across different subnets should all be checked."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        pool1 = SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
            client_class=only_additional_class,
        )
        pool2 = SubnetPool.objects.create(
            subnet=restriction_subnet_2,
            ip_range=restriction_ip_range_prefix2,
            client_class=second_only_additional_class,
        )

        unreachable = restriction_server.get_unreachable_pool_restrictions()
        unreachable_ids = {p.pk for p in unreachable}
        assert pool1.pk in unreachable_ids
        assert pool2.pk in unreachable_ids

    def test_mixed_reachable_and_unreachable_pools(
        self,
        restriction_server,
        restriction_subnet,
        restriction_ip_range,
        restriction_ip_range_2,
        only_additional_class,
        normal_class,
    ):
        """Only unreachable pools should be detected, not all pools."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        unreachable_pool = SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
            client_class=only_additional_class,
        )
        SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range_2,
            client_class=normal_class,
        )

        unreachable = restriction_server.get_unreachable_pool_restrictions()
        assert len(unreachable) == 1
        assert unreachable[0].pk == unreachable_pool.pk


# ===========================================================================
# Server get_unused_only_in_additional_list_classes integration
# ===========================================================================


class TestServerUnusedOnlyInAdditionalListIntegration:
    """Test that get_unused_only_in_additional_list_classes works with
    the new subnet/pool client class fields."""

    def test_class_used_as_subnet_restriction_is_not_unused(
        self, restriction_server, restriction_subnet, only_additional_class
    ):
        """An only_in_additional_list class used as subnet restriction
        should not appear as unused (even though it's a misconfiguration,
        it IS referenced)."""
        from netbox_dhcp_kea_plugin.models import Subnet

        only_additional_class.servers.add(restriction_server)
        Subnet.objects.filter(pk=restriction_subnet.pk).update(client_class=only_additional_class)
        restriction_subnet.refresh_from_db()

        unused = restriction_server.get_unused_only_in_additional_list_classes()
        assert only_additional_class not in unused

    def test_class_used_in_subnet_eval_additional_is_not_unused(
        self, restriction_server, restriction_subnet, only_additional_class
    ):
        only_additional_class.servers.add(restriction_server)
        restriction_subnet.evaluate_additional_classes.add(only_additional_class)

        unused = restriction_server.get_unused_only_in_additional_list_classes()
        assert only_additional_class not in unused

    def test_class_used_in_pool_restriction_is_not_unused(
        self, restriction_server, restriction_subnet, restriction_ip_range, only_additional_class
    ):
        from netbox_dhcp_kea_plugin.models import SubnetPool

        only_additional_class.servers.add(restriction_server)
        SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
            client_class=only_additional_class,
        )

        unused = restriction_server.get_unused_only_in_additional_list_classes()
        assert only_additional_class not in unused

    def test_class_used_in_pool_eval_additional_is_not_unused(
        self, restriction_server, restriction_subnet, restriction_ip_range, only_additional_class
    ):
        from netbox_dhcp_kea_plugin.models import SubnetPool

        only_additional_class.servers.add(restriction_server)
        pool = SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
        )
        pool.evaluate_additional_classes.add(only_additional_class)

        unused = restriction_server.get_unused_only_in_additional_list_classes()
        assert only_additional_class not in unused

    def test_class_not_used_anywhere_is_unused(self, restriction_server, restriction_subnet, only_additional_class):
        only_additional_class.servers.add(restriction_server)

        unused = restriction_server.get_unused_only_in_additional_list_classes()
        assert only_additional_class in unused


# ===========================================================================
# KEA config output correctness
# ===========================================================================


class TestKeaConfigClientClassConsistency:
    """Test that to_kea_dict output is consistent with client class
    restriction semantics."""

    def test_subnet_restriction_appears_in_kea_output(self, restriction_server, restriction_subnet, normal_class):
        """A subnet's restricting class should appear in the KEA config
        both in the global client-classes array and as the subnet's
        client-class field."""
        restriction_subnet.client_class = normal_class
        restriction_subnet.save()

        kea = restriction_server.to_kea_dict()
        dhcp4 = kea["Dhcp4"]

        # Class should be in global client-classes
        class_names = [cc["name"] for cc in dhcp4.get("client-classes", [])]
        assert normal_class.name in class_names

        # Subnet should reference it
        subnet4 = dhcp4.get("subnet4", [])
        assert len(subnet4) == 1
        assert subnet4[0]["client-class"] == normal_class.name

    def test_subnet_eval_additional_appears_in_kea_output(
        self, restriction_server, restriction_subnet, only_additional_class
    ):
        """A class in subnet's evaluate_additional_classes should appear in
        the KEA config's subnet evaluate-additional-classes list."""
        restriction_subnet.evaluate_additional_classes.add(only_additional_class)

        kea = restriction_server.to_kea_dict()
        dhcp4 = kea["Dhcp4"]

        # Class should be in global client-classes
        class_names = [cc["name"] for cc in dhcp4.get("client-classes", [])]
        assert only_additional_class.name in class_names

        # Subnet should list it in evaluate-additional-classes
        subnet4 = dhcp4.get("subnet4", [])
        assert len(subnet4) == 1
        assert only_additional_class.name in subnet4[0].get("evaluate-additional-classes", [])

    def test_only_in_additional_list_flag_in_kea_class_output(
        self, restriction_server, restriction_subnet, only_additional_class
    ):
        """A class with only_in_additional_list=True should have the
        only-in-additional-list flag set in its KEA definition."""
        restriction_subnet.evaluate_additional_classes.add(only_additional_class)

        kea = restriction_server.to_kea_dict()
        dhcp4 = kea["Dhcp4"]

        kea_classes = {cc["name"]: cc for cc in dhcp4.get("client-classes", [])}
        assert only_additional_class.name in kea_classes
        assert kea_classes[only_additional_class.name].get("only-in-additional-list") is True

    def test_normal_class_no_only_in_additional_list_flag(self, restriction_server, restriction_subnet, normal_class):
        """A normal class should NOT have only-in-additional-list in output."""
        restriction_subnet.client_class = normal_class
        restriction_subnet.save()

        kea = restriction_server.to_kea_dict()
        dhcp4 = kea["Dhcp4"]

        kea_classes = {cc["name"]: cc for cc in dhcp4.get("client-classes", [])}
        assert normal_class.name in kea_classes
        assert "only-in-additional-list" not in kea_classes[normal_class.name]

    def test_pool_restriction_appears_in_kea_subnet_pools(
        self, restriction_server, restriction_subnet, restriction_ip_range, normal_class
    ):
        """A pool's restricting class should appear in the pool dict
        within the subnet's pools list."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
            client_class=normal_class,
        )

        kea = restriction_server.to_kea_dict()
        dhcp4 = kea["Dhcp4"]

        subnet4 = dhcp4.get("subnet4", [])
        assert len(subnet4) == 1
        pools = subnet4[0].get("pools", [])

        # Find the pool with our range
        matching_pools = [p for p in pools if "10.50.0.10" in p["pool"] and "10.50.0.50" in p["pool"]]
        assert len(matching_pools) == 1
        assert matching_pools[0]["client-class"] == normal_class.name

    def test_pool_eval_additional_appears_in_kea_pool_dict(
        self, restriction_server, restriction_subnet, restriction_ip_range, only_additional_class
    ):
        """A pool's evaluate_additional_classes should appear in the pool dict."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        pool = SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
        )
        pool.evaluate_additional_classes.add(only_additional_class)

        kea = restriction_server.to_kea_dict()
        dhcp4 = kea["Dhcp4"]

        subnet4 = dhcp4.get("subnet4", [])
        pools = subnet4[0].get("pools", [])
        matching_pools = [p for p in pools if "10.50.0.10" in p["pool"] and "10.50.0.50" in p["pool"]]
        assert len(matching_pools) == 1
        assert only_additional_class.name in matching_pools[0].get("evaluate-additional-classes", [])

    def test_server_globally_assigned_classes_in_kea_output(
        self, restriction_server, restriction_subnet, normal_class, only_additional_class
    ):
        """Classes assigned directly to the server should appear in the
        global client-classes array regardless of subnet/pool usage."""
        normal_class.servers.add(restriction_server)
        only_additional_class.servers.add(restriction_server)

        kea = restriction_server.to_kea_dict()
        dhcp4 = kea["Dhcp4"]

        class_names = [cc["name"] for cc in dhcp4.get("client-classes", [])]
        assert normal_class.name in class_names
        assert only_additional_class.name in class_names

    def test_classes_from_all_levels_collected_in_global_array(
        self,
        restriction_server,
        restriction_subnet,
        restriction_ip_range,
        normal_class,
        normal_class_2,
        only_additional_class,
        second_only_additional_class,
    ):
        """All client classes from server, subnet, and pool levels must
        appear in the global client-classes array."""
        from netbox_dhcp_kea_plugin.models import SubnetPool

        # Server-level class
        normal_class.servers.add(restriction_server)

        # Subnet-level classes
        restriction_subnet.client_class = normal_class_2
        restriction_subnet.save()
        restriction_subnet.evaluate_additional_classes.add(only_additional_class)

        # Pool-level class
        pool = SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
        )
        pool.evaluate_additional_classes.add(second_only_additional_class)

        kea = restriction_server.to_kea_dict()
        dhcp4 = kea["Dhcp4"]

        class_names = {cc["name"] for cc in dhcp4.get("client-classes", [])}
        assert normal_class.name in class_names
        assert normal_class_2.name in class_names
        assert only_additional_class.name in class_names
        assert second_only_additional_class.name in class_names


# ===========================================================================
# HA server delegation
# ===========================================================================


class TestHAServerRestrictionChecks:
    """For HA standby/secondary servers, restriction checks should
    return empty lists since they inherit from the primary."""

    def test_standby_returns_empty_unreachable_subnets(self, db, service_template):
        from ipam.models import IPAddress

        from netbox_dhcp_kea_plugin.models import DHCPHARelationship, DHCPServer

        ha = DHCPHARelationship.objects.create(name="test-ha", mode="hot-standby")

        ip1 = IPAddress.objects.create(address="10.99.0.1/24")
        ip2 = IPAddress.objects.create(address="10.99.0.2/24")

        primary = DHCPServer.objects.create(
            name="HA-Primary",
            ip_address=ip1,
            service_template=service_template,
            status="active",
            ha_relationship=ha,
            ha_role="primary",
            ha_url="http://10.99.0.1:8000/",
        )
        standby = DHCPServer.objects.create(
            name="HA-Standby",
            ip_address=ip2,
            service_template=service_template,
            status="active",
            ha_relationship=ha,
            ha_role="standby",
            ha_url="http://10.99.0.2:8000/",
        )

        assert standby.get_unreachable_subnet_restrictions() == []
        assert standby.get_unreachable_pool_restrictions() == []

    def test_primary_still_checks_restrictions(self, db, service_template):
        from ipam.models import IPAddress, Prefix

        from netbox_dhcp_kea_plugin.models import (
            ClientClass,
            DHCPHARelationship,
            DHCPServer,
            Subnet,
        )

        ha = DHCPHARelationship.objects.create(name="test-ha-2", mode="hot-standby")

        ip1 = IPAddress.objects.create(address="10.98.0.1/24")
        ip2 = IPAddress.objects.create(address="10.98.0.2/24")

        primary = DHCPServer.objects.create(
            name="HA-Primary-2",
            ip_address=ip1,
            service_template=service_template,
            status="active",
            ha_relationship=ha,
            ha_role="primary",
            ha_url="http://10.98.0.1:8000/",
        )
        DHCPServer.objects.create(
            name="HA-Standby-2",
            ip_address=ip2,
            service_template=service_template,
            status="active",
            ha_relationship=ha,
            ha_role="standby",
            ha_url="http://10.98.0.2:8000/",
        )

        cc = ClientClass.objects.create(
            name="HA-Only-Additional",
            test_expression="option[60].hex == 'ha'",
            only_in_additional_list=True,
        )

        prefix = Prefix.objects.create(prefix="10.98.0.0/24")
        subnet = Subnet.objects.create(
            prefix=prefix,
            server=primary,
            valid_lifetime=3600,
            max_lifetime=7200,
            routers_option_offset=1,
        )
        # Bypass validation to create bad data
        Subnet.objects.filter(pk=subnet.pk).update(client_class=cc)

        unreachable = primary.get_unreachable_subnet_restrictions()
        assert len(unreachable) == 1


# ===========================================================================
# Form-level validation tests
# ===========================================================================


class TestSubnetFormClientClassValidation:
    """Test SubnetForm.clean() validates only_in_additional_list restriction."""

    def test_form_rejects_only_additional_restriction(self, restriction_subnet, only_additional_class):
        """Model-level clean() should reject only_in_additional_list class
        as subnet restriction."""
        restriction_subnet.client_class = only_additional_class
        with pytest.raises(ValidationError) as exc_info:
            restriction_subnet.clean()

        assert "client_class" in exc_info.value.message_dict

    def test_form_allows_normal_restriction(self, restriction_subnet, normal_class):
        """Model-level clean() should allow a normal class as subnet restriction."""
        restriction_subnet.client_class = normal_class
        restriction_subnet.clean()


class TestSubnetPoolFormClientClassValidation:
    """Test SubnetPoolForm.clean() validates only_in_additional_list
    restriction against parent subnet's evaluate_additional_classes."""

    def test_form_rejects_unreachable_pool_restriction(
        self, restriction_subnet, restriction_ip_range, only_additional_class
    ):
        from netbox_dhcp_kea_plugin.models import SubnetPool

        pool = SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
            client_class=only_additional_class,
        )
        with pytest.raises(ValidationError) as exc_info:
            pool.clean()

        assert "client_class" in exc_info.value.message_dict

    def test_form_allows_reachable_pool_restriction(
        self, restriction_subnet, restriction_ip_range, only_additional_class
    ):
        from netbox_dhcp_kea_plugin.models import SubnetPool

        restriction_subnet.evaluate_additional_classes.add(only_additional_class)

        pool = SubnetPool.objects.create(
            subnet=restriction_subnet,
            ip_range=restriction_ip_range,
            client_class=only_additional_class,
        )
        pool.clean()
