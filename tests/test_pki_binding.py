"""The binding between a DHCPServer's PKI identity and its netbox_dns record.

pki_record_id is a soft reference, not a ForeignKey — a real FK would make
netbox-plugin-dns mandatory. These assert that the signals in signals.py supply
what the FK would have: the record is protected while bound, deleting the server
deletes it, and renaming it re-derives the published name.
"""

import pytest
from django.db.models import ProtectedError


def _make_zone(name="pki.example.net"):
    from netbox_dns.models import NameServer, View, Zone

    view, _ = View.objects.get_or_create(name="default")
    soa = NameServer.objects.get_or_create(name="ns-soa.example.net")[0]
    zone, _ = Zone.objects.get_or_create(
        name=name, view=view, defaults={"soa_mname": soa, "soa_rname": "hostmaster.example.net"}
    )
    return zone


@pytest.fixture
def dns_record(db):
    from netbox_dns.models import Record

    return Record.objects.create(zone=_make_zone(), name="kea-bound", type="A", value="192.0.2.71")


@pytest.mark.django_db
class TestPKIRecordBinding:
    def test_binding_derives_the_published_name(self, dhcp_server_factory, dns_record):
        server = dhcp_server_factory(name="kea-bind", ip_suffix=71)
        server.pki_record_id = dns_record.pk
        server.save()

        server.refresh_from_db()
        assert server.pki_fqdn == "kea-bound.pki.example.net"

    def test_a_bound_record_cannot_be_deleted(self, dhcp_server_factory, dns_record):
        """What on_delete=PROTECT would do for a real FK."""
        server = dhcp_server_factory(name="kea-protect", ip_suffix=72)
        server.pki_record_id = dns_record.pk
        server.save()

        with pytest.raises(ProtectedError) as exc:
            dns_record.delete()

        assert "kea-protect" in str(exc.value)

    def test_an_unbound_record_deletes_freely(self, dns_record):
        from netbox_dns.models import Record

        dns_record.delete()

        assert not Record.objects.filter(pk=dns_record.pk).exists()

    def test_deleting_the_server_deletes_the_record(self, dhcp_server_factory, dns_record):
        from netbox_dns.models import Record

        server = dhcp_server_factory(name="kea-cascade", ip_suffix=73)
        server.pki_record_id = dns_record.pk
        server.save()

        server.delete()

        assert not Record.objects.filter(pk=dns_record.pk).exists()

    def test_a_bulk_delete_also_removes_the_record(self, dhcp_server_factory, dns_record):
        """List-view deletes go through queryset.delete(), not Model.delete()."""
        from netbox_dns.models import Record

        from netbox_dhcp_kea_plugin.models import DHCPServer

        server = dhcp_server_factory(name="kea-bulk", ip_suffix=74)
        server.pki_record_id = dns_record.pk
        server.save()

        DHCPServer.objects.filter(pk=server.pk).delete()

        assert not Record.objects.filter(pk=dns_record.pk).exists()

    def test_a_record_shared_by_another_server_survives(self, dhcp_server_factory, dns_record):
        from netbox_dns.models import Record

        first = dhcp_server_factory(name="kea-share-a", ip_suffix=75)
        first.pki_record_id = dns_record.pk
        first.save()
        second = dhcp_server_factory(name="kea-share-b", ip_suffix=76)
        second.pki_record_id = dns_record.pk
        second.save()

        first.delete()

        assert Record.objects.filter(pk=dns_record.pk).exists()

    def test_deleting_an_unbound_server_touches_no_records(self, dhcp_server_factory, dns_record):
        """A typed identity is not a binding — nothing may be deleted for it."""
        from netbox_dns.models import Record

        server = dhcp_server_factory(
            name="kea-typed", ip_suffix=77, pki_fqdn="kea-bound.pki.example.net"
        )

        server.delete()

        assert Record.objects.filter(pk=dns_record.pk).exists()

    def test_renaming_the_record_re_derives_the_name(self, dhcp_server_factory, dns_record):
        """Otherwise the pin silently diverges from the certificate."""
        server = dhcp_server_factory(name="kea-rename", ip_suffix=78)
        server.pki_record_id = dns_record.pk
        server.save()

        dns_record.name = "kea-renamed"
        dns_record.save()

        server.refresh_from_db()
        assert server.pki_fqdn == "kea-renamed.pki.example.net"


@pytest.mark.django_db
class TestPKIFormBinding:
    def test_the_picker_replaces_the_text_field(self, dhcp_server_factory, settings, monkeypatch):
        from netbox_dhcp_kea_plugin.forms import DHCPServerForm

        monkeypatch.setitem(settings.PLUGINS_CONFIG["netbox_dhcp_kea_plugin"], "enable_netbox_dns", True)
        server = dhcp_server_factory(name="kea-formbind", ip_suffix=79)

        form = DHCPServerForm(instance=server)

        assert "pki_record" in form.fields
        assert "pki_fqdn" not in form.fields

    def test_the_text_field_remains_without_the_dns_plugin(
        self, dhcp_server_factory, settings, monkeypatch
    ):
        from netbox_dhcp_kea_plugin.forms import DHCPServerForm

        monkeypatch.setitem(settings.PLUGINS_CONFIG["netbox_dhcp_kea_plugin"], "enable_netbox_dns", False)
        server = dhcp_server_factory(name="kea-formtext", ip_suffix=80)

        form = DHCPServerForm(instance=server)

        assert "pki_fqdn" in form.fields
        assert "pki_record" not in form.fields


