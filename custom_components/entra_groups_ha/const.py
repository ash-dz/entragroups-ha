"""Constants for Entra Groups HA."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum

DOMAIN = "entra_groups_ha"
NAME = "Entra Groups HA"

CONF_GROUPS = "groups"
CONF_GROUP_INPUTS = "group_inputs"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_TENANT_ID = "tenant_id"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)
DEFAULT_SCAN_INTERVAL_MINUTES = 15

PLATFORMS = ["sensor"]

SERVICE_ADD_MEMBER = "add_member"
SERVICE_REMOVE_MEMBER = "remove_member"
SERVICE_REFRESH = "refresh"

ATTR_GROUP = "group"
ATTR_MEMBER = "member"
ATTR_MEMBER_TYPE = "member_type"


class MemberType(StrEnum):
    """Supported directory object types for member resolution."""

    AUTO = "auto"
    USER = "user"
    DEVICE = "device"
    DIRECTORY_OBJECT = "directory_object"
