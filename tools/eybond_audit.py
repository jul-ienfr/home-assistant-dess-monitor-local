#!/usr/bin/env python3
"""Audit lecture/ecriture du SMG-II a travers un dongle Eybond.

Le script se connecte au dongle (annonce UDP 58899 + TCP inverse), lit les
blocs de mesures et de configuration, decode chaque registre, verifie les
invariants physiques, puis peut reecrire chaque registre avec sa valeur
courante (FC16) pour prouver que le chemin d'ecriture fonctionne sans
modifier le reglage.

Par defaut : lecture seule. Les ecritures ne sont activees qu'avec
--write-same. Aucune valeur differente de la valeur lue n'est ecrite, sauf
--toggle 305 qui bascule brievement le retroeclairage LCD puis le restaure, et
--invalid-probe qui teste des valeurs hors plage sur 303/305/337 (le firmware
les refuse ; sinon la valeur d'origine est reecrite).

Un seul processus peut posseder la session du dongle : arreter l'integration
Home Assistant avant, puis la laisser reprendre apres.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import socket
import struct
import sys
import time
from pathlib import Path

UDP_PORT = 58899
DEVCODE = 0x0994
FC_HEARTBEAT = 1
FC_FORWARD2DEVICE = 4
FC_READ = 3
FC_WRITE = 16
MAX_FRAME = 4096
OUT = None


def emit(line: str = "") -> None:
    if sys.stdout is not None:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
    if OUT is not None:
        OUT.write(line + "\n")
        OUT.flush()


def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def with_crc(body: bytes) -> bytes:
    return body + struct.pack("<H", crc16_modbus(body))


def build_read(unit: int, start: int, count: int) -> bytes:
    return with_crc(struct.pack(">BBHH", unit, FC_READ, start, count))


def build_write(unit: int, start: int, values: list[int]) -> bytes:
    body = struct.pack(">BBHHB", unit, FC_WRITE, start, len(values), len(values) * 2)
    body += b"".join(struct.pack(">H", value & 0xFFFF) for value in values)
    return with_crc(body)


def check_crc(payload: bytes, end: int) -> None:
    if len(payload) < end + 2:
        raise ValueError(f"CRC absent: {payload.hex()}")
    got = int.from_bytes(payload[end:end + 2], "little")
    calc = crc16_modbus(payload[:end])
    if got != calc:
        raise ValueError(f"CRC invalide: recu=0x{got:04x} calcule=0x{calc:04x}")


def parse_read(payload: bytes, count: int) -> list[int]:
    if len(payload) >= 5 and payload[1] & 0x80:
        check_crc(payload, 3)
        raise ValueError(f"exception Modbus {payload[1] & 0x7f}: code={payload[2]}")
    if len(payload) < 5:
        raise ValueError(f"reponse trop courte: {payload.hex()}")
    unit, func, byte_count = payload[0], payload[1], payload[2]
    if func != FC_READ:
        raise ValueError(f"fonction inattendue 0x{func:02x}")
    if byte_count != count * 2:
        raise ValueError(f"{byte_count} octets, attendu {count * 2}")
    end = 3 + byte_count
    check_crc(payload, end)
    data = payload[3:end]
    return [int.from_bytes(data[i:i + 2], "big") for i in range(0, len(data), 2)]


def parse_write(payload: bytes, start: int, count: int) -> None:
    if len(payload) >= 5 and payload[1] & 0x80:
        check_crc(payload, 3)
        raise ValueError(f"exception Modbus {payload[1] & 0x7f}: code={payload[2]}")
    if len(payload) < 6:
        raise ValueError(f"reponse trop courte: {payload.hex()}")
    unit, func = payload[0], payload[1]
    if func != FC_WRITE:
        raise ValueError(f"fonction inattendue 0x{func:02x}")
    rx_start, rx_count = struct.unpack(">HH", payload[2:6])
    if rx_start != start or rx_count != count:
        raise ValueError(f"echo inattendu start={rx_start} count={rx_count}")
    if len(payload) == 8:
        check_crc(payload, 6)
    elif len(payload) > 8:
        check_crc(payload, len(payload) - 2)


class State:
    def __init__(self, logfile: Path | None) -> None:
        self.logfile = logfile.open("w", encoding="utf-8") if logfile else None
        self.connected = asyncio.Event()
        self.done = asyncio.Event()
        self.session: Session | None = None
        self.pn = ""

    def log(self, message: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} {message}"
        if self.logfile:
            self.logfile.write(line + "\n")
            self.logfile.flush()
        if sys.stdout is not None:
            emit(line)

    def close(self) -> None:
        if self.logfile:
            self.logfile.close()


class Session:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                 state: State, unit: int) -> None:
        self.reader = reader
        self.writer = writer
        self.state = state
        self.unit = unit
        self.tid = 1
        self.lock = asyncio.Lock()

    def next_tid(self) -> int:
        tid = self.tid
        self.tid = (self.tid + 1) & 0xFFFF
        return tid

    async def read_frame(self) -> tuple[int, int, int, int, bytes]:
        header = await self.reader.readexactly(8)
        tid, devcode, wire_len, devaddr, func = struct.unpack(">HHHBB", header)
        if wire_len < 2 or wire_len > MAX_FRAME:
            raise ValueError(f"longueur invalide: wire_len={wire_len}")
        payload = await self.reader.readexactly(wire_len - 2)
        return tid, devcode, devaddr, func, payload

    async def request(self, inner: bytes, timeout: float = 8.0) -> bytes:
        async with self.lock:
            tid = self.next_tid()
            frame = struct.pack(
                ">HHHBB", tid, DEVCODE, len(inner) + 2, self.unit, FC_FORWARD2DEVICE
            ) + inner
            self.writer.write(frame)
            await self.writer.drain()
            loop = asyncio.get_running_loop()
            deadline = loop.time() + timeout
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise asyncio.TimeoutError("pas de reponse du dongle")
                rx_tid, rx_devcode, rx_devaddr, rx_func, payload = await asyncio.wait_for(
                    self.read_frame(), remaining
                )
                if rx_func == FC_HEARTBEAT:
                    pn = "".join(chr(b) for b in payload if 0x20 <= b < 0x7F)
                    if pn:
                        self.state.pn = pn
                    continue
                if rx_func != FC_FORWARD2DEVICE:
                    self.state.log(f"FC {rx_func} ignoree (tid={rx_tid})")
                    continue
                if rx_devaddr != self.unit:
                    self.state.log(f"devaddr {rx_devaddr} ignoree (tid={rx_tid})")
                    continue
                if rx_tid != tid:
                    self.state.log(f"tid {rx_tid} != {tid} (accepte)")
                return payload

    async def heartbeat(self) -> None:
        while not self.state.done.is_set():
            now = time.gmtime()
            payload = bytes([
                now.tm_year % 100, now.tm_mon, now.tm_mday,
                now.tm_hour, now.tm_min, now.tm_sec,
            ]) + struct.pack(">H", 60)
            tid = self.next_tid()
            frame = struct.pack(">HHHBB", tid, 0, len(payload) + 2, self.unit, FC_HEARTBEAT) + payload
            try:
                async with self.lock:
                    self.writer.write(frame)
                    await self.writer.drain()
            except Exception as err:  # noqa: BLE001
                self.state.log(f"Heartbeat interrompu: {type(err).__name__}: {err}")
                return
            try:
                await asyncio.wait_for(self.state.done.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                pass


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                        state: State, args: argparse.Namespace) -> None:
    peer = writer.get_extra_info("peername")
    state.log(f"CONNECTED from {peer}")
    session = Session(reader, writer, state, args.devaddr)
    state.session = session
    state.connected.set()
    heartbeat = asyncio.create_task(session.heartbeat())
    try:
        await state.done.wait()
    finally:
        heartbeat.cancel()
        try:
            await heartbeat
        except asyncio.CancelledError:
            pass
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        state.log("Connexion fermee")


async def announce(state: State, targets: list[str], announce_ip: str, port: int) -> None:
    command = f"set>server={announce_ip}:{port};".encode("ascii")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    loop = asyncio.get_running_loop()
    try:
        while not state.connected.is_set():
            for target in targets:
                try:
                    await loop.sock_sendto(sock, command, (target, UDP_PORT))
                    state.log(f"UDP announce -> {target}:{UDP_PORT} {command.decode()}")
                except OSError as err:
                    state.log(f"UDP announce vers {target} impossible: {err}")
            try:
                await asyncio.wait_for(state.connected.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                pass
    finally:
        sock.close()


# ---------------------------------------------------------------------------
# Carte de registres
# ---------------------------------------------------------------------------
SENSORS = {
    100: ("Fault Code (32 bits)", "u32", 1, ""),
    108: ("Warning Code (32 bits)", "u32", 1, ""),
    201: ("Operation Mode", "u16", 1, ""),
    202: ("AC Input Voltage", "s16", 0.1, "V"),
    203: ("AC Input Frequency", "s16", 0.01, "Hz"),
    204: ("AC Input Power", "s16", 1, "W"),
    205: ("Inverter Voltage", "s16", 0.1, "V"),
    206: ("Inverter Current", "s16", 0.1, "A"),
    207: ("Inverter Frequency", "s16", 0.01, "Hz"),
    208: ("Inverter Power", "s16", 1, "W"),
    209: ("Inverter Charging Power", "s16", 1, "W"),
    210: ("AC Output Voltage", "s16", 0.1, "V"),
    211: ("AC Output Current", "s16", 0.1, "A"),
    212: ("AC Output Frequency", "s16", 0.01, "Hz"),
    213: ("AC Output Active Power", "s16", 1, "W"),
    214: ("AC Output Apparent Power", "s16", 1, "VA"),
    215: ("Battery Voltage", "s16", 0.1, "V"),
    216: ("Battery Current", "s16", 0.1, "A"),
    217: ("Battery Power", "s16", 1, "W"),
    219: ("PV Voltage", "s16", 0.1, "V"),
    220: ("PV Current", "s16", 0.1, "A"),
    223: ("PV Power", "s16", 1, "W"),
    224: ("PV Charging Power", "s16", 1, "W"),
    225: ("Load", "s16", 1, "%"),
    226: ("DCDC Temperature", "s16", 1, "degC"),
    227: ("Inverter Temperature", "s16", 1, "degC"),
    229: ("Battery SOC", "u16", 1, "%"),
    232: ("Battery Current (BMS)", "s16", 0.1, "A"),
    233: ("Inverter Charging Current", "s16", 0.1, "A"),
    234: ("PV Charging Current", "s16", 0.1, "A"),
    643: ("Rated Power", "u16", 1, "W"),
}

CONFIG = {
    300: ("Output Mode", 0, 4, {0: "Single", 1: "Parallel", 2: "Phase P1", 3: "Phase P2", 4: "Phase P3"}),
    301: ("Output Priority", 0, 3, {0: "UTI", 1: "SOL", 2: "SBU", 3: "SUB"}),
    302: ("Input Voltage Range", 0, 1, {0: "Wide", 1: "Narrow"}),
    303: ("Buzzer Mode", 0, 3, {0: "Silent", 1: "Input+warn+fault", 2: "Warn+fault", 3: "Fault only"}),
    305: ("LCD Backlight", 0, 1, {0: "Timed off", 1: "Always on"}),
    306: ("LCD Auto Home", 0, 1, {0: "Stay", 1: "Return home"}),
    307: ("Energy Saving", 0, 1, {0: "Off", 1: "On"}),
    308: ("Overload Auto Restart", 0, 1, {0: "Off", 1: "On"}),
    309: ("Over Temperature Auto Restart", 0, 1, {0: "Off", 1: "On"}),
    310: ("Overload Transfer To Bypass", 0, 1, {0: "Off", 1: "On"}),
    313: ("Battery Equalization", 0, 1, {0: "Off", 1: "On"}),
    320: ("Output Voltage Setting", 2200, 2400, {}),
    321: ("Output Frequency Setting", 5000, 6000, {}),
    322: ("Battery Type", 0, 8, {0: "AGM", 1: "Flooded", 2: "User", 3: "Li1", 4: "Li2", 5: "Li3", 6: "Li4", 8: "Lib"}),
    323: ("Battery OVP", 280, 320, {}),
    324: ("Max Charging Voltage", 240, 300, {}),
    325: ("Float Charging Voltage", 240, 300, {}),
    326: ("Recovery Voltage (mains)", 200, 260, {}),
    327: ("Low DC Cut-off (mains)", 200, 260, {}),
    329: ("Low DC Cut-off (off-grid)", 200, 260, {}),
    331: ("Charging Priority", 0, 3, {0: "Utility", 1: "PV", 2: "PV=Utility", 3: "PV only"}),
    332: ("Max Charging Current", 0, 1000, {}),
    333: ("Max Mains Charging Current", 0, 800, {}),
    334: ("Equalization Voltage", 240, 300, {}),
    335: ("Equalization Time", 0, 900, {}),
    336: ("Equalization Timeout", 0, 900, {}),
    337: ("Equalization Interval", 1, 90, {}),
    341: ("SOC Point Back To Utility", 31, 100, {}),
    342: ("SOC Point Back To Battery", 60, 100, {}),
    343: ("Low DC Cut-off SOC", 3, 30, {}),
    406: ("Turn On Mode", 0, 2, {0: "Local+remote", 1: "Local only", 2: "Remote only"}),
    420: ("Remote Output Enable", 0, 1, {0: "Shutdown", 1: "Turn-on"}),
    426: ("Exit Fault State", 1, 1, {}),
}

SCALES = {
    320: (0.1, "V"), 321: (0.01, "Hz"), 323: (0.1, "V"), 324: (0.1, "V"),
    325: (0.1, "V"), 326: (0.1, "V"), 327: (0.1, "V"), 329: (0.1, "V"),
    332: (0.1, "A"), 333: (0.1, "A"), 334: (0.1, "V"),
}

WRITE_REGS = [
    300, 301, 302, 303, 305, 306, 307, 308, 309, 310, 313,
    320, 321, 322, 323, 324, 325, 326, 327, 329,
    331, 332, 333, 334, 335, 336, 337, 341, 342, 343, 406, 420,
]


def signed16(raw: int) -> int:
    return raw - 0x10000 if raw >= 0x8000 else raw


def value_of(raw: int, kind: str, scale: float):
    if kind == "s16":
        return signed16(raw) * scale
    if kind == "u32":
        return raw
    return raw * scale


def format_value(reg: int, raw: int) -> str:
    if reg in SENSORS:
        name, kind, scale, unit = SENSORS[reg]
        if kind == "u32":
            return f"{raw} (0x{raw:08x})"
        value = value_of(raw, kind, scale)
        text = f"{value:.2f}".rstrip("0").rstrip(".") if scale != 1 else str(value)
        return f"{text} {unit}".strip()
    if reg in CONFIG:
        name, low, high, options = CONFIG[reg]
        if reg in SCALES:
            scale, unit = SCALES[reg]
            return f"{raw * scale:.2f}".rstrip("0").rstrip(".") + f" {unit}"
        if options:
            return f"{raw} = {options.get(raw, 'INCONNU')}"
        return str(raw)
    return str(raw)


async def read_block(session: Session, start: int, count: int) -> list[int]:
    payload = await session.request(build_read(session.unit, start, count))
    return parse_read(payload, count)


async def read_range(session: Session, start: int, count: int,
                     values: dict[int, int], errors: dict[int, str]) -> None:
    try:
        regs = await read_block(session, start, count)
    except Exception as err:  # noqa: BLE001
        if count == 1:
            errors[start] = str(err)
            return
        mid = count // 2
        await read_range(session, start, mid, values, errors)
        await read_range(session, start + mid, count - mid, values, errors)
        return
    for offset, raw in enumerate(regs):
        values[start + offset] = raw


def check_invariants(values: dict[int, int], errors: dict[int, str]) -> list[str]:
    issues: list[str] = []

    def v(reg: int):
        return values.get(reg)

    def scaled(reg: int):
        raw = values.get(reg)
        if raw is None:
            return None
        kind = SENSORS.get(reg, ("", "u16"))[1]
        scale = SENSORS.get(reg, ("", "u16", 1, ""))[2]
        return value_of(raw, kind, scale)

    if v(202) is not None and not 170 <= scaled(202) <= 280:
        issues.append(f"202 tension entree hors plage: {scaled(202):.1f} V")
    if v(210) is not None and not 170 <= scaled(210) <= 280:
        issues.append(f"210 tension sortie hors plage: {scaled(210):.1f} V")
    if v(203) is not None and not 45 <= scaled(203) <= 65:
        issues.append(f"203 frequence entree hors plage: {scaled(203):.2f} Hz")
    if v(212) is not None and not 45 <= scaled(212) <= 65:
        issues.append(f"212 frequence sortie hors plage: {scaled(212):.2f} Hz")
    if v(215) is not None and not 18 <= scaled(215) <= 34:
        issues.append(f"215 tension batterie hors plage 24 V: {scaled(215):.1f} V")
    if v(229) is not None and not 0 <= v(229) <= 100:
        issues.append(f"229 SOC hors 0-100: {v(229)}")
    if v(225) is not None and not 0 <= signed16(v(225)) <= 110:
        issues.append(f"225 charge hors 0-110%: {signed16(v(225))}")
    for reg in (226, 227):
        if v(reg) is not None and not -20 <= signed16(v(reg)) <= 90:
            issues.append(f"{reg} temperature hors plage: {signed16(v(reg))} degC")

    if all(v(r) is not None for r in (204, 213, 208)):
        # 208 est positif en sortie onduleur, negatif en entree onduleur.
        expected = signed16(v(204)) - signed16(v(213))
        actual = -signed16(v(208))
        if abs(expected - actual) > 25:
            issues.append(f"208 incoherent: {signed16(v(208))} W, attendu ~-{expected} W (204-213)")
    if all(v(r) is not None for r in (213, 214)):
        if signed16(v(214)) + 2 < signed16(v(213)):
            issues.append(f"214 ({signed16(v(214))} VA) < 213 ({signed16(v(213))} W)")
    if all(v(r) is not None for r in (215, 216, 217)):
        expected = scaled(215) * (signed16(v(216)) * 0.1)
        actual = signed16(v(217))
        if abs(expected - actual) > 25:
            issues.append(f"217 incoherent: {actual} W, attendu ~{expected:.0f} W (215*216)")
    if all(v(r) is not None for r in (213, 225, 643)):
        rated = v(643)
        if rated:
            expected = signed16(v(213)) / rated * 100
            if abs(expected - signed16(v(225))) > 5:
                issues.append(f"225 incoherent: {signed16(v(225))}%, attendu ~{expected:.0f}% (213/643)")

    for reg, (name, low, high, options) in CONFIG.items():
        if reg == 426:
            continue  # commande d'acquittement, pas un reglage lisible
        raw = v(reg)
        if raw is None:
            continue
        if not low <= raw <= high:
            issues.append(f"{reg} {name}: valeur {raw} hors bornes {low}-{high}")
        if options and raw not in options:
            issues.append(f"{reg} {name}: valeur {raw} sans libelle")
    if v(323) is not None and v(324) is not None and v(323) <= v(324):
        issues.append(f"323 OVP ({v(323)/10:.1f} V) <= 324 bulk ({v(324)/10:.1f} V)")
    if v(324) is not None and v(325) is not None and v(325) > v(324):
        issues.append(f"325 float ({v(325)/10:.1f} V) > 324 bulk ({v(324)/10:.1f} V)")
    if v(326) is not None and v(327) is not None and v(327) >= v(326):
        issues.append(f"327 cutoff ({v(327)/10:.1f} V) >= 326 recovery ({v(326)/10:.1f} V)")
    if v(332) is not None and v(332) > 1000:
        issues.append(f"332 courant charge ({v(332)/10:.1f} A) > 100 A")
    if v(333) is not None and v(333) > 800:
        issues.append(f"333 courant reseau ({v(333)/10:.1f} A) > 80 A")
    if v(341) is not None and v(343) is not None and v(343) >= v(341):
        issues.append(f"343 cutoff SOC ({v(343)}%) >= 341 retour utilitaire ({v(341)}%)")
    if v(341) is not None and v(342) is not None and v(341) >= v(342):
        issues.append(f"341 retour utilitaire ({v(341)}%) >= 342 retour batterie ({v(342)}%)")
    if v(342) is not None and not 60 <= v(342) <= 100:
        issues.append(f"342 retour batterie ({v(342)}%) hors 60-100%")
    if v(320) is not None and not 2200 <= v(320) <= 2400:
        issues.append(f"320 tension sortie ({v(320)/10:.1f} V) hors 220-240 V")
    if v(321) is not None and v(321) not in (5000, 6000):
        issues.append(f"321 frequence sortie ({v(321)/100:.2f} Hz) ni 50 ni 60 Hz")
    if v(300) is not None and v(300) != 0:
        issues.append(f"300 mode sortie {v(300)} != Single sur un onduleur seul")
    for reg in errors:
        issues.append(f"{reg} lecture impossible: {errors[reg]}")
    return issues


async def run(args: argparse.Namespace) -> int:
    global OUT
    if args.report:
        OUT = Path(args.report).open("w", encoding="utf-8")
    state = State(Path(args.log) if args.log else None)
    targets = [args.broadcast]
    if args.target:
        targets.insert(0, args.target)
    if "255.255.255.255" not in targets:
        targets.append("255.255.255.255")

    server = await asyncio.start_server(
        lambda reader, writer: asyncio.create_task(handle_client(reader, writer, state, args)),
        args.bind, args.port,
    )
    state.log(f"LISTENING {args.bind}:{args.port}")
    state.log(f"Announce IP {args.announce_ip}; cibles {targets}")
    announcer = asyncio.create_task(announce(state, targets, args.announce_ip, args.port))
    session: Session | None = None
    try:
        try:
            await asyncio.wait_for(state.connected.wait(), timeout=args.timeout)
        except asyncio.TimeoutError:
            state.log(f"TIMEOUT: aucune connexion apres {args.timeout:g}s")
            return 2
        session = state.session
        assert session is not None
        state.log(f"PN {state.pn or 'inconnu'}")

        values: dict[int, int] = {}
        errors: dict[int, str] = {}
        for start, count in ((100, 16), (201, 31), (232, 3), (300, 44),
                             (406, 1), (420, 1), (426, 1), (643, 1)):
            state.log(f"READ {start}..{start + count - 1}")
            await read_range(session, start, count, values, errors)
            await asyncio.sleep(0.15)

        emit("\n=== MESURES ===")
        for reg in sorted(r for r in values if r in SENSORS):
            emit(f"{reg:4d}  {values[reg]:5d}  0x{values[reg]:04x}  {SENSORS[reg][0]:28s} {format_value(reg, values[reg])}")

        emit("\n=== CONFIGURATION ===")
        for reg in sorted(r for r in values if r in CONFIG):
            name = CONFIG[reg][0]
            emit(f"{reg:4d}  {values[reg]:5d}  0x{values[reg]:04x}  {name:28s} {format_value(reg, values[reg])}")

        unknown = sorted(r for r in values if r not in SENSORS and r not in CONFIG)
        if unknown:
            emit("\n=== REGISTRES NON DOCUMENTES ===")
            for reg in unknown:
                emit(f"{reg:4d}  {values[reg]:5d}  0x{values[reg]:04x}")

        if errors:
            emit("\n=== LECTURES EN ERREUR ===")
            for reg in sorted(errors):
                emit(f"{reg:4d}  {errors[reg]}")

        issues = check_invariants(values, errors)
        emit("\n=== INVARIANTS ===")
        if issues:
            for issue in issues:
                emit(f"ECHEC  {issue}")
        else:
            emit("OK  tous les invariants physiques et les bornes sont respectes")

        writes: list[dict] = []
        if args.write_same:
            emit("\n=== ECRITURES FC16 (valeur identique) ===")
            for reg in WRITE_REGS:
                if reg not in values:
                    emit(f"SKIP  {reg}: valeur inconnue")
                    continue
                original = values[reg]
                try:
                    payload = await session.request(build_write(session.unit, reg, [original]))
                    parse_write(payload, reg, 1)
                except Exception as err:  # noqa: BLE001
                    emit(f"ECHEC {reg} {CONFIG[reg][0]}: ecriture refusee: {err}")
                    writes.append({"reg": reg, "ok": False, "error": str(err)})
                    continue
                await asyncio.sleep(0.2)
                try:
                    readback = (await read_block(session, reg, 1))[0]
                except Exception as err:  # noqa: BLE001
                    emit(f"ECHEC {reg} {CONFIG[reg][0]}: relecture impossible: {err}")
                    writes.append({"reg": reg, "ok": False, "error": f"readback: {err}"})
                    continue
                ok = readback == original
                emit(f"{'OK   ' if ok else 'ECHEC'} {reg:4d} {CONFIG[reg][0]:28s} ecrit={original} relu={readback}")
                writes.append({"reg": reg, "ok": ok, "written": original, "readback": readback})

            if args.toggle:
                reg = args.toggle
                if reg in values and values[reg] in (0, 1):
                    original = values[reg]
                    toggled = 1 - original
                    emit(f"\n=== BASCULE {reg} {CONFIG[reg][0]}: {original} -> {toggled} -> {original} ===")
                    for value in (toggled, original):
                        try:
                            payload = await session.request(build_write(session.unit, reg, [value]))
                            parse_write(payload, reg, 1)
                            await asyncio.sleep(0.2)
                            readback = (await read_block(session, reg, 1))[0]
                            emit(f"{'OK   ' if readback == value else 'ECHEC'} ecrit={value} relu={readback}")
                        except Exception as err:  # noqa: BLE001
                            emit(f"ECHEC bascule {value}: {err}")
                            break

        if args.invalid_probe:
            emit("\n=== SONDE DE VALIDATION FIRMWARE (valeurs invalides) ===")
            for reg, invalid in ((303, 4), (305, 2), (337, 91)):
                if reg not in values:
                    continue
                original = values[reg]
                try:
                    payload = await session.request(build_write(session.unit, reg, [invalid]))
                    parse_write(payload, reg, 1)
                    await asyncio.sleep(0.2)
                    readback = (await read_block(session, reg, 1))[0]
                    verdict = "ACCEPTEE" if readback == invalid else f"RAMENEE A {readback}"
                    emit(f"{reg} {CONFIG[reg][0]}: ecriture {invalid} {verdict}")
                    payload = await session.request(build_write(session.unit, reg, [original]))
                    parse_write(payload, reg, 1)
                    await asyncio.sleep(0.2)
                    restored = (await read_block(session, reg, 1))[0]
                    emit(f"{reg} restaure {original}: {'OK' if restored == original else 'ECHEC ' + str(restored)}")
                except Exception as err:  # noqa: BLE001
                    emit(f"{reg} sonde invalide refusee: {err} (valeur conservee)")

        if args.exit_fault:
            faults = values.get(100, 0)
            warnings = values.get(108, 0)
            emit(f"\n=== EXIT FAULT STATE (fault=0x{faults:08x} warning=0x{warnings:08x}) ===")
            if faults:
                emit("SKIP  426: un defaut est actif, acquittement non teste")
            else:
                try:
                    payload = await session.request(build_write(session.unit, 426, [1]))
                    parse_write(payload, 426, 1)
                    emit("OK    426: ecriture 1 acceptee (aucun defaut actif)")
                except Exception as err:  # noqa: BLE001
                    emit(f"ECHEC 426: ecriture refusee: {err}")

        result = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "pn": state.pn,
            "values": {str(k): val for k, val in sorted(values.items())},
            "errors": {str(k): val for k, val in sorted(errors.items())},
            "issues": issues,
            "writes": writes,
        }
        if args.json:
            Path(args.json).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
            emit(f"\nJSON ecrit dans {args.json}")
        return 0 if not issues else 1
    finally:
        state.done.set()
        if session is not None:
            await asyncio.sleep(0.1)
        announcer.cancel()
        try:
            await announcer
        except asyncio.CancelledError:
            pass
        server.close()
        await server.wait_closed()
        await asyncio.sleep(0.3)
        state.log("Fermeture; le dongle retourne au cloud")
        state.close()
        if OUT is not None:
            OUT.close()
            OUT = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit SMG-II via dongle Eybond.")
    parser.add_argument("--announce-ip", required=True, help="IP LAN de ce poste.")
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8899)
    parser.add_argument("--target", default=None, help="IP du dongle pour une annonce unicast.")
    parser.add_argument("--broadcast", default="192.168.71.255")
    parser.add_argument("--devaddr", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=45.0, help="Delai de connexion.")
    parser.add_argument("--write-same", action="store_true", help="Reecrit chaque registre avec sa valeur.")
    parser.add_argument("--toggle", type=int, default=0, help="Registre 0/1 a basculer puis restaurer.")
    parser.add_argument("--exit-fault", action="store_true", help="Teste l'ecriture 426=1 si aucun defaut.")
    parser.add_argument("--invalid-probe", action="store_true",
                        help="Teste des valeurs hors plage sur 303/305/337.")
    parser.add_argument("--json", default=None)
    parser.add_argument("--log", default=None)
    parser.add_argument("--report", default=None, help="Fichier texte du rapport.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not 1 <= args.devaddr <= 247:
        parser.error("--devaddr doit etre entre 1 et 247")
    if not 1 <= args.port <= 65535:
        parser.error("--port doit etre entre 1 et 65535")
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 130
    except Exception:  # noqa: BLE001
        import traceback
        Path(__file__).with_name("eybond_audit_error.log").write_text(
            traceback.format_exc(), encoding="utf-8"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())



