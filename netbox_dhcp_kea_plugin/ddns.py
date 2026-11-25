"""Derive D2 (kea-dhcp-ddns) domains from what a DHCP server hands out.

D2 never sees subnets. kea-dhcp4 builds each lease's forward name from the
hostname and the ``ddns-qualifying-suffix`` in effect, and its reverse name
from the address, and D2 picks the domain whose zone is the longest match of
each name. So a server needs:

- a forward domain for every qualifying suffix its subnets and pools send
  updates with, and
- a reverse domain for every reverse zone its subnets' prefixes overlap,

plus whatever it is told to always include. Nothing else — in particular not
another site's zones or keys.

Which ``DDNSDomain`` row is used for a zone depends on the server: one limited
to the server wins over one limited to its HA relationship, which wins over a
global one.
"""

import dataclasses

from django.db.models import Q

# How many subnets or pools a message names before summarising the rest.
_MAX_NAMED = 3


@dataclasses.dataclass
class DerivedDomain:
    """A domain a server needs, and what brought it in."""

    domain: object
    reasons: list = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class DerivedDDNS:
    """The outcome of deriving one server's D2 domains.

    ``errors`` would make the rendered configuration fail to load;
    ``warnings`` describe updates D2 will drop because no domain covers them.
    """

    enabled: bool = False
    domains: list = dataclasses.field(default_factory=list)
    errors: list = dataclasses.field(default_factory=list)
    warnings: list = dataclasses.field(default_factory=list)

    @property
    def domain_list(self):
        return [entry.domain for entry in self.domains]


def _named(items):
    """'a, b and c' — or 'a, b, c and 4 more' past a few."""
    items = list(items)
    if len(items) > _MAX_NAMED:
        shown = ", ".join(items[:_MAX_NAMED])
        return f"{shown} and {len(items) - _MAX_NAMED} more"
    if len(items) > 1:
        return f"{', '.join(items[:-1])} and {items[-1]}"
    return items[0] if items else ""


def _first_set(policies, field):
    """The first value along a pool → subnet → server chain that is set.

    Mirrors KEA's own inheritance: None and "" mean "not set here".
    """
    for policy in policies:
        if policy is None:
            continue
        value = getattr(policy, field)
        if value is not None and value != "":
            return value
    return None


def _normalize_name(name):
    return (name or "").rstrip(".").lower()


def _overlaps(network_a, network_b):
    return network_a.version == network_b.version and network_a.first <= network_b.last and network_b.first <= network_a.last


def applicable_domains(server):
    """The DDNS domain each zone uses on this server: narrowest scope wins.

    Returns a list of ``DDNSDomain``, at most one per zone.
    """
    from netbox_dhcp_kea_plugin.models import DDNSDomain

    scope = Q(dhcp_server=server) | Q(dhcp_server__isnull=True, ha_relationship__isnull=True)
    if server.ha_relationship_id:
        scope |= Q(ha_relationship_id=server.ha_relationship_id)

    candidates = (
        DDNSDomain.objects.filter(scope)
        .select_related("zone", "tsig_key", "dhcp_server", "ha_relationship")
        .prefetch_related("zone__nameservers")
    )
    chosen = {}
    for domain in candidates:
        current = chosen.get(domain.zone_id)
        if current is None or domain.scope_rank < current.scope_rank:
            chosen[domain.zone_id] = domain
    return list(chosen.values())


def _update_sources(server):
    """Every subnet and pool that sends updates, with its qualifying suffix.

    Returns ``(suffixes, prefixes)``: ``suffixes`` maps a normalised suffix
    ("" when none is set) to the labels of the subnets and pools using it;
    ``prefixes`` lists ``(label, network)`` for subnets with any updates.
    Only IPv4 subnets count, because only they are rendered.
    """
    server_policy = server.effective_ddns_policy
    subnets = (
        server.get_effective_subnet_items()
        .select_related("prefix", "ddns_policy")
        .prefetch_related("subnet_pools__ddns_policy", "subnet_pools__ip_range")
    )

    suffixes = {}
    prefixes = []
    for subnet in subnets:
        network = subnet.prefix.prefix
        if network.version != 4:
            continue
        label = f"subnet {network}"
        scopes = [(label, [subnet.ddns_policy, server_policy])]
        for pool in subnet.subnet_pools.all():
            scopes.append((f"pool {pool}", [pool.ddns_policy, subnet.ddns_policy, server_policy]))

        sends_any = False
        for scope_label, chain in scopes:
            # KEA's default for ddns-send-updates is true.
            send = _first_set(chain, "ddns_send_updates")
            if send is False:
                continue
            sends_any = True
            suffix = _normalize_name(_first_set(chain, "ddns_qualifying_suffix"))
            suffixes.setdefault(suffix, []).append(scope_label)
        if sends_any:
            prefixes.append((label, network))
    return suffixes, prefixes


