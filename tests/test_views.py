"""
Tests for the DHCP KEA plugin views.

Run with:
    cd /path/to/netbox-dhcp-kea-plugin
    source /path/to/netbox/venv/bin/activate
    pytest tests/test_views.py -v
"""

import pytest
from django.urls import reverse


class TestPrefixDHCPConfigReservationsView:
    """Tests for the PrefixDHCPConfig reservations view."""

    def test_reservations_view_exists(self, db, prefix_dhcp_config_factory):
        """Test that the reservations view URL exists."""
        config = prefix_dhcp_config_factory()
        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:prefixdhcpconfig_reservations",
            kwargs={"pk": config.pk},
        )
        assert url is not None
        assert str(config.pk) in url

    def test_reservations_view_returns_200(self, db, client, prefix_dhcp_config_factory, admin_user):
        """Test that the reservations view returns 200 for authenticated user."""
        config = prefix_dhcp_config_factory()
        client.force_login(admin_user)

        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:prefixdhcpconfig_reservations",
            kwargs={"pk": config.pk},
        )
        response = client.get(url)

        assert response.status_code == 200

    def test_reservations_view_context_has_reservations(self, db, client, prefix_dhcp_config_factory, admin_user):
        """Test that the view context contains reservations list."""
        config = prefix_dhcp_config_factory()
        client.force_login(admin_user)

        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:prefixdhcpconfig_reservations",
            kwargs={"pk": config.pk},
        )
        response = client.get(url)

        assert "reservations" in response.context
        assert "reservation_count" in response.context
        assert "kea_reservations" in response.context

    def test_reservations_view_empty_prefix(self, db, client, prefix_dhcp_config_factory, admin_user):
        """Test that view handles prefix with no reservable IPs."""
        config = prefix_dhcp_config_factory()
        client.force_login(admin_user)

        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:prefixdhcpconfig_reservations",
            kwargs={"pk": config.pk},
        )
        response = client.get(url)

        assert response.status_code == 200
        assert response.context["reservation_count"] == 0
        assert response.context["reservations"] == []

    def test_reservations_includes_primary_ip(self, db, client, prefix_dhcp_config_factory, admin_user):
        """Test that reservations include IPs marked as primary."""
        from dcim.models import Device, DeviceRole, DeviceType, Interface, Manufacturer, Site
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
            mac_address="AA:BB:CC:DD:EE:FF",
        )

        # Create IP in the prefix and assign to interface
        ip = IPAddress.objects.create(
            address="192.168.100.10/24",
            assigned_object=interface,
            dns_name="test-host.example.com",
        )

        # Set as primary IP
        device.primary_ip4 = ip
        device.save()

        # Create DHCP config for the prefix
        config = prefix_dhcp_config_factory(prefix=prefix)

        client.force_login(admin_user)
        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:prefixdhcpconfig_reservations",
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

    def test_reservations_includes_oob_ip(self, db, client, prefix_dhcp_config_factory, admin_user):
        """Test that reservations include IPs marked as OOB."""
        from dcim.models import Device, DeviceRole, DeviceType, Interface, Manufacturer, Site
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
            mac_address="11:22:33:44:55:66",
        )

        # Create IP in the prefix and assign to interface
        ip = IPAddress.objects.create(
            address="192.168.200.20/24",
            assigned_object=interface,
        )

        # Set as OOB IP
        device.oob_ip = ip
        device.save()

        # Create DHCP config for the prefix
        config = prefix_dhcp_config_factory(prefix=prefix)

        client.force_login(admin_user)
        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:prefixdhcpconfig_reservations",
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

    def test_reservations_excludes_non_primary_non_oob(self, db, client, prefix_dhcp_config_factory, admin_user):
        """Test that IPs not marked as primary or OOB are excluded."""
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
        IPAddress.objects.create(
            address="192.168.50.30/24",
            assigned_object=interface,
        )

        # Create DHCP config for the prefix
        config = prefix_dhcp_config_factory(prefix=prefix)

        client.force_login(admin_user)
        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:prefixdhcpconfig_reservations",
            kwargs={"pk": config.pk},
        )
        response = client.get(url)

        assert response.status_code == 200
        # Should have no reservations since IP is not primary or OOB
        assert response.context["reservation_count"] == 0

    def test_reservations_excludes_fhrp_groups(self, db, client, prefix_dhcp_config_factory, admin_user):
        """Test that FHRP group IPs are excluded from reservations."""
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
            address="192.168.60.1/24",
            assigned_object=fhrp_group,
        )

        # Create DHCP config for the prefix
        config = prefix_dhcp_config_factory(prefix=prefix)

        client.force_login(admin_user)
        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:prefixdhcpconfig_reservations",
            kwargs={"pk": config.pk},
        )
        response = client.get(url)

        assert response.status_code == 200
        # Should have no reservations since FHRP IPs are excluded
        assert response.context["reservation_count"] == 0

    def test_reservations_kea_format(self, db, client, prefix_dhcp_config_factory, admin_user):
        """Test that KEA reservations are properly formatted."""
        from dcim.models import Device, DeviceRole, DeviceType, Interface, Manufacturer, Site
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
            mac_address="DE:AD:BE:EF:CA:FE",
        )

        ip = IPAddress.objects.create(
            address="192.168.70.100/24",
            assigned_object=interface,
            dns_name="json-host.test.local",
        )
        device.primary_ip4 = ip
        device.save()

        config = prefix_dhcp_config_factory(prefix=prefix)

        client.force_login(admin_user)
        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:prefixdhcpconfig_reservations",
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

    def test_reservations_without_mac_address(self, db, client, prefix_dhcp_config_factory, admin_user):
        """Test that reservations work without MAC address."""
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

        ip = IPAddress.objects.create(
            address="192.168.80.50/24",
            assigned_object=interface,
        )
        device.primary_ip4 = ip
        device.save()

        config = prefix_dhcp_config_factory(prefix=prefix)

        client.force_login(admin_user)
        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:prefixdhcpconfig_reservations",
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

    def test_reservations_hostname_from_dns_name(self, db, client, prefix_dhcp_config_factory, admin_user):
        """Test that hostname is extracted from dns_name when available."""
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

        ip = IPAddress.objects.create(
            address="192.168.90.10/24",
            assigned_object=interface,
            dns_name="short-name.subdomain.example.com",
        )
        device.primary_ip4 = ip
        device.save()

        config = prefix_dhcp_config_factory(prefix=prefix)

        client.force_login(admin_user)
        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:prefixdhcpconfig_reservations",
            kwargs={"pk": config.pk},
        )
        response = client.get(url)

        reservations = response.context["reservations"]
        kea_res, _ = reservations[0]
        # Should use first part of dns_name, not device name
        assert kea_res["hostname"] == "short-name"


class TestReservationCountBadge:
    """Tests for the reservation count badge on the tab."""

    def test_badge_shows_correct_count(self, db, client, prefix_dhcp_config_factory, admin_user):
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

        config = prefix_dhcp_config_factory(prefix=prefix)

        client.force_login(admin_user)
        url = reverse(
            "plugins:netbox_dhcp_kea_plugin:prefixdhcpconfig_reservations",
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
            "is_staff": True,
            "is_active": True,
        },
    )
    return user


@pytest.fixture
def client():
    """Return Django test client."""
    from django.test import Client

    return Client()
