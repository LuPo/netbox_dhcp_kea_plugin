#!/usr/bin/env python
"""
Test script to verify ClientClass server redirect logic.

This script simulates the form cleaning process to ensure that:
1. Non-primary HA servers are redirected to primary servers
2. Redirect flags are properly set
3. Messages will be displayed correctly

Usage:
    python test_clientclass_redirect.py
"""


class MockServer:
    """Mock DHCP Server for testing."""

    def __init__(self, name, ha_relationship=None, ha_role=None):
        self.name = name
        self.ha_relationship = ha_relationship
        self.ha_role = ha_role

    def is_ha_primary(self):
        """Check if this server is primary in HA."""
        return self.ha_role == "primary"

    def __repr__(self):
        return f"<Server: {self.name} (role={self.ha_role})>"

    def __eq__(self, other):
        return self.name == other.name

    def __hash__(self):
        return hash(self.name)


class MockHARelationship:
    """Mock HA Relationship for testing."""

    def __init__(self, name, primary_server, secondary_server):
        self.name = name
        self.primary_server = primary_server
        self.secondary_server = secondary_server
        primary_server.ha_relationship = self
        secondary_server.ha_relationship = self

    def get_primary(self):
        """Get primary server."""
        return self.primary_server


def clean_servers(selected_servers):
    """
    Simulate the ClientClassForm.clean_servers() method.

    Args:
        selected_servers: List of server objects

    Returns:
        tuple: (actual_servers, redirected_servers, primary_servers, flags_set)
    """
    if not selected_servers:
        return selected_servers, [], [], False

    # Track redirects for messaging
    redirected_servers = []
    primary_servers = []

    # Replace non-primary HA servers with their primaries
    actual_servers = []
    for server in selected_servers:
        if server.ha_relationship and not server.is_ha_primary():
            # Server is in HA but not primary - redirect to primary
            primary_server = server.ha_relationship.get_primary()
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

    # Flags would be set if any redirects occurred
    flags_set = len(redirected_servers) > 0

    return actual_servers, redirected_servers, primary_servers, flags_set


def test_scenario_1():
    """Test: Selecting secondary server should redirect to primary."""
    print("\n" + "=" * 70)
    print("TEST 1: Selecting secondary server")
    print("=" * 70)

    # Setup
    ha_rel = MockHARelationship(
        "ha-pair-1",
        primary_server=MockServer("primary-dhcp", ha_role="primary"),
        secondary_server=MockServer("secondary-dhcp", ha_role="secondary"),
    )

    # User selects secondary server
    selected = [ha_rel.secondary_server]

    # Run clean_servers logic
    actual, redirected, primaries, flags = clean_servers(selected)

    # Verify
    print(f"Selected servers: {[s.name for s in selected]}")
    print(f"Actual servers:   {[s.name for s in actual]}")
    print(f"Redirected:       {redirected}")
    print(f"Primary names:    {primaries}")
    print(f"Flags set:        {flags}")

    assert len(actual) == 1, f"Expected 1 server, got {len(actual)}"
    assert actual[0].name == "primary-dhcp", f"Expected primary-dhcp, got {actual[0].name}"
    assert redirected == ["secondary-dhcp"], f"Expected redirect from secondary, got {redirected}"
    assert primaries == ["primary-dhcp"], f"Expected primary in list, got {primaries}"
    assert flags, "Flags should be set"

    print("✓ PASS: Secondary correctly redirected to primary")
    return True


def test_scenario_2():
    """Test: Selecting primary server should NOT redirect."""
    print("\n" + "=" * 70)
    print("TEST 2: Selecting primary server")
    print("=" * 70)

    # Setup
    ha_rel = MockHARelationship(
        "ha-pair-1",
        primary_server=MockServer("primary-dhcp", ha_role="primary"),
        secondary_server=MockServer("secondary-dhcp", ha_role="secondary"),
    )

    # User selects primary server
    selected = [ha_rel.primary_server]

    # Run clean_servers logic
    actual, redirected, primaries, flags = clean_servers(selected)

    # Verify
    print(f"Selected servers: {[s.name for s in selected]}")
    print(f"Actual servers:   {[s.name for s in actual]}")
    print(f"Redirected:       {redirected}")
    print(f"Primary names:    {primaries}")
    print(f"Flags set:        {flags}")

    assert len(actual) == 1, f"Expected 1 server, got {len(actual)}"
    assert actual[0].name == "primary-dhcp", f"Expected primary-dhcp, got {actual[0].name}"
    assert redirected == [], f"Expected no redirects, got {redirected}"
    assert primaries == [], f"Expected no primaries in redirect list, got {primaries}"
    assert not flags, "Flags should NOT be set"

    print("✓ PASS: Primary server used as-is, no redirect")
    return True


