# Entra Groups HA

Entra Groups HA is a Home Assistant custom integration for monitoring and managing selected Microsoft Entra ID group memberships.

It supports:

- Adding the integration from the Home Assistant UI
- Managing multiple Entra groups from one config entry
- Polling group members on a schedule (default: 15 minutes)
- Exposing one sensor per managed group
- Adding and removing members through Home Assistant services
- Forcing an immediate refresh outside the normal polling cycle

## HACS

This repository is structured so it can be added to HACS as a custom integration repository.

HACS update detection is expected to use GitHub releases. The integration version is declared in [manifest.json](custom_components/entra_groups_ha/manifest.json), and releases should use matching version tags such as `v0.1.1`.

## Installation

### HACS

1. In HACS, add this repository as a custom repository of type `Integration`.
2. Install `Entra Groups HA`.
3. Restart Home Assistant.
4. Go to `Settings -> Devices & services -> Add integration`.
5. Search for `Entra Groups HA`.

### Manual

1. Copy `custom_components/entra_groups_ha` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration from `Settings -> Devices & services`.

## Microsoft Entra App Permissions

Create an Entra application registration with application permissions for Microsoft Graph. At minimum, this integration is intended to work with:

- `Group.Read.All`
- `GroupMember.ReadWrite.All`
- `User.Read.All`
- `Device.Read.All`

Grant admin consent after assigning the permissions.

## Configuration

The initial setup flow asks for:

- Tenant ID or tenant name
- Application (client) ID
- Client secret
- One or more group identifiers, entered as comma-separated IDs or exact display names
- Sync interval in minutes

After setup, use the integration options to update the managed group list or polling interval.

## Sensors

Each managed group creates a sensor:

- State: current member count
- Attributes:
  - `group_id`
  - `group_name`
  - `last_sync`
  - `members`

The `members` attribute contains a list of resolved member records including IDs, display names, object types, and user principal names where available.

## Services

### `entra_groups_ha.add_member`

Add a member to a managed group.

Fields:

- `group`: managed group ID or managed group display name
- `member`: object ID, user principal name, email address, or exact device display name
- `member_type`: optional `auto`, `user`, `device`, or `directory_object`

### `entra_groups_ha.remove_member`

Remove a member from a managed group.

Fields:

- `group`: managed group ID or managed group display name
- `member`: object ID, user principal name, email address, or exact device display name
- `member_type`: optional `auto`, `user`, `device`, or `directory_object`

### `entra_groups_ha.refresh`

Force an immediate refresh of all configured groups.

Optional fields:

- `group`: refresh only a single managed group by ID or display name

## Notes

- Group display name lookups use exact matching. Group IDs are more reliable.
- User resolution prefers exact UPN or mail matches.
- Device resolution uses exact display name or device ID matches.
- Nested group expansion is not performed; the sensor reflects direct group members returned by Microsoft Graph.

## Releasing

1. Update the version in `custom_components/entra_groups_ha/manifest.json`.
2. Commit and push the change.
3. Create and push a matching tag such as `v0.1.1`.
4. GitHub Actions will publish a GitHub release automatically.

Using tagged GitHub releases allows HACS to detect and offer updates cleanly.
