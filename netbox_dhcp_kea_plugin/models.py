from dcim.models import Manufacturer
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from ipam.models import IPAddress, Prefix, Service, ServiceTemplate
from netbox.models import NetBoxModel


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
    is_active = models.BooleanField(default=True, help_text="Is this server active?")
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
    ha_url = models.URLField(
        blank=True,
        help_text="URL for HA communication (e.g., http://192.168.1.1:8000/)",
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

    def clean(self):
        """Validate HA configuration."""
        super().clean()

        # If ha_relationship is set, ha_role and ha_url are required
        if self.ha_relationship:
            if not self.ha_role:
                raise ValidationError({"ha_role": "HA role is required when server is part of an HA relationship."})
            if not self.ha_url:
                raise ValidationError({"ha_url": "HA URL is required when server is part of an HA relationship."})

        # If changing from primary to another role, check for orphaned configs
        if self.pk:
            try:
                old_server = DHCPServer.objects.get(pk=self.pk)
                if old_server.ha_role == "primary" and self.ha_role != "primary":
                    prefix_count = self.prefix_configs.count()
                    class_count = self.client_classes.count()
                    option_count = self.option_data.count()

                    if prefix_count > 0 or class_count > 0 or option_count > 0:
                        raise ValidationError(
                            f"Cannot change role from Primary: server '{self.name}' has "
                            f"{prefix_count} prefix config(s), {class_count} client class(es), and "
                            f"{option_count} option data assigned. Use 'Migrate Configs to New Primary' "
                            f"on the HA Relationship to transfer these to the new primary first."
                        )
            except DHCPServer.DoesNotExist:
                pass

    def get_ha_config(self):
        """Generate HA configuration if this server is part of an HA relationship.

        Returns:
            dict: KEA high-availability configuration, or None if not in HA.
        """
        if not self.ha_relationship:
            return None

        return self.ha_relationship.to_kea_dict(this_server=self)

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

    def is_ha_primary(self):
        """Check if this server is the primary in its HA relationship.

        Returns:
            bool: True if primary or not in HA, False if secondary/standby/backup.
        """
        if not self.ha_relationship:
            return True  # Not in HA, treat as primary
        return self.ha_role == "primary"

    def get_effective_prefix_configs(self):
        """Get prefix configs for this server, including from HA primary if applicable.

        In HA mode, all servers serve the same subnets (from primary's config).

        Returns:
            QuerySet: PrefixDHCPConfig instances this server should serve.
        """
        if not self.ha_relationship:
            # Not in HA, return own configs
            return self.prefix_configs.all()

        # In HA, get configs from the primary server
        primary_server = self.ha_relationship.servers.filter(ha_role="primary").first()
        if primary_server:
            return primary_server.prefix_configs.all()

        # Fallback to own configs if no primary found
        return self.prefix_configs.all()

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
            }
        }

        dhcp4 = result["Dhcp4"]

        # Use effective methods that respect HA configuration
        effective_prefix_configs = self.get_effective_prefix_configs()
        effective_client_classes = self.get_effective_client_classes()
        effective_option_data = self.get_effective_option_data()

        # Collect all option data and their definitions from all sources
        all_option_data = set()
        vendor_spaces = set()

        # From prefix configs (using effective configs for HA)
        for prefix_config in effective_prefix_configs:
            for opt in prefix_config.option_data.all():
                all_option_data.add(opt)
                if opt.vendor_option_space:
                    vendor_spaces.add(opt.vendor_option_space)
            for cc in prefix_config.client_classes.all():
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

        # Collect definitions that are included locally in client classes (local_definitions=True)
        # These should NOT be included in the global option-def
        local_definitions = set()
        for cc in effective_client_classes.filter(local_definitions=True):
            for definition in cc.get_option_definitions():
                local_definitions.add(definition.pk)
        for prefix_config in effective_prefix_configs:
            for cc in prefix_config.client_classes.filter(local_definitions=True):
                for definition in cc.get_option_definitions():
                    local_definitions.add(definition.pk)

        # Collect ALL option definitions needed (vendor + standard custom)
        option_defs = []
        seen_definitions = set()

        # From vendor spaces
        for vs in vendor_spaces:
            for definition in vs.option_definitions.exclude(pk__in=local_definitions):
                if definition.pk not in seen_definitions:
                    seen_definitions.add(definition.pk)
                    option_defs.append(definition.to_kea_dict())

        # From option data that uses custom (non-standard) definitions in dhcp4/dhcp6 space
        for opt in all_option_data:
            if opt.definition and opt.definition.pk not in local_definitions:
                definition = opt.definition
                # Include if it's a custom definition (not standard) and not already added
                if not definition.is_standard and definition.pk not in seen_definitions:
                    seen_definitions.add(definition.pk)
                    option_defs.append(definition.to_kea_dict())

        if option_defs:
            dhcp4["option-def"] = option_defs

        # Collect all client-classes from prefix configs and server-level (using effective)
        all_client_classes = set()
        for prefix_config in effective_prefix_configs:
            for cc in prefix_config.client_classes.all():
                all_client_classes.add(cc)
        # Add client classes directly linked to this server (using effective)
        for cc in effective_client_classes:
            all_client_classes.add(cc)

        # Add client-classes
        if all_client_classes:
            dhcp4["client-classes"] = [cc.to_kea_dict() for cc in all_client_classes]

        # Add subnets (subnet4) - using effective prefix configs for HA
        subnets = []
        for prefix_config in effective_prefix_configs:
            # Only include IPv4 prefixes
            if prefix_config.prefix.prefix.version == 4:
                subnets.append(prefix_config.to_kea_dict())

        if subnets:
            dhcp4["subnet4"] = subnets

        # Add HA hooks-libraries if this server is part of an HA relationship
        ha_config = self.get_ha_config()
        if ha_config:
            dhcp4["hooks-libraries"] = [
                {"library": "/usr/lib/kea/hooks/libdhcp_lease_cmds.so"},
                {
                    "library": "/usr/lib/kea/hooks/libdhcp_ha.so",
                    "parameters": {"high-availability": [ha_config]},
                },
            ]

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

    @property
    def space_name(self):
        """Return the effective space name for KEA config"""
        if self.vendor_option_space:
            return self.vendor_option_space.name
        return self.option_space

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
    data = models.TextField(help_text="Option value/data")
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
            except ValueError:
                raise ValidationError(
                    {
                        "data": 'When CSV format is disabled, data must be a valid hexadecimal string (e.g., "48656C6C6F" or "48:65:6C:6C:6F").'
                    }
                )
        # If referencing a definition, sync the space info
        if self.definition:
            if self.definition.vendor_option_space and not self.vendor_option_space:
                self.vendor_option_space = self.definition.vendor_option_space

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
        """Return hex data converted to ASCII (only meaningful when csv_format is False)"""
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

        # Add data
        result["data"] = self.data

        # Add optional fields
        if self.always_send:
            result["always-send"] = True
        if not self.csv_format:
            result["csv-format"] = False

        return result


