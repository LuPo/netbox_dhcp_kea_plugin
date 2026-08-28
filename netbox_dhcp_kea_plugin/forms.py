from dcim.choices import DeviceStatusChoices
from dcim.models import MACAddress, Manufacturer
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.urls import reverse
from django.utils.safestring import mark_safe
from ipam.models import IPAddress, IPRange, Prefix, ServiceTemplate
from netbox.forms import (
    NetBoxModelBulkEditForm,
    NetBoxModelFilterSetForm,
    NetBoxModelForm,
    NetBoxModelImportForm,
)
from netbox.plugins.utils import get_plugin_config
from utilities.forms.fields import (
    CSVChoiceField,
    CSVModelChoiceField,
    DynamicModelChoiceField,
    DynamicModelMultipleChoiceField,
)
from utilities.forms.rendering import FieldSet, InlineFields
from utilities.forms.utils import get_field_value
from utilities.forms.widgets import BulkEditNullBooleanSelect, HTMXSelect

from .models import (
    ClientClass,
    D2Daemon,
    DDNSDomain,
    DDNSPolicy,
    DHCPHARelationship,
    DHCPServer,
    Hook,
    HookGroup,
    OptionData,
    OptionDefinition,
    StaticReservation,
    StorkAgentGroup,
    StorkServer,
    Subnet,
    SubnetPool,
    TSIGKey,
    VendorOptionSpace,
    normalize_fqdn,
    pki_allowed_zone_suffixes,
)


class BootstrapCheckboxSelectMultiple(forms.CheckboxSelectMultiple):
    """
    A CheckboxSelectMultiple widget styled for Bootstrap 5.
    Renders checkboxes with proper form-check and form-check-input classes.
    """

    def __init__(self, attrs=None, disabled=False):
        super().__init__(attrs)
        self.disabled = disabled

    def render(self, name, value, attrs=None, renderer=None):
        if value is None:
            value = []
        if attrs is None:
            attrs = {}
        # Check for disabled in both widget attribute and attrs dict
        is_disabled = self.disabled or attrs.get("disabled", False)
        html = []
        for i, (option_value, option_label) in enumerate(self.choices):
            option_id = f"{attrs.get('id', name)}_{i}"
            checked = "checked" if str(option_value) in [str(v) for v in value] else ""
            disabled_attr = "disabled" if is_disabled else ""
            html.append(
                f'<div class="form-check">'
                f'<input class="form-check-input" type="checkbox" name="{name}" '
                f'value="{option_value}" id="{option_id}" {checked} {disabled_attr}>'
                f'<label class="form-check-label" for="{option_id}">{option_label}</label>'
                f"</div>"
            )
        return mark_safe("\n".join(html))


def validate_unique_option_data_space_code(option_data):
    """
    Validate that no two option data entries have the same space and code.

    Args:
        option_data: QuerySet or list of OptionData instances

    Raises:
        ValidationError: If duplicate space/code combinations are found
    """
    if not option_data:
        return

    # Track (space, code) combinations to detect duplicates
    seen = {}
    duplicates = []

    for opt in option_data:
        # Determine the effective space
        if opt.vendor_option_space:
            space = opt.vendor_option_space.name
        else:
            space = opt.option_space

        code = opt.code
        key = (space, code)

        if key in seen:
            duplicates.append(f"'{opt.distinctive_name}' and '{seen[key]}' both use space '{space}' with code {code}")
        else:
            seen[key] = opt.distinctive_name

    if duplicates:
        raise ValidationError(
            "Cannot assign multiple option data with the same space and code: " + "; ".join(duplicates)
        )


# Import Forms
class VendorOptionSpaceImportForm(NetBoxModelImportForm):
    manufacturer = CSVModelChoiceField(
        queryset=Manufacturer.objects.all(),
        required=False,
        to_field_name="name",
        help_text="Manufacturer/vendor name",
    )

    class Meta:
        model = VendorOptionSpace
        fields = ("name", "enterprise_id", "manufacturer", "description", "tags")


class OptionDefinitionImportForm(NetBoxModelImportForm):
    # Model fields
    option_type = CSVChoiceField(
        choices=OptionDefinition.OPTION_TYPE_CHOICES,
        required=False,  # Made optional - can come from 'type' alias
        help_text="Data type (e.g., string, binary, boolean, ipv4-address)",
    )
    option_space = CSVChoiceField(
        choices=OptionDefinition.OPTION_SPACE_CHOICES,
        required=False,
        help_text="Option space (dhcp4 or dhcp6)",
    )
    vendor_option_space = CSVModelChoiceField(
        queryset=VendorOptionSpace.objects.all(),
        required=False,
        to_field_name="name",
        help_text="Vendor option space name",
    )
    # KEA JSON aliases - these translate to model fields
    type = CSVChoiceField(
        choices=OptionDefinition.OPTION_TYPE_CHOICES,
        required=False,
        help_text="KEA alias for option_type",
    )
    space = forms.CharField(
        required=False,
        help_text="KEA alias for option_space or vendor_option_space",
    )

    class Meta:
        model = OptionDefinition
        fields = (
            "name",
            "code",
            "option_type",
            "option_space",
            "vendor_option_space",
            "is_array",
            "encapsulate",
            "record_types",
            "description",
            "tags",
        )

    def clean(self):
        super().clean()

        # Translate KEA JSON field names to model field names
        # 'type' -> 'option_type'
        if not self.cleaned_data.get("option_type") and self.cleaned_data.get("type"):
            self.cleaned_data["option_type"] = self.cleaned_data["type"]

        # 'space' -> 'option_space' or 'vendor_option_space'
        space = self.cleaned_data.get("space")
        if space and not self.cleaned_data.get("option_space") and not self.cleaned_data.get("vendor_option_space"):
            if space in ("dhcp4", "dhcp6", "vendor-encapsulated-options-space"):
                self.cleaned_data["option_space"] = space
            else:
                # Try to look up as vendor option space
                try:
                    vendor_space = VendorOptionSpace.objects.get(name=space)
                    self.cleaned_data["vendor_option_space"] = vendor_space
                except VendorOptionSpace.DoesNotExist:
                    # Default to dhcp4 if space not found
                    self.cleaned_data["option_space"] = "dhcp4"

        # Ensure option_type is set
        if not self.cleaned_data.get("option_type"):
            raise forms.ValidationError({"option_type": "This field is required (or use 'type' for KEA JSON format)."})

        # Prevent importing definitions that would conflict with standard options
        code = self.cleaned_data.get("code")
        option_space = self.cleaned_data.get("option_space", "dhcp4")
        vendor_option_space = self.cleaned_data.get("vendor_option_space")

        if code and not vendor_option_space:
            existing = OptionDefinition.objects.filter(
                code=code,
                option_space=option_space,
                vendor_option_space__isnull=True,
                is_standard=True,
            ).first()
            if existing:
                raise forms.ValidationError(
                    f"Cannot import: option code {code} in {option_space} space is a standard DHCP option ({existing.name})."
                )
        return self.cleaned_data


class OptionDataImportForm(NetBoxModelImportForm):
    definition = CSVModelChoiceField(
        queryset=OptionDefinition.objects.all(),
        required=True,
        to_field_name="name",
        help_text="Option definition name (required)",
    )
    vendor_option_space = CSVModelChoiceField(
        queryset=VendorOptionSpace.objects.all(),
        required=False,
        to_field_name="name",
        help_text="Vendor option space name",
    )
    delivery_type = CSVChoiceField(
        choices=OptionData.DELIVERY_TYPE_CHOICES,
        required=False,
        help_text="Delivery method: standard, option43, or vivso",
    )

    class Meta:
        model = OptionData
        fields = (
            "distinctive_name",
            "definition",
            "option_space",
            "vendor_option_space",
            "delivery_type",
            "data",
            "always_send",
            "csv_format",
            "description",
            "tags",
        )

    def clean_csv_format(self):
        """Set csv_format to True if not provided (matching model default)"""
        csv_format = self.cleaned_data.get("csv_format")
        # If csv_format is not explicitly set to False, default to True
        if csv_format is None or csv_format == "":
            return True
        return csv_format


