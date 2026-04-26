import ipaddress as ipaddress_module

from dcim.choices import DeviceStatusChoices
from dcim.models import Manufacturer
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from ipam.models import IPAddress, IPRange, Prefix, Service, ServiceTemplate
from netbox.models import NetBoxModel


class Hook(NetBoxModel):
    """KEA Hook Library configuration.

    Represents a single hook library that can be loaded by KEA processes.
    Standard hooks are pre-populated from KEA documentation; custom hooks
    can be created by users.
    """

    # Process type choices - which KEA processes can load this hook
    PROCESS_CHOICES = (
        ("kea-ctrl-agent", "KEA Control Agent"),
        ("kea-dhcp4", "KEA DHCPv4"),
        ("kea-dhcp6", "KEA DHCPv6"),
        ("kea-dhcp-ddns", "KEA DHCP-DDNS"),
    )

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Human-readable name for this hook library",
    )
    library_name = models.CharField(
        max_length=255,
        help_text="Library filename (e.g., libdhcp_lease_cmds.so) or full path for custom hooks",
    )
    description = models.TextField(
        blank=True,
        help_text="Description of what this hook library does",
    )
    is_standard = models.BooleanField(
        default=False,
        help_text="Whether this is a standard KEA hook library (pre-populated, read-only)",
    )
    allowed_processes = ArrayField(
        models.CharField(max_length=20, choices=PROCESS_CHOICES),
        default=list,
        help_text="KEA processes that can load this hook library",
    )
    parameters = models.JSONField(
        blank=True,
        null=True,
        help_text="Hook library parameters as JSON (will be passed to KEA configuration)",
    )

    class Meta:
        ordering = ("name",)
        verbose_name = "Hook"
        verbose_name_plural = "Hooks"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_dhcp_kea_plugin:hook", args=[self.pk])

    def clean(self):
        super().clean()
        if not self.allowed_processes:
            raise ValidationError({"allowed_processes": "At least one allowed process must be specified."})

    def get_library_path(self, base_path=""):
        """Construct the full library path.

        Args:
            base_path: Optional base path to prepend (from HookGroup.library_path)

        Returns:
            The full library path/filename for KEA configuration
        """
        if base_path:
            # Remove trailing slash from base_path and leading slash from library_name
            base = base_path.rstrip("/")
            lib = self.library_name.lstrip("/")
            return f"{base}/{lib}"
        return self.library_name

    def to_kea_dict(self, base_path=""):
        """Generate the KEA hooks-libraries entry for this hook.

        Args:
            base_path: Optional base path to prepend (from HookGroup.library_path)

        Returns:
            Dictionary suitable for inclusion in KEA hooks-libraries array
        """
        result = {"library": self.get_library_path(base_path)}
        if self.parameters:
            result["parameters"] = self.parameters
        return result


