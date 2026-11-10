# Changelog

## 1.1.0-beta.4-anenji.1 — 2026-11-10

### Added

- **The integration now follows the Home Assistant UI language (English and
  French bundled).** Entity names, configuration/options flows, the select
  descriptions and the SMG-II warning/fault text are translated. Other
  languages fall back to English automatically. Dynamic state text lives in
  `smg2_faults.py`; entity names live in `translations/en.json` and
  `translations/fr.json`.
- **SMG-II warning and fault codes are decoded instead of shown as hex.**
  Warning `0x40` (`0x00000040`) is bit 6 of the warning DWORD: *PV low
  voltage*. It is normal at night or in deep shade; it only needs wiring
  checks if it persists in daylight. The fault-summary sensor now exposes
  `active_warnings` / `warning_keys` / `warning_advice` (and the fault
  equivalents), a dedicated **Fault and warning advice** sensor states what
  to do, and the same readable labels are available on the any-warning
  binary sensor.
- **Charge source priority now offers "Solar only" (`PCP03`).** SMG-II
  register 331 value 3 was readable but not writable before.
- **Every writable SMG-II setting is now available in Home Assistant.**
  Modbus entries expose selects (input voltage range, buzzer, LCD
  backlight, output voltage/frequency, battery type, turn-on mode),
  switches (LCD auto home, energy saving, overload/over-temperature
  restart, overload bypass, battery equalization, remote output) and
  numbers (battery OVP, bulk/float/recovery/cut-off voltages, max charge
  current, equalization voltage/time/timeout/interval, SOC thresholds).
  A diagnostic **Configuration incoherent** sensor flags invalid
  threshold combinations. The optional ESPHome web UI is no longer needed
  for daily operation.

### Changed

- **Output and charge source priorities use explicit labels and
  descriptions.** `UtilityFirst` / `SBU` / `Solar` / `SUB` become
  *Grid first*, *SBU (battery before grid)*, *Solar first*,
  *SUB (grid before battery)*, with a one-line explanation exposed as the
  `description` attribute. The machine-readable value stays in
  `raw_value`; existing `SolarFirst` readbacks are normalised to `Solar`.
- **Entity names now use Home Assistant's entity-name translations**
  (`has_entity_name` + `translation_key`). Existing entity IDs and
  history are preserved by the registry; new installations get the
  device name plus the translated entity name.

### Fixed

- **Utility charging current can no longer be set to 110 A or 120 A.**
  The 4.2 kW SMG-II rates register 333 at 80 A, not 100 A. The select now
  caps its options at 80 A, or lower when register 332 reports a lower
  total charge limit, and exposes the cap as `max_allowed_amps`.
- **Single-device Modbus over an EyBond dongle now polls the inverter.**
  Selecting protocol `modbus` and transport `eybond` in the device wizard
  used to store `modbus://0.0.0.0:8899` and open a Modbus TCP client against
  the listener itself. The wizard now builds
  `eybond-modbus://0.0.0.0:8899/<devaddr>?broadcast=…&announce=…`, the URI
  the Eybond adapter already supported. The options flow also recovers the
  protocol/transport correctly when editing such an entry.

### Documentation

- Everything now lives on `main`, including `hacs.json` and
  `custom_components/`, so the Home Assistant 2026.11 Marketplace (formerly
  HACS) can install the integration from the default branch or a release.
- Installation instructions updated for **Settings → Marketplace → Add from
  link**; the legacy HACS path is kept for Home Assistant versions before
  2026.11.
- Added the single-Modbus-master warning: do not use the `serial`/`modbus`
  transport while ESPHome is polling the same inverter port.

## 1.1.0-beta.3-anenji.3 — 2026-11-10

### Fixed

- **vSoC setup no longer fails when the float-deadband controls are not in the
  registry yet.** The estimator reads those controls through the existing
  null-safe state helper, so entity creation cannot raise
  `AttributeError: 'NoneType' object has no attribute 'lower'`.
- **Clean unload with an in-flight first poll.** The initial refresh task is
  cancelled and awaited before the endpoint command queues are drained; a poll
  waking up mid-unload can no longer create a fresh queue and leave a worker
  task behind.

### Tests

- The full suite (383 tests, including the Home Assistant lifecycle tests)
  passes against Home Assistant 2026.10.4.

## 1.1.0-beta.3-anenji.2 — 2026-11-10

### Fixed

- **Startup is no longer blocked by the first inverter poll.** The direct
  coordinator resolves its targets synchronously and the initial refresh runs
  as a config-entry background task; entities are created immediately.
- **Modbus snapshot cache** is stamped after the read, so a slow dongle read
  is not immediately expired, and a failed read is cached for only 0.2 s so
  the coordinator retry can reach the inverter.
- **Real SMG-II values**: battery SOC from register 229, output apparent power
  from register 214, and signed battery power from register 217.
- **QMOD / QPIWS / QFWS emulation** for SMG-II, so operating mode, fault
  summary and the aggregate warning sensor have data.
- **NAK and error handling**: rejected commands no longer count as successful
  reads. Expected unsupported replies for optional commands are still treated
  as clean empty sections.
- **Exit Fault State** goes through `ModbusAdapter`, so it works for both
  `modbus://` and `eybond-modbus://` transports.
- **vSoC controls** are resolved through the entity registry by unique ID and
  re-resolved on registry changes; renaming a control no longer breaks the
  SoC estimator.
- **Select writes** update optimistically, force a QPIRI refresh on the next
  cycle, and leave the old value in place when the write fails.
- **`DirectDeviceStatusSensor`** no longer falls through to `"OK"` after
  setting a real status.
- **`DirectLoadPercentSensor`** no longer uses `POWER_FACTOR` as its device
  class; apparent power uses VA instead of W.

### Changed

- SMG-II/Modbus entries no longer create entities for fields the inverter
  does not report: bus voltage, SCC battery voltage, status bits, EEPROM
  version, PV2 sensors/energy, and fabricated QPIRI rated/parallel values.
- Typed sensors expose `stale` and `stale_cycles` attributes.
- HACS metadata now points at this fork, requires Home Assistant 2024.6.0,
  and the HACS validation job is enabled.

### Tests

- Added Modbus coverage for SOC, apparent power, battery power, QMOD, QPIWS,
  QFWS, SUB writes and the post-read snapshot cache.
- Added Eybond 18-character PN framing coverage.
- Added pure tests for the coordinator rejection policy.

## 1.1.0-beta.3-anenji.1

- Initial Anenji fork of upstream `v1.1.0-beta.3`.
- Full 18-character Eybond dongle PN.
- SUB output priority (`register 301 = 3`) in the QPIRI projection, select
  options and Modbus write path.
