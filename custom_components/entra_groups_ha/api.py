"""Microsoft Graph client for Entra Groups HA."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
import logging
import re
from typing import Any
from urllib.parse import urlencode

from aiohttp import ClientError, ClientSession
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError

from .const import MemberType

_LOGGER = logging.getLogger(__name__)

GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
TOKEN_SCOPE = "https://graph.microsoft.com/.default"
UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB]"
    r"[0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)


@dataclass(slots=True)
class ManagedGroup:
    """Configured managed group."""

    id: str
    display_name: str
    description: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe mapping."""
        return asdict(self)


@dataclass(slots=True)
class MemberRecord:
    """Resolved group member."""

    id: str
    display_name: str
    object_type: str
    user_principal_name: str | None = None
    mail: str | None = None
    device_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe mapping."""
        return asdict(self)


class EntraGroupsApiClient:
    """Small Microsoft Graph client for Entra group management."""

    def __init__(
        self,
        session: ClientSession,
        tenant_id: str,
        client_id: str,
        client_secret: str,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._tenant_id = tenant_id.strip() or "organizations"
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token: str | None = None
        self._token_expires_at = datetime.now(tz=UTC)

    async def async_validate_credentials(self) -> None:
        """Validate credentials and Graph access."""
        await self._async_request("GET", f"{GRAPH_ROOT}/groups?$top=1&$select=id")

    async def async_resolve_groups(self, group_inputs: list[str]) -> list[ManagedGroup]:
        """Resolve a list of group IDs or exact display names."""
        groups: list[ManagedGroup] = []
        seen_ids: set[str] = set()

        for value in group_inputs:
            group = await self.async_resolve_group(value)
            if group.id in seen_ids:
                continue
            seen_ids.add(group.id)
            groups.append(group)

        if not groups:
            raise HomeAssistantError("No groups were resolved")

        return groups

    async def async_resolve_group(self, identifier: str) -> ManagedGroup:
        """Resolve a group ID or exact display name."""
        identifier = identifier.strip()
        if not identifier:
            raise HomeAssistantError("Group identifier cannot be empty")

        if UUID_PATTERN.match(identifier):
            payload = await self._async_request(
                "GET",
                f"{GRAPH_ROOT}/groups/{identifier}?$select=id,displayName,description",
            )
            return ManagedGroup(
                id=payload["id"],
                display_name=payload.get("displayName") or payload["id"],
                description=payload.get("description"),
            )

        escaped = identifier.replace("'", "''")
        params = urlencode(
            {
                "$filter": f"displayName eq '{escaped}'",
                "$select": "id,displayName,description",
            }
        )
        payload = await self._async_request("GET", f"{GRAPH_ROOT}/groups?{params}")
        values = payload.get("value", [])
        if not values:
            raise HomeAssistantError(f"Group '{identifier}' was not found")
        if len(values) > 1:
            raise HomeAssistantError(
                f"Group name '{identifier}' matched multiple groups; use the group ID"
            )

        result = values[0]
        return ManagedGroup(
            id=result["id"],
            display_name=result.get("displayName") or result["id"],
            description=result.get("description"),
        )

    async def async_get_group_members(self, group_id: str) -> list[MemberRecord]:
        """Return the direct members of a group."""
        url = (
            f"{GRAPH_ROOT}/groups/{group_id}/members"
            "?$select=id,displayName,userPrincipalName,mail,deviceId"
        )
        members: list[MemberRecord] = []

        while url:
            payload = await self._async_request("GET", url)
            for item in payload.get("value", []):
                odata_type = item.get("@odata.type", "")
                members.append(
                    MemberRecord(
                        id=item["id"],
                        display_name=item.get("displayName") or item["id"],
                        object_type=odata_type.removeprefix("#microsoft.graph.") or "unknown",
                        user_principal_name=item.get("userPrincipalName"),
                        mail=item.get("mail"),
                        device_id=item.get("deviceId"),
                    )
                )
            url = payload.get("@odata.nextLink")

        members.sort(key=lambda member: (member.display_name.lower(), member.id))
        return members

    async def async_add_member(self, group_id: str, member_id: str) -> None:
        """Add a member to a group."""
        await self._async_request(
            "POST",
            f"{GRAPH_ROOT}/groups/{group_id}/members/$ref",
            json_data={"@odata.id": f"{GRAPH_ROOT}/directoryObjects/{member_id}"},
            expect_json=False,
        )

    async def async_remove_member(self, group_id: str, member_id: str) -> None:
        """Remove a member from a group."""
        await self._async_request(
            "DELETE",
            f"{GRAPH_ROOT}/groups/{group_id}/members/{member_id}/$ref",
            expect_json=False,
        )

    async def async_resolve_member(
        self,
        identifier: str,
        member_type: MemberType = MemberType.AUTO,
    ) -> MemberRecord:
        """Resolve a user, device, or raw directory object ID."""
        identifier = identifier.strip()
        if not identifier:
            raise HomeAssistantError("Member identifier cannot be empty")

        if member_type in (MemberType.DIRECTORY_OBJECT, MemberType.AUTO) and UUID_PATTERN.match(
            identifier
        ):
            return MemberRecord(
                id=identifier,
                display_name=identifier,
                object_type="directoryObject",
            )

        if member_type in (MemberType.AUTO, MemberType.USER):
            user = await self._async_find_user(identifier)
            if user is not None:
                return user
            if member_type == MemberType.USER:
                raise HomeAssistantError(f"User '{identifier}' was not found")

        if member_type in (MemberType.AUTO, MemberType.DEVICE):
            device = await self._async_find_device(identifier)
            if device is not None:
                return device
            if member_type == MemberType.DEVICE:
                raise HomeAssistantError(f"Device '{identifier}' was not found")

        raise HomeAssistantError(
            f"Member '{identifier}' could not be resolved; use an object ID if needed"
        )

    async def _async_find_user(self, identifier: str) -> MemberRecord | None:
        """Resolve a user by UPN or mail."""
        escaped = identifier.replace("'", "''")
        params = urlencode(
            {
                "$filter": f"userPrincipalName eq '{escaped}' or mail eq '{escaped}'",
                "$select": "id,displayName,userPrincipalName,mail",
            }
        )
        payload = await self._async_request("GET", f"{GRAPH_ROOT}/users?{params}")
        values = payload.get("value", [])
        if not values:
            return None
        if len(values) > 1:
            raise HomeAssistantError(
                f"User identifier '{identifier}' matched multiple users; use the object ID"
            )

        result = values[0]
        return MemberRecord(
            id=result["id"],
            display_name=result.get("displayName") or result["id"],
            object_type="user",
            user_principal_name=result.get("userPrincipalName"),
            mail=result.get("mail"),
        )

    async def _async_find_device(self, identifier: str) -> MemberRecord | None:
        """Resolve a device by display name or device ID."""
        escaped = identifier.replace("'", "''")
        params = urlencode(
            {
                "$filter": f"displayName eq '{escaped}' or deviceId eq '{escaped}'",
                "$select": "id,displayName,deviceId",
            }
        )
        payload = await self._async_request("GET", f"{GRAPH_ROOT}/devices?{params}")
        values = payload.get("value", [])
        if not values:
            return None
        if len(values) > 1:
            raise HomeAssistantError(
                f"Device identifier '{identifier}' matched multiple devices; use the object ID"
            )

        result = values[0]
        return MemberRecord(
            id=result["id"],
            display_name=result.get("displayName") or result["id"],
            object_type="device",
            device_id=result.get("deviceId"),
        )

    async def _async_request(
        self,
        method: str,
        url: str,
        *,
        json_data: dict[str, Any] | None = None,
        expect_json: bool = True,
    ) -> Any:
        """Send an authenticated request to Microsoft Graph."""
        headers = {"Authorization": f"Bearer {await self._async_get_access_token()}"}
        if json_data is not None:
            headers["Content-Type"] = "application/json"

        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                json=json_data,
            ) as response:
                if response.status == 401:
                    raise ConfigEntryAuthFailed("Authentication with Microsoft Graph failed")

                if response.status >= 400:
                    text = await response.text()
                    _LOGGER.debug(
                        "Graph error %s for %s %s: %s",
                        response.status,
                        method,
                        url,
                        text,
                    )
                    raise self._map_error(response.status, text)

                if not expect_json or response.status == 204:
                    return None

                return await response.json()
        except ClientError as err:
            raise HomeAssistantError("Unable to reach Microsoft Graph") from err

    async def _async_get_access_token(self) -> str:
        """Return a cached app-only token."""
        now = datetime.now(tz=UTC)
        if self._access_token is not None and now < self._token_expires_at:
            return self._access_token

        token_url = f"https://login.microsoftonline.com/{self._tenant_id}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "scope": TOKEN_SCOPE,
        }
        try:
            async with self._session.post(token_url, data=data) as response:
                if response.status >= 400:
                    text = await response.text()
                    _LOGGER.debug("Token request failed: %s", text)
                    raise ConfigEntryAuthFailed("Unable to obtain a Microsoft Graph token")
                payload = await response.json()
        except ClientError as err:
            raise HomeAssistantError("Unable to reach Microsoft Graph") from err

        expires_in = int(payload.get("expires_in", 3600))
        self._access_token = payload["access_token"]
        self._token_expires_at = now + timedelta(seconds=max(expires_in - 120, 60))
        return self._access_token

    def _map_error(self, status: int, text: str) -> HomeAssistantError:
        """Map Graph HTTP errors to HA exceptions."""
        lowered = text.lower()
        if status in (401, 403):
            return ConfigEntryAuthFailed("Microsoft Graph rejected the configured credentials")
        if status == 404:
            return HomeAssistantError("The requested Entra object was not found")
        if status == 400 and "already exist" in lowered:
            return HomeAssistantError("The member is already in the group")
        if status == 400 and "unsupported reference target" in lowered:
            return HomeAssistantError("This object type cannot be added to the group")
        if status == 400 and "resource" in lowered and "does not exist" in lowered:
            return HomeAssistantError("The supplied object ID does not exist")
        return HomeAssistantError(
            f"Microsoft Graph request failed with HTTP {status}: {text[:200]}"
        )