class HookGroup(NetBoxModel):
    """Group of KEA Hook Libraries.

    Hook groups allow organizing hooks together and associating them with
    DHCP servers. The library_path field specifies where hook libraries
    are installed on the target system.
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique name for this hook group",
    )
    description = models.TextField(
        blank=True,
        help_text="Description of this hook group",
    )
    library_path = models.CharField(
        max_length=255,
        blank=True,
        default="/usr/lib64/kea/hooks",
        help_text="Base path where hook libraries are installed (e.g., /usr/lib64/kea/hooks). "
        "Leave empty to use only the library filename.",
    )
    hooks = models.ManyToManyField(
        Hook,
        blank=True,
        related_name="hook_groups",
        help_text="Hooks included in this group",
    )
    servers = models.ManyToManyField(
        "DHCPServer",
        blank=True,
        related_name="hook_groups",
        help_text="DHCP servers that use this hook group",
    )

    class Meta:
        ordering = ("name",)
        verbose_name = "Hook Group"
        verbose_name_plural = "Hook Groups"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_dhcp_kea_plugin:hookgroup", args=[self.pk])

    def get_hooks_for_process(self, process):
        """Get hooks that are valid for a specific KEA process.

        Args:
            process: Process identifier (e.g., 'kea-dhcp4', 'kea-dhcp6')

        Returns:
            QuerySet of Hook objects valid for the specified process
        """
        return self.hooks.filter(allowed_processes__contains=[process])

    def to_kea_hooks_libraries(self, process):
        """Generate KEA hooks-libraries array for a specific process.

        Args:
            process: Process identifier (e.g., 'kea-dhcp4', 'kea-dhcp6')

        Returns:
            List of dictionaries suitable for KEA hooks-libraries configuration
        """
        hooks = self.get_hooks_for_process(process)
        return [hook.to_kea_dict(self.library_path) for hook in hooks]


def get_model_default(model_name, field_name, fallback=None):
    """Return a default value from plugin config ``model_defaults.<Model>.<field>``."""
    from netbox.plugins.utils import get_plugin_config

    model_defaults = get_plugin_config("netbox_dhcp_kea_plugin", "model_defaults") or {}
    return model_defaults.get(model_name, {}).get(field_name, fallback)


def get_default_reservations_global():
    return get_model_default("Subnet", "reservations_global", False)


def get_default_reservations_in_subnet():
    return get_model_default("Subnet", "reservations_in_subnet", True)


def get_default_reservations_out_of_pool():
    return get_model_default("Subnet", "reservations_out_of_pool", True)


def get_default_reservations_only():
    return get_model_default("Subnet", "reservations_only", False)


class DHCPServer(NetBoxModel):
    """ISC KEA DHCP Server instance"""

    HA_ROLE_CHOICES = (
        ("primary", "Primary"),
        ("secondary", "Secondary"),
        ("standby", "Standby"),
        ("backup", "Backup"),
    )

    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=200, blank=True)
    ip_address = models.ForeignKey(
        IPAddress,
        on_delete=models.PROTECT,
        related_name="dhcp_servers",
        help_text="IP address of the DHCP server (from NetBox IPAM)",
    )
    status = models.CharField(
        verbose_name=_("status"),
        max_length=50,
        choices=DeviceStatusChoices,
        default=DeviceStatusChoices.STATUS_ACTIVE,
        help_text="Operational status of this DHCP server",
    )
    service_template = models.ForeignKey(
        ServiceTemplate,
        on_delete=models.PROTECT,
        related_name="dhcp_servers",
        help_text="Application service template to create a service on the assigned object",
    )
    option_data = models.ManyToManyField(
        "OptionData",
        blank=True,
        related_name="dhcp_servers",
        help_text="Global option data for this DHCP server",
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dhcp_servers",
        help_text="Auto-created Application Service (managed automatically)",
    )

    # Global KEA reservation mode defaults (subnets can override per-subnet)
    reservations_global = models.BooleanField(
        default=get_default_reservations_global,
        verbose_name="Reservations Global",
        help_text="Default: look for host reservations in the global scope (subnets can override)",
    )
    reservations_in_subnet = models.BooleanField(
        default=get_default_reservations_in_subnet,
        verbose_name="Reservations In-Subnet",
        help_text="Default: look for host reservations within subnets (subnets can override)",
    )
    reservations_out_of_pool = models.BooleanField(
        default=get_default_reservations_out_of_pool,
        verbose_name="Reservations Out-of-Pool",
        help_text="Default: exclude reserved addresses from dynamic pool allocation (subnets can override)",
    )

    # HA-related fields (optional - only set if server is part of an HA relationship)
    ha_relationship = models.ForeignKey(
        "DHCPHARelationship",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="servers",
        help_text="The HA relationship this server belongs to",
    )
    ha_role = models.CharField(
        max_length=20,
        choices=HA_ROLE_CHOICES,
        blank=True,
        help_text="Role in the HA relationship",
    )
    ha_address = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="HA Address",
        help_text="IP address for HA communication (e.g., 192.168.1.1)",
    )
    ha_port = models.PositiveIntegerField(
        default=8080,
        null=True,
        blank=True,
        verbose_name="HA Port",
        help_text="Port for HA communication (default: 8080)",
    )
    ha_tls = models.BooleanField(
        default=False,
        verbose_name="HA TLS",
        help_text="Use TLS (HTTPS) for HA communication",
    )
    ha_auto_failover = models.BooleanField(default=True, help_text="Enable automatic failover for this server in HA")
    ha_basic_auth_user = models.CharField(
        max_length=100,
        blank=True,
        help_text="Username for HTTP basic authentication in HA (optional)",
    )
    ha_basic_auth_password = models.CharField(
        max_length=100,
        blank=True,
        help_text="Password for HTTP basic authentication in HA (optional)",
    )
    stork_agent_group = models.ForeignKey(
        "StorkAgentGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="servers",
        help_text="Stork agent group configuration for this DHCP server",
    )
    d2_daemon = models.ForeignKey(
        "D2Daemon",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="servers",
        help_text=(
            "D2 daemon this server forwards NCRs to. Ignored when the server "
            "is in an HA relationship with the field set."
        ),
    )
    ddns_enable_updates = models.BooleanField(
        default=True,
        help_text="Globally enable DDNS updates on this DHCP server (dhcp-ddns.enable-updates)",
    )
    ddns_sender_ip = models.CharField(
        max_length=45,
        blank=True,
        default="",
        help_text="Source IP the DHCP server uses to send NCRs (optional)",
    )
    ddns_sender_port = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Source port the DHCP server uses to send NCRs (optional)",
    )
    ddns_policy = models.ForeignKey(
        "DDNSPolicy",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="servers",
        help_text="Server-level DDNS policy (ddns-* tunables)",
    )

    # Control Socket
    CTRL_SOCKET_TYPE_CHOICES = (
        ("", "Disabled"),
        ("http", "HTTP"),
        ("unix", "Unix"),
        ("both", "HTTP + Unix"),
    )

    ctrl_socket_type = models.CharField(
        max_length=10,
        choices=CTRL_SOCKET_TYPE_CHOICES,
        blank=True,
        default="",
        verbose_name="Control socket type",
        help_text="Type of control socket to enable for this KEA server",
    )
    ctrl_socket_http_address = models.CharField(
        max_length=255,
        default="127.0.0.1",
        blank=True,
        verbose_name="HTTP socket address",
        help_text="IP address for the HTTP control socket (e.g., 127.0.0.1)",
    )
    ctrl_socket_http_port = models.PositiveIntegerField(
        default=8000,
        null=True,
        blank=True,
        verbose_name="HTTP socket port",
        help_text="Port number for the HTTP control socket (e.g., 8000)",
    )
    ctrl_socket_unix_path = models.CharField(
        max_length=255,
        default="/var/run/kea/kea-dhcp4-socket",
        blank=True,
        verbose_name="Unix socket path",
        help_text="File path for the Unix domain socket (e.g., /var/run/kea/kea-dhcp4-socket)",
    )

    @property
    def ctrl_socket_http_enabled(self):
        """Return True if HTTP control socket is enabled."""
        return self.ctrl_socket_type in ("http", "both")

    @property
    def ctrl_socket_unix_enabled(self):
        """Return True if Unix control socket is enabled."""
        return self.ctrl_socket_type in ("unix", "both")

    class Meta:
        ordering = ("name",)
        verbose_name = "DHCP Server"
        verbose_name_plural = "DHCP Servers"
        constraints = [
            models.UniqueConstraint(
                fields=["ip_address", "service_template"],
                name="unique_ip_address_service_template",
            )
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_dhcp_kea_plugin:dhcpserver", args=[self.pk])

    def get_status_color(self):
        """Return the color associated with the current status for badge display."""
        return DeviceStatusChoices.colors.get(self.status, "secondary")

    def save(self, *args, **kwargs):
        # Check if this is a new instance or service_template changed
        creating = self.pk is None
        old_template = None
        if not creating:
            old_instance = DHCPServer.objects.filter(pk=self.pk).first()
            if old_instance:
                old_template = old_instance.service_template

        super().save(*args, **kwargs)

        # Create service if template is set and IP is assigned to an object
        if self.service_template and self.service_template != old_template:
            self._create_service_from_template()

    def _create_service_from_template(self):
        """Create an Application Service from the template on the parent object."""
        if not self.ip_address or not self.ip_address.assigned_object:
            return  # IP not assigned to anything

        # Get the parent object (device or VM) via the interface's parent_object
        parent_object = self.ip_address.assigned_object.parent_object

        if not parent_object:
            return

        # Check if service already exists
        existing = Service.objects.filter(
            parent_object_type=ContentType.objects.get_for_model(parent_object),
            parent_object_id=parent_object.pk,
            name=self.service_template.name,
            protocol=self.service_template.protocol,
        ).exists()

        if existing:
            return

        # Create the service
        service = Service.objects.create(
            parent_object_type=ContentType.objects.get_for_model(parent_object),
            parent_object_id=parent_object.pk,
            name=self.service_template.name,
            protocol=self.service_template.protocol,
            ports=self.service_template.ports,
            description=self.service_template.description or f"DHCP Server: {self.name}",
        )
        service.ipaddresses.add(self.ip_address)

        # Store reference to the created service
        DHCPServer.objects.filter(pk=self.pk).update(service=service)
        self.service = service

    def delete(self, *args, **kwargs):
        """Delete the auto-created Application Service when DHCPServer is deleted."""
        service_to_delete = self.service
        result = super().delete(*args, **kwargs)
        if service_to_delete:
            service_to_delete.delete()
        return result

    @property
    def ha_url(self):
        """Reconstruct the full HA URL from address, port, and TLS fields.

        Returns:
            str: Full URL like 'http://192.168.1.1:8080/' or empty string if no address set.
        """
        if not self.ha_address:
            return ""
        scheme = "https" if self.ha_tls else "http"
        port = self.ha_port or 8080
        return f"{scheme}://{self.ha_address}:{port}/"

    def clean(self):
        """Validate HA and control socket configuration."""
        super().clean()

        # If ha_relationship is set, ha_role and ha_address are required
        if self.ha_relationship:
            if not self.ha_role:
                raise ValidationError({"ha_role": "HA role is required when server is part of an HA relationship."})
            if not self.ha_address:
                raise ValidationError(
                    {"ha_address": "HA address is required when server is part of an HA relationship."}
                )
            if not self.ha_port:
                raise ValidationError({"ha_port": "HA port is required when server is part of an HA relationship."})

        # Validate ha_address is a valid IP address (when provided)
        if self.ha_address:
            try:
                ipaddress_module.ip_address(self.ha_address)
            except ValueError:
                raise ValidationError({"ha_address": "HA address must be a valid IP address (e.g., 192.168.1.1)."})

        # Validate control socket configuration
        if self.ctrl_socket_http_enabled:
            if not self.ctrl_socket_http_address:
                raise ValidationError(
                    {"ctrl_socket_http_address": "HTTP socket address is required when HTTP control socket is enabled."}
                )
            if not self.ctrl_socket_http_port:
                raise ValidationError(
                    {"ctrl_socket_http_port": "HTTP socket port is required when HTTP control socket is enabled."}
                )

        # Validate ctrl_socket_http_address is a valid IP address (when provided)
        if self.ctrl_socket_http_address:
            try:
                ipaddress_module.ip_address(self.ctrl_socket_http_address)
            except ValueError:
                raise ValidationError(
                    {"ctrl_socket_http_address": "HTTP socket address must be a valid IP address (e.g., 127.0.0.1)."}
                )

        # Validate HA port and HTTP socket port are different (when both are actively in use)
        if (
            self.ctrl_socket_http_enabled
            and self.ha_port
            and self.ctrl_socket_http_port
            and self.ha_port == self.ctrl_socket_http_port
        ):
            raise ValidationError(
                {
                    "ha_port": "HA port must be different from the HTTP control socket port.",
                    "ctrl_socket_http_port": "HTTP control socket port must be different from the HA port.",
                }
            )

        if self.ctrl_socket_unix_enabled:
            if not self.ctrl_socket_unix_path:
                raise ValidationError(
                    {"ctrl_socket_unix_path": "Unix socket path is required when Unix control socket is enabled."}
                )

        # Validate no port conflicts between KEA daemon ports and Stork agent group ports
        if self.stork_agent_group:
            self._validate_stork_port_conflicts()

        # If changing from primary to another role, check for orphaned configs
        if self.pk:
            try:
                old_server = DHCPServer.objects.get(pk=self.pk)
                if old_server.ha_role == "primary" and self.ha_role != "primary":
                    subnet_count = self.subnet_items.count()
                    class_count = self.client_classes.count()
                    option_count = self.option_data.count()

                    if subnet_count > 0 or class_count > 0 or option_count > 0:
                        raise ValidationError(
                            f"Cannot change role from Primary: server '{self.name}' has "
                            f"{subnet_count} Subnet(s), {class_count} client class(es), and "
                            f"{option_count} option data assigned. Use 'Migrate Configs to New Primary' "
                            f"on the HA Relationship to transfer these to the new primary first."
                        )
            except DHCPServer.DoesNotExist:
                pass

    def _validate_stork_port_conflicts(self):
        """Check for port conflicts between KEA daemon ports and Stork agent group ports."""
        group = self.stork_agent_group
        errors = {}

        # Collect active stork agent ports
        stork_ports = {}
        stork_ports[group.agent_port] = "Stork agent port"
        if group.operating_mode in ("both", "prometheus-only") and group.prometheus_exporter_port:
            stork_ports[group.prometheus_exporter_port] = "Stork Prometheus exporter port"

        # Check HTTP control socket port conflicts
        if self.ctrl_socket_http_enabled and self.ctrl_socket_http_port:
            if self.ctrl_socket_http_port in stork_ports:
                conflicting = stork_ports[self.ctrl_socket_http_port]
                errors["ctrl_socket_http_port"] = (
                    f"HTTP control socket port ({self.ctrl_socket_http_port}) conflicts with "
                    f"{conflicting} in Stork agent group '{group.name}'."
                )

        # Check HA port conflicts
        if self.ha_relationship and self.ha_port:
            if self.ha_port in stork_ports:
                conflicting = stork_ports[self.ha_port]
                errors["ha_port"] = (
                    f"HA port ({self.ha_port}) conflicts with {conflicting} in Stork agent group '{group.name}'."
                )

        if errors:
            raise ValidationError(errors)

    def get_ha_config(self):
        """Generate HA configuration if this server is part of an HA relationship.

        Returns:
            dict: KEA high-availability configuration, or None if not in HA.
        """
        if not self.ha_relationship:
            return None

        return self.ha_relationship.to_kea_dict(this_server=self)

    @property
    def effective_d2_daemon(self):
        """Return the D2Daemon that actually applies to this server.

        HA precedence: if the server is in an HA relationship whose
        ``d2_daemon`` is set, that wins — peers must agree on the
        ``dhcp-ddns`` block.
        """
        if self.ha_relationship_id and self.ha_relationship.d2_daemon_id:
            return self.ha_relationship.d2_daemon
        return self.d2_daemon

    @property
    def effective_ddns_policy(self):
        """Return the DDNSPolicy that actually applies to this server.

        HA precedence: when the server is in an HA relationship whose
        ``ddns_policy`` is set, that wins so peers emit identical
        ``ddns-*`` overrides at the Dhcp4/6 root level.
        """
        if self.ha_relationship_id and self.ha_relationship.ddns_policy_id:
            return self.ha_relationship.ddns_policy
        return self.ddns_policy

    def _effective_ddns_field(self, name, blank_sentinel=""):
        """Resolve a DDNS scalar with HA precedence.

        When the server is in an HA relationship whose ``d2_daemon`` is set,
        the relationship's value wins so peers stay in sync. Otherwise the
        server's own value is used. ``blank_sentinel`` lets callers treat
        empty strings as "unset" without overriding meaningful zero/False
        values on numeric/boolean fields.
        """
        if self.ha_relationship_id and self.ha_relationship.d2_daemon_id:
            return getattr(self.ha_relationship, name)
        return getattr(self, name)

    def effective_ddns_block(self):
        """Build the ``dhcp-ddns`` block for kea-dhcp4/6, or None if not configured."""
        daemon = self.effective_d2_daemon
        if daemon is None:
            return None
        block = {
            "enable-updates": self._effective_ddns_field("ddns_enable_updates"),
            "server-ip": daemon.listener_ip,
            "server-port": daemon.port,
            "ncr-protocol": daemon.ncr_protocol,
            "ncr-format": daemon.ncr_format,
        }
        # Sender IP/port are per-server (the local source endpoint that
        # sends NCRs), not shared across HA peers — read directly from self.
        if self.ddns_sender_ip:
            block["sender-ip"] = self.ddns_sender_ip
        if self.ddns_sender_port is not None:
            block["sender-port"] = self.ddns_sender_port
        return block

    def get_ha_primary(self):
        """Get the primary server in this server's HA relationship, if any.

        Returns:
            DHCPServer: The primary server, or None if not in HA or this is the primary.
        """
        if not self.ha_relationship:
            return None

        # Find the primary server in this relationship
        primary_server = self.ha_relationship.servers.filter(ha_role="primary").first()
        if primary_server and primary_server.pk != self.pk:
            return primary_server
        return None

    def get_unused_only_in_additional_list_classes(self):
        """Get client classes with only_in_additional_list=True that are not used in any subnet or pool.

        For HA standby/secondary servers, this always returns an empty list since they inherit
        Subnets from the primary server.

        Returns:
            list: List of ClientClass instances that have only_in_additional_list=True
                  but are not referenced in any subnet's client_class,
                  evaluate_additional_classes, or any pool's client_class /
                  evaluate_additional_classes.
        """
        # Skip validation for non-primary HA servers - they inherit configs from primary
        if not self.is_ha_primary():
            return []

        # Get all classes with only_in_additional_list=True assigned to this server
        only_in_list_classes = self.client_classes.filter(only_in_additional_list=True)

        if not only_in_list_classes.exists():
            return []

        # Get all classes referenced in subnets and pools (use effective subnets for HA)
        used_class_ids = set()
        for subnet_item in self.get_effective_subnet_items():
            # Subnet-level: restricting client_class + evaluate_additional_classes
            for cc in subnet_item.get_all_subnet_client_classes():
                used_class_ids.add(cc.id)
            # Also check pool-level client classes
            for cc in subnet_item.get_all_pool_client_classes():
                used_class_ids.add(cc.id)

        # Find classes that are not used
        unused_classes = [cc for cc in only_in_list_classes if cc.id not in used_class_ids]
        return unused_classes

    def get_unreachable_subnet_restrictions(self):
        """Get subnets whose restricting client_class has only_in_additional_list=True.

        KEA evaluates the subnet-level ``client-class`` restriction *after*
        global class evaluation.  Classes with ``only-in-additional-list``
        are skipped during global evaluation and there is no higher scope
        that could list them in ``evaluate-additional-classes``, so no
        client would ever match — making the subnet permanently unreachable.

        For HA standby/secondary servers this always returns an empty list
        since they inherit subnets from the primary server.

        Returns:
            list[Subnet]: Subnets with an unreachable restricting class.
        """
        if not self.is_ha_primary():
            return []

        unreachable = []
        for subnet in self.get_effective_subnet_items().select_related("client_class"):
            if subnet.client_class_id and subnet.client_class.only_in_additional_list:
                unreachable.append(subnet)
        return unreachable

    def get_unreachable_pool_restrictions(self):
        """Get subnet pools whose restricting client_class has
        only_in_additional_list=True and is NOT listed in the parent
        subnet's evaluate_additional_classes.

        At pool level, KEA checks the ``client-class`` restriction after
        evaluating the subnet's ``evaluate-additional-classes``.  An
        ``only-in-additional-list`` class used as a pool restriction is
        therefore valid *only* if the parent subnet explicitly lists it in
        ``evaluate_additional_classes`` (triggering its evaluation before
        pool selection).  Without that, KEA never evaluates the class and
        no client can obtain addresses from the pool.

        For HA standby/secondary servers this always returns an empty list
        since they inherit subnets from the primary server.

        Returns:
            list[SubnetPool]: Pools with an unreachable restricting class.
        """
        if not self.is_ha_primary():
            return []

        unreachable = []
        for subnet in self.get_effective_subnet_items().prefetch_related(
            "evaluate_additional_classes",
            "subnet_pools__client_class",
        ):
            # Pre-compute the set of class IDs the subnet evaluates additionally
            subnet_eval_ids = set(subnet.evaluate_additional_classes.values_list("pk", flat=True))

            for pool in subnet.subnet_pools.all():
                if (
                    pool.client_class_id
                    and pool.client_class.only_in_additional_list
                    and pool.client_class_id not in subnet_eval_ids
                ):
                    unreachable.append(pool)
        return unreachable

    def is_ha_primary(self):
        """Check if this server is the primary in its HA relationship.

        Returns:
            bool: True if primary or not in HA, False if secondary/standby/backup.
        """
        if not self.ha_relationship:
            return True  # Not in HA, treat as primary
        return self.ha_role == "primary"

    def get_effective_subnet_items(self):
        """Get subnets for this server, including from HA primary if applicable.

        In HA mode, all servers serve the same subnets (from primary's config).

        Returns:
            QuerySet: Subnet instances this server should serve.
        """
        if not self.ha_relationship:
            # Not in HA, return own configs
            return self.subnet_items.all()

        # In HA, get configs from the primary server
        primary_server = self.ha_relationship.servers.filter(ha_role="primary").first()
        if primary_server:
            return primary_server.subnet_items.all()

        # Fallback to own configs if no primary found
        return self.subnet_items.all()

    def get_effective_client_classes(self):
        """Get client classes for this server, including from HA primary if applicable.

        Returns:
            QuerySet: ClientClass instances this server should use.
        """
        if not self.ha_relationship:
            return self.client_classes.all()

        # In HA, get from primary
        primary_server = self.ha_relationship.servers.filter(ha_role="primary").first()
        if primary_server:
            return primary_server.client_classes.all()

        return self.client_classes.all()

    def get_effective_option_data(self):
        """Get global option data for this server, including from HA primary if applicable.

        Returns:
            QuerySet: OptionData instances this server should use globally.
        """
        if not self.ha_relationship:
            return self.option_data.all()

        # In HA, get from primary
        primary_server = self.ha_relationship.servers.filter(ha_role="primary").first()
        if primary_server:
            return primary_server.option_data.all()

        return self.option_data.all()

    def get_hooks_libraries(self, process="kea-dhcp4"):
        """Get all hooks-libraries entries for this server.

        Collects hooks from all associated hook groups, filtered by the
        specified process type, and deduplicates by library path.

        Args:
            process: KEA process identifier (default: 'kea-dhcp4')

        Returns:
            List of dictionaries suitable for KEA hooks-libraries configuration
        """
        hooks_libraries = []
        seen_libraries = set()

        for hook_group in self.hook_groups.all():
            for hook_entry in hook_group.to_kea_hooks_libraries(process):
                library_path = hook_entry.get("library")
                if library_path not in seen_libraries:
                    seen_libraries.add(library_path)
                    hooks_libraries.append(hook_entry)

        return hooks_libraries

    def _resolve_ha_library_path(self, library_name):
        """Resolve the full library path for an HA-injected hook.

        When HA is enabled, the HA hook (``libdhcp_ha.so``) and its
        prerequisite (``libdhcp_lease_cmds.so``) must be added to the
        configuration.  Instead of hardcoding ``/usr/lib64/kea/hooks`` this
        method determines the correct base path by inspecting the hook
        groups assigned to this server:

        1. If one of the assigned hook groups already contains a ``Hook``
           whose ``library_name`` matches *library_name*, the full path
           produced by that group (``library_path`` + ``library_name``) is
           returned.  This way, a hook that is explicitly managed through a
           group always uses that group's ``library_path``.
        2. Otherwise, if the server has **exactly one** hook group, that
           group's ``library_path`` is used as the base path.  This covers
           the common case where all hooks on a server share the same
           install location.
        3. If multiple groups with **different** ``library_path`` values
           exist and none of them contains the requested hook, the method
           falls back to the default path ``/usr/lib64/kea/hooks``.

        Args:
            library_name: Library filename (e.g. ``libdhcp_ha.so``).

        Returns:
            str: Fully-qualified library path for use in KEA configuration.
        """
        default_base = "/usr/lib64/kea/hooks"
        hook_groups = list(self.hook_groups.prefetch_related("hooks").all())

        if not hook_groups:
            # No hook groups assigned — use the default path.
            base = default_base.rstrip("/")
            lib = library_name.lstrip("/")
            return f"{base}/{lib}"

        # 1. Check if any assigned group already contains this hook by library_name.
        for group in hook_groups:
            for hook in group.hooks.all():
                if hook.library_name == library_name:
                    return hook.get_library_path(group.library_path)

        # 2. Collect distinct library_path values across all groups.
        distinct_paths = {g.library_path for g in hook_groups}

        if len(distinct_paths) == 1:
            base = distinct_paths.pop().rstrip("/")
        else:
            # 3. Multiple differing paths and no explicit hook — fall back to default.
            base = default_base.rstrip("/")

        lib = library_name.lstrip("/")
        return f"{base}/{lib}"

    def get_control_sockets(self):
        """Return the control-sockets list for KEA configuration.

        Returns a list of control socket dictionaries based on enabled socket types.
        Returns an empty list if no control sockets are enabled.
        """
        sockets = []
        if self.ctrl_socket_http_enabled:
            sockets.append(
                {
                    "socket-type": "http",
                    "socket-address": self.ctrl_socket_http_address,
                    "socket-port": self.ctrl_socket_http_port,
                }
            )
        if self.ctrl_socket_unix_enabled:
            sockets.append(
                {
                    "socket-type": "unix",
                    "socket-name": self.ctrl_socket_unix_path,
                }
            )
        return sockets

    def to_kea_dict(self):
        """Return a complete KEA Dhcp4 configuration dictionary for this server.

        In HA mode, this method uses get_effective_* methods to pull configuration
        from the primary server, ensuring all HA peers have identical subnet configs.
        """
        result = {
            "Dhcp4": {
                "interfaces-config": {
                    "interfaces": ["*"],  # Placeholder - should be configured per deployment
                },
                "valid-lifetime": 3600,
                "max-valid-lifetime": 7200,
                # Global reservation mode defaults (subnets can override per-subnet)
                "reservations-global": self.reservations_global,
                "reservations-in-subnet": self.reservations_in_subnet,
                "reservations-out-of-pool": self.reservations_out_of_pool,
            }
        }

        dhcp4 = result["Dhcp4"]

        # Add control sockets if configured
        control_sockets = self.get_control_sockets()
        if control_sockets:
            dhcp4["control-sockets"] = control_sockets

        # Use effective methods that respect HA configuration
        effective_subnet_items = self.get_effective_subnet_items()
        effective_client_classes = self.get_effective_client_classes()
        effective_option_data = self.get_effective_option_data()

        # Collect all option data and their definitions from all sources
        all_option_data = set()
        vendor_spaces = set()

        # From subnet_items (using effective items for HA)
        for subnet_item in effective_subnet_items:
            for opt in subnet_item.option_data.all():
                all_option_data.add(opt)
                if opt.vendor_option_space:
                    vendor_spaces.add(opt.vendor_option_space)
            # Subnet-level client classes (restricting + evaluate-additional)
            for cc in subnet_item.get_all_subnet_client_classes():
                for opt in cc.option_data.all():
                    all_option_data.add(opt)
                    if opt.vendor_option_space:
                        vendor_spaces.add(opt.vendor_option_space)
            # From subnet pool-level configurations
            for opt in subnet_item.get_all_pool_option_data():
                all_option_data.add(opt)
                if opt.vendor_option_space:
                    vendor_spaces.add(opt.vendor_option_space)
            for cc in subnet_item.get_all_pool_client_classes():
                for opt in cc.option_data.all():
                    all_option_data.add(opt)
                    if opt.vendor_option_space:
                        vendor_spaces.add(opt.vendor_option_space)

        # From server-level client classes (using effective classes for HA)
        for cc in effective_client_classes:
            for opt in cc.option_data.all():
                all_option_data.add(opt)
                if opt.vendor_option_space:
                    vendor_spaces.add(opt.vendor_option_space)

        # From server-level global option data (using effective options for HA)
        for opt in effective_option_data:
            all_option_data.add(opt)
            if opt.vendor_option_space:
                vendor_spaces.add(opt.vendor_option_space)

        # Add global option-data if any
        global_option_data = [opt.to_kea_dict() for opt in effective_option_data]
        if global_option_data:
            dhcp4["option-data"] = global_option_data

        # Collect all client-classes from subnets, pools, and server-level (using effective)
        # All classes are included in global client-classes array
        # The only-in-additional-list flag tells KEA not to auto-evaluate them globally
        all_client_classes = set()
        for subnet_item in effective_subnet_items:
            # Subnet-level: restricting client_class + evaluate_additional_classes
            for cc in subnet_item.get_all_subnet_client_classes():
                all_client_classes.add(cc)
            # Include client classes from pool-level configurations
            for cc in subnet_item.get_all_pool_client_classes():
                all_client_classes.add(cc)
        # Add client classes directly linked to this server (using effective)
        for cc in effective_client_classes:
            all_client_classes.add(cc)

        # Collect ALL option definitions needed (vendor + standard custom + client class definitions)
        option_defs = []
        seen_definitions = set()  # Track by (code, space) to avoid duplicates

        # From vendor spaces
        for vs in vendor_spaces:
            for definition in vs.option_definitions.all():
                def_key = (definition.code, definition.space_name)
                if def_key not in seen_definitions:
                    seen_definitions.add(def_key)
                    option_defs.append(definition.to_kea_dict())

        # From option data that uses custom (non-standard) definitions in dhcp4/dhcp6 space
        for opt in all_option_data:
            if opt.definition:
                definition = opt.definition
                # Include if it's a custom definition (not standard) and not already added
                if not definition.is_standard:
                    def_key = (definition.code, definition.space_name)
                    if def_key not in seen_definitions:
                        seen_definitions.add(def_key)
                        option_defs.append(definition.to_kea_dict())

        # From client classes - add their option definitions (Option 43 and VIVSO)
        for cc in all_client_classes:
            for opt_def_dict in cc.get_kea_option_defs():
                # Track by (code, space) to avoid duplicates
                def_key = (opt_def_dict.get("code"), opt_def_dict.get("space"))
                if def_key not in seen_definitions:
                    seen_definitions.add(def_key)
                    option_defs.append(opt_def_dict)

        if option_defs:
            dhcp4["option-def"] = option_defs

        # Add client-classes
        if all_client_classes:
            dhcp4["client-classes"] = [cc.to_kea_dict() for cc in all_client_classes]

        # Add subnets (subnet4) - using effective subnets for HA
        # Also collect global reservations from subnets where effective
        # reservations_global is True (explicit or inherited from server)
        subnets = []
        global_reservations = []
        for subnet_item in effective_subnet_items:
            # Only include IPv4 prefixes
            if subnet_item.prefix.prefix.version == 4:
                subnets.append(subnet_item.to_kea_dict())
                if subnet_item.effective_reservations_global:
                    global_reservations.extend(subnet_item.get_kea_global_reservations())

        if subnets:
            dhcp4["subnet4"] = subnets

        if global_reservations:
            dhcp4["reservations"] = global_reservations

        # Build hooks-libraries from hook groups assigned to this server
        hooks_libraries = self.get_hooks_libraries("kea-dhcp4")

        # Add HA hooks-libraries if this server is part of an HA relationship
        ha_config = self.get_ha_config()
        if ha_config:
            # Track libraries already added from hook groups
            seen_libraries = {h.get("library") for h in hooks_libraries}

            # Add lease_cmds hook if not already present (required for HA)
            lease_cmds_lib = self._resolve_ha_library_path("libdhcp_lease_cmds.so")
            if lease_cmds_lib not in seen_libraries:
                hooks_libraries.append({"library": lease_cmds_lib})
                seen_libraries.add(lease_cmds_lib)

            # Add HA hook with configuration
            ha_lib = self._resolve_ha_library_path("libdhcp_ha.so")
            # Remove any existing HA hook entry (we need to add our configured one)
            hooks_libraries = [h for h in hooks_libraries if h.get("library") != ha_lib]
            hooks_libraries.append(
                {
                    "library": ha_lib,
                    "parameters": {"high-availability": [ha_config]},
                }
            )

        if hooks_libraries:
            dhcp4["hooks-libraries"] = hooks_libraries

        # DDNS: emit connection block + server-level policy overrides.
        # Kea resolves the override chain at packet-processing time —
        # subnet- and class-level overrides are emitted separately in
        # Subnet.to_kea_dict() / ClientClass.to_kea_dict().
        ddns_block = self.effective_ddns_block()
        if ddns_block is not None:
            dhcp4["dhcp-ddns"] = ddns_block
        eff_policy = self.effective_ddns_policy
        if eff_policy is not None:
            dhcp4.update(eff_policy.to_kea_overrides())

        return result


class VendorOptionSpace(NetBoxModel):
    """Vendor Option Space for managing vendor-specific DHCP options

    In KEA, vendor option spaces define custom options that can be delivered via:
    - Option 43 (Vendor-Encapsulated-Options): Legacy, widely supported
    - Option 125 (VIVSO): Newer, supports multiple vendors

    The delivery method is chosen at the OptionData level, not here.
    Enterprise ID is optional but recommended for VIVSO delivery.
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Name of the vendor option space (e.g., 'cisco-options', 'fortinet-space')",
    )
    enterprise_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="IANA Enterprise ID (e.g., 9 for Cisco, 12356 for Fortinet) - required for VIVSO delivery",
    )
    manufacturer = models.ForeignKey(
        Manufacturer,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="vendor_option_spaces",
        help_text="Manufacturer/vendor associated with this option space",
    )
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ("enterprise_id", "name")
        verbose_name = "Vendor Option Space"
        verbose_name_plural = "Vendor Option Spaces"

    def __str__(self):
        if self.manufacturer:
            return f"{self.name} ({self.manufacturer.name})"
        if self.enterprise_id:
            return f"{self.name} (EID: {self.enterprise_id})"
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_dhcp_kea_plugin:vendoroptionspace", args=[self.pk])


