"""
Pytest configuration for NetBox plugin testing.

To run tests, you need:
1. NetBox installed and configured
2. Plugin installed in development mode: pip install -e .
3. pytest-django installed: pip install pytest-django
4. Run from within NetBox's virtual environment

Usage:
    cd /path/to/netbox
    source venv/bin/activate
    cd /path/to/netbox-dhcp-kea-plugin
    pytest tests/ -v
"""

import os
import sys

import django
import pytest


def pytest_configure(config):
    """Configure Django settings for pytest."""
    # Add NetBox to the path
    netbox_path = os.environ.get("NETBOX_PATH", "/home/lupo/Github/netbox/netbox")
    if netbox_path not in sys.path:
        sys.path.insert(0, netbox_path)

    # Set Django settings module
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "netbox.settings")

    # Setup Django
    django.setup()


# Enable database access for all tests
@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """Automatically enable database access for all tests using pytest-django's db fixture."""
    pass


@pytest.fixture
def manufacturer(db):
    """Create a test Manufacturer."""
    from dcim.models import Manufacturer

    return Manufacturer.objects.create(name="Test Vendor Inc", slug="test-vendor-inc")


@pytest.fixture
def vendor_option_space(db, manufacturer):
    """Create a test VendorOptionSpace."""
    from netbox_dhcp_kea_plugin.models import VendorOptionSpace

    return VendorOptionSpace.objects.create(
        name="TestVendor", enterprise_id=12345, manufacturer=manufacturer, description="Test vendor space"
    )


@pytest.fixture
def option_definition(db, vendor_option_space):
    """Create a test OptionDefinition."""
    from netbox_dhcp_kea_plugin.models import OptionDefinition

    return OptionDefinition.objects.create(
        name="test-option",
        code=1,
        option_type="string",
        option_space="dhcp4",
        vendor_option_space=vendor_option_space,
        is_standard=False,
        description="Test option",
    )


@pytest.fixture
def option_definition_no_vendor(db):
    """Create a test OptionDefinition without vendor space."""
    from netbox_dhcp_kea_plugin.models import OptionDefinition

    return OptionDefinition.objects.create(
        name="standard-option",
        code=100,
        option_type="string",
        option_space="dhcp4",
        is_standard=False,
        description="Standard test option",
    )


@pytest.fixture
def option_data(db, option_definition):
    """Create a test OptionData."""
    from netbox_dhcp_kea_plugin.models import OptionData

    return OptionData.objects.create(
        distinctive_name="test-option-data",
        definition=option_definition,
        option_space="dhcp4",
        vendor_option_space=option_definition.vendor_option_space,
        delivery_type="option43",
        data="test-value",
        always_send=False,
        csv_format=True,
    )


@pytest.fixture
def option_data_standard(db, option_definition_no_vendor):
    """Create a test OptionData with standard delivery."""
    from netbox_dhcp_kea_plugin.models import OptionData

    return OptionData.objects.create(
        distinctive_name="standard-option-data",
        definition=option_definition_no_vendor,
        option_space="dhcp4",
        delivery_type="standard",
        data="standard-value",
        always_send=False,
        csv_format=True,
    )


@pytest.fixture
def client_class(db):
    """Create a test ClientClass."""
    from netbox_dhcp_kea_plugin.models import ClientClass

    return ClientClass.objects.create(
        name="TestClass",
        test_expression="option[60].hex == 'test'",
        description="Test client class",
        local_definitions=False,
    )


@pytest.fixture
def client_class_local_defs(db):
    """Create a test ClientClass with local_definitions=True."""
    from netbox_dhcp_kea_plugin.models import ClientClass

    return ClientClass.objects.create(
        name="TestClassLocalDefs",
        test_expression="option[60].hex == 'local'",
        description="Test client class with local definitions",
        local_definitions=True,
    )


@pytest.fixture
def ip_address(db):
    """Create a test IP address."""
    from ipam.models import IPAddress

    return IPAddress.objects.create(
        address="192.168.1.1/24",
    )


@pytest.fixture
def service_template(db):
    """Create a test ServiceTemplate."""
    from ipam.models import ServiceTemplate

    return ServiceTemplate.objects.create(
        name="dhcp-test",
        protocol="udp",
        ports=[67, 68],
    )


@pytest.fixture
def dhcp_server(db, ip_address, service_template):
    """Create a test DHCPServer."""
    from netbox_dhcp_kea_plugin.models import DHCPServer

    return DHCPServer.objects.create(
        name="TestServer",
        description="Test DHCP server",
        ip_address=ip_address,
        service_template=service_template,
        is_active=True,
    )


@pytest.fixture
def dhcp_server_factory(db, service_template):
    """Factory fixture to create multiple DHCP servers with unique IPs."""
    from ipam.models import IPAddress

    from netbox_dhcp_kea_plugin.models import DHCPServer

    counter = [0]  # Use list to allow modification in nested function

    def create_dhcp_server(
        name=None,
        ip_suffix=None,
        ha_relationship=None,
        ha_role="",
        ha_url="",
        ha_auto_failover=True,
        ha_basic_auth_user="",
        ha_basic_auth_password="",
    ):
        counter[0] += 1
        suffix = ip_suffix or counter[0]
        server_name = name or f"TestServer-{counter[0]}"

        ip = IPAddress.objects.create(
            address=f"192.168.1.{suffix}/24",
        )

        return DHCPServer.objects.create(
            name=server_name,
            description=f"Test DHCP server {counter[0]}",
            ip_address=ip,
            service_template=service_template,
            is_active=True,
            ha_relationship=ha_relationship,
            ha_role=ha_role,
            ha_url=ha_url,
            ha_auto_failover=ha_auto_failover,
            ha_basic_auth_user=ha_basic_auth_user,
            ha_basic_auth_password=ha_basic_auth_password,
        )

    return create_dhcp_server


@pytest.fixture
def prefix_factory(db):
    """Factory fixture to create multiple Prefixes with unique networks."""
    from ipam.models import Prefix

    counter = [0]

    def create_prefix(network=None):
        counter[0] += 1
        prefix_network = network or f"10.{counter[0]}.0.0/24"

        return Prefix.objects.create(
            prefix=prefix_network,
        )

    return create_prefix


@pytest.fixture
def prefix_dhcp_config_factory(db, dhcp_server_factory, prefix_factory):
    """Factory fixture to create PrefixDHCPConfig instances."""
    from netbox_dhcp_kea_plugin.models import PrefixDHCPConfig

    def create_config(server=None, prefix=None):
        if server is None:
            server = dhcp_server_factory()
        if prefix is None:
            prefix = prefix_factory()

        return PrefixDHCPConfig.objects.create(
            prefix=prefix,
            server=server,
            valid_lifetime=3600,
            max_lifetime=7200,
            routers_option_offset=1,
        )

    return create_config


@pytest.fixture
def client_class_factory(db):
    """Factory fixture to create ClientClass instances."""
    from netbox_dhcp_kea_plugin.models import ClientClass

    counter = [0]

    def create_client_class(name=None, test_expression=None):
        counter[0] += 1
        class_name = name or f"TestClass-{counter[0]}"
        expression = test_expression or f"option[60].hex == 'test{counter[0]}'"

        return ClientClass.objects.create(
            name=class_name,
            test_expression=expression,
            description=f"Test client class {counter[0]}",
            local_definitions=False,
        )

    return create_client_class
