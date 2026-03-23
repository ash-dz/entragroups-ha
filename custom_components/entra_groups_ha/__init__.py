"""The Entra Groups HA integration."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EntraGroupsApiClient, ManagedGroup
from .const import (
    CONF_GROUPS,
    CONF_SCAN_INTERVAL,
    CONF_TENANT_ID,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import EntraGroupsCoordinator
from .services import RuntimeEntryData, async_register_services


async def async_setup(hass: HomeAssistant, config: Mapping[str, Any]) -> bool:
    """Set up the integration."""
    await async_register_services(hass)
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Entra Groups HA from a config entry."""
    client = EntraGroupsApiClient(
        async_get_clientsession(hass),
        entry.data[CONF_TENANT_ID],
        entry.data[CONF_CLIENT_ID],
        entry.data[CONF_CLIENT_SECRET],
    )
    groups = [ManagedGroup(**group) for group in entry.options.get(CONF_GROUPS, [])]
    coordinator = EntraGroupsCoordinator(
        hass,
        client,
        groups,
        timedelta(minutes=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES)),
    )
    await coordinator.async_config_entry_first_refresh()

    unsubscribe_update_listener = entry.add_update_listener(async_reload_entry)
    runtime_data = RuntimeEntryData(
        coordinator=coordinator,
        unsubscribe_update_listener=unsubscribe_update_listener,
    )
    entry.runtime_data = runtime_data
    hass.data[DOMAIN][entry.entry_id] = runtime_data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        runtime_data: RuntimeEntryData = entry.runtime_data
        runtime_data.unsubscribe_update_listener()
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload a config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
