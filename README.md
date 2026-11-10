# DESS Monitor Local — Anenji / SMG-II fork

> **Anenji fork** — based on upstream `v1.1.0-beta.3`, hardened for
> Anenji / EASUN / ISolar **SMG-II** inverters reached through an
> Eybond/SmartESS Wi-Fi dongle (or plain Modbus TCP).
>
> Fork: <https://github.com/jul-ienfr/home-assistant-dess-monitor-local>
> Upstream: <https://github.com/Antoxa1081/home-assistant-dess-monitor-local>
>
> **Repository layout**: the default branch is `archive/dess-monitor-local`
> and contains this integration (`hacs.json`, `custom_components/`). The
> `main` branch contains the Anenji ESPHome firmware, not this integration.
> Marketplace metadata and release rules:
> <https://github.com/jul-ienfr/home-assistant-dess-monitor-local/blob/main/MARKETPLACE.md>

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

## Installation

### Marketplace (recommended, Home Assistant 2026.11+)

HACS is built into Home Assistant 2026.11 as the **Marketplace**. The old
“Get HACS” add-on is obsolete and should be removed.

1. Open **Settings → Marketplace**.
2. In the upper-right corner, select **Add from link**.
3. Enter
   `https://github.com/jul-ienfr/home-assistant-dess-monitor-local` and add
   it. Choose **Integration** if the type is requested.
4. Open the repository, select **Install**, and choose the version
   `v1.1.0-beta.3-anenji.3`.
5. The integration has a config flow and loads immediately. If a restart is
   requested, restart Home Assistant, then add it under
   **Settings → Devices & services**.

The Marketplace installs the latest **published GitHub release**, not a bare
tag. The version in `manifest.json` must match the tag without its `v` prefix.
The repository's
default branch (`archive/dess-monitor-local`) contains `hacs.json` and
`custom_components/`, so the Marketplace can resolve the repository directly.
Future releases must be published on that branch; see
[`MARKETPLACE.md`](https://github.com/jul-ienfr/home-assistant-dess-monitor-local/blob/main/MARKETPLACE.md).

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
polling. In particular, do not run it alongside the ESPHome `Anenji 4000w
Master` node on the same inverter COM port. Use the `eybond` transport of the
Wi-Fi dongle or the Eybond hub, or disable the other master first.

## Configuration

The setup wizard asks for a hub name, protocol, transport, and connection
settings. Everything can be changed later via **Configure** in the
integration card.

| Protocol | What it is | Transports |
| --- | --- | --- |
| `voltronic` | Voltronic / Axpert PI30 | `tcp_elfin`, `serial`, `eybond` |
| `pi18` | PI18 / InfiniSolar-V | `tcp`, `serial` |
| `modbus` | Modbus RTU (SMG-II) | `tcp`, `eybond-modbus` |
| `agent` | Local [`solar-system-agent`] HTTP API | `agent_http` |

Common option for all protocols:

- **Update interval** — how often Home Assistant polls the device, `1`–`300` s
  (default `10`).

For SMG-II through an Eybond hub, enable the child and assign the `modbus`
protocol in the hub's discovered-device options. The hub creates the
`eybond-modbus://` URI automatically; the `devaddr` is the Modbus unit ID
(usually `1`).

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

## Optional patch for upstream

`patches/dess-monitor-local-beta3-anenji.patch` is the minimal compatibility
patch for staying on upstream `v1.1.0-beta.3` (full 18-character PN + SUB).
This fork already includes it and does not need the patch. See
[`patches/README.md`](patches/README.md) for instructions.

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
until upstream clarifies. The optional patch is provided for interoperability
with the same upstream code.