@pytest.mark.django_db
class TestPKIRecordPickerFiltering:
    """The picker only offers names the CA will sign.

    clean() rejects a pki_fqdn outside pki_allowed_zone_suffixes, so a picker
    that offered one would hand the user a choice that cannot be saved.
    """

    @pytest.fixture
    def records(self, db):
        from netbox_dns.models import Record

        issuable = Record.objects.create(
            zone=_make_zone("pki.example.net"), name="kea-ok", type="A", value="192.0.2.81"
        )
        elsewhere = Record.objects.create(
            zone=_make_zone("other.example.net"), name="kea-nope", type="A", value="192.0.2.82"
        )
        managed = Record.objects.create(
            zone=_make_zone("pki.example.net"),
            name="kea-managed",
            type="A",
            value="192.0.2.83",
            managed=True,
        )
        return issuable, elsewhere, managed

    def _picker(self, server, settings, monkeypatch, suffixes):
        from netbox_dhcp_kea_plugin.forms import DHCPServerForm

        monkeypatch.setitem(settings.PLUGINS_CONFIG["netbox_dhcp_kea_plugin"], "enable_netbox_dns", True)
        monkeypatch.setitem(
            settings.PLUGINS_CONFIG["netbox_dhcp_kea_plugin"], "pki_allowed_zone_suffixes", suffixes
        )
        return DHCPServerForm(instance=server).fields["pki_record"]

    def test_only_issuable_zones_are_offered(
        self, dhcp_server_factory, records, settings, monkeypatch
    ):
        issuable, elsewhere, _ = records
        server = dhcp_server_factory(name="kea-filter", ip_suffix=81)

        field = self._picker(server, settings, monkeypatch, [".pki.example.net"])

        offered = set(field.queryset.values_list("pk", flat=True))
        assert issuable.pk in offered
        assert elsewhere.pk not in offered

    def test_managed_records_are_never_offered(
        self, dhcp_server_factory, records, settings, monkeypatch
    ):
        _, _, managed = records
        server = dhcp_server_factory(name="kea-filter-managed", ip_suffix=82)

        field = self._picker(server, settings, monkeypatch, [".pki.example.net"])

        assert managed.pk not in set(field.queryset.values_list("pk", flat=True))

    def test_the_dropdown_is_scoped_to_matching_zones(
        self, dhcp_server_factory, records, settings, monkeypatch
    ):
        """The dropdown is served over the REST API, so it filters by zone."""
        from netbox_dns.models import Zone

        issuable, elsewhere, _ = records
        server = dhcp_server_factory(name="kea-filter-zone", ip_suffix=83)

        field = self._picker(server, settings, monkeypatch, [".pki.example.net"])

        zone_ids = field.query_params["zone_id"]
        assert issuable.zone_id in zone_ids
        assert elsewhere.zone_id not in zone_ids
        assert set(zone_ids) <= set(Zone.objects.values_list("pk", flat=True))

    def test_no_configured_zones_offers_everything_unmanaged(
        self, dhcp_server_factory, records, settings, monkeypatch
    ):
        issuable, elsewhere, managed = records
        server = dhcp_server_factory(name="kea-filter-off", ip_suffix=84)

        field = self._picker(server, settings, monkeypatch, [])

        offered = set(field.queryset.values_list("pk", flat=True))
        assert {issuable.pk, elsewhere.pk} <= offered
        assert managed.pk not in offered
        assert "zone_id" not in field.query_params

    def test_a_suffix_matching_no_zone_offers_nothing(
        self, dhcp_server_factory, records, settings, monkeypatch
    ):
        """Better an empty picker than one full of unsaveable choices."""
        server = dhcp_server_factory(name="kea-filter-none", ip_suffix=85)

        field = self._picker(server, settings, monkeypatch, [".nothing-here.test"])

        assert not field.queryset.exists()
        assert field.query_params["zone_id"] == [0]

    def test_a_picked_record_still_validates(
        self, dhcp_server_factory, records, settings, monkeypatch
    ):
        """End to end: what the picker offers is what clean() accepts."""
        from netbox_dhcp_kea_plugin.forms import DHCPServerForm
        from tests.test_dhcpserver_form import _form_data

        issuable, _, _ = records
        monkeypatch.setitem(settings.PLUGINS_CONFIG["netbox_dhcp_kea_plugin"], "enable_netbox_dns", True)
        monkeypatch.setitem(
            settings.PLUGINS_CONFIG["netbox_dhcp_kea_plugin"],
            "pki_allowed_zone_suffixes",
            [".pki.example.net"],
        )
        server = dhcp_server_factory(name="kea-filter-e2e", ip_suffix=86)

        form = DHCPServerForm(
            data=_form_data(server, pki_record=issuable.pk), instance=server
        )

        assert form.is_valid(), form.errors
        assert form.cleaned_data["pki_fqdn"] == "kea-ok.pki.example.net"


