"""DDNS configuration KEA 3.0 refuses to load, and TSIG secrets leaking past their permission.

Each rule here was checked against KEA 3.0's own grammar and parsers
(dhcp4_parser.yy, d2_parser.yy, d2_client_cfg.cc, d2_config.cc), not prose.
Fixtures are reused from test_ddns_models.
"""

# ruff: noqa: F811 — test parameters shadow the fixtures imported for pytest.

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from netbox.plugins.utils import get_plugin_config
from rest_framework.test import APIClient

from tests.test_ddns_models import (  # noqa: F401
    _make_zone,
    d2_daemon,
    d2_listener_ip,
    forward_zone,
    name_server,
    tsig_key,
)


pytestmark = pytest.mark.django_db

ddns_routes = pytest.mark.skipif(
    not get_plugin_config("netbox_dhcp_kea_plugin", "enable_ddns"),
    reason="enable_ddns plugin flag is off — DDNS routes not registered",
)


def _grant(user, model, *actions):
    from core.models import ObjectType
    from users.models import ObjectPermission

    op = ObjectPermission.objects.create(
        name=f"perm-{user.pk}-{model.__name__}-{'-'.join(actions)}", actions=list(actions)
    )
    op.users.add(user)
    op.object_types.add(ObjectType.objects.get_for_model(model))
    return op


def _vault_key(name="vault-key"):
    from netbox_dhcp_kea_plugin.models import TSIGKey

    return TSIGKey.objects.create(
        name=name,
        algorithm="HMAC-SHA256",
        secret_backend="vault",
        secret_ref=f"kea/tsig/{name}#secret",
    )


@pytest.fixture
def second_name_server(db):
    """A second nameserver of example.com, resolvable to 192.0.2.54."""
    from netbox_dns.choices import RecordTypeChoices
    from netbox_dns.models import NameServer, Record

    ns = NameServer.objects.get_or_create(name="ns2.example.com")[0]
    Record.objects.get_or_create(
        zone=_make_zone("example.com"),
        name="ns2",
        type=RecordTypeChoices.A,
        value="192.0.2.54",
    )
    return ns


@pytest.fixture
def domain(d2_daemon, forward_zone, name_server, tsig_key):
    from netbox_dhcp_kea_plugin.models import DDNSDomain

    forward_zone.nameservers.add(name_server)
    return DDNSDomain.objects.create(zone=forward_zone, tsig_key=tsig_key)


# ---------------------------------------------------------------------------
# TSIG secrets
# ---------------------------------------------------------------------------


class TestSecretRedaction:
    def test_a_plaintext_secret_is_redacted_on_request(self, tsig_key):
        from netbox_dhcp_kea_plugin.models import TSIGKey

        entry = tsig_key.to_kea_dict(redact_secret=True)

        assert entry["secret"] == TSIGKey.REDACTED_SECRET
        assert tsig_key.secret_plaintext not in str(entry)

    def test_a_reference_is_never_redacted(self):
        entry = _vault_key().to_kea_dict(redact_secret=True)

        assert entry["secret"] == "${BAO:kea/tsig/vault-key#secret}"

    def test_the_daemon_redacts_every_held_secret(self, d2_daemon, domain, tsig_key):
        config = d2_daemon.render([domain], redact_secrets=True)

        assert tsig_key.secret_plaintext not in str(config)
        assert d2_daemon.contains_secrets([domain]) is True

    def test_a_vault_only_daemon_holds_no_secrets(self, d2_daemon, forward_zone, name_server):
        from netbox_dhcp_kea_plugin.models import DDNSDomain

        forward_zone.nameservers.add(name_server)
        vault_domain = DDNSDomain.objects.create(zone=forward_zone, tsig_key=_vault_key())

        assert d2_daemon.contains_secrets([vault_domain]) is False
        assert d2_daemon.requires_secret_substitution([vault_domain]) is True


