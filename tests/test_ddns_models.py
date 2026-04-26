"""Tests for the DDNS model layer.

Covers TSIGKey validation, secret backend resolution, DDNSDomain direction
derivation and clean(), and DDNSPolicy.to_kea_overrides() emission rules.
"""

import base64
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def d2_listener_ip(db):
    from ipam.models import IPAddress

    return IPAddress.objects.create(address="10.0.0.50/24")


@pytest.fixture
def d2_daemon(db, d2_listener_ip):
    from netbox_dhcp_kea_plugin.models import D2Daemon

    return D2Daemon.objects.create(
        name="d2-primary",
        ip_address=d2_listener_ip,
        port=53001,
    )


@pytest.fixture
def tsig_key(db):
    from netbox_dhcp_kea_plugin.models import TSIGKey

    return TSIGKey.objects.create(
        name="d2.example.com.",
        algorithm="HMAC-SHA256",
        secret_backend="plaintext",
        secret_plaintext=base64.b64encode(b"super-secret-bytes").decode(),
    )


@pytest.fixture
def forward_zone(db):
    from netbox_dns.models import View, Zone

    view, _ = View.objects.get_or_create(name="default")
    return Zone.objects.create(name="example.com", view=view, soa_mname_id=None) if False else _make_zone("example.com")


@pytest.fixture
def reverse_zone(db):
    return _make_zone("1.168.192.in-addr.arpa")


@pytest.fixture
def name_server(db):
    """A NameServer plus an A record so _resolve_nameserver_ips returns an IP."""
    from netbox_dns.choices import RecordTypeChoices
    from netbox_dns.models import NameServer, Record

    ns = NameServer.objects.get_or_create(name="ns1.example.com")[0]
    # Record needs a zone; reuse a dedicated zone for the NS A record.
    ns_zone = _make_zone("example.com")
    Record.objects.get_or_create(
        zone=ns_zone,
        name="ns1",
        type=RecordTypeChoices.A,
        value="192.0.2.53",
    )
    return ns


def _make_zone(name):
    """Create a netbox-dns Zone with whatever defaults the local install requires."""
    from netbox_dns.models import NameServer, View, Zone

    view, _ = View.objects.get_or_create(name="default")
    soa = NameServer.objects.get_or_create(name="ns-soa.example.com")[0]
    zone, _ = Zone.objects.get_or_create(
        name=name,
        view=view,
        defaults={
            "soa_mname": soa,
            "soa_rname": "hostmaster.example.com",
        },
    )
    return zone


def _attach_ns_to_zone(zone, ns):
    zone.nameservers.add(ns)


# ---------------------------------------------------------------------------
# TSIGKey
# ---------------------------------------------------------------------------


def test_tsig_key_clean_accepts_valid_base64():
    from netbox_dhcp_kea_plugin.models import TSIGKey

    key = TSIGKey(
        name="ok.",
        algorithm="HMAC-SHA256",
        secret_backend="plaintext",
        secret_plaintext=base64.b64encode(b"1234567890").decode(),
    )
    key.full_clean()


def test_tsig_key_clean_regenerates_for_non_base64():
    from netbox_dhcp_kea_plugin.models import TSIGKey

    key = TSIGKey(
        name="bad.",
        algorithm="HMAC-SHA256",
        secret_backend="plaintext",
        secret_plaintext="not!base64!!",
    )
    key.full_clean()
    assert key.secret_plaintext != "not!base64!!"
    decoded = base64.b64decode(key.secret_plaintext, validate=True)
    assert len(decoded) == 32  # HMAC-SHA256 natural length


def test_tsig_key_clean_rejects_oversize_digest_bits():
    from netbox_dhcp_kea_plugin.models import TSIGKey

    key = TSIGKey(
        name="oversize.",
        algorithm="HMAC-SHA1",  # 160 bits max
        secret_backend="plaintext",
        secret_plaintext=base64.b64encode(b"x").decode(),
        digest_bits=512,
    )
    with pytest.raises(ValidationError) as exc:
        key.full_clean()
    assert "digest_bits" in exc.value.message_dict


