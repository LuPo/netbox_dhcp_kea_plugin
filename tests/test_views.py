"""
Tests for the DHCP KEA plugin views.

Run with:
    cd /path/to/netbox-dhcp-kea-plugin
    source /path/to/netbox/venv/bin/activate
    pytest tests/test_views.py -v
"""

import pytest
from django.urls import reverse


class TestSubnetReservationsView:
    """Tests for the Subnet reservations view."""

    def test_reservations_view_exists(self, db, subnet_factory):
        """Test that the reservations view URL exists."""
        config = subnet_factory()
        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:subnet_reservations",
            kwargs={"pk": config.pk},
        )
        assert url is not None
        assert str(config.pk) in url

    def test_reservations_view_returns_200(self, db, client, subnet_factory, admin_user):
        """Test that the reservations view returns 200 for authenticated user."""
        config = subnet_factory()
        client.force_login(admin_user)

        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:subnet_reservations",
            kwargs={"pk": config.pk},
        )
        response = client.get(url)

        assert response.status_code == 200

    def test_reservations_view_context_has_reservations(self, db, client, subnet_factory, admin_user):
        """Test that the view context contains reservations list."""
        config = subnet_factory()
        client.force_login(admin_user)

        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:subnet_reservations",
            kwargs={"pk": config.pk},
        )
        response = client.get(url)

        assert "reservations" in response.context
        assert "reservation_count" in response.context
        assert "kea_reservations" in response.context

    def test_reservations_view_empty_prefix(self, db, client, subnet_factory, admin_user):
        """Test that view handles prefix with no reservable IPs."""
        config = subnet_factory()
        client.force_login(admin_user)

        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:subnet_reservations",
            kwargs={"pk": config.pk},
        )
        response = client.get(url)

        assert response.status_code == 200
        assert response.context["reservation_count"] == 0
        assert response.context["reservations"] == []

    def test_reservations_includes_primary_ip(self, db, client, subnet_factory, admin_user):
        """Test that reservations include IPs marked as primary."""
        import netaddr
        from dcim.models import Device, DeviceRole, DeviceType, Interface, MACAddress, Manufacturer, Site
        from django.contrib.contenttypes.models import ContentType
        from ipam.models import IPAddress, Prefix

        # Create a prefix
        prefix = Prefix.objects.create(prefix="192.168.100.0/24")

        # Create device with interface
        site = Site.objects.create(name="Test Site", slug="test-site-res")
        manufacturer = Manufacturer.objects.create(name="Test Mfg Res", slug="test-mfg-res")
        device_type = DeviceType.objects.create(
            manufacturer=manufacturer, model="Test Model Res", slug="test-model-res"
        )
        device_role = DeviceRole.objects.create(name="Test Role Res", slug="test-role-res")
        device = Device.objects.create(
            name="test-device-res",
            site=site,
            device_type=device_type,
            role=device_role,
        )
        interface = Interface.objects.create(
            device=device,
            name="eth0",
            type="1000base-t",
        )
        # Create MAC address and assign to interface
        mac = MACAddress.objects.create(
            mac_address="AA:BB:CC:DD:EE:FF",
            assigned_object_type=ContentType.objects.get_for_model(Interface),
            assigned_object_id=interface.pk,
        )
        interface.primary_mac_address = mac
        interface.save()

        # Create IP in the prefix and assign to interface
        ip = IPAddress.objects.create(
            address=netaddr.IPNetwork("192.168.100.10/24"),
            assigned_object=interface,
            dns_name="test-host.example.com",
        )

        # Set as primary IP
        device.primary_ip4 = ip
        device.save()

        # Create DHCP config for the prefix
        config = subnet_factory(prefix=prefix)

        client.force_login(admin_user)
        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:subnet_reservations",
            kwargs={"pk": config.pk},
        )
        response = client.get(url)

        assert response.status_code == 200
        assert response.context["reservation_count"] == 1

        reservations = response.context["reservations"]
        assert len(reservations) == 1

        kea_res, meta = reservations[0]
        assert kea_res["ip-address"] == "192.168.100.10"
        assert kea_res["hw-address"] == "aa:bb:cc:dd:ee:ff"
        assert kea_res["hostname"] == "test-host"
        assert meta["is_primary"] is True

    def test_reservations_includes_oob_ip(self, db, client, subnet_factory, admin_user):
        """Test that reservations include IPs marked as OOB."""
        import netaddr
        from dcim.models import Device, DeviceRole, DeviceType, Interface, MACAddress, Manufacturer, Site
        from django.contrib.contenttypes.models import ContentType
        from ipam.models import IPAddress, Prefix

        # Create a prefix
        prefix = Prefix.objects.create(prefix="192.168.200.0/24")

        # Create device with interface
        site = Site.objects.create(name="Test Site OOB", slug="test-site-oob")
        manufacturer = Manufacturer.objects.create(name="Test Mfg OOB", slug="test-mfg-oob")
        device_type = DeviceType.objects.create(
            manufacturer=manufacturer, model="Test Model OOB", slug="test-model-oob"
        )
        device_role = DeviceRole.objects.create(name="Test Role OOB", slug="test-role-oob")
        device = Device.objects.create(
            name="test-device-oob",
            site=site,
            device_type=device_type,
            role=device_role,
        )
        interface = Interface.objects.create(
            device=device,
            name="mgmt0",
            type="1000base-t",
        )
        # Create MAC address and assign to interface
        mac = MACAddress.objects.create(
            mac_address="11:22:33:44:55:66",
            assigned_object_type=ContentType.objects.get_for_model(Interface),
            assigned_object_id=interface.pk,
        )
        interface.primary_mac_address = mac
        interface.save()

        # Create IP in the prefix and assign to interface
        ip = IPAddress.objects.create(
            address=netaddr.IPNetwork("192.168.200.20/24"),
            assigned_object=interface,
        )

        # Set as OOB IP
        device.oob_ip = ip
        device.save()

        # Create DHCP config for the prefix
        config = subnet_factory(prefix=prefix)

        client.force_login(admin_user)
        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:subnet_reservations",
            kwargs={"pk": config.pk},
        )
        response = client.get(url)

        assert response.status_code == 200
        assert response.context["reservation_count"] == 1

        reservations = response.context["reservations"]
        kea_res, meta = reservations[0]
        assert kea_res["ip-address"] == "192.168.200.20"
        assert meta["is_oob"] is True
        # OOB IP should have interface name appended to hostname
        assert "mgmt0" in kea_res["hostname"] or kea_res["hostname"] == "test-device-oob_mgmt0"

    def test_reservations_excludes_non_primary_non_oob(self, client, subnet_factory, admin_user):
        """Test that IPs not marked as primary or OOB are excluded."""
        import netaddr
        from dcim.models import Device, DeviceRole, DeviceType, Interface, Manufacturer, Site
        from ipam.models import IPAddress, Prefix

        # Create a prefix
        prefix = Prefix.objects.create(prefix="192.168.50.0/24")

        # Create device with interface
        site = Site.objects.create(name="Test Site Excl", slug="test-site-excl")
        manufacturer = Manufacturer.objects.create(name="Test Mfg Excl", slug="test-mfg-excl")
        device_type = DeviceType.objects.create(
            manufacturer=manufacturer, model="Test Model Excl", slug="test-model-excl"
        )
        device_role = DeviceRole.objects.create(name="Test Role Excl", slug="test-role-excl")
        device = Device.objects.create(
            name="test-device-excl",
            site=site,
            device_type=device_type,
            role=device_role,
        )
        interface = Interface.objects.create(
            device=device,
            name="eth1",
            type="1000base-t",
        )

        # Create IP in the prefix and assign to interface, but NOT as primary or OOB
        # Note: IP is created but intentionally not set as primary_ip4 or oob_ip
        IPAddress.objects.create(
            address=netaddr.IPNetwork("192.168.50.50/24"),
            assigned_object=interface,
        )

        # Create DHCP config for the prefix
        config = subnet_factory(prefix=prefix)

        client.force_login(admin_user)
        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:subnet_reservations",
            kwargs={"pk": config.pk},
        )
        response = client.get(url)

        assert response.status_code == 200
        # Should have no reservations since IP is not primary or OOB
        assert response.context["reservation_count"] == 0

    def test_reservations_excludes_fhrp_groups(self, db, client, subnet_factory, admin_user):
        """Test that FHRP group IPs are excluded from reservations."""
        import netaddr
        from ipam.models import FHRPGroup, IPAddress, Prefix

        # Create a prefix
        prefix = Prefix.objects.create(prefix="192.168.60.0/24")

        # Create FHRP group
        fhrp_group = FHRPGroup.objects.create(
            group_id=1,
            protocol="vrrp2",
        )

        # Create IP assigned to FHRP group
        IPAddress.objects.create(
            address=netaddr.IPNetwork("192.168.60.1/24"),
            assigned_object=fhrp_group,
        )

        # Create DHCP config for the prefix
        config = subnet_factory(prefix=prefix)

        client.force_login(admin_user)
        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:subnet_reservations",
            kwargs={"pk": config.pk},
        )
        response = client.get(url)

        assert response.status_code == 200
        # Should have no reservations since FHRP IPs are excluded
        assert response.context["reservation_count"] == 0

    def test_reservations_kea_format(self, db, client, subnet_factory, admin_user):
        """Test that KEA reservations are properly formatted."""
        import netaddr
        from dcim.models import Device, DeviceRole, DeviceType, Interface, MACAddress, Manufacturer, Site
        from django.contrib.contenttypes.models import ContentType
        from ipam.models import IPAddress, Prefix

        # Create a prefix
        prefix = Prefix.objects.create(prefix="192.168.70.0/24")

        # Create device with interface
        site = Site.objects.create(name="Test Site JSON", slug="test-site-json")
        manufacturer = Manufacturer.objects.create(name="Test Mfg JSON", slug="test-mfg-json")
        device_type = DeviceType.objects.create(
            manufacturer=manufacturer, model="Test Model JSON", slug="test-model-json"
        )
        device_role = DeviceRole.objects.create(name="Test Role JSON", slug="test-role-json")
        device = Device.objects.create(
            name="json-test-device",
            site=site,
            device_type=device_type,
            role=device_role,
        )
        interface = Interface.objects.create(
            device=device,
            name="eth0",
            type="1000base-t",
        )
        # Create MAC address and assign to interface
        mac = MACAddress.objects.create(
            mac_address="DE:AD:BE:EF:CA:FE",
            assigned_object_type=ContentType.objects.get_for_model(Interface),
            assigned_object_id=interface.pk,
        )
        interface.primary_mac_address = mac
        interface.save()

        ip = IPAddress.objects.create(
            address=netaddr.IPNetwork("192.168.70.100/24"),
            assigned_object=interface,
            dns_name="json-host.test.local",
        )
        device.primary_ip4 = ip
        device.save()

        config = subnet_factory(prefix=prefix)

        client.force_login(admin_user)
        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:subnet_reservations",
            kwargs={"pk": config.pk},
        )
        response = client.get(url)

        # Verify the KEA reservations list
        reservations = response.context["kea_reservations"]

        assert isinstance(reservations, list)
        assert len(reservations) == 1
        assert reservations[0]["ip-address"] == "192.168.70.100"
        assert reservations[0]["hw-address"] == "de:ad:be:ef:ca:fe"
        assert reservations[0]["hostname"] == "json-host"

    def test_reservations_without_mac_address(self, db, client, subnet_factory, admin_user):
        """Test that reservations work without MAC address."""
        import netaddr
        from dcim.models import Device, DeviceRole, DeviceType, Interface, Manufacturer, Site
        from ipam.models import IPAddress, Prefix

        # Create a prefix
        prefix = Prefix.objects.create(prefix="192.168.80.0/24")

        # Create device with interface (no MAC)
        site = Site.objects.create(name="Test Site NoMAC", slug="test-site-nomac")
        manufacturer = Manufacturer.objects.create(name="Test Mfg NoMAC", slug="test-mfg-nomac")
        device_type = DeviceType.objects.create(
            manufacturer=manufacturer, model="Test Model NoMAC", slug="test-model-nomac"
        )
        device_role = DeviceRole.objects.create(name="Test Role NoMAC", slug="test-role-nomac")
        device = Device.objects.create(
            name="nomac-device",
            site=site,
            device_type=device_type,
            role=device_role,
        )
        interface = Interface.objects.create(
            device=device,
            name="eth0",
            type="1000base-t",
            # No MAC address
        )

        # Create IP assigned to interface and set as primary
        ip = IPAddress.objects.create(
            address=netaddr.IPNetwork("192.168.80.50/24"),
            assigned_object=interface,
        )
        device.primary_ip4 = ip
        device.save()

        config = subnet_factory(prefix=prefix)

        client.force_login(admin_user)
        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:subnet_reservations",
            kwargs={"pk": config.pk},
        )
        response = client.get(url)

        assert response.status_code == 200
        assert response.context["reservation_count"] == 1

        reservations = response.context["reservations"]
        kea_res, meta = reservations[0]
        assert kea_res["ip-address"] == "192.168.80.50"
        assert "hw-address" not in kea_res  # No MAC address
        assert kea_res["hostname"] == "nomac-device"

    def test_reservations_hostname_from_dns_name(self, db, client, subnet_factory, admin_user):
        """Test that hostname is extracted from dns_name when available."""
        import netaddr
        from dcim.models import Device, DeviceRole, DeviceType, Interface, Manufacturer, Site
        from ipam.models import IPAddress, Prefix

        # Create a prefix
        prefix = Prefix.objects.create(prefix="192.168.90.0/24")

        # Create device with interface
        site = Site.objects.create(name="Test Site DNS", slug="test-site-dns")
        manufacturer = Manufacturer.objects.create(name="Test Mfg DNS", slug="test-mfg-dns")
        device_type = DeviceType.objects.create(
            manufacturer=manufacturer, model="Test Model DNS", slug="test-model-dns"
        )
        device_role = DeviceRole.objects.create(name="Test Role DNS", slug="test-role-dns")
        device = Device.objects.create(
            name="device-with-long-name",
            site=site,
            device_type=device_type,
            role=device_role,
        )
        interface = Interface.objects.create(
            device=device,
            name="eth0",
            type="1000base-t",
        )
        # No MAC address for this test

        ip = IPAddress.objects.create(
            address=netaddr.IPNetwork("192.168.90.10/24"),
            assigned_object=interface,
            dns_name="short-name.subdomain.example.com",
        )
        device.primary_ip4 = ip
        device.save()

        config = subnet_factory(prefix=prefix)

        client.force_login(admin_user)
        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:subnet_reservations",
            kwargs={"pk": config.pk},
        )
        response = client.get(url)

        reservations = response.context["reservations"]
        kea_res, _ = reservations[0]
        # Should use first part of dns_name, not device name
        assert kea_res["hostname"] == "short-name"