@pytest.fixture
def ddns_server(dhcp_server, d2_daemon, subnet_factory):
    """A server on the local D2 daemon whose subnet's names fall in example.com."""
    from netbox_dhcp_kea_plugin.models import DDNSPolicy

    policy = DDNSPolicy.objects.create(name="lab-names", ddns_qualifying_suffix="host.example.com")
    subnet = subnet_factory(server=dhcp_server)
    subnet.ddns_policy = policy
    subnet.save()
    dhcp_server.d2_daemon = d2_daemon
    dhcp_server.save()
    return dhcp_server


@ddns_routes
class TestSecretPermission:
    """Viewing a D2 configuration must not reveal what the TSIG key page withholds."""

    @pytest.fixture
    def viewer(self, db):
        from netbox_dhcp_kea_plugin.models import D2Daemon, DHCPServer

        user = get_user_model().objects.create_user(username="d2viewer", password="x")
        _grant(user, D2Daemon, "view")
        _grant(user, DHCPServer, "view")
        return user

    @pytest.fixture
    def secret_viewer(self, viewer):
        from netbox_dhcp_kea_plugin.models import TSIGKey

        _grant(viewer, TSIGKey, "view", "view_secret")
        return viewer

    @staticmethod
    def _get(user, viewname, pk):
        client = APIClient()
        client.force_authenticate(user=user)
        return client.get(reverse(f"plugins-api:netbox_dhcp_kea_plugin-api:{viewname}", args=[pk]))

    def test_the_server_config_refuses_secrets_without_the_permission(self, viewer, ddns_server, domain):
        resp = self._get(viewer, "dhcpserver-kea-config", ddns_server.pk)

        assert resp.status_code == 403
        assert "view_secret_tsigkey" in str(resp.data)

    def test_the_server_config_carries_its_d2_with_the_permission(self, secret_viewer, ddns_server, domain, tsig_key):
        resp = self._get(secret_viewer, "dhcpserver-kea-config", ddns_server.pk)

        assert resp.status_code == 200
        assert "Dhcp4" in resp.data
        assert resp.data["DhcpDdns"]["tsig-keys"][0]["secret"] == tsig_key.secret_plaintext

    def test_a_server_without_d2_gets_only_dhcp4(self, viewer, dhcp_server):
        resp = self._get(viewer, "dhcpserver-kea-config", dhcp_server.pk)

        assert resp.status_code == 200
        assert "DhcpDdns" not in resp.data

    def test_a_local_daemon_has_no_config_of_its_own(self, secret_viewer, d2_daemon):
        resp = self._get(secret_viewer, "d2daemon-kea-config", d2_daemon.pk)

        assert resp.status_code == 409
        assert "dhcp-servers/<id>/kea-config/" in str(resp.data)

    def test_a_remote_daemon_refuses_secrets_without_the_permission(self, viewer, ddns_server, d2_daemon, domain):
        d2_daemon.listener_mode = "remote"
        d2_daemon.save()

        assert self._get(viewer, "d2daemon-kea-config", d2_daemon.pk).status_code == 403

    def test_a_remote_daemon_renders_its_servers_domains(self, secret_viewer, ddns_server, d2_daemon, domain):
        d2_daemon.listener_mode = "remote"
        d2_daemon.save()

        resp = self._get(secret_viewer, "d2daemon-kea-config", d2_daemon.pk)

        assert resp.status_code == 200
        names = [d["name"] for d in resp.data["DhcpDdns"]["forward-ddns"]["ddns-domains"]]
        assert names == ["example.com."]

    def test_the_server_tab_redacts_without_the_permission(self, client, viewer, ddns_server, domain, tsig_key):
        client.force_login(viewer)
        url = reverse("plugins:netbox_dhcp_kea_plugin:dhcpserver_d2config", args=[ddns_server.pk])

        resp = client.get(url)

        assert resp.status_code == 200
        assert tsig_key.secret_plaintext not in resp.content.decode()
        assert resp.context["secrets_redacted"] is True

    def test_the_server_tab_shows_secrets_with_the_permission(self, client, secret_viewer, ddns_server, domain, tsig_key):
        client.force_login(secret_viewer)
        url = reverse("plugins:netbox_dhcp_kea_plugin:dhcpserver_d2config", args=[ddns_server.pk])

        resp = client.get(url)

        assert tsig_key.secret_plaintext in resp.content.decode()
        assert resp.context["secrets_redacted"] is False


