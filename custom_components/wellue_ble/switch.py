"""The Monitoring switch: pause the integration so the ViHealth app can connect.

The oximeter accepts only one connection at a time. While Home Assistant is
connected, the official ViHealth app can't connect, so this switch:

- **Off:** stops polling and disconnects. Every other entity shows
  Unavailable. Use the app, then switch it back on.
- **On:** reconnects and polls every second again.

Its state is saved, so after a restart Home Assistant stays off the device
if monitoring was off. (The ESPHome setup always turned monitoring back on at
boot.)
"""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import WellueConfigEntry
from .entity import WellueCheckmeO2Entity

# No limit on parallel updates; see the same line in sensor.py.
PARALLEL_UPDATES = 0

MONITORING_SWITCH_DESCRIPTION = SwitchEntityDescription(
    key="monitoring",
    translation_key="monitoring",
    # CONFIG: a setting that changes how the integration behaves, not a
    # reading. Home Assistant lists it under "Configuration" on the device
    # page.
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WellueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the Monitoring switch. Home Assistant calls this during setup."""
    async_add_entities(
        [
            WellueCheckmeO2MonitoringSwitch(
                entry.runtime_data, MONITORING_SWITCH_DESCRIPTION
            )
        ]
    )


class WellueCheckmeO2MonitoringSwitch(WellueCheckmeO2Entity, SwitchEntity):
    """Turns polling of the oximeter on and off."""

    @property
    @override
    def available(self) -> bool:
        """Always available, so monitoring can be turned back on any time.

        Other entities go Unavailable when the device can't be reached; this
        switch controls Home Assistant itself, not the device.
        """
        return True

    @property
    @override
    def is_on(self) -> bool:
        """Return True while monitoring is on."""
        return self.coordinator.monitoring_enabled

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn monitoring on. Called when you switch it on in the UI.

        "**kwargs" accepts any extra options Home Assistant might pass; a
        simple switch has none to use.
        """
        await self.coordinator.async_start_monitoring()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn monitoring off. Called when you switch it off in the UI."""
        await self.coordinator.async_stop_monitoring()
