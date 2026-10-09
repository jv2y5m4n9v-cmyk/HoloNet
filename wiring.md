# Shelly 1 Gen4 lamp wiring

This guide is for one ordinary **110–240 V AC lamp** controlled by a Shelly 1 Gen4, model **S4SW-001X16EU**, with HoloNet/Zigbee2MQTT. It assumes a permanent live and neutral are available at the Shelly. The device requires both **L** and **N** for its own power.

> **Mains-voltage work:** Isolate the circuit at the breaker and verify it is de-energized before touching conductors. If you are not qualified to identify and wire mains conductors, have an electrician install it. Do not rely on wire color alone to identify live or neutral.

## Wiring diagram

```text
                  Shelly 1 Gen4 (AC supply)                 Lamp
                ┌──────────────────────────┐
Mains live (L) ─┼─────────────────────────►│ L
                ├──── short jumper ───────►│ I ──[relay]── O├──────► Lamp live (L)
                └──── wall switch ────────►│ SW
                │                          │
Mains neutral ──┼─────────────────────────►│ N
                └─────────────────────────────────────────────────► Lamp neutral (N)

Protective earth (PE) ────────────────────────────────────────────► Lamp PE, if required
                └──────────────────────────┘

12V terminal: leave unused for this AC wiring.
```

The **I–O contacts are a dry relay contact**. For this mains-lamp arrangement, the jumper feeds live from **L** to relay input **I**; the relay then switches it from **I** to **O** and onward to the lamp. The Shelly has no protective-earth terminal—continue PE directly to the lamp/fixture where required.

## Connections

1. Connect the supply **neutral** to Shelly **N** and to the lamp’s neutral.
2. Connect the permanent supply **live** to Shelly **L**.
3. Add a short insulated jumper from Shelly **L** to **I**.
4. Connect Shelly **O** to the lamp’s live conductor.
5. If using a conventional wall switch, connect it between **L** and **SW**. If there is no wall switch, leave **SW** unused.
6. Continue protective earth directly to the lamp if its fixture requires PE. Do not connect PE to the Shelly.

Use the device terminals and conductor sizes/strip length specified in the [Shelly 1 Gen4 technical documentation](https://kb.shelly.cloud/knowledge-base/shelly-1-gen4). Stay within the ratings of the Shelly, lamp, circuit wiring, and circuit protection; the relay rating is not a substitute for the rating of the installed wiring.

## Connect it to HoloNet

1. Restore power after the wiring has been safely checked.
2. Update the Shelly firmware while it is still connected to Wi-Fi.
3. In the Shelly’s local web interface, choose **Settings → Device settings → Switch to Zigbee**. The Shelly starts in Matter mode by default. The device’s control button can also be pressed five times to switch to Zigbee and open a pairing window.
4. Open HoloNet’s Zigbee2MQTT dashboard at <http://127.0.0.1:8080> and select **Permit join**.
5. In the Shelly web interface, open **Settings → Zigbee → Start pairing** if offered. Follow the [Zigbee2MQTT model-specific instructions](https://www.zigbee2mqtt.io/devices/S4SW-001X16EU.html) if its status does not become **Joined**.
6. When **Shelly S4SW-001X16EU** appears in Zigbee2MQTT, use its switch control to test the lamp. If a physical wall switch is connected, select `toggle` for a maintained rocker switch or `momentary` for a pushbutton in the device’s `switch_type` setting.

The Zigbee2MQTT computer and coordinator must remain running for app-based control. The Shelly’s wired wall switch can still operate its relay locally.

## Sources

- [Shelly 1 Gen4 technical documentation and wiring diagram](https://kb.shelly.cloud/knowledge-base/shelly-1-gen4)
- [Shelly 1 Gen4 local web-interface guide](https://kb.shelly.cloud/knowledge-base/shelly-1-gen4-web-interface-guide)
- [Zigbee2MQTT support and pairing notes for S4SW-001X16EU](https://www.zigbee2mqtt.io/devices/S4SW-001X16EU.html)
