"""Levers for decline-driven pool starvation.

A client stuck in a DHCPDECLINE loop walks a pool: each declined lease is put
into probation and the next DISCOVER gets a fresh address. These three fields
are what the plugin can express about that — the probation window itself, and
the two class/subnet constructs the limits hook and per-client classification
need.
"""

import pytest
from django.core.exceptions import ValidationError


@pytest.mark.django_db
class TestDeclineProbationPeriod:
    """KEA's default holds an address for a full day per decline."""

    def test_it_is_omitted_when_unset(self, dhcp_server_factory):
        server = dhcp_server_factory(name="kea-decline-default", ip_suffix=181)

        dhcp4 = server.to_kea_dict()["Dhcp4"]

        # Absent rather than defaulted: the config should not assert a value
        # the operator never chose.
        assert "decline-probation-period" not in dhcp4

    def test_it_is_emitted_when_set(self, dhcp_server_factory):
        server = dhcp_server_factory(name="kea-decline-set", ip_suffix=182)
        server.decline_probation_period = 120
        server.save()

        assert server.to_kea_dict()["Dhcp4"]["decline-probation-period"] == 120

    def test_zero_is_kept_not_treated_as_unset(self, dhcp_server_factory):
        """0 means "return the address immediately" — a real choice, not a blank."""
        server = dhcp_server_factory(name="kea-decline-zero", ip_suffix=183)
        server.decline_probation_period = 0
        server.save()

        assert server.to_kea_dict()["Dhcp4"]["decline-probation-period"] == 0


@pytest.mark.django_db
class TestClientClassTemplate:
    """template-test spawns one subclass per distinct evaluated value."""

    def _cls(self, **kwargs):
        from netbox_dhcp_kea_plugin.models import ClientClass

        defaults = {"name": "declines", "test_expression": "pkt4.msgtype == 4"}
        defaults.update(kwargs)
        return ClientClass.objects.create(**defaults)

    def test_a_plain_class_still_renders_test(self):
        cls = self._cls()

        result = cls.to_kea_dict()

        assert result["test"] == "pkt4.msgtype == 4"
        assert "template-test" not in result

    def test_a_template_class_renders_template_test(self):
        cls = self._cls(
            name="per-mac",
            test_expression="ifelse(pkt4.msgtype == 4, hexstring(pkt4.mac, ':'), '')",
            template_test=True,
        )

        result = cls.to_kea_dict()

        assert result["template-test"] == "ifelse(pkt4.msgtype == 4, hexstring(pkt4.mac, ':'), '')"
        # Exactly one of the two keys, never both.
        assert "test" not in result

    def test_a_template_class_needs_an_expression(self):
        from netbox_dhcp_kea_plugin.models import ClientClass

        cls = ClientClass(name="empty-template", test_expression="", template_test=True)

        with pytest.raises(ValidationError) as exc:
            cls.clean()

        assert "test_expression" in exc.value.message_dict

    def test_an_unconditional_plain_class_is_still_allowed(self):
        from netbox_dhcp_kea_plugin.models import ClientClass

        ClientClass(name="always", test_expression="").clean()


@pytest.mark.django_db
class TestUserContext:
    """The limits hook takes its configuration from user-context."""

    LIMITS = {"limits": {"rate-limit": "10 packets per second"}}

    def test_a_class_renders_its_user_context(self):
        from netbox_dhcp_kea_plugin.models import ClientClass

        cls = ClientClass.objects.create(
            name="rate-limited", test_expression="pkt4.msgtype == 4", user_context=self.LIMITS
        )

        assert cls.to_kea_dict()["user-context"] == self.LIMITS

    def test_a_class_without_one_emits_no_key(self):
        from netbox_dhcp_kea_plugin.models import ClientClass

        cls = ClientClass.objects.create(name="plain", test_expression="pkt4.msgtype == 4")

        assert "user-context" not in cls.to_kea_dict()

    def test_a_subnet_renders_its_user_context(self, subnet_factory):
        subnet = subnet_factory()
        subnet.user_context = {"limits": {"address-limit": 50}}
        subnet.save()

        assert subnet.to_kea_dict()["user-context"] == {"limits": {"address-limit": 50}}

    def test_a_subnet_without_one_emits_no_key(self, subnet_factory):
        subnet = subnet_factory()

        assert "user-context" not in subnet.to_kea_dict()

    @pytest.mark.parametrize("bad", [["a", "list"], "a string", 42, True])
    def test_a_non_object_is_rejected(self, bad):
        """KEA reads user-context as a map and refuses to start otherwise."""
        from netbox_dhcp_kea_plugin.models import ClientClass

        cls = ClientClass(name="bad-context", test_expression="", user_context=bad)

        with pytest.raises(ValidationError) as exc:
            cls.clean()

        assert "user_context" in exc.value.message_dict

    def test_a_subnet_rejects_a_non_object_too(self, subnet_factory):
        subnet = subnet_factory()
        subnet.user_context = ["not", "a", "map"]

        with pytest.raises(ValidationError) as exc:
            subnet.clean()

        assert "user_context" in exc.value.message_dict

    def test_an_empty_object_is_allowed_and_omitted(self):
        from netbox_dhcp_kea_plugin.models import ClientClass

        cls = ClientClass(name="empty-context", test_expression="", user_context={})
        cls.clean()
        cls.save()

        assert "user-context" not in cls.to_kea_dict()


