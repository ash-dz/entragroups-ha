"""Entity helpers for Entra Groups HA."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EntraGroupsCoordinator


class EntraGroupsCoordinatorEntity(CoordinatorEntity[EntraGroupsCoordinator]):
    """Base entity for Entra Groups HA."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return shared service device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, "service")},
            name="Entra Groups HA",
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Microsoft Entra ID",
            model="Graph group manager",
        )