class OptionDefinition(NetBoxModel):
    """DHCP Option Definition (KEA option-def)

    Defines the structure/schema of custom DHCP options. Standard DHCP options
    (like option 66, 67, etc.) are built into KEA and don't need definitions.
    Custom vendor options MUST be defined before they can be used in option-data.
    """

    OPTION_SPACE_CHOICES = (
        ("dhcp4", "DHCPv4"),
        ("dhcp6", "DHCPv6"),
        (
            "vendor-encapsulated-options-space",
            "Vendor-Encapsulated-Options (Option 43)",
        ),
    )

    OPTION_TYPE_CHOICES = (
        ("string", "String"),
        ("binary", "Binary"),
        ("boolean", "Boolean"),
        ("empty", "Empty"),
        ("fqdn", "FQDN"),
        ("ipv4-address", "IPv4 Address"),
        ("ipv6-address", "IPv6 Address"),
        ("ipv6-prefix", "IPv6 Prefix"),
        ("psid", "PSID"),
        ("record", "Record"),
        ("tuple", "Tuple"),
        ("int8", "Signed Integer 8-bit"),
        ("int16", "Signed Integer 16-bit"),
        ("int32", "Signed Integer 32-bit"),
        ("uint8", "Unsigned Integer 8-bit"),
        ("uint16", "Unsigned Integer 16-bit"),
        ("uint32", "Unsigned Integer 32-bit"),
    )

    name = models.CharField(max_length=100, help_text="Option name (e.g., 'UCIdentifier')")
    code = models.PositiveIntegerField(help_text="Option code within the space")
    option_type = models.CharField(
        max_length=20,
        choices=OPTION_TYPE_CHOICES,
        default="string",
        help_text="Data type of the option",
    )
    option_space = models.CharField(
        max_length=50,
        choices=OPTION_SPACE_CHOICES,
        default="dhcp4",
        help_text="Base option space (used when not in a vendor space)",
    )
    vendor_option_space = models.ForeignKey(
        VendorOptionSpace,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="option_definitions",
        help_text="Vendor option space this definition belongs to",
    )
    is_array = models.BooleanField(default=False, help_text="Whether this option contains an array of values")
    encapsulate = models.CharField(
        max_length=100,
        blank=True,
        help_text="Name of option space to encapsulate (for container options)",
    )
    record_types = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated list of types for record options (e.g., 'uint8, string, ipv4-address')",
    )
    description = models.CharField(max_length=200, blank=True)
    is_standard = models.BooleanField(
        default=False,
        help_text="Standard DHCP option (read-only, auto-populated from RFC specifications)",
    )

    class Meta:
        ordering = ("vendor_option_space", "code", "name")
        verbose_name = "Option Definition"
        verbose_name_plural = "Option Definitions"
        unique_together = ("vendor_option_space", "code")

    def __str__(self):
        if self.vendor_option_space:
            return f"{self.name} (code {self.code}, {self.vendor_option_space.name})"
        return f"{self.name} (code {self.code}, {self.get_option_space_display()})"

    def get_absolute_url(self):
        return reverse("plugins:netbox_dhcp_kea_plugin:optiondefinition", args=[self.pk])

    IP_TYPES = {"ipv4-address", "ipv6-address"}

    @property
    def space_name(self):
        """Return the effective space name for KEA config"""
        if self.vendor_option_space:
            return self.vendor_option_space.name
        return self.option_space

    def parsed_record_types(self):
        """Return a list of type strings from the comma-separated record_types field."""
        if not self.record_types:
            return []
        return [t.strip() for t in self.record_types.split(",")]

    def record_ip_field_index(self):
        """Return the index of the first IP-type field in record_types, or None."""
        for i, t in enumerate(self.parsed_record_types()):
            if t in self.IP_TYPES:
                return i
        return None

    def to_kea_dict(self):
        """Return a dictionary representation for KEA option-def configuration.

        Returns:
            Dictionary with KEA option-def format:
            {
                "name": "option-name",
                "code": 123,
                "type": "string",
                "space": "dhcp4",  # or vendor space name
                ...
            }
        """
        result = {
            "name": self.name,
            "code": self.code,
            "type": self.option_type,
            "space": self.space_name,
        }

        if self.is_array:
            result["array"] = True
        if self.encapsulate:
            result["encapsulate"] = self.encapsulate
        if self.record_types:
            result["record-types"] = self.record_types

        return result