@pytest.mark.django_db
class TestNewFieldsRenderOnDetailPages:
    """The three detail templates were edited; only one was covered before.

    A malformed template fails at render time and nowhere else, so each page is
    actually fetched here rather than inspected as a file.
    """

    def _get(self, client, admin_user, url_name, pk):
        from django.urls import reverse

        client.force_login(admin_user)
        return client.get(reverse(f"plugins:netbox_dhcp_kea_plugin:{url_name}", kwargs={"pk": pk}))

    def test_the_client_class_page_shows_both_fields(self, client, admin_user):
        from netbox_dhcp_kea_plugin.models import ClientClass

        cls = ClientClass.objects.create(
            name="rendered-class",
            test_expression="pkt4.msgtype == 4",
            template_test=True,
            user_context={"limits": {"rate-limit": "3 packets per hour"}},
        )

        response = self._get(client, admin_user, "clientclass", cls.pk)

        assert response.status_code == 200
        assert b"Template Class" in response.content
        assert b"User Context" in response.content
        assert b"rate-limit" in response.content

    def test_the_subnet_page_shows_user_context(self, client, admin_user, subnet_factory):
        subnet = subnet_factory()
        subnet.user_context = {"limits": {"address-limit": 50}}
        subnet.save()

        response = self._get(client, admin_user, "subnet", subnet.pk)

        assert response.status_code == 200
        assert b"User Context" in response.content
        assert b"address-limit" in response.content

    def test_the_server_page_names_the_kea_default(self, client, admin_user, dhcp_server_factory):
        """Blank is not nothing — it means a full day per declined address."""
        server = dhcp_server_factory(name="kea-render-default", ip_suffix=191)

        response = self._get(client, admin_user, "dhcpserver", server.pk)

        assert response.status_code == 200
        assert b"Decline Probation Period" in response.content
        assert b"86400 seconds (KEA default)" in response.content

    def test_the_server_page_shows_a_configured_value(
        self, client, admin_user, dhcp_server_factory
    ):
        server = dhcp_server_factory(name="kea-render-set", ip_suffix=192)
        server.decline_probation_period = 120
        server.save()

        response = self._get(client, admin_user, "dhcpserver", server.pk)

        assert b"120 seconds" in response.content
        assert b"KEA default" not in response.content


@pytest.mark.django_db
class TestRouterIPWithAnUnsavedPrefix:
    """get_router_ip() lacked the string guard clean() has.

    Prefix.prefix only comes back as an IPNetwork once it has round-tripped
    through the database. Before that it is whatever was passed in, and
    to_kea_dict() reaches this method — so it raised AttributeError rather than
    returning an address.
    """

    @staticmethod
    def _expected_first_address(subnet):
        import netaddr

        return str(netaddr.IPNetwork(str(subnet.prefix.prefix)).network + 1)

    def test_it_handles_a_string_prefix(self, subnet_factory):
        subnet = subnet_factory()
        subnet.routers_option_offset = 1

        # Previously raised AttributeError: 'str' object has no attribute 'network'
        assert subnet.get_router_ip() == self._expected_first_address(subnet)

    def test_to_kea_dict_emits_the_routers_option(self, subnet_factory):
        subnet = subnet_factory()
        subnet.routers_option_offset = 1
        subnet.save()

        routers = [o for o in subnet.to_kea_dict()["option-data"] if o["name"] == "routers"]

        assert routers and routers[0]["data"] == self._expected_first_address(subnet)
