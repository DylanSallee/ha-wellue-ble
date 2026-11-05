"""The Wellue Checkme O2 integration: set up and unload a config entry.

Home Assistant calls these functions itself:

- ``async_setup_entry`` when a config entry starts: after it's first added,
  each time Home Assistant starts, and when you click "Reload".
- ``async_unload_entry`` when it stops: on "Reload", "Disable", "Delete",
  and when Home Assistant shuts down.

If setup raises ``ConfigEntryNotReady``, Home Assistant shows the entry as
"Retrying setup" and tries again by itself a little later, waiting longer
between each try. That's the standard way to handle a device that's off or
out of range when Home Assistant starts.

Step A (this version) only checks that Home Assistant can reach the oximeter.
Step B adds the coordinator, which connects and reads the sensors, and the
entities that show the readings.
"""

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one oximeter from its config entry.

    Return True when setup succeeded.
    """
    # The config flow stored the device's Bluetooth address in the entry.
    address: str = entry.data[CONF_ADDRESS]

    # Ask Home Assistant's Bluetooth integration for a way to connect to this
    # address: through the local adapter or one of the ESPHome proxies,
    # whichever has heard it best recently. connectable=True skips proxies
    # that can only listen. It returns None if no adapter or proxy has heard
    # the device recently, e.g. it's off, out of range, or another device
    # (like the old ESPHome setup) is connected to it.
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

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Return True when unloading succeeded. There's nothing to clean up yet;
    step B will disconnect from the device here.
    """
    return True
