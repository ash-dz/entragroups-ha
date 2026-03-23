"""Service registration for Entra Groups HA."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_GROUP,
    ATTR_MEMBER,
    ATTR_MEMBER_TYPE,
    DOMAIN,
    SERVICE_ADD_MEMBER,
    SERVICE_REFRESH,
    SERVICE_REMOVE_MEMBER,
    MemberType,
)
from .coordinator import EntraGroupsCoordinator

ADD_REMOVE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_GROUP): cv.string,
        vol.Required(ATTR_MEMBER): cv.string,
        vol.Optional(ATTR_MEMBER_TYPE, default=MemberType.AUTO.value): vol.In(
            [member_type.value for member_type in MemberType]
        ),
    }
)

REFRESH_SCHEMA = vol.Schema({vol.Optional(ATTR_GROUP): cv.string})


@dataclass(slots=True)
class RuntimeEntryData:
    """Runtime data for a config entry."""

    coordinator: EntraGroupsCoordinator
    unsubscribe_update_listener: Callable[[], None]


@callback
def get_entry_data(entry: ConfigEntry) -> RuntimeEntryData:
    """Return runtime data for an entry."""
    return entry.runtime_data


async def async_register_services(hass: HomeAssistant) -> None:
    """Register integration services once."""
    if hass.services.has_service(DOMAIN, SERVICE_ADD_MEMBER):
        return

    async def async_handle_add_member(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        member_type = MemberType(call.data[ATTR_MEMBER_TYPE])
        try:
            await coordinator.async_add_member_to_group(
                call.data[ATTR_GROUP],
                call.data[ATTR_MEMBER],
                member_type,
            )
        except HomeAssistantError as err:
            raise ServiceValidationError(str(err)) from err

    async def async_handle_remove_member(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        member_type = MemberType(call.data[ATTR_MEMBER_TYPE])
        try:
            await coordinator.async_remove_member_from_group(
                call.data[ATTR_GROUP],
                call.data[ATTR_MEMBER],
                member_type,
            )
        except HomeAssistantError as err:
            raise ServiceValidationError(str(err)) from err

    async def async_handle_refresh(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        try:
            await coordinator.async_refresh_group(call.data.get(ATTR_GROUP))
        except HomeAssistantError as err:
            raise ServiceValidationError(str(err)) from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_MEMBER,
        async_handle_add_member,
        schema=ADD_REMOVE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_MEMBER,
        async_handle_remove_member,
        schema=ADD_REMOVE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        async_handle_refresh,
        schema=REFRESH_SCHEMA,
    )


def _get_coordinator(hass: HomeAssistant) -> EntraGroupsCoordinator:
    """Return the only configured coordinator."""
    entries = hass.data.get(DOMAIN, {})
    if not entries:
        raise ServiceValidationError("Entra Groups HA is not configured")

    runtime_data = next(iter(entries.values()))
    return runtime_data.coordinator
