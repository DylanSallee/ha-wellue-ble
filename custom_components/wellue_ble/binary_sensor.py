"""Binary sensor entities: finger present, charging and reading valid.

A binary sensor is on or off. Its "device class" decides how Home Assistant
shows those two states, e.g. Detected/Clear or Charging/Not charging.

This file works the same way as sensor.py: a list of descriptions, and one
entity class that uses them.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from wellue_ble import SensorReading

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import WellueConfigEntry
from .entity import WellueCheckmeO2Entity

# No limit on parallel updates; see the same line in sensor.py.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class WellueBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Everything about one binary sensor, plus how to get its value."""

    # Takes a SensorReading and returns True (on), False (off), or None (no
    # value, which makes the binary sensor Unavailable).
    value_fn: Callable[[SensorReading], bool | None]


def _is_charging(reading: SensorReading) -> bool | None:
    """Return whether the device is charging, or None if the state is unknown.

    On only while actively charging; off once fully charged, even if it's
    still on its dock (same as the ESPHome setup).

    Careful: ChargingState.NOT_CHARGING is 0, which Python treats as False.
    So test "is None" explicitly, never "if reading.charging_state:".
    """
    if reading.charging_state is None:
        return None
    return reading.is_charging


BINARY_SENSOR_DESCRIPTIONS: tuple[WellueBinarySensorEntityDescription, ...] = (
    WellueBinarySensorEntityDescription(
        key="finger_present",
        translation_key="finger_present",
        # OCCUPANCY shows the states as Detected / Clear.
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        # The library ignores the finger flag while charging, because the
        # firmware falsely reports a finger while docked.
        value_fn=lambda reading: reading.finger_detected,
    ),
    WellueBinarySensorEntityDescription(
        key="charging",
        # No translation_key: Home Assistant names it "Charging" from the
        # device class, and shows the states as Charging / Not charging.
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=_is_charging,
    ),
    WellueBinarySensorEntityDescription(
        key="reading_valid",
        translation_key="reading_valid",
        # True when the health values are real measurements: a finger is
        # present and SpO2 and heart rate are within believable ranges.
        value_fn=lambda reading: reading.reading_is_valid,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WellueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the binary sensors. Home Assistant calls this during setup."""
    coordinator = entry.runtime_data
    async_add_entities(
        WellueCheckmeO2BinarySensor(coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class WellueCheckmeO2BinarySensor(WellueCheckmeO2Entity, BinarySensorEntity):
    """One binary sensor, configured by its description."""

    entity_description: WellueBinarySensorEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True for on, False for off, from the latest reading."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    @override
    def available(self) -> bool:
        """Unavailable when the last update failed, or the value is missing."""
        return super().available and self.is_on is not None