class OptionData(NetBoxModel):
    """DHCP Option Data/Value (KEA option-data)

    Represents actual option values that can be assigned to client classes,
    subnets/prefixes, or globally. Can reference a custom OptionDefinition
    or use standard DHCP option names/codes.
    """

    OPTION_SPACE_CHOICES = (
        ("dhcp4", "DHCPv4"),
        ("dhcp6", "DHCPv6"),
    )

    DELIVERY_TYPE_CHOICES = (
        ("standard", "Standard (direct option)"),
        ("option43", "Option 43 (Vendor-Encapsulated-Options)"),
        ("vivso", "Option 125 (VIVSO)"),
    )

    definition = models.ForeignKey(
        OptionDefinition,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="option_data_instances",
        help_text="Reference to custom option definition (leave blank for standard options)",
    )
    distinctive_name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Distinctive Name",
        help_text="Unique identifier for this option data instance (KEA name/code comes from definition)",
    )
    option_space = models.CharField(
        max_length=50,
        choices=OPTION_SPACE_CHOICES,
        default="dhcp4",
        help_text="Option space for standard options",
    )
    vendor_option_space = models.ForeignKey(
        VendorOptionSpace,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="option_data_instances",
        help_text="Vendor option space (for vendor-specific option data)",
    )
    delivery_type = models.CharField(
        max_length=20,
        choices=DELIVERY_TYPE_CHOICES,
        default="standard",
        help_text="How to deliver this option: standard (direct), Option 43, or VIVSO (Option 125)",
    )
    data = models.TextField(blank=True, default="", help_text="Option value/data")
    record_manual_fields = models.JSONField(
        blank=True,
        null=True,
        help_text="For record-type options with IP sources: JSON dict mapping field positions to manual values.",
    )
    always_send = models.BooleanField(
        default=False,
        help_text="Always send this option even if not requested by client",
    )
    csv_format = models.BooleanField(default=True, help_text="Data is in CSV format (KEA default)")
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = (
            "delivery_type",
            "vendor_option_space",
            "option_space",
            "distinctive_name",
        )
        verbose_name = "Option Data"
        verbose_name_plural = "Option Data"

    def clean(self):
        super().clean()
        # Standard delivery should not have a vendor_option_space
        if self.delivery_type == "standard" and self.vendor_option_space:
            raise ValidationError(
                {
                    "vendor_option_space": "Vendor Option Space should not be set for standard (direct) option delivery. "
                    "Use Option 43 or VIVSO delivery type for vendor-specific options."
                }
            )
        # VIVSO requires enterprise_id on the vendor_option_space
        if self.delivery_type == "vivso":
            if not self.vendor_option_space:
                raise ValidationError({"vendor_option_space": "Vendor Option Space is required for VIVSO delivery."})
            if not self.vendor_option_space.enterprise_id:
                raise ValidationError(
                    {
                        "vendor_option_space": "Selected Vendor Option Space must have an Enterprise ID for VIVSO delivery."
                    }
                )
        # Option 43 requires a vendor_option_space
        if self.delivery_type == "option43" and not self.vendor_option_space:
            raise ValidationError({"vendor_option_space": "Vendor Option Space is required for Option 43 delivery."})
        # If csv_format is False, data must be valid hexadecimal
        if not self.csv_format and self.data:
            # Remove any spaces or colons that might be used as separators
            hex_data = self.data.replace(" ", "").replace(":", "").replace("-", "")
            # Check if it's valid hexadecimal
            try:
                if hex_data:
                    int(hex_data, 16)
                    # Check for even number of characters (complete bytes)
                    if len(hex_data) % 2 != 0:
                        raise ValidationError(
                            {"data": "Hexadecimal data must have an even number of characters (complete bytes)."}
                        )
            except ValueError as err:
                raise ValidationError(
                    {
                        "data": 'When CSV format is disabled, data must be a valid hexadecimal string (e.g., "48656C6C6F" or "48:65:6C:6C:6F").'
                    }
                ) from err
        # If referencing a definition, sync the space info
        if self.definition:
            if self.definition.vendor_option_space and not self.vendor_option_space:
                self.vendor_option_space = self.definition.vendor_option_space

        # Type-based validation of data against definition's option_type
        # For record types with IP sources, validate only the manual fields — IP
        # positions are filled from validated NetBox objects and need no re-checking.
        if self.record_manual_fields and self.definition and self.definition.option_type == "record":
            record_types = self.definition.parsed_record_types()
            ip_index = self.definition.record_ip_field_index()
            for idx_str, val in self.record_manual_fields.items():
                i = int(idx_str)
                if i == ip_index or not val or i >= len(record_types):
                    continue
                self._validate_typed_value(val, record_types[i])
        elif self.csv_format and self.data and self.definition:
            values = [v.strip() for v in self.data.split(",")] if self.definition.is_array else [self.data.strip()]
            # Single-value options must not contain commas, unless the definition
            # is a "record" type where commas separate fields within a single value
            # (e.g., slp-service-scope: "true, FPSLP, Unscoped").
            if not self.definition.is_array and self.definition.option_type != "record" and "," in self.data:
                raise ValidationError(
                    {"data": "This option does not accept multiple values (definition is not an array)."}
                )
            for val in values:
                if val:
                    self._validate_typed_value(val, self.definition.option_type)

    @staticmethod
    def _validate_typed_value(value, option_type):
        """Validate a single value against the expected KEA option type."""
        import ipaddress as ipaddress_mod

        validators = {
            "ipv4-address": (ipaddress_mod.IPv4Address, "Must be a valid IPv4 address (e.g., 192.168.1.1)."),
            "ipv6-address": (ipaddress_mod.IPv6Address, "Must be a valid IPv6 address (e.g., 2001:db8::1)."),
            "ipv6-prefix": (ipaddress_mod.IPv6Network, "Must be a valid IPv6 prefix (e.g., 2001:db8::/32)."),
        }
        if option_type in validators:
            cls, msg = validators[option_type]
            try:
                cls(value)
            except (ValueError, ipaddress_mod.AddressValueError, ipaddress_mod.NetmaskValueError):
                raise ValidationError({"data": f"'{value}': {msg}"})
            return

        if option_type == "boolean":
            if value.lower() not in ("true", "false", "0", "1"):
                raise ValidationError({"data": f"'{value}': Must be true, false, 0, or 1."})
            return

        int_ranges = {
            "uint8": (0, 255),
            "uint16": (0, 65535),
            "uint32": (0, 4294967295),
            "int8": (-128, 127),
            "int16": (-32768, 32767),
            "int32": (-2147483648, 2147483647),
        }
        if option_type in int_ranges:
            lo, hi = int_ranges[option_type]
            try:
                n = int(value)
            except ValueError:
                raise ValidationError({"data": f"'{value}': Must be an integer."})
            if not (lo <= n <= hi):
                raise ValidationError({"data": f"'{value}': Must be between {lo} and {hi} for {option_type}."})
            return

        if option_type == "fqdn":
            import re

            if not re.match(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})*\.?$", value):
                raise ValidationError({"data": f"'{value}': Must be a valid FQDN."})
            return

        # string, binary, empty, record, tuple, psid — no extra validation

    def __str__(self):
        if self.vendor_option_space:
            return f"{self.distinctive_name} ({self.vendor_option_space.name})"
        return self.distinctive_name

    def get_absolute_url(self):
        return reverse("plugins:netbox_dhcp_kea_plugin:optiondata", args=[self.pk])

    @property
    def name(self):
        """Return the KEA option name from the definition"""
        if self.definition:
            return self.definition.name
        return None

    @property
    def code(self):
        """Return the KEA option code from the definition"""
        if self.definition:
            return self.definition.code
        return None

    @property
    def ascii_data(self):
        """Return hex data converted to ASCII, or resolved IP sources if linked."""
        # Resolve from IP sources if any are linked
        if self.pk and self.ip_sources.exists():
            resolved = [self._resolve_ip(src.ip_source) for src in self.ip_sources.order_by("ordinal")]
            resolved_ips = [ip for ip in resolved if ip]
            if resolved_ips:
                return ", ".join(resolved_ips)
        if self.csv_format or not self.data:
            return self.data
        try:
            # Remove any separators
            hex_data = self.data.replace(" ", "").replace(":", "").replace("-", "")
            # Convert hex to bytes, then to ASCII
            bytes_data = bytes.fromhex(hex_data)
            # Replace non-printable characters with dots
            ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in bytes_data)
            return ascii_str
        except (ValueError, TypeError):
            return self.data

    @property
    def space_name(self):
        """Return the effective space name for KEA config"""
        if self.vendor_option_space:
            return self.vendor_option_space.name
        return self.option_space

    def to_kea_dict(self):
        """Return a dictionary representation for KEA option-data configuration"""
        result = {}

        # Add space first based on delivery type
        if self.delivery_type == "vivso" and self.vendor_option_space:
            result["space"] = f"vendor-{self.vendor_option_space.enterprise_id}"
        elif self.vendor_option_space:
            result["space"] = self.vendor_option_space.name
        else:
            result["space"] = self.option_space

        # Add name and code
        result["name"] = self.name
        if self.code:
            result["code"] = self.code

        # Add data — resolve from IP sources if linked, otherwise use manual entry
        ip_sources = self.ip_sources.order_by("ordinal")

        if self.record_manual_fields and self.definition and self.definition.option_type == "record":
            # Record-type with IP sources: assemble from manual fields + resolved IPs
            record_types = self.definition.parsed_record_types()
            ip_index = self.definition.record_ip_field_index()
            parts = []
            for i, type_name in enumerate(record_types):
                if i == ip_index:
                    # Resolve IP sources for this position
                    resolved = [self._resolve_ip(src.ip_source) for src in ip_sources]
                    seen = set()
                    for entry in resolved:
                        if not entry:
                            continue
                        for ip in entry.split(", "):
                            if ip not in seen:
                                seen.add(ip)
                                parts.append(ip)
                else:
                    parts.append(self.record_manual_fields.get(str(i), ""))
            result["data"] = ", ".join(parts)
        elif ip_sources.exists():
            resolved = [self._resolve_ip(src.ip_source) for src in ip_sources]
            # Flatten (CNAME sources may resolve to multiple comma-separated IPs)
            # and deduplicate while preserving order.
            seen = set()
            unique_ips = []
            for entry in resolved:
                if not entry:
                    continue
                for ip in entry.split(", "):
                    if ip not in seen:
                        seen.add(ip)
                        unique_ips.append(ip)
            if unique_ips:
                result["data"] = ", ".join(unique_ips)
            else:
                result["data"] = self.data  # fallback if all sources deleted
        else:
            result["data"] = self.data

        # Add optional fields
        if self.always_send:
            result["always-send"] = True
        if not self.csv_format:
            result["csv-format"] = False

        return result

    @staticmethod
    def _resolve_ip(obj):
        """Extract IP string from an IPAddress or DNS Record object.

        For A records, returns the record value (an IP address).
        For CNAME records, follows the chain to the target A records and
        returns their IPs as a comma-separated string.
        """
        if obj is None:
            return None
        from ipam.models import IPAddress

        if isinstance(obj, IPAddress):
            return str(obj.address.ip)
        # Check for DNS Record without hard import
        try:
            from netbox_dns.models import Record as DNSRecord

            if isinstance(obj, DNSRecord):
                if obj.type in ("A", "AAAA"):
                    return obj.value
                if obj.type == "CNAME":
                    ips = OptionData._resolve_cname_chain(obj.value, DNSRecord)
                    return ", ".join(ips) if ips else None
                return obj.value
        except ImportError:
            pass
        return None

    @staticmethod
    def _resolve_cname_chain(fqdn, DNSRecord, max_depth=10):
        """Follow a CNAME chain until A/AAAA records are reached.

        Returns a list of IP address strings. Stops after *max_depth* hops
        to guard against circular CNAME references.
        """
        visited = set()
        current = fqdn
        for __ in range(max_depth):
            if current in visited:
                break
            visited.add(current)
            # Look for A/AAAA records at this name
            a_records = DNSRecord.objects.filter(fqdn=current, type__in=("A", "AAAA"))
            if a_records.exists():
                return [r.value for r in a_records]
            # Follow one more CNAME hop
            cname = DNSRecord.objects.filter(fqdn=current, type="CNAME").first()
            if cname is None:
                break
            current = cname.value
        return []


class OptionDataIPSource(NetBoxModel):
    """Links an OptionData to an IP source (IPAddress or DNS Record) via GenericFK.

    When IP sources are linked, OptionData.to_kea_dict() resolves current IPs
    from the linked objects instead of using the manual ``data`` field.
    Multiple sources are ordered by ``ordinal`` for array-type options.
    """

    option_data = models.ForeignKey(
        to="OptionData",
        on_delete=models.CASCADE,
        related_name="ip_sources",
    )
    content_type = models.ForeignKey(
        to=ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=models.Q(app_label="ipam", model="ipaddress"),
    )
    object_id = models.PositiveBigIntegerField()
    ip_source = GenericForeignKey("content_type", "object_id")
    ordinal = models.PositiveSmallIntegerField(
        default=0,
        help_text="Order of this IP source within the option data value list.",
    )

    class Meta:
        ordering = ("ordinal",)
        verbose_name = "IP Source"
        verbose_name_plural = "IP Sources"

    def __str__(self):
        return f"{self.option_data} → {self.ip_source}"

    def get_absolute_url(self):
        return self.option_data.get_absolute_url()


class ClientClass(NetBoxModel):
    """DHCP Client Classification (KEA client-classes)

    Client classes allow conditional assignment of options based on
    client characteristics using KEA's flexible test expressions.
    """

    name = models.CharField(max_length=100, unique=True)
    test_expression = models.TextField(
        blank=True,
        help_text="KEA test expression for client classification (e.g., \"option[60].text == 'MS-UC-Client'\"). Leave empty for unconditional classes that always match when evaluated.",
    )
    description = models.CharField(max_length=200, blank=True)
    servers = models.ManyToManyField(
        "DHCPServer",
        blank=True,
        related_name="client_classes",
        help_text="DHCP servers this client class applies to",
    )
    option_data = models.ManyToManyField(
        OptionData,
        blank=True,
        related_name="client_classes",
        help_text="Option data to send to clients matching this class",
    )

    only_in_additional_list = models.BooleanField(
        default=False,
        help_text="When enabled, this class is only evaluated when explicitly listed in a subnet's evaluate-additional-classes, not for every packet. The class is still defined in the server's global client-classes, but KEA won't auto-evaluate it.",
    )
    # Additional KEA client-class fields
    next_server = models.GenericIPAddressField(
        null=True,
        blank=True,
        protocol="IPv4",
        help_text="Next server IP for PXE boot (siaddr)",
    )
    server_hostname = models.CharField(max_length=255, blank=True, help_text="Server hostname for PXE boot (sname)")
    boot_file_name = models.CharField(max_length=255, blank=True, help_text="Boot file name for PXE boot (file)")
    ddns_policy = models.ForeignKey(
        "DDNSPolicy",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="client_classes",
        help_text="Class-level DDNS policy overrides (ddns-* tunables)",
    )

    class Meta:
        ordering = ("name",)
        verbose_name = "Client Class"
        verbose_name_plural = "Client Classes"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_dhcp_kea_plugin:clientclass", args=[self.pk])

    def has_option43_data(self):
        """Check if this class has any option data with option43 delivery type"""
        return self.option_data.filter(delivery_type="option43").exists()

    def has_vivso_data(self):
        """Check if this class has any option data with vivso delivery type"""
        return self.option_data.filter(delivery_type="vivso").exists()

    def get_option43_vendor_spaces(self):
        """Get unique vendor option spaces used by option43 delivery type options"""
        return VendorOptionSpace.objects.filter(
            option_data_instances__client_classes=self,
            option_data_instances__delivery_type="option43",
        ).distinct()

    def get_vivso_vendor_spaces(self):
        """Get unique vendor option spaces used by vivso delivery type options"""
        return VendorOptionSpace.objects.filter(
            option_data_instances__client_classes=self,
            option_data_instances__delivery_type="vivso",
        ).distinct()

    def get_option_definitions(self):
        """Get unique option definitions from this class's option data, sorted by code"""
        return OptionDefinition.objects.filter(option_data_instances__client_classes=self).distinct().order_by("code")

    def get_option_data_sorted(self):
        """Get option data sorted by code"""
        return self.option_data.select_related("definition", "vendor_option_space").order_by("definition__code")

    def get_kea_option_defs(self, ascii_format=False):
        """
        Get option-def list for KEA configuration.

        Returns list of option definition dicts when:
        - has_option43_data(): includes vendor-encapsulated-options definition and custom option definitions in vendor space
        - has_vivso_data(): includes custom option definitions in vendor-{enterprise_id} space

        Args:
            ascii_format: Not used here, but kept for consistency with get_kea_option_data

        Returns:
            List of option-def dictionaries, or empty list if none
        """
        option_defs = []

        # Add vendor-encapsulated-options and custom definitions when we have option43 data
        if self.has_option43_data():
            for vendor_space in self.get_option43_vendor_spaces():
                # Add vendor-encapsulated-options definition
                option_defs.append(
                    {
                        "name": "vendor-encapsulated-options",
                        "code": 43,
                        "type": "empty",
                        "encapsulate": vendor_space.name,
                    }
                )

                # Add custom option definitions in vendor space
                option43_definitions = OptionDefinition.objects.filter(
                    option_data_instances__client_classes=self,
                    option_data_instances__delivery_type="option43",
                    vendor_option_space=vendor_space,
                ).distinct()

                for opt_def in option43_definitions:
                    option_defs.append(
                        {
                            "name": opt_def.name,
                            "code": opt_def.code,
                            "type": opt_def.option_type,
                            "space": vendor_space.name,
                        }
                    )

        # Add custom option definitions for VIVSO delivery type in vendor-{enterprise_id} space
        if self.has_vivso_data():
            for vendor_space in self.get_vivso_vendor_spaces():
                if vendor_space.enterprise_id:
                    # Get all option definitions used by VIVSO options in this vendor space
                    vivso_definitions = OptionDefinition.objects.filter(
                        option_data_instances__client_classes=self,
                        option_data_instances__delivery_type="vivso",
                        vendor_option_space=vendor_space,
                    ).distinct()

                    for opt_def in vivso_definitions:
                        option_defs.append(
                            {
                                "name": opt_def.name,
                                "code": opt_def.code,
                                "type": opt_def.option_type,
                                "space": f"vendor-{vendor_space.enterprise_id}",
                            }
                        )

        return option_defs

    def get_kea_option_data(self, ascii_format=False):
        """
        Get option-data list for KEA configuration.

        Args:
            ascii_format: If True, use ascii_data and csv-format=true;
                         If False, use raw data and csv-format=false

        Returns:
            List of option-data dictionaries
        """
        option_data_list = []

        # Add vendor-encapsulated-options entry if we have option43 data
        if self.has_option43_data():
            option_data_list.append({"name": "vendor-encapsulated-options", "code": 43})

        # Add vivso-suboptions entry for each unique enterprise ID if we have vivso data
        if self.has_vivso_data():
            for vendor_space in self.get_vivso_vendor_spaces():
                if vendor_space.enterprise_id:
                    option_data_list.append(
                        {
                            "name": "vivso-suboptions",
                            "data": str(vendor_space.enterprise_id),
                        }
                    )

        # Add the rest of the option data
        for opt in self.get_option_data_sorted():
            opt_dict = {
                "name": opt.name,
            }

            # Set space based on delivery type
            if opt.delivery_type == "vivso" and opt.vendor_option_space:
                opt_dict["space"] = f"vendor-{opt.vendor_option_space.enterprise_id}"
            elif opt.vendor_option_space:
                opt_dict["space"] = opt.vendor_option_space.name
            else:
                opt_dict["space"] = opt.option_space

            if opt.code:
                opt_dict["code"] = opt.code

            # Use ascii_data or raw data based on format
            if ascii_format:
                opt_dict["data"] = opt.ascii_data
            else:
                opt_dict["data"] = opt.data

            # Use the actual csv_format value from the database
            # Only include csv-format in output if it's False (KEA default is True)
            if not opt.csv_format:
                opt_dict["csv-format"] = False

            if opt.always_send:
                opt_dict["always-send"] = True

            option_data_list.append(opt_dict)

        return option_data_list

    def to_kea_dict(self, ascii_format=False):
        """
        Return a dictionary representation for KEA client-class configuration.

        Args:
            ascii_format: If True, use ascii_data and csv-format=true;
                         If False, use raw data and csv-format=false

        Returns:
            Dictionary suitable for KEA client-class configuration
        """
        result = {
            "name": self.name,
        }

        # Only include test if there's an expression (empty = unconditional class)
        if self.test_expression:
            result["test"] = self.test_expression

        # Add only-in-additional-list flag if set
        if self.only_in_additional_list:
            result["only-in-additional-list"] = True

        # Note: option-def is now added to global Dhcp4.option-def array by DHCPServer.to_kea_dict()
        # This is required because KEA needs all option definitions in the global scope

        # Add option-data if any
        option_data = self.get_kea_option_data(ascii_format=ascii_format)
        if option_data:
            result["option-data"] = option_data

        # Add PXE boot fields if set
        if self.next_server:
            result["next-server"] = str(self.next_server)
        if self.server_hostname:
            result["server-hostname"] = self.server_hostname
        if self.boot_file_name:
            result["boot-file-name"] = self.boot_file_name

        if self.ddns_policy_id is not None:
            result.update(self.ddns_policy.to_kea_overrides())

        return result

    def to_kea_json(self, ascii_format=False, indent=4):
        """
        Return a JSON string representation for KEA client-class configuration.

        Args:
            ascii_format: If True, use ascii_data and csv-format=true
            indent: JSON indentation level

        Returns:
            JSON string
        """
        import json

        return json.dumps(self.to_kea_dict(ascii_format=ascii_format), indent=indent)