class TestReservationCountBadge:
    """Tests for the reservation count badge on the tab."""

    def test_badge_shows_correct_count(self, db, client, subnet_factory, admin_user):
        """Test that the badge shows the correct reservation count."""
        from dcim.models import Device, DeviceRole, DeviceType, Interface, Manufacturer, Site
        from ipam.models import IPAddress, Prefix

        # Create a prefix with multiple reservable IPs
        prefix = Prefix.objects.create(prefix="10.10.0.0/24")

        site = Site.objects.create(name="Badge Test Site", slug="badge-test-site")
        manufacturer = Manufacturer.objects.create(name="Badge Mfg", slug="badge-mfg")
        device_type = DeviceType.objects.create(manufacturer=manufacturer, model="Badge Model", slug="badge-model")
        device_role = DeviceRole.objects.create(name="Badge Role", slug="badge-role")

        # Create 3 devices with primary IPs
        for i in range(3):
            device = Device.objects.create(
                name=f"badge-device-{i}",
                site=site,
                device_type=device_type,
                role=device_role,
            )
            interface = Interface.objects.create(
                device=device,
                name="eth0",
                type="1000base-t",
            )
            ip = IPAddress.objects.create(
                address=f"10.10.0.{10 + i}/24",
                assigned_object=interface,
            )
            device.primary_ip4 = ip
            device.save()

        config = subnet_factory(prefix=prefix)

        client.force_login(admin_user)
        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:subnet_reservations",
            kwargs={"pk": config.pk},
        )
        response = client.get(url)

        assert response.context["reservation_count"] == 3


