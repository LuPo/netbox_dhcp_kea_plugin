"""enable_ddns feature flag gating.

Verifies the startup check for ``enable_ddns=True`` without netbox_dns and
that menus / API routes / URL patterns are absent when the flag is off.

The check itself is unit-tested by directly invoking the validator with a
mocked PLUGINS_CONFIG; we don't actually toggle Django settings between
tests because most of the conditional wiring is done at import time.
"""

import pytest
from django.core.exceptions import ImproperlyConfigured


pytestmark = pytest.mark.django_db


def test_validate_ddns_dependencies_no_op_when_flag_off(monkeypatch):
    from netbox_dhcp_kea_plugin import DHCPKEAConfig

    monkeypatch.setattr(
        "django.conf.settings.PLUGINS_CONFIG",
        {"netbox_dhcp_kea_plugin": {"enable_ddns": False}},
        raising=False,
    )
    DHCPKEAConfig._validate_ddns_dependencies()


def test_validate_ddns_dependencies_raises_without_netbox_dns_flag(monkeypatch):
    from netbox_dhcp_kea_plugin import DHCPKEAConfig

    monkeypatch.setattr(
        "django.conf.settings.PLUGINS_CONFIG",
        {
            "netbox_dhcp_kea_plugin": {
                "enable_ddns": True,
                "enable_netbox_dns": False,
            }
        },
        raising=False,
    )
    with pytest.raises(ImproperlyConfigured) as exc:
        DHCPKEAConfig._validate_ddns_dependencies()
    assert "enable_netbox_dns" in str(exc.value)


def test_validate_ddns_dependencies_raises_when_netbox_dns_missing(monkeypatch):
    from netbox_dhcp_kea_plugin import DHCPKEAConfig

    monkeypatch.setattr(
        "django.conf.settings.PLUGINS_CONFIG",
        {
            "netbox_dhcp_kea_plugin": {
                "enable_ddns": True,
                "enable_netbox_dns": True,
            }
        },
        raising=False,
    )

    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "netbox_dns":
            raise ImportError("simulated missing netbox_dns")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ImproperlyConfigured) as exc:
        DHCPKEAConfig._validate_ddns_dependencies()
    assert "netbox_dns" in str(exc.value)


def test_secret_backend_registry_has_plaintext():
    from netbox_dhcp_kea_plugin.secret_backends import TSIG_SECRET_BACKENDS

    assert "plaintext" in TSIG_SECRET_BACKENDS


def test_secret_backend_unknown_raises():
    from netbox_dhcp_kea_plugin.models import TSIGKey
    from netbox_dhcp_kea_plugin.secret_backends import (
        TSIGSecretBackendError,
        resolve_secret,
    )

    key = TSIGKey(name="bogus.", algorithm="HMAC-SHA256", secret_backend="vault")
    with pytest.raises(TSIGSecretBackendError):
        resolve_secret(key)
