# DESS Monitor Local — Anenji / SMG-II fork

> **Anenji fork** — based on upstream `v1.1.0-beta.3`, hardened for
> Anenji / EASUN / ISolar **SMG-II** inverters reached through an
> Eybond/SmartESS Wi-Fi dongle (or plain Modbus TCP).
>
> Fork: <https://github.com/jul-ienfr/home-assistant-dess-monitor-local>
> Upstream: <https://github.com/Antoxa1081/home-assistant-dess-monitor-local>
>
> **Repository layout**: the `main` branch contains this integration
> (`hacs.json`, `custom_components/`) and its documentation. Marketplace
> metadata and release rules: [`MARKETPLACE.md`](MARKETPLACE.md).

## What this fork changes

### SMG-II / Eybond compatibility

- Reads the **full 18-character** Eybond dongle PN instead of truncating it
  to 14 characters.
- Adds the **SUB** output priority (`register 301 = 3`) to the QPIRI
  projection, the Home Assistant select, and the Modbus write path.
- Emulates **QMOD**, **QPIWS** and **QFWS** from the SMG-II snapshot, so
  operating mode, fault summary and the aggregate warning sensor work.
- Reads the real **battery SOC** (register 229) instead of hard-coding 100 %.
- Reads the real **output apparent power** (register 214) instead of copying
  active power.
- Uses the signed **battery power** from register 217 when present.
- Sends **Exit Fault State** through the Modbus adapter, so it works for both
  `modbus://` and `eybond-modbus://` transports.

### Reliability and data correctness

- **Non-blocking startup**: the first poll runs as a config-entry background
  task instead of delaying Home Assistant startup (and the entry watchdog).
- **Modbus snapshot cache fixes**: the cache is timestamped after the read,
  so a slow dongle read is not "born expired"; a failed read is cached for
  only 0.2 s so the coordinator retry can actually reach the inverter.
- **NAK/error policy**: a NAK or Modbus exception no longer counts as a
  successful read. Expected "unsupported command" replies for optional
  commands (`QPIGS2`, `QFWS`) are still treated as clean empty sections.
- **Optimistic selects**: a successful write updates the select immediately
  and forces a QPIRI refresh on the next cycle, instead of reverting until
  the slow QPIRI cadence comes around.
- Writes that fail now leave the previous select value in place and log a
  warning.
- **vSoC controls are resolved through the entity registry** by unique ID
  instead of guessing entity IDs from the device name. Renaming a control or
  HA prefixing the entity ID no longer silently breaks the SoC estimator.
  Registry changes are watched, so the controls are found after all
  platforms finish loading. The float-deadband lookup is null-safe while
  those platforms are still being created.
- **Clean unload**: the initial poll is cancelled before the command queues
  are drained, so an in-flight poll cannot recreate a queue after unload.
- Every typed sensor exposes `stale` / `stale_cycles` attributes so
  automations can tell frozen data from live data.

### Entities that no longer lie

SMG-II does not report these QPIGS/QPIRI fields. The old projection filled
them with plausible-looking constants; this fork hides the corresponding
entities instead:

- bus voltage (`400 V`), SCC battery voltage (mirrored), device status bits,
  EEPROM version, battery voltage offset;
- PV2 power / voltage / current and the PV2 energy sensor;
- QPIRI rated grid/AC/battery values, battery type, parallel settings and
  reserved fields.

`DirectDeviceStatusSensor` also had a Python fall-through bug that always
ended at `"OK"`; it now reports the actual status, and its entity is hidden
for Modbus because the status bits do not exist there.

`DirectLoadPercentSensor` no longer claims `POWER_FACTOR` as its device
class, and output apparent power now uses the VA unit instead of W.

### Warnings, priorities and languages

The fault-summary sensor decodes the two SMG-II status DWORDs instead of
showing raw hex. Warning `0x40` is *PV low voltage* (normal at night or in
deep shade); each active bit also gets an actionable `warning_advice` or
`fault_advice` attribute, in English or French depending on the Home
Assistant UI language. The any-warning binary sensor exposes the same
stable keys.

The two priority selects are deliberately separate:

- **Output source priority** decides what powers the loads — grid, solar,
  battery, or a combination.
- **Charge source priority** decides what charges the battery — grid,
  solar, both, or solar only.

Their labels are plain language (*Grid first*, *SBU (battery before
grid)*, *Solar first*, *SUB (grid before battery)*) and the `description`
attribute explains the selected mode. The raw firmware value remains in
`raw_value` for automations.

Entity names and both configuration flows follow the Home Assistant
language. English and French are bundled; any other language falls back to
English. Changing the Home Assistant language picks up the new names after
the integration reloads (or after a restart).

Utility charging current is capped at the 4.2 kW SMG-II maximum of **80 A**
(register 333); if the inverter reports a lower total charge limit, that
lower value is offered instead. The applied cap is exposed as
`max_allowed_amps`.

### Full inverter control from Home Assistant

Modbus/SMG-II entries expose the complete writable register set, not just
the telemetry:

- **Selects** — input voltage range (wide/UPS), buzzer mode, LCD
  backlight, output voltage (220/230/240 V), output frequency (50/60 Hz),
  inverter battery type, turn-on mode.
- **Switches** — LCD auto home, energy saving, overload auto restart,
  over-temperature auto restart, overload transfer to bypass, battery
  equalization, remote output enable.
- **Numbers** — battery OVP, bulk/float/recovery/low-cut-off voltages,
  max charge current (the SMG-II total for solar + mains; it must stay at
  or above the max mains current), equalization voltage/time/timeout/
  interval, and the three SOC thresholds (low cut-off, back to utility,
  back to battery). To lower the total below the current mains limit, lower
  the mains limit first.
