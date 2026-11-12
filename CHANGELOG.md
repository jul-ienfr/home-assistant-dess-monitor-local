# Changelog

## 1.1.0-beta.4-anenji.8 — 2026-11-12

### Changed

- **The default refresh interval is now 5 s**, matching the other DESS local
  integrations and the vendor's web monitor. The allowed range is unchanged
  (1–300 s); EyBond dongles keep their 5 s floor.
- **Existing EyBond entries still on the old 10 s default are migrated to
  5 s once.** A deliberate value on another transport, or any other EyBond
  value, is left untouched. The entry version moves to 2 so the migration
  runs exactly once.
- **The Modbus snapshot cache TTL drops from 5 s to 2 s.** With a 5 s poll,
  a 5 s TTL could serve the previous cycle's snapshot to the next one and
  silently halve the effective refresh rate. Two seconds still covers every
  command of one cycle.

### Notes

- Restart Home Assistant after updating so the migration and the new
  interval are applied.
- At 5 s the recorder writes roughly twice as many state rows per hour as at
  10 s. Exclude entities you do not chart from the recorder if the database
  grows too fast.

## 1.1.0-beta.4-anenji.7 — 2026-11-12

### Fixed

- **The *Last live sample* diagnostic sensor no longer errors before the
  first successful poll.** With no QPIGS sample recorded yet, the
  `age_seconds` attribute called `round()` on `None`, which Home Assistant
  logs as an entity error on every state write. It now stays `null` until a
  timestamp exists.
- **The Home Assistant CI job is green again.** Its entity-ID assertions
  still used the pre-translation IDs (`sensor.test_inv_direct_grid_voltage`,
  `number.test_inv_vsoc_battery_capacity_ah`, …); they now match the IDs
  derived from the translated entity names. The energy-guard test also
  expected the wrong trapezoid value (it omitted the division by two).

### Notes

- No other runtime behaviour changed. Restart Home Assistant after
  updating.

## 1.1.0-beta.4-anenji.6 — 2026-11-11

### Changed

- **The repository is now integration-only.** Removed the ESPHome firmware,
  the ESP32 wiring guide, the legacy firmware configurations, the upstream
  compatibility patch, the SpecKit scaffolding and the hardware validation
  specs. The README and the EyBond/Marketplace documentation now describe
  only the Home Assistant integration.
- **All documentation links were checked against the new tree.** The README
  is a Marketplace-ready landing page; `INTEGRATION.md`, `EYBOND_LOCAL.md`,
  `PROTOCOL.md` and `MARKETPLACE.md` no longer reference the removed files.

### Notes

- No integration behaviour changed in this release. It publishes the cleaned
  repository and the rewritten documentation.

## 1.1.0-beta.4-anenji.5 — 2026-11-11

### Added

- **A new diagnostic sensor, *Last live sample* / *Dernier échantillon
  live*, exposes the wall-clock time of the last successful QPIGS read.**
  Its `age_seconds` attribute keeps growing while the dongle is silent,
  and `stale` / `stale_cycles` mirror the QPIGS failure counter. This makes
  a dongle that stopped answering visible before every entity flips
  unavailable.
- **Inverter endpoint identity is now stable across an IP or hostname
  change.** Single-device entries persist the original endpoint as
  `device_id`; editing the host in the options keeps the same entity
  unique IDs, HA device and history. Legacy entries adopt their current
  URI as the stable ID on the first save.
- **The host field now documents the resilient setup:** use a DHCP
  reservation or a local hostname (e.g. `inverter.local`) so an inverter
  IP change is resolved automatically.

### Fixed

- **The EyBond announcer no longer caches Home Assistant's IP forever.**
  When `Announce IP` is left empty, the local address is re-checked every
  30 s while a dongle is missing; the first broadcast after a longer pause
  re-checks immediately. If a DHCP lease change moves Home Assistant to a new address
  (and subnet), the next `set>server` payload and UDP broadcast target are
  updated automatically, so dongles can reconnect without a Home
  Assistant restart. Nothing is checked while every dongle is connected:
  a healthy system is left alone. An explicit announce IP is still used
  verbatim for Docker bridge setups.
- **Energy accumulators no longer bridge a data outage.** A trapezoidal
  step is skipped when the source section is stale (for example QPIGS
  failed while QPIRI was read) or when the elapsed gap exceeds
  `max(5 × poll interval, 60 s)`. The integrator restarts from a fresh
  sample after recovery instead of counting energy the inverter never
  reported.
- **Update intervals are clamped and EyBond now has a 5 s floor.** Values
  below 1 s or above 300 s are rejected/clamped in the coordinator and all
  configuration flows. EyBond dongles cycle their TCP session every few
  seconds, so a 1 s poll mostly hit connection gaps; the effective
  interval is now at least 5 s (the stored option is raised on the next
  save). The coordinator also reports the stored and effective intervals
  in diagnostics.

### Notes

- Existing entity IDs and unique IDs are unchanged. A legacy EyBond entry
  configured at 1 s runs at 5 s immediately and stores 5 s the next time
  its options are saved.
- Restart Home Assistant after installing this release so the new sensor
  and coordinator/announcer code are loaded.

## 1.1.0-beta.4-anenji.4 — 2026-11-11

### Fixed

- **The register-333 select now refreshes its options as soon as register
  332 changes, and register 332 exposes the new minimum as soon as register
  333 changes.** The two settings are coupled (the mains current cannot
  exceed the total current, and the total cannot be set below the mains
  current), but the entities only recomputed that coupling on the next
  full QPIRI poll — up to two minutes. A write sequence such as
  `332=100` then `333=80` could fail with
  `Option 80 is not valid ... valid options are: 2, 10, 20`. The
  coordinator now keeps an optimistic override of the written QPIRI value
  until a fresh poll confirms it, so the options update immediately even
  when a poll started before the write is still in flight.

### Notes

- No entity or service change; existing automations keep working
  unchanged.
- Restart Home Assistant after installing this release so the coordinator
  code is reloaded.

## 1.1.0-beta.4-anenji.3 — 2026-11-10

### Changed

- **The maximum charging current control is now explicitly the total
  solar + mains limit, and it can no longer be set below the max mains
  charging current.** The SMG-II manual defines program 02 as
  `max charging current = utility charging current + solar charging current`
  and the firmware rejects a total lower than program 11 (register 333).
  The number entity is renamed *Max charging current (solar + mains)* /
  *Courant de charge max (solaire + réseau)*, and its slider minimum follows
  the current mains limit. To lower the total/solar charge cap to 60 A,
  first lower the max mains charging current to 60 A or less, then set the
  total to 60 A. The configuration-coherence sensor now also flags a total
  lower than the mains limit.

### Notes

- Restart Home Assistant after installing this release so the renamed
  entity and the new dynamic minimum are loaded.

## 1.1.0-beta.4-anenji.2 — 2026-11-10

### Fixed

- **The Eybond dongle now recovers from a half-open TCP session.** After a
  Home Assistant reload or restart, a dongle connection can stay open at the
  TCP level while no frame comes back. Writes keep succeeding, so the
  heartbeat task sees no error and the announcer stays paused because the
  manager still counts the dongle as connected. Polling then times out
  forever until Home Assistant is restarted. The manager now drops any
  session that has received no frame for 90 seconds, which clears the
  connected set and lets the existing announce loop bring the dongle back
  automatically.

### Notes

- Restart Home Assistant after installing this release. Copying the files
  alone leaves the previously imported module in memory, so new entities and
  fixes only take effect after a restart.

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
  threshold combinations. No separate firmware web UI is needed for daily
  operation.

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
  transport while another master is polling the same inverter port.

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
