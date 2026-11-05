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
- **Not connected, and the device can be heard:** ask Home Assistant for the
  best adapter or proxy to reach it, connect, then fetch the device's identity
  and settings (DeviceInfo) and update its device page. This happens after
  every reconnect, so changes made in the ViHealth app show up once Home
  Assistant reconnects.
- **The device stops answering:** drop the connection, so the next poll
  starts a fresh one instead of reusing a connection that has gone stuck.

Monitoring on and off
---------------------
The Monitoring switch (switch.py) pauses all of this so the ViHealth app can
connect. While monitoring is off the coordinator doesn't poll and doesn't
touch the device, and every entity except the switch shows Unavailable. The
switch's state is saved in the config entry, so it survives restarts.
"""

import asyncio
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_MONITORING_ENABLED, DOMAIN, MANUFACTURER, UPDATE_INTERVAL
from .naming import model_name_from_advertised_name

_LOGGER = logging.getLogger(__name__)

# A config entry for this integration. The part in square brackets says what
# its "runtime_data" holds: the coordinator. __init__.py stores it there
# during setup, and the entity files read it back from there. Writing it as a
# type lets editors and type checkers know what entry.runtime_data contains.
type WellueConfigEntry = ConfigEntry[WellueCheckmeO2Coordinator]


class WellueCheckmeO2Coordinator(DataUpdateCoordinator[SensorReading | None]):
    """Fetch a reading from one oximeter every second.

    ``DataUpdateCoordinator[SensorReading | None]`` means the data this
    coordinator hands out (``coordinator.data``) is a library SensorReading,
    or None when there's no reading: before the first one, and while
    monitoring is off.
    """

    # Tells type checkers that config_entry is our typed config entry.
    config_entry: WellueConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: WellueConfigEntry) -> None:
        """Set up the coordinator. This doesn't connect yet."""
        # Whether the Monitoring switch is on. Read from the config entry,
        # where switch changes are saved; on by default.
        monitoring_enabled: bool = config_entry.data.get(CONF_MONITORING_ENABLED, True)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            # Used in log messages, e.g. "Error fetching Checkme O2 Max 2693
            # data: ...".
            name=config_entry.title,
            # None means "don't poll", for when monitoring is off.
            update_interval=UPDATE_INTERVAL if monitoring_enabled else None,
            # Only tell the entities about a reading when it differs from the
            # previous one. SensorReading can be compared with ==, so
            # identical readings (common while the device sits on its
            # charger) don't make every entity re-write its state.
            always_update=False,
        )
        self.monitoring_enabled = monitoring_enabled
        # The device's Bluetooth address, stored by the config flow.
        self.address: str = config_entry.data[CONF_ADDRESS]
        # The library object that talks to the oximeter. Created the first
        # time we connect, because it needs a route to the device (a
        # BLEDevice), which only exists while Home Assistant can hear it.
        self.device: WellueCheckmeO2 | None = None
        # The device's identity and settings, fetched after each (re)connect.
        # None until then, and while monitoring is off.
        self.wellue_device_info: WellueDeviceInfo | None = None
        # Makes reading and switching monitoring off take turns. Without it,
        # switching off in the middle of a reading could disconnect, and then
        # the reading's next command would quietly reconnect.
        self._device_access_lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        """Return True while the Bluetooth connection is open."""
        return self.device is not None and self.device.is_connected

    @override
    async def _async_update_data(self) -> SensorReading | None:
        """Fetch one reading. The coordinator calls this every second.

        Raising UpdateFailed marks every entity Unavailable until an update
        succeeds again.
        """
        async with self._device_access_lock:
            if not self.monitoring_enabled:
                # Monitoring was switched off while this update was waiting
                # its turn. Leave the device alone.
                return None

            if not self.is_connected:
                self._prepare_device_for_connecting()

            # _prepare_device_for_connecting either created the device or
            # raised, so it's set from here on. "assert" states that for
            # type checkers.
            assert self.device is not None
            try:
                if not self.device.is_connected:
                    # get_device_info() opens the connection first, since the
                    # library connects automatically before any command.
                    await self._async_refresh_device_info()
                    # Now connected. Tell the entities straight away, so the
                    # Connected entity shows it (see _handle_device_disconnected
                    # for why it needs telling).
                    self.async_update_listeners()
                return await self.device.read_sensors()
            except WellueResponseTimeoutError as error:
                # Connected, but the device didn't answer within 5 seconds.
                # Drop the connection so the next poll reconnects from scratch.
                await self.device.disconnect()
                raise self._communication_error(error) from error
            except WellueError as error:
                # Any other library error: connection failed or dropped, or a
                # garbled answer. If the connection dropped, the next poll
                # reconnects.
                raise self._communication_error(error) from error

    def _prepare_device_for_connecting(self) -> None:
        """Give the library the best route to the device, before connecting.

        Raises UpdateFailed if Home Assistant can't hear the device at all.
        """
        # Ask Home Assistant's Bluetooth integration for the best way to reach
        # the device right now: the local adapter or one of the proxies,
        # whichever heard it best recently. connectable=True skips proxies
        # that can only listen. None means nothing has heard it recently: it's
        # off, out of range, or something else (like the ViHealth app) is
        # connected to it.
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
                translation_placeholders={
                    "address": self.address,
                    # A plain-words explanation, e.g. which adapters and
                    # proxies last heard the device.
                    "reason": bluetooth.async_address_reachability_diagnostics(
                        self.hass,
                        self.address,
                        bluetooth.BluetoothReachabilityIntent.CONNECTION,
                    ),
                },
            )

        if self.device is None:
            self.device = WellueCheckmeO2(
                ble_device, disconnected_callback=self._handle_device_disconnected
            )
        else:
            self.device.set_ble_device(ble_device)

    @callback
    def _handle_device_disconnected(self) -> None:
        """Called by the library whenever the Bluetooth connection closes.

        The coordinator only tells the entities about changes to the reading
        (or to whether the last update worked). The connection opening or
        closing isn't part of the reading, so without this the Connected
        entity could miss a quick drop-and-reconnect. So tell the entities
        ourselves: here when the connection closes, and in _async_update_data
        right after it opens.

        @callback marks a function that runs inside Home Assistant's event
        loop and doesn't wait for anything, so it's safe to call directly.
        """
        self.async_update_listeners()

    async def _async_refresh_device_info(self) -> None:
        """Fetch the device's identity and settings, and update its device page.

        The device page is the one under Settings > Devices & services >
        Devices. Home Assistant's "device registry" stores those pages.
        """
        assert self.device is not None
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

    # -----------------------------------------------------------------
    # Monitoring switch, connecting and disconnecting
    # -----------------------------------------------------------------

    async def async_start_monitoring(self) -> None:
        """Turn monitoring on: save it, then connect and poll again."""
        if self.monitoring_enabled:
            return
        self.monitoring_enabled = True
        self._save_monitoring_enabled(True)
        self.update_interval = UPDATE_INTERVAL
        # Show the switch as on straight away. The other entities stay
        # Unavailable until the first reading arrives, because there's no
        # reading yet.
        self.async_update_listeners()
        # Fetch a reading now instead of waiting a second. When it finishes,
        # the coordinator schedules the next poll by itself.
        await self.async_refresh()

    async def async_stop_monitoring(self) -> None:
        """Turn monitoring off: save it, stop polling and disconnect."""
        if not self.monitoring_enabled:
            return
        # Set first, so an update that's waiting its turn sees it and leaves
        # the device alone.
        self.monitoring_enabled = False
        self._save_monitoring_enabled(False)
        # No interval: the coordinator stops scheduling polls.
        self.update_interval = None

        # Wait for a reading in progress to finish, then disconnect.
        async with self._device_access_lock:
            if self.device is not None:
                await self.device.disconnect()
            # Forget the device's settings; they're fetched again on
            # reconnect, in case they were changed in the app meanwhile.
            self.wellue_device_info = None

        # Forget the last reading too, so no old values show up when
        # monitoring resumes, then tell every entity to update. With no
        # reading, they all show Unavailable.
        self.async_set_updated_data(None)

    def _save_monitoring_enabled(self, monitoring_enabled: bool) -> None:
        """Save the switch's state in the config entry, so restarts keep it."""
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            # "**" copies the existing data (like the address), then the
            # monitoring flag is added or replaced.
            data={
                **self.config_entry.data,
                CONF_MONITORING_ENABLED: monitoring_enabled,
            },
        )

    async def async_disconnect(self) -> None:
        """Close the Bluetooth connection, if there is one."""
        if self.device is not None:
            await self.device.disconnect()