# Fixtures needed for tests
@pytest.fixture
def admin_user(db):
    """Create an admin user for testing authenticated views."""
    from users.models import User

    user, _ = User.objects.get_or_create(
        username="admin_test",
        defaults={
            "email": "admin@test.com",
            "is_superuser": True,
            "is_active": True,
        },
    )
    return user


@pytest.fixture
def client():
    """Return Django test client."""
    from django.test import Client

    return Client()


@pytest.mark.django_db
class TestHARelationshipEmptyState:
    """A freshly created relationship has no members and no obvious next step."""

    def _get(self, client, admin_user, relationship):
        client.force_login(admin_user)
        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:dhcpharelationship", kwargs={"pk": relationship.pk}
        )
        return client.get(url)

    @pytest.fixture
    def relationship(self, db):
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        return DHCPHARelationship.objects.create(name="empty-cluster", mode="hot-standby")

    def test_an_empty_relationship_offers_the_add_action(self, client, admin_user, relationship):
        response = self._get(client, admin_user, relationship)

        assert response.status_code == 200
        add_url = reverse("plugins:netbox_dhcp_kea_plugin:dhcpserver_add")
        assert f"{add_url}?ha_relationship={relationship.pk}".encode() in response.content

    def test_the_action_stays_once_a_member_exists(
        self, client, admin_user, relationship, dhcp_server_factory
    ):
        """A hot-standby pair needs two members, so adding the second must work."""

        dhcp_server_factory(
            name="kea-member",
            ip_suffix=96,
            ha_relationship=relationship,
            ha_role="primary",
            ha_address="10.0.0.96",
        )

        response = self._get(client, admin_user, relationship)

        add_url = reverse("plugins:netbox_dhcp_kea_plugin:dhcpserver_add")
        assert f"{add_url}?ha_relationship={relationship.pk}".encode() in response.content
        assert b"kea-member" in response.content

    def test_the_prefilled_form_preselects_the_relationship(
        self, client, admin_user, relationship
    ):
        """The button is only useful if the target form honours the parameter."""
        from django.urls import reverse

        client.force_login(admin_user)
        response = client.get(
            reverse("plugins:netbox_dhcp_kea_plugin:dhcpserver_add"),
            {"ha_relationship": relationship.pk},
        )

        assert response.status_code == 200
        assert response.context["form"]["ha_relationship"].value() == str(relationship.pk)


