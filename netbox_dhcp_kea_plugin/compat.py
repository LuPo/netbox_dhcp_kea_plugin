"""Compatibility with the NetBox versions the plugin supports.

NetBox 4.7 replaced the ``protocol`` and ``ports`` columns of ``Service`` and
``ServiceTemplate`` with a single ``port_mappings`` list of ``"protocol/port"``
strings, keeping ``protocol`` and ``ports`` only as read-only properties derived
from it. Reading them works on every version; filtering on or writing them fails
from 4.7 on, with a ``FieldError`` in a query and an error on assignment.
"""

from functools import cache


@cache
def has_port_mappings() -> bool:
    """Whether this NetBox stores service ports as ``port_mappings`` (4.7+)."""
    from ipam.models import ServiceTemplate

    return any(field.name == "port_mappings" for field in ServiceTemplate._meta.get_fields())


def service_port_fields(protocol, ports):
    """Field values for a Service or ServiceTemplate listening on ``ports``."""
    if has_port_mappings():
        return {"port_mappings": [f"{protocol}/{port}" for port in ports]}
    return {"protocol": protocol, "ports": list(ports)}


def port_fields_from(template):
    """Field values that copy ``template``'s ports onto a new Service."""
    if has_port_mappings():
        return {"port_mappings": list(template.port_mappings)}
    return {"protocol": template.protocol, "ports": list(template.ports)}


def find_service_for_template(parent, template):
    """Return ``parent``'s Service built from ``template``, or None.

    A match has the template's name and protocol. The protocol is compared in
    Python rather than in the query because it is a column before NetBox 4.7 and
    a computed property from 4.7 on; reading it works on both.
    """
    from django.contrib.contenttypes.models import ContentType
    from ipam.models import Service

    candidates = Service.objects.filter(
        parent_object_type=ContentType.objects.get_for_model(parent),
        parent_object_id=parent.pk,
        name=template.name,
    )
    return next((s for s in candidates if s.protocol == template.protocol), None)