def derive_for_server(server):
    """Work out the D2 domains ``server`` needs. Returns ``DerivedDDNS``."""
    result = DerivedDDNS()
    if server.effective_d2_daemon is None or not server._effective_ddns_field("ddns_enable_updates"):
        return result
    result.enabled = True

    domains = applicable_domains(server)
    forward = [d for d in domains if not d.is_reverse]
    reverse = [d for d in domains if d.is_reverse]
    needed = {}

    def bring_in(domain, reason):
        needed.setdefault(domain.pk, DerivedDomain(domain)).reasons.append(reason)

    suffixes, prefixes = _update_sources(server)

    for suffix, sources in sorted(suffixes.items()):
        if not suffix:
            result.warnings.append(
                f"{_named(sources)} send updates with no qualifying suffix, so the names are whatever "
                "clients send. Add an always-included DDNS domain for each zone those names fall in."
            )
            continue
        covering = [d for d in forward if suffix == d.zone_name or suffix.endswith(f".{d.zone_name}")]
        if not covering:
            result.warnings.append(
                f"No DDNS domain covers '{suffix}', the qualifying suffix of {_named(sources)}. D2 will "
                "drop the forward updates for those names."
            )
            continue
        longest = max(len(d.zone_name) for d in covering)
        for domain in (d for d in covering if len(d.zone_name) == longest):
            bring_in(domain, f"qualifying suffix '{suffix}' ({_named(sources)})")

    for label, network in prefixes:
        covering = [d for d in reverse if d.zone.arpa_network is not None and _overlaps(d.zone.arpa_network, network)]
        if not covering:
            result.warnings.append(f"No reverse DDNS domain covers {label}. D2 will drop its PTR updates.")
            continue
        for domain in covering:
            bring_in(domain, label)

    for domain in domains:
        if domain.always_include:
            bring_in(domain, "always included")

    result.domains = sorted(needed.values(), key=lambda entry: (entry.domain.is_reverse, entry.domain.zone_name))
    result.errors.extend(_duplicate_name_errors(result.domain_list))
    return result


def _duplicate_name_errors(domains, context=""):
    """D2 refuses two domains with one name — e.g. the same zone in two views."""
    by_name = {}
    for domain in domains:
        by_name.setdefault((domain.is_reverse, domain.zone_name), []).append(domain)
    errors = []
    for (_reverse, name), group in sorted(by_name.items()):
        if len(group) > 1:
            entries = _named([f"{d.zone} ({d.scope_label})" for d in group])
            errors.append(
                f"{context}'{name}' would be served by {len(group)} DDNS domains: {entries}. "
                "kea-dhcp-ddns refuses two domains with the same name; keep one."
            )
    return errors


def merge_for_daemon(daemon, derived_by_server):
    """Combine ``(server, DerivedDDNS)`` pairs for ``daemon`` into one domain list.

    Returns ``(domains, errors)``. Every server's own errors are carried,
    named. For a remote daemon, which is one process, two servers that use
    different entries for the same zone are an error as well; a local
    daemon's hosts are separate processes, so they may.
    """
    domains = {}
    errors = []
    for server, derived in derived_by_server:
        errors.extend(f"{server}: {error}" for error in derived.errors)
        for domain in derived.domain_list:
            domains.setdefault(domain.pk, domain)
    ordered = sorted(domains.values(), key=lambda d: (d.is_reverse, d.zone_name))
    if not daemon.is_local:
        errors.extend(_duplicate_name_errors(ordered, context="Shared D2: "))
    return ordered, errors


@dataclasses.dataclass
class DerivedGroup:
    """Servers shown together: an HA relationship's members, or one server.

    HA peers serve the same subnets, so they normally derive the same domains
    and ``variants`` holds one entry for all of them. An entry limited to one
    peer makes the peers differ, and then each distinct result is its own
    variant, listing the servers that share it.
    """

    ha_relationship: object
    servers: list
    variants: list  # [(servers, DerivedDDNS)]

    @property
    def domain_count(self):
        return len({domain.pk for _servers, derived in self.variants for domain in derived.domain_list})

    @property
    def warning_count(self):
        return sum(len(derived.warnings) for _servers, derived in self.variants)

    @property
    def error_count(self):
        return sum(len(derived.errors) for _servers, derived in self.variants)


def _signature(derived):
    """What makes two servers' results the same for display."""
    return (
        tuple((entry.domain.pk, tuple(entry.reasons)) for entry in derived.domains),
        tuple(derived.warnings),
        tuple(derived.errors),
    )


def group_by_relationship(derived_by_server):
    """Fold ``(server, DerivedDDNS)`` pairs into ``DerivedGroup``s.

    Servers in one HA relationship share a group; a server outside any has a
    group of its own. Groups keep the order their first server came in.
    """
    groups = {}
    for server, derived in derived_by_server:
        key = ("ha", server.ha_relationship_id) if server.ha_relationship_id else ("server", server.pk)
        group = groups.get(key)
        if group is None:
            group = groups[key] = DerivedGroup(server.ha_relationship if server.ha_relationship_id else None, [], [])
        group.servers.append(server)
        signature = _signature(derived)
        for servers, existing in group.variants:
            if _signature(existing) == signature:
                servers.append(server)
                break
        else:
            group.variants.append(([server], derived))
    return list(groups.values())
