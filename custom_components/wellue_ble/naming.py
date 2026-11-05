"""Turn the name a device advertises into friendly names for Home Assistant.

These are small helper functions shared by the config flow (which names the
config entry) and, later, the entities (which name the device in Home
Assistant's device registry).
"""

from .const import MODEL_NAME_BY_ADVERTISED_NAME_PREFIX


def model_name_from_advertised_name(advertised_name: str) -> str | None:
    """Return the model name for an advertised name, or None if unrecognized.

    Example: "O2M 2693" -> "Checkme O2 Max".
    """
    for name_prefix, model_name in MODEL_NAME_BY_ADVERTISED_NAME_PREFIX.items():
        if advertised_name.startswith(name_prefix):
            return model_name
    return None


def friendly_device_name(advertised_name: str) -> str:
    """Return a friendly device name, or the advertised name if unrecognized.

    Examples:
        "O2M 2693"     -> "Checkme O2 Max 2693"
        "Band-WU 1234" -> "Checkme O2 Ultra 1234"
        "Something 12" -> "Something 12"  (unknown model: left unchanged)
    """
    for name_prefix, model_name in MODEL_NAME_BY_ADVERTISED_NAME_PREFIX.items():
        if advertised_name.startswith(name_prefix):
            # Whatever follows the prefix is the serial number suffix, e.g.
            # " 2693". strip() removes the space in front of it.
            serial_number_suffix = advertised_name.removeprefix(name_prefix).strip()
            if serial_number_suffix:
                return f"{model_name} {serial_number_suffix}"
            return model_name
    return advertised_name


def is_supported_advertised_name(advertised_name: str) -> bool:
    """Return True if the advertised name belongs to a model we recognize."""
    return model_name_from_advertised_name(advertised_name) is not None