class ClientClass(NetBoxModel):
    """DHCP Client Classification (KEA client-classes)

    Client classes allow conditional assignment of options based on
    client characteristics using KEA's flexible test expressions.
    """

    name = models.CharField(max_length=100, unique=True)
    test_expression = models.TextField(
        help_text="KEA test expression for client classification (e.g., \"option[60].text == 'MS-UC-Client'\")"
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
    local_definitions = models.BooleanField(
        default=False,
        help_text="Include option definitions locally in this class config (otherwise they go to global option-def)",
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
        - has_option43_data(): includes vendor-encapsulated-options definition
        - local_definitions=True: additionally includes actual option definitions

        Args:
            ascii_format: Not used here, but kept for consistency with get_kea_option_data

        Returns:
            List of option-def dictionaries, or empty list if none
        """
        option_defs = []

        # Always add vendor-encapsulated-options when we have option43 data
        if self.has_option43_data():
            for vendor_space in self.get_option43_vendor_spaces():
                option_defs.append(
                    {
                        "name": "vendor-encapsulated-options",
                        "code": 43,
                        "type": "empty",
                        "encapsulate": vendor_space.name,
                    }
                )

        # Add actual option definitions if local_definitions is enabled
        if self.local_definitions:
            for definition in self.get_option_definitions():
                opt_def = {
                    "name": definition.name,
                    "code": definition.code,
                    "type": definition.option_type,
                }
                if definition.is_array:
                    opt_def["array"] = True
                if definition.encapsulate:
                    opt_def["encapsulate"] = definition.encapsulate
                if definition.record_types:
                    opt_def["record-types"] = definition.record_types
                if definition.vendor_option_space:
                    opt_def["space"] = definition.vendor_option_space.name
                option_defs.append(opt_def)

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
                opt_dict["csv-format"] = True
            else:
                opt_dict["data"] = opt.data
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
            "test": self.test_expression,
        }

        # Add option-def if any
        option_defs = self.get_kea_option_defs()
        if option_defs:
            result["option-def"] = option_defs

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


class PrefixDHCPConfig(NetBoxModel):
    """DHCP configuration for NetBox Prefixes (KEA subnet configuration)"""

    prefix = models.OneToOneField(Prefix, on_delete=models.CASCADE, related_name="dhcp_config")
    server = models.ForeignKey(DHCPServer, on_delete=models.PROTECT, related_name="prefix_configs")
    option_data = models.ManyToManyField(
        OptionData,
        blank=True,
        related_name="prefix_configs",
        help_text="Option data for this subnet",
    )
    client_classes = models.ManyToManyField(ClientClass, blank=True, related_name="prefix_configs")
    valid_lifetime = models.PositiveIntegerField(default=3600, help_text="Lease valid lifetime in seconds")
    max_lifetime = models.PositiveIntegerField(default=7200, help_text="Maximum lease lifetime in seconds")
    routers_option_offset = models.PositiveIntegerField(
        default=1,
        help_text="Offset from network address for router IP (e.g., 1 for .1, 254 for .254 in a /24). Set to 0 to disable routers option.",
    )

    class Meta:
        ordering = ("prefix",)
        verbose_name = "DHCP Prefix"
        verbose_name_plural = "DHCP Prefixes"

    def __str__(self):
        return str(self.prefix)

    def get_absolute_url(self):
        return reverse("plugins:netbox_dhcp_kea_plugin:prefixdhcpconfig", args=[self.pk])

    def clean(self):
        super().clean()
        if self.max_lifetime < self.valid_lifetime:
            raise ValidationError("Maximum lifetime must be greater than or equal to valid lifetime")

        # Validate routers_option_offset is within prefix range
        if self.routers_option_offset and self.prefix_id:
            prefix = self.prefix.prefix
            max_offset = prefix.size - 2  # Exclude network and broadcast
            if self.routers_option_offset > max_offset:
                raise ValidationError(
                    {"routers_option_offset": f"Offset must be between 0 and {max_offset} for this prefix."}
                )

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

        Priority:
        1. If the prefix has IPRanges that are NOT mark_utilized, use those ranges
        2. Otherwise, use prefix.get_available_ips() to get available IP ranges

        Returns:
            list: List of pool dictionaries with 'pool' key containing "start - end" format
        """
        import netaddr

        pools = []

        # Use prefix's built-in method to get child ranges
        ip_ranges = self.prefix.get_child_ranges().filter(mark_utilized=False)

        if ip_ranges.exists():
            # Use IPRanges as pools
            for ip_range in ip_ranges:
                # Extract IP without mask for pool range
                start_ip = str(ip_range.start_address).split("/")[0]
                end_ip = str(ip_range.end_address).split("/")[0]
                pools.append({"pool": f"{start_ip} - {end_ip}"})
        else:
            # Use prefix's built-in method to get available IPs
            available_ips = self.prefix.get_available_ips()

            # Get all CIDRs and merge contiguous ranges
            cidrs = list(available_ips.iter_cidrs())
            if not cidrs:
                return pools

            # Sort CIDRs by first IP (should already be sorted, but just in case)
            cidrs.sort(key=lambda c: c.first)

            # Merge contiguous ranges
            current_start = cidrs[0].first
            current_end = cidrs[0].last

            for cidr in cidrs[1:]:
                if cidr.first == current_end + 1:
                    # Contiguous - extend the current range
                    current_end = cidr.last
                else:
                    # Gap found - save current range and start new one
                    first_ip = netaddr.IPAddress(current_start)
                    last_ip = netaddr.IPAddress(current_end)
                    pools.append({"pool": f"{first_ip} - {last_ip}"})
                    current_start = cidr.first
                    current_end = cidr.last

            # Don't forget the last range
            first_ip = netaddr.IPAddress(current_start)
            last_ip = netaddr.IPAddress(current_end)
            pools.append({"pool": f"{first_ip} - {last_ip}"})

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

            # Get MAC address if available
            mac_address = getattr(assigned_object, "mac_address", None)

            # Build KEA reservation dict
            kea_reservation = {
                "ip-address": str(ip.address.ip),
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
            }

            reservations.append((kea_reservation, metadata))

        return reservations

    def get_kea_reservations(self):
        """Get DHCP reservations in KEA format only (without metadata).

        Returns a list of KEA reservation dictionaries suitable for
        including in the KEA configuration.
        """
        return [r[0] for r in self.get_reservations()]

    def to_kea_dict(self):
        """Return a dictionary representation for KEA subnet configuration"""
        prefix = self.prefix.prefix
        result = {
            "subnet": str(prefix),
            "valid-lifetime": self.valid_lifetime,
            "max-valid-lifetime": self.max_lifetime,
        }

        # Add pools from available IPs or IP ranges
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

        # Add client-classes if any
        client_class_names = [cc.name for cc in self.client_classes.all()]
        if client_class_names:
            result["require-client-classes"] = client_class_names

        # Add reservations from assigned IP addresses
        reservations = self.get_kea_reservations()
        if reservations:
            result["reservations"] = reservations

        return result


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

    def get_synced_prefix_count(self):
        """Get the number of prefixes synced across this HA relationship.

        Returns:
            int: Number of prefix configs on the primary server.
        """
        primary = self.get_primary_server()
        if primary:
            return primary.prefix_configs.count()
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
        """Migrate all prefix configs, client classes, and options to a new primary server.

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

        # Migrate prefix configs
        prefix_configs = list(current_primary.prefix_configs.all())
        for config in prefix_configs:
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