# ---------------------------------------------------------------------------
# D2 daemon values KEA refuses
# ---------------------------------------------------------------------------


class TestD2DaemonValidation:
    def _daemon(self, **kwargs):
        from netbox_dhcp_kea_plugin.models import D2Daemon

        return D2Daemon(name="d2-check", **kwargs)

    def test_tcp_is_not_offered(self):
        from netbox_dhcp_kea_plugin.models import D2Daemon

        assert [value for value, _ in D2Daemon._meta.get_field("ncr_protocol").choices] == ["UDP"]

    def test_tcp_is_rejected(self):
        with pytest.raises(ValidationError) as exc:
            self._daemon(ncr_protocol="TCP").full_clean()

        assert "ncr_protocol" in exc.value.message_dict

    def test_port_zero_is_rejected(self):
        with pytest.raises(ValidationError) as exc:
            self._daemon(port=0).full_clean()

        assert "port" in exc.value.message_dict

    def test_a_zero_dns_server_timeout_is_rejected(self):
        with pytest.raises(ValidationError) as exc:
            self._daemon(dns_server_timeout=0).full_clean()

        assert "dns_server_timeout" in exc.value.message_dict

    @pytest.mark.parametrize("path", ["/tmp/kea-dhcp-ddns-ctrl.sock", "/var/tmp/d2.sock", "/tmp/./d2.sock", "/tmp/kea/d2.sock"])
    def test_a_socket_in_a_world_writable_directory_is_rejected(self, path):
        with pytest.raises(ValidationError) as exc:
            self._daemon(control_socket_path=path).full_clean()

        assert "control_socket_path" in exc.value.message_dict

    def test_a_socket_in_the_run_directory_is_accepted(self):
        self._daemon(control_socket_path="/var/run/kea/kea-ddns-ctrl-socket").full_clean()

    def test_the_default_socket_path_is_accepted(self):
        path = get_plugin_config("netbox_dhcp_kea_plugin", "d2_default_control_socket_path")

        self._daemon(control_socket_path=path).full_clean()

    def test_a_row_saved_before_the_checks_is_reported(self, d2_daemon):
        d2_daemon.ncr_protocol = "TCP"
        d2_daemon.control_socket_path = "/tmp/kea-dhcp-ddns-ctrl.sock"
        d2_daemon.save()

        errors = d2_daemon.configuration_errors()

        assert len(errors) == 2
        assert any("TCP" in e for e in errors)
        assert any("/tmp" in e for e in errors)

    def test_a_valid_daemon_reports_nothing(self, d2_daemon):
        assert d2_daemon.configuration_errors() == []


# ---------------------------------------------------------------------------
# The DHCP server's sender endpoint
# ---------------------------------------------------------------------------


class TestDDNSSender:
    @pytest.fixture
    def local_d2(self, db):
        from netbox_dhcp_kea_plugin.models import D2Daemon

        return D2Daemon.objects.create(name="d2-local", listener_mode="local", port=53001)

    def test_a_non_address_is_rejected(self, dhcp_server):
        dhcp_server.ddns_sender_ip = "not-an-ip"

        with pytest.raises(ValidationError) as exc:
            dhcp_server.full_clean()

        assert "ddns_sender_ip" in exc.value.message_dict

    def test_a_family_mismatch_is_rejected(self, dhcp_server, local_d2):
        dhcp_server.d2_daemon = local_d2
        dhcp_server.ddns_sender_ip = "2001:db8::10"

        with pytest.raises(ValidationError) as exc:
            dhcp_server.full_clean()

        assert "address family" in str(exc.value.message_dict["ddns_sender_ip"])

    def test_the_servers_own_endpoint_is_rejected(self, dhcp_server, local_d2):
        dhcp_server.d2_daemon = local_d2
        dhcp_server.ddns_sender_ip = "127.0.0.1"
        dhcp_server.ddns_sender_port = local_d2.port

        with pytest.raises(ValidationError) as exc:
            dhcp_server.full_clean()

        assert "ddns_sender_port" in exc.value.message_dict

    def test_a_matching_family_on_another_port_is_accepted(self, dhcp_server, local_d2):
        dhcp_server.d2_daemon = local_d2
        dhcp_server.ddns_sender_ip = "127.0.0.1"
        dhcp_server.ddns_sender_port = 53002

        dhcp_server.full_clean()

    def test_a_blank_sender_is_accepted(self, dhcp_server, local_d2):
        dhcp_server.d2_daemon = local_d2

        dhcp_server.full_clean()


