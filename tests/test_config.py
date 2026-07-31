"""Unit tests for jcli.sdk.config.

jcli 2.0 mapping (v1 → v2):
- ``jcli.sdk.config.Config`` is unchanged and shared by v1/v2.
- The ``config`` CLI command group migrated from ``jcli/plugins/config.py``
  to ``specs/plugins/jcli_commands.py`` (init/show/list/set/add/delete/use),
  which calls the same ``Config`` class — no test changes required.
"""

import os
from pathlib import Path

import pytest
import yaml

from jcli.sdk.config import (
    DEFAULT_CONFIG_TEMPLATE,
    ENV_API_TOKEN,
    ENV_PROFILE,
    ENV_URL,
    ENV_USERNAME,
    FIELD_API_TOKEN,
    FIELD_DESCRIPTION,
    FIELD_URL,
    FIELD_USERNAME,
    Config,
    ProfileNotFoundError,
)


@pytest.fixture
def tmp_config(tmp_path: Path) -> Path:
    """Provide a temporary config file path."""
    return tmp_path / ".jcli" / "config.yaml"


@pytest.fixture
def config(tmp_config: Path) -> Config:
    """Return a Config instance using a temporary config file."""
    return Config(config_path=tmp_config)


class TestLoadAndSave:
    """Tests for config loading and saving."""

    def test_load_creates_default_config(self, config: Config, tmp_config: Path) -> None:
        """First load should create the config file with defaults."""
        assert not tmp_config.exists()
        config.load()
        assert tmp_config.exists()
        assert config._data["active_profile"] == "default"
        assert "default" in config._data["profiles"]

    def test_load_reads_existing_config(self, config: Config, tmp_config: Path) -> None:
        """Load should read existing config file."""
        tmp_config.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "active_profile": "staging",
            "profiles": {
                "staging": {
                    "url": "https://staging.jenkins.io",
                    "username": "deploy",
                    "api_token": "staging-token",
                    "description": "Staging server",
                }
            },
        }
        tmp_config.write_text(yaml.dump(data))

        config.load()
        assert config._data["active_profile"] == "staging"
        assert config._data["profiles"]["staging"]["url"] == "https://staging.jenkins.io"

    def test_save_persists_changes(self, config: Config, tmp_config: Path) -> None:
        """save() should write current data to disk."""
        config.load()
        config.add_profile("prod", "https://prod.jenkins.io", "admin", "prod-token", "Prod")

        # Re-read from disk
        with open(tmp_config, "r") as f:
            saved = yaml.safe_load(f)
        assert saved["profiles"]["prod"]["url"] == "https://prod.jenkins.io"

    def test_load_returns_self(self, config: Config) -> None:
        """load() should return self for chaining."""
        result = config.load()
        assert result is config


class TestProfileCRUD:
    """Tests for profile CRUD operations."""

    def test_add_profile(self, config: Config) -> None:
        """add_profile should create a new profile and save."""
        config.load()
        config.add_profile("staging", "https://staging.jenkins.io", "user1", "token1", "Staging")

        profiles = config.list_profiles()
        assert "staging" in profiles
        assert profiles["staging"][FIELD_URL] == "https://staging.jenkins.io"
        assert profiles["staging"][FIELD_USERNAME] == "user1"
        assert profiles["staging"][FIELD_API_TOKEN] == "token1"
        assert profiles["staging"][FIELD_DESCRIPTION] == "Staging"

    def test_add_profile_overwrites_existing(self, config: Config) -> None:
        """add_profile should overwrite an existing profile."""
        config.load()
        config.add_profile("test", "https://old.jenkins.io", "old", "old-token")
        config.add_profile("test", "https://new.jenkins.io", "new", "new-token", "Updated")

        profiles = config.list_profiles()
        assert profiles["test"][FIELD_URL] == "https://new.jenkins.io"
        assert profiles["test"][FIELD_USERNAME] == "new"

    def test_add_profile_default_description(self, config: Config) -> None:
        """add_profile should default description to empty string."""
        config.load()
        config.add_profile("minimal", "https://jenkins.io", "admin", "tok")
        profiles = config.list_profiles()
        assert profiles["minimal"][FIELD_DESCRIPTION] == ""

    def test_remove_profile(self, config: Config) -> None:
        """remove_profile should delete the profile."""
        config.load()
        config.add_profile("tmp", "https://tmp.jenkins.io", "user", "tok")
        config.remove_profile("tmp")
        assert "tmp" not in config.list_profiles()

    def test_remove_nonexistent_profile_raises(self, config: Config) -> None:
        """remove_profile should raise ProfileNotFoundError for missing profile."""
        config.load()
        with pytest.raises(ProfileNotFoundError, match="nope"):
            config.remove_profile("nope")

    def test_get_profile(self, config: Config) -> None:
        """get_profile should return the profile data."""
        config.load()
        config.add_profile("dev", "https://dev.jenkins.io", "devuser", "devtoken", "Dev server")

        profile = config.get_profile("dev")
        assert profile[FIELD_URL] == "https://dev.jenkins.io"
        assert profile[FIELD_USERNAME] == "devuser"
        assert profile[FIELD_API_TOKEN] == "devtoken"
        assert profile[FIELD_DESCRIPTION] == "Dev server"

    def test_get_nonexistent_profile_raises(self, config: Config) -> None:
        """get_profile should raise ProfileNotFoundError for missing profile."""
        config.load()
        with pytest.raises(ProfileNotFoundError, match="ghost"):
            config.get_profile("ghost")

    def test_list_profiles(self, config: Config) -> None:
        """list_profiles should return all profiles."""
        config.load()
        config.add_profile("a", "https://a.io", "u", "t")
        config.add_profile("b", "https://b.io", "u", "t")
        profiles = config.list_profiles()
        assert set(profiles.keys()) == {"default", "a", "b"}


