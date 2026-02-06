"""
Tests for Hook form validation and saving behavior.
"""

import pytest


@pytest.fixture
def hook_factory(db):
    """Factory for creating Hook instances."""
    from netbox_dhcp_kea_plugin.models import Hook

    def create_hook(**kwargs):
        defaults = {
            "name": "test-hook",
            "library_name": "libtest.so",
            "description": "Test hook",
            "is_standard": False,
            "allowed_processes": ["kea-dhcp4"],
            "parameters": None,
        }
        defaults.update(kwargs)
        return Hook.objects.create(**defaults)

    return create_hook


@pytest.fixture
def standard_hook(db):
    """Create a standard (read-only) hook."""
    from netbox_dhcp_kea_plugin.models import Hook

    return Hook.objects.create(
        name="Standard Hook",
        library_name="libdhcp_lease_cmds.so",
        description="Standard lease commands hook",
        is_standard=True,
        allowed_processes=["kea-dhcp4", "kea-dhcp6"],
        parameters=None,
    )


@pytest.fixture
def custom_hook(db):
    """Create a custom (editable) hook."""
    from netbox_dhcp_kea_plugin.models import Hook

    return Hook.objects.create(
        name="Custom Hook",
        library_name="libcustom.so",
        description="Custom hook",
        is_standard=False,
        allowed_processes=["kea-dhcp4"],
        parameters={"option": "value"},
    )


class TestHookFormCreation:
    """Tests for creating new hooks via HookForm."""

    def test_create_hook_with_valid_data(self, db):
        """Test creating a hook with valid form data."""
        from netbox_dhcp_kea_plugin.forms import HookForm

        form_data = {
            "name": "New Hook",
            "library_name": "libnew.so",
            "description": "A new hook",
            "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
            "parameters": "",
        }
        form = HookForm(data=form_data)

        assert form.is_valid(), f"Form errors: {form.errors}"
        hook = form.save()

        assert hook.name == "New Hook"
        assert hook.library_name == "libnew.so"
        assert hook.description == "A new hook"
        assert set(hook.allowed_processes) == {"kea-dhcp4", "kea-dhcp6"}
        assert hook.is_standard is False

    def test_create_hook_without_allowed_processes_fails(self, db):
        """Test that creating a hook without allowed_processes fails validation."""
        from netbox_dhcp_kea_plugin.forms import HookForm

        form_data = {
            "name": "Invalid Hook",
            "library_name": "libinvalid.so",
            "description": "Should fail",
            "allowed_processes": [],
            "parameters": "",
        }
        form = HookForm(data=form_data)

        assert not form.is_valid()
        assert "allowed_processes" in form.errors

    def test_create_hook_with_single_process(self, db):
        """Test creating a hook with a single allowed process."""
        from netbox_dhcp_kea_plugin.forms import HookForm

        form_data = {
            "name": "Single Process Hook",
            "library_name": "libsingle.so",
            "description": "Single process",
            "allowed_processes": ["kea-ctrl-agent"],
            "parameters": "",
        }
        form = HookForm(data=form_data)

        assert form.is_valid(), f"Form errors: {form.errors}"
        hook = form.save()

        assert hook.allowed_processes == ["kea-ctrl-agent"]

    def test_create_hook_with_all_processes(self, db):
        """Test creating a hook with all allowed processes."""
        from netbox_dhcp_kea_plugin.forms import HookForm

        form_data = {
            "name": "All Process Hook",
            "library_name": "liball.so",
            "description": "All processes",
            "allowed_processes": ["kea-ctrl-agent", "kea-dhcp4", "kea-dhcp6", "kea-dhcp-ddns"],
            "parameters": "",
        }
        form = HookForm(data=form_data)

        assert form.is_valid(), f"Form errors: {form.errors}"
        hook = form.save()

        assert len(hook.allowed_processes) == 4

    def test_create_hook_with_json_parameters(self, db):
        """Test creating a hook with JSON parameters."""
        from netbox_dhcp_kea_plugin.forms import HookForm

        form_data = {
            "name": "Parameterized Hook",
            "library_name": "libparams.so",
            "description": "Has parameters",
            "allowed_processes": ["kea-dhcp4"],
            "parameters": '{"max-threads": 4, "enabled": true}',
        }
        form = HookForm(data=form_data)

        assert form.is_valid(), f"Form errors: {form.errors}"
        hook = form.save()

        assert hook.parameters == {"max-threads": 4, "enabled": True}


