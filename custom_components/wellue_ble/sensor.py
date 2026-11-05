"""Sensor entities: SpO2, heart rate, perfusion index, motion and battery.

Each sensor is described by a WellueSensorEntityDescription: a list of
settings (key, unit, device class, ...) plus ``value_fn``, a small function
that picks this sensor's value out of a SensorReading. One entity class,
WellueCheckmeO2Sensor, then works for all of them.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from wellue_ble import SensorReading

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import WellueConfigEntry
from .entity import WellueCheckmeO2Entity

# How many updates of these entities Home Assistant may run at the same time.
# 0 means no limit, which is right here: the entities never fetch anything
# themselves, they only read the coordinator's latest reading.
PARALLEL_UPDATES = 0


# A dataclass is a class that mostly just holds named values. frozen=True
# makes it read-only once created. kw_only=True means every value has to be
# passed by name (key="motion", ...), which keeps the descriptions readable.
@dataclass(frozen=True, kw_only=True)
class WellueSensorEntityDescription(SensorEntityDescription):
    """Everything about one sensor, plus how to get its value."""

    # A function that takes a SensorReading and returns this sensor's value.
    # None means "no valid value", which makes the sensor Unavailable.
    value_fn: Callable[[SensorReading], int | float | None]


# The sensors this integration creates.
#
# - key: identifies the sensor; part of its unique_id. Never change it, or
#   Home Assistant treats the sensor as a new one and loses its history.
# - translation_key: where its name lives in translations/en.json, and its
#   icon in icons.json. Battery has none: Home Assistant names it "Battery"
#   and picks a battery icon from its device class.
# - state_class MEASUREMENT: the value is a measurement at a point in time.
#   This makes Home Assistant keep long-term statistics (5-minute and hourly
#   mean/min/max) for it.
# - value_fn=lambda reading: ...: "lambda" writes a tiny one-line function.
#   This one takes a reading and returns one of its fields.
SENSOR_DESCRIPTIONS: tuple[WellueSensorEntityDescription, ...] = (
    WellueSensorEntityDescription(
        key="oxygen_saturation",
        translation_key="oxygen_saturation",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda reading: reading.oxygen_saturation_percent,
    ),
    WellueSensorEntityDescription(
        key="heart_rate",
        translation_key="heart_rate",
        # Home Assistant has no constant for beats per minute; core
        # integrations use the plain text "bpm".
        native_unit_of_measurement="bpm",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda reading: reading.heart_rate_bpm,
    ),
    WellueSensorEntityDescription(
        key="perfusion_index",
        translation_key="perfusion_index",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        # Show one decimal place, like the ViHealth app (e.g. 2.3 %).
        suggested_display_precision=1,
        value_fn=lambda reading: reading.perfusion_index_percent,
    ),
    WellueSensorEntityDescription(
        key="motion",
        translation_key="motion",
        # Unitless: a higher number means more movement.
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda reading: reading.motion,
    ),
    WellueSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda reading: reading.battery_level_percent,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WellueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the sensors. Home Assistant calls this during setup.

    __init__.py asks for it with async_forward_entry_setups.
    """
    coordinator = entry.runtime_data
    async_add_entities(
        WellueCheckmeO2Sensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class WellueCheckmeO2Sensor(WellueCheckmeO2Entity, SensorEntity):
    """One sensor, configured by its WellueSensorEntityDescription."""

    # Tells type checkers which kind of description this entity has.
    entity_description: WellueSensorEntityDescription

    @property
    @override
    def native_value(self) -> int | float | None:
        """Return the sensor's value from the latest reading."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    @override
    def available(self) -> bool:
        """Return False to show the sensor as Unavailable.

        Unavailable when the coordinator's last update failed (the base class
        checks that), and also when this value is missing. For example,
        without a finger on the sensor the library returns None for SpO2,
        heart rate, perfusion index and motion. Showing Unavailable instead
        of Unknown was Dylan's choice; see CLAUDE.md.
        """
        return super().available and self.native_value is not None
