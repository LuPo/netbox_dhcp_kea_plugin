from dcim.models import Manufacturer
from django import forms
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
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
    Hook,
    HookGroup,
    OptionData,
    OptionDefinition,
    PrefixDHCPConfig,
    VendorOptionSpace,
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
    ha_url = forms.URLField(
        required=False,
        assume_scheme="https",
        help_text="URL for HA communication (e.g., http://192.168.1.1:8000/)",
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
            "only_in_additional_list",
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure csv_format defaults to True (matching model default)
        if not self.instance.pk:
            self.fields["csv_format"].initial = True

    def clean_csv_format(self):
        """Set csv_format to True if not provided (matching model default)"""
        csv_format = self.cleaned_data.get("csv_format")
        # If csv_format is not explicitly set to False, default to True
        if csv_format is None or csv_format == "":
            return True
        return csv_format


class DHCPServerForm(NetBoxModelForm):
    ip_address = DynamicModelChoiceField(
        queryset=IPAddress.objects.all(),
        help_text="IP address of the DHCP server (from NetBox IPAM)",
    )
    ha_url = forms.URLField(
        required=False,
        assume_scheme="https",
        help_text="URL for HA communication (e.g., http://192.168.1.1:8000/)",
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
            FieldSet("hook_groups", name="Hook Libraries"),
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
            self.initial["hook_groups"] = self.instance.hook_groups.all()

        # Hide option_data and client_classes fields if this is a non-primary HA server
        if self.instance.pk and self.instance.ha_relationship and not self.instance.is_ha_primary():
            # Remove these fields from the form as they should only be managed on the primary
            if "option_data" in self.fields:
                del self.fields["option_data"]
            if "client_classes" in self.fields:
                del self.fields["client_classes"]

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
            "tags",
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


class PrefixDHCPConfigForm(NetBoxModelForm):
    prefix = DynamicModelChoiceField(queryset=Prefix.objects.all())
    server = DynamicModelChoiceField(queryset=DHCPServer.objects.all())
    option_data = DynamicModelMultipleChoiceField(
        queryset=OptionData.objects.all(),
        required=False,
        help_text="Option data for this subnet",
    )
    client_classes = DynamicModelMultipleChoiceField(
        queryset=ClientClass.objects.all(),
        required=False,
        query_params={"only_in_additional_list": True},
        help_text="Client classes to evaluate additionally for this subnet (only classes with 'Only in additional list' enabled)",
    )
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

        return cleaned_data

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
        FieldSet("name", "description", name="Hook Group"),
        FieldSet("library_path", name="Library Path"),
        FieldSet("hooks", name="Hooks"),
        FieldSet("servers", name="DHCP Servers"),
        FieldSet("tags", name="Tags"),
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