# ---------------------------------------------------------------------------
# Per-nameserver port and key
# ---------------------------------------------------------------------------


class TestServerOverride:
    def _override(self, domain, nameserver, **kwargs):
        from netbox_dhcp_kea_plugin.models import DDNSServerOverride

        return DDNSServerOverride.objects.create(ddns_domain=domain, nameserver=nameserver, **kwargs)

    def test_it_sets_port_and_key_on_its_nameserver_only(self, domain, forward_zone, name_server, second_name_server):
        forward_zone.nameservers.add(second_name_server)
        other_key = _vault_key("ns2-key")
        self._override(domain, second_name_server, port=5353, tsig_key=other_key)

        servers = {s["ip-address"]: s for s in domain.to_kea_dict()["dns-servers"]}

        assert servers["192.0.2.53"] == {"ip-address": "192.0.2.53", "port": 53}
        assert servers["192.0.2.54"] == {"ip-address": "192.0.2.54", "port": 5353, "key-name": "ns2-key"}

    def test_its_key_is_defined_in_tsig_keys(self, d2_daemon, domain, forward_zone, second_name_server, tsig_key):
        forward_zone.nameservers.add(second_name_server)
        self._override(domain, second_name_server, tsig_key=_vault_key("ns2-key"))

        names = [key["name"] for key in d2_daemon.render([domain])["DhcpDdns"]["tsig-keys"]]

        assert names == [tsig_key.name, "ns2-key"]
        assert d2_daemon.requires_secret_substitution([domain]) is True

    def test_a_nameserver_outside_the_zone_is_rejected(self, domain, second_name_server):
        from netbox_dhcp_kea_plugin.models import DDNSServerOverride

        override = DDNSServerOverride(ddns_domain=domain, nameserver=second_name_server, port=5353)

        with pytest.raises(ValidationError) as exc:
            override.full_clean()

        assert "nameserver" in exc.value.message_dict

    def test_an_override_with_nothing_set_is_rejected(self, domain, name_server):
        from netbox_dhcp_kea_plugin.models import DDNSServerOverride

        with pytest.raises(ValidationError):
            DDNSServerOverride(ddns_domain=domain, nameserver=name_server).full_clean()

    def test_an_out_of_range_port_is_rejected(self, domain, name_server):
        from netbox_dhcp_kea_plugin.models import DDNSServerOverride

        with pytest.raises(ValidationError) as exc:
            DDNSServerOverride(ddns_domain=domain, nameserver=name_server, port=70000).full_clean()

        assert "port" in exc.value.message_dict


# ---------------------------------------------------------------------------
# kea-dhcp-ddns hooks
# ---------------------------------------------------------------------------


class TestD2Hooks:
    def test_a_hook_group_loads_its_d2_hooks(self, d2_daemon):
        from netbox_dhcp_kea_plugin.models import Hook, HookGroup

        gss = Hook.objects.create(
            name="Test GSS-TSIG",
            library_name="libddns_gss_tsig.so",
            allowed_processes=["kea-dhcp-ddns"],
            parameters={"server-principal": "DNS/ns1.example.com@EXAMPLE.COM"},
        )
        dhcp_only = Hook.objects.create(
            name="Test lease commands",
            library_name="libdhcp_lease_cmds.so",
            allowed_processes=["kea-dhcp4"],
        )
        group = HookGroup.objects.create(name="d2-hooks", library_path="/usr/lib/kea/hooks")
        group.hooks.add(gss, dhcp_only)
        group.d2_daemons.add(d2_daemon)

        libraries = d2_daemon.render([])["DhcpDdns"]["hooks-libraries"]

        assert libraries == [
            {
                "library": "/usr/lib/kea/hooks/libddns_gss_tsig.so",
                "parameters": {"server-principal": "DNS/ns1.example.com@EXAMPLE.COM"},
            }
        ]

    def test_no_hooks_key_without_a_group(self, d2_daemon):
        assert "hooks-libraries" not in d2_daemon.render([])["DhcpDdns"]


