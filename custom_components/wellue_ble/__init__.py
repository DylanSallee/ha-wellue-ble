"""The Wellue Checkme O2 integration: set up and unload a config entry.

Home Assistant calls these functions itself:

- ``async_setup_entry`` when a config entry starts: after it's first added,
  each time Home Assistant starts, and when you click "Reload".
- ``async_unload_entry`` when it stops: on "Reload", "Disable" and "Delete".

If setup raises ``ConfigEntryNotReady``, Home Assistant shows the entry as
"Retrying setup" and tries again by itself later, waiting longer between each
try (up to 10 minutes). It also retries straight away when it hears the
device advertise, because Bluetooth discovery then finds the already
configured entry (see config_flow.py). That's the standard way to handle a
device that's off or out of range when Home Assistant starts.
"""

from wellue_ble import WellueCheckmeO2

from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import WellueCheckmeO2Coordinator, WellueConfigEntry

# The entity platforms this integration provides. Each one is a file
# (sensor.py, binary_sensor.py) with its own async_setup_entry.
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: WellueConfigEntry) -> bool:
    """Set up one oximeter from its config entry.

    Return True when setup succeeded.
    """
    # The config flow stored the device's Bluetooth address in the entry.
    address: str = entry.data[CONF_ADDRESS]

    # Ask Home Assistant's Bluetooth integration for a way to connect to this
    # address: through the local adapter or one of the ESPHome proxies,
    # whichever has heard it best recently. connectable=True skips proxies
    # that can only listen. It returns None if no adapter or proxy has heard
    # the device recently, e.g. it's off, out of range, or something else
    # (like the old ESPHome setup or the ViHealth app) is connected to it.
    ble_device = bluetooth.async_ble_device_from_address(
        hass, address, connectable=True
    )
    if ble_device is None:
        # The message comes from "exceptions" in translations/en.json. The
        # "reason" explains in plain words why Home Assistant can't reach
        # the device, e.g. which adapters and proxies last heard it.
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={
                "address": address,
                "reason": bluetooth.async_address_reachability_diagnostics(
                    hass, address, bluetooth.BluetoothReachabilityIntent.CONNECTION
                ),
            },
        )

    # The library object for this oximeter, and the coordinator that polls it.
    # Creating them doesn't connect yet.
    device = WellueCheckmeO2(ble_device)
    coordinator = WellueCheckmeO2Coordinator(hass, entry, device)

    # Fetch the first reading now. This connects, fills in the device page,
    # and makes sure the entities have a value as soon as they're created.
    # If it fails, async_config_entry_first_refresh raises
    # ConfigEntryNotReady, so Home Assistant retries the whole setup later.
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        # The retry will create a new library object, so close any
        # connection this one opened before failing.
        await device.disconnect()
        raise

    # Keep the coordinator with the config entry, so the sensor files (and
    # async_unload_entry below) can get it back from entry.runtime_data.
    entry.runtime_data = coordinator

    @callback
    def _async_handle_bluetooth_advertisement(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Pass the device's latest route on to the library.

        Called every time an adapter or proxy hears the device advertise.
        service_info.device is the BLEDevice for the best way to reach it
        right now, which the library then uses for its next connection.
        """
        device.set_ble_device(service_info.device)

    # Ask Home Assistant's Bluetooth integration to call the function above
    # whenever it hears this address. PASSIVE: just listen; don't ask the
    # adapters to scan harder for it. Registering returns a function that
    # cancels the registration; async_on_unload runs it when the entry
    # unloads, so the callback doesn't outlive the integration.
    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_handle_bluetooth_advertisement,
            bluetooth.BluetoothCallbackMatcher(address=address),
            bluetooth.BluetoothScanningMode.PASSIVE,
        )
    )

    # Home Assistant doesn't unload config entries when it shuts down, so
    # disconnect explicitly then. That frees the oximeter for the ViHealth app
    # straight away, instead of only after the connection times out.
    async def _async_disconnect_on_stop(event: Event) -> None:
        await device.disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_disconnect_on_stop)
    )

    # Create the entities: runs async_setup_entry in sensor.py and
    # binary_sensor.py.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WellueConfigEntry) -> bool:
    """Unload a config entry: remove its entities and disconnect.

    Return True when unloading succeeded. The coordinator stops polling by
    itself, and the callbacks registered with async_on_unload are cancelled.
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.device.disconnect()
    return unload_ok
