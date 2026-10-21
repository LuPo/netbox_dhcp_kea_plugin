"""NetBox configuration for running this plugin's test suite.

Select it with ``NETBOX_CONFIGURATION=tests.netbox_configuration`` (and this
repository on ``PYTHONPATH``). The suite then runs against settings kept here
rather than whatever a developer's own ``configuration.py`` contains — plugins,
feature flags and site-specific values in that file otherwise leak into the
tests and make the result depend on the machine running them.

Connection details come from the environment. The defaults match the service
containers in ``.github/workflows/tests.yaml``.
"""

import os


def _env(name, default):
    return os.environ.get(name, default)


ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _env("NETBOX_DB_NAME", "netbox"),
        "USER": _env("NETBOX_DB_USER", "netbox"),
        "PASSWORD": _env("NETBOX_DB_PASSWORD", "netbox"),
        "HOST": _env("NETBOX_DB_HOST", "localhost"),
        "PORT": _env("NETBOX_DB_PORT", ""),
        "CONN_MAX_AGE": 300,
    }
}


def _redis(database):
    return {
        "HOST": _env("NETBOX_REDIS_HOST", "localhost"),
        "PORT": int(_env("NETBOX_REDIS_PORT", "6379")),
        "USERNAME": "",
        "PASSWORD": _env("NETBOX_REDIS_PASSWORD", ""),
        "DATABASE": database,
        "SSL": False,
    }


REDIS = {
    "tasks": _redis(0),
    "caching": _redis(1),
}

# Test-only; NetBox requires at least 50 characters.
SECRET_KEY = "test-only-secret-key-not-used-anywhere-real-0123456789abcdef"

# Only what the suite imports: netbox_dns backs the DNS integration and DDNS.
PLUGINS = [
    "netbox_dns",
    "netbox_dhcp_kea_plugin",
]

# Both default to off. The DDNS and DNS-record tests exercise them, so the
# suite runs with them on; tests that need them off say so with monkeypatch.
PLUGINS_CONFIG = {
    "netbox_dhcp_kea_plugin": {
        "enable_netbox_dns": True,
        "enable_ddns": True,
    },
}
