"""StaticReservation model + its merge into Subnet.get_reservations()."""

import pytest
from django.core.exceptions import ValidationError


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sr_prefix(db):
    from ipam.models import Prefix

    return Prefix.objects.create(prefix="10.20.0.0/24")


@pytest.fixture
def sr_subnet(db, sr_prefix, dhcp_server_factory):
    from netbox_dhcp_kea_plugin.models import Subnet

    return Subnet.objects.create(
        prefix=sr_prefix,
        server=dhcp_server_factory(),
        valid_lifetime=3600,
        max_lifetime=7200,
        routers_option_offset=1,
    )


def _mac(addr):
    from dcim.models import MACAddress

    return MACAddress.objects.create(mac_address=addr)


def _ip(addr):
    from ipam.models import IPAddress

    return IPAddress.objects.create(address=addr)


def _reservation(subnet, ip_addr, mac_addr, **kwargs):
    from netbox_dhcp_kea_plugin.models import StaticReservation

    return StaticReservation.objects.create(
        subnet=subnet,
        ip_address=_ip(ip_addr),
        mac_address=_mac(mac_addr),
        **kwargs,
    )


def _make_derived(prefix_str, ip_str, mac_str, vm_name):
    """Create a VM whose primary IP yields a device-derived reservation."""
    from dcim.models import MACAddress
    from ipam.models import IPAddress
    from virtualization.models import Cluster, ClusterType, VirtualMachine, VMInterface

    ct, _ = ClusterType.objects.get_or_create(name="sr-ct", slug="sr-ct")
    cluster, _ = Cluster.objects.get_or_create(name="sr-cl", type=ct)
    vm = VirtualMachine.objects.create(name=vm_name, cluster=cluster)
    iface = VMInterface.objects.create(virtual_machine=vm, name="eth0")
    mac = MACAddress.objects.create(mac_address=mac_str, assigned_object=iface)
    iface.primary_mac_address = mac
    iface.save()
    ip = IPAddress.objects.create(address=ip_str, assigned_object=iface)
    vm.primary_ip4 = ip
    vm.save()
    return ip


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


def test_to_kea_dict(sr_subnet):
    res = _reservation(sr_subnet, "10.20.0.30/24", "AA:BB:CC:DD:EE:01", hostname="printer-1")
    d = res.to_kea_dict()
    assert d == {
        "ip-address": "10.20.0.30",
        "hw-address": "aa:bb:cc:dd:ee:01",
        "hostname": "printer-1",
    }


def test_clean_rejects_ip_outside_prefix(sr_subnet):
    from netbox_dhcp_kea_plugin.models import StaticReservation

    res = StaticReservation(
        subnet=sr_subnet,
        ip_address=_ip("10.99.0.5/24"),  # not within 10.20.0.0/24
        mac_address=_mac("AA:BB:CC:DD:EE:02"),
    )
    with pytest.raises(ValidationError) as exc:
        res.clean()
    assert "ip_address" in exc.value.message_dict


def test_clean_rejects_duplicate_mac_string(sr_subnet):
    from netbox_dhcp_kea_plugin.models import StaticReservation

    _reservation(sr_subnet, "10.20.0.31/24", "AA:BB:CC:DD:EE:03")
    dup = StaticReservation(
        subnet=sr_subnet,
        ip_address=_ip("10.20.0.32/24"),
        mac_address=_mac("AA:BB:CC:DD:EE:03"),  # same MAC string, different object
    )
    with pytest.raises(ValidationError) as exc:
        dup.clean()
    assert "mac_address" in exc.value.message_dict


def test_db_constraint_rejects_same_mac_object(sr_subnet):
    from django.db.utils import IntegrityError

    from netbox_dhcp_kea_plugin.models import StaticReservation

    mac = _mac("AA:BB:CC:DD:EE:05")
    StaticReservation.objects.create(
        subnet=sr_subnet, ip_address=_ip("10.20.0.33/24"), mac_address=mac
    )
    with pytest.raises(IntegrityError):
        StaticReservation.objects.create(
            subnet=sr_subnet, ip_address=_ip("10.20.0.34/24"), mac_address=mac
        )


# ---------------------------------------------------------------------------
# Merge into Subnet.get_reservations()
# ---------------------------------------------------------------------------


def test_explicit_reservation_emitted(sr_subnet):
    _reservation(sr_subnet, "10.20.0.40/24", "AA:BB:CC:DD:EE:04")
    kea = sr_subnet.get_kea_reservations()
    assert {"ip-address": "10.20.0.40", "hw-address": "aa:bb:cc:dd:ee:04"} in [
        {k: v for k, v in r.items() if k in ("ip-address", "hw-address")} for r in kea
    ]


def test_explicit_merges_with_derived(sr_subnet):
    _make_derived("10.20.0.0/24", "10.20.0.50/24", "AA:BB:CC:DD:EE:50", "sr-vm-a")
    _reservation(sr_subnet, "10.20.0.60/24", "AA:BB:CC:DD:EE:60")
    ips = {r["ip-address"] for r in sr_subnet.get_kea_reservations()}
    assert "10.20.0.50" in ips  # derived
    assert "10.20.0.60" in ips  # explicit


def test_auto_reservations_false_excludes_derived(sr_subnet):
    _make_derived("10.20.0.0/24", "10.20.0.51/24", "AA:BB:CC:DD:EE:51", "sr-vm-b")
    _reservation(sr_subnet, "10.20.0.61/24", "AA:BB:CC:DD:EE:61")
    sr_subnet.auto_reservations = False
    sr_subnet.save()
    ips = {r["ip-address"] for r in sr_subnet.get_kea_reservations()}
    assert ips == {"10.20.0.61"}  # only the explicit one


def test_explicit_wins_on_same_ip(sr_subnet):
    # The derived IP and an explicit reservation on the *same* IPAddress collide;
    # the explicit MAC must win.
    derived_ip = _make_derived("10.20.0.0/24", "10.20.0.70/24", "AA:BB:CC:DD:EE:70", "sr-vm-c")
    from netbox_dhcp_kea_plugin.models import StaticReservation

    StaticReservation.objects.create(
        subnet=sr_subnet,
        ip_address=derived_ip,
        mac_address=_mac("AA:BB:CC:DD:EE:99"),
    )
    entries = [r for r in sr_subnet.get_kea_reservations() if r["ip-address"] == "10.20.0.70"]
    assert len(entries) == 1
    assert entries[0]["hw-address"] == "aa:bb:cc:dd:ee:99"  # explicit wins