class TestHookFormEditingCustomHook:
    """Tests for editing custom hooks via HookForm."""

    def test_edit_custom_hook_name(self, custom_hook):
        """Test editing the name of a custom hook."""
        from netbox_dhcp_kea_plugin.forms import HookForm

        form_data = {
            "name": "Updated Custom Hook",
            "library_name": custom_hook.library_name,
            "description": custom_hook.description,
            "allowed_processes": custom_hook.allowed_processes,
            "parameters": "",
        }
        form = HookForm(data=form_data, instance=custom_hook)

        assert form.is_valid(), f"Form errors: {form.errors}"
        hook = form.save()

        assert hook.name == "Updated Custom Hook"

    def test_edit_custom_hook_allowed_processes(self, custom_hook):
        """Test editing allowed_processes of a custom hook."""
        from netbox_dhcp_kea_plugin.forms import HookForm

        form_data = {
            "name": custom_hook.name,
            "library_name": custom_hook.library_name,
            "description": custom_hook.description,
            "allowed_processes": ["kea-dhcp4", "kea-dhcp6"],
            "parameters": "",
        }
        form = HookForm(data=form_data, instance=custom_hook)

        assert form.is_valid(), f"Form errors: {form.errors}"
        hook = form.save()

        assert set(hook.allowed_processes) == {"kea-dhcp4", "kea-dhcp6"}

    def test_edit_custom_hook_all_fields(self, custom_hook):
        """Test editing all fields of a custom hook."""
        from netbox_dhcp_kea_plugin.forms import HookForm

        form_data = {
            "name": "Completely Updated Hook",
            "library_name": "libupdated.so",
            "description": "Updated description",
            "allowed_processes": ["kea-dhcp6", "kea-dhcp-ddns"],
            "parameters": '{"new": "value"}',
        }
        form = HookForm(data=form_data, instance=custom_hook)

        assert form.is_valid(), f"Form errors: {form.errors}"
        hook = form.save()

        assert hook.name == "Completely Updated Hook"
        assert hook.library_name == "libupdated.so"
        assert hook.description == "Updated description"
        assert set(hook.allowed_processes) == {"kea-dhcp6", "kea-dhcp-ddns"}
        assert hook.parameters == {"new": "value"}


class TestHookFormEditingStandardHook:
    """Tests for editing standard (read-only) hooks via HookForm."""

    def test_standard_hook_preserves_name(self, standard_hook):
        """Test that editing a standard hook preserves the original name."""
        from netbox_dhcp_kea_plugin.forms import HookForm

        form_data = {
            "name": "Should Be Ignored",
            "library_name": "should_be_ignored.so",
            "description": "Should be ignored",
            "allowed_processes": ["kea-ctrl-agent"],
            "parameters": '{"new": "params"}',
        }
        form = HookForm(data=form_data, instance=standard_hook)

        assert form.is_valid(), f"Form errors: {form.errors}"
        hook = form.save()

        # Name, library_name, description, and allowed_processes should be preserved
        assert hook.name == "Standard Hook"
        assert hook.library_name == "libdhcp_lease_cmds.so"
        assert hook.description == "Standard lease commands hook"
        assert set(hook.allowed_processes) == {"kea-dhcp4", "kea-dhcp6"}
        # Only parameters should be updated
        assert hook.parameters == {"new": "params"}

    def test_standard_hook_can_update_parameters(self, standard_hook):
        """Test that parameters can be updated on a standard hook."""
        from netbox_dhcp_kea_plugin.forms import HookForm

        form_data = {
            "name": standard_hook.name,
            "library_name": standard_hook.library_name,
            "description": standard_hook.description,
            "allowed_processes": standard_hook.allowed_processes,
            "parameters": '{"option": "value"}',
        }
        form = HookForm(data=form_data, instance=standard_hook)

        assert form.is_valid(), f"Form errors: {form.errors}"
        hook = form.save()

        assert hook.parameters == {"option": "value"}

    def test_standard_hook_disabled_fields_not_submitted(self, standard_hook):
        """Test that standard hook form works when disabled fields are not submitted."""
        from netbox_dhcp_kea_plugin.forms import HookForm

        # Simulate browser behavior where disabled fields aren't submitted
        form_data = {
            # name, library_name, description, allowed_processes are NOT submitted
            "parameters": '{"updated": true}',
        }
        form = HookForm(data=form_data, instance=standard_hook)

        assert form.is_valid(), f"Form errors: {form.errors}"
        hook = form.save()

        # All preserved values should remain intact
        assert hook.name == "Standard Hook"
        assert hook.library_name == "libdhcp_lease_cmds.so"
        assert hook.description == "Standard lease commands hook"
        assert set(hook.allowed_processes) == {"kea-dhcp4", "kea-dhcp6"}
        assert hook.parameters == {"updated": True}


