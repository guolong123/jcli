"""Configuration management for jcli.

Handles loading/saving YAML config, profile CRUD, and environment variable overrides.
"""

import copy
import os
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG_DIR = Path.home() / ".jcli"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"

DEFAULT_PROFILE_NAME = "default"

# Environment variable names
ENV_URL = "JCLI_URL"
ENV_USERNAME = "JCLI_USERNAME"
ENV_API_TOKEN = "JCLI_API_TOKEN"
ENV_PROFILE = "JCLI_PROFILE"

# Profile field names
FIELD_URL = "url"
FIELD_USERNAME = "username"
FIELD_API_TOKEN = "api_token"
FIELD_DESCRIPTION = "description"

PROFILE_FIELDS = (FIELD_URL, FIELD_USERNAME, FIELD_API_TOKEN, FIELD_DESCRIPTION)

DEFAULT_CONFIG_TEMPLATE: dict[str, Any] = {
    "active_profile": DEFAULT_PROFILE_NAME,
    "profiles": {
        DEFAULT_PROFILE_NAME: {
            FIELD_URL: "https://jenkins.example.com",
            FIELD_USERNAME: "admin",
            FIELD_API_TOKEN: "your-api-token-here",
            FIELD_DESCRIPTION: "Default Jenkins instance",
        }
    },
}


class ConfigError(Exception):
    """Raised when configuration operations fail."""


class ProfileNotFoundError(ConfigError):
    """Raised when a requested profile does not exist."""


class Config:
    """Jenkins CLI configuration manager.

    Manages profiles (url, username, api_token, description) stored in YAML.
    Environment variables (JCLI_URL, JCLI_USERNAME, JCLI_API_TOKEN, JCLI_PROFILE)
    override config file values when present.
    """

    def __init__(self, config_path: str | Path | None = None) -> None:
        self._config_path = Path(config_path) if config_path else DEFAULT_CONFIG_FILE
        self._data: dict[str, Any] = {}
        self._loaded = False

    @property
    def config_path(self) -> Path:
        return self._config_path

    def load(self) -> "Config":
        """Load config from disk. Creates default config if file doesn't exist.

        Returns:
            self, for chaining.
        """
        if self._config_path.exists():
            with open(self._config_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if loaded and isinstance(loaded, dict):
                    self._data = loaded
                else:
                    self._data = copy.deepcopy(DEFAULT_CONFIG_TEMPLATE)
        else:
            self._data = copy.deepcopy(DEFAULT_CONFIG_TEMPLATE)
            self.save()

        self._loaded = True
        return self

    def save(self) -> None:
        """Persist current config to disk, creating parent dirs as needed."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as f:
            yaml.dump(self._data, f, default_flow_style=False, allow_unicode=True)

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def _get_profiles(self) -> dict[str, dict[str, str]]:
        self._ensure_loaded()
        profiles = self._data.get("profiles", {})
        if not isinstance(profiles, dict):
            return {}
        return profiles

    def _apply_env_overrides(self, profile_data: dict[str, str]) -> dict[str, str]:
        """Apply environment variable overrides to a profile's data.

        Environment variables take precedence over config file values.
        """
        result = dict(profile_data)

        env_url = os.environ.get(ENV_URL)
        if env_url:
            result[FIELD_URL] = env_url

        env_username = os.environ.get(ENV_USERNAME)
        if env_username:
            result[FIELD_USERNAME] = env_username

        env_token = os.environ.get(ENV_API_TOKEN)
        if env_token:
            result[FIELD_API_TOKEN] = env_token

        return result

    def get_active_profile_name(self) -> str:
        """Return the active profile name (env override > config file > default)."""
        self._ensure_loaded()
        env_profile = os.environ.get(ENV_PROFILE)
        if env_profile:
            return env_profile
        return self._data.get("active_profile", DEFAULT_PROFILE_NAME)

    def get_active_profile(self) -> dict[str, str]:
        """Return the active profile data with env overrides applied.

        Raises:
            ProfileNotFoundError: if the active profile doesn't exist.
        """
        name = self.get_active_profile_name()
        return self.get_profile(name)

    def list_profiles(self) -> dict[str, dict[str, str]]:
        """Return all profiles (without env overrides)."""
        return self._get_profiles()

    def get_profile(self, name: str) -> dict[str, str]:
        """Return a specific profile with env overrides applied.

        Args:
            name: Profile name.

        Returns:
            Profile data dict with keys: url, username, api_token, description.

        Raises:
            ProfileNotFoundError: if profile doesn't exist.
        """
        profiles = self._get_profiles()
        if name not in profiles:
            raise ProfileNotFoundError(f"Profile '{name}' not found")
        return self._apply_env_overrides(profiles[name])

    def add_profile(
        self,
        name: str,
        url: str,
        username: str,
        api_token: str,
        description: str = "",
    ) -> None:
        """Create or update a profile.

        Args:
            name: Profile name.
            url: Jenkins server URL.
            username: Jenkins username.
            api_token: Jenkins API token.
            description: Optional description.
        """
        self._ensure_loaded()
        profiles = self._data.setdefault("profiles", {})
        profiles[name] = {
            FIELD_URL: url,
            FIELD_USERNAME: username,
            FIELD_API_TOKEN: api_token,
            FIELD_DESCRIPTION: description,
        }
        self.save()

    def remove_profile(self, name: str) -> None:
        """Remove a profile.

        Args:
            name: Profile name to remove.

        Raises:
            ProfileNotFoundError: if profile doesn't exist.
        """
        self._ensure_loaded()
        profiles = self._data.get("profiles", {})
        if name not in profiles:
            raise ProfileNotFoundError(f"Profile '{name}' not found")
        del profiles[name]
        # If we removed the active profile, reset to default
        if self._data.get("active_profile") == name:
            self._data["active_profile"] = DEFAULT_PROFILE_NAME
        self.save()

    def set_active_profile(self, name: str) -> None:
        """Set the active profile.

        Args:
            name: Profile name to activate.

        Raises:
            ProfileNotFoundError: if profile doesn't exist.
        """
        self._ensure_loaded()
        profiles = self._data.get("profiles", {})
        if name not in profiles:
            raise ProfileNotFoundError(f"Profile '{name}' not found")
        self._data["active_profile"] = name
        self.save()
