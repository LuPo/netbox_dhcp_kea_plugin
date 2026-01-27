from dcim.models import Manufacturer
from django import forms
from django.core.exceptions import ValidationError
from ipam.models import IPAddress, Prefix, ServiceTemplate
from netbox.forms import (
    NetBoxModelFilterSetForm,
    NetBoxModelForm,
    NetBoxModelImportForm,
)
from utilities.forms.fields import (
    CSVChoiceField,
    CSVModelChoiceField,
    DynamicModelChoiceField,
    DynamicModelMultipleChoiceField,
)
from utilities.forms.rendering import FieldSet

from .models import (
    ClientClass,
    DHCPHARelationship,
    DHCPServer,
    OptionData,
    OptionDefinition,
    PrefixDHCPConfig,
    VendorOptionSpace,
)


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


class DHCPServerImportForm(NetBoxModelImportForm):
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

    class Meta:
        model = DHCPServer
        fields = (
            "name",
            "description",
            "ip_address",
            "is_active",
            "service_template",
            "ha_relationship",
            "ha_role",
            "ha_url",
            "ha_auto_failover",
            "ha_basic_auth_user",
            "ha_basic_auth_password",
            "tags",
        )


class ClientClassImportForm(NetBoxModelImportForm):
    class Meta:
        model = ClientClass
        fields = (
            "name",
            "test_expression",
            "description",
            "next_server",
            "server_hostname",
            "boot_file_name",
            "tags",
        )


class PrefixDHCPConfigImportForm(NetBoxModelImportForm):
    prefix = CSVModelChoiceField(
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

    class Meta:
        model = PrefixDHCPConfig
        fields = (
            "prefix",
            "server",
            "valid_lifetime",
            "max_lifetime",
            "routers_option_offset",
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
            except VRF.DoesNotExist:
                raise forms.ValidationError({"vrf": f"VRF {vrf_name} does not exist."})

        return self.cleaned_data


# Edit Forms


class VendorOptionSpaceForm(NetBoxModelForm):
    manufacturer = DynamicModelChoiceField(
        queryset=Manufacturer.objects.all(),
        required=False,
        help_text="Manufacturer/vendor associated with this option space",
    )

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
        return self.cleaned_data


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
        },
        help_text="Option definition - filtered by vendor option space (or standard/custom if none selected)",
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


class DHCPServerForm(NetBoxModelForm):
    ip_address = DynamicModelChoiceField(
        queryset=IPAddress.objects.all(),
        help_text="IP address of the DHCP server (from NetBox IPAM)",
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

    class Meta:
        model = DHCPServer
        fields = (
            "name",
            "description",
            "ip_address",
            "is_active",
            "service_template",
            "option_data",
            "ha_relationship",
            "ha_role",
            "ha_url",
            "ha_auto_failover",
            "ha_basic_auth_user",
            "ha_basic_auth_password",
            "tags",
        )
        fieldsets = (
            FieldSet(
                "name",
                "description",
                "ip_address",
                "is_active",
                "service_template",
                "option_data",
                "tags",
                name="General",
            ),
            FieldSet("ha_relationship", "ha_role", "ha_url", "ha_auto_failover", name="High Availability"),
            FieldSet("ha_basic_auth_user", "ha_basic_auth_password", name="HA Authentication"),
        )
        widgets = {
            "ha_basic_auth_password": forms.PasswordInput(render_value=True),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate client_classes from reverse relation
        if self.instance.pk:
            self.initial["client_classes"] = self.instance.client_classes.all()

    def save(self, *args, **kwargs):
        instance = super().save(*args, **kwargs)
        # Handle client_classes (reverse ManyToMany relation)
        if "client_classes" in self.cleaned_data:
            # Get the selected client classes
            selected_classes = self.cleaned_data["client_classes"]
            # Get current client classes linked to this server
            current_classes = set(instance.client_classes.all())
            selected_set = set(selected_classes)

            # Remove server from classes that were deselected
            for cc in current_classes - selected_set:
                cc.servers.remove(instance)

            # Add server to newly selected classes
            for cc in selected_set - current_classes:
                cc.servers.add(instance)

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

    class Meta:
        model = ClientClass
        fields = (
            "name",
            "test_expression",
            "description",
            "servers",
            "option_data",
            "local_definitions",
            "next_server",
            "server_hostname",
            "boot_file_name",
            "tags",
        )

    def clean_option_data(self):
        """Validate that no two option data entries have the same space and code."""
        option_data = self.cleaned_data.get("option_data")
        validate_unique_option_data_space_code(option_data)
        return option_data


class PrefixDHCPConfigForm(NetBoxModelForm):
    prefix = DynamicModelChoiceField(queryset=Prefix.objects.all())
    server = DynamicModelChoiceField(queryset=DHCPServer.objects.all())
    option_data = DynamicModelMultipleChoiceField(
        queryset=OptionData.objects.all(),
        required=False,
        help_text="Option data for this subnet",
    )
    client_classes = DynamicModelMultipleChoiceField(queryset=ClientClass.objects.all(), required=False)
    routers_option_offset = forms.IntegerField(
        required=False,
        min_value=0,
        initial=1,
        help_text="Offset from network address for router IP (e.g., 1 for .1, 254 for .254). Set to 0 to disable routers option.",
    )

    fieldsets = (
        FieldSet("prefix", "server", name="Prefix Assignment"),
        FieldSet("valid_lifetime", "max_lifetime", name="Lease Timing"),
        FieldSet("routers_option_offset", "option_data", name="DHCP Options"),
        FieldSet("client_classes", name="Client Classes"),
    )

    class Meta:
        model = PrefixDHCPConfig
        fields = (
            "prefix",
            "server",
            "valid_lifetime",
            "max_lifetime",
            "routers_option_offset",
            "option_data",
            "client_classes",
            "tags",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Track if server was redirected to primary (for messaging)
        self._redirected_to_primary = False
        self._original_server_name = None

    def clean_option_data(self):
        """Validate that no two option data entries have the same space and code."""
        option_data = self.cleaned_data.get("option_data")
        validate_unique_option_data_space_code(option_data)
        return option_data

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
    is_active = forms.NullBooleanField(
        required=False,
        widget=forms.Select(
            choices=[
                ("", "---------"),
                ("true", "Yes"),
                ("false", "No"),
            ]
        ),
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


class PrefixDHCPConfigFilterForm(NetBoxModelFilterSetForm):
    model = PrefixDHCPConfig
    server = DynamicModelChoiceField(queryset=DHCPServer.objects.all(), required=False)


# DHCPHARelationship Forms
class DHCPHARelationshipForm(NetBoxModelForm):
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
            "description",
            "tags",
        )
        fieldsets = (
            FieldSet("name", "mode", "description", "tags", name="General"),
            FieldSet(
                "heartbeat_delay",
                "max_response_delay",
                "max_ack_delay",
                "max_unacked_clients",
                "max_rejected_lease_updates",
                name="Timing Parameters",
            ),
            FieldSet(
                "enable_multi_threading",
                "http_dedicated_listener",
                "http_listener_threads",
                "http_client_threads",
                name="Multi-Threading",
            ),
        )


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
            "description",
            "tags",
        )
