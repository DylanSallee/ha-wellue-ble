"""The coordinator: the one place that talks to the oximeter.

What a coordinator is
---------------------
Home Assistant's ``DataUpdateCoordinator`` fetches data on a timer and hands
the latest result to every entity that uses it. Here that means:

- Every second, the coordinator asks the oximeter for one reading.
- All the sensors (SpO2, heart rate, battery, ...) read their value from that
  one shared reading, instead of each one talking to the device separately.
- If fetching fails, the coordinator marks every entity Unavailable at once,
  and Home Assistant logs one error. When fetching works again, it logs that
  it recovered and the entities come back.

The coordinator only polls while at least one entity is listening, and stops
by itself when the integration is unloaded.

How it connects
---------------
The library keeps the Bluetooth connection open between readings. This file
only decides *when* to (re)connect:

- **Not connected, and Home Assistant can't hear the device:** fail straight
  away without trying to connect. Connecting would just time out, and keep
  a Bluetooth proxy's connection slot busy while it does.
- **Not connected, and the device can be heard:** connect, then fetch the
  device's identity and settings (DeviceInfo) and update its device page.
  This happens after every reconnect, so changes made in the ViHealth app
  show up once Home Assistant reconnects.
- **The device stops answering:** drop the connection, so the next poll
  starts a fresh one instead of reusing a connection that has gone stuck.
"""

import logging
from typing import override

from wellue_ble import (
    # The library and Home Assistant both have a class called DeviceInfo.
    # Rename the library's one here so it's always clear which is meant.
    DeviceInfo as WellueDeviceInfo,
    SensorReading,
    WellueCheckmeO2,
    WellueError,
    WellueResponseTimeoutError,
)

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, MANUFACTURER, UPDATE_INTERVAL
from .naming import model_name_from_advertised_name

_LOGGER = logging.getLogger(__name__)

# A config entry for this integration. The part in square brackets says what
# its "runtime_data" holds: the coordinator. __init__.py stores it there
# during setup, and the sensor files read it back from there. Writing it as a
# type lets editors and type checkers know what entry.runtime_data contains.
type WellueConfigEntry = ConfigEntry[WellueCheckmeO2Coordinator]


class WellueCheckmeO2Coordinator(DataUpdateCoordinator[SensorReading]):
    """Fetch a reading from one oximeter every second.

    ``DataUpdateCoordinator[SensorReading]`` means the data this coordinator
    hands out is a library ``SensorReading``. After each successful update it
    is available as ``coordinator.data``.
    """

    # Tells type checkers that config_entry is our typed config entry.
    config_entry: WellueConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: WellueConfigEntry,
        device: WellueCheckmeO2,
    ) -> None:
        """Set up the coordinator. This doesn't connect yet."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            # Used in log messages, e.g. "Error fetching Checkme O2 Max 2693
            # data: ...".
            name=config_entry.title,
            update_interval=UPDATE_INTERVAL,
            # Only tell the entities about a reading when it differs from the
            # previous one. SensorReading can be compared with ==, so
            # identical readings (common while the device sits on its
            # charger) don't make every entity re-write its state.
            always_update=False,
        )
        # The library object that talks to the oximeter.
        self.device = device
        # The device's Bluetooth address, stored by the config flow.
        self.address: str = config_entry.data[CONF_ADDRESS]
        # The device's identity and settings, fetched after each (re)connect.
        # None until the first successful connection.
        self.wellue_device_info: WellueDeviceInfo | None = None

    @override
    async def _async_update_data(self) -> SensorReading:
        """Fetch one reading. The coordinator calls this every second.

        Raising UpdateFailed marks every entity Unavailable until an update
        succeeds again.
        """
        if not self.device.is_connected:
            # Ask Home Assistant's Bluetooth integration for the best way to
            # reach the device right now: the local adapter or a proxy. None
            # means no adapter or proxy has heard it recently.
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            if ble_device is None:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="device_not_found",
                    translation_placeholders={
                        "address": self.address,
                        "reason": bluetooth.async_address_reachability_diagnostics(
                            self.hass,
                            self.address,
                            bluetooth.BluetoothReachabilityIntent.CONNECTION,
                        ),
                    },
                )
            self.device.set_ble_device(ble_device)

        try:
            if not self.device.is_connected:
                # get_device_info() opens the connection first, since the
                # library connects automatically before any command.
                await self._async_refresh_device_info()
            return await self.device.read_sensors()
        except WellueResponseTimeoutError as error:
            # Connected, but the device didn't answer within 5 seconds. Drop
            # the connection so the next poll reconnects from scratch.
            await self.device.disconnect()
            raise self._communication_error(error) from error
        except WellueError as error:
            # Any other library error: connection failed or dropped, or a
            # garbled answer. If the connection dropped, the next poll
            # reconnects.
            raise self._communication_error(error) from error

    async def _async_refresh_device_info(self) -> None:
        """Fetch the device's identity and settings, and update its device page.

        The device page is the one under Settings > Devices & services >
        Devices. Home Assistant's "device registry" stores those pages.
        """
        self.wellue_device_info = await self.device.get_device_info()

        # async_get_or_create creates the device page the first time, and
        # updates it on later calls. "identifiers" is how Home Assistant
        # recognizes this device; the entities use the same identifier to
        # attach themselves to the page (see entity.py).
        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, self.address)},
            # Marks it as a Bluetooth device with this address, which links
            # it with Home Assistant's own Bluetooth information.
            connections={(dr.CONNECTION_BLUETOOTH, self.address)},
            name=self.config_entry.title,
            manufacturer=MANUFACTURER,
            # e.g. "Checkme O2 Max". None for an unrecognized model.
            model=model_name_from_advertised_name(self.device.name),
            # The model code the device reports, e.g. "1642". Both the Max
            # and the Ultra report the same code.
            model_id=self.wellue_device_info.model,
            serial_number=self.wellue_device_info.serial_number,
            hw_version=self.wellue_device_info.hardware_version,
            # No sw_version (firmware): the device reports "0.0.0" while the
            # ViHealth app shows "1.0.0.0", so the real value isn't known yet.
            # A blank field is less confusing than a wrong one.
        )

    def _communication_error(self, error: WellueError) -> UpdateFailed:
        """Build the UpdateFailed error for a failed exchange with the device."""
        return UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="communication_error",
            translation_placeholders={
                "name": self.config_entry.title,
                "error": str(error),
            },
        )