def test_tsig_key_clean_generates_when_empty_plaintext():
    from netbox_dhcp_kea_plugin.models import TSIGKey

    key = TSIGKey(
        name="empty.",
        algorithm="HMAC-SHA1",
        secret_backend="plaintext",
        secret_plaintext="",
    )
    key.full_clean()
    decoded = base64.b64decode(key.secret_plaintext, validate=True)
    assert len(decoded) == 20  # HMAC-SHA1 natural length


def test_tsig_key_get_secret_plaintext(tsig_key):
    assert tsig_key.get_secret() == tsig_key.secret_plaintext


def test_tsig_key_to_kea_dict_includes_lower_algorithm(tsig_key):
    d = tsig_key.to_kea_dict()
    assert d["name"] == tsig_key.name
    assert d["algorithm"] == "hmac-sha256"
    assert d["secret"] == tsig_key.secret_plaintext


def test_tsig_key_to_kea_dict_includes_digest_bits_when_set(db):
    from netbox_dhcp_kea_plugin.models import TSIGKey

    key = TSIGKey.objects.create(
        name="trunc.",
        algorithm="HMAC-SHA256",
        digest_bits=128,
        secret_backend="plaintext",
        secret_plaintext=base64.b64encode(b"y").decode(),
    )
    assert key.to_kea_dict()["digest-bits"] == 128


# ---------------------------------------------------------------------------
# DDNSDomain
# ---------------------------------------------------------------------------


def test_ddnsdomain_is_reverse_for_in_addr_arpa(db, d2_daemon):
    from netbox_dhcp_kea_plugin.models import DDNSDomain

    zone = _make_zone("0.10.in-addr.arpa")
    domain = DDNSDomain.objects.create(d2_daemon=d2_daemon, zone=zone)
    assert domain.is_reverse is True


def test_ddnsdomain_is_reverse_for_ip6_arpa(db, d2_daemon):
    from netbox_dhcp_kea_plugin.models import DDNSDomain

    zone = _make_zone("0.0.0.0.ip6.arpa")
    domain = DDNSDomain.objects.create(d2_daemon=d2_daemon, zone=zone)
    assert domain.is_reverse is True


def test_ddnsdomain_is_forward_for_regular_zone(db, d2_daemon):
    from netbox_dhcp_kea_plugin.models import DDNSDomain

    zone = _make_zone("example.com")
    domain = DDNSDomain.objects.create(d2_daemon=d2_daemon, zone=zone)
    assert domain.is_reverse is False


def test_ddnsdomain_to_kea_dict_omits_key_name_when_no_tsig(db, d2_daemon, name_server):
    from netbox_dhcp_kea_plugin.models import DDNSDomain

    zone = _make_zone("nokey.example.com")
    _attach_ns_to_zone(zone, name_server)
    domain = DDNSDomain.objects.create(d2_daemon=d2_daemon, zone=zone)
    d = domain.to_kea_dict()
    assert "key-name" not in d
    assert d["name"].endswith(".")


def test_ddnsdomain_to_kea_dict_includes_key_name_when_tsig_set(
    db, d2_daemon, tsig_key, name_server
):
    from netbox_dhcp_kea_plugin.models import DDNSDomain

    zone = _make_zone("withkey.example.com")
    _attach_ns_to_zone(zone, name_server)
    domain = DDNSDomain.objects.create(d2_daemon=d2_daemon, zone=zone, tsig_key=tsig_key)
    assert domain.to_kea_dict()["key-name"] == tsig_key.name


def test_ddnsdomain_to_kea_dict_resolves_nameserver_ips(db, d2_daemon, name_server):
    from netbox_dhcp_kea_plugin.models import DDNSDomain

    zone = _make_zone("ips.example.com")
    _attach_ns_to_zone(zone, name_server)
    domain = DDNSDomain.objects.create(d2_daemon=d2_daemon, zone=zone)
    out = domain.to_kea_dict()
    assert out["dns-servers"] == [{"ip-address": "192.0.2.53", "port": 53}]


