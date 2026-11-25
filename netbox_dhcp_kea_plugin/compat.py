"""Ports of NetBox's ``Service`` and ``ServiceTemplate``.

NetBox 4.7 replaced their ``protocol`` and ``ports`` columns with a single
``port_mappings`` list of ``"protocol/port"`` strings, keeping ``protocol`` and
``ports`` only as read-only properties derived from it. Reading them works;
filtering on or writing them fails, with a ``FieldError`` in a query and an
error on assignment.
"""


def service_port_fields(protocol, ports):
    """Field values for a Service or ServiceTemplate listening on ``ports``."""
    return {"port_mappings": [f"{protocol}/{port}" for port in ports]}


def port_fields_from(template):
    """Field values that copy ``template``'s ports onto a new Service."""
    return {"port_mappings": list(template.port_mappings)}


def find_service_for_template(parent, template):
    """Return ``parent``'s Service built from ``template``, or None.

    A match has the template's name and protocol. The protocol is compared in
    Python because it is derived from ``port_mappings``, so a query cannot
    filter on it.
    """
    from django.contrib.contenttypes.models import ContentType
    from ipam.models import Service

    candidates = Service.objects.filter(
        parent_object_type=ContentType.objects.get_for_model(parent),
        parent_object_id=parent.pk,
        name=template.name,
    )
    return next((s for s in candidates if s.protocol == template.protocol), None)
