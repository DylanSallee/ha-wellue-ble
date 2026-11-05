"""The Wellue integration: set up and unload a config entry.

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

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import WellueCheckmeO2Coordinator, WellueConfigEntry

# The entity platforms this integration provides. Each one is a file
# (sensor.py, binary_sensor.py, switch.py) with its own async_setup_entry.
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: WellueConfigEntry) -> bool:
    """Set up one oximeter from its config entry.

    Return True when setup succeeded.
    """
    # The coordinator polls the oximeter. Creating it doesn't connect yet.
    coordinator = WellueCheckmeO2Coordinator(hass, entry)

    if coordinator.monitoring_enabled:
        # Fetch the first reading now. This connects, fills in the device
        # page, and makes sure the entities have a value as soon as they're
        # created. If it fails (e.g. the device is out of range),
        # async_config_entry_first_refresh raises ConfigEntryNotReady, so
        # Home Assistant retries the whole setup later.
        try:
            await coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady:
            # The retry creates a new coordinator, so close any connection
            # this one opened before failing.
            await coordinator.async_disconnect()
            raise
    # With monitoring off, don't connect at all: the ViHealth app may be using
    # the device. Setup still succeeds, so the Monitoring switch is there to
    # turn it back on.

    # Keep the coordinator with the config entry, so the entity files (and
    # async_unload_entry below) can get it back from entry.runtime_data.
    entry.runtime_data = coordinator

    # Home Assistant doesn't unload config entries when it shuts down, so
    # disconnect explicitly then. That frees the oximeter for the ViHealth app
    # straight away, instead of only after the connection times out.
    async def _async_disconnect_on_stop(event: Event) -> None:
        await coordinator.async_disconnect()

    # async_listen_once returns a function that cancels the listener;
    # async_on_unload runs it when the entry unloads, so the listener doesn't
    # outlive the integration.
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_disconnect_on_stop)
    )

    # Create the entities: runs async_setup_entry in sensor.py,
    # binary_sensor.py and switch.py.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WellueConfigEntry) -> bool:
    """Unload a config entry: remove its entities and disconnect.

    Return True when unloading succeeded. The coordinator stops polling by
    itself, and the callbacks registered with async_on_unload are cancelled.
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_disconnect()
    return unload_ok