def test_scenario_3():
    """Test: Selecting standalone server should NOT redirect."""
    print("\n" + "=" * 70)
    print("TEST 3: Selecting standalone server (no HA)")
    print("=" * 70)

    # Setup - standalone server (no HA relationship)
    standalone = MockServer("standalone-dhcp", ha_relationship=None, ha_role=None)

    # User selects standalone server
    selected = [standalone]

    # Run clean_servers logic
    actual, redirected, primaries, flags = clean_servers(selected)

    # Verify
    print(f"Selected servers: {[s.name for s in selected]}")
    print(f"Actual servers:   {[s.name for s in actual]}")
    print(f"Redirected:       {redirected}")
    print(f"Primary names:    {primaries}")
    print(f"Flags set:        {flags}")

    assert len(actual) == 1, f"Expected 1 server, got {len(actual)}"
    assert actual[0].name == "standalone-dhcp", f"Expected standalone-dhcp, got {actual[0].name}"
    assert redirected == [], f"Expected no redirects, got {redirected}"
    assert primaries == [], f"Expected no primaries in redirect list, got {primaries}"
    assert not flags, "Flags should NOT be set"

    print("✓ PASS: Standalone server used as-is, no redirect")
    return True


def test_scenario_4():
    """Test: Selecting multiple servers with mixed types."""
    print("\n" + "=" * 70)
    print("TEST 4: Selecting multiple servers (primary, secondary, standalone)")
    print("=" * 70)

    # Setup
    ha_rel = MockHARelationship(
        "ha-pair-1",
        primary_server=MockServer("primary-dhcp", ha_role="primary"),
        secondary_server=MockServer("secondary-dhcp", ha_role="secondary"),
    )
    standalone = MockServer("standalone-dhcp", ha_relationship=None, ha_role=None)

    # User selects all three
    selected = [ha_rel.primary_server, ha_rel.secondary_server, standalone]

    # Run clean_servers logic
    actual, redirected, primaries, flags = clean_servers(selected)

    # Verify
    print(f"Selected servers: {[s.name for s in selected]}")
    print(f"Actual servers:   {[s.name for s in actual]}")
    print(f"Redirected:       {redirected}")
    print(f"Primary names:    {primaries}")
    print(f"Flags set:        {flags}")

    assert len(actual) == 2, f"Expected 2 servers (primary + standalone), got {len(actual)}"
    actual_names = [s.name for s in actual]
    assert "primary-dhcp" in actual_names, "Expected primary-dhcp in actual"
    assert "standalone-dhcp" in actual_names, "Expected standalone-dhcp in actual"
    assert "secondary-dhcp" not in actual_names, "secondary-dhcp should be redirected"
    assert redirected == ["secondary-dhcp"], f"Expected redirect from secondary, got {redirected}"
    assert primaries == ["primary-dhcp"], f"Expected primary in list, got {primaries}"
    assert flags, "Flags should be set (redirect occurred)"

    print("✓ PASS: Secondary redirected, primary and standalone kept")
    return True


def test_scenario_5():
    """Test: Selecting both primary and secondary from same HA pair."""
    print("\n" + "=" * 70)
    print("TEST 5: Selecting both primary and secondary from same HA pair")
    print("=" * 70)

    # Setup
    ha_rel = MockHARelationship(
        "ha-pair-1",
        primary_server=MockServer("primary-dhcp", ha_role="primary"),
        secondary_server=MockServer("secondary-dhcp", ha_role="secondary"),
    )

    # User selects both
    selected = [ha_rel.primary_server, ha_rel.secondary_server]

    # Run clean_servers logic
    actual, redirected, primaries, flags = clean_servers(selected)

    # Verify
    print(f"Selected servers: {[s.name for s in selected]}")
    print(f"Actual servers:   {[s.name for s in actual]}")
    print(f"Redirected:       {redirected}")
    print(f"Primary names:    {primaries}")
    print(f"Flags set:        {flags}")

    assert len(actual) == 1, f"Expected 1 server (primary only), got {len(actual)}"
    assert actual[0].name == "primary-dhcp", f"Expected primary-dhcp, got {actual[0].name}"
    assert redirected == ["secondary-dhcp"], f"Expected redirect from secondary, got {redirected}"
    assert primaries == ["primary-dhcp"], f"Expected primary in list, got {primaries}"
    assert flags, "Flags should be set"

    print("✓ PASS: Duplicate primary prevented, secondary redirected")
    return True


def test_scenario_6():
    """Test: Empty server list."""
    print("\n" + "=" * 70)
    print("TEST 6: Empty server list")
    print("=" * 70)

    # User selects nothing
    selected = []

    # Run clean_servers logic
    actual, redirected, primaries, flags = clean_servers(selected)

    # Verify
    print(f"Selected servers: {selected}")
    print(f"Actual servers:   {actual}")
    print(f"Redirected:       {redirected}")
    print(f"Primary names:    {primaries}")
    print(f"Flags set:        {flags}")

    assert actual == [], f"Expected empty list, got {actual}"
    assert redirected == [], f"Expected no redirects, got {redirected}"
    assert primaries == [], f"Expected no primaries, got {primaries}"
    assert not flags, "Flags should NOT be set"

    print("✓ PASS: Empty list handled correctly")
    return True
