"""Every page and tab of every plugin model renders.

The plugin's pages are declared with NetBox's layouts, panels and child
views. This walks NetBox's view registry, so a page added or converted later
is covered without listing it here.
"""

import base64

import pytest
from django.contrib.auth import get_user_model
from django.urls import NoReverseMatch, reverse
from netaddr import IPNetwork
from netbox.registry import registry
from utilities.views import get_viewname

pytestmark = pytest.mark.django_db

APP_LABEL = "netbox_dhcp_kea_plugin"


@pytest.fixture
def every_object(dhcp_server, option_data, client_class, subnet_factory):
    """One object of every plugin model, wired together so related panels have rows."""
    from dcim.models import MACAddress
    from ipam.models import IPAddress, IPRange

    from netbox_dhcp_kea_plugin import models
    from tests.test_ddns_models import _make_zone

    hook = models.Hook.objects.create(
        name="ui-hook", library_name="libdhcp_lease_cmds.so", allowed_processes=["kea-dhcp4"]
    )
    group = models.HookGroup.objects.create(name="ui-group", library_path="/usr/lib/kea/hooks")
    group.hooks.add(hook)
    group.servers.add(dhcp_server)

    ha = models.DHCPHARelationship.objects.create(name="ui-ha", mode="hot-standby")
    subnet = subnet_factory(server=dhcp_server)
    network = IPNetwork(str(subnet.prefix.prefix))
    ip_range = IPRange.objects.create(
        start_address=IPNetwork(f"{network[10]}/24"),
        end_address=IPNetwork(f"{network[20]}/24"),
    )
    pool = models.SubnetPool.objects.create(subnet=subnet, ip_range=ip_range)
    reservation = models.StaticReservation.objects.create(
        subnet=subnet,
        ip_address=IPAddress.objects.create(address=f"{network[30]}/24"),
        mac_address=MACAddress.objects.create(mac_address="02:00:00:00:00:30"),
    )

    stork = models.StorkServer.objects.create(
        name="ui-stork",
        ip_address=IPAddress.objects.create(address="10.250.0.10/24"),
        rest_port=8080,
        rest_base_url="/",
        endpoint_type="ip",
    )
    agents = models.StorkAgentGroup.objects.create(
        name="ui-agents", stork_server=stork, operating_mode="both", agent_port=8081
    )

    policy = models.DDNSPolicy.objects.create(name="ui-policy", ddns_qualifying_suffix="ui.example.org")
    subnet.ddns_policy = policy
    subnet.save()
    key = models.TSIGKey.objects.create(
        name="ui-key.",
        algorithm="HMAC-SHA256",
        secret_backend="plaintext",
        secret_plaintext=base64.b64encode(b"x" * 32).decode(),
    )
    daemon = models.D2Daemon.objects.create(name="ui-d2")
    dhcp_server.d2_daemon = daemon
    dhcp_server.save()

    from netbox_dns.choices import RecordTypeChoices
    from netbox_dns.models import NameServer, Record

    nameserver = NameServer.objects.get_or_create(name="ns1.ui.example.org")[0]
    zone = _make_zone("ui.example.org")
    zone.nameservers.add(nameserver)
    Record.objects.get_or_create(zone=zone, name="ns1", type=RecordTypeChoices.A, value="192.0.2.80")
    domain = models.DDNSDomain.objects.create(zone=zone, tsig_key=key)
    override = models.DDNSServerOverride.objects.create(ddns_domain=domain, nameserver=nameserver, port=5353)

    return [
        hook,
        group,
        option_data.definition.vendor_option_space,
        option_data.definition,
        option_data,
        dhcp_server,
        client_class,
        subnet,
        pool,
        reservation,
        ha,
        stork,
        agents,
        policy,
        key,
        daemon,
        domain,
        override,
    ]


def _detail_view_names(model):
    """Every registered object-level view of a model, e.g. "", "edit", "kea_config"."""
    views = registry["views"][APP_LABEL].get(model._meta.model_name, [])
    return [view["name"] for view in views if view["detail"]]


# Query parameters an embedded table URL carries that are not filters.
_NON_FILTER_PARAMS = {"embedded", "return_url", "include_columns", "exclude_columns"}


def _embedded_table_problems(client, page_url, content):
    """Fetch every HTMX-embedded table on a page and check its filters exist.

    NetBox list views ignore unknown query parameters, so a misspelt filter
    would quietly list every object instead of the related ones.
    """
    import html
    import re
    from urllib.parse import parse_qsl, urlsplit

    from django.urls import resolve

    problems = []
    tables = re.findall(r'hx-get="([^"]+embedded=True[^"]*)"', content)
    for raw in tables:
        url = html.unescape(raw)
        parts = urlsplit(url)
        filterset = resolve(parts.path).func.view_class.filterset
        known = set(filterset.base_filters) | {"q"}
        for key, _value in parse_qsl(parts.query):
            if key not in _NON_FILTER_PARAMS and key not in known:
                problems.append(f"{page_url}: table {parts.path} has no filter '{key}'")
        resp = client.get(url, HTTP_HX_REQUEST="true")
        if resp.status_code != 200:
            problems.append(f"{page_url}: table {url} → {resp.status_code}")
    return problems, len(tables)


def test_every_page_and_tab_renders(every_object, client):
    client.force_login(get_user_model().objects.create_superuser(username="ui-pages", password="x"))

    failures = []
    rendered = 0
    embedded = 0
    for obj in every_object:
        for name in _detail_view_names(type(obj)):
            try:
                url = reverse(get_viewname(obj, name or None), kwargs={"pk": obj.pk})
            except NoReverseMatch:
                # Registered but not routed, e.g. a feature flag is off.
                continue
            resp = client.get(url)
            rendered += 1
            # Deleting a still-referenced object redirects back with a message.
            if name == "delete" and resp.status_code == 302:
                continue
            if resp.status_code != 200:
                failures.append(f"{url} → {resp.status_code}")
                continue
            problems, count = _embedded_table_problems(client, url, resp.content.decode())
            failures += problems
            embedded += count

    assert not failures, "\n".join(failures)
    assert rendered > len(every_object)
    assert embedded > 0


def test_every_list_renders(every_object, client):
    client.force_login(get_user_model().objects.create_superuser(username="ui-lists", password="x"))

    failures = []
    for obj in every_object:
        try:
            url = reverse(get_viewname(obj, "list"))
        except NoReverseMatch:
            continue
        resp = client.get(url)
        if resp.status_code != 200:
            failures.append(f"{url} → {resp.status_code}")

    assert not failures, "\n".join(failures)
