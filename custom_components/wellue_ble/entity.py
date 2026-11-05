"""The base class shared by all of this integration's entities.

An "entity" is one value Home Assistant shows and records, like
``sensor.checkme_o2_max_2693_spo2``. Every entity here:

- gets its value from the coordinator's latest reading (CoordinatorEntity),
- belongs to the oximeter's device page,
- has a unique_id, so Home Assistant remembers it across restarts and you
  can rename it or change its settings in the UI.
"""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WellueCheckmeO2Coordinator


class WellueCheckmeO2Entity(CoordinatorEntity[WellueCheckmeO2Coordinator]):
    """Base entity: links to the coordinator and the device page.

    CoordinatorEntity does two things for us. It updates the entity whenever
    the coordinator has a new reading, and it makes the entity Unavailable
    whenever the coordinator's last update failed.
    """

    # The entity's name is combined with the device name. For example the
    # "SpO2" entity of "Checkme O2 Max 2693" is shown as
    # "Checkme O2 Max 2693 SpO2", with the entity ID
    # sensor.checkme_o2_max_2693_spo2.
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WellueCheckmeO2Coordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Set up the entity from its description (see sensor.py)."""
        super().__init__(coordinator)
        # The description holds everything that makes this entity what it
        # is: its key, name, unit, device class, and so on.
        self.entity_description = entity_description
        # Unique across all of Home Assistant: the device's address plus what
        # this entity measures, e.g. "AA:BB:CC:DD:EE:FF_heart_rate".
        self._attr_unique_id = f"{coordinator.address}_{entity_description.key}"
        # Attach this entity to the device page. The coordinator creates that
        # page and fills in its details (serial number, model, ...) when it
        # connects; here we only need the same identifier to point at it.
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.address)})
