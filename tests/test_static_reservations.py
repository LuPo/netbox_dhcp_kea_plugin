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


def _ip_range(start, end):
    from ipam.models import IPRange
    from netaddr import IPNetwork

    return IPRange.objects.create(start_address=IPNetwork(start), end_address=IPNetwork(end))


def test_clean_rejects_in_pool_reservation_when_out_of_pool_enforced(sr_subnet):
    from netbox_dhcp_kea_plugin.models import StaticReservation

    sr_subnet.reservations_out_of_pool = True
    sr_subnet.save()
    _ip_range("10.20.0.100/24", "10.20.0.150/24")  # dynamic pool
    res = StaticReservation(
        subnet=sr_subnet,
        ip_address=_ip("10.20.0.120/24"),  # inside the pool
        mac_address=_mac("AA:BB:CC:DD:EE:F1"),
    )
    with pytest.raises(ValidationError) as exc:
        res.clean()
    assert "ip_address" in exc.value.message_dict


def test_clean_allows_out_of_pool_reservation_with_explicit_range(sr_subnet):
    from netbox_dhcp_kea_plugin.models import StaticReservation

    sr_subnet.reservations_out_of_pool = True
    sr_subnet.save()
    _ip_range("10.20.0.100/24", "10.20.0.150/24")
    res = StaticReservation(
        subnet=sr_subnet,
        ip_address=_ip("10.20.0.40/24"),  # outside the pool
        mac_address=_mac("AA:BB:CC:DD:EE:F2"),
    )
    res.clean()  # no error raised


def test_clean_allows_in_pool_reservation_when_out_of_pool_false(sr_subnet):
    from netbox_dhcp_kea_plugin.models import StaticReservation

    sr_subnet.reservations_out_of_pool = False  # in-pool reservations permitted
    sr_subnet.save()
    _ip_range("10.20.0.100/24", "10.20.0.150/24")
    res = StaticReservation(
        subnet=sr_subnet,
        ip_address=_ip("10.20.0.120/24"),  # inside the pool, but allowed
        mac_address=_mac("AA:BB:CC:DD:EE:F3"),
    )
    res.clean()  # no error raised


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


def test_reservations_sorted_by_ip(sr_subnet):
    # An explicit reservation must interleave with derived ones in numeric IP
    # order, not get appended after them (regression: it used to sort last).
    _make_derived("10.20.0.0/24", "10.20.0.50/24", "AA:BB:CC:DD:EE:a0", "sr-vm-lo")
    _make_derived("10.20.0.0/24", "10.20.0.90/24", "AA:BB:CC:DD:EE:b0", "sr-vm-hi")
    _reservation(sr_subnet, "10.20.0.70/24", "AA:BB:CC:DD:EE:c0")
    ips = [r["ip-address"] for r in sr_subnet.get_kea_reservations()]
    assert ips == ["10.20.0.50", "10.20.0.70", "10.20.0.90"]


# ---------------------------------------------------------------------------
# Views + REST API
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_client(db):
    from django.contrib.auth import get_user_model
    from django.test import Client

    u = get_user_model().objects.create_superuser("sr-admin", "sr@example.com", "x")
    c = Client()
    c.force_login(u)
    return c


@pytest.fixture
def api_client(db):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient

    u = get_user_model().objects.create_superuser("sr-api", "sr-api@example.com", "x")
    c = APIClient()
    c.force_authenticate(u)
    return c


def test_list_view_renders(admin_client, sr_subnet):
    from django.urls import reverse

    _reservation(sr_subnet, "10.20.0.80/24", "AA:BB:CC:DD:EE:80")
    resp = admin_client.get(reverse("plugins:netbox_dhcp_kea_plugin:staticreservation_list"))
    assert resp.status_code == 200


def test_detail_view_renders(admin_client, sr_subnet):
    res = _reservation(sr_subnet, "10.20.0.81/24", "AA:BB:CC:DD:EE:81")
    resp = admin_client.get(res.get_absolute_url())
    assert resp.status_code == 200


def test_api_create(api_client, sr_subnet):
    from django.urls import reverse

    from netbox_dhcp_kea_plugin.models import StaticReservation

    ip = _ip("10.20.0.82/24")
    mac = _mac("AA:BB:CC:DD:EE:82")
    url = reverse("plugins-api:netbox_dhcp_kea_plugin-api:staticreservation-list")
    resp = api_client.post(
        url,
        {"subnet": sr_subnet.pk, "ip_address": ip.pk, "mac_address": mac.pk, "hostname": "host1"},
        format="json",
    )
    assert resp.status_code == 201, resp.data
    assert StaticReservation.objects.filter(ip_address=ip, mac_address=mac).exists()


def test_subnet_reservations_tab_renders_with_explicit(admin_client, sr_subnet):
    from django.urls import reverse

    _reservation(sr_subnet, "10.20.0.85/24", "AA:BB:CC:DD:EE:85", hostname="nvr-1")
    url = reverse("plugins:netbox_dhcp_kea_plugin:subnet_reservations", kwargs={"pk": sr_subnet.pk})
    resp = admin_client.get(url)
    assert resp.status_code == 200
    assert b"aa:bb:cc:dd:ee:85" in resp.content.lower()  # explicit MAC rendered


# ---------------------------------------------------------------------------
# Form: subnet scope + dynamic IP restriction
# ---------------------------------------------------------------------------


