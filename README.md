# NetBox DHCP-KEA Plugin

!!! warning "This project was developed using AI-assisted coding tools. It is undergoing review for accuracy, stability, security, and performance. If you encounter any problems, please feel free to open an issue or contribute a pull request!"

A NetBox plugin that models the **entire ISC Kea DHCP configuration surface** — DHCP servers, HA relationships, subnets, pools, client classes, option definitions and data, hooks, control sockets, Stork agents, and (optionally) the Kea 3.0+ Dynamic DNS subsystem (D2 daemons, TSIG keys, DDNS domains and policies) — and renders it as a complete Kea JSON configuration available through the REST API.

NetBox becomes the source of truth for *what Kea should be*; deploying the rendered config to the actual servers is left to your own IaC / CaC tooling (Ansible, GitLab CI, AWX, etc.).

- Free software: GPL-3.0-only
- Documentation: <https://lupo.github.io/netbox_dhcp_kea_plugin/>

## Compatibility

| NetBox Version | Plugin Version |
|----------------|----------------|
| 4.5            | 0.8.x          |

## Quick install

```bash
pip install git+https://github.com/LuPo/netbox_dhcp_kea_plugin
```

Add `netbox_dhcp_kea_plugin` to `PLUGINS` in your NetBox configuration, run `python manage.py migrate`, and restart NetBox.

Full installation, configuration, feature reference, usage walkthroughs, and design guides live in the documentation site linked above.

## Contributing

Contributions are welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Credits

This package was created with [Cookiecutter](https://github.com/audreyr/cookiecutter) and the [`netbox-community/cookiecutter-netbox-plugin`](https://github.com/netbox-community/cookiecutter-netbox-plugin) project template.

Based on the NetBox plugin tutorial:

- [Demo repository](https://github.com/netbox-community/netbox-plugin-demo)
- [Tutorial](https://github.com/netbox-community/netbox-plugin-tutorial)

## License

GPL-3.0-only
