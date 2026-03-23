"""Sensor platform for Entra Groups HA."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EntraGroupsCoordinator, GroupSnapshot
from .entity import EntraGroupsCoordinatorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Entra group sensors."""
    del hass
    coordinator: EntraGroupsCoordinator = entry.runtime_data.coordinator
    async_add_entities(
        EntraGroupSensor(coordinator, group.id) for group in coordinator.managed_groups
    )


class EntraGroupSensor(EntraGroupsCoordinatorEntity, SensorEntity):
    """Sensor representing a managed Entra group."""

    _attr_icon = "mdi:account-group"

    def __init__(self, coordinator: EntraGroupsCoordinator, group_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._group_id = group_id
        group = coordinator.get_managed_group(group_id)
        self._attr_unique_id = f"{DOMAIN}_{group.id}"
        self._attr_name = f"{group.display_name} members"
        self._attr_native_unit_of_measurement = "members"

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return super().available and bool(self.coordinator.data) and self._group_id in self.coordinator.data

    @property
    def native_value(self) -> int | None:
        """Return the current member count."""
        snapshot = self._snapshot
        return len(snapshot.members) if snapshot is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        """Return snapshot attributes."""
        snapshot = self._snapshot
        return snapshot.as_attributes() if snapshot is not None else None

    @property
    def _snapshot(self) -> GroupSnapshot | None:
        """Return the latest group snapshot."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._group_id)
