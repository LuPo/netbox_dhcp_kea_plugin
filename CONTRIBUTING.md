# Contributing

Contributions are welcome, and they are greatly appreciated! Every little bit
helps, and credit will always be given.

We love your input! We want to make contributing to this project as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features
- Becoming a maintainer

## General Tips for Working on GitHub

* Register for a free [GitHub account](https://github.com/signup) if you haven't already.
* You can use [GitHub Markdown](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax) for formatting text and adding images.
* To help mitigate notification spam, please avoid "bumping" issues with no activity. (To vote an issue up or down, use a :thumbsup: or :thumbsdown: reaction.)
* Please avoid pinging members with `@` unless they've previously expressed interest or involvement with that particular issue.
* Familiarize yourself with [this list of discussion anti-patterns](https://github.com/bradfitz/issue-tracker-behaviors) and make every effort to avoid them.

## Types of Contributions

### Report Bugs

Report bugs at https://github.com/LuPo/netbox_dhcp_kea_plugin/issues.

If you are reporting a bug, please include:

* Your operating system name and version.
* Any details about your local setup that might be helpful in troubleshooting.
* Detailed steps to reproduce the bug.

### Fix Bugs

Look through the GitHub issues for bugs. Anything tagged with "bug" and "help
wanted" is open to whoever wants to implement it.

### Implement Features

Look through the GitHub issues for features. Anything tagged with "enhancement"
and "help wanted" is open to whoever wants to implement it.

### Write Documentation

NetBox DHCP-KEA Plugin could always use more documentation, whether as part of the
official NetBox DHCP-KEA Plugin docs, in docstrings, or even on the web in blog posts,
articles, and such.

### Submit Feedback

The best way to send feedback is to file an issue at https://github.com/LuPo/netbox_dhcp_kea_plugin/issues.

If you are proposing a feature:

* Explain in detail how it would work.
* Keep the scope as narrow as possible, to make it easier to implement.
* Remember that this is a volunteer-driven project, and that contributions
  are welcome :)

## Get Started!

Ready to contribute? Here's how to set up `netbox-dhcp-kea-plugin` for local development.

1. Fork the `netbox_dhcp_kea_plugin` repo on GitHub, and clone your fork:

    ```
    $ git clone git@github.com:your_name_here/netbox_dhcp_kea_plugin.git
    ```

2. Set up a NetBox development environment, as described in [Setting up a Development Environment](https://docs.netbox.dev/en/stable/development/getting-started/). The tests need NetBox's source tree and its requirements, plus PostgreSQL and Redis.

3. Activate NetBox's virtual environment, and install the plugin in editable mode with its test and docs extras (see [Plugins Development](https://docs.netbox.dev/en/stable/plugins/development/)):

    ```
    $ source ~/.venv/netbox/bin/activate
    $ pip install -e ".[test,docs]"
    ```

4. Install the netbox-plugin-dns release that matches your NetBox version, from the compatibility table in the README. The plugin cannot load without it:

    ```
    $ pip install "netbox-plugin-dns~=1.7.0"
    ```

5. Create a branch for local development:

    ```
    $ git checkout -b name-of-your-bugfix-or-feature
    ```

6. Commit your changes, push your branch to GitHub, and open a pull request through the GitHub website.

## Running the tests

The tests import NetBox from `NETBOX_PATH`, the `netbox/` directory of your NetBox checkout:

```
$ export NETBOX_PATH=~/netbox/netbox
$ make test                          # whole suite, reusing the test database
$ make test T=tests/test_models.py   # one file, or a node id
$ make test K=test_pool STOP=1       # pytest -k, stop at the first failure
```

`make test` runs under the `configuration.py` of your NetBox checkout, so every plugin enabled there takes part. `make test-ci` runs the suite the way CI does: under `tests/netbox_configuration.py`, with only netbox-plugin-dns and this plugin enabled, in a database of its own (`test_netbox_ci`). It reads the connection from `NETBOX_DB_USER`, `NETBOX_DB_PASSWORD`, `NETBOX_DB_HOST`, `NETBOX_DB_PORT`, `NETBOX_REDIS_HOST`, `NETBOX_REDIS_PORT` and `NETBOX_REDIS_PASSWORD`, which default to user and password `netbox` on `localhost` with no Redis password:

```
$ export NETBOX_REDIS_PASSWORD=...
$ make test-ci
```

`make help` lists every target and variable.

## Building the docs

The documentation site is built with [Zensical](https://zensical.org) from `docs/` and `zensical.toml`:

```
$ make docs          # live preview at http://localhost:8000
$ make docs-check    # strict build that fails on broken links, as CI does
```

## Pull Request Guidelines

Before you submit a pull request, check that it meets these guidelines:

1. The pull request should include tests.
2. If the pull request adds functionality, the docs should be updated, and the change described under `Unreleased` in `CHANGELOG.md`.
3. The pull request should work on every NetBox version in the README's compatibility table, with Python 3.12 or later. The [tests workflow](https://github.com/LuPo/netbox_dhcp_kea_plugin/actions/workflows/tests.yaml) runs the suite against each of them; make sure it passes.

## Deploying

A reminder for the maintainers on how to release:

1. Set the new version in `pyproject.toml` and `netbox_dhcp_kea_plugin/__init__.py`, and run `make lock`.
2. Rename the `Unreleased` heading in `CHANGELOG.md` to the version and date.
3. Commit, push `main`, and wait for the tests workflow to pass.
4. Tag that commit with the bare version, and push the tag:

    ```
    $ git tag 0.10.4
    $ git push origin 0.10.4
    ```

    The publish workflow runs the tests again, builds the package and uploads it to PyPI. It refuses a tag that does not match the package version.