class TestActiveProfile:
    """Tests for active profile management."""

    def test_get_active_profile_name_default(self, config: Config) -> None:
        """Default active profile should be 'default'."""
        config.load()
        assert config.get_active_profile_name() == "default"

    def test_set_active_profile(self, config: Config) -> None:
        """set_active_profile should update the active profile."""
        config.load()
        config.add_profile("staging", "https://s.io", "u", "t")
        config.set_active_profile("staging")
        assert config.get_active_profile_name() == "staging"

    def test_set_active_nonexistent_raises(self, config: Config) -> None:
        """set_active_profile should raise for missing profile."""
        config.load()
        with pytest.raises(ProfileNotFoundError):
            config.set_active_profile("nonexistent")

    def test_get_active_profile(self, config: Config) -> None:
        """get_active_profile should return the active profile data."""
        config.load()
        active = config.get_active_profile()
        assert active[FIELD_URL] == "https://jenkins.example.com"

    def test_remove_active_profile_resets_to_default(self, config: Config) -> None:
        """Removing the active profile should reset to 'default'."""
        config.load()
        config.add_profile("temp", "https://temp.io", "u", "t")
        config.set_active_profile("temp")
        config.remove_profile("temp")
        assert config.get_active_profile_name() == "default"


class TestEnvironmentOverrides:
    """Tests for environment variable overrides."""

    def test_env_url_overrides(self, config: Config, monkeypatch: pytest.MonkeyPatch) -> None:
        """JCLI_URL env var should override config url."""
        config.load()
        monkeypatch.setenv(ENV_URL, "https://env.jenkins.io")
        profile = config.get_active_profile()
        assert profile[FIELD_URL] == "https://env.jenkins.io"

    def test_env_username_overrides(self, config: Config, monkeypatch: pytest.MonkeyPatch) -> None:
        """JCLI_USERNAME env var should override config username."""
        config.load()
        monkeypatch.setenv(ENV_USERNAME, "env_user")
        profile = config.get_active_profile()
        assert profile[FIELD_USERNAME] == "env_user"

    def test_env_token_overrides(self, config: Config, monkeypatch: pytest.MonkeyPatch) -> None:
        """JCLI_API_TOKEN env var should override config api_token."""
        config.load()
        monkeypatch.setenv(ENV_API_TOKEN, "env_token_123")
        profile = config.get_active_profile()
        assert profile[FIELD_API_TOKEN] == "env_token_123"

    def test_env_profile_overrides(self, config: Config, monkeypatch: pytest.MonkeyPatch) -> None:
        """JCLI_PROFILE env var should override active profile selection."""
        config.load()
        config.add_profile("staging", "https://s.io", "u", "t")
        monkeypatch.setenv(ENV_PROFILE, "staging")
        assert config.get_active_profile_name() == "staging"
        profile = config.get_active_profile()
        assert profile[FIELD_URL] == "https://s.io"

    def test_env_nonexistent_profile_raises(
        self, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """JCLI_PROFILE pointing to missing profile should raise."""
        config.load()
        monkeypatch.setenv(ENV_PROFILE, "no_such_profile")
        with pytest.raises(ProfileNotFoundError):
            config.get_active_profile()

    def test_no_env_uses_config(self, config: Config, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without env vars, config values should be used."""
        config.load()
        monkeypatch.delenv(ENV_URL, raising=False)
        monkeypatch.delenv(ENV_USERNAME, raising=False)
        monkeypatch.delenv(ENV_API_TOKEN, raising=False)
        monkeypatch.delenv(ENV_PROFILE, raising=False)
        profile = config.get_active_profile()
        assert profile[FIELD_URL] == "https://jenkins.example.com"
        assert profile[FIELD_USERNAME] == "admin"

    def test_partial_env_overrides(self, config: Config, monkeypatch: pytest.MonkeyPatch) -> None:
        """Only set env vars should override, others use config."""
        config.load()
        monkeypatch.setenv(ENV_URL, "https://env-only.io")
        monkeypatch.delenv(ENV_USERNAME, raising=False)
        monkeypatch.delenv(ENV_API_TOKEN, raising=False)
        profile = config.get_active_profile()
        assert profile[FIELD_URL] == "https://env-only.io"
        assert profile[FIELD_USERNAME] == "admin"  # from config
        assert profile[FIELD_API_TOKEN] == "your-api-token-here"  # from config


class TestConfigPath:
    """Tests for custom config path."""

    def test_custom_config_path(self, tmp_path: Path) -> None:
        """Config should accept a custom path."""
        custom = tmp_path / "custom" / "config.yaml"
        config = Config(config_path=custom)
        config.load()
        assert custom.exists()

    def test_config_path_property(self, tmp_path: Path) -> None:
        """config_path property should return the configured path."""
        custom = tmp_path / "my.yaml"
        config = Config(config_path=custom)
        assert config.config_path == custom