def test_form_subnet_is_plugin_subnets(sr_subnet):
    from netbox_dhcp_kea_plugin.forms import StaticReservationForm
    from netbox_dhcp_kea_plugin.models import Subnet

    form = StaticReservationForm()
    assert form.fields["subnet"].queryset.model is Subnet


def test_form_ip_picker_points_at_subnet_endpoint(sr_subnet):
    from django.urls import reverse

    from netbox_dhcp_kea_plugin.forms import StaticReservationForm

    form = StaticReservationForm()
    assert form.fields["ip_address"].widget.attrs.get("data-url") == reverse(
        "plugins-api:netbox_dhcp_kea_plugin-api:subnet-ip-choices"
    )


def test_subnet_ip_choices_endpoint_filters_to_prefix(api_client, sr_subnet):
    from django.urls import reverse

    _ip("10.20.0.5/24")  # inside 10.20.0.0/24
    _ip("10.99.0.5/24")  # outside
    url = reverse("plugins-api:netbox_dhcp_kea_plugin-api:subnet-ip-choices")
    resp = api_client.get(url, {"subnet_id": sr_subnet.pk})
    assert resp.status_code == 200
    addrs = {r["address"] for r in resp.data["results"]}
    assert "10.20.0.5/24" in addrs
    assert "10.99.0.5/24" not in addrs


def test_subnet_ip_choices_empty_without_subnet_id(api_client, sr_subnet):
    from django.urls import reverse

    _ip("10.20.0.6/24")
    url = reverse("plugins-api:netbox_dhcp_kea_plugin-api:subnet-ip-choices")
    resp = api_client.get(url)
    assert resp.status_code == 200
    assert resp.data["count"] == 0


# ---------------------------------------------------------------------------
# Allocate-and-reserve provisioning endpoint
# ---------------------------------------------------------------------------


@pytest.fixture
def provision_subnet(db, dhcp_server_factory):
    """A subnet where every available address is reservable
    (``reservations_out_of_pool=False``), so allocation has capacity."""
    from ipam.models import Prefix

    from netbox_dhcp_kea_plugin.models import Subnet

    return Subnet.objects.create(
        prefix=Prefix.objects.create(prefix="10.30.0.0/24"),
        server=dhcp_server_factory(),
        valid_lifetime=3600,
        max_lifetime=7200,
        routers_option_offset=1,  # .1 is the gateway → never allocated
        reservations_out_of_pool=False,
    )


def _provision_url():
    from django.urls import reverse

    return reverse("plugins-api:netbox_dhcp_kea_plugin-api:staticreservation-provision")


def test_provision_allocates_and_reserves(api_client, provision_subnet):
    from netbox_dhcp_kea_plugin.models import StaticReservation

    resp = api_client.post(
        _provision_url(),
        {"subnet": provision_subnet.pk, "mac_address": "AA:BB:CC:00:00:01", "source": "nac"},
        format="json",
    )
    assert resp.status_code == 201, resp.data
    # .1 is the gateway and is skipped → lowest allocatable is .2
    assert resp.data["ip_address"]["address"] == "10.30.0.2/24"
    sr = StaticReservation.objects.get(pk=resp.data["id"])
    assert sr.source == "nac"
    assert sr.last_synced is not None


def test_provision_skips_gateway_and_increments(api_client, provision_subnet):
    a = api_client.post(
        _provision_url(),
        {"subnet": provision_subnet.pk, "mac_address": "AA:BB:CC:00:00:0A"},
        format="json",
    )
    b = api_client.post(
        _provision_url(),
        {"subnet": provision_subnet.pk, "mac_address": "AA:BB:CC:00:00:0B"},
        format="json",
    )
    assert a.data["ip_address"]["address"] == "10.30.0.2/24"
    assert b.data["ip_address"]["address"] == "10.30.0.3/24"


def test_provision_idempotent_external_id(api_client, provision_subnet):
    from netbox_dhcp_kea_plugin.models import StaticReservation

    body = {
        "subnet": provision_subnet.pk,
        "mac_address": "AA:BB:CC:00:00:02",
        "external_id": "nac-42",
    }
    r1 = api_client.post(_provision_url(), body, format="json")
    assert r1.status_code == 201
    r2 = api_client.post(_provision_url(), body, format="json")
    assert r2.status_code == 200  # idempotent retry, not a new allocation
    assert r2.data["id"] == r1.data["id"]
    assert StaticReservation.objects.filter(external_id="nac-42").count() == 1


def test_provision_duplicate_mac_conflict(api_client, provision_subnet):
    body = {"subnet": provision_subnet.pk, "mac_address": "AA:BB:CC:00:00:03"}
    assert api_client.post(_provision_url(), body, format="json").status_code == 201
    resp = api_client.post(_provision_url(), body, format="json")
    assert resp.status_code == 400


def test_provision_no_out_of_pool_capacity(api_client, sr_subnet):
    # Enforce out-of-pool with no IP Range defined → the pool spans the whole
    # usable space, so there is nothing out-of-pool to allocate.
    sr_subnet.reservations_out_of_pool = True
    sr_subnet.save()
    resp = api_client.post(
        _provision_url(),
        {"subnet": sr_subnet.pk, "mac_address": "AA:BB:CC:00:00:04"},
        format="json",
    )
    assert resp.status_code == 400
