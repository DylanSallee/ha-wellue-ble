# Wellue integration (`wellue_ble`): context for Claude

This is the Home Assistant integration for Wellue Checkme O2 wrist pulse
oximeters (the Checkme O2 **Max** and **Ultra**). It lives in its own GitHub
repository, **`ha-wellue-ble`**, laid out for HACS.

- The integration domain is `wellue_ble`. Its display name (`"name"` in
  `manifest.json` and `hacs.json`) is **"Wellue"**, not "Wellue Checkme O2",
  leaving room for other Wellue devices. User-facing text about the device
  itself still says "Wellue Checkme O2".
- It ships through **HACS** first and aims for HA core later, so follow core
  conventions from the start: config flow, translation keys,
  `has_entity_name`, and a coordinator.
- All BLE and protocol work lives in a separate PyPI library, **`wellue-ble`**
  (<https://github.com/DylanSallee/wellue-ble>). This integration only maps that
  library onto HA entities. **Don't** put packet or byte handling here. If
  something is missing, add it to the library.
- Both are called `wellue_ble` in Python, and that's fine: the integration
  imports as `custom_components.wellue_ble` and the library as plain
  `wellue_ble`. Inside the integration, `from wellue_ble import ...` gets the
  library.

## Repository layout (HACS)

HACS expects exactly one integration, in `custom_components/<domain>/`, with a
`hacs.json` at the repository root:

```text
ha-wellue-ble/
├── custom_components/
│   └── wellue_ble/
│       ├── __init__.py          # set up / unload a config entry
│       ├── manifest.json
│       ├── config_flow.py
│       ├── const.py             # DOMAIN and other constants
│       ├── naming.py            # friendly names from the advertised name
│       ├── coordinator.py
│       ├── entity.py            # shared base entity (device info, unique_id)
│       ├── sensor.py
│       ├── binary_sensor.py
│       ├── switch.py
│       └── translations/
│           └── en.json          # user-facing text (see below)
├── .github/workflows/validate.yml
├── hacs.json
├── README.md
└── LICENSE
```

- **`manifest.json` for a custom integration** needs these on top of the
  milestone 1 keys below: `"name"`, `"version"` (e.g. `"0.1.0"`; HA refuses to
  load a custom integration without it), `"documentation"` and
  `"issue_tracker"` (GitHub URLs of this repo), and `"codeowners":
  ["@DylanSallee"]`. It also has two keys added in HA 2026.11, optional for
  custom integrations but required in core: `"categories":
  ["health_wellbeing"]` (where the integration appears when browsing, see
  <https://contributors.home-assistant.io/core/integrations/categories/>) and
  `"connectivity": ["bluetooth"]`. Older HA versions ignore them.
- **Translations:** core integrations write `strings.json` and a build script
  generates `translations/en.json` from it. Custom integrations don't get that
  script, so write `translations/en.json` directly. The format is the same, so
  moving to core later just means renaming it to `strings.json`.
- **`hacs.json`:** `{"name": "Wellue", "homeassistant":
  "2026.10.0"}`. Dylan only wants to support recent HA versions; 2026.10.0 is
  the minimum.
- **Validation in CI:** `.github/workflows/validate.yml` runs HACS's
  `hacs/action` (with `category: integration`) and HA's `hassfest` action on
  every push, every pull request, and once a day. They catch manifest and
  translation mistakes early. The HACS action's `topics` check needs topics set
  on the GitHub repo (Dylan sets those in GitHub's settings).
- **Releases:** HACS installs GitHub Releases. Raise `"version"` in
  `manifest.json`, then publish a release with a matching tag (`v0.1.0`).
  Without any releases, HACS installs the default branch.
- **Brand images:** since HA 2026.3, custom integrations ship their own images
  in `custom_components/wellue_ble/brand/`. This repo has `icon.png`
  (256×256), `icon@2x.png` (512×512), `logo.png` and `logo@2x.png`, all
  transparent PNGs. HA only serves those file names plus `dark_` versions, and
  any missing file falls back to `icon.png`. Guidelines: icon square,
  256×256 (512×512 for `@2x`); logo's shortest side 128–256 px (256–512 for
  `@2x`); trimmed, no empty border; never Home Assistant's own branding. The
  HACS `brands` check looks for `brand/icon.png`. HA only notices a new
  `brand/` folder after a restart.
- **Getting into the default HACS store** is a later step. Until then, users
  add the repo in HACS as a *custom repository*.

## Running it during development

**Dylan tests on his real HA instance.** He develops on a Mac, where getting
Bluetooth into a Docker container is impractical, so there's no local HA core
checkout. His instance has a Bluetooth adapter plus several ESPHome Bluetooth
proxies. To test a change: install through HACS as a custom repository (or copy
`custom_components/wellue_ble` into `/config/custom_components/`) and restart
HA.

**Checking code before Dylan installs it.** Since a mistake costs a restart of
his live instance, check changes locally first. Make a scratch virtual
environment with `uv` (HA 2026.10 needs Python 3.14.2 or newer, and `uv` can
download one: `uv venv --python-preference only-managed --python ">=3.14.2"`),
then install `homeassistant==2026.10.0` and `wellue-ble` into it. Importing
`homeassistant.components.bluetooth` also needs the pinned requirements of HA's
`bluetooth`, `usb` and `hassio` components (listed in each component's
`manifest.json` inside the installed package). Then:

- import the integration's modules against that HA;
- run `ruff check` and `ruff format` with HA core's `pyproject.toml` as the
  config (`--config path/to/core/pyproject.toml`), to match core's style. Add
  `--config "lint.isort.known-third-party = ['wellue_ble']"` to `ruff check`:
  outside a core checkout, ruff otherwise mistakes the library for this
  package (same name) and wants the wrong import order. Imports go standard
  library, then the `wellue_ble` library, then `homeassistant`, then local.
- In 2026.10, look up devices with `async_get_device_by_identifier` (or
  `..._by_connection`); `async_get_device` is deprecated because identifiers
  are no longer unique across config entries.

`hassfest` itself runs in CI on every push.

HA needs a Bluetooth adapter or an ESPHome Bluetooth proxy within range of the
oximeter. To see the integration's and library's debug logs, add this to
`configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.wellue_ble: debug
    wellue_ble: debug
```

> **Gotcha: one connection at a time.** Dylan's existing ESPHome setup
> connects to the oximeter directly. While it's connected, HA can't connect
> (and neither can the ViHealth app). Turn its "Monitoring Enabled" switch off,
> or power it down, before testing the integration. If that ESP32 is reused as
> a Bluetooth proxy, remove its `ble_client` config first. Proxies also have a
> small number of connection slots (3 by default), and this integration keeps
> one busy all the time.

## The developer

Dylan is new to Python and wants to understand everything, not "vibe code".

- **Comments:** extremely well commented, self-documenting code with verbose,
  human-readable names.
- **Simplicity:** the simplest standard HA pattern is better than a clever
  one. Explain HA concepts when you introduce them: config entries, the
  coordinator, `bluetooth` callbacks, `unique_id`, and so on.
- **Tests:** none yet. Testing and extra complexity come later.
- **Pace:** for a new chunk of work, ask a few clarifying questions before
  writing code.
- **Git:** leave committing to Dylan, and work on `main` for now.

## Installing the library during development

`wellue-ble` is published on PyPI (<https://pypi.org/project/wellue-ble/>).
`manifest.json` lists it as `"requirements": ["wellue-ble==1.0.0"]`, and HA
installs it automatically from PyPI when the integration loads. Nothing else
is needed just to use the library.

**Changing the library at the same time.** On Dylan's real instance, the
integration only gets new library code once a new library version is released
to PyPI and `manifest.json` pins it. With an HA core checkout (which Dylan
doesn't use right now), you could instead install a local copy editable into
the virtual environment HA runs from:

```console
git clone https://github.com/DylanSallee/wellue-ble ../wellue-ble
pip install -e ../wellue-ble
```

HA only installs a requirement when the installed version doesn't satisfy it,
so the local copy is used. If HA tries to reinstall it anyway, start it with
`hass --skip-pip`. Changes to the library take effect after an HA restart.

When the library change is done, release a new library version, then raise
the version in `manifest.json` to match. Users only get the new library code
once `manifest.json` asks for the new version.

**Releasing the library:** raise `version` in the library's `pyproject.toml`,
commit and push, then publish a GitHub Release with a matching tag (`v0.1.2`).
A GitHub Actions workflow builds it and uploads to TestPyPI, then PyPI. Pin
the exact version (`==`) in `manifest.json`; HA core requires exact pins.

The library has a CLI for checking the device without HA:
`python -m wellue_ble scan | info ADDRESS | monitor ADDRESS`.

## Library API (wellue-ble 1.0.0)

```python
from wellue_ble import (
    WellueCheckmeO2, SensorReading, DeviceInfo, ChargingState,
    WellueError, WellueConnectionError, WellueResponseTimeoutError, WellueProtocolError,
)

device = WellueCheckmeO2(ble_device, disconnected_callback=callback)  # ble_device: bleak BLEDevice
device.set_ble_device(new_ble_device)   # call when HA sees a better route/proxy
await device.get_device_info()          # -> DeviceInfo
await device.read_sensors()             # -> SensorReading (connects automatically if needed)
await device.disconnect()               # frees the device for the official ViHealth app
device.is_connected, device.address, device.name
```

How the library behaves:

- **Connecting:** it connects through `bleak-retry-connector`
  (`establish_connection` + `BleakClientWithServiceCache`), so it works with
  HA's adapters and Bluetooth proxies.
- **Persistent connection:** the connection stays open between commands, and
  the next command reconnects if it dropped.
- **No push data:** the device never sends readings on its own. Each value must
  be requested, one command at a time.
- **Errors:** every error the library raises on purpose subclasses
  `WellueError`.

`SensorReading` fields:

- `oxygen_saturation_percent: int | None`
- `heart_rate_bpm: int | None`
- `perfusion_index_percent: float | None` (already divided by 10, e.g. `2.3`)
- `motion: int | None` (unitless)
- `battery_level_percent: int`
- `charging_state: ChargingState | None` (`NOT_CHARGING=0`, `CHARGING=1`,
  `FULLY_CHARGED=2`)
- `is_charging` (property)
- `finger_detected: bool`
- `reading_is_valid: bool`
- `raw_payload: bytes`

The library marks a reading invalid when there's no finger, SpO2 is outside
50–100, or heart rate is outside 30–250. When the reading is invalid, all four
health values are `None`. The library also ignores the finger flag while the
device is charging, because the firmware falsely reports a finger while docked.

> **Gotcha:** `ChargingState.NOT_CHARGING == 0` is falsy. Always compare
> with `is None`, never `if reading.charging_state:`.

`DeviceInfo` fields:

- **Identity:** `serial_number`, `model`, `firmware_version`,
  `hardware_version`, `bootloader_version`, `protocol_version`,
  `file_format_version`, `branch_code`, `region`
- **Current settings (read only for now):** `oxygen_alert_enabled`,
  `oxygen_alert_threshold_percent`, `heart_rate_alert_enabled`,
  `heart_rate_alert_high_bpm`, `heart_rate_alert_low_bpm`, `buzzer_volume`,
  `vibration_intensity`, `screen_mode` (raw `LightingMode`)
- **`raw_json`:** every key the device sent

## Decisions already made

- **Minimum HA version:** 2026.10.0. Follow that version's core conventions:
  - Forms use **`probatio`**, not `voluptuous`. Core bans `voluptuous` ("use
    probatio instead"); the API is the same (`probatio.Schema`,
    `probatio.Required`, `probatio.In`). Don't alias it as `vol`.
  - Mark methods that override a parent class method with `@override` (from
    `typing`).
  - Don't add `from __future__ import annotations`; HA bans it as unneeded.
- **Connection:** keep a persistent connection and poll every **1 second**.
  Dylan tested this rate thoroughly with ESPHome, and the battery impact is
  acceptable. Dylan's priorities: connection stability, and reconnecting as
  soon as possible. How `coordinator.py` does it:
  - If not connected and HA can't currently hear the device
    (`async_ble_device_from_address` returns `None`), fail the update right
    away (`UpdateFailed`) instead of trying to connect. That way an absent
    device doesn't keep a proxy connection slot busy.
  - The coordinator keeps polling every second after failures, so it
    reconnects within a second of HA hearing the device again. A "refresh when
    it advertises" trigger was considered and left out: it would save under a
    second.
  - The `bluetooth.async_register_callback` callback passes each new
    `BLEDevice` to `device.set_ble_device()`, so reconnects use the best
    adapter or proxy.
  - A `WellueResponseTimeoutError` (connected, but no answer in 5 s) drops
    the connection, so the next poll reconnects fresh instead of reusing a
    stuck one. Other errors leave the connection alone.
  - Disconnect on unload and on `EVENT_HOMEASSISTANT_STOP` (HA doesn't unload
    entries on shutdown), so the ViHealth app can connect straight away.
  - If HA starts while the device is away, setup raises `ConfigEntryNotReady`.
    HA retries with growing waits (up to 10 minutes), but also retries at once
    when Bluetooth discovery hears the device, because the config flow's
    `_abort_if_unique_id_configured()` reloads entries in "setup retry".
- **Unavailable, never Unknown:**
  - Monitoring switch off, lost connection or failed update: **all** entities
    are **Unavailable**. With a coordinator, raising `UpdateFailed` does this
    automatically.
  - Invalid reading (the library returns `None`; e.g. no finger): the four
    health sensors (SpO2, heart rate, perfusion index, motion) are
    **Unavailable**. Battery, charging, finger present and reading valid stay
    available, since they're still meaningful.
- **Recorder history:** no `force_update`. HA then writes a history row only
  when a value changes, which is still a complete record: each row holds until
  the next one, and gaps show as Unavailable. Dylan used `force_update` in
  ESPHome to prove the oximeter was still reading and to keep a record for
  medical reports. Here, an entity that isn't Unavailable already proves it's
  connected and reading. Note for medical records: HA keeps raw history for 10
  days by default (`recorder: purge_keep_days`). Long-term statistics
  (5-minute and hourly mean/min/max) are kept forever.
- **Unit conversion** happens in the library, not the integration.
- **Monitoring switch:** add a `switch` entity (entity category `config`).
  - **Off:** stop polling and call `device.disconnect()`, so Dylan can use the
    official ViHealth app.
  - **On:** resume polling.
  - **Remembers its state across HA restarts.** This differs from ESPHome's
    `ALWAYS_ON`: a restart shouldn't take the device back while Dylan is
    using the app.
  - This mirrors the "Monitoring Enabled" switch in the ESPHome setup.
- **Naming:** the config entry title and device name are a friendly name built
  from the advertised name: `O2M 2693` → `Checkme O2 Max 2693`, `Band-WU 1234`
  → `Checkme O2 Ultra 1234`. An unrecognized prefix keeps the advertised name
  unchanged, since other Wellue models might work too. The prefix → model
  table is `MODEL_NAME_BY_ADVERTISED_NAME_PREFIX` in `const.py`. Keep it in
  sync with the `bluetooth` matchers in `manifest.json`.
- **Device info** fills HA's device registry: `serial_number`, `model`
  (friendly model name from the prefix when recognized), `model_id` (the
  device's code, `1642`), `hw_version`, manufacturer "Wellue". **No
  `sw_version`**: the device reports firmware `0.0.0` but the app shows
  `1.0.0.0`, so leave it blank until the real source is found. The coordinator
  fetches it again after **every** (re)connect and calls
  `async_get_or_create` (creates the device page, then updates it), so
  settings changed in the ViHealth app show up when monitoring resumes.
  Entities attach to the page with just `identifiers`.
- **Entity names:** sentence case, like HA core ("Heart rate", not "Heart
  Rate"). Names: SpO2, Heart rate, Perfusion index, Motion, Battery, Finger
  present, Charging, Reading valid. Battery and Charging have no
  `translation_key`; HA names them from their device class.
- **Charging:** one binary sensor, on only while actively charging, off once
  fully charged (same as ESPHome). No separate 3-state sensor.

## Device facts from real hardware

- **Advertised names:**
  - Max: `O2M ####`
  - Ultra: `Band-WU ####`
  - The four digits are the last digits of the serial number.
- **The Ultra doesn't advertise the Wellue service UUID.** The manifest's
  `bluetooth` matchers therefore need to use `local_name`, e.g.
  `{"local_name": "O2M*"}` and `{"local_name": "Band-WU*"}`. The device must
  also be `connectable`.
- **Model code:** both models report `Model: "1642"`, so the model code can't
  tell them apart.
  - To tell them apart, use the advertised name prefix, or the serial number
    prefix (Max `2507…`, Ultra `2642…`).
  - The integration's friendly names come from the name prefix (see "Naming"
    under "Decisions already made").
- **One connection at a time:** while HA is connected, the official app can't
  connect.
- **Other GATT services on the device:**
  - Standard Heart Rate (`180D`) and Battery (`180F`): not needed, since
    polling covers both.
  - Nordic DFU (`FE59`): **never touch**.
  - An undocumented proprietary service, `e8fb0001-a14b-98f9-831b-4e2941d01248`.

## Milestone 1 (match the existing ESPHome setup)

Built in three steps, each tested on Dylan's instance before the next:

- **Step A** (done; tested on Dylan's instance 2026-11-05): repo skeleton,
  `manifest.json`, `hacs.json`, CI, the config flow, and a setup that only
  checks HA can hear the device. Items 1–2 below.
- **Step B** (written 2026-11-05; not yet tested on hardware): coordinator,
  sensors and binary sensors. Items 3–5.
- **Step C:** monitoring switch and diagnostic sensors. Items 6–7.

1. **`manifest.json`:**
   - `"domain": "wellue_ble"`
   - `"config_flow": true`
   - `"dependencies": ["bluetooth_adapters"]`
   - `"iot_class": "local_polling"`
   - `"integration_type": "device"`
   - the `bluetooth` matchers above
   - `"requirements"`
2. **Config flow:** support Bluetooth discovery (`async_step_bluetooth` →
   confirm), plus a manual step that lists discovered devices (`async_step_user`).
   Use the address as `unique_id`.
3. **Coordinator:** a `DataUpdateCoordinator` with a 1 second interval.
   - Get the `BLEDevice` with
     `bluetooth.async_ble_device_from_address(hass, address, connectable=True)`.
   - Call `device.read_sensors()` on each update. Turn any `WellueError` into
     `UpdateFailed`.
   - Fetch `get_device_info()` after every (re)connect.
   - Register a `bluetooth.async_register_callback` that calls
     `device.set_ble_device()` (see "Connection" above).
   - Disconnect on unload.
   - The 1 second interval may draw pushback in a core review. Decide then.
     Keep it simple for now.
4. **`sensor` entities:**
   - SpO2: `%`, state class `measurement`. HA has no SpO2 device class.
   - Heart rate: `bpm`.
   - Perfusion index: `%`.
   - Motion.
   - Battery: device class `battery`.
5. **`binary_sensor` entities:**
   - Finger present: device class `occupancy` (shows Detected/Clear).
   - Charging: device class `battery_charging`.
   - Reading valid.
6. **`switch`:** the monitoring switch.
7. **Diagnostic entities:** the alert switches, thresholds and intensities
   from `DeviceInfo`, shown as read-only sensors. They become editable
   `number`/`select` entities in a later milestone.

**ESPHome entities deliberately left out:** Connected (Unavailable already
shows it), Signal Strength (the library doesn't provide it, and HA's
advertisement signal goes stale while connected), Reading Count and Last Seen
(HA tracks when each entity last updated). The identity values (serial number,
model, firmware, etc.) go in the device registry, not separate sensors.

## Open questions and later milestones

- **Firmware version:** the app shows `1.0.0.0`, but the device-info JSON says
  `SoftwareVer: "0.0.0"`, and the standard Device Information service only has
  a manufacturer name. The likely source is the `e8fb…` service. This is
  low priority.
- **Changing settings (library milestone 2):** this uses command `0x16`, which
  takes a JSON payload and is untested. Settings to cover:
  - SpO2 and heart rate alert thresholds and switches
  - buzzer volume and vibration intensity
  - screen mode (`LightingMode`?)
  - storage interval (1 s or 4 s), which has **no key** in the device-info JSON
  
  Dylan has an nRF52840 sniffer. The plan is to capture the ViHealth app while
  it changes each setting, instead of guessing the keys.
- **Recordings:** the device-info JSON has a `FileList` of recorded sessions,
  which could be downloaded later. For medical reports these may be a better
  source than HA's history, since the device records even when HA isn't
  connected.
- **Unmapped keys:** `CurBAT`, `CurTIME`, `CurState`, `CurMode`, `CurPedtar`.

## Reference material

The library repo's `ai-agent-context/` folder (on Dylan's Mac, next to this
repo at `../wellue-ble/ai-agent-context/`) holds the following. It's
gitignored, so it isn't on GitHub; copy it over if needed.

- Dylan's working **ESPHome config**, which shows the entity set and behavior
  to replicate.
- Reference protocol projects. **o2r is GPL-3.0: use it as reference only and
  never copy its code.**