def get_default_valid_lifetime():
    return get_model_default("Subnet", "valid_lifetime", 3600)


def get_default_max_lifetime():
    return get_model_default("Subnet", "max_lifetime", 7200)


class Subnet(NetBoxModel):
    """KEA subnet configuration linked to NetBox Prefixes"""

    prefix = models.OneToOneField(Prefix, on_delete=models.CASCADE, related_name="dhcp_config")
    server = models.ForeignKey(DHCPServer, on_delete=models.PROTECT, related_name="subnet_items")
    option_data = models.ManyToManyField(
        OptionData,
        blank=True,
        related_name="subnet_items",
        help_text="Option data for this subnet",
    )
    client_class = models.ForeignKey(
        ClientClass,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subnet_restrictions",
        help_text="Client class that restricts which clients can use this subnet (KEA client-class)",
    )
    evaluate_additional_classes = models.ManyToManyField(
        ClientClass,
        blank=True,
        related_name="subnet_evaluations",
        help_text="Additional client classes to evaluate for clients in this subnet (KEA evaluate-additional-classes)",
    )
    valid_lifetime = models.PositiveIntegerField(
        default=get_default_valid_lifetime, help_text="Lease valid lifetime in seconds"
    )
    max_lifetime = models.PositiveIntegerField(
        default=get_default_max_lifetime, help_text="Maximum lease lifetime in seconds"
    )
    routers_option_offset = models.PositiveIntegerField(
        default=1,
        help_text="Offset from network address for router IP (e.g., 1 for .1, 254 for .254 in a /24). Set to 0 to disable routers option.",
    )

    # KEA reservation mode flags (per-subnet overrides, None = inherit from server)
    reservations_global = models.BooleanField(
        null=True,
        blank=True,
        default=None,
        verbose_name="Reservations Global",
        help_text="Look for host reservations in the global scope. Leave blank to inherit from server.",
    )
    reservations_in_subnet = models.BooleanField(
        null=True,
        blank=True,
        default=None,
        verbose_name="Reservations In-Subnet",
        help_text="Look for host reservations within this subnet. Leave blank to inherit from server.",
    )
    reservations_out_of_pool = models.BooleanField(
        null=True,
        blank=True,
        default=None,
        verbose_name="Reservations Out-of-Pool",
        help_text="Exclude reserved addresses from dynamic pool allocation. Leave blank to inherit from server.",
    )
    reservations_only = models.BooleanField(
        default=get_default_reservations_only,
        verbose_name="Reservations Only",
        help_text="Disable dynamic pool allocation — only reserved hosts will receive an IP from this subnet",
    )
    ddns_policy = models.ForeignKey(
        "DDNSPolicy",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subnets",
        help_text="Subnet-level DDNS policy overrides (ddns-* tunables)",
    )

    class Meta:
        ordering = ("prefix",)
        verbose_name = "Subnet"
        verbose_name_plural = "Subnets"

    def __str__(self):
        return str(self.prefix)

    def get_absolute_url(self):
        return reverse("plugins:netbox_dhcp_kea_plugin:subnet", args=[self.pk])

    def get_effective_reservation_flag(self, field_name):
        """Return the effective value of a reservation flag.

        If the subnet has an explicit value (True/False), return it.
        If None, inherit from the parent DHCPServer.
        """
        value = getattr(self, field_name)
        if value is not None:
            return value
        return getattr(self.server, field_name)

    @property
    def effective_reservations_global(self):
        return self.get_effective_reservation_flag("reservations_global")

    @property
    def effective_reservations_in_subnet(self):
        return self.get_effective_reservation_flag("reservations_in_subnet")

    @property
    def effective_reservations_out_of_pool(self):
        return self.get_effective_reservation_flag("reservations_out_of_pool")

    def clean(self):
        super().clean()
        if self.max_lifetime < self.valid_lifetime:
            raise ValidationError({"valid_lifetime": "Valid lifetime cannot be greater than max lifetime."})

        # Validate routers_option_offset is within prefix range
        if self.routers_option_offset and self.prefix_id:  # type: ignore[attr-defined]
            import netaddr

            prefix = self.prefix.prefix
            if isinstance(prefix, str):
                prefix = netaddr.IPNetwork(prefix)
            max_offset = prefix.size - 2  # Exclude network and broadcast
            if self.routers_option_offset > max_offset:
                raise ValidationError(
                    {"routers_option_offset": f"Offset must be between 0 and {max_offset} for this prefix."}
                )

        # Validate that a restricting client_class with only_in_additional_list=True
        # is not used at subnet level. KEA evaluates client-class restrictions AFTER
        # global class evaluation. Classes with only-in-additional-list are skipped
        # during global evaluation and there is no higher scope that could list them
        # in evaluate-additional-classes, so no client would ever match — making the
        # subnet permanently unreachable.
        if self.client_class_id:  # type: ignore[attr-defined]
            # Need to fetch the related object if not already loaded
            cc = self.client_class
            if cc and cc.only_in_additional_list:
                raise ValidationError(
                    {
                        "client_class": f"Client class '{cc.name}' has 'only in additional list' enabled. "
                        "It will not be evaluated globally by KEA, and there is no higher scope that can "
                        "trigger its evaluation via evaluate-additional-classes. No client will ever match "
                        "this class, making the subnet permanently unreachable. Either disable "
                        "'only in additional list' on the class, or use a different restricting class."
                    }
                )

        # Validate that client_class is not also in evaluate_additional_classes
        # (can only check after save for M2M, so this is a best-effort check)
        if self.pk and self.client_class_id:  # type: ignore[attr-defined]
            if self.evaluate_additional_classes.filter(pk=self.client_class_id).exists():  # type: ignore[attr-defined]
                raise ValidationError(
                    {
                        "client_class": "The restricting client class should not also appear in "
                        "evaluate-additional-classes."
                    }
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_router_ip(self):
        """Calculate the router IP address based on routers_option_offset.

        Returns:
            str: The router IP address, or None if routers_option_offset is 0.
        """
        if not self.routers_option_offset:
            return None

        prefix = self.prefix.prefix
        return str(prefix.network + self.routers_option_offset)

    def get_pools(self):
        """Calculate DHCP pools based on NetBox IP ranges or available IPs.

        Returns an empty list when ``reservations_only`` is enabled, so KEA
        will only serve reserved hosts from this subnet.

        Priority:
        1. If the prefix has IPRanges that are NOT mark_utilized, use those ranges
        2. Otherwise, calculate pools from the prefix address space:
           - When ``reservations_out_of_pool`` is True: use only unassigned IPs
             (``prefix.get_available_ips()``) so reserved addresses are excluded.
           - When ``reservations_out_of_pool`` is False: use the full usable range
             (network+1 to broadcast-1, or the entire range when ``prefix.is_pool``
             is True) excluding only the gateway (``routers_option_offset``).
             KEA handles reservation/pool overlap at runtime.

        When IP ranges are used, any associated SubnetPool configuration
        (client class, evaluate-additional-classes, option-data) is merged
        into the pool dictionary.

        Returns:
            list: List of pool dictionaries with 'pool' key containing
                  "start - end" format and optional KEA pool-level config.
        """
        if self.reservations_only:
            return []

        import netaddr

        pools = []

        # Use prefix's built-in method to get child ranges
        ip_ranges = self.prefix.get_child_ranges().filter(mark_utilized=False)

        if ip_ranges.exists():
            # Pre-fetch SubnetPool configs for these ranges in one query
            pool_configs = {
                sp.ip_range_id: sp  # type: ignore[attr-defined]
                for sp in SubnetPool.objects.filter(subnet=self, ip_range__in=ip_ranges)
                .select_related("client_class")
                .prefetch_related("evaluate_additional_classes", "option_data")
            }

            # Use IPRanges as pools
            for ip_range in ip_ranges:
                # Extract IP without mask for pool range
                start_ip = str(ip_range.start_address).split("/")[0]
                end_ip = str(ip_range.end_address).split("/")[0]
                pool_dict = {"pool": f"{start_ip} - {end_ip}"}

                # Merge SubnetPool configuration if it exists
                subnet_pool = pool_configs.get(ip_range.pk)
                if subnet_pool:
                    subnet_pool.apply_to_pool_dict(pool_dict)

                pools.append(pool_dict)
        elif self.effective_reservations_out_of_pool:
            # Exclude reserved (assigned) IPs from pools — use only available IPs
            available_ips = self.prefix.get_available_ips()

            # Also exclude the gateway IP from the available set
            gateway_offset = self.routers_option_offset
            if gateway_offset:
                prefix_net = self.prefix.prefix
                if isinstance(prefix_net, str):
                    prefix_net = netaddr.IPNetwork(prefix_net)
                gateway_ip = netaddr.IPAddress(prefix_net.network.value + gateway_offset)
                available_ips = available_ips - netaddr.IPSet([gateway_ip])

            # Get all CIDRs and merge contiguous ranges
            cidrs = list(available_ips.iter_cidrs())
            if not cidrs:
                return pools

            cidrs.sort(key=lambda c: c.first)

            # Merge contiguous ranges
            current_start = cidrs[0].first
            current_end = cidrs[0].last

            for cidr in cidrs[1:]:
                if cidr.first == current_end + 1:
                    current_end = cidr.last
                else:
                    first_ip = netaddr.IPAddress(current_start)
                    last_ip = netaddr.IPAddress(current_end)
                    pools.append({"pool": f"{first_ip} - {last_ip}"})
                    current_start = cidr.first
                    current_end = cidr.last

            first_ip = netaddr.IPAddress(current_start)
            last_ip = netaddr.IPAddress(current_end)
            pools.append({"pool": f"{first_ip} - {last_ip}"})
        else:
            # Full usable range — KEA handles reservation/pool overlap at runtime
            prefix = self.prefix.prefix
            if isinstance(prefix, str):
                prefix = netaddr.IPNetwork(prefix)

            if self.prefix.is_pool:
                # is_pool: all addresses are usable (including network/broadcast)
                pool_start = prefix.first
                pool_end = prefix.last
            else:
                # Standard: exclude network and broadcast addresses
                pool_start = prefix.first + 1
                pool_end = prefix.last - 1

            if pool_start > pool_end:
                return pools

            # Exclude the gateway IP by splitting the range around it
            gateway_offset = self.routers_option_offset
            if gateway_offset:
                gateway_int = prefix.network.value + gateway_offset
                if pool_start <= gateway_int <= pool_end:
                    # Range before gateway
                    if gateway_int > pool_start:
                        pools.append(
                            {"pool": f"{netaddr.IPAddress(pool_start)} - {netaddr.IPAddress(gateway_int - 1)}"}
                        )
                    # Range after gateway
                    if gateway_int < pool_end:
                        pools.append({"pool": f"{netaddr.IPAddress(gateway_int + 1)} - {netaddr.IPAddress(pool_end)}"})
                else:
                    # Gateway outside range, use full range
                    pools.append({"pool": f"{netaddr.IPAddress(pool_start)} - {netaddr.IPAddress(pool_end)}"})
            else:
                # No gateway configured
                pools.append({"pool": f"{netaddr.IPAddress(pool_start)} - {netaddr.IPAddress(pool_end)}"})

        return pools

    def get_reservations(self):
        """Get IP addresses that can be used as DHCP reservations with metadata.

        Returns IPs that:
        - Have an assigned object (interface)
        - Are not FHRP groups
        - Are either primary IP or OOB IP

        Returns a list of tuples: (kea_reservation_dict, metadata_dict)
        """
        reservations = []

        # Get child IPs from the prefix
        child_ips = self.prefix.get_child_ips()

        # Get the FHRP group content type to filter it out
        try:
            fhrp_ct = ContentType.objects.get(app_label="ipam", model="fhrpgroup")
        except ContentType.DoesNotExist:
            fhrp_ct = None

        for ip in child_ips:
            # Skip IPs without assigned objects
            if not ip.assigned_object_type:
                continue

            # Skip FHRP groups
            if fhrp_ct and ip.assigned_object_type_id == fhrp_ct.id:
                continue

            # Only include primary IPs or OOB IPs
            if not (ip.is_primary_ip or ip.is_oob_ip):
                continue

            # Get the assigned interface and parent object (device/VM)
            assigned_object = ip.assigned_object
            if not assigned_object:
                continue

            parent_object = getattr(assigned_object, "parent_object", None)
            if not parent_object:
                continue

            # Build the hostname similar to the Jinja template logic
            interface_name = assigned_object.name
            if ip.is_oob_ip and not ip.is_primary_ip:
                # Clean interface name for OOB IPs
                dev_interface = interface_name.replace("/", "-").replace(" ", "").replace(".", "-")
                host_id = f"{parent_object.name}_{dev_interface}"
            else:
                host_id = parent_object.name

            # Get MAC address if available (check primary_mac_address first, then mac_address for compatibility)
            mac_address = None
            primary_mac = getattr(assigned_object, "primary_mac_address", None)
            if primary_mac:
                mac_address = getattr(primary_mac, "mac_address", None)
            if not mac_address:
                # Fallback for older NetBox versions or VMInterface
                mac_address = getattr(assigned_object, "mac_address", None)

            # Build KEA reservation dict
            # Handle both netaddr.IPNetwork objects and string addresses
            ip_addr = ip.address
            if hasattr(ip_addr, "ip"):
                # netaddr.IPNetwork object - extract the IP without prefix
                ip_str = str(ip_addr.ip)
            else:
                # String or other format - strip any prefix notation
                ip_str = str(ip_addr).split("/")[0]

            kea_reservation = {
                "ip-address": ip_str,
            }

            # Add MAC address if available
            if mac_address:
                kea_reservation["hw-address"] = str(mac_address).lower()

            # Determine hostname from dns_name or use host_id
            if ip.dns_name:
                hostname = ip.dns_name.partition(".")[0]
                kea_reservation["hostname"] = hostname
            else:
                kea_reservation["hostname"] = host_id

            # Metadata for display purposes
            metadata = {
                "ip": ip,
                "host_id": host_id,
                "parent_object": parent_object,
                "interface": assigned_object,
                "is_primary": ip.is_primary_ip,
                "is_oob": ip.is_oob_ip,
                "has_hw_address": bool(mac_address),
            }

            reservations.append((kea_reservation, metadata))

        return reservations

    def get_kea_reservations(self):
        """Get DHCP reservations in KEA format only (without metadata).

        Only includes reservations that have a hw-address (MAC address).
        KEA requires either hw-address or duid for a valid reservation;
        entries without either will cause kea-dhcp4.service validation
        to fail.

        Returns a list of KEA reservation dictionaries suitable for
        including in the KEA configuration.
        """
        return [r[0] for r in self.get_reservations() if "hw-address" in r[0]]

    def get_kea_global_reservations(self):
        """Get DHCP reservations in KEA global format (without ip-address).

        Global reservations are placed at the Dhcp4 level and omit the
        ip-address field — the host receives an IP dynamically from
        whichever subnet it falls into, but is still identified by
        hw-address/hostname for option assignment and logging.

        Returns a list of KEA reservation dictionaries without ip-address.
        """
        global_reservations = []
        for res in self.get_kea_reservations():
            global_res = {k: v for k, v in res.items() if k != "ip-address"}
            global_reservations.append(global_res)
        return global_reservations

    def get_all_pool_option_data(self):
        """Get all OptionData instances used across this subnet's pool configurations.

        Returns:
            set: Set of OptionData instances from all SubnetPool configs.
        """
        option_data = set()
        for sp in self.subnet_pools.prefetch_related("option_data"):
            for opt in sp.option_data.all():
                option_data.add(opt)
        return option_data

    def get_all_pool_client_classes(self):
        """Get all ClientClass instances used across this subnet's pool configurations.

        Returns:
            set: Set of ClientClass instances from all SubnetPool configs
                 (both client_class and evaluate_additional_classes).
        """
        client_classes = set()
        for sp in self.subnet_pools.select_related("client_class").prefetch_related("evaluate_additional_classes"):
            if sp.client_class:
                client_classes.add(sp.client_class)
            for cc in sp.evaluate_additional_classes.all():
                client_classes.add(cc)
        return client_classes

    def get_all_subnet_client_classes(self):
        """Get all ClientClass instances used at the subnet level.

        Includes both the restricting client_class (if set) and all
        evaluate_additional_classes.

        Returns:
            set: Set of ClientClass instances from subnet-level config.
        """
        client_classes = set()
        if self.client_class:
            client_classes.add(self.client_class)
        for cc in self.evaluate_additional_classes.all():
            client_classes.add(cc)
        return client_classes

    def to_kea_dict(self):
        """Return a dictionary representation for KEA subnet configuration"""
        prefix = self.prefix.prefix
        result = {
            "id": self.pk,
            "subnet": str(prefix),
            "valid-lifetime": self.valid_lifetime,
            "max-valid-lifetime": self.max_lifetime,
        }

        # Add pools from available IPs or IP ranges (includes pool-level config)
        pools = self.get_pools()
        if pools:
            result["pools"] = pools

        # Build option-data list
        option_data_list = []

        # Add option data from the multiselect field
        for opt in self.option_data.all():
            option_data_list.append(opt.to_kea_dict())

        # Add routers option if configured (offset > 0)
        router_ip = self.get_router_ip()
        if router_ip:
            option_data_list.append({"space": "dhcp4", "name": "routers", "code": 3, "data": router_ip})

        if option_data_list:
            result["option-data"] = option_data_list

        # Add restricting client-class if set
        if self.client_class:
            result["client-class"] = self.client_class.name

        # Add evaluate-additional-classes
        additional_class_names = [cc.name for cc in self.evaluate_additional_classes.all()]
        if additional_class_names:
            result["evaluate-additional-classes"] = additional_class_names

        # Add reservation mode flags only when explicitly set (not None).
        # When None, KEA inherits from the Dhcp4 global block (set by DHCPServer).
        if self.reservations_global is not None:
            result["reservations-global"] = self.reservations_global
        if self.reservations_in_subnet is not None:
            result["reservations-in-subnet"] = self.reservations_in_subnet
        if self.reservations_out_of_pool is not None:
            result["reservations-out-of-pool"] = self.reservations_out_of_pool

        # Add reservations at subnet level only when not using global reservations.
        # When reservations_global is True (explicitly or inherited), reservations
        # are collected by DHCPServer.to_kea_dict() and placed in Dhcp4.reservations.
        if not self.effective_reservations_global:
            reservations = self.get_kea_reservations()
            if reservations:
                result["reservations"] = reservations

        if self.ddns_policy_id is not None:
            result.update(self.ddns_policy.to_kea_overrides())

        return result


class SubnetPool(NetBoxModel):
    """Pool-level DHCP configuration for a Subnet's IP Range.

    Optionally annotates a NetBox IPRange (child of the Subnet's Prefix) with
    KEA pool-level settings: a restricting client class, additional evaluated
    classes, and pool-specific option data.

    IP Ranges without a SubnetPool are rendered as plain pools in KEA config.
    """

    subnet = models.ForeignKey(
        Subnet,
        on_delete=models.CASCADE,
        related_name="subnet_pools",
    )
    ip_range = models.OneToOneField(
        IPRange,
        on_delete=models.CASCADE,
        related_name="dhcp_pool_config",
        help_text="NetBox IP Range that defines this pool's address boundaries",
    )
    client_class = models.ForeignKey(
        ClientClass,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pool_restrictions",
        help_text="Client class that restricts which clients can obtain addresses from this pool (KEA client-class)",
    )
    evaluate_additional_classes = models.ManyToManyField(
        ClientClass,
        blank=True,
        related_name="pool_evaluations",
        help_text="Additional client classes to evaluate for clients in this pool (KEA evaluate-additional-classes)",
    )
    option_data = models.ManyToManyField(
        OptionData,
        blank=True,
        related_name="pool_configs",
        help_text="DHCP options specific to this pool (KEA option-data)",
    )
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ("subnet", "ip_range")
        verbose_name = "Subnet Pool"
        verbose_name_plural = "Subnet Pools"

    def __str__(self):
        start_ip = str(self.ip_range.start_address).split("/")[0]
        end_ip = str(self.ip_range.end_address).split("/")[0]
        return f"{self.subnet} / {start_ip}-{end_ip}"

    @property
    def pool_range(self):
        """Return the pool range as 'start - end' without prefix masks."""
        start_ip = str(self.ip_range.start_address).split("/")[0]
        end_ip = str(self.ip_range.end_address).split("/")[0]
        return f"{start_ip} - {end_ip}"

    def get_absolute_url(self):
        return reverse("plugins:netbox_dhcp_kea_plugin:subnetpool", args=[self.pk])

    def clean(self):
        super().clean()

        # Validate that the IP range belongs to the subnet's prefix
        if self.ip_range_id and self.subnet_id:
            child_range_ids = set(self.subnet.prefix.get_child_ranges().values_list("pk", flat=True))
            if self.ip_range_id not in child_range_ids:
                raise ValidationError({"ip_range": "The selected IP range must be a child of this subnet's prefix."})

            # Warn if the IP range is mark_utilized (won't be used as a pool)
            if self.ip_range.mark_utilized:
                raise ValidationError(
                    {
                        "ip_range": "This IP range is marked as utilized and will not be rendered as a DHCP pool. "
                        "Remove the 'mark utilized' flag on the IP range to use it as a pool."
                    }
                )

        # Validate that a restricting client_class with only_in_additional_list=True
        # is reachable. At pool level, KEA checks client-class AFTER evaluating the
        # subnet's evaluate-additional-classes. So an only-in-additional-list class
        # used as pool restriction is valid ONLY if the parent subnet explicitly lists
        # it in evaluate_additional_classes (triggering its evaluation before pool
        # selection). Without that, KEA never evaluates the class and no client can
        # obtain addresses from the pool.
        if self.client_class_id and self.subnet_id:
            cc = self.client_class
            if cc and cc.only_in_additional_list:
                # Check if the parent subnet has this class in evaluate_additional_classes
                subnet_evaluates_class = self.subnet.evaluate_additional_classes.filter(pk=cc.pk).exists()
                if not subnet_evaluates_class:
                    raise ValidationError(
                        {
                            "client_class": f"Client class '{cc.name}' has 'only in additional list' enabled. "
                            "KEA will not evaluate it globally. For a pool-level restriction to work, the "
                            "parent subnet must list this class in its 'evaluate additional classes' so that "
                            "KEA evaluates it before pool selection. Either add the class to the subnet's "
                            "evaluate-additional-classes, disable 'only in additional list' on the class, "
                            "or use a different restricting class for this pool."
                        }
                    )

        # Validate that client_class is not also in evaluate_additional_classes
        # (can only check after save for M2M, so this is a best-effort check)
        if self.pk and self.client_class_id:
            if self.evaluate_additional_classes.filter(pk=self.client_class_id).exists():
                raise ValidationError(
                    {
                        "client_class": "The restricting client class should not also appear in "
                        "evaluate-additional-classes."
                    }
                )

    def apply_to_pool_dict(self, pool_dict):
        """Merge this SubnetPool's configuration into a KEA pool dictionary.

        Args:
            pool_dict: Dictionary with at least a 'pool' key. Modified in place.
        """
        # Add restricting client-class
        if self.client_class:
            pool_dict["client-class"] = self.client_class.name

        # Add evaluate-additional-classes
        additional_names = [cc.name for cc in self.evaluate_additional_classes.all()]
        if additional_names:
            pool_dict["evaluate-additional-classes"] = additional_names

        # Add pool-level option-data
        option_data_list = [opt.to_kea_dict() for opt in self.option_data.all()]
        if option_data_list:
            pool_dict["option-data"] = option_data_list

    def to_kea_dict(self):
        """Return a dictionary representation for this pool in KEA format."""
        start_ip = str(self.ip_range.start_address).split("/")[0]
        end_ip = str(self.ip_range.end_address).split("/")[0]
        pool_dict = {"pool": f"{start_ip} - {end_ip}"}
        self.apply_to_pool_dict(pool_dict)
        return pool_dict


class DHCPHARelationship(NetBoxModel):
    """High Availability relationship between KEA DHCP servers.

    Defines the HA configuration including mode (hot-standby, load-balancing, passive-backup),
    timing parameters, and multi-threading settings.
    """

    HA_MODE_CHOICES = (
        ("hot-standby", "Hot Standby"),
        ("load-balancing", "Load Balancing"),
        ("passive-backup", "Passive Backup"),
    )

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Name of the HA relationship (e.g., 'Primary DC HA')",
    )
    mode = models.CharField(
        max_length=20,
        choices=HA_MODE_CHOICES,
        default="hot-standby",
        help_text="HA mode: hot-standby (active/passive), load-balancing (active/active), or passive-backup",
    )

    # Timing parameters (in milliseconds)
    heartbeat_delay = models.PositiveIntegerField(
        default=10000, help_text="Heartbeat interval in milliseconds (default: 10000)"
    )
    max_response_delay = models.PositiveIntegerField(
        default=60000,
        help_text="Maximum time to wait for response in milliseconds (default: 60000)",
    )
    max_ack_delay = models.PositiveIntegerField(
        default=5000,
        help_text="Maximum acknowledgment delay in milliseconds (default: 5000)",
    )
    max_unacked_clients = models.PositiveIntegerField(
        default=5,
        help_text="Maximum number of unacknowledged clients before failover (default: 5)",
    )
    max_rejected_lease_updates = models.PositiveIntegerField(
        default=10,
        help_text="Maximum rejected lease updates before partner is considered unavailable (default: 10)",
    )

    # Multi-threading settings (HA+MT)
    enable_multi_threading = models.BooleanField(
        default=True,
        help_text="Enable multi-threading support for HA (requires KEA 2.3.2+)",
    )
    http_dedicated_listener = models.BooleanField(
        default=True, help_text="Use dedicated HTTP listener for HA communication"
    )
    http_listener_threads = models.PositiveIntegerField(
        default=4, help_text="Number of HTTP listener threads (0 = auto)"
    )
    http_client_threads = models.PositiveIntegerField(default=4, help_text="Number of HTTP client threads (0 = auto)")

    description = models.CharField(max_length=200, blank=True)
    d2_daemon = models.ForeignKey(
        "D2Daemon",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ha_relationships",
        help_text=(
            "D2 daemon shared by all peers in this HA relationship. "
            "When set, overrides each member server's standalone d2_daemon."
        ),
    )
    ddns_enable_updates = models.BooleanField(
        default=True,
        help_text="DDNS enable-updates value used by all peers in this HA relationship",
    )
    ddns_policy = models.ForeignKey(
        "DDNSPolicy",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ha_relationships",
        help_text=(
            "DDNS policy shared by all peers in this HA relationship. "
            "When set, overrides each member server's standalone ddns_policy."
        ),
    )

    class Meta:
        ordering = ("name",)
        verbose_name = "DHCP HA Relationship"
        verbose_name_plural = "DHCP HA Relationships"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_dhcp_kea_plugin:dhcpharelationship", args=[self.pk])

    def is_valid_configuration(self):
        """Validate the HA relationship configuration.

        Validates:
        - hot-standby: requires one primary and one standby server
        - load-balancing: requires one primary and one secondary server
        - passive-backup: requires at least one primary

        Returns:
            bool: True if configuration is valid, False otherwise
        """
        servers = self.servers.all()

        roles = [server.ha_role for server in servers]
        primary_count = roles.count("primary")
        secondary_count = roles.count("secondary")
        standby_count = roles.count("standby")

        if self.mode == "hot-standby":
            if primary_count != 1:
                return False
            if standby_count != 1:
                return False

        elif self.mode == "load-balancing":
            if primary_count != 1:
                return False
            if secondary_count != 1:
                return False

        elif self.mode == "passive-backup":
            if primary_count < 1:
                return False

        return True

    def to_kea_dict(self, this_server=None):
        """Generate KEA high-availability configuration.

        Args:
            this_server: The DHCPServer instance for which this config is being generated.
                        Used to set "this-server-name" in the configuration.

        Returns:
            dict: KEA high-availability hook library configuration
        """
        # Find this server's name
        this_server_name = None
        if this_server:
            this_server_name = this_server.name

        ha_config = {
            "this-server-name": this_server_name,
            "mode": self.mode,
            "heartbeat-delay": self.heartbeat_delay,
            "max-response-delay": self.max_response_delay,
            "max-ack-delay": self.max_ack_delay,
            "max-unacked-clients": self.max_unacked_clients,
            "max-rejected-lease-updates": self.max_rejected_lease_updates,
        }

        # Add multi-threading config if enabled
        if self.enable_multi_threading:
            ha_config["multi-threading"] = {
                "enable-multi-threading": True,
                "http-dedicated-listener": self.http_dedicated_listener,
                "http-listener-threads": self.http_listener_threads,
                "http-client-threads": self.http_client_threads,
            }

        # Add peers configuration (all servers in this relationship)
        peers_config = []
        for server in self.servers.select_related("ip_address"):
            peer_dict = {
                "name": server.name,
                "url": server.ha_url,
                "role": server.ha_role,
                "auto-failover": server.ha_auto_failover,
            }
            # Add basic auth if configured
            if server.ha_basic_auth_user:
                peer_dict["basic-auth-user"] = server.ha_basic_auth_user
            if server.ha_basic_auth_password:
                peer_dict["basic-auth-password"] = server.ha_basic_auth_password
            peers_config.append(peer_dict)

        ha_config["peers"] = peers_config

        return ha_config

    def get_primary_server(self):
        """Get the primary server in this HA relationship.

        Returns:
            DHCPServer: The primary server, or None if not found.
        """
        return self.servers.filter(ha_role="primary").first()

    def get_synced_subnet_count(self):
        """Get the number of subnets synced across this HA relationship.

        Returns:
            int: Number of subnets on the primary server.
        """
        primary = self.get_primary_server()
        if primary:
            return primary.subnet_items.count()
        return 0

    def get_synced_client_class_count(self):
        """Get the number of client classes synced across this HA relationship.

        Returns:
            int: Number of client classes on the primary server.
        """
        primary = self.get_primary_server()
        if primary:
            return primary.client_classes.count()
        return 0

    def get_synced_option_data_count(self):
        """Get the number of global option data synced across this HA relationship.

        Returns:
            int: Number of option data on the primary server.
        """
        primary = self.get_primary_server()
        if primary:
            return primary.option_data.count()
        return 0

    def migrate_configs_to_new_primary(self, new_primary_server):
        """Migrate all subnets, client classes, and options to a new primary server.

        Use this method when changing which server is the primary in an HA relationship.
        It transfers all DHCP configurations from the current primary to the new one.

        Args:
            new_primary_server: The DHCPServer that will become the new primary.

        Returns:
            dict: Summary of migrated items {'prefixes': int, 'client_classes': int, 'options': int}
        """
        current_primary = self.get_primary_server()
        if not current_primary or current_primary.pk == new_primary_server.pk:
            return {"prefixes": 0, "client_classes": 0, "options": 0}

        migrated = {"prefixes": 0, "client_classes": 0, "options": 0}

        # Migrate Subnets
        subnet_items = list(current_primary.subnet_items.all())
        for config in subnet_items:
            config.server = new_primary_server
            config.save()
            migrated["prefixes"] += 1

        # Migrate client classes (ManyToMany - need to update the servers relation)
        client_classes = list(current_primary.client_classes.all())
        for cc in client_classes:
            cc.servers.remove(current_primary)
            cc.servers.add(new_primary_server)
            migrated["client_classes"] += 1

        # Migrate global option data (ManyToMany)
        options = list(current_primary.option_data.all())
        for opt in options:
            current_primary.option_data.remove(opt)
            new_primary_server.option_data.add(opt)
            migrated["options"] += 1

        return migrated


