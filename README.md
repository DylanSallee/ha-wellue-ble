# Wellue Checkme O2 for Home Assistant

A Home Assistant integration for **Wellue Checkme O2** wrist pulse oximeters
(the Checkme O2 Max and Checkme O2 Ultra). It connects over Bluetooth, directly
or through an ESPHome Bluetooth proxy, using the
[`wellue-ble`](https://github.com/DylanSallee/wellue-ble) library.

> **Not a medical device.** This is an unofficial hobby project that isn't
> affiliated with Wellue or Viatom. Don't rely on it for medical decisions or
> alarms.

## Status

Early development. Version 0.1.0 can discover the oximeter and add it to Home
Assistant, but doesn't show any readings yet.

Planned for the first full release: blood oxygen (SpO2), heart rate, perfusion
index, motion, battery level, charging and finger detection, plus a switch to
pause monitoring so the official ViHealth app can connect.

## Requirements

- Home Assistant 2026.10 or newer.
- A Bluetooth adapter on the Home Assistant machine, or an
  [ESPHome Bluetooth proxy](https://esphome.io/components/bluetooth_proxy/),
  within range of the oximeter.
- **The oximeter accepts only one connection at a time.** While Home Assistant
  is connected, the ViHealth app can't connect, and the other way round.

## Installation

### With HACS

1. In HACS, add `https://github.com/DylanSallee/ha-wellue-ble` as a custom
   repository, with the type **Integration**.
2. Download **Wellue Checkme O2**.
3. Restart Home Assistant.

### By hand

Copy the `custom_components/wellue_ble` folder into your Home Assistant
`config/custom_components/` folder, then restart Home Assistant.

## Setup

Turn the oximeter on and close the ViHealth app. Then either:

- wait for Home Assistant to discover it: open **Settings > Devices &
  services** and click **Add** on the discovered "Checkme O2" card; or
- click **Add integration**, choose **Wellue Checkme O2**, and pick the
  oximeter from the list.

## Debug logging

To see what the integration and the library are doing, add this to
`configuration.yaml` and restart:

```yaml
logger:
  default: warning
  logs:
    custom_components.wellue_ble: debug
    wellue_ble: debug
```

## License

Apache License 2.0. See [LICENSE](LICENSE).
