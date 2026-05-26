"""DHCPServer.service auto-linking — regression tests for the bug where the
back-reference FK was left null when a matching Application Service already
existed (or had been nulled via SET_NULL).
"""

import pytest


pytestmark = pytest.mark.django_db


@pytest.fixture
def vm_ip(db):
    """An IPAddress assigned to a VM interface (so it has a parent_object)."""
    from ipam.models import IPAddress
    from virtualization.models import Cluster, ClusterType, VirtualMachine, VMInterface

    ct = ClusterType.objects.create(name="svc-ct", slug="svc-ct")
    cluster = Cluster.objects.create(name="svc-cluster", type=ct)
    vm = VirtualMachine.objects.create(name="v-dhcp-test", cluster=cluster)
    iface = VMInterface.objects.create(virtual_machine=vm, name="eth0")
    return IPAddress.objects.create(address="10.50.0.10/24", assigned_object=iface)


@pytest.fixture
def service_template(db):
    from ipam.models import ServiceTemplate

    return ServiceTemplate.objects.create(name="KEA DHCP Server", protocol="udp", ports=[67, 68])


def _make_server(name, vm_ip, service_template):
    from netbox_dhcp_kea_plugin.models import DHCPServer

    return DHCPServer.objects.create(
        name=name,
        ip_address=vm_ip,
        service_template=service_template,
        status="active",
    )


def test_save_creates_and_links_service(vm_ip, service_template):
    server = _make_server("dhcp-create", vm_ip, service_template)
    server.refresh_from_db()
    assert server.service is not None
    assert server.service.name == "KEA DHCP Server"


def test_save_links_preexisting_service(vm_ip, service_template):
    """Regression: a matching Service already exists → FK must be linked,
    not left null, and no duplicate created."""
    from django.contrib.contenttypes.models import ContentType
    from ipam.models import Service

    parent = vm_ip.assigned_object.parent_object
    existing = Service.objects.create(
        parent_object_type=ContentType.objects.get_for_model(parent),
        parent_object_id=parent.pk,
        name=service_template.name,
        protocol=service_template.protocol,
        ports=service_template.ports,
    )

    server = _make_server("dhcp-preexisting", vm_ip, service_template)
    server.refresh_from_db()

    assert server.service_id == existing.pk
    assert Service.objects.filter(name=service_template.name, parent_object_id=parent.pk).count() == 1


def test_resave_relinks_after_set_null(vm_ip, service_template):
    """Deleting the Service nulls the FK (SET_NULL); re-saving must re-link."""
    from ipam.models import Service

    server = _make_server("dhcp-setnull", vm_ip, service_template)
    server.refresh_from_db()
    assert server.service is not None

    server.service.delete()
    server.refresh_from_db()
    assert server.service is None  # SET_NULL fired

    server.save()
    server.refresh_from_db()
    assert server.service is not None
    assert Service.objects.filter(name=service_template.name).count() == 1


def test_repeated_saves_are_idempotent(vm_ip, service_template):
    from ipam.models import Service

    server = _make_server("dhcp-idem", vm_ip, service_template)
    for _ in range(3):
        server.save()
    server.refresh_from_db()

    assert server.service is not None
    parent = vm_ip.assigned_object.parent_object
    assert Service.objects.filter(name=service_template.name, parent_object_id=parent.pk).count() == 1


def test_repair_command_links_null_fk(vm_ip, service_template):
    """The management command links a pre-existing Service for a server whose
    FK is null, without creating duplicates."""
    from django.contrib.contenttypes.models import ContentType
    from django.core.management import call_command
    from ipam.models import Service

    server = _make_server("dhcp-repair", vm_ip, service_template)

    # Force the broken state: a matching Service exists but the FK is null.
    parent = vm_ip.assigned_object.parent_object
    service = Service.objects.get(
        parent_object_type=ContentType.objects.get_for_model(parent),
        parent_object_id=parent.pk,
        name=service_template.name,
    )
    type(server).objects.filter(pk=server.pk).update(service=None)
    server.refresh_from_db()
    assert server.service is None

    call_command("repair_dhcp_services")

    server.refresh_from_db()
    assert server.service_id == service.pk
    assert Service.objects.filter(name=service_template.name, parent_object_id=parent.pk).count() == 1