class DHCPServerImportForm(NetBoxModelImportForm):
    stork_agent_group = CSVModelChoiceField(
        queryset=StorkAgentGroup.objects.all(),
        to_field_name="name",
        required=False,
        help_text="Name of the Stork Agent Group (optional)",
    )
    ip_address = CSVModelChoiceField(
        queryset=IPAddress.objects.all(),
        to_field_name="address",
        help_text="IP address of the DHCP server",
    )
    service_template = CSVModelChoiceField(
        queryset=ServiceTemplate.objects.all(),
        help_text="Service template ID",
    )
    ha_relationship = CSVModelChoiceField(
        queryset=DHCPHARelationship.objects.all(),
        to_field_name="name",
        required=False,
        help_text="Name of the HA relationship (optional)",
    )
    ha_role = CSVChoiceField(
        choices=[("", "")] + list(DHCPServer.HA_ROLE_CHOICES),
        required=False,
        help_text="Role in the HA relationship: primary, secondary, standby, or backup",
    )
    ha_address = forms.CharField(
        max_length=255,
        required=False,
        help_text="IP address for HA communication (e.g., 192.168.1.1)",
    )
    ha_port = forms.IntegerField(
        required=False,
        help_text="Port for HA communication (default: 8080)",
    )
    ha_tls = forms.BooleanField(
        required=False,
        help_text="Use TLS (HTTPS) for HA communication",
    )
    ctrl_socket_type = CSVChoiceField(
        choices=[("", "")] + list(DHCPServer.CTRL_SOCKET_TYPE_CHOICES),
        required=False,
        help_text="Control socket type: http, unix, or both",
    )
    ctrl_socket_http_address = forms.CharField(
        max_length=255,
        required=False,
        help_text="HTTP socket address (e.g., 127.0.0.1)",
    )
    ctrl_socket_http_port = forms.IntegerField(
        required=False,
        help_text="HTTP socket port (e.g., 8000)",
    )

    ctrl_socket_unix_path = forms.CharField(
        max_length=255,
        required=False,
        help_text="Unix socket path (e.g., /var/run/kea/kea-dhcp4-socket)",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not get_plugin_config("netbox_dhcp_kea_plugin", "enable_stork"):
            if "stork_agent_group" in self.fields:
                del self.fields["stork_agent_group"]

    class Meta:
        model = DHCPServer
        fields = (
            "name",
            "description",
            "ip_address",
            "status",
            "service_template",
            "ha_relationship",
            "ha_role",
            "ha_address",
            "ha_port",
            "ha_tls",
            "ha_auto_failover",
            "stork_agent_group",
            "ctrl_socket_type",
            "ctrl_socket_http_address",
            "ctrl_socket_http_port",
            "ctrl_socket_unix_path",
            "tags",
        )


class ClientClassImportForm(NetBoxModelImportForm):
    class Meta:
        model = ClientClass
        fields = (
            "name",
            "test_expression",
            "description",
            "only_in_additional_list",
            "next_server",
            "server_hostname",
            "boot_file_name",
            "tags",
        )


class SubnetPoolImportForm(NetBoxModelImportForm):
    subnet = CSVModelChoiceField(
        queryset=Subnet.objects.all(),
        to_field_name="pk",
        help_text="Subnet ID",
    )
    ip_range = CSVModelChoiceField(
        queryset=IPRange.objects.all(),
        to_field_name="pk",
        help_text="IP Range ID",
    )
    client_class = CSVModelChoiceField(
        queryset=ClientClass.objects.all(),
        to_field_name="name",
        required=False,
        help_text="Restricting client class name",
    )

    class Meta:
        model = SubnetPool
        fields = (
            "subnet",
            "ip_range",
            "client_class",
            "description",
            "tags",
        )


class SubnetImportForm(NetBoxModelImportForm):
    prefix = CSVModelChoiceField(  # type: ignore[assignment]
        queryset=Prefix.objects.all(),
        to_field_name="prefix",
        help_text="Prefix in CIDR notation",
    )
    vrf = forms.CharField(
        required=False,
        help_text="VRF name (leave empty for global)",
    )
    server = CSVModelChoiceField(
        queryset=DHCPServer.objects.all(),
        to_field_name="name",
        help_text="DHCP server name",
    )
    client_class = CSVModelChoiceField(
        queryset=ClientClass.objects.all(),
        to_field_name="name",
        required=False,
        help_text="Restricting client class name (KEA client-class)",
    )

    class Meta:
        model = Subnet
        fields = (
            "prefix",
            "server",
            "client_class",
            "valid_lifetime",
            "max_lifetime",
            "routers_option_offset",
            "reservations_global",
            "reservations_in_subnet",
            "reservations_out_of_pool",
            "reservations_only",
            "tags",
        )

    def clean(self):
        super().clean()
        # Handle VRF lookup for prefix disambiguation
        vrf_name = self.cleaned_data.get("vrf")
        prefix = self.cleaned_data.get("prefix")

        if prefix and vrf_name:
            # Re-lookup prefix with VRF filter
            from ipam.models import VRF

            try:
                vrf = VRF.objects.get(name=vrf_name)
                prefix_with_vrf = Prefix.objects.filter(prefix=prefix.prefix, vrf=vrf).first()
                if prefix_with_vrf:
                    self.cleaned_data["prefix"] = prefix_with_vrf
                else:
                    raise forms.ValidationError({"prefix": f"Prefix {prefix.prefix} not found in VRF {vrf_name}."})
            except VRF.DoesNotExist as err:
                raise forms.ValidationError({"vrf": f"VRF {vrf_name} does not exist."}) from err

        return self.cleaned_data


# Edit Forms


class VendorOptionSpaceForm(NetBoxModelForm):
    manufacturer = DynamicModelChoiceField(
        queryset=Manufacturer.objects.all(),
        required=False,
        help_text="Manufacturer/vendor associated with this option space",
    )

    fieldsets = (FieldSet("name", "enterprise_id", "manufacturer", "description", "tags", name="Vendor Option Space"),)

    class Meta:
        model = VendorOptionSpace
        fields = ("name", "enterprise_id", "manufacturer", "description", "tags")


class OptionDefinitionForm(NetBoxModelForm):
    vendor_option_space = DynamicModelChoiceField(
        queryset=VendorOptionSpace.objects.all(),
        required=False,
        help_text="Vendor option space this definition belongs to",
    )

    class Meta:
        model = OptionDefinition
        fields = (
            "name",
            "code",
            "option_type",
            "option_space",
            "vendor_option_space",
            "is_array",
            "encapsulate",
            "record_types",
            "description",
            "tags",
        )
        widgets = {
            "option_type": HTMXSelect(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        option_type = get_field_value(self, "option_type")
        if option_type != "record":
            self.fields.pop("record_types", None)

    @property
    def fieldsets(self):
        advanced_fields = ["is_array", "encapsulate"]
        if "record_types" in self.fields:
            advanced_fields.append("record_types")
        return (
            FieldSet(
                "name",
                InlineFields("code", "option_type", label="Code & Type"),
                InlineFields("option_space", "vendor_option_space", label="Option Space"),
                "description",
                "tags",
                name="Option Definition",
            ),
            FieldSet(*advanced_fields, name="Advanced"),
        )

    def clean(self):
        super().clean()
        # Prevent creating definitions that would conflict with standard options
        code = self.cleaned_data.get("code")
        option_space = self.cleaned_data.get("option_space", "dhcp4")
        vendor_option_space = self.cleaned_data.get("vendor_option_space")

        if code and not vendor_option_space:
            existing = (
                OptionDefinition.objects.filter(
                    code=code,
                    option_space=option_space,
                    vendor_option_space__isnull=True,
                    is_standard=True,
                )
                .exclude(pk=self.instance.pk if self.instance else None)
                .first()
            )
            if existing:
                raise forms.ValidationError(
                    f"Cannot create: option code {code} in {option_space} space is already a standard DHCP option ({existing.name})."
                )


class OptionDataForm(NetBoxModelForm):
    vendor_option_space = DynamicModelChoiceField(
        queryset=VendorOptionSpace.objects.all(),
        required=False,
        null_option="None",
        help_text="Vendor option space (required for Option 43 and VIVSO delivery)",
    )
    definition = DynamicModelChoiceField(
        queryset=OptionDefinition.objects.all(),
        required=True,
        query_params={
            "vendor_option_space_id": "$vendor_option_space",
            "option_space": "$option_space",
        },
        help_text="Option definition - filtered by vendor option space, or by option space when no vendor is selected",
    )

    # IP source fields — conditionally shown when definition is ipv4-address type.
    # These are defined here and deleted in __init__ when not applicable.
    ipam_ip_sources = DynamicModelMultipleChoiceField(
        queryset=IPAddress.objects.all(),
        required=False,
        label="IPAM IP Addresses",
        help_text="Select IP addresses from NetBox IPAM. Overrides the Data field in KEA config output.",
    )

    class Meta:
        model = OptionData
        fields = (
            "distinctive_name",
            "delivery_type",
            "vendor_option_space",
            "definition",
            "option_space",
            "data",
            "always_send",
            "csv_format",
            "description",
            "tags",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure csv_format defaults to True (matching model default)
        if not self.instance.pk:
            self.fields["csv_format"].initial = True

        # Add HTMX attributes to the definition widget so the form reloads on change
        defn_widget = self.fields["definition"].widget
        defn_widget.attrs.update(
            {
                "hx-get": ".",
                "hx-include": "#form_fields",
                "hx-target": "#form_fields",
            }
        )

        # Determine form mode based on selected definition
        # Modes: "simple_ip" (plain ipv4/ipv6), "record" (individual fields per record type), "manual" (text data)
        self._record_mode = False
        self._record_types_list = []
        self._record_ip_index = None
        mode = "manual"
        is_array = True
        definition_id = get_field_value(self, "definition")
        defn = None
        if definition_id:
            try:
                defn = OptionDefinition.objects.get(pk=definition_id)
                is_array = defn.is_array
                if defn.option_type in OptionDefinition.IP_TYPES:
                    mode = "simple_ip"
                elif defn.option_type == "record" and defn.record_types:
                    mode = "record"
            except OptionDefinition.DoesNotExist:
                pass

        if mode == "manual":
            self.fields.pop("ipam_ip_sources", None)
            self.fields.pop("dns_record_sources", None)
        elif mode == "simple_ip":
            # Hide data field — IP sources replace manual data entry
            self.fields.pop("data", None)
            self._add_ip_source_fields(is_array)
            if self.instance.pk:
                self._populate_ip_source_fields()
        elif mode == "record":
            self._record_mode = True
            self._record_types_list = defn.parsed_record_types()
            self._record_ip_index = defn.record_ip_field_index()
            # Hide the plain data field — we build it from individual record fields
            self.fields.pop("data", None)
            # Add a field for each position in the record
            for i, type_name in enumerate(self._record_types_list):
                if type_name in OptionDefinition.IP_TYPES:
                    continue  # IP positions get source selectors below
                if type_name == "boolean":
                    self.fields[f"record_field_{i}"] = forms.ChoiceField(
                        choices=[("true", "True"), ("false", "False")],
                        label=f"Field {i + 1} ({type_name})",
                        required=False,
                        help_text=f"Record field {i + 1}: {type_name}",
                    )
                else:
                    self.fields[f"record_field_{i}"] = forms.CharField(
                        label=f"Field {i + 1} ({type_name})",
                        required=False,
                        help_text=f"Record field {i + 1}: {type_name}",
                    )
            # Add IP source selectors if the record has an IP-type field
            if self._record_ip_index is not None:
                # Only the last field in a record can be an array in KEA
                ip_is_array = is_array and self._record_ip_index == len(self._record_types_list) - 1
                self._add_ip_source_fields(ip_is_array)
            else:
                self.fields.pop("ipam_ip_sources", None)
                self.fields.pop("dns_record_sources", None)
            # Pre-populate for existing objects
            if self.instance.pk:
                self._populate_ip_source_fields()

    def _add_ip_source_fields(self, is_array):
        """Add IPAM and DNS IP source selector fields."""
        if not is_array:
            self.fields["ipam_ip_sources"] = DynamicModelChoiceField(
                queryset=IPAddress.objects.all(),
                required=False,
                label="IPAM IP Address",
                help_text="Select an IP address from NetBox IPAM.",
            )
        # (multi-select is already defined as a class field; only override for single)

        if get_plugin_config("netbox_dhcp_kea_plugin", "enable_netbox_dns"):
            try:
                from netbox_dns.models import Record as DNSRecord

                dns_query_params = {"type": ["A", "AAAA", "CNAME"]}
                if is_array:
                    self.fields["dns_record_sources"] = DynamicModelMultipleChoiceField(
                        queryset=DNSRecord.objects.all(),
                        query_params=dns_query_params,
                        required=False,
                        label="DNS Records",
                        help_text="Select DNS A/AAAA or CNAME records. IPs resolved at KEA config generation time.",
                    )
                else:
                    self.fields["dns_record_sources"] = DynamicModelChoiceField(
                        queryset=DNSRecord.objects.all(),
                        query_params=dns_query_params,
                        required=False,
                        label="DNS Record",
                        help_text="Select a DNS A/AAAA or CNAME record. IP resolved at KEA config generation time.",
                    )
            except ImportError:
                pass

    def _populate_ip_source_fields(self):
        """Set initial values for IP source fields from existing OptionDataIPSource entries."""
        from django.contrib.contenttypes.models import ContentType

        from netbox_dhcp_kea_plugin.models import OptionDataIPSource

        # Populate record manual fields from stored JSON
        if self._record_mode and self.instance.record_manual_fields:
            for idx_str, value in self.instance.record_manual_fields.items():
                field_name = f"record_field_{idx_str}"
                if field_name in self.fields:
                    self.initial[field_name] = value

        sources = OptionDataIPSource.objects.filter(option_data=self.instance).order_by("ordinal")
        if not sources.exists():
            return

        ipam_ct = ContentType.objects.get(app_label="ipam", model="ipaddress")
        ipam_ids = list(sources.filter(content_type=ipam_ct).values_list("object_id", flat=True))
        if ipam_ids and "ipam_ip_sources" in self.fields:
            self.initial["ipam_ip_sources"] = ipam_ids

        if "dns_record_sources" in self.fields:
            try:
                dns_ct = ContentType.objects.get(app_label="netbox_dns", model="record")
                dns_ids = list(sources.filter(content_type=dns_ct).values_list("object_id", flat=True))
                if dns_ids:
                    self.initial["dns_record_sources"] = dns_ids
            except ContentType.DoesNotExist:
                pass

    @property
    def fieldsets(self):
        base = [
            FieldSet(
                "distinctive_name",
                "delivery_type",
                "vendor_option_space",
                "option_space",
                "definition",
                name="Option Selection",
            ),
        ]
        # Build value fieldset based on form mode
        if self._record_mode:
            # Record mode: individual fields for each record position + IP source selectors
            record_items = []
            for i, type_name in enumerate(self._record_types_list):
                field_name = f"record_field_{i}"
                if field_name in self.fields:
                    record_items.append(field_name)
            if "ipam_ip_sources" in self.fields:
                record_items.append("ipam_ip_sources")
            if "dns_record_sources" in self.fields:
                record_items.append("dns_record_sources")
            record_items.append(InlineFields("always_send", "csv_format", label="Flags"))
            base.append(FieldSet(*record_items, name="Record Fields"))
        else:
            ip_source_items = []
            if "ipam_ip_sources" in self.fields:
                ip_source_items.append("ipam_ip_sources")
            if "dns_record_sources" in self.fields:
                ip_source_items.append("dns_record_sources")
            if ip_source_items:
                base.append(
                    FieldSet(
                        *ip_source_items, InlineFields("always_send", "csv_format", label="Flags"), name="IP Sources"
                    )
                )
            else:
                base.append(FieldSet("data", InlineFields("always_send", "csv_format", label="Flags"), name="Value"))
        base.append(FieldSet("description", "tags", name="Metadata"))
        return tuple(base)

    def clean_csv_format(self):
        """Set csv_format to True if not provided (matching model default)"""
        csv_format = self.cleaned_data.get("csv_format")
        # If csv_format is not explicitly set to False, default to True
        if csv_format is None or csv_format == "":
            return True
        return csv_format

    def save(self, *args, **kwargs):
        # Collect record manual fields into JSON before saving
        if self._record_mode:
            manual_fields = {}
            for i, type_name in enumerate(self._record_types_list):
                field_name = f"record_field_{i}"
                if field_name in self.cleaned_data:
                    manual_fields[str(i)] = self.cleaned_data[field_name]
            self.instance.record_manual_fields = manual_fields or None
            if self._record_ip_index is not None:
                # Has IP sources — data will be assembled at config generation time
                self.instance.data = ""
            else:
                # No IP sources — assemble data now from manual fields
                parts = [manual_fields.get(str(i), "") for i in range(len(self._record_types_list))]
                self.instance.data = ", ".join(parts)
        instance = super().save(*args, **kwargs)
        self._save_ip_sources(instance)
        return instance

    def _save_ip_sources(self, instance):
        """Sync OptionDataIPSource entries from form selections."""
        from django.contrib.contenttypes.models import ContentType

        from netbox_dhcp_kea_plugin.models import OptionDataIPSource

        # Only process if IP source fields were present in the form
        if "ipam_ip_sources" not in self.fields and "dns_record_sources" not in self.fields:
            return

        # Clear existing sources and rebuild
        OptionDataIPSource.objects.filter(option_data=instance).delete()

        ordinal = 0

        # Add IPAM IP sources
        ipam_selection = self.cleaned_data.get("ipam_ip_sources")
        if ipam_selection:
            ipam_ct = ContentType.objects.get(app_label="ipam", model="ipaddress")
            # Handle both single and multi-select
            if not hasattr(ipam_selection, "__iter__"):
                ipam_selection = [ipam_selection]
            for ip_obj in ipam_selection:
                OptionDataIPSource.objects.create(
                    option_data=instance,
                    content_type=ipam_ct,
                    object_id=ip_obj.pk,
                    ordinal=ordinal,
                )
                ordinal += 1

        # Add DNS Record sources
        dns_selection = self.cleaned_data.get("dns_record_sources")
        if dns_selection:
            try:
                dns_ct = ContentType.objects.get(app_label="netbox_dns", model="record")
                if not hasattr(dns_selection, "__iter__"):
                    dns_selection = [dns_selection]
                for record_obj in dns_selection:
                    OptionDataIPSource.objects.create(
                        option_data=instance,
                        content_type=dns_ct,
                        object_id=record_obj.pk,
                        ordinal=ordinal,
                    )
                    ordinal += 1
            except ContentType.DoesNotExist:
                pass


class DHCPServerForm(NetBoxModelForm):
    ip_address = DynamicModelChoiceField(
        queryset=IPAddress.objects.all(),
        help_text="IP address of the DHCP server (from NetBox IPAM)",
        # NetBox's quick-add: a "+" beside the selector that creates the IP
        # inline, so defining a server does not mean leaving for IPAM first.
        quick_add=True,
    )

    service_template = DynamicModelChoiceField(
        queryset=ServiceTemplate.objects.all(),
        query_params={
            "tag": "dhcp",
        },
        help_text="Application service template (must have 'dhcp' tag)",
    )
    option_data = DynamicModelMultipleChoiceField(
        queryset=OptionData.objects.all(),
        required=False,
        help_text="Global option data for this DHCP server",
    )
    client_classes = DynamicModelMultipleChoiceField(
        queryset=ClientClass.objects.all(),
        required=False,
        help_text="Client classes associated with this DHCP server",
    )
    ha_relationship = DynamicModelChoiceField(
        queryset=DHCPHARelationship.objects.all(),
        required=False,
        label="HA Relationship",
        help_text="The HA relationship this server belongs to (optional)",
    )
    hook_groups = DynamicModelMultipleChoiceField(
        queryset=HookGroup.objects.all(),
        required=False,
        help_text="Hook groups to apply to this DHCP server",
    )
    stork_agent_group = DynamicModelChoiceField(
        queryset=StorkAgentGroup.objects.all(),
        required=False,
        help_text="Stork agent group configuration for this DHCP server",
    )
    d2_daemon = DynamicModelChoiceField(
        queryset=D2Daemon.objects.all(),
        required=False,
        label="D2 daemon",
        help_text=(
            "Kea D2 daemon to send NCRs to. Ignored when the server is in an HA relationship with D2 daemon set."
        ),
    )
    ddns_policy = DynamicModelChoiceField(
        queryset=DDNSPolicy.objects.all(),
        required=False,
        help_text="Server-level DDNS policy (ddns-* tunables)",
    )

    @property
    def fieldsets(self):
        # Build Control Sockets fieldset dynamically based on which fields exist
        ctrl_socket_items: list = ["ctrl_socket_type"]
        if "ctrl_socket_http_address" in self.fields:
            ctrl_socket_items.append(
                InlineFields("ctrl_socket_http_address", "ctrl_socket_http_port", label="HTTP Socket")
            )
            ctrl_socket_items.append("ctrl_socket_proxy_enabled")
        if "ctrl_socket_unix_path" in self.fields:
            ctrl_socket_items.append("ctrl_socket_unix_path")

        return (
            FieldSet(
                "name",
                "description",
                "ip_address",
                "status",
                "service_template",
                "tags",
                name="General",
            ),
            FieldSet("option_data", "client_classes", name="DHCP Configuration"),
            FieldSet(
                InlineFields(
                    "reservations_global",
                    "reservations_in_subnet",
                    "reservations_out_of_pool",
                    label="Reservation Mode Defaults",
                ),
                name="Reservations",
            ),
            FieldSet("hook_groups", name="Hook Libraries"),
            FieldSet(
                *ctrl_socket_items,
                name="Control Sockets",
            ),
            FieldSet("stork_agent_group", "stork_proxy_enabled", name="Stork Monitoring"),
            FieldSet(
                "ddns_enable_updates",
                "d2_daemon",
                "ddns_policy",
                InlineFields("ddns_sender_ip", "ddns_sender_port", label="Sender"),
                name="DDNS",
            ),
            FieldSet(
                "ha_relationship",
                "ha_role",
                InlineFields("ha_address", "ha_port", label="HA Peer"),
                InlineFields("ha_tls", "ha_auto_failover", label="HA Options"),
                "ha_egress_base_port",
                name="High Availability",
            ),
            # Exactly one of these exists at a time: the picker when
            # netbox-plugin-dns is installed, the text field otherwise.
            FieldSet(
                "pki_record",
                "pki_fqdn",
                name="PKI Identity",
            ),
        )

    class Meta:
        model = DHCPServer
        fields = (
            "name",
            "description",
            "ip_address",
            "status",
            "service_template",
            "option_data",
            "reservations_global",
            "reservations_in_subnet",
            "reservations_out_of_pool",
            "stork_agent_group",
            "d2_daemon",
            "ddns_enable_updates",
            "ddns_sender_ip",
            "ddns_sender_port",
            "ddns_policy",
            "ctrl_socket_type",
            "ctrl_socket_http_address",
            "ctrl_socket_http_port",
            "ctrl_socket_unix_path",
            "ha_relationship",
            "ha_role",
            "ha_address",
            "ha_port",
            "ha_tls",
            "ha_auto_failover",
            "ha_egress_base_port",
            "pki_fqdn",
            "ctrl_socket_proxy_enabled",
            "stork_proxy_enabled",
            "tags",
        )
        widgets = {
            "ctrl_socket_type": HTMXSelect(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Hide stork_agent_group when Stork is disabled in plugin settings
        if not get_plugin_config("netbox_dhcp_kea_plugin", "enable_stork"):
            if "stork_agent_group" in self.fields:
                del self.fields["stork_agent_group"]

        # Hide DDNS fields when DDNS is disabled in plugin settings
        if not get_plugin_config("netbox_dhcp_kea_plugin", "enable_ddns"):
            for fname in (
                "d2_daemon",
                "ddns_enable_updates",
                "ddns_sender_ip",
                "ddns_sender_port",
                "ddns_policy",
            ):
                if fname in self.fields:
                    del self.fields[fname]

        # PKI identity. netbox_dns is optional, so pki_fqdn is always a plain
        # text field; when the DNS plugin is present we add a record picker in
        # front of it so the name is chosen from DNS rather than retyped.
        self._add_pki_record_picker()

        # Determine the selected control socket type
        ctrl_socket_type = get_field_value(self, "ctrl_socket_type")

        # Delete control socket fields which are not relevant for the selected type
        if ctrl_socket_type not in ("http", "both"):
            del self.fields["ctrl_socket_http_address"]
            del self.fields["ctrl_socket_http_port"]
        if ctrl_socket_type not in ("unix", "both"):
            del self.fields["ctrl_socket_unix_path"]

        # Populate client_classes from reverse relation
        if self.instance.pk:
            self.initial["client_classes"] = self.instance.client_classes.all()
            self.initial["hook_groups"] = self.instance.hook_groups.all()

        # Hide option_data and client_classes fields if this is a non-primary HA server
        if self.instance.pk and self.instance.ha_relationship and not self.instance.is_ha_primary():
            # Remove these fields from the form as they should only be managed on the primary
            if "option_data" in self.fields:
                del self.fields["option_data"]
            if "client_classes" in self.fields:
                del self.fields["client_classes"]

    def _add_pki_record_picker(self):
        """Swap the PKI identity text field for a netbox_dns record picker.

        With the DNS plugin installed the identity is *bound* to a record rather
        than typed: the record cannot then be deleted out from under the
        certificate, and renaming it re-derives the name. Without the plugin the
        plain ``pki_fqdn`` text field stays, which is the supported way to run
        this without netbox-plugin-dns.
        """
        if not get_plugin_config("netbox_dhcp_kea_plugin", "enable_netbox_dns"):
            return
        try:
            from netbox_dns.models import Record as DNSRecord
            from netbox_dns.models import Zone as DNSZone
        except ImportError:
            return

        # Managed records are regenerated from IPAM, so they are the wrong thing
        # to name a certificate after; the PKI name is a deliberate service record.
        # Inactive records are excluded too: PKI onboarding resolves the name
        # before minting a certificate and refuses one that does not resolve.
        queryset = DNSRecord.objects.filter(
            type__in=("A", "AAAA", "CNAME"), managed=False, status="active"
        )
        query_params = {"type": ["A", "AAAA", "CNAME"], "managed": False, "status": "active"}
        help_text = (
            "The DNS record naming this host in the PKI. The PKI FQDN is derived from it, "
            "the record cannot be deleted while bound, and deleting this server deletes it."
        )

        suffixes = pki_allowed_zone_suffixes()
        if suffixes:
            # Restrict to what the CA will actually sign, so the picker cannot
            # offer a name that clean() then rejects.
            #
            # The queryset filters on the record's own FQDN, which is what is
            # validated. The dropdown is populated over the REST API, which has
            # no suffix lookup, so it filters by zone instead — every record in a
            # matching zone also matches by FQDN, making the offered set a subset
            # of the valid one.
            fqdn_filter = Q()
            for suffix in suffixes:
                fqdn_filter |= Q(fqdn__iendswith=f".{suffix}.") | Q(fqdn__iexact=f"{suffix}.")
            queryset = queryset.filter(fqdn_filter)

            zone_filter = Q()
            for suffix in suffixes:
                zone_filter |= Q(name__iendswith=f".{suffix}") | Q(name__iexact=suffix)
            query_params["zone_id"] = list(
                DNSZone.objects.filter(zone_filter).values_list("pk", flat=True)
            ) or [0]  # no matching zone: offer nothing rather than everything

            help_text += " Restricted to the zones in pki_allowed_zone_suffixes."

        self.fields["pki_record"] = DynamicModelChoiceField(
            queryset=queryset,
            query_params=query_params,
            required=False,
            label="PKI DNS record",
            help_text=help_text,
            initial=self.instance.pki_record_id if self.instance.pk else None,
        )
        # The name is derived from the record now, so drop the free-text field.
        self.fields.pop("pki_fqdn", None)

    def clean(self):
        # NetBoxModelForm.clean() ends in CheckLastUpdatedMixin.clean(), which
        # returns None on every path, so the return value of super().clean() is
        # not usable here. Django's contract is that clean() may return None and
        # the form falls back to self.cleaned_data — read that instead.
        super().clean()
        cleaned_data = self.cleaned_data

        if "pki_record" in self.fields:
            # Picker present: the record is the identity, bound and derived.
            record = cleaned_data.get("pki_record")
            self.instance.pki_record_id = record.pk if record is not None else None
            cleaned_data["pki_fqdn"] = (
                DHCPServer.normalize_pki_fqdn(record.fqdn) if record is not None else ""
            )
            self.instance.pki_fqdn = cleaned_data["pki_fqdn"]
        elif cleaned_data.get("pki_fqdn"):
            cleaned_data["pki_fqdn"] = DHCPServer.normalize_pki_fqdn(cleaned_data["pki_fqdn"])
        return cleaned_data

    def save(self, *args, **kwargs):
        instance = super().save(*args, **kwargs)
        # Handle hook_groups (reverse ManyToMany relation from HookGroup)
        if "hook_groups" in self.cleaned_data:
            selected_groups = self.cleaned_data["hook_groups"]
            current_groups = set(instance.hook_groups.all())
            selected_set = set(selected_groups)

            # Remove server from groups that were deselected
            for group in current_groups - selected_set:
                group.servers.remove(instance)

            # Add server to newly selected groups
            for group in selected_set - current_groups:
                group.servers.add(instance)

        # Handle client_classes (reverse ManyToMany relation)
        if "client_classes" in self.cleaned_data:
            # Get the selected client classes
            selected_classes = self.cleaned_data["client_classes"]
            # Get current client classes linked to this server
            current_classes = set(instance.client_classes.all())
            selected_set = set(selected_classes)

            # If this server is not primary in HA, redirect to primary
            actual_server = instance
            redirected = False
            if instance.ha_relationship and not instance.is_ha_primary():
                primary_server = instance.ha_relationship.servers.filter(ha_role="primary").first()
                if primary_server:
                    actual_server = primary_server
                    redirected = True

            # Remove server from classes that were deselected
            for cc in current_classes - selected_set:
                cc.servers.remove(actual_server)

            # Add server to newly selected classes
            classes_added = selected_set - current_classes
            for cc in classes_added:
                cc.servers.add(actual_server)

            # Set flag for messaging only if we redirected AND added classes
            if redirected and classes_added:
                self._redirected_to_primary = True
                self._original_server_name = instance.name

        return instance


class ClientClassForm(NetBoxModelForm):
    servers = DynamicModelMultipleChoiceField(
        queryset=DHCPServer.objects.all(),
        required=False,
        help_text="DHCP servers this client class applies to",
    )
    option_data = DynamicModelMultipleChoiceField(
        queryset=OptionData.objects.all(),
        required=False,
        help_text="Option data to send to clients matching this class",
    )
    ddns_policy = DynamicModelChoiceField(
        queryset=DDNSPolicy.objects.all(),
        required=False,
        help_text="Class-level DDNS policy overrides (ddns-* tunables)",
    )

    class Meta:
        model = ClientClass
        fields = (
            "name",
            "test_expression",
            "description",
            "servers",
            "option_data",
            "only_in_additional_list",
            "next_server",
            "server_hostname",
            "boot_file_name",
            "ddns_policy",
            "tags",
        )

    fieldsets = (
        FieldSet("name", "test_expression", "description", "tags", name="Client Class"),
        FieldSet("servers", "option_data", name="Assignments"),
        FieldSet("only_in_additional_list", name="Evaluation"),
        FieldSet("next_server", "server_hostname", "boot_file_name", name="Boot Options"),
        FieldSet("ddns_policy", name="DDNS"),
    )

    def __init__(self, *args, **kwargs):
        # Extract request if passed (NetBox pattern)
        request = kwargs.pop("request", None)

        super().__init__(*args, **kwargs)

        # Store request for later use in clean methods
        self.request = request

        # Initialize redirect flags
        self._redirected_to_primary = False
        self._redirected_server_names = []
        self._primary_server_names = []

        # Hide DDNS fields when DDNS is disabled in plugin settings
        if not get_plugin_config("netbox_dhcp_kea_plugin", "enable_ddns"):
            if "ddns_policy" in self.fields:
                del self.fields["ddns_policy"]

    def clean_option_data(self):
        """Validate that no two option data entries have the same space and code."""
        option_data = self.cleaned_data.get("option_data")
        validate_unique_option_data_space_code(option_data)
        return option_data

    def clean_servers(self):
        """Handle HA redirect for servers - modify cleaned_data before save."""
        selected_servers = self.cleaned_data.get("servers", [])

        if not selected_servers:
            return selected_servers

        # Track redirects for messaging
        redirected_servers = []
        primary_servers = []

        # Replace non-primary HA servers with their primaries
        actual_servers = []
        for server in selected_servers:
            if server.ha_relationship and not server.is_ha_primary():
                # Server is in HA but not primary - redirect to primary
                primary_server = server.ha_relationship.servers.filter(ha_role="primary").first()
                if primary_server:
                    # Only add if not already in the list
                    if primary_server not in actual_servers:
                        actual_servers.append(primary_server)
                    redirected_servers.append(server.name)
                    if primary_server.name not in primary_servers:
                        primary_servers.append(primary_server.name)
            else:
                # Server is primary or standalone - use as-is
                if server not in actual_servers:
                    actual_servers.append(server)

        # Set flags for messaging if any redirects occurred
        if redirected_servers:
            self._redirected_to_primary = True
            self._redirected_server_names = redirected_servers
            self._primary_server_names = primary_servers

            # ALSO store on request so view can access them reliably
            if self.request:
                self.request._clientclass_redirected_to_primary = True
                self.request._clientclass_redirected_server_names = redirected_servers
                self.request._clientclass_primary_server_names = primary_servers

        # Return the modified server list
        return actual_servers


class SubnetForm(NetBoxModelForm):
    prefix = DynamicModelChoiceField(queryset=Prefix.objects.all())  # type: ignore[assignment]
    server = DynamicModelChoiceField(queryset=DHCPServer.objects.all())  # type: ignore[assignment]
    option_data = DynamicModelMultipleChoiceField(
        queryset=OptionData.objects.all(),
        required=False,
        help_text="Option data for this subnet",
    )
    client_class = DynamicModelChoiceField(
        queryset=ClientClass.objects.all(),
        required=False,
        help_text="Client class that restricts which clients can use this subnet (KEA client-class)",
    )
    evaluate_additional_classes = DynamicModelMultipleChoiceField(
        queryset=ClientClass.objects.all(),
        required=False,
        query_params={
            "server_id": "$server",
            "only_in_additional_list": "True",
        },
        help_text="Additional client classes to evaluate for clients in this subnet (KEA evaluate-additional-classes)",
    )
    routers_option_offset = forms.IntegerField(
        required=False,
        min_value=0,
        initial=1,
        help_text="Offset from network address for router IP (e.g., 1 for .1, 254 for .254). Set to 0 to disable routers option.",
    )

    reservations_global = forms.NullBooleanField(
        required=False,
        label="Reservations Global",
        help_text="Look for host reservations in the global scope. Leave blank to inherit from server.",
    )
    reservations_in_subnet = forms.NullBooleanField(
        required=False,
        label="Reservations In-Subnet",
        help_text="Look for host reservations within this subnet. Leave blank to inherit from server.",
    )
    reservations_out_of_pool = forms.NullBooleanField(
        required=False,
        label="Reservations Out-of-Pool",
        help_text="Exclude reserved addresses from dynamic pool allocation. Leave blank to inherit from server.",
    )
    ddns_policy = DynamicModelChoiceField(
        queryset=DDNSPolicy.objects.all(),
        required=False,
        help_text="Subnet-level DDNS policy overrides (ddns-* tunables)",
    )

    fieldsets = (
        FieldSet("prefix", "server", name="Prefix Assignment"),
        FieldSet(
            InlineFields("valid_lifetime", "max_lifetime", label="Lifetime"),
            name="Lease Timing",
        ),
        FieldSet("routers_option_offset", "option_data", name="DHCP Options"),
        FieldSet("client_class", "evaluate_additional_classes", name="Client Classes"),
        FieldSet(
            InlineFields(
                "reservations_global",
                "reservations_in_subnet",
                "reservations_out_of_pool",
                label="Reservation Modes",
            ),
            "reservations_only",
            "auto_reservations",
            name="Reservations",
        ),
        FieldSet("ddns_policy", name="DDNS"),
    )

    class Meta:
        model = Subnet
        fields = (
            "prefix",
            "server",
            "valid_lifetime",
            "max_lifetime",
            "routers_option_offset",
            "option_data",
            "client_class",
            "evaluate_additional_classes",
            "reservations_global",
            "reservations_in_subnet",
            "reservations_out_of_pool",
            "reservations_only",
            "auto_reservations",
            "ddns_policy",
            "tags",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Relabel NullBooleanSelect "Unknown" → "Inherit from Server"
        inherit_label = [("unknown", "Inherit from Server"), ("true", "Yes"), ("false", "No")]
        for field_name in ("reservations_global", "reservations_in_subnet", "reservations_out_of_pool"):
            self.fields[field_name].widget.choices = inherit_label

        # Hide DDNS fields when DDNS is disabled in plugin settings
        if not get_plugin_config("netbox_dhcp_kea_plugin", "enable_ddns"):
            if "ddns_policy" in self.fields:
                del self.fields["ddns_policy"]

        # Track if server was redirected to primary (for messaging)
        self._redirected_to_primary = False
        self._original_server_name = None

        # Set initial lifetime values from plugin config for new objects
        if not self.instance.pk:
            from netbox_dhcp_kea_plugin.models import get_model_default

            valid_lifetime = get_model_default("Subnet", "valid_lifetime")
            if valid_lifetime is not None:
                self.initial["valid_lifetime"] = valid_lifetime
            max_lifetime = get_model_default("Subnet", "max_lifetime")
            if max_lifetime is not None:
                self.initial["max_lifetime"] = max_lifetime
            reservations_only = get_model_default("Subnet", "reservations_only")
            if reservations_only is not None:
                self.initial["reservations_only"] = reservations_only

    def clean_option_data(self):
        """Validate that no two option data entries have the same space and code."""
        option_data = self.cleaned_data.get("option_data")
        validate_unique_option_data_space_code(option_data)
        return option_data

    def clean(self):
        super().clean()
        client_class = self.cleaned_data.get("client_class")
        evaluate_additional = self.cleaned_data.get("evaluate_additional_classes")

        # Validate client_class not in evaluate_additional_classes
        if client_class and evaluate_additional:
            if client_class in evaluate_additional:
                raise ValidationError(
                    {
                        "client_class": "The restricting client class should not also appear in "
                        "evaluate-additional-classes."
                    }
                )

        # Validate that a restricting client_class with only_in_additional_list=True
        # is not used at subnet level. KEA evaluates client-class restrictions AFTER
        # global class evaluation. Classes with only-in-additional-list are skipped
        # during global evaluation and there is no higher scope that could list them
        # in evaluate-additional-classes, so no client would ever match — making the
        # subnet permanently unreachable.
        if client_class and client_class.only_in_additional_list:
            raise ValidationError(
                {
                    "client_class": f"Client class '{client_class.name}' has 'only in additional list' enabled. "
                    "It will not be evaluated globally by KEA, and there is no higher scope that can "
                    "trigger its evaluation via evaluate-additional-classes. No client will ever match "
                    "this class, making the subnet permanently unreachable. Either disable "
                    "'only in additional list' on the class, or use a different restricting class."
                }
            )

    def clean_server(self):
        """Redirect non-primary HA servers to their primary.

        When a user selects a server that is part of an HA relationship but
        is not the primary (e.g., secondary, standby, backup), automatically
        redirect the assignment to the primary server.
        """
        server = self.cleaned_data.get("server")
        if not server:
            return server

        # Check if this server is part of an HA relationship but not primary
        primary = server.get_ha_primary()
        if primary:
            # Store original server name for messaging
            self._original_server_name = server.name
            self._redirected_to_primary = True
            return primary

        return server


# Filter Forms
class DHCPServerFilterForm(NetBoxModelFilterSetForm):
    model = DHCPServer
    name = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not get_plugin_config("netbox_dhcp_kea_plugin", "enable_stork"):
            if "stork_agent_group" in self.fields:
                del self.fields["stork_agent_group"]

    status = forms.MultipleChoiceField(
        choices=DeviceStatusChoices,
        required=False,
    )
    ha_relationship = DynamicModelChoiceField(
        queryset=DHCPHARelationship.objects.all(),
        required=False,
        label="HA Relationship",
    )
    ha_role = forms.ChoiceField(
        choices=[("", "---------")] + list(DHCPServer.HA_ROLE_CHOICES),
        required=False,
        label="HA Role",
    )
    ha_auto_failover = forms.NullBooleanField(
        required=False,
        label="HA Auto Failover",
        widget=forms.Select(
            choices=[
                ("", "---------"),
                ("true", "Yes"),
                ("false", "No"),
            ]
        ),
    )
    stork_agent_group = DynamicModelChoiceField(
        queryset=StorkAgentGroup.objects.all(),
        required=False,
        label="Stork Agent Group",
    )
    ctrl_socket_type = forms.ChoiceField(
        choices=[("", "---------")] + list(DHCPServer.CTRL_SOCKET_TYPE_CHOICES),
        required=False,
        label="Control Socket Type",
    )


class VendorOptionSpaceFilterForm(NetBoxModelFilterSetForm):
    model = VendorOptionSpace
    name = forms.CharField(required=False)
    manufacturer = DynamicModelChoiceField(
        queryset=Manufacturer.objects.all(),
        required=False,
    )
    enterprise_id = forms.IntegerField(required=False)


class OptionDefinitionFilterForm(NetBoxModelFilterSetForm):
    model = OptionDefinition
    name = forms.CharField(required=False)
    code = forms.IntegerField(required=False)
    option_type = forms.ChoiceField(
        choices=[("", "---------")] + list(OptionDefinition.OPTION_TYPE_CHOICES),
        required=False,
    )
    option_space = forms.ChoiceField(
        choices=[("", "---------")] + list(OptionDefinition.OPTION_SPACE_CHOICES),
        required=False,
    )
    vendor_option_space = DynamicModelChoiceField(queryset=VendorOptionSpace.objects.all(), required=False)
    is_standard = forms.NullBooleanField(
        required=False,
        label="Standard Option",
        widget=forms.Select(
            choices=[
                ("", "---------"),
                ("true", "Yes"),
                ("false", "No"),
            ]
        ),
    )
    is_array = forms.NullBooleanField(
        required=False,
        widget=forms.Select(
            choices=[
                ("", "---------"),
                ("true", "Yes"),
                ("false", "No"),
            ]
        ),
    )


class OptionDataFilterForm(NetBoxModelFilterSetForm):
    model = OptionData
    distinctive_name = forms.CharField(required=False, label="Distinctive Name")
    definition = DynamicModelChoiceField(queryset=OptionDefinition.objects.all(), required=False)
    vendor_option_space = DynamicModelChoiceField(queryset=VendorOptionSpace.objects.all(), required=False)
    delivery_type = forms.ChoiceField(
        choices=[("", "---------")] + list(OptionData.DELIVERY_TYPE_CHOICES),
        required=False,
    )
    always_send = forms.NullBooleanField(
        required=False,
        widget=forms.Select(
            choices=[
                ("", "---------"),
                ("true", "Yes"),
                ("false", "No"),
            ]
        ),
    )


class ClientClassFilterForm(NetBoxModelFilterSetForm):
    model = ClientClass
    name = forms.CharField(required=False)
    only_in_additional_list = forms.NullBooleanField(
        required=False,
        label="Only in Additional List",
        widget=forms.Select(
            choices=[
                ("", "---------"),
                ("true", "Yes"),
                ("false", "No"),
            ]
        ),
    )


class SubnetFilterForm(NetBoxModelFilterSetForm):
    model = Subnet
    client_class = DynamicModelChoiceField(queryset=ClientClass.objects.all(), required=False)
    server = DynamicModelChoiceField(queryset=DHCPServer.objects.all(), required=False)


class SubnetPoolForm(NetBoxModelForm):
    subnet = DynamicModelChoiceField(queryset=Subnet.objects.all())
    ip_range = DynamicModelChoiceField(
        queryset=IPRange.objects.all(),
        help_text="IP Range that defines this pool's address boundaries",
    )
    client_class = DynamicModelChoiceField(
        queryset=ClientClass.objects.all(),
        required=False,
        help_text="Client class that restricts which clients can use this pool (KEA client-class)",
    )
    evaluate_additional_classes = DynamicModelMultipleChoiceField(
        queryset=ClientClass.objects.all(),
        required=False,
        query_params={
            "only_in_additional_list": "True",
        },
        help_text="Additional client classes to evaluate for clients in this pool (KEA evaluate-additional-classes)",
    )
    option_data = DynamicModelMultipleChoiceField(
        queryset=OptionData.objects.all(),
        required=False,
        help_text="DHCP options specific to this pool",
    )

    fieldsets = (
        FieldSet("subnet", "ip_range", name="Pool Assignment"),
        FieldSet("client_class", "evaluate_additional_classes", name="Client Classes"),
        FieldSet("option_data", name="DHCP Options"),
        FieldSet("description", "tags", name="Metadata"),
    )

    class Meta:
        model = SubnetPool
        fields = (
            "subnet",
            "ip_range",
            "client_class",
            "evaluate_additional_classes",
            "option_data",
            "description",
            "tags",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Determine the subnet from existing instance or initial data (query params)
        subnet_obj = None
        if self.instance and self.instance.subnet_id:
            subnet_obj = self.instance.subnet
        elif self.initial.get("subnet"):
            try:
                subnet_obj = Subnet.objects.get(pk=self.initial["subnet"])
            except (Subnet.DoesNotExist, ValueError):
                pass

        # Filter ip_range to only the child ranges of the subnet's prefix —
        # both the validating queryset and the API-backed dropdown (via the
        # IPRange `parent` filter), so the picker never lists ranges from
        # other subnets/prefixes.
        if subnet_obj:
            self.fields["ip_range"].queryset = IPRange.objects.filter(  # type: ignore[attr-defined]
                pk__in=subnet_obj.prefix.get_child_ranges().values_list("pk", flat=True)
            )
            self.fields["ip_range"].widget.add_query_param("parent", str(subnet_obj.prefix.prefix))

    def clean_option_data(self):
        """Validate that no two option data entries have the same space and code."""
        option_data = self.cleaned_data.get("option_data")
        validate_unique_option_data_space_code(option_data)
        return option_data

    def clean(self):
        super().clean()
        subnet = self.cleaned_data.get("subnet")
        ip_range = self.cleaned_data.get("ip_range")
        client_class = self.cleaned_data.get("client_class")
        evaluate_additional = self.cleaned_data.get("evaluate_additional_classes")

        # Validate IP range belongs to subnet's prefix
        if subnet and ip_range:
            child_range_ids = set(subnet.prefix.get_child_ranges().values_list("pk", flat=True))
            if ip_range.pk not in child_range_ids:
                raise ValidationError({"ip_range": "The selected IP range must be a child of this subnet's prefix."})

        # Validate client_class not in evaluate_additional_classes
        if client_class and evaluate_additional:
            if client_class in evaluate_additional:
                raise ValidationError(
                    {
                        "client_class": "The restricting client class should not also appear in "
                        "evaluate-additional-classes."
                    }
                )

        # Validate that a restricting client_class with only_in_additional_list=True
        # is reachable. At pool level, KEA checks client-class AFTER evaluating the
        # subnet's evaluate-additional-classes. So an only-in-additional-list class
        # used as pool restriction is valid ONLY if the parent subnet explicitly lists
        # it in evaluate_additional_classes (triggering its evaluation before pool
        # selection). Without that, KEA never evaluates the class and no client can
        # obtain addresses from the pool.
        if client_class and subnet and client_class.only_in_additional_list:
            subnet_evaluates_class = subnet.evaluate_additional_classes.filter(pk=client_class.pk).exists()
            if not subnet_evaluates_class:
                raise ValidationError(
                    {
                        "client_class": f"Client class '{client_class.name}' has 'only in additional list' enabled. "
                        "KEA will not evaluate it globally. For a pool-level restriction to work, the "
                        "parent subnet must list this class in its 'evaluate additional classes' so that "
                        "KEA evaluates it before pool selection. Either add the class to the subnet's "
                        "evaluate-additional-classes, disable 'only in additional list' on the class, "
                        "or use a different restricting class for this pool."
                    }
                )


class SubnetPoolFilterForm(NetBoxModelFilterSetForm):
    model = SubnetPool
    subnet = DynamicModelChoiceField(queryset=Subnet.objects.all(), required=False)
    client_class = DynamicModelChoiceField(queryset=ClientClass.objects.all(), required=False)


# StaticReservation Forms
class StaticReservationForm(NetBoxModelForm):
    subnet = DynamicModelChoiceField(
        queryset=Subnet.objects.all(),
        help_text="Subnet this reservation belongs to (Kea subnets only)",
    )
    ip_address = DynamicModelChoiceField(
        queryset=IPAddress.objects.all(),
        quick_add=True,
        # Dynamically restricted to the selected subnet's prefix via a plugin
        # endpoint keyed on the subnet's id (data-url set in __init__).
        query_params={"subnet_id": "$subnet"},
        help_text="Reserved IP address (restricted to the selected subnet's prefix)",
    )
    mac_address = DynamicModelChoiceField(
        queryset=MACAddress.objects.all(),
        quick_add=True,
        label="MAC address",
        help_text="Client hardware (MAC) address",
    )

    fieldsets = (
        FieldSet("subnet", "ip_address", "mac_address", "hostname", name="Reservation"),
        FieldSet("source", "external_id", "description", "tags", name="Metadata"),
    )

    class Meta:
        model = StaticReservation
        fields = (
            "subnet",
            "ip_address",
            "mac_address",
            "hostname",
            "source",
            "external_id",
            "description",
            "tags",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Point the IP picker at the plugin endpoint that returns only the IPs
        # contained in the selected subnet's prefix (keyed on ?subnet_id=).
        self.fields["ip_address"].widget.attrs["data-url"] = reverse(
            "plugins-api:netbox_dhcp_kea_plugin-api:subnet-ip-choices"
        )


class StaticReservationFilterForm(NetBoxModelFilterSetForm):
    model = StaticReservation
    subnet = DynamicModelChoiceField(queryset=Subnet.objects.all(), required=False)
    mac_address = DynamicModelChoiceField(
        queryset=MACAddress.objects.all(), required=False, label="MAC address"
    )
    source = forms.CharField(required=False)


class StaticReservationImportForm(NetBoxModelImportForm):
    subnet = CSVModelChoiceField(queryset=Subnet.objects.all(), to_field_name="pk")
    ip_address = CSVModelChoiceField(queryset=IPAddress.objects.all(), to_field_name="address")
    mac_address = CSVModelChoiceField(queryset=MACAddress.objects.all(), to_field_name="mac_address")

    class Meta:
        model = StaticReservation
        fields = (
            "subnet",
            "ip_address",
            "mac_address",
            "hostname",
            "source",
            "external_id",
            "description",
        )


# DHCPHARelationship Forms
class DHCPHARelationshipForm(NetBoxModelForm):
    d2_daemon = DynamicModelChoiceField(
        queryset=D2Daemon.objects.all(),
        required=False,
        label="D2 daemon",
        help_text=(
            "Shared Kea D2 daemon for all member servers. When set, each member's standalone D2 daemon is ignored."
        ),
    )
    ddns_policy = DynamicModelChoiceField(
        queryset=DDNSPolicy.objects.all(),
        required=False,
        label="DDNS policy",
        help_text=(
            "Shared DDNS policy for all member servers. When set, each member's standalone DDNS policy is ignored."
        ),
    )

    fieldsets = (
        FieldSet("name", "mode", "description", "tags", name="General"),
        FieldSet(
            InlineFields("heartbeat_delay", "max_response_delay", label="Heartbeat / Response Delay"),
            InlineFields("max_ack_delay", "max_unacked_clients", label="Ack Delay / Unacked Clients"),
            "max_rejected_lease_updates",
            name="Timing Parameters",
        ),
        FieldSet(
            "enable_multi_threading",
            "http_dedicated_listener",
            InlineFields("http_listener_threads", "http_client_threads", label="Thread Counts"),
            name="Multi-Threading",
        ),
        FieldSet(
            "ha_proxy_enabled",
            name="Reverse Proxy",
        ),
        FieldSet(
            InlineFields("ha_basic_auth_user", "ha_basic_auth_password", label="Credentials"),
            name="HA Authentication",
        ),
        FieldSet(
            "ddns_enable_updates",
            "d2_daemon",
            "ddns_policy",
            name="DDNS",
        ),
    )

    class Meta:
        model = DHCPHARelationship
        fields = (
            "name",
            "mode",
            "heartbeat_delay",
            "max_response_delay",
            "max_ack_delay",
            "max_unacked_clients",
            "max_rejected_lease_updates",
            "enable_multi_threading",
            "http_dedicated_listener",
            "http_listener_threads",
            "http_client_threads",
            "ha_proxy_enabled",
            "ha_basic_auth_user",
            "ha_basic_auth_password",
            "description",
            "d2_daemon",
            "ddns_enable_updates",
            "ddns_policy",
            "tags",
        )
        widgets = {
            "ha_basic_auth_password": forms.PasswordInput(render_value=True),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not get_plugin_config("netbox_dhcp_kea_plugin", "enable_ddns"):
            for fname in ("d2_daemon", "ddns_enable_updates", "ddns_policy"):
                if fname in self.fields:
                    del self.fields[fname]


class DHCPHARelationshipFilterForm(NetBoxModelFilterSetForm):
    model = DHCPHARelationship
    name = forms.CharField(required=False)
    mode = forms.ChoiceField(
        choices=[("", "---------")] + list(DHCPHARelationship.HA_MODE_CHOICES),
        required=False,
    )
    enable_multi_threading = forms.NullBooleanField(
        required=False,
        widget=forms.Select(
            choices=[
                ("", "---------"),
                ("true", "Yes"),
                ("false", "No"),
            ]
        ),
    )


class DHCPHARelationshipImportForm(NetBoxModelImportForm):
    mode = CSVChoiceField(
        choices=DHCPHARelationship.HA_MODE_CHOICES,
        help_text="HA mode: hot-standby, load-balancing, or passive-backup",
    )

    class Meta:
        model = DHCPHARelationship
        fields = (
            "name",
            "mode",
            "heartbeat_delay",
            "max_response_delay",
            "max_ack_delay",
            "max_unacked_clients",
            "max_rejected_lease_updates",
            "enable_multi_threading",
            "http_dedicated_listener",
            "http_listener_threads",
            "http_client_threads",
            "ha_proxy_enabled",
            "ha_basic_auth_user",
            "ha_basic_auth_password",
            "description",
            "tags",
        )


# Hook Forms
class HookForm(NetBoxModelForm):
    allowed_processes = forms.MultipleChoiceField(
        choices=Hook.PROCESS_CHOICES,
        widget=BootstrapCheckboxSelectMultiple(),
        help_text="Select which KEA processes can load this hook library",
        required=False,  # Required validation handled in clean_allowed_processes()
    )

    class Meta:
        model = Hook
        fields = (
            "name",
            "library_name",
            "description",
            "allowed_processes",
            "parameters",
            "tags",
        )
        widgets = {
            "parameters": forms.Textarea(attrs={"class": "font-monospace", "rows": 5}),
        }
        help_texts = {
            "parameters": 'Hook parameters as JSON object (e.g., {"max-threads": 4})',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set initial value for allowed_processes from instance
        if self.instance.pk and self.instance.allowed_processes:
            self.initial["allowed_processes"] = self.instance.allowed_processes

        # If editing a standard hook, only allow editing parameters and tags
        if self.instance.pk and self.instance.is_standard:
            # Make name, library_name, description read-only by disabling them
            # and marking them as not required (we'll restore values in clean)
            self.fields["name"].disabled = True
            self.fields["library_name"].disabled = True
            self.fields["description"].disabled = True
            # Disable allowed_processes checkboxes for standard hooks
            self.fields["allowed_processes"].widget.disabled = True
            self.fields["allowed_processes"].disabled = True

    @property
    def fieldsets(self):
        # Dynamic fieldsets based on whether this is a standard hook
        if self.instance.pk and self.instance.is_standard:
            return (
                FieldSet("name", "library_name", "description", name="Hook Library (Read-Only)"),
                FieldSet("allowed_processes", name="Allowed Processes (Read-Only)"),
                FieldSet("parameters", name="Parameters"),
                FieldSet("tags", name="Tags"),
            )
        else:
            return (
                FieldSet("name", "library_name", "description", name="Hook Library"),
                FieldSet("allowed_processes", name="Allowed Processes"),
                FieldSet("parameters", name="Parameters"),
                FieldSet("tags", name="Tags"),
            )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data is None:
            cleaned_data = self.cleaned_data

        # For standard hooks, preserve the original read-only field values
        # since disabled fields don't submit data
        if self.instance.pk and self.instance.is_standard:
            cleaned_data["name"] = self.instance.name
            cleaned_data["library_name"] = self.instance.library_name
            cleaned_data["description"] = self.instance.description
            cleaned_data["allowed_processes"] = self.instance.allowed_processes

    def clean_allowed_processes(self):
        """Validate allowed_processes for custom hooks."""
        # Skip validation for standard hooks (value will be preserved in clean())
        if self.instance.pk and self.instance.is_standard:
            return self.instance.allowed_processes

        allowed_processes = self.cleaned_data.get("allowed_processes")
        # For custom hooks, require at least one process
        if not allowed_processes:
            raise ValidationError("At least one process must be selected.")
        return list(allowed_processes)  # Ensure it's a list for ArrayField


class HookFilterForm(NetBoxModelFilterSetForm):
    model = Hook
    name = forms.CharField(required=False)
    is_standard = forms.NullBooleanField(
        required=False,
        widget=forms.Select(
            choices=[
                ("", "---------"),
                ("true", "Yes"),
                ("false", "No"),
            ]
        ),
    )
    allowed_processes = forms.MultipleChoiceField(
        choices=Hook.PROCESS_CHOICES,
        required=False,
        widget=BootstrapCheckboxSelectMultiple(),
    )


class HookImportForm(NetBoxModelImportForm):
    class Meta:
        model = Hook
        fields = (
            "name",
            "library_name",
            "description",
            "is_standard",
            "allowed_processes",
            "parameters",
            "tags",
        )


# HookGroup Forms
class HookGroupForm(NetBoxModelForm):
    hooks = DynamicModelMultipleChoiceField(
        queryset=Hook.objects.all(),
        required=False,
        help_text="Select hooks to include in this group",
    )
    servers = DynamicModelMultipleChoiceField(
        queryset=DHCPServer.objects.all(),
        required=False,
        help_text="Select DHCP servers that will use this hook group",
    )

    class Meta:
        model = HookGroup
        fields = (
            "name",
            "description",
            "library_path",
            "hooks",
            "servers",
            "tags",
        )

    fieldsets = (
        FieldSet("name", "description", "tags", name="Hook Group"),
        FieldSet("library_path", name="Library Path"),
        FieldSet("hooks", name="Hooks"),
        FieldSet("servers", name="DHCP Servers"),
    )


class HookGroupFilterForm(NetBoxModelFilterSetForm):
    model = HookGroup
    name = forms.CharField(required=False)
    hooks = DynamicModelMultipleChoiceField(
        queryset=Hook.objects.all(),
        required=False,
    )
    servers = DynamicModelMultipleChoiceField(
        queryset=DHCPServer.objects.all(),
        required=False,
    )


class HookGroupImportForm(NetBoxModelImportForm):
    class Meta:
        model = HookGroup
        fields = (
            "name",
            "description",
            "library_path",
            "tags",
        )


# --- StorkServer Forms ---


class StorkServerForm(NetBoxModelForm):
    ip_address = DynamicModelChoiceField(
        queryset=IPAddress.objects.all(),
        help_text="IP address of the Stork server (from NetBox IPAM)",
    )

    fieldsets = (
        FieldSet(
            "name",
            "description",
            "ip_address",
            "status",
            InlineFields("stork_version", "log_level", label="Version / Log Level"),
            "tags",
            name="General",
        ),
        FieldSet(
            InlineFields("rest_port", "rest_base_url", label="Port / Base URL"),
            "use_tls",
            "endpoint_type",
            "endpoint_record",
            "endpoint_fqdn",
            name="REST API",
        ),
        FieldSet(
            InlineFields("db_host", "db_port", label="Host / Port"),
            InlineFields("db_name", "db_user", label="Database / User"),
            "db_ssl_mode",
            name="Database",
        ),
        FieldSet(
            "enable_metrics",
            "grafana_url",
            name="Monitoring & Integration",
        ),
        FieldSet(
            "default_agent_registration",
            name="Agent Registration",
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._add_endpoint_record_picker()

    def _add_endpoint_record_picker(self):
        """Offer a netbox_dns record for the endpoint, when that plugin is present.

        Unlike DHCPServer's PKI picker this does *not* replace the text field.
        The Stork listener's name may legitimately be served by DNS that NetBox
        does not manage, and a server that cannot be named is unregisterable.
        """
        if not get_plugin_config("netbox_dhcp_kea_plugin", "enable_netbox_dns"):
            return
        try:
            from netbox_dns.models import Record as DNSRecord
        except ImportError:
            return

        self.fields["endpoint_record"] = DynamicModelChoiceField(
            queryset=DNSRecord.objects.filter(type__in=("A", "AAAA", "CNAME"), managed=False, status="active"),
            query_params={"type": ["A", "AAAA", "CNAME"], "managed": False, "status": "active"},
            required=False,
            label="Endpoint DNS record",
            help_text=(
                "The record agents dial. Fills the endpoint FQDN and binds it: the record cannot "
                "be deleted while bound, and renaming it updates the name here."
            ),
            initial=self.instance.endpoint_record_id if self.instance.pk else None,
        )

    def clean(self):
        # NetBoxModelForm.clean() ends in a mixin that returns None on every
        # path, so read self.cleaned_data rather than the return value.
        super().clean()
        cleaned_data = self.cleaned_data

        if "endpoint_record" in self.fields:
            record = cleaned_data.get("endpoint_record")
            self.instance.endpoint_record_id = record.pk if record is not None else None
            if record is not None:
                cleaned_data["endpoint_fqdn"] = normalize_fqdn(record.fqdn)
        cleaned_data["endpoint_fqdn"] = normalize_fqdn(cleaned_data.get("endpoint_fqdn"))
        self.instance.endpoint_fqdn = cleaned_data["endpoint_fqdn"]
        return cleaned_data

    class Meta:
        model = StorkServer
        fields = (
            "name",
            "description",
            "ip_address",
            "status",
            "rest_port",
            "rest_base_url",
            "use_tls",
            "endpoint_type",
            "endpoint_fqdn",
            "db_host",
            "db_port",
            "db_name",
            "db_user",
            "db_ssl_mode",
            "enable_metrics",
            "grafana_url",
            "default_agent_registration",
            "stork_version",
            "log_level",
            "tags",
        )


class StorkServerFilterForm(NetBoxModelFilterSetForm):
    model = StorkServer
    status = forms.ChoiceField(
        choices=[("", "---------")] + list(DeviceStatusChoices),
        required=False,
    )
    use_tls = forms.NullBooleanField(required=False)
    enable_metrics = forms.NullBooleanField(required=False)


class StorkServerImportForm(NetBoxModelImportForm):
    class Meta:
        model = StorkServer
        fields = (
            "name",
            "description",
            "ip_address",
            "status",
            "rest_port",
            "rest_base_url",
            "use_tls",
            "endpoint_type",
            "endpoint_fqdn",
            "db_host",
            "db_port",
            "db_name",
            "db_user",
            "db_ssl_mode",
            "enable_metrics",
            "grafana_url",
            "default_agent_registration",
            "stork_version",
            "log_level",
        )


# --- StorkAgentGroup Forms ---


class StorkAgentGroupForm(NetBoxModelForm):
    stork_server = DynamicModelChoiceField(
        queryset=StorkServer.objects.all(),
        required=False,
        help_text="Stork server these agents report to (required unless Prometheus-only mode)",
    )

    fieldsets = (
        FieldSet(
            "name",
            "description",
            "stork_server",
            "operating_mode",
            "tags",
            name="General",
        ),
        FieldSet(
            "agent_port",
            name="Agent gRPC Settings",
        ),
        FieldSet(
            "skip_tls_cert_verification",
            name="Kea Connection",
        ),
        FieldSet(
            InlineFields("prometheus_exporter_address", "prometheus_exporter_port", label="Address / Port"),
            "prometheus_per_subnet_stats",
            name="Prometheus Exporter",
        ),
        FieldSet(
            "log_level",
            name="Logging",
        ),
    )

    class Meta:
        model = StorkAgentGroup
        fields = (
            "name",
            "description",
            "stork_server",
            "operating_mode",
            "agent_port",
            "prometheus_exporter_address",
            "prometheus_exporter_port",
            "prometheus_per_subnet_stats",
            "skip_tls_cert_verification",
            "log_level",
            "tags",
        )


class StorkAgentGroupFilterForm(NetBoxModelFilterSetForm):
    model = StorkAgentGroup
    stork_server = DynamicModelChoiceField(
        queryset=StorkServer.objects.all(),
        required=False,
    )
    operating_mode = forms.ChoiceField(
        choices=[("", "---------")] + list(StorkAgentGroup.OPERATING_MODE_CHOICES),
        required=False,
    )
    server = DynamicModelChoiceField(
        queryset=DHCPServer.objects.all(),
        required=False,
        label="DHCP Server",
    )


class StorkAgentGroupImportForm(NetBoxModelImportForm):
    class Meta:
        model = StorkAgentGroup
        fields = (
            "name",
            "description",
            "stork_server",
            "operating_mode",
            "agent_port",
            "prometheus_exporter_address",
            "prometheus_exporter_port",
            "prometheus_per_subnet_stats",
            "skip_tls_cert_verification",
            "log_level",
        )


# --- DDNS Forms ---


class TSIGKeyForm(NetBoxModelForm):
    fieldsets = (
        FieldSet("name", "description", "tags", name="General"),
        FieldSet("algorithm", "digest_bits", name="Algorithm"),
        FieldSet("secret_backend", "secret_plaintext", "secret_ref", name="Secret"),
    )

    class Meta:
        model = TSIGKey
        fields = (
            "name",
            "description",
            "algorithm",
            "digest_bits",
            "secret_backend",
            "secret_plaintext",
            "secret_ref",
            "tags",
        )
        widgets = {
            "secret_backend": HTMXSelect(),
            "secret_plaintext": forms.PasswordInput(render_value=True),
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        # Show only the secret field relevant to the selected backend.
        secret_backend = get_field_value(self, "secret_backend")
        if secret_backend != "plaintext":
            del self.fields["secret_plaintext"]
        if secret_backend != "vault":
            del self.fields["secret_ref"]

        # Hide the plaintext secret from users who lack the reveal perm when
        # editing. New objects always show the field (you need to set it
        # somehow, and creating the row implies write).
        if self.instance.pk and request is not None:
            if not request.user.has_perm("netbox_dhcp_kea_plugin.view_secret_tsigkey"):
                if "secret_plaintext" in self.fields:
                    del self.fields["secret_plaintext"]


class TSIGKeyFilterForm(NetBoxModelFilterSetForm):
    model = TSIGKey
    name = forms.CharField(required=False)
    algorithm = forms.ChoiceField(
        choices=[("", "---------")] + list(TSIGKey._meta.get_field("algorithm").choices or []),
        required=False,
    )
    secret_backend = forms.ChoiceField(
        choices=[("", "---------")] + list(TSIGKey._meta.get_field("secret_backend").choices or []),
        required=False,
    )


class TSIGKeyImportForm(NetBoxModelImportForm):
    class Meta:
        model = TSIGKey
        fields = (
            "name",
            "description",
            "algorithm",
            "digest_bits",
            "secret_backend",
            "secret_plaintext",
            "secret_ref",
        )


class D2DaemonForm(NetBoxModelForm):
    ip_address = DynamicModelChoiceField(
        queryset=IPAddress.objects.all(),
        required=False,
        help_text="Listener IP for NameChangeRequests from kea-dhcp4/6 (only when mode is 'remote')",
    )

    fieldsets = (
        FieldSet("name", "description", "tags", name="General"),
        FieldSet(
            "listener_mode",
            InlineFields("ip_address", "port", label="Listener"),
            name="NCR Listener",
        ),
        FieldSet("ncr_protocol", "ncr_format", name="NCR Transport"),
        FieldSet("control_socket_path", name="Control Socket"),
    )

    class Meta:
        model = D2Daemon
        fields = (
            "name",
            "description",
            "listener_mode",
            "ip_address",
            "port",
            "ncr_protocol",
            "ncr_format",
            "control_socket_path",
            "tags",
        )
        widgets = {
            "listener_mode": HTMXSelect(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Default the control socket path from plugin config when creating
        # a new D2Daemon (existing rows keep whatever they were saved with).
        # Set form.initial (not field.initial) — ModelForm populates initial
        # from the empty model instance and that wins over field.initial.
        if not self.instance.pk and not self.initial.get("control_socket_path"):
            self.initial["control_socket_path"] = get_plugin_config(
                "netbox_dhcp_kea_plugin", "d2_default_control_socket_path"
            )
        # Hide ip_address and port when the daemon is in local-listener mode —
        # each peer runs its own D2 on 127.0.0.1 with the model default port.
        if get_field_value(self, "listener_mode") == D2Daemon.LISTENER_MODE_LOCAL:
            for fname in ("ip_address", "port"):
                self.fields.pop(fname, None)


class D2DaemonFilterForm(NetBoxModelFilterSetForm):
    model = D2Daemon
    name = forms.CharField(required=False)
    ip_address = DynamicModelChoiceField(queryset=IPAddress.objects.all(), required=False)
    ncr_protocol = forms.ChoiceField(
        choices=[("", "---------"), ("UDP", "UDP"), ("TCP", "TCP")],
        required=False,
    )


class D2DaemonImportForm(NetBoxModelImportForm):
    ip_address = CSVModelChoiceField(
        queryset=IPAddress.objects.all(),
        to_field_name="address",
        required=False,
    )

    class Meta:
        model = D2Daemon
        fields = (
            "name",
            "description",
            "listener_mode",
            "ip_address",
            "port",
            "ncr_protocol",
            "ncr_format",
            "control_socket_path",
        )


try:
    from netbox_dns.models import Zone as _DNSZone
except ImportError:  # netbox_dns is optional unless enable_ddns=True
    _DNSZone = None


class DDNSDomainForm(NetBoxModelForm):
    d2_daemon = DynamicModelChoiceField(queryset=D2Daemon.objects.all())
    tsig_key = DynamicModelChoiceField(
        queryset=TSIGKey.objects.all(),
        required=False,
        quick_add=True,
        help_text="TSIG key for authenticating updates to this zone (optional)",
    )

    fieldsets = (FieldSet("d2_daemon", "zone", "tsig_key", "tags", name="General"),)

    class Meta:
        model = DDNSDomain
        fields = ("d2_daemon", "zone", "tsig_key", "tags")

    def __init__(self, *args, **kwargs):
        if _DNSZone is None:
            raise RuntimeError("DDNSDomainForm requires netbox-plugin-dns to be installed.")
        super().__init__(*args, **kwargs)
        if self.instance.pk is None:
            # Create mode: pick any number of zones (forward and/or reverse).
            # One DDNSDomain row will be created per selected zone; direction
            # is derived from each zone's name at config-emission time.
            self.fields["zone"] = DynamicModelMultipleChoiceField(
                queryset=_DNSZone.objects.all(),
                label="Zones",
                help_text=(
                    "Select one or more forward and/or reverse zones managed "
                    "by this D2 daemon. One DDNS Domain row is created per "
                    "selected zone."
                ),
            )
        else:
            # Edit mode: a row binds exactly one zone.
            self.fields["zone"] = DynamicModelChoiceField(
                queryset=_DNSZone.objects.all(),
                help_text=(
                    "Forward or reverse zone managed by this D2 daemon. "
                    "Authoritative DNS servers are taken from the zone's "
                    "nameservers."
                ),
            )

    def _post_clean(self):
        # In create mode, ``zone`` is a queryset of multiple Zones — Django's
        # ModelForm._post_clean() would try to assign it to the single-FK
        # ``instance.zone`` and ValueError. Temporarily swap in the first
        # selected zone so model-level validation has a real instance, then
        # restore the queryset for our save() override.
        zones = self.cleaned_data.get("zone")
        if self.instance.pk is None and zones is not None and not isinstance(zones, _DNSZone):
            zone_list = list(zones)
            if zone_list:
                self.cleaned_data["zone"] = zone_list[0]
                try:
                    super()._post_clean()
                finally:
                    self.cleaned_data["zone"] = zone_list
                return
        super()._post_clean()

    def save(self, commit=True):
        # Edit path: standard single-instance save.
        if self.instance.pk:
            return super().save(commit=commit)

        zones_or_one = self.cleaned_data.get("zone")
        zones = [zones_or_one] if isinstance(zones_or_one, _DNSZone) else list(zones_or_one or [])
        d2_daemon = self.cleaned_data["d2_daemon"]
        tsig_key = self.cleaned_data.get("tsig_key")
        tags = self.cleaned_data.get("tags") or []

        created = []
        for z in zones:
            obj, was_created = DDNSDomain.objects.get_or_create(
                d2_daemon=d2_daemon,
                zone=z,
                defaults={"tsig_key": tsig_key},
            )
            new_tsig_pk = tsig_key.pk if tsig_key else None
            if not was_created and obj.tsig_key_id != new_tsig_pk:
                obj.tsig_key = tsig_key
                obj.save()
            if tags:
                obj.tags.set(tags)
            created.append(obj)

        # Point self.instance at one of the new rows so the view's success
        # message and redirect have something to chew on.
        self.instance = created[0] if created else self.instance
        return self.instance


class DDNSDomainFilterForm(NetBoxModelFilterSetForm):
    model = DDNSDomain
    d2_daemon = DynamicModelChoiceField(queryset=D2Daemon.objects.all(), required=False)
    tsig_key = DynamicModelChoiceField(queryset=TSIGKey.objects.all(), required=False)


class DDNSDomainImportForm(NetBoxModelImportForm):
    d2_daemon = CSVModelChoiceField(queryset=D2Daemon.objects.all(), to_field_name="name")
    tsig_key = CSVModelChoiceField(
        queryset=TSIGKey.objects.all(),
        to_field_name="name",
        required=False,
    )

    class Meta:
        model = DDNSDomain
        fields = ("d2_daemon", "zone", "tsig_key")


class DHCPServerBulkEditForm(NetBoxModelBulkEditForm):
    """Bulk edit for DHCP servers.

    Only fields that can sensibly hold the same value across several servers
    appear here. Name, IP address, HA address and PKI FQDN are each unique to
    one host, so setting them in bulk could only ever produce a collision.
    """

    description = forms.CharField(max_length=200, required=False)
    status = forms.ChoiceField(choices=[("", "---------")] + list(DeviceStatusChoices), required=False)
    service_template = DynamicModelChoiceField(
        queryset=ServiceTemplate.objects.all(), required=False, query_params={"tag": "dhcp"}
    )
    ha_relationship = DynamicModelChoiceField(queryset=DHCPHARelationship.objects.all(), required=False)
    ha_role = forms.ChoiceField(
        choices=[("", "---------")] + list(DHCPServer.HA_ROLE_CHOICES), required=False
    )
    ha_port = forms.IntegerField(required=False)
    ha_tls = forms.NullBooleanField(required=False, widget=BulkEditNullBooleanSelect())
    ha_auto_failover = forms.NullBooleanField(required=False, widget=BulkEditNullBooleanSelect())
    ha_egress_base_port = forms.IntegerField(required=False)
    stork_agent_group = DynamicModelChoiceField(queryset=StorkAgentGroup.objects.all(), required=False)
    stork_proxy_enabled = forms.NullBooleanField(required=False, widget=BulkEditNullBooleanSelect())
    ctrl_socket_type = forms.ChoiceField(
        choices=[("", "---------")] + list(DHCPServer.CTRL_SOCKET_TYPE_CHOICES), required=False
    )
    ctrl_socket_http_port = forms.IntegerField(required=False)
    ctrl_socket_proxy_enabled = forms.NullBooleanField(required=False, widget=BulkEditNullBooleanSelect())
    reservations_global = forms.NullBooleanField(required=False, widget=BulkEditNullBooleanSelect())
    reservations_in_subnet = forms.NullBooleanField(required=False, widget=BulkEditNullBooleanSelect())
    reservations_out_of_pool = forms.NullBooleanField(required=False, widget=BulkEditNullBooleanSelect())

    model = DHCPServer
    fieldsets = (
        FieldSet("status", "description", "service_template", name="General"),
        FieldSet(
            "ha_relationship",
            "ha_role",
            "ha_port",
            "ha_tls",
            "ha_auto_failover",
            "ha_egress_base_port",
            name="High Availability",
        ),
        FieldSet("stork_agent_group", "stork_proxy_enabled", name="Stork Monitoring"),
        FieldSet(
            "ctrl_socket_type",
            "ctrl_socket_http_port",
            "ctrl_socket_proxy_enabled",
            name="Control Sockets",
        ),
        FieldSet(
            "reservations_global",
            "reservations_in_subnet",
            "reservations_out_of_pool",
            name="Reservations",
        ),
    )
    nullable_fields = ("description", "service_template", "ha_relationship", "stork_agent_group")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not get_plugin_config("netbox_dhcp_kea_plugin", "enable_stork"):
            for fname in ("stork_agent_group", "stork_proxy_enabled"):
                self.fields.pop(fname, None)


class DDNSDomainBulkEditForm(NetBoxModelBulkEditForm):
    d2_daemon = DynamicModelChoiceField(queryset=D2Daemon.objects.all(), required=False)
    tsig_key = DynamicModelChoiceField(queryset=TSIGKey.objects.all(), required=False)

    model = DDNSDomain
    fieldsets = (FieldSet("d2_daemon", "tsig_key"),)
    nullable_fields = ("tsig_key",)


class DDNSPolicyForm(NetBoxModelForm):
    ddns_send_updates = forms.NullBooleanField(required=False)
    ddns_override_no_update = forms.NullBooleanField(required=False)
    ddns_override_client_update = forms.NullBooleanField(required=False)
    ddns_update_on_renew = forms.NullBooleanField(required=False)

    fieldsets = (
        FieldSet("name", "description", "tags", name="General"),
        FieldSet(
            "ddns_send_updates",
            "ddns_override_no_update",
            "ddns_override_client_update",
            "ddns_update_on_renew",
            "ddns_replace_client_name",
            name="Override Flags",
        ),
        FieldSet(
            "ddns_generated_prefix",
            "ddns_qualifying_suffix",
            "hostname_char_set",
            "hostname_char_replacement",
            name="Hostname",
        ),
        FieldSet(
            "ddns_conflict_resolution_mode",
            name="Conflict Resolution",
        ),
        FieldSet(
            "ddns_ttl_percent",
            InlineFields("ddns_ttl", "ddns_ttl_min", "ddns_ttl_max", label="TTL (abs / min / max)"),
            name="TTL",
        ),
    )

    class Meta:
        model = DDNSPolicy
        fields = (
            "name",
            "description",
            "ddns_send_updates",
            "ddns_override_no_update",
            "ddns_override_client_update",
            "ddns_replace_client_name",
            "ddns_generated_prefix",
            "ddns_qualifying_suffix",
            "hostname_char_set",
            "hostname_char_replacement",
            "ddns_update_on_renew",
            "ddns_conflict_resolution_mode",
            "ddns_ttl_percent",
            "ddns_ttl",
            "ddns_ttl_min",
            "ddns_ttl_max",
            "tags",
        )


class DDNSPolicyFilterForm(NetBoxModelFilterSetForm):
    model = DDNSPolicy
    name = forms.CharField(required=False)
    server = DynamicModelChoiceField(
        queryset=DHCPServer.objects.all(),
        required=False,
        label="DHCP Server",
    )
    subnet = DynamicModelChoiceField(
        queryset=Subnet.objects.all(),
        required=False,
    )
    client_class = DynamicModelChoiceField(
        queryset=ClientClass.objects.all(),
        required=False,
    )


class DDNSPolicyImportForm(NetBoxModelImportForm):
    class Meta:
        model = DDNSPolicy
        fields = (
            "name",
            "description",
            "ddns_send_updates",
            "ddns_override_no_update",
            "ddns_override_client_update",
            "ddns_replace_client_name",
            "ddns_generated_prefix",
            "ddns_qualifying_suffix",
            "hostname_char_set",
            "hostname_char_replacement",
            "ddns_update_on_renew",
            "ddns_conflict_resolution_mode",
            "ddns_ttl_percent",
            "ddns_ttl",
            "ddns_ttl_min",
            "ddns_ttl_max",
        )