# ---------------------------------------------------------------------------
# DDNSPolicy
# ---------------------------------------------------------------------------


def test_ddnspolicy_to_kea_overrides_returns_only_set_keys(db):
    from netbox_dhcp_kea_plugin.models import DDNSPolicy

    policy = DDNSPolicy.objects.create(
        name="partial",
        ddns_send_updates=True,
        ddns_qualifying_suffix="lab.example.com",
    )
    overrides = policy.to_kea_overrides()
    assert overrides == {
        "ddns-send-updates": True,
        "ddns-qualifying-suffix": "lab.example.com",
    }


def test_ddnspolicy_to_kea_overrides_kebab_cases_field_names(db):
    from netbox_dhcp_kea_plugin.models import DDNSPolicy

    policy = DDNSPolicy.objects.create(
        name="kebab",
        ddns_override_no_update=False,
        ddns_override_client_update=True,
        hostname_char_set="[^a-zA-Z0-9]",
        hostname_char_replacement="-",
    )
    overrides = policy.to_kea_overrides()
    assert "ddns-override-no-update" in overrides
    assert "ddns-override-client-update" in overrides
    assert "hostname-char-set" in overrides
    assert "hostname-char-replacement" in overrides
    assert all("_" not in k for k in overrides)


def test_ddnspolicy_to_kea_overrides_decimal_emitted_as_float(db):
    from netbox_dhcp_kea_plugin.models import DDNSPolicy

    policy = DDNSPolicy.objects.create(name="ttl", ddns_ttl_percent=Decimal("0.3333"))
    out = policy.to_kea_overrides()["ddns-ttl-percent"]
    assert isinstance(out, float)
    assert abs(out - 0.3333) < 1e-9


def test_ddnspolicy_to_kea_overrides_drops_empty_strings(db):
    from netbox_dhcp_kea_plugin.models import DDNSPolicy

    policy = DDNSPolicy.objects.create(
        name="emptystrs",
        ddns_qualifying_suffix="",
        ddns_generated_prefix="",
    )
    assert policy.to_kea_overrides() == {}


# ---------------------------------------------------------------------------
# D2Daemon
# ---------------------------------------------------------------------------


def test_d2daemon_to_kea_dict_partitions_forward_and_reverse(
    db, d2_daemon, name_server
):
    from netbox_dhcp_kea_plugin.models import DDNSDomain

    fwd_zone = _make_zone("fwd.example.com")
    rev_zone = _make_zone("0.10.in-addr.arpa")
    _attach_ns_to_zone(fwd_zone, name_server)
    _attach_ns_to_zone(rev_zone, name_server)
    DDNSDomain.objects.create(d2_daemon=d2_daemon, zone=fwd_zone)
    DDNSDomain.objects.create(d2_daemon=d2_daemon, zone=rev_zone)

    config = d2_daemon.to_kea_dict()["DhcpDdns"]
    fwd_names = [d["name"] for d in config["forward-ddns"]["ddns-domains"]]
    rev_names = [d["name"] for d in config["reverse-ddns"]["ddns-domains"]]
    assert any(n.startswith("fwd.") for n in fwd_names)
    assert any("in-addr.arpa" in n for n in rev_names)


def test_d2daemon_to_kea_dict_emits_unique_tsig_keys(
    db, d2_daemon, tsig_key, name_server
):
    from netbox_dhcp_kea_plugin.models import DDNSDomain

    z1 = _make_zone("a.example.com")
    z2 = _make_zone("b.example.com")
    for z in (z1, z2):
        _attach_ns_to_zone(z, name_server)
        DDNSDomain.objects.create(d2_daemon=d2_daemon, zone=z, tsig_key=tsig_key)

    config = d2_daemon.to_kea_dict()["DhcpDdns"]
    assert "tsig-keys" in config
    assert len(config["tsig-keys"]) == 1
    assert config["tsig-keys"][0]["name"] == tsig_key.name
