#!/usr/bin/env python3
"""Diagnostic lecture seule pour un dongle Eybond / SmartESS.

Le script annonce une adresse locale au dongle sur le port UDP 58899, accepte
sa connexion TCP inverse, puis lit un bloc de registres Modbus RTU via le
canal Forward2Device. Il ne fait aucune écriture.

Il faut l'arreter avant de relancer l'integration Home Assistant : un seul
processus peut posseder la session du dongle a la fois.
"""
from __future__ import annotations

import argparse
import asyncio
import socket
import struct
import sys
import time
from pathlib import Path

UDP_PORT = 58899
DEFAULT_DEVCODE = 0x0994
FC_HEARTBEAT = 1
FC_FORWARD2DEVICE = 4
MAX_FRAME = 4096

def crc16_modbus(data: bytes) -> int:
    """CRC-16/Modbus (polynome 0xA001, valeur initiale 0xFFFF)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF

def build_read_frame(unit: int, start: int, count: int) -> bytes:
    """Trame Modbus RTU de lecture de registres holding (FC3)."""
    body = struct.pack(">BBHH", unit, 0x03, start, count)
    return body + struct.pack("<H", crc16_modbus(body))

def parse_read_response(payload: bytes, count: int) -> list[int]:
    """Valide et decode une reponse Modbus RTU FC3."""
    if len(payload) < 5:
        raise ValueError(f"reponse trop courte: {payload.hex()}")
    unit, func, byte_count = payload[0], payload[1], payload[2]
    if func & 0x80:
        raise ValueError(f"exception Modbus: fonction=0x{func:02x} code={payload[2]}")
    if func != 0x03:
        raise ValueError(f"fonction inattendue: 0x{func:02x}")
    if byte_count != count * 2:
        raise ValueError(f"octets={byte_count}, attendu={count * 2}")
    end = 3 + byte_count
    if len(payload) < end + 2:
        raise ValueError("CRC absent")
    crc_rx = int.from_bytes(payload[end:end + 2], "little")
    crc_calc = crc16_modbus(payload[:end])
    if crc_rx != crc_calc:
        raise ValueError(f"CRC invalide: recu=0x{crc_rx:04x} calcule=0x{crc_calc:04x}")
    data = payload[3:end]
    return [int.from_bytes(data[i:i + 2], "big") for i in range(0, len(data), 2)]

def printable_prefix(payload: bytes) -> str:
    """Retourne la chaine ASCII imprimable en tete du payload."""
    chars: list[str] = []
    for byte in payload:
        if 0x20 <= byte < 0x7F:
            chars.append(chr(byte))
        else:
            break
    return "".join(chars)

class State:
    def __init__(self, logfile: Path | None) -> None:
        self.logfile = logfile.open("w", encoding="utf-8") if logfile else None
        self.connected = asyncio.Event()
        self.done = asyncio.Event()
        self.sent_read = asyncio.Event()
        self.tid = 1
        self.write_lock = asyncio.Lock()
        self.result: list[int] | None = None

    def log(self, message: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} {message}"
        if self.logfile:
            self.logfile.write(line + "\n")
            self.logfile.flush()
        if sys.stdout is not None:
            print(line, flush=True)

    def next_tid(self) -> int:
        tid = self.tid
        self.tid = (self.tid + 1) & 0xFFFF
        return tid

    def close(self) -> None:
        if self.logfile:
            self.logfile.close()

async def read_frame(reader: asyncio.StreamReader) -> tuple[int, int, int, int, bytes]:
    """Lit une trame Eybond complete."""
    header = await reader.readexactly(8)
    tid, devcode, wire_len, devaddr, func = struct.unpack(">HHHBB", header)
    total_len = wire_len + 6
    if total_len < 8 or total_len > MAX_FRAME:
        raise ValueError(f"longueur de trame invalide: wire_len={wire_len}")
    payload = await reader.readexactly(total_len - 8)
    return tid, devcode, devaddr, func, payload

async def heartbeat_loop(
    state: State,
    writer: asyncio.StreamWriter,
    devaddr: int,
) -> None:
    """Envoie le heartbeat serveur attendu par le dongle."""
    while not state.done.is_set():
        now = time.gmtime()
        payload = bytes([
            now.tm_year % 100, now.tm_mon, now.tm_mday,
            now.tm_hour, now.tm_min, now.tm_sec,
        ]) + struct.pack(">H", 60)
        tid = state.next_tid()
        frame = struct.pack(
            ">HHHBB", tid, 0, len(payload) + 2, devaddr, FC_HEARTBEAT
        ) + payload
        try:
            async with state.write_lock:
                writer.write(frame)
                await writer.drain()
            state.log(f"TX heartbeat {frame.hex()}")
        except Exception as err:
            state.log(f"Heartbeat interrompu: {type(err).__name__}: {err}")
            return
        try:
            await asyncio.wait_for(state.done.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            pass

async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    state: State,
    args: argparse.Namespace,
) -> None:
    peer = writer.get_extra_info("peername")
    state.log(f"CONNECTED from {peer}")
    state.connected.set()
    heartbeat = asyncio.create_task(heartbeat_loop(state, writer, args.devaddr))
    try:
        while True:
            tid, devcode, devaddr, func, payload = await read_frame(reader)
            state.log(
                f"RX tid={tid} devcode=0x{devcode:04x} devaddr={devaddr} "
                f"fc={func} payload={payload.hex()}"
            )
            if func == FC_HEARTBEAT:
                pn = printable_prefix(payload)
                state.log(f"PN {pn} ({len(pn)} caracteres)")
                if state.sent_read.is_set():
                    continue
                state.sent_read.set()
                inner = build_read_frame(args.devaddr, args.register, args.count)
                tid_out = state.next_tid()
                wire_len = len(inner) + 2
                frame = struct.pack(
                    ">HHHBB", tid_out, DEFAULT_DEVCODE, wire_len,
                    args.devaddr, FC_FORWARD2DEVICE,
                ) + inner
                state.log(
                    f"TX read {args.register} x{args.count} "
                    f"inner={inner.hex()} frame={frame.hex()}"
                )
                async with state.write_lock:
                    writer.write(frame)
                    await writer.drain()
            elif func == FC_FORWARD2DEVICE:
                state.result = parse_read_response(payload, args.count)
                state.log(f"REGS {args.register} {state.result}")
                state.done.set()
                break
            else:
                state.log(f"FC {func} ignoree")
    except asyncio.IncompleteReadError:
        state.log("Connexion fermee par le dongle")
        state.done.set()
    except Exception as err:
        state.log(f"ERREUR: {type(err).__name__}: {err}")
        state.done.set()
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

async def announce(
    state: State,
    targets: list[str],
    announce_ip: str,
    port: int,
) -> None:
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

async def run(args: argparse.Namespace) -> int:
    state = State(Path(args.out) if args.out else None)
    targets = [args.broadcast]
    if "255.255.255.255" not in targets:
        targets.append("255.255.255.255")

    server = await asyncio.start_server(
        lambda reader, writer: handle_client(reader, writer, state, args),
        args.bind,
        args.port,
    )
    state.log(f"LISTENING on {args.bind}:{args.port}")
    state.log(f"Announce IP {args.announce_ip}; broadcast {targets}")
    announcer = asyncio.create_task(
        announce(state, targets, args.announce_ip, args.port)
    )

    try:
        await asyncio.wait_for(state.done.wait(), timeout=args.timeout)
    except asyncio.TimeoutError:
        state.log(
            f"TIMEOUT apres {args.timeout:g}s: aucune lecture complete. "
            "Verifier l'IP annoncee, le pare-feu et le port 8899."
        )
        return_code = 2
    else:
        return_code = 0 if state.result is not None else 3
    finally:
        announcer.cancel()
        try:
            await announcer
        except asyncio.CancelledError:
            pass
        server.close()
        await server.wait_closed()
        await asyncio.sleep(0.3)
        state.log("Fermeture de l'ecoute; le dongle retourne au cloud sous quelques secondes")
        state.close()
    return return_code

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Lecture Modbus lecture seule via un dongle Eybond/SmartESS.",
    )
    parser.add_argument(
        "--announce-ip", default=None,
        help="IP LAN de la machine qui execute ce script (defaut: detection auto).",
    )
    parser.add_argument(
        "--bind", default="0.0.0.0",
        help="Adresse d'ecoute TCP (defaut: 0.0.0.0).",
    )
    parser.add_argument(
        "--port", type=int, default=8899,
        help="Port TCP d'ecoute (defaut: 8899).",
    )
    parser.add_argument(
        "--broadcast", default="255.255.255.255",
        help="Adresse de broadcast UDP (ex: 192.168.71.255).",
    )
    parser.add_argument("--devaddr", type=int, default=1, help="Adresse Modbus (defaut: 1).")
    parser.add_argument("--register", type=int, default=201, help="Premier registre (defaut: 201).")
    parser.add_argument("--count", type=int, default=31, help="Nombre de registres (defaut: 31).")
    parser.add_argument("--timeout", type=float, default=45.0, help="Delai total en secondes (defaut: 45).")
    parser.add_argument("--out", default=None, help="Fichier de log (utile avec pythonw.exe).")
    return parser

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not 0 <= args.register <= 0xFFFF:
        parser.error("--register doit etre entre 0 et 65535")
    if not 1 <= args.count <= 125:
        parser.error("--count doit etre entre 1 et 125")
    if not 1 <= args.devaddr <= 247:
        parser.error("--devaddr doit etre entre 1 et 247")
    if not 1 <= args.port <= 65535:
        parser.error("--port doit etre entre 1 et 65535")
    if args.announce_ip is None:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("8.8.8.8", 80))
            args.announce_ip = probe.getsockname()[0]
        except OSError as err:
            parser.error(f"impossible de detecter l'IP locale: {err}")
        finally:
            probe.close()
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 130

if __name__ == "__main__":
    raise SystemExit(main())