@pytest.mark.django_db
class TestHARelationshipValidityExplained:
    """The badge says Invalid; the page has to say why."""

    def _get(self, client, admin_user, relationship):
        client.force_login(admin_user)
        return client.get(
            reverse(
                "plugins:netbox_dhcp_kea_plugin:dhcpharelationship", kwargs={"pk": relationship.pk}
            )
        )

    def _pair(self, dhcp_server_factory, relationship, standby_role):
        for index, (suffix, role) in enumerate(
            ((201, "primary"), (202, standby_role)), start=1
        ):
            dhcp_server_factory(
                name=f"{relationship.name}-{index}",
                ip_suffix=suffix,
                ha_relationship=relationship,
                ha_role=role,
                ha_address=f"10.20.0.{suffix}",
            )

    @pytest.fixture
    def relationship(self, db):
        from netbox_dhcp_kea_plugin.models import DHCPHARelationship

        return DHCPHARelationship.objects.create(name="explain-me", mode="hot-standby")

    def test_a_secondary_in_hot_standby_is_explained(
        self, client, admin_user, relationship, dhcp_server_factory
    ):
        """The exact mix-up the roles invite: secondary is load-balancing's."""
        self._pair(dhcp_server_factory, relationship, "secondary")

        response = self._get(client, admin_user, relationship)

        assert response.status_code == 200
        reasons = response.context["configuration_errors"]
        assert len(reasons) == 1
        assert "exactly one standby" in reasons[0]
        assert "load-balancing role" in reasons[0]
        assert b"Invalid" in response.content
        # Carried in the badge's tooltip rather than as body text.
        assert b"exactly one standby" in response.content
        assert b'data-bs-toggle="tooltip"' in response.content

    def test_a_valid_pair_lists_no_reasons(
        self, client, admin_user, relationship, dhcp_server_factory
    ):
        self._pair(dhcp_server_factory, relationship, "standby")

        response = self._get(client, admin_user, relationship)

        assert response.context["configuration_errors"] == []
        assert b"Valid" in response.content

    def test_an_empty_relationship_explains_both_gaps(self, client, admin_user, relationship):
        response = self._get(client, admin_user, relationship)

        reasons = response.context["configuration_errors"]
        assert len(reasons) == 2
        assert any("exactly one primary" in r for r in reasons)
        assert any("exactly one standby" in r for r in reasons)

    def test_the_help_tooltips_are_rendered(self, client, admin_user, relationship):
        response = self._get(client, admin_user, relationship)

        # NetBox's own chrome uses tooltips too, so scope the count to ours.
        # Four here: the three help labels plus the invalid-reason badge, since
        # this fixture's relationship has no members yet.
        assert response.content.count(b"mdi mdi-information-outline text-primary") == 4
        assert b"edit the server and set its HA Relationship field" in response.content
        assert b"<small>To add an existing server" not in response.content
        assert b"All or nothing for the relationship" in response.content
        assert b"Shared by every member" in response.content
        # The prose moved into the tooltips, so it is no longer body text.
        assert b"<small>All or nothing" not in response.content


