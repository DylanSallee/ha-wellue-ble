"""Sensor entities.

Two kinds:

- **Readings**, from the latest SensorReading (once a second): SpO2, heart
  rate, perfusion index, motion and battery.
- **Settings**, from the device's DeviceInfo (fetched after each reconnect):
  the SpO2 and heart rate alert thresholds, buzzer volume and vibration
  intensity. These are "diagnostic" entities, listed separately on the device
  page. They're read-only for now; changing them needs a library update.

Each sensor is described by an entity description: a list of settings (key,
unit, device class, ...) plus ``value_fn``, a small function that picks this
sensor's value out of a SensorReading or a DeviceInfo. One entity class per
kind then works for all of them.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from wellue_ble import DeviceInfo as WellueDeviceInfo, SensorReading

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import UNIT_BEATS_PER_MINUTE
from .coordinator import WellueConfigEntry
from .entity import WellueCheckmeO2Entity

# How many updates of these entities Home Assistant may run at the same time.
# 0 means no limit, which is right here: the entities never fetch anything
# themselves, they only read the coordinator's latest data.
PARALLEL_UPDATES = 0


# A dataclass is a class that mostly just holds named values. frozen=True
# makes it read-only once created. kw_only=True means every value has to be
# passed by name (key="motion", ...), which keeps the descriptions readable.
@dataclass(frozen=True, kw_only=True)
class WellueReadingSensorEntityDescription(SensorEntityDescription):
    """A sensor whose value comes from the latest SensorReading."""

    # A function that takes a SensorReading and returns this sensor's value.
    # None means "no valid value", which makes the sensor Unavailable.
    value_fn: Callable[[SensorReading], int | float | None]


@dataclass(frozen=True, kw_only=True)
class WellueSettingSensorEntityDescription(SensorEntityDescription):
    """A sensor whose value comes from the device's settings (DeviceInfo)."""

    # Takes a DeviceInfo and returns this sensor's value, or None.
    value_fn: Callable[[WellueDeviceInfo], int | None]


# The reading sensors.
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
READING_SENSOR_DESCRIPTIONS: tuple[WellueReadingSensorEntityDescription, ...] = (
    WellueReadingSensorEntityDescription(
        key="oxygen_saturation",
        translation_key="oxygen_saturation",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda reading: reading.oxygen_saturation_percent,
    ),
    WellueReadingSensorEntityDescription(
        key="heart_rate",
        translation_key="heart_rate",
        native_unit_of_measurement=UNIT_BEATS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda reading: reading.heart_rate_bpm,
    ),
    WellueReadingSensorEntityDescription(
        key="perfusion_index",
        translation_key="perfusion_index",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        # Show one decimal place, like the ViHealth app (e.g. 2.3 %).
        suggested_display_precision=1,
        value_fn=lambda reading: reading.perfusion_index_percent,
    ),
    WellueReadingSensorEntityDescription(
        key="motion",
        translation_key="motion",
        # Unitless: a higher number means more movement.
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda reading: reading.motion,
    ),
    WellueReadingSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda reading: reading.battery_level_percent,
    ),
)

# The setting sensors. EntityCategory.DIAGNOSTIC lists them in the device
# page's "Diagnostic" section instead of with the readings. They have no
# state_class: they're settings, not measurements, so no statistics.
SETTING_SENSOR_DESCRIPTIONS: tuple[WellueSettingSensorEntityDescription, ...] = (
    WellueSettingSensorEntityDescription(
        key="oxygen_alert_threshold",
        translation_key="oxygen_alert_threshold",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda settings: settings.oxygen_alert_threshold_percent,
    ),
    WellueSettingSensorEntityDescription(
        key="heart_rate_alert_high",
        translation_key="heart_rate_alert_high",
        native_unit_of_measurement=UNIT_BEATS_PER_MINUTE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda settings: settings.heart_rate_alert_high_bpm,
    ),
    WellueSettingSensorEntityDescription(
        key="heart_rate_alert_low",
        translation_key="heart_rate_alert_low",
        native_unit_of_measurement=UNIT_BEATS_PER_MINUTE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda settings: settings.heart_rate_alert_low_bpm,
    ),
    WellueSettingSensorEntityDescription(
        key="buzzer_volume",
        translation_key="buzzer_volume",
        # Unitless: the device's own volume level.
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda settings: settings.buzzer_volume,
    ),
    WellueSettingSensorEntityDescription(
        key="vibration_intensity",
        translation_key="vibration_intensity",
        # Unitless: the device's own intensity level.
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda settings: settings.vibration_intensity,
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
        WellueCheckmeO2ReadingSensor(coordinator, description)
        for description in READING_SENSOR_DESCRIPTIONS
    )
    async_add_entities(
        WellueCheckmeO2SettingSensor(coordinator, description)
        for description in SETTING_SENSOR_DESCRIPTIONS
    )


class WellueCheckmeO2ReadingSensor(WellueCheckmeO2Entity, SensorEntity):
    """A sensor showing one value from the latest reading."""

    # Tells type checkers which kind of description this entity has.
    entity_description: WellueReadingSensorEntityDescription

    @property
    @override
    def native_value(self) -> int | float | None:
        """Return the sensor's value from the latest reading."""
        reading = self.coordinator.data
        # No reading yet, or monitoring is off.
        if reading is None:
            return None
        return self.entity_description.value_fn(reading)

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


class WellueCheckmeO2SettingSensor(WellueCheckmeO2Entity, SensorEntity):
    """A diagnostic sensor showing one of the device's settings."""

    entity_description: WellueSettingSensorEntityDescription

    @property
    @override
    def native_value(self) -> int | None:
        """Return the setting's value, as last fetched from the device."""
        settings = self.coordinator.wellue_device_info
        # Not fetched yet, or monitoring is off.
        if settings is None:
            return None
        return self.entity_description.value_fn(settings)

    @property
    @override
    def available(self) -> bool:
        """Unavailable when the last update failed, or the value is missing."""
        return super().available and self.native_value is not None