STORK_LOG_LEVEL_CHOICES = (
    ("DEBUG", "Debug"),
    ("INFO", "Info"),
    ("WARN", "Warning"),
    ("ERROR", "Error"),
)


class StorkServer(NetBoxModel):
    """ISC Stork Server instance for centralized monitoring and management of KEA DHCP servers.

    The Stork Server provides a web UI and REST API for monitoring KEA DHCP operations,
    viewing leases, managing configurations, and integrating with Prometheus/Grafana.
    Stork Agents running alongside KEA servers connect back to this server.
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Name of this Stork server instance",
    )
    description = models.CharField(
        max_length=200,
        blank=True,
    )
    status = models.CharField(
        verbose_name=_("status"),
        max_length=50,
        choices=DeviceStatusChoices,
        default=DeviceStatusChoices.STATUS_ACTIVE,
        help_text="Operational status of this Stork server",
    )

    # --- Network / Connectivity ---
    ip_address = models.ForeignKey(
        IPAddress,
        on_delete=models.PROTECT,
        related_name="stork_servers",
        help_text="IP address of the Stork server (from NetBox IPAM)",
    )
    rest_port = models.PositiveIntegerField(
        default=8080,
        help_text="Port for the Stork REST API and Web UI (default: 8080)",
    )
    rest_base_url = models.CharField(
        max_length=255,
        blank=True,
        default="/",
        help_text="Base URL path if Stork UI is served from a subdirectory (e.g., /stork/)",
    )
    use_tls = models.BooleanField(
        default=False,
        help_text="Whether the Stork server REST API uses TLS/SSL",
    )

    # --- Database Connection (useful for Ansible deployment) ---
    db_host = models.CharField(
        max_length=255,
        default="localhost",
        help_text="PostgreSQL database host for Stork",
    )
    db_port = models.PositiveIntegerField(
        default=5432,
        help_text="PostgreSQL database port",
    )
    db_name = models.CharField(
        max_length=100,
        default="stork",
        help_text="PostgreSQL database name",
    )
    db_user = models.CharField(
        max_length=100,
        default="stork",
        help_text="PostgreSQL database user name",
    )
    DB_SSL_MODE_CHOICES = (
        ("disable", "Disable"),
        ("require", "Require"),
        ("verify-ca", "Verify CA"),
        ("verify-full", "Verify Full"),
    )
    db_ssl_mode = models.CharField(
        max_length=20,
        choices=DB_SSL_MODE_CHOICES,
        default="disable",
        help_text="SSL mode for the database connection",
    )

    # --- Prometheus / Metrics ---
    enable_metrics = models.BooleanField(
        default=False,
        help_text="Enable the Prometheus /metrics endpoint on the Stork server",
    )

    # --- Grafana Integration ---
    grafana_url = models.URLField(
        blank=True,
        help_text="URL of the Grafana instance integrated with this Stork server",
    )

    # --- Agent Registration ---
    AGENT_AUTH_CHOICES = (
        ("agent-token", "Agent Token (manual approval in UI)"),
        ("server-token", "Server Token (auto-approval)"),
    )
    default_agent_registration = models.CharField(
        max_length=20,
        choices=AGENT_AUTH_CHOICES,
        default="agent-token",
        help_text="Default method for registering new Stork agents",
    )

    # --- Versioning ---
    stork_version = models.CharField(
        max_length=20,
        default="stable",
        blank=True,
        help_text="Stork server version (e.g., 1.18.0 or 'stable')",
    )

    # --- Logging ---
    log_level = models.CharField(
        max_length=10,
        choices=STORK_LOG_LEVEL_CHOICES,
        default="INFO",
        help_text="Logging level for the Stork server (DEBUG, INFO, WARN, ERROR)",
    )

    class Meta:
        ordering = ("name",)
        verbose_name = "Stork Server"
        verbose_name_plural = "Stork Servers"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_dhcp_kea_plugin:storkserver", args=[self.pk])

    def get_status_color(self):
        """Return the color associated with the current status for badge display."""
        return DeviceStatusChoices.colors.get(self.status, "secondary")

    def to_env_content(self):
        """Generate Stork Server environment variable file content.

        Produces the content for /etc/stork/server.env used by the
        stork-server systemd service.

        Returns:
            str: The environment file content.
        """
        lines = []
        ip = str(self.ip_address).split("/")[0]

        # --- Database settings ---
        lines.append("### database settings")
        lines.append("### the address of a PostgreSQL database")
        lines.append(f"STORK_DATABASE_HOST={self.db_host}")
        lines.append("### the port of a PostgreSQL database")
        lines.append(f"STORK_DATABASE_PORT={self.db_port}")
        lines.append("### the name of a database")
        lines.append(f"STORK_DATABASE_NAME={self.db_name}")
        lines.append("### the user name for connecting to the database")
        lines.append(f"STORK_DATABASE_USER_NAME={self.db_user}")
        lines.append("### the SSL mode for connecting to the database")
        lines.append(f"STORK_DATABASE_SSLMODE={self.db_ssl_mode}")
        lines.append("")

        # --- REST API settings ---
        lines.append("### REST API settings")
        lines.append("### the IP address on which the server listens")
        lines.append(f"STORK_REST_HOST={ip}")
        lines.append("### the port number on which the server listens")
        lines.append(f"STORK_REST_PORT={self.rest_port}")
        lines.append("### the directory with static files served in the UI")
        lines.append("STORK_REST_STATIC_FILES_DIR=/usr/share/stork/www")
        lines.append("")

        # --- Metrics ---
        lines.append("### enable Prometheus /metrics HTTP endpoint for exporting metrics from")
        lines.append("### the server to Prometheus.")
        enable_metrics = "true" if self.enable_metrics else "false"
        lines.append(f"STORK_SERVER_ENABLE_METRICS={enable_metrics}")
        lines.append("")

        # --- Logging ---
        lines.append("### Logging parameters")
        lines.append("### Set logging level. Supported values are: DEBUG, INFO, WARN, ERROR")
        lines.append(f"STORK_LOG_LEVEL={self.log_level}")
        lines.append("")

        return "\n".join(lines)

    @property
    def url(self):
        """Construct the full Stork server URL."""
        scheme = "https" if self.use_tls else "http"
        ip = str(self.ip_address).split("/")[0]  # strip CIDR notation
        base = self.rest_base_url.rstrip("/")
        return f"{scheme}://{ip}:{self.rest_port}{base}"


class StorkAgentGroup(NetBoxModel):
    """Configuration profile for Stork Agents running alongside KEA DHCP servers.

    Rather than creating individual agent records for each KEA server, this model
    defines a shared configuration profile (agent port, exporter settings, operating
    mode) that applies to all assigned DHCP servers. This follows the same pattern
    as HookGroup — a configuration group linked to many servers.

    The Stork Agent runs on the same machine as KEA and serves two roles:
    1. Communication with the Stork Server (gRPC) for monitoring/management
    2. Prometheus exporter that converts KEA statistics into Prometheus metrics

    These roles can be enabled independently via the operating_mode field.
    """

    OPERATING_MODE_CHOICES = (
        ("both", "Stork + Prometheus"),
        ("prometheus-only", "Prometheus Only"),
        ("stork-only", "Stork Only"),
    )

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Name of this Stork agent configuration group",
    )
    description = models.TextField(
        blank=True,
        help_text="Description of this agent group configuration",
    )

    # --- Stork Server association (optional — not needed for prometheus-only mode) ---
    stork_server = models.ForeignKey(
        StorkServer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agent_groups",
        help_text="The Stork server these agents report to (not required for Prometheus-only mode)",
    )

    # --- Operating Mode ---
    operating_mode = models.CharField(
        max_length=20,
        choices=OPERATING_MODE_CHOICES,
        default="both",
        help_text="Agent operating mode: both roles, Prometheus exporter only, or Stork communication only",
    )

    # --- Agent gRPC settings ---
    agent_port = models.PositiveIntegerField(
        default=8080,
        help_text="Port the Stork agent listens on for gRPC connections from the server (default: 8080)",
    )

    # --- Prometheus Exporter settings ---
    # These are optional: only required when operating_mode includes Prometheus
    # (i.e., "both" or "prometheus-only"). The Stork Agent exposes a single
    # Prometheus exporter endpoint regardless of whether it exports KEA or BIND9 stats.
    prometheus_exporter_address = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="IP address or hostname for the Prometheus exporter to listen on (e.g., 0.0.0.0). "
        "Required when operating mode includes Prometheus.",
    )
    prometheus_exporter_port = models.PositiveIntegerField(
        null=True,
        blank=True,
        default=None,
        help_text="Port for the Prometheus statistics exporter (e.g., 9547). "
        "Required when operating mode includes Prometheus.",
    )
    prometheus_per_subnet_stats = models.BooleanField(
        default=True,
        help_text="Enable per-subnet statistics export to Prometheus (disable for very large networks)",
    )

    # --- TLS / Security ---
    skip_tls_cert_verification = models.BooleanField(
        default=False,
        help_text="Skip TLS certificate verification when the agent connects to Kea over TLS with self-signed certificates",
    )

    # --- Logging ---
    log_level = models.CharField(
        max_length=10,
        choices=STORK_LOG_LEVEL_CHOICES,
        default="INFO",
        help_text="Logging level for the Stork agent (DEBUG, INFO, WARN, ERROR)",
    )

    class Meta:
        ordering = ("name",)
        verbose_name = "Stork Agent Group"
        verbose_name_plural = "Stork Agent Groups"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_dhcp_kea_plugin:storkagentgroup", args=[self.pk])

    def clean(self):
        """Validate conditional field requirements based on operating mode."""
        super().clean()
        errors = {}

        # Stork Server is required when operating mode includes Stork communication
        if self.operating_mode in ("both", "stork-only") and not self.stork_server:
            errors["stork_server"] = "A Stork Server is required when operating mode includes Stork communication."

        # Prometheus exporter address and port are required when mode includes Prometheus
        if self.operating_mode in ("both", "prometheus-only"):
            if not self.prometheus_exporter_address:
                errors["prometheus_exporter_address"] = (
                    "Prometheus exporter address is required when operating mode includes Prometheus."
                )
            if not self.prometheus_exporter_port:
                errors["prometheus_exporter_port"] = (
                    "Prometheus exporter port is required when operating mode includes Prometheus."
                )
            elif self.prometheus_exporter_port == self.agent_port:
                errors["prometheus_exporter_port"] = "Prometheus exporter port must be different from the agent port."

        if errors:
            raise ValidationError(errors)

    def to_env_content(self, server=None):
        """Generate Stork Agent environment variable file content.

        Produces the content for /etc/stork/agent.env used by the
        stork-agent systemd service.  When *server* is given the
        STORK_AGENT_HOST line is set to that server's IP; otherwise
        a ``<AGENT_HOST_IP>`` placeholder is emitted.

        Args:
            server: Optional DHCPServer instance whose IP address will
                    be used for STORK_AGENT_HOST.

        Returns:
            str: The environment file content.
        """
        lines = []

        # --- Agent host / port ---
        if server:
            host_ip = str(server.ip_address).split("/")[0]
        else:
            host_ip = "<AGENT_HOST_IP>"

        lines.append("### the IP or hostname to listen on for incoming Stork server connections")
        lines.append(f"STORK_AGENT_HOST={host_ip}")
        lines.append("")
        lines.append("### the TCP port to listen on for incoming Stork server connections")
        lines.append(f"STORK_AGENT_PORT={self.agent_port}")
        lines.append("")

        # --- Prometheus exporter settings ---
        if self.operating_mode in ("both", "prometheus-only"):
            lines.append("### settings for exporting stats to Prometheus")
            lines.append("### the IP or hostname on which the agent exports Kea statistics to Prometheus")
            lines.append(f"STORK_AGENT_PROMETHEUS_KEA_EXPORTER_ADDRESS={self.prometheus_exporter_address}")
            lines.append("### the port on which the agent exports Kea statistics to Prometheus")
            lines.append(f"STORK_AGENT_PROMETHEUS_KEA_EXPORTER_PORT={self.prometheus_exporter_port}")
            lines.append("## enable or disable collecting per-subnet stats from Kea")
            per_subnet = "true" if self.prometheus_per_subnet_stats else "false"
            lines.append(f"STORK_AGENT_PROMETHEUS_KEA_EXPORTER_PER_SUBNET_STATS={per_subnet}")
            lines.append("")

        # --- Stork Server URL ---
        if self.stork_server:
            lines.append(
                "### Stork Server URL used by the agent to send REST commands to the server during agent registration"
            )
            lines.append(f"STORK_AGENT_SERVER_URL={self.stork_server.url}")
            lines.append("")

        # --- Skip TLS cert verification ---
        if self.skip_tls_cert_verification:
            lines.append("### Skip TLS certificate verification for connections to Kea over TLS")
            lines.append("STORK_AGENT_SKIP_TLS_CERT_VERIFICATION=true")
            lines.append("")

        # --- Logging ---
        lines.append("### Logging parameters")
        lines.append("### Set logging level. Supported values are: DEBUG, INFO, WARN, ERROR")
        lines.append(f"STORK_LOG_LEVEL={self.log_level}")
        lines.append("")

        return "\n".join(lines)

    @property
    def server_url(self):
        """Return the Stork server URL if configured, for agent registration."""
        if self.stork_server:
            return self.stork_server.url
        return None


# ---------------------------------------------------------------------------
# DDNS (kea-dhcp-ddns / D2) — models
# ---------------------------------------------------------------------------

TSIG_ALGORITHM_CHOICES = (
    ("HMAC-MD5", "HMAC-MD5"),
    ("HMAC-SHA1", "HMAC-SHA1"),
    ("HMAC-SHA224", "HMAC-SHA224"),
    ("HMAC-SHA256", "HMAC-SHA256"),
    ("HMAC-SHA384", "HMAC-SHA384"),
    ("HMAC-SHA512", "HMAC-SHA512"),
)

TSIG_SECRET_BACKEND_CHOICES = (
    ("plaintext", "Plaintext (stored in NetBox DB)"),
    ("vault", "HashiCorp Vault (by path reference)"),
)

NCR_PROTOCOL_CHOICES = (
    ("UDP", "UDP"),
    ("TCP", "TCP"),
)

NCR_FORMAT_CHOICES = (("JSON", "JSON"),)

DDNS_REPLACE_CLIENT_NAME_CHOICES = (
    ("never", "never"),
    ("always", "always"),
    ("when-present", "when-present"),
    ("when-not-present", "when-not-present"),
)

# Kea 3.0+ — ddns-conflict-resolution-mode replaces the deprecated
# boolean ddns-use-conflict-resolution. Do not emit the deprecated alias.
DDNS_CONFLICT_RESOLUTION_MODE_CHOICES = (
    ("check-with-dhcid", "check-with-dhcid"),
    ("no-check-with-dhcid", "no-check-with-dhcid"),
    ("check-exists-with-dhcid", "check-exists-with-dhcid"),
    ("no-check-without-dhcid", "no-check-without-dhcid"),
)


class TSIGKey(NetBoxModel):
    """RFC 2845 TSIG key used to authenticate DNS UPDATE messages sent by D2.

    Secret storage is delegated to a pluggable backend (see
    ``secret_backends.py``) so the v1 plaintext model can be replaced later
    by Vault / external secret retrieval without any schema change.
    """

    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="TSIG key name as it appears in Kea (e.g. 'd2.example.com.')",
    )
    description = models.CharField(max_length=200, blank=True)
    algorithm = models.CharField(
        max_length=20,
        choices=TSIG_ALGORITHM_CHOICES,
        default="HMAC-SHA256",
        help_text="TSIG HMAC algorithm",
    )
    digest_bits = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Truncated digest length in bits (optional; default is full length)",
    )
    secret_backend = models.CharField(
        max_length=20,
        choices=TSIG_SECRET_BACKEND_CHOICES,
        default="plaintext",
        help_text="Where the raw secret is sourced from at config-emission time",
    )
    secret_plaintext = models.CharField(
        max_length=512,
        blank=True,
        default="",
        help_text=(
            "Base64-encoded TSIG secret (used when backend is 'plaintext'). "
            "Leave blank or enter any non-base64 text to auto-generate a fresh "
            "random secret matching the selected algorithm."
        ),
    )
    secret_ref = models.CharField(
        max_length=512,
        blank=True,
        default="",
        help_text="External reference (e.g. Vault path) — used when backend is non-plaintext",
    )

    class Meta:
        ordering = ("name",)
        verbose_name = "TSIG Key"
        verbose_name_plural = "TSIG Keys"
        permissions = [
            ("view_secret_tsigkey", "Can view TSIG key plaintext secret"),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_dhcp_kea_plugin:tsigkey", args=[self.pk])

    _ALGORITHM_BYTE_LEN = {
        "HMAC-MD5": 16,
        "HMAC-SHA1": 20,
        "HMAC-SHA224": 28,
        "HMAC-SHA256": 32,
        "HMAC-SHA384": 48,
        "HMAC-SHA512": 64,
    }

    def _generate_secret(self):
        import base64 as _base64
        import secrets as _secrets

        nbytes = self._ALGORITHM_BYTE_LEN.get(self.algorithm, 32)
        return _base64.b64encode(_secrets.token_bytes(nbytes)).decode()

    def _normalize_secret(self):
        """If plaintext secret isn't valid base64 of the algorithm's natural
        length, replace it with a freshly generated one. Idempotent."""
        if self.secret_backend != "plaintext":
            return
        import base64 as _base64
        import binascii as _binascii

        expected_len = self._ALGORITHM_BYTE_LEN.get(self.algorithm)
        if self.secret_plaintext:
            try:
                decoded = _base64.b64decode(self.secret_plaintext, validate=True)
                if expected_len is None or len(decoded) == expected_len:
                    return
            except (_binascii.Error, ValueError):
                pass
        self.secret_plaintext = self._generate_secret()

    def save(self, *args, **kwargs):
        self._normalize_secret()
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        errors = {}

        if self.secret_backend == "plaintext":
            self._normalize_secret()
        else:
            if not self.secret_ref:
                errors["secret_ref"] = f"Backend '{self.secret_backend}' requires a reference."

        # Digest-bits must be a positive multiple of 8 when set, and never
        # exceed the underlying algorithm's natural output.
        if self.digest_bits is not None:
            if self.digest_bits <= 0 or self.digest_bits % 8:
                errors["digest_bits"] = "digest_bits must be a positive multiple of 8."
            max_bits = {
                "HMAC-MD5": 128,
                "HMAC-SHA1": 160,
                "HMAC-SHA224": 224,
                "HMAC-SHA256": 256,
                "HMAC-SHA384": 384,
                "HMAC-SHA512": 512,
            }.get(self.algorithm)
            if max_bits and self.digest_bits > max_bits:
                errors["digest_bits"] = f"digest_bits ({self.digest_bits}) exceeds algorithm output size ({max_bits})."

        if errors:
            raise ValidationError(errors)

    def get_secret(self):
        """Resolve the raw (base64) secret via the configured backend."""
        from .secret_backends import resolve_secret

        return resolve_secret(self)

    def to_kea_dict(self):
        """Emit the Kea tsig-keys entry for this key.

        Only called at config-emission time — the caller is expected to have
        the ``view_secret_tsigkey`` permission or to be rendering to a
        deployment pipeline.
        """
        entry = {
            "name": self.name,
            "algorithm": self.algorithm.lower(),
            "secret": self.get_secret(),
        }
        if self.digest_bits:
            entry["digest-bits"] = self.digest_bits
        return entry


class D2Daemon(NetBoxModel):
    """A kea-dhcp-ddns (D2) daemon instance.

    Models the listener socket, control socket, and NCR (NameChangeRequest)
    transport for one D2 process. DDNSDomain rows attached to this daemon
    become entries under ``forward-ddns.ddns-domains`` / ``reverse-ddns.ddns-domains``
    in the emitted ``kea-dhcp-ddns.conf``.
    """

    LISTENER_MODE_LOCAL = "local"
    LISTENER_MODE_REMOTE = "remote"
    LISTENER_MODE_CHOICES = (
        (LISTENER_MODE_LOCAL, "Local (127.0.0.1, deployed per peer)"),
        (LISTENER_MODE_REMOTE, "Remote (single shared instance)"),
    )

    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=200, blank=True)
    listener_mode = models.CharField(
        max_length=10,
        choices=LISTENER_MODE_CHOICES,
        default=LISTENER_MODE_LOCAL,
        help_text=(
            "'Local' renders ip-address=127.0.0.1; deploy one D2 instance "
            "on every host running kea-dhcp4/6 that uses this row. "
            "'Remote' uses the IPAM-tracked listener address."
        ),
    )
    ip_address = models.ForeignKey(
        IPAddress,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="d2_daemons",
        help_text="IP address the D2 daemon listens on (required only when listener_mode is 'remote')",
    )
    port = models.PositiveIntegerField(
        default=53001,
        help_text="Port the D2 daemon listens on (default: 53001)",
    )
    control_socket_path = models.CharField(
        max_length=512,
        blank=True,
        default="",
        help_text="Unix domain socket path for D2 control channel (optional)",
    )
    ncr_protocol = models.CharField(
        max_length=3,
        choices=NCR_PROTOCOL_CHOICES,
        default="UDP",
        help_text="NameChangeRequest transport protocol",
    )
    ncr_format = models.CharField(
        max_length=4,
        choices=NCR_FORMAT_CHOICES,
        default="JSON",
        help_text="NameChangeRequest wire format",
    )

    class Meta:
        ordering = ("name",)
        verbose_name = "D2 Daemon"
        verbose_name_plural = "D2 Daemons"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_dhcp_kea_plugin:d2daemon", args=[self.pk])

    def clean(self):
        super().clean()
        if self.listener_mode == self.LISTENER_MODE_REMOTE and self.ip_address is None:
            from django.core.exceptions import ValidationError

            raise ValidationError(
                {"ip_address": "Required when listener mode is 'remote'."}
            )

    @property
    def listener_ip(self):
        if self.listener_mode == self.LISTENER_MODE_LOCAL:
            return "127.0.0.1"
        if self.ip_address is None:
            return None
        return str(self.ip_address.address.ip)

    def to_kea_dict(self):
        """Emit a full ``kea-dhcp-ddns.conf`` dictionary for this D2 daemon.

        Domains are partitioned into forward/reverse based on the zone name
        (``.in-addr.arpa`` or ``.ip6.arpa`` ⇒ reverse).
        """
        forward_domains = []
        reverse_domains = []
        tsig_keys = {}

        for domain in self.domains.select_related("zone", "tsig_key").prefetch_related("zone__nameservers"):
            domain_dict = domain.to_kea_dict()
            if domain.is_reverse:
                reverse_domains.append(domain_dict)
            else:
                forward_domains.append(domain_dict)
            if domain.tsig_key_id and domain.tsig_key.name not in tsig_keys:
                tsig_keys[domain.tsig_key.name] = domain.tsig_key.to_kea_dict()

        dhcp_ddns = {
            "ip-address": self.listener_ip,
            "port": self.port,
            "ncr-protocol": self.ncr_protocol,
            "ncr-format": self.ncr_format,
        }
        if self.control_socket_path:
            dhcp_ddns["control-socket"] = {
                "socket-type": "unix",
                "socket-name": self.control_socket_path,
            }
        if tsig_keys:
            dhcp_ddns["tsig-keys"] = list(tsig_keys.values())
        dhcp_ddns["forward-ddns"] = {"ddns-domains": forward_domains}
        dhcp_ddns["reverse-ddns"] = {"ddns-domains": reverse_domains}

        return {"DhcpDdns": dhcp_ddns}


class DDNSDomain(NetBoxModel):
    """A single forward or reverse DDNS domain entry on a D2 daemon.

    Direction (forward vs reverse) is **derived** from the linked netbox-dns
    Zone's name — a zone ending in ``.in-addr.arpa`` or ``.ip6.arpa`` is
    reverse. This avoids the footgun of the direction field drifting out of
    sync with the zone.
    """

    d2_daemon = models.ForeignKey(
        "D2Daemon",
        on_delete=models.CASCADE,
        related_name="domains",
        help_text="The D2 daemon that handles this domain",
    )
    # Zone and NameServer are FK'd through django's string-form model
    # references with db_constraint=False so the plugin still migrates
    # cleanly when netbox_dns isn't installed. Startup gating in
    # __init__.py blocks enable_ddns=True without netbox_dns, so these
    # columns are only ever populated when netbox_dns is present.
    zone = models.ForeignKey(
        "netbox_dns.Zone",
        on_delete=models.PROTECT,
        related_name="+",
        db_constraint=False,
        help_text="Forward or reverse zone that this domain serves",
    )
    tsig_key = models.ForeignKey(
        "TSIGKey",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="domains",
        help_text="TSIG key for authenticating updates (optional)",
    )

    class Meta:
        ordering = ("d2_daemon", "zone")
        verbose_name = "DDNS Domain"
        verbose_name_plural = "DDNS Domains"
        unique_together = (("d2_daemon", "zone"),)

    def __str__(self):
        return f"{self.zone} @ {self.d2_daemon}"

    def get_absolute_url(self):
        return reverse("plugins:netbox_dhcp_kea_plugin:ddnsdomain", args=[self.pk])

    @property
    def is_reverse(self):
        if self.zone_id is None:
            return False
        name = (self.zone.name or "").rstrip(".").lower()
        return (
            name.endswith(".in-addr.arpa")
            or name.endswith(".ip6.arpa")
            or name
            in (
                "in-addr.arpa",
                "ip6.arpa",
            )
        )

    @staticmethod
    def _resolve_nameserver_ips(ns_name):
        """Resolve a nameserver FQDN to its A/AAAA IPs via netbox_dns.

        Returns a list of IP strings (may be empty if no records exist or
        netbox_dns isn't installed).
        """
        try:
            from netbox_dns.models import Record as DNSRecord
        except ImportError:
            return []

        fqdn = ns_name if ns_name.endswith(".") else f"{ns_name}."
        ips = []
        for rec in DNSRecord.objects.filter(fqdn=fqdn, type__in=("A", "AAAA")):
            value = rec.value
            if value and value not in ips:
                ips.append(value)
        return ips

    def to_kea_dict(self):
        """Emit a single ddns-domains entry.

        ``dns-servers`` is derived from ``zone.nameservers`` — for each
        NameServer the linked A/AAAA records in netbox_dns are resolved to
        IPs. Nameservers with no resolvable IPs are silently skipped (Kea
        requires IPs, not hostnames).
        """
        zone_name = self.zone.name
        if not zone_name.endswith("."):
            zone_name = zone_name + "."

        dns_servers = []
        for ns in self.zone.nameservers.all():
            for ip in self._resolve_nameserver_ips(ns.name):
                dns_servers.append({"ip-address": ip, "port": 53})

        entry = {
            "name": zone_name,
            "dns-servers": dns_servers,
        }
        if self.tsig_key_id:
            entry["key-name"] = self.tsig_key.name
        return entry


class DDNSPolicy(NetBoxModel):
    """A reusable set of ``ddns-*`` override keys.

    Attachable at any of server / subnet / client-class. Only non-null
    fields are emitted at config-generation time — the Kea resolver itself
    walks the override chain when processing packets. The plugin does
    **not** merge layers in Python.
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=200, blank=True)

    # Field name → Kea key mapping is done by to_kea_overrides() below.
    ddns_send_updates = models.BooleanField(null=True, blank=True)
    ddns_override_no_update = models.BooleanField(null=True, blank=True)
    ddns_override_client_update = models.BooleanField(null=True, blank=True)
    ddns_replace_client_name = models.CharField(
        max_length=20,
        choices=DDNS_REPLACE_CLIENT_NAME_CHOICES,
        blank=True,
        default="",
        help_text="When Kea should replace the client-supplied FQDN",
    )
    ddns_generated_prefix = models.CharField(max_length=255, blank=True, default="")
    ddns_qualifying_suffix = models.CharField(max_length=255, blank=True, default="")
    hostname_char_set = models.CharField(max_length=255, blank=True, default="")
    hostname_char_replacement = models.CharField(max_length=255, blank=True, default="")
    ddns_update_on_renew = models.BooleanField(null=True, blank=True)
    ddns_conflict_resolution_mode = models.CharField(
        max_length=32,
        choices=DDNS_CONFLICT_RESOLUTION_MODE_CHOICES,
        blank=True,
        default="",
        help_text="Kea 3.0+ conflict resolution mode (replaces ddns-use-conflict-resolution)",
    )
    ddns_ttl_percent = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="TTL as a fraction of lease lifetime (e.g. 0.3333 → 33%)",
    )
    ddns_ttl = models.PositiveIntegerField(null=True, blank=True)
    ddns_ttl_min = models.PositiveIntegerField(null=True, blank=True)
    ddns_ttl_max = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "DDNS Policy"
        verbose_name_plural = "DDNS Policies"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_dhcp_kea_plugin:ddnspolicy", args=[self.pk])

    # Kea key names are the kebab-cased Django field names — list the
    # mapping explicitly for any that don't map trivially.
    _KEA_FIELD_MAP = (
        ("ddns_send_updates", "ddns-send-updates"),
        ("ddns_override_no_update", "ddns-override-no-update"),
        ("ddns_override_client_update", "ddns-override-client-update"),
        ("ddns_replace_client_name", "ddns-replace-client-name"),
        ("ddns_generated_prefix", "ddns-generated-prefix"),
        ("ddns_qualifying_suffix", "ddns-qualifying-suffix"),
        ("hostname_char_set", "hostname-char-set"),
        ("hostname_char_replacement", "hostname-char-replacement"),
        ("ddns_update_on_renew", "ddns-update-on-renew"),
        ("ddns_conflict_resolution_mode", "ddns-conflict-resolution-mode"),
        ("ddns_ttl_percent", "ddns-ttl-percent"),
        ("ddns_ttl", "ddns-ttl"),
        ("ddns_ttl_min", "ddns-ttl-min"),
        ("ddns_ttl_max", "ddns-ttl-max"),
    )

    def to_kea_overrides(self):
        """Return only the non-null/non-blank keys, kebab-cased for Kea.

        String fields use ``""`` to mean "not set" (so they can round-trip
        through CharField without null=True quirks). Decimals are emitted
        as floats to match Kea's JSON schema.
        """
        result = {}
        for field_name, kea_key in self._KEA_FIELD_MAP:
            value = getattr(self, field_name)
            if value is None:
                continue
            if isinstance(value, str) and value == "":
                continue
            if field_name == "ddns_ttl_percent":
                value = float(value)
            result[kea_key] = value
        return result