@pytest.mark.django_db
class TestDHCPServerBulkEdit:
    """Bulk edit posted to a route that did not exist, giving a 404."""

    def test_the_route_resolves(self):
        assert reverse("plugins:netbox_dhcp_kea_plugin:dhcpserver_bulk_edit").endswith(
            "/dhcp-servers/edit/"
        )

    def test_the_form_renders_for_a_selection(self, client, admin_user, dhcp_server_factory):
        first = dhcp_server_factory(name="kea-bulk-a", ip_suffix=131)
        second = dhcp_server_factory(name="kea-bulk-b", ip_suffix=132)
        client.force_login(admin_user)

        response = client.post(
            reverse("plugins:netbox_dhcp_kea_plugin:dhcpserver_bulk_edit"),
            {"pk": [first.pk, second.pk], "_edit": ""},
        )

        assert response.status_code == 200

    def test_applying_a_change_updates_every_selected_server(
        self, client, admin_user, dhcp_server_factory
    ):
        from netbox_dhcp_kea_plugin.models import DHCPServer

        first = dhcp_server_factory(name="kea-bulk-c", ip_suffix=133)
        second = dhcp_server_factory(name="kea-bulk-d", ip_suffix=134)
        client.force_login(admin_user)

        response = client.post(
            reverse("plugins:netbox_dhcp_kea_plugin:dhcpserver_bulk_edit"),
            {
                "pk": [first.pk, second.pk],
                "_apply": "",
                "status": "offline",
                "description": "bulk edited",
            },
        )

        assert response.status_code in (200, 302), response.status_code
        for server in DHCPServer.objects.filter(pk__in=[first.pk, second.pk]):
            assert server.status == "offline"
            assert server.description == "bulk edited"

    def test_per_host_fields_are_not_offered(self):
        """Bulk-setting these could only ever collide."""
        from netbox_dhcp_kea_plugin.forms import DHCPServerBulkEditForm

        fields = DHCPServerBulkEditForm().fields
        for unique_to_one_host in ("name", "ip_address", "ha_address", "pki_fqdn"):
            assert unique_to_one_host not in fields
