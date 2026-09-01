"""Levers for decline-driven pool starvation.

A client stuck in a DHCPDECLINE loop walks a pool: each declined lease is put
into probation and the next DISCOVER gets a fresh address. These three fields
are what the plugin can express about that — the probation window itself, and
the two class/subnet constructs the limits hook and per-client classification
need.
"""

import re

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

    def test_the_client_class_label_column_is_pinned(self, client, admin_user):
        """NetBox sizes attr-table labels to content, so they otherwise move.

        A long test expression squeezes the label column, and every class then
        renders its labels at a different position.
        """
        from netbox_dhcp_kea_plugin.models import ClientClass

        cls = ClientClass.objects.create(
            name="wide-class",
            test_expression="ifelse(pkt4.msgtype == 4, hexstring(pkt4.mac, ':'), '') " * 3,
        )

        response = self._get(client, admin_user, "clientclass", cls.pk)

        assert b"table-layout: fixed" in response.content
        # The exact split is a design choice; that one is pinned at all is not.
        assert re.search(rb"<col style=\"width: \d+%;\">", response.content)
        # Django's {# #} is single-line only, so a multi-line one renders as
        # text instead of being stripped.
        assert b"NetBox sizes attr-table labels" not in response.content

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
        # Right-hand column: past Configuration Summary, which ends the left one.
        content = response.content
        assert content.index(b'card-header">Configuration Summary<') < content.index(
            b'card-header">Lease Handling<'
        )

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


@pytest.mark.django_db
class TestServerCardsAlign:
    """Values should line up down the page, not per-card.

    With table-layout auto, a card whose values are short (a tick, a count)
    lets the label column expand to most of the width, while a card with a
    long value pulls it back — so the value column lands somewhere different
    in every card.
    """

    def test_every_attr_table_pins_the_same_split(
        self, client, admin_user, dhcp_server_factory
    ):
        from django.urls import reverse

        server = dhcp_server_factory(name="kea-align", ip_suffix=195)
        client.force_login(admin_user)

        content = client.get(
            reverse("plugins:netbox_dhcp_kea_plugin:dhcpserver", kwargs={"pk": server.pk})
        ).content

        # Every attr-table on the page is pinned, and all to the same width —
        # aligning them with each other is the whole point.
        assert content.count(b'attr-table" style="table-layout: fixed;"') == content.count(
            b'class="table table-hover attr-table'
        )
        # Aligning the cards with each other is the point, so they must all use
        # the same split — whatever that split happens to be.
        widths = set(re.findall(rb"<col style=\"width: (\d+)%;\">", content))
        assert len(widths) == 1, f"cards disagree on column width: {widths}"


@pytest.mark.django_db
class TestLeaseTimers:
    """T1/T2 at all three levels KEA accepts them: global, subnet, client class."""

    def test_the_global_lifetimes_are_editable(self, dhcp_server_factory):
        """They were hardcoded at 3600/7200 before, so defaults must not move."""
        server = dhcp_server_factory(name="kea-timers-default", ip_suffix=201)

        dhcp4 = server.to_kea_dict()["Dhcp4"]

        assert dhcp4["valid-lifetime"] == 3600
        assert dhcp4["max-valid-lifetime"] == 7200
        # Optional, so absent unless chosen.
        assert "renew-timer" not in dhcp4
        assert "rebind-timer" not in dhcp4

    def test_global_timers_are_emitted_when_set(self, dhcp_server_factory):
        server = dhcp_server_factory(name="kea-timers-global", ip_suffix=202)
        server.valid_lifetime = 3600
        server.renew_timer = 900
        server.rebind_timer = 1800
        server.save()

        dhcp4 = server.to_kea_dict()["Dhcp4"]

        assert (dhcp4["renew-timer"], dhcp4["rebind-timer"]) == (900, 1800)

    def test_subnet_timers_are_emitted_when_set(self, subnet_factory):
        subnet = subnet_factory()
        subnet.renew_timer = 450
        subnet.rebind_timer = 900
        subnet.save()

        result = subnet.to_kea_dict()

        assert (result["renew-timer"], result["rebind-timer"]) == (450, 900)

    def test_a_subnet_without_timers_emits_none(self, subnet_factory):
        result = subnet_factory().to_kea_dict()

        assert "renew-timer" not in result
        assert "rebind-timer" not in result

    def test_client_class_timers_are_emitted_when_set(self):
        """Per-class lifetimes need KEA 1.9.5 or later."""
        from netbox_dhcp_kea_plugin.models import ClientClass

        cls = ClientClass.objects.create(
            name="short-lease",
            test_expression="pkt4.msgtype == 4",
            valid_lifetime=600,
            renew_timer=150,
            rebind_timer=300,
        )

        result = cls.to_kea_dict()

        assert result["valid-lifetime"] == 600
        assert (result["renew-timer"], result["rebind-timer"]) == (150, 300)

    def test_a_client_class_without_timers_emits_none(self):
        from netbox_dhcp_kea_plugin.models import ClientClass

        cls = ClientClass.objects.create(name="inherits", test_expression="")

        result = cls.to_kea_dict()

        for key in ("valid-lifetime", "renew-timer", "rebind-timer"):
            assert key not in result


@pytest.mark.django_db
class TestLeaseTimerOrdering:
    """KEA silently drops misordered timers rather than complaining.

    Option 58 is sent only when renew < rebind, and option 59 only when
    rebind < valid. A misordered set looks configured and does nothing, so it
    is rejected here instead.
    """

    def test_renew_must_be_below_rebind(self, dhcp_server_factory):
        server = dhcp_server_factory(name="kea-timers-bad1", ip_suffix=203)
        server.renew_timer = 1800
        server.rebind_timer = 900

        with pytest.raises(ValidationError) as exc:
            server.clean()

        assert "renew_timer" in exc.value.message_dict

    def test_rebind_must_be_below_the_valid_lifetime(self, dhcp_server_factory):
        server = dhcp_server_factory(name="kea-timers-bad2", ip_suffix=204)
        server.valid_lifetime = 3600
        server.renew_timer = 900
        server.rebind_timer = 7200

        with pytest.raises(ValidationError) as exc:
            server.clean()

        assert "rebind_timer" in exc.value.message_dict

    def test_a_correct_ordering_passes(self, dhcp_server_factory):
        server = dhcp_server_factory(name="kea-timers-ok", ip_suffix=205)
        server.valid_lifetime = 3600
        server.renew_timer = 900
        server.rebind_timer = 1800

        server.clean()

    def test_a_class_with_no_lifetime_only_checks_the_timers(self):
        """valid_lifetime is optional on a class, so that half is skipped."""
        from netbox_dhcp_kea_plugin.models import ClientClass

        ClientClass(name="partial", test_expression="", renew_timer=100, rebind_timer=200).clean()

        bad = ClientClass(name="partial-bad", test_expression="", renew_timer=300, rebind_timer=200)
        with pytest.raises(ValidationError):
            bad.clean()

    def test_the_subnet_is_checked_too(self, subnet_factory):
        subnet = subnet_factory()
        subnet.renew_timer = 5000
        subnet.rebind_timer = 6000  # above valid_lifetime

        with pytest.raises(ValidationError) as exc:
            subnet.clean()

        assert "rebind_timer" in exc.value.message_dict
