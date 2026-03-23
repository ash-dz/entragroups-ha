"""Config flow for Entra Groups HA."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    TextSelector,
    TextSelectorConfig,
)

from .api import EntraGroupsApiClient
from .const import (
    CONF_GROUP_INPUTS,
    CONF_GROUPS,
    CONF_SCAN_INTERVAL,
    CONF_TENANT_ID,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    NAME,
)


class EntraGroupsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Entra Groups HA."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._credentials: dict[str, Any] = {}
        self._reconfigure_entry: ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return EntraGroupsOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client = self._build_client(user_input)
            try:
                await client.async_validate_credentials()
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                self._credentials = user_input
                return await self.async_step_groups()

        return self.async_show_form(
            step_id="user",
            data_schema=self._credentials_schema(user_input),
            errors=errors,
        )

    async def async_step_groups(self, user_input: dict[str, Any] | None = None):
        """Configure groups and polling interval."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client = self._build_client(self._credentials)
            try:
                groups = await client.async_resolve_groups(
                    _parse_group_inputs(user_input[CONF_GROUP_INPUTS])
                )
            except Exception:
                errors["base"] = "invalid_groups"
            else:
                return self.async_create_entry(
                    title=NAME,
                    data=self._credentials,
                    options={
                        CONF_GROUPS: [group.as_dict() for group in groups],
                        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    },
                )

        return self.async_show_form(
            step_id="groups",
            data_schema=_groups_schema(user_input),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        """Allow credentials to be reconfigured."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        self._reconfigure_entry = entry

        if user_input is not None:
            client = self._build_client(user_input)
            try:
                await client.async_validate_credentials()
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                self._credentials = user_input
                return await self.async_step_reconfigure_groups()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._credentials_schema(entry.data),
            errors=errors,
        )

    async def async_step_reconfigure_groups(
        self, user_input: dict[str, Any] | None = None
    ):
        """Update managed groups and polling during reconfigure."""
        errors: dict[str, str] = {}
        entry = self._reconfigure_entry or self._get_reconfigure_entry()

        if user_input is not None:
            client = self._build_client(self._credentials)
            try:
                groups = await client.async_resolve_groups(
                    _parse_group_inputs(user_input[CONF_GROUP_INPUTS])
                )
            except Exception:
                errors["base"] = "invalid_groups"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=self._credentials,
                    options_updates={
                        CONF_GROUPS: [group.as_dict() for group in groups],
                        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    },
                )

        return self.async_show_form(
            step_id="reconfigure_groups",
            data_schema=_groups_schema(
                {
                    CONF_GROUP_INPUTS: _stringify_groups(entry.options.get(CONF_GROUPS, [])),
                    CONF_SCAN_INTERVAL: entry.options.get(
                        CONF_SCAN_INTERVAL,
                        DEFAULT_SCAN_INTERVAL_MINUTES,
                    ),
                }
            ),
            errors=errors,
        )

    def _build_client(self, data: Mapping[str, Any]) -> EntraGroupsApiClient:
        """Build a Graph client from flow data."""
        return EntraGroupsApiClient(
            async_get_clientsession(self.hass),
            data[CONF_TENANT_ID],
            data[CONF_CLIENT_ID],
            data[CONF_CLIENT_SECRET],
        )

    def _credentials_schema(self, data: Mapping[str, Any] | None = None) -> vol.Schema:
        """Return the credentials schema."""
        data = data or {}
        return vol.Schema(
            {
                vol.Required(
                    CONF_TENANT_ID,
                    default=data.get(CONF_TENANT_ID, "organizations"),
                ): str,
                vol.Required(
                    CONF_CLIENT_ID,
                    default=data.get(CONF_CLIENT_ID, ""),
                ): str,
                vol.Required(
                    CONF_CLIENT_SECRET,
                    default=data.get(CONF_CLIENT_SECRET, ""),
                ): TextSelector(TextSelectorConfig(type="password")),
            }
        )


class EntraGroupsOptionsFlow(OptionsFlow):
    """Handle options for Entra Groups HA."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Handle the options step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            entry = self.config_entry
            client = EntraGroupsApiClient(
                async_get_clientsession(self.hass),
                entry.data[CONF_TENANT_ID],
                entry.data[CONF_CLIENT_ID],
                entry.data[CONF_CLIENT_SECRET],
            )
            try:
                groups = await client.async_resolve_groups(
                    _parse_group_inputs(user_input[CONF_GROUP_INPUTS])
                )
            except Exception:
                errors["base"] = "invalid_groups"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_GROUPS: [group.as_dict() for group in groups],
                        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    },
                )

        return self.async_show_form(
            step_id="init",
            data_schema=_groups_schema(
                {
                    CONF_GROUP_INPUTS: _stringify_groups(
                        self.config_entry.options.get(CONF_GROUPS, [])
                    ),
                    CONF_SCAN_INTERVAL: self.config_entry.options.get(
                        CONF_SCAN_INTERVAL,
                        DEFAULT_SCAN_INTERVAL_MINUTES,
                    ),
                }
            ),
            errors=errors,
        )


def _groups_schema(data: Mapping[str, Any] | None = None) -> vol.Schema:
    """Return the schema for managed group input."""
    data = data or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_GROUP_INPUTS,
                default=data.get(CONF_GROUP_INPUTS, ""),
            ): TextSelector(TextSelectorConfig()),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=int(data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES)),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=1440,
                    mode="box",
                    unit_of_measurement="minutes",
                )
            ),
        }
    )


def _parse_group_inputs(value: str) -> list[str]:
    """Parse groups entered as lines or comma-separated values."""
    items: list[str] = []
    for chunk in value.replace(",", "\n").splitlines():
        normalized = chunk.strip()
        if normalized:
            items.append(normalized)
    return items


def _stringify_groups(groups: list[dict[str, Any]]) -> str:
    """Convert stored groups into editable multiline text."""
    return ", ".join(group.get("id", "") for group in groups)
