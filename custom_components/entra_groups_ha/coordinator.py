"""Coordinator for Entra Groups HA."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EntraGroupsApiClient, ManagedGroup, MemberRecord
from .const import DEFAULT_SCAN_INTERVAL, MemberType

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class GroupSnapshot:
    """Current state for a managed group."""

    group: ManagedGroup
    members: list[MemberRecord]
    last_sync: datetime

    def as_attributes(self) -> dict[str, Any]:
        """Return group snapshot attributes."""
        return {
            "group_id": self.group.id,
            "group_name": self.group.display_name,
            "last_sync": self.last_sync.isoformat(),
            "members": [member.as_dict() for member in self.members],
        }


class EntraGroupsCoordinator(DataUpdateCoordinator[dict[str, GroupSnapshot]]):
    """Fetch and cache managed group memberships."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: EntraGroupsApiClient,
        groups: list[ManagedGroup],
        scan_interval: timedelta = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.managed_groups = groups
        super().__init__(
            hass,
            logger=_LOGGER,
            name="Entra Groups HA",
            update_interval=scan_interval,
        )

    async def _async_update_data(self) -> dict[str, GroupSnapshot]:
        """Fetch all configured group memberships."""
        try:
            results = await asyncio.gather(
                *(self._async_fetch_group_snapshot(group) for group in self.managed_groups)
            )
        except ConfigEntryAuthFailed:
            raise
        except HomeAssistantError as err:
            raise UpdateFailed(str(err)) from err

        return {snapshot.group.id: snapshot for snapshot in results}

    async def _async_fetch_group_snapshot(self, group: ManagedGroup) -> GroupSnapshot:
        """Fetch one group snapshot."""
        members = await self.client.async_get_group_members(group.id)
        return GroupSnapshot(
            group=group,
            members=members,
            last_sync=datetime.now(tz=UTC),
        )

    async def async_add_member_to_group(
        self,
        group_identifier: str,
        member_identifier: str,
        member_type: MemberType,
    ) -> MemberRecord:
        """Add a member to a configured group and refresh data."""
        group = self.get_managed_group(group_identifier)
        member = await self.client.async_resolve_member(member_identifier, member_type)
        await self.client.async_add_member(group.id, member.id)
        await self.async_request_refresh()
        return member

    async def async_remove_member_from_group(
        self,
        group_identifier: str,
        member_identifier: str,
        member_type: MemberType,
    ) -> MemberRecord:
        """Remove a member from a configured group and refresh data."""
        group = self.get_managed_group(group_identifier)
        member = await self.client.async_resolve_member(member_identifier, member_type)
        await self.client.async_remove_member(group.id, member.id)
        await self.async_request_refresh()
        return member

    async def async_refresh_group(self, group_identifier: str | None = None) -> None:
        """Refresh all groups or validate one requested group."""
        if group_identifier is not None:
            self.get_managed_group(group_identifier)
        await self.async_request_refresh()

    def get_managed_group(self, identifier: str) -> ManagedGroup:
        """Resolve a configured group by ID or name."""
        identifier = identifier.strip().casefold()
        for group in self.managed_groups:
            if group.id.casefold() == identifier or group.display_name.casefold() == identifier:
                return group
        raise HomeAssistantError(
            "Group is not managed by this integration; add it in the options flow first"
        )
