"""Tests for the squashed migration's DNS-linking data step.

Driven against the real models through django's app registry, which is shape-
compatible with the historical models here — the migration only touches fields
that still exist. What matters is the *selection* logic: which record it is
willing to take a certificate name from, and which it refuses.
"""

import importlib

import pytest


def _migration():
    return importlib.import_module("netbox_dhcp_kea_plugin.migrations.0009_ha_relationship_settings_and_pki")


def _apps():
    from django.apps import apps

    return apps


class _AppsWithoutDNS:
    """Stands in for an install where netbox_dns is not present."""

    @staticmethod
    def get_model(app_label, model_name):
        from django.apps import apps

        if app_label == "netbox_dns":
            raise LookupError("No installed app with label 'netbox_dns'.")
        return apps.get_model(app_label, model_name)


def _make_zone(name):
    from netbox_dns.models import NameServer, View, Zone

    view, _ = View.objects.get_or_create(name="default")
    soa = NameServer.objects.get_or_create(name="ns-soa.example.net")[0]
    zone, _ = Zone.objects.get_or_create(
        name=name,
        view=view,
        defaults={"soa_mname": soa, "soa_rname": "hostmaster.example.net"},
    )
    return zone


@pytest.fixture
def pki_zone(db):
    return _make_zone("pki.example.net")


@pytest.mark.django_db
class TestLinkExistingDNSRecords:
    def test_an_unmanaged_address_record_is_adopted(self, dhcp_server_factory, pki_zone):
        from netbox_dns.models import Record

        server = dhcp_server_factory(name="kea-seed", ip_suffix=41)
        Record.objects.create(zone=pki_zone, name="kea-seed", type="A", value=str(server.ip_address.address.ip))

        _migration().link_existing_dns_records(_apps(), None)

        server.refresh_from_db()
        assert server.pki_fqdn == "kea-seed.pki.example.net"

    def test_a_managed_record_is_refused(self, dhcp_server_factory, pki_zone):
        """A wrong pin is worse than a blank one — it fails at the handshake."""
        from netbox_dns.models import Record

        server = dhcp_server_factory(name="kea-managed", ip_suffix=42)
        Record.objects.create(
            zone=pki_zone,
            name="kea-managed",
            type="A",
            value=str(server.ip_address.address.ip),
            managed=True,
        )

        _migration().link_existing_dns_records(_apps(), None)

        server.refresh_from_db()
        assert server.pki_fqdn == ""

    def test_an_inactive_record_is_refused(self, dhcp_server_factory, pki_zone):
        from netbox_dns.models import Record

        server = dhcp_server_factory(name="kea-inactive", ip_suffix=43)
        Record.objects.create(
            zone=pki_zone,
            name="kea-inactive",
            type="A",
            value=str(server.ip_address.address.ip),
            status="inactive",
        )

        _migration().link_existing_dns_records(_apps(), None)

        server.refresh_from_db()
        assert server.pki_fqdn == ""

    def test_a_record_for_another_ip_is_not_adopted(self, dhcp_server_factory, pki_zone):
        from netbox_dns.models import Record

        server = dhcp_server_factory(name="kea-elsewhere", ip_suffix=44)
        Record.objects.create(zone=pki_zone, name="somebody-else", type="A", value="192.0.2.200")

        _migration().link_existing_dns_records(_apps(), None)

        server.refresh_from_db()
        assert server.pki_fqdn == ""

    def test_a_server_with_no_record_stays_blank(self, dhcp_server_factory, pki_zone):
        server = dhcp_server_factory(name="kea-norecord", ip_suffix=45)

        _migration().link_existing_dns_records(_apps(), None)

        server.refresh_from_db()
        assert server.pki_fqdn == ""

    def test_a_zone_outside_the_issuable_list_is_skipped(self, dhcp_server_factory, settings, monkeypatch):
        from netbox_dns.models import Record

        monkeypatch.setitem(
            settings.PLUGINS_CONFIG["netbox_dhcp_kea_plugin"], "pki_allowed_zone_suffixes", [".pki.example.net"]
        )
        other_zone = _make_zone("not-issuable.example.net")
        server = dhcp_server_factory(name="kea-wrongzone", ip_suffix=46)
        Record.objects.create(zone=other_zone, name="kea-wrongzone", type="A", value=str(server.ip_address.address.ip))

        _migration().link_existing_dns_records(_apps(), None)

        server.refresh_from_db()
        assert server.pki_fqdn == ""

    def test_it_no_ops_without_the_dns_plugin(self, dhcp_server_factory):
        """netbox_dns is optional, so an absent app must not break the migration."""
        server = dhcp_server_factory(name="kea-nodns", ip_suffix=47)

        _migration().link_existing_dns_records(_AppsWithoutDNS, None)

        server.refresh_from_db()
        assert server.pki_fqdn == ""

    def test_reverse_blanks_the_field(self, dhcp_server_factory):
        from netbox_dhcp_kea_plugin.models import DHCPServer

        dhcp_server_factory(name="kea-reverse", ip_suffix=48, pki_fqdn="kea-reverse.pki.example.net")

        _migration().clear_pki_fqdn(_apps(), None)

        assert set(DHCPServer.objects.values_list("pki_fqdn", flat=True)) == {""}
