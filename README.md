# Wellue for Home Assistant

A Home Assistant integration for **Wellue Checkme O2** wrist pulse oximeters
(the Checkme O2 Max and Checkme O2 Ultra). It connects over Bluetooth, directly
or through an ESPHome Bluetooth proxy, using the
[`wellue-ble`](https://github.com/DylanSallee/wellue-ble) library.

> **Not a medical device.** This is an unofficial hobby project that isn't
> affiliated with Wellue or Viatom. Don't rely on it for medical decisions or
> alarms.

## What it provides

Home Assistant reads the oximeter once a second over a connection it keeps
open, and shows:

| Entity | Type | Notes |
| --- | --- | --- |
| SpO2 | Sensor, % | Blood oxygen saturation |
| Heart rate | Sensor, bpm | |
| Perfusion index | Sensor, % | Signal strength at the sensor, e.g. 2.3 % |
| Motion | Sensor | Unitless; a higher number means more movement |
| Battery | Sensor, % | |
| Finger present | Binary sensor | Detected / Clear |
| Charging | Binary sensor | On only while charging; off once fully charged |
| Reading valid | Binary sensor | On when SpO2 and heart rate are real measurements |
| Connected | Binary sensor | Connected / Disconnected; never Unavailable |
| Monitoring | Switch | Turn off to free the oximeter for the ViHealth app (see below) |

The four health sensors (SpO2, heart rate, perfusion index and motion) show
**Unavailable** when there's no valid reading, e.g. with no finger on the
sensor. Every entity except Connected and Monitoring shows Unavailable while
Home Assistant can't reach the oximeter; Connected shows **Disconnected**, which
makes it handy for dashboard conditions.

The device page shows the serial number, model and hardware version, and,
under **Diagnostic**, the oximeter's own settings (read-only for now): SpO2
alert and its threshold, heart rate alert and its high and low limits, buzzer
volume and vibration intensity. They're re-read each time Home Assistant
reconnects.

## Using the ViHealth app

The oximeter accepts only one connection at a time. To use the official
ViHealth app (for example, to change a setting or download a recording):

1. Turn the oximeter's **Monitoring** switch off. Home Assistant disconnects,
   and its entities show Unavailable.
2. Use the app, then close it, or turn off your phone's Bluetooth.
3. Turn **Monitoring** back on. Home Assistant reconnects within a few seconds.

The switch remembers its state across Home Assistant restarts, so a restart
won't take the oximeter back while you're using the app.

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
2. Download **Wellue**.
3. Restart Home Assistant.

### By hand

Copy the `custom_components/wellue_ble` folder into your Home Assistant
`config/custom_components/` folder, then restart Home Assistant.

## Setup

Turn the oximeter on and close the ViHealth app. Then either:

- wait for Home Assistant to discover it: open **Settings > Devices &
  services** and click **Add** on the discovered "Checkme O2" card; or
- click **Add integration**, choose **Wellue**, and pick the
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