@pytest.mark.django_db
class TestPKIIdentityOnServerView:
    """The identity has to be visible on the object it belongs to."""

    def _get(self, client, admin_user, server):
        from django.urls import reverse

        client.force_login(admin_user)
        url = reverse("plugins:netbox_dhcp_kea_plugin:dhcpserver", kwargs={"pk": server.pk})
        return client.get(url)

    def test_the_name_is_rendered(self, client, admin_user, dhcp_server_factory):
        server = dhcp_server_factory(
            name="kea-view", ip_suffix=91, pki_fqdn="kea-view.pki.example.net"
        )

        response = self._get(client, admin_user, server)

        assert response.status_code == 200
        assert b"kea-view.pki.example.net" in response.content
        assert b"PKI FQDN" in response.content

    def test_a_bound_name_links_to_its_record(self, client, admin_user, dhcp_server_factory):
        """One row: the name itself is the link when it is bound."""
        from netbox_dns.models import Record

        record = Record.objects.create(
            zone=_make_zone(), name="kea-viewbound", type="A", value="192.0.2.92"
        )
        server = dhcp_server_factory(name="kea-viewbound", ip_suffix=92)
        server.pki_record_id = record.pk
        server.save()

        response = self._get(client, admin_user, server)

        assert response.status_code == 200
        assert response.context["pki_record"].pk == record.pk
        expected = f'<a href="{record.get_absolute_url()}">kea-viewbound.pki.example.net</a>'
        assert expected.encode() in response.content

    def test_an_unbound_name_is_plain_text_and_flagged(
        self, client, admin_user, dhcp_server_factory, settings, monkeypatch
    ):
        """With the DNS integration on, an unbound name is anomalous.

        The form binds every name it sets, so one that is not bound arrived by
        another route — the API, an import, or before the integration was on.
        """
        monkeypatch.setitem(settings.PLUGINS_CONFIG["netbox_dhcp_kea_plugin"], "enable_netbox_dns", True)
        server = dhcp_server_factory(
            name="kea-viewtyped", ip_suffix=93, pki_fqdn="kea-viewtyped.pki.example.net"
        )

        response = self._get(client, admin_user, server)

        assert response.context["pki_record"] is None
        assert b"kea-viewtyped.pki.example.net" in response.content
        assert b">kea-viewtyped.pki.example.net</a>" not in response.content
        assert b"unbound" in response.content

    def test_no_unbound_marker_without_the_dns_integration(
        self, client, admin_user, dhcp_server_factory, settings, monkeypatch
    ):
        """Every name is unbound then, so the marker would be noise everywhere."""
        monkeypatch.setitem(settings.PLUGINS_CONFIG["netbox_dhcp_kea_plugin"], "enable_netbox_dns", False)
        server = dhcp_server_factory(
            name="kea-viewnodns", ip_suffix=95, pki_fqdn="kea-viewnodns.pki.example.net"
        )

        response = self._get(client, admin_user, server)

        assert response.context["pki_dns_integration"] is False
        assert b"kea-viewnodns.pki.example.net" in response.content
        assert b"unbound" not in response.content

    def test_a_server_without_an_identity_renders(self, client, admin_user, dhcp_server_factory):
        server = dhcp_server_factory(name="kea-viewnone", ip_suffix=94)

        response = self._get(client, admin_user, server)

        assert response.status_code == 200
        assert b"PKI FQDN" in response.content



@pytest.mark.django_db
class TestPKIRecordPickerExcludesInactive:
    """A name that does not resolve cannot be certified.

    PKI onboarding resolves every certificate name before minting and refuses
    one that does not, so an inactive record is not a usable identity.
    """

    def test_an_inactive_record_is_not_offered(
        self, dhcp_server_factory, settings, monkeypatch
    ):
        from netbox_dns.models import Record

        from netbox_dhcp_kea_plugin.forms import DHCPServerForm

        monkeypatch.setitem(settings.PLUGINS_CONFIG["netbox_dhcp_kea_plugin"], "enable_netbox_dns", True)
        active = Record.objects.create(
            zone=_make_zone(), name="kea-active", type="A", value="192.0.2.101"
        )
        inactive = Record.objects.create(
            zone=_make_zone(),
            name="kea-inactive-pick",
            type="A",
            value="192.0.2.102",
            status="inactive",
        )
        server = dhcp_server_factory(name="kea-pick-status", ip_suffix=101)

        offered = set(DHCPServerForm(instance=server).fields["pki_record"].queryset.values_list("pk", flat=True))

        assert active.pk in offered
        assert inactive.pk not in offered