# ---------------------------------------------------------------------------
# Creating several domains at once
# ---------------------------------------------------------------------------


@ddns_routes
class TestMultiZoneCreate:
    def _form(self, zones, **data):
        from netbox_dhcp_kea_plugin.forms import DDNSDomainForm

        return DDNSDomainForm(data={"zone": [z.pk for z in zones], **data})

    def test_every_zone_is_validated(self, forward_zone, name_server):
        forward_zone.nameservers.add(name_server)
        unresolvable = _make_zone("nothing-resolves.example.com")

        form = self._form([forward_zone, unresolvable])

        assert not form.is_valid()
        assert "nothing-resolves.example.com" in str(form.errors["zone"])

    def test_user_context_reaches_every_row(self, forward_zone, name_server):
        from netbox_dhcp_kea_plugin.models import DDNSDomain

        second = _make_zone("second.example.com")
        for zone in (forward_zone, second):
            zone.nameservers.add(name_server)

        form = self._form([forward_zone, second], user_context='{"site": "lab"}')
        assert form.is_valid(), form.errors
        form.save()

        contexts = list(DDNSDomain.objects.values_list("user_context", flat=True))
        assert contexts == [{"site": "lab"}, {"site": "lab"}]

    def test_every_row_gets_the_scope(self, forward_zone, name_server, dhcp_server):
        from netbox_dhcp_kea_plugin.models import DDNSDomain

        second = _make_zone("second.example.com")
        for zone in (forward_zone, second):
            zone.nameservers.add(name_server)

        form = self._form([forward_zone, second], dhcp_server=dhcp_server.pk, always_include=True)
        assert form.is_valid(), form.errors
        form.save()

        assert set(DDNSDomain.objects.values_list("dhcp_server", "always_include")) == {(dhcp_server.pk, True)}

    def test_always_include_needs_a_scope(self, forward_zone, name_server):
        forward_zone.nameservers.add(name_server)

        form = self._form([forward_zone], always_include=True)

        assert not form.is_valid()
        assert "always_include" in form.errors


@ddns_routes
def test_the_d2_api_reports_outstanding_substitution(ddns_server, d2_daemon, forward_zone, name_server):
    from netbox_dhcp_kea_plugin.models import DDNSDomain

    forward_zone.nameservers.add(name_server)
    DDNSDomain.objects.create(zone=forward_zone, tsig_key=_vault_key())
    user = get_user_model().objects.create_superuser(username="d2-admin", password="x")
    client = APIClient()
    client.force_authenticate(user=user)

    url = reverse("plugins-api:netbox_dhcp_kea_plugin-api:d2daemon-detail", args=[d2_daemon.pk])
    resp = client.get(url)

    assert resp.data["requires_secret_substitution"] is True


# ---------------------------------------------------------------------------
# Writing DDNS objects through the REST API
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_api(db):
    user = get_user_model().objects.create_superuser(username="ddns-api-admin", password="x")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@ddns_routes
