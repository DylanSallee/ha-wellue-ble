"""Config flow: the setup screens for adding a Wellue Checkme O2.

Some Home Assistant terms used below:

- **Config entry:** one configured instance of an integration, stored by Home
  Assistant. Each oximeter you add becomes its own config entry. It shows up
  under Settings > Devices & services > Wellue.

- **Config flow:** the series of screens ("steps") that creates a config
  entry. Each step is a method named ``async_step_<step id>``. A step either
  shows a form, moves on to another step, creates the entry, or aborts.

- **Discovery:** manifest.json lists Bluetooth "matchers" (advertised names
  starting with "O2M" or "Band-WU"). When Home Assistant hears a matching
  device, it starts this flow by itself at ``async_step_bluetooth``. You see
  that as a "Discovered" card on the Devices & services page.

- **unique_id:** a value that identifies one physical device, so the same
  oximeter can't be added twice. We use its Bluetooth address.

There are two ways into this flow:

1. Automatic: async_step_bluetooth -> async_step_bluetooth_confirm
2. Manual ("Add integration" button): async_step_user, which lists the
   recognized devices Home Assistant can currently hear.
"""

from typing import Any, override

# probatio describes and checks the fields of a form. Home Assistant core used
# to use a library called voluptuous for this and now uses probatio. It works
# the same way: Schema, Required, In, and so on.
import probatio

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN
from .naming import friendly_device_name, is_supported_advertised_name


class WellueCheckmeO2ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle adding a Wellue Checkme O2 to Home Assistant.

    ``domain=DOMAIN`` registers this class as the config flow for our
    integration. Home Assistant creates a new instance of it every time a
    flow starts, so the attributes below only live for one setup attempt.
    """

    # Version of the data we store in the config entry. If the stored format
    # ever changes, raise this and add a migration, so existing entries keep
    # working.
    VERSION = 1

    def __init__(self) -> None:
        """Start a new flow with nothing discovered yet."""
        # Set by async_step_bluetooth: the advertisement that started the flow.
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        # Filled by async_step_user: devices to offer, as address -> name.
        self._device_names_by_address: dict[str, str] = {}

    # -----------------------------------------------------------------
    # Way 1: Home Assistant discovered the device by itself
    # -----------------------------------------------------------------

    # @override marks a method that replaces one from the parent class
    # (ConfigFlow). If the parent's method were ever renamed, type checkers
    # would flag this one instead of it silently never being called.
    @override
    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a device found by Bluetooth discovery.

        ``discovery_info`` holds what Home Assistant heard: the device's
        address, advertised name, signal strength, and so on.
        """
        # Claim this device for the flow. If it's already configured, stop
        # here (the "already_configured" abort). If another flow is already
        # setting it up, this one stops too ("already_in_progress").
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info

        # "title_placeholders" fills in "{name}" in the "flow_title" text in
        # translations/en.json. It's the name shown on the "Discovered" card.
        self.context["title_placeholders"] = {
            "name": friendly_device_name(discovery_info.name)
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to confirm adding the discovered device.

        Every step is called twice: first with ``user_input=None`` to show
        the form, then again with what the user submitted.
        """
        assert self._discovery_info is not None
        device_name = friendly_device_name(self._discovery_info.name)

        # Second call: the user clicked Submit, so create the config entry.
        # "title" is the entry's name in the UI. "data" is stored with the
        # entry, and __init__.py reads the address back from it.
        if user_input is not None:
            return self.async_create_entry(
                title=device_name,
                data={CONF_ADDRESS: self._discovery_info.address},
            )

        # First call: show a form with no fields, just a Submit button.
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": device_name},
        )

    # -----------------------------------------------------------------
    # Way 2: the user clicked "Add integration" and picked Wellue
    # -----------------------------------------------------------------

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick from the recognized devices nearby."""
        # Second call: the user picked a device and clicked Submit.
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            # raise_on_progress=False: if a "Discovered" card is already open
            # for this device, let this manual setup go ahead anyway. Home
            # Assistant removes the card once this entry is created.
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._device_names_by_address[address],
                data={CONF_ADDRESS: address},
            )

        # First call: build the list of devices to offer. Skip devices that
        # are already set up, and devices that aren't a model we recognize.
        # connectable=True: only devices that can be connected to (some
        # Bluetooth proxies only listen and can't connect).
        already_configured_addresses = self._async_current_ids(include_ignore=False)
        for service_info in async_discovered_service_info(self.hass, connectable=True):
            if service_info.address in already_configured_addresses:
                continue
            if not is_supported_advertised_name(service_info.name):
                continue
            self._device_names_by_address[service_info.address] = friendly_device_name(
                service_info.name
            )

        if not self._device_names_by_address:
            return self.async_abort(reason="no_devices_found")

        # Show a dropdown. The key is what we get back in user_input (the
        # address). The value is the label the user sees.
        dropdown_labels_by_address = {
            address: f"{device_name} ({address})"
            for address, device_name in self._device_names_by_address.items()
        }
        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_ADDRESS): probatio.In(
                        dropdown_labels_by_address
                    )
                }
            ),
        )