class TestHookFormFieldsDisabled:
    """Tests for verifying field disabled state."""

    def test_standard_hook_has_disabled_fields(self, standard_hook):
        """Test that standard hook form has certain fields disabled."""
        from netbox_dhcp_kea_plugin.forms import HookForm

        form = HookForm(instance=standard_hook)

        assert form.fields["name"].disabled is True
        assert form.fields["library_name"].disabled is True
        assert form.fields["description"].disabled is True
        assert form.fields["allowed_processes"].disabled is True

    def test_custom_hook_has_no_disabled_fields(self, custom_hook):
        """Test that custom hook form has no disabled fields."""
        from netbox_dhcp_kea_plugin.forms import HookForm

        form = HookForm(instance=custom_hook)

        assert form.fields["name"].disabled is False
        assert form.fields["library_name"].disabled is False
        assert form.fields["description"].disabled is False
        assert form.fields["allowed_processes"].disabled is False

    def test_new_hook_has_no_disabled_fields(self, db):
        """Test that new hook form has no disabled fields."""
        from netbox_dhcp_kea_plugin.forms import HookForm

        form = HookForm()

        assert form.fields["name"].disabled is False
        assert form.fields["library_name"].disabled is False
        assert form.fields["description"].disabled is False
        assert form.fields["allowed_processes"].disabled is False


class TestHookFormInitialValues:
    """Tests for verifying initial values are set correctly."""

    def test_existing_hook_has_allowed_processes_initial(self, custom_hook):
        """Test that existing hook's allowed_processes are set as initial values."""
        from netbox_dhcp_kea_plugin.forms import HookForm

        form = HookForm(instance=custom_hook)

        assert form.initial.get("allowed_processes") == custom_hook.allowed_processes

    def test_standard_hook_has_allowed_processes_initial(self, standard_hook):
        """Test that standard hook's allowed_processes are set as initial values."""
        from netbox_dhcp_kea_plugin.forms import HookForm

        form = HookForm(instance=standard_hook)

        assert set(form.initial.get("allowed_processes", [])) == {"kea-dhcp4", "kea-dhcp6"}


class TestHookFormValidation:
    """Tests for form validation."""

    def test_required_fields_for_new_hook(self, db):
        """Test that name and library_name are required for new hooks."""
        from netbox_dhcp_kea_plugin.forms import HookForm

        form_data = {
            "description": "Missing required fields",
            "allowed_processes": ["kea-dhcp4"],
            "parameters": "",
        }
        form = HookForm(data=form_data)

        assert not form.is_valid()
        assert "name" in form.errors
        assert "library_name" in form.errors

    def test_empty_form_fails_validation(self, db):
        """Test that an empty form fails validation."""
        from netbox_dhcp_kea_plugin.forms import HookForm

        form = HookForm(data={})

        assert not form.is_valid()
        # Should have errors for required fields
        assert len(form.errors) > 0

    def test_invalid_json_parameters(self, db):
        """Test that invalid JSON in parameters field fails."""
        from netbox_dhcp_kea_plugin.forms import HookForm

        form_data = {
            "name": "Invalid JSON Hook",
            "library_name": "libinvalid.so",
            "description": "Has invalid JSON",
            "allowed_processes": ["kea-dhcp4"],
            "parameters": "{not valid json}",
        }
        form = HookForm(data=form_data)

        # JSON field should validate and reject invalid JSON
        assert not form.is_valid()
        assert "parameters" in form.errors