class TestWritableAPI:
    def test_a_domain_can_be_created(self, admin_api, forward_zone, name_server, tsig_key):
        forward_zone.nameservers.add(name_server)
        url = reverse("plugins-api:netbox_dhcp_kea_plugin-api:ddnsdomain-list")

        resp = admin_api.post(url, {"zone": forward_zone.pk, "tsig_key": tsig_key.pk}, format="json")

        assert resp.status_code == 201, resp.data
        assert resp.data["zone"] == {"id": forward_zone.pk, "name": forward_zone.name}
        assert resp.data["scope"] == "global"
        assert resp.data["tsig_key"]["id"] == tsig_key.pk

    def test_a_domain_can_be_limited_to_a_server(self, admin_api, forward_zone, name_server, dhcp_server):
        forward_zone.nameservers.add(name_server)
        url = reverse("plugins-api:netbox_dhcp_kea_plugin-api:ddnsdomain-list")

        resp = admin_api.post(url, {"zone": forward_zone.pk, "dhcp_server": dhcp_server.pk}, format="json")

        assert resp.status_code == 201, resp.data
        assert resp.data["scope"] == "server"
        assert resp.data["dhcp_server"]["id"] == dhcp_server.pk

    def test_a_second_global_entry_for_a_zone_is_refused(self, admin_api, domain, forward_zone):
        url = reverse("plugins-api:netbox_dhcp_kea_plugin-api:ddnsdomain-list")

        resp = admin_api.post(url, {"zone": forward_zone.pk}, format="json")

        assert resp.status_code == 400

    def test_a_domain_without_a_resolvable_nameserver_is_refused(self, admin_api):
        zone = _make_zone("unresolvable.example.com")
        url = reverse("plugins-api:netbox_dhcp_kea_plugin-api:ddnsdomain-list")

        resp = admin_api.post(url, {"zone": zone.pk}, format="json")

        assert resp.status_code == 400
        assert "zone" in resp.data

    def test_a_remote_daemon_takes_its_listener_address(self, admin_api, d2_listener_ip):
        url = reverse("plugins-api:netbox_dhcp_kea_plugin-api:d2daemon-list")

        resp = admin_api.post(
            url,
            {"name": "d2-remote", "listener_mode": "remote", "ip_address": d2_listener_ip.pk},
            format="json",
        )

        assert resp.status_code == 201, resp.data
        assert resp.data["ip_address"]["id"] == d2_listener_ip.pk


# ---------------------------------------------------------------------------
# GraphQL
# ---------------------------------------------------------------------------


def _gql(user, query):
    import json

    from django.test import Client

    client = Client()
    client.force_login(user)
    resp = client.post("/graphql/", data=json.dumps({"query": query}), content_type="application/json")
    assert resp.status_code == 200, resp.content
    return resp.json()


@ddns_routes
class TestGraphQL:
    @pytest.fixture
    def admin(self, db):
        return get_user_model().objects.create_superuser(username="ddns-gql-admin", password="x")

    def test_a_domain_traverses_to_its_zone_key_and_scope(self, admin, domain, tsig_key):
        payload = _gql(
            admin,
            """
            {
              netbox_dhcp_kea_ddns_domain_list {
                is_reverse
                scope
                always_include
                dhcp_server { name }
                zone { name }
                tsig_key { name algorithm secret_backend }
              }
            }
            """,
        )

        assert "errors" not in payload, payload.get("errors")
        (row,) = payload["data"]["netbox_dhcp_kea_ddns_domain_list"]
        assert row["zone"]["name"] == domain.zone.name
        assert row["tsig_key"]["name"] == tsig_key.name
        assert row["scope"] == "global"
        assert row["dhcp_server"] is None
        assert row["is_reverse"] is False

    def test_a_daemon_lists_its_servers(self, admin, ddns_server, d2_daemon, domain):
        payload = _gql(
            admin,
            "{ netbox_dhcp_kea_d2_daemon_list { name servers { name } requires_secret_substitution } }",
        )

        assert "errors" not in payload, payload.get("errors")
        (row,) = payload["data"]["netbox_dhcp_kea_d2_daemon_list"]
        assert row == {
            "name": d2_daemon.name,
            "servers": [{"name": ddns_server.name}],
            "requires_secret_substitution": False,
        }

    def test_the_tsig_key_type_has_no_secret(self, admin, tsig_key):
        payload = _gql(admin, "{ netbox_dhcp_kea_tsig_key_list { name secret_plaintext } }")

        assert "errors" in payload
        assert "secret_plaintext" in str(payload["errors"])