- **Diagnostic** — *Configuration incoherent* turns on when the battery
  voltage order or SOC order is impossible, or when a current setting
  exceeds the model limit.

Every setting is a normal Home Assistant entity, so it can be dashboarded,
automated, logged, and renamed like the sensors. The integration polls the
SMG-II directly over Modbus or the Eybond dongle. Do not run two Modbus
masters on the same inverter port.

## Installation

### Marketplace (recommended, Home Assistant 2026.11+)

HACS is built into Home Assistant 2026.11 as the **Marketplace**. The old
“Get HACS” add-on is obsolete and should be removed.

1. Open **Settings → Marketplace**.
2. In the upper-right corner, select **Add from link**.
3. Enter
   `https://github.com/jul-ienfr/home-assistant-dess-monitor-local` and add
   it. Choose **Integration** if the type is requested.
4. Open the repository, select **Install**, and choose the latest published
   release. Enable pre-releases in the Marketplace if you want the beta line.
5. The integration has a config flow and loads immediately. If a restart is
   requested, restart Home Assistant, then add it under
   **Settings → Devices & services**.

The Marketplace installs the latest **published GitHub release**, not a bare
tag. The version in `manifest.json` must match the tag without its `v` prefix.
The default branch (`main`) contains `hacs.json` and `custom_components/`, so
the Marketplace can resolve the repository directly. Future releases must be
published on `main`; see [`MARKETPLACE.md`](MARKETPLACE.md).

Requires Home Assistant **2024.6.0** or newer.

### HACS before Home Assistant 2026.11 (legacy)

1. Open **HACS → Integrations → ⋮ → Custom repositories**.
2. Add
   `https://github.com/jul-ienfr/home-assistant-dess-monitor-local` as an
   **Integration**.
3. Install **DESS Monitor Local (Anenji SMG-II)** and restart Home
   Assistant.
4. Add the integration and configure the protocol/transport.

### Manual

Copy `custom_components/dess_monitor_local` into your Home Assistant
`config/custom_components/` directory and restart. The Marketplace is
preferable: it handles updates and the `pyserial-asyncio-fast` requirement.

### Modbus bus conflict

The SMG-II has a single Modbus bus. Do **not** configure this integration with
the `serial` or `modbus` transport on a port that another master is already
polling — another integration, a firmware, or a diagnostic tool. Use the
`eybond` transport of the Wi-Fi dongle or the Eybond hub, or disable the other
master first.

## Configuration

The setup wizard asks for a hub name, protocol, transport, and connection
settings. Everything can be changed later via **Configure** in the
integration card.

| Protocol | What it is | Transports |
| --- | --- | --- |
| `voltronic` | Voltronic / Axpert PI30 | `tcp_elfin`, `serial`, `eybond` |
| `pi18` | PI18 / InfiniSolar-V | `tcp`, `serial` |
| `modbus` | Modbus RTU (SMG-II) | `tcp`, `eybond` |
| `agent` | Local [`solar-system-agent`] HTTP API | `agent_http` |

Common option for all protocols:

- **Update interval** — how often Home Assistant polls the device, `1`–`300` s
  (default `10`). EyBond dongles have a **5 s minimum** because they cycle
  their TCP session every few seconds; faster polls mostly hit connection
  gaps.

For a single SMG-II behind an EyBond dongle, choose protocol `modbus`,
transport `eybond`, bind `0.0.0.0:8899`, and the RS485 address (usually `1`).
The wizard creates the `eybond-modbus://` URI automatically. The `devaddr`
is the Modbus unit ID. Set the broadcast address of the dongle's subnet. Leave
**Announce IP** empty on HAOS/native installations: while a dongle is missing,
the local address is re-checked every 30 s (the first broadcast after a long
pause re-checks immediately), so a DHCP change is picked up without a
restart. Nothing is checked
while every dongle is connected. Set it explicitly only in Docker bridge mode,
where the host LAN IP is not a local interface (and update it yourself if that
host IP changes).

For a direct TCP/Modbus/PI18 inverter, prefer a **DHCP reservation or a local
hostname** (e.g. `inverter.local`) over a raw IP. If the address changes
anyway, editing **Host** in the options keeps the existing entities, unique
IDs and history — the endpoint identity is stored separately.

For several dongles, use an Eybond hub and enable each discovered child with
the `modbus` protocol; the hub adds the dongle PN to every child URI.

For protocol-specific notes and the internal device URI format see the
[upstream configuration wiki](https://github.com/Antoxa1081/home-assistant-dess-monitor-local/wiki).

## Upgrading from `1.1.0-beta.3-anenji.1`

- **Battery SOC** now follows register 229. If the inverter reports an
  implausible value, the sensor shows `unknown` rather than a fabricated
  100 %.
- **Output apparent power** is now in VA. Automations that assumed the old
  active-power copy may need their thresholds adjusted.
- **PV2 and several QPIRI/SMG-II entities are gone** for Modbus entries.
  They never had real data on SMG-II. Their old registry entries may remain
  orphaned; delete them from the entity registry if you want a clean list.
- **vSoC controls** keep their entity IDs. If you renamed one, the estimator
  now follows the registry instead of the old slug guess.
- If an Eybond child was configured with the old 14-character PN, remove
  and re-add it so the full PN becomes the routing key.

## Tests

```bash
python -m pytest -q          # pure, HA-free suite
ruff check .                 # lint
```

The Home Assistant lifecycle tests in `tests/test_setup_hass.py` require
`pytest-homeassistant-custom-component` and run in the Linux CI job. The
pure suite (protocols, Modbus projections, rejection policy, Eybond framing)
runs anywhere Python 3.12+ is available.

## License

The upstream repository does not declare a license. This fork does not add
one unilaterally; treat it as “all rights reserved by the upstream author”
until upstream clarifies.
