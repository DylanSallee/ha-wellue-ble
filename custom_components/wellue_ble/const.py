"""Constants for the Wellue integration.

A "constant" is a value that never changes while Home Assistant runs. Keeping
them all in this one file means every other file imports the same value, so
something like the integration's domain is only ever typed out in one place.
"""

from datetime import timedelta
from typing import Final

# The integration's "domain": its unique ID inside Home Assistant. It must
# match both the folder name (custom_components/wellue_ble) and the "domain"
# key in manifest.json. Home Assistant uses it to find the integration, to
# group its config entries, and as a prefix in log messages and services.
DOMAIN: Final = "wellue_ble"

# Shown as the manufacturer on the device's page in Home Assistant.
MANUFACTURER: Final = "Wellue"

# How often to ask the oximeter for a new reading. The device never sends
# readings by itself, so every value has to be asked for. One second matches
# the ESPHome setup, where this rate was tested for battery impact.
UPDATE_INTERVAL: Final = timedelta(seconds=1)

# The key under which the Monitoring switch's on/off state is saved in the
# config entry's data, so it's remembered across Home Assistant restarts.
CONF_MONITORING_ENABLED: Final = "monitoring_enabled"

# Unit for heart rates. Home Assistant has no constant for beats per minute;
# core integrations use the plain text "bpm".
UNIT_BEATS_PER_MINUTE: Final = "bpm"

# The models we recognize, keyed by the start of the name each one advertises
# over Bluetooth. For example, a Checkme O2 Max advertises "O2M 2693", where
# 2693 is the last four digits of its serial number.
#
# This is used in two places:
#   - to build a friendly device name ("O2M 2693" -> "Checkme O2 Max 2693"),
#   - to pick which nearby Bluetooth devices to offer during manual setup.
#
# Keep it in sync with the "bluetooth" matchers in manifest.json. Those
# matchers decide which devices Home Assistant discovers on its own.
MODEL_NAME_BY_ADVERTISED_NAME_PREFIX: Final = {
    "O2M": "Checkme O2 Max",
    "Band-WU": "Checkme O2 Ultra",
}
