"""Top-level package for NetBox DHCP-KEA Plugin."""

__author__ = """Łukasz Polański"""
__email__ = "wookasz@gmail.com"
__version__ = "0.9.0"


from netbox.plugins import PluginConfig
from rest_framework import serializers


class DHCPKEAConfig(PluginConfig):
    name = "netbox_dhcp_kea_plugin"
    verbose_name = "NetBox DHCP-KEA Plugin"
    description = "NetBox plugin for KEA DHCP configuration"
    version = __version__
    author = __author__
    author_email = __email__
    base_url = "netbox_dhcp_kea_plugin"
    default_settings = {
        "top_level_menu": True,
        "menu_name": "DHCP KEA",
        "enable_stork": True,
        "enable_netbox_dns": False,
        "enable_ddns": False,
        "ddns_secret_backend": "plaintext",
        "d2_default_control_socket_path": "/tmp/kea-dhcp-ddns-ctrl.sock",
        "model_defaults": {
            "Subnet": {
                "valid_lifetime": 3600,
                "max_lifetime": 7200,
                "reservations_global": False,
                "reservations_in_subnet": True,
                "reservations_out_of_pool": True,
                "reservations_only": False,
            },
        },
        "demo_data": {
            "enabled": False,
            "vendor_option_spaces": 3,
            "option_definitions_per_space": 5,
            "option_data": 10,
            "client_classes": 5,
            "dhcp_servers": 3,
            "ha_relationships": 1,
            "dhcp_subnets": 5,
        },
    }

    def ready(self):
        """Extend Prefix API serializer with DHCP config and relay targets."""
        super().ready()

        from ipam.api.serializers import PrefixSerializer

        from .models import Subnet

        def get_dhcp_config(self, obj):
            """Return DHCP config with server info and relay targets."""
            try:
                config = obj.dhcp_config
            except Subnet.DoesNotExist:
                return None

            if not config or not config.server:
                return None

            return config.get_relay_config()

        # Create the SerializerMethodField
        dhcp_config_field = serializers.SerializerMethodField()

        # Add to _declared_fields (this is what DRF actually uses)
        PrefixSerializer._declared_fields["dhcp_config"] = dhcp_config_field

        # Add the method to the class
        PrefixSerializer.get_dhcp_config = get_dhcp_config

        # Add dhcp_config to the fields list
        if hasattr(PrefixSerializer.Meta, "fields") and isinstance(PrefixSerializer.Meta.fields, list):
            if "dhcp_config" not in PrefixSerializer.Meta.fields:
                PrefixSerializer.Meta.fields.append("dhcp_config")

        # Protect IP sources from deletion — GenericFK has no DB-level constraint
        self._register_ip_source_protection()

        # DDNS depends on netbox-dns for Zone and NameServer objects
        self._validate_ddns_dependencies()

    @staticmethod
    def _validate_ddns_dependencies():
        """Raise if enable_ddns=True but netbox-dns isn't available."""
        from django.conf import settings
        from django.core.exceptions import ImproperlyConfigured

        cfg = settings.PLUGINS_CONFIG.get("netbox_dhcp_kea_plugin", {})
        if not cfg.get("enable_ddns"):
            return

        if not cfg.get("enable_netbox_dns"):
            raise ImproperlyConfigured(
                "netbox_dhcp_kea_plugin: enable_ddns=True requires "
                "enable_netbox_dns=True — DDNS zones and nameservers are "
                "pulled from the netbox-plugin-dns integration."
            )

        try:
            import netbox_dns  # noqa: F401
        except ImportError as exc:
            raise ImproperlyConfigured(
                "netbox_dhcp_kea_plugin: enable_ddns=True but "
                "netbox_dns could not be imported. Install netbox-plugin-dns "
                "and add it to PLUGINS."
            ) from exc

    @staticmethod
    def _register_ip_source_protection():
        """Register pre_delete signal to prevent deletion of objects linked as IP sources."""
        from django.contrib.contenttypes.models import ContentType
        from django.db.models import ProtectedError
        from django.db.models.signals import pre_delete

        from .models import OptionDataIPSource

        def protect_ip_source(sender, instance, **kwargs):
            ct = ContentType.objects.get_for_model(instance)
            refs = OptionDataIPSource.objects.filter(content_type=ct, object_id=instance.pk)
            if refs.exists():
                option_names = ", ".join(refs.values_list("option_data__distinctive_name", flat=True))
                raise ProtectedError(
                    f"Cannot delete {instance} — it is linked as an IP source on Option Data: {option_names}",
                    set(refs),
                )

        # Protect IPAM IPAddress
        from ipam.models import IPAddress

        pre_delete.connect(protect_ip_source, sender=IPAddress)

        # Protect netbox-dns Record if available
        try:
            from netbox_dns.models import Record as DNSRecord

            pre_delete.connect(protect_ip_source, sender=DNSRecord)
        except ImportError:
            pass


config = DHCPKEAConfig
