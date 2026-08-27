"""Tests that actually submit DHCPServerForm.

The existing form tests construct the form and inspect ``fields``, which never
runs ``clean()``. A regression that crashed every save through the UI therefore
passed the whole suite — these call ``is_valid()`` so the clean path is covered.
"""

import pytest


def _form_data(server, **overrides):
    """A complete POST payload for editing an existing server."""
    data = {
        "name": server.name,
        "description": server.description,
        "ip_address": server.ip_address_id,
        "status": server.status,
        "service_template": server.service_template_id,
        "ha_port": server.ha_port or 8080,
        "ha_egress_base_port": server.ha_egress_base_port or 18080,
        "ctrl_socket_type": server.ctrl_socket_type or "",
        "pki_fqdn": server.pki_fqdn,
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
class TestDHCPServerFormClean:
    def test_editing_a_server_validates(self, dhcp_server_factory):
        """The regression: super().clean() returns None in this MRO.

        NetBoxModelForm.clean() ends in CheckLastUpdatedMixin.clean(), which
        returns None on every path, so treating its return value as a dict
        raised AttributeError on every save.
        """
        from netbox_dhcp_kea_plugin.forms import DHCPServerForm

        server = dhcp_server_factory(name="kea-form", ip_suffix=61)

        form = DHCPServerForm(data=_form_data(server), instance=server)

        assert form.is_valid(), form.errors
        assert form.cleaned_data["name"] == "kea-form"

    def test_a_typed_identity_is_normalised(self, dhcp_server_factory, settings, monkeypatch):
        """Only reachable without the DNS integration — the picker replaces it."""
        from netbox_dhcp_kea_plugin.forms import DHCPServerForm

        monkeypatch.setitem(settings.PLUGINS_CONFIG["netbox_dhcp_kea_plugin"], "enable_netbox_dns", False)
        server = dhcp_server_factory(name="kea-form-norm", ip_suffix=62)

        form = DHCPServerForm(
            data=_form_data(server, pki_fqdn="Kea-Form.PKI.Example.NET."), instance=server
        )

        assert form.is_valid(), form.errors
        assert form.cleaned_data["pki_fqdn"] == "kea-form.pki.example.net"
        saved = form.save()
        assert saved.pki_fqdn == "kea-form.pki.example.net"

    def test_an_ip_address_identity_is_rejected(self, dhcp_server_factory, settings, monkeypatch):
        from netbox_dhcp_kea_plugin.forms import DHCPServerForm

        monkeypatch.setitem(settings.PLUGINS_CONFIG["netbox_dhcp_kea_plugin"], "enable_netbox_dns", False)
        server = dhcp_server_factory(name="kea-form-ip", ip_suffix=63)

        form = DHCPServerForm(data=_form_data(server, pki_fqdn="10.0.0.9"), instance=server)

        assert not form.is_valid()
        assert "pki_fqdn" in form.errors

    def test_the_record_picker_is_absent_without_the_dns_integration(
        self, dhcp_server_factory, settings, monkeypatch
    ):
        from netbox_dhcp_kea_plugin.forms import DHCPServerForm

        monkeypatch.setitem(settings.PLUGINS_CONFIG["netbox_dhcp_kea_plugin"], "enable_netbox_dns", False)
        server = dhcp_server_factory(name="kea-form-nodns", ip_suffix=64)

        form = DHCPServerForm(data=_form_data(server), instance=server)

        assert "pki_record" not in form.fields
        assert form.is_valid(), form.errors

    def test_a_picked_record_fills_the_identity(self, dhcp_server_factory, settings, monkeypatch):
        """The picker wins over typed text — it is the name DNS actually serves."""
        from netbox_dns.models import NameServer, Record, View, Zone

        from netbox_dhcp_kea_plugin.forms import DHCPServerForm

        monkeypatch.setitem(settings.PLUGINS_CONFIG["netbox_dhcp_kea_plugin"], "enable_netbox_dns", True)

        view, _ = View.objects.get_or_create(name="default")
        soa = NameServer.objects.get_or_create(name="ns-soa.example.net")[0]
        zone, _ = Zone.objects.get_or_create(
            name="pki.example.net",
            view=view,
            defaults={"soa_mname": soa, "soa_rname": "hostmaster.example.net"},
        )
        record = Record.objects.create(zone=zone, name="kea-picked", type="A", value="192.0.2.65")

        server = dhcp_server_factory(name="kea-form-pick", ip_suffix=65)
        form = DHCPServerForm(
            data=_form_data(server, pki_record=record.pk, pki_fqdn="typed-and-ignored.example.net"),
            instance=server,
        )

        assert "pki_record" in form.fields
        assert form.is_valid(), form.errors
        assert form.cleaned_data["pki_fqdn"] == "kea-picked.pki.example.net"


@pytest.mark.django_db
class TestIPAddressQuickAdd:
    """The IP address selector offers NetBox's inline "+" create."""

    def _get_form_page(self, client, admin_user, url_name, **kwargs):
        from django.urls import reverse

        client.force_login(admin_user)
        return client.get(reverse(f"plugins:netbox_dhcp_kea_plugin:{url_name}", kwargs=kwargs))

    def test_the_field_declares_quick_add(self):
        from netbox_dhcp_kea_plugin.forms import DHCPServerForm

        assert DHCPServerForm().fields["ip_address"].quick_add is True

    def test_the_create_page_renders_the_quick_add_control(self, client, admin_user):
        from django.urls import reverse

        response = self._get_form_page(client, admin_user, "dhcpserver_add")

        assert response.status_code == 200
        # The affordance is an hx-get at the IPAM add form flagged _quickadd.
        assert f"{reverse('ipam:ipaddress_add')}?_quickadd=True".encode() in response.content

    def test_the_edit_page_renders_it_too(self, client, admin_user, dhcp_server_factory):
        from django.urls import reverse

        server = dhcp_server_factory(name="kea-quickadd", ip_suffix=97)

        response = self._get_form_page(client, admin_user, "dhcpserver_edit", pk=server.pk)

        assert response.status_code == 200
        assert f"{reverse('ipam:ipaddress_add')}?_quickadd=True".encode() in response.content
