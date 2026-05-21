"""
Modbus TCP Server Example using modbus_tk.

This server exposes holding registers #40001 to #40040 (40 registers total)
for both read and write operations, and prints PLC-like monitoring output.

Address mapping note:
- Human-friendly Modbus register number #40001 maps to internal offset 0.
- Human-friendly Modbus register number #40040 maps to internal offset 39.
"""

import argparse
from datetime import datetime
import signal
import socket
import sys
import time
from typing import Iterable, List, Sequence, Set, Tuple

import modbus_tk.hooks as hooks
from colorama import just_fix_windows_console

from modbus_tk import defines as cst
from modbus_tk import modbus_tcp


RESET = "\033[0m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
BRIGHT_RED = "\033[91m"


def timestamp() -> str:
    """Return a short timestamp for every server-side log line."""
    return datetime.now().strftime("%H:%M:%S")


def offset_to_register_number(offset: int) -> int:
    """Convert internal zero-based offset into human register number (4xxxx)."""
    return 40001 + offset


def decode_modbus_request(request_pdu_with_mbap: bytes) -> str:
    """
    Decode a Modbus TCP request packet and return a human-readable action string.

    Packet layout:
    - MBAP header is 7 bytes for Modbus TCP.
    - PDU starts at byte 7 where function code is located.
    """
    if len(request_pdu_with_mbap) < 8:
        return "UNKNOWN REQUEST (packet too short)"

    unit_id = request_pdu_with_mbap[6]
    function_code = request_pdu_with_mbap[7]

    # READ_HOLDING_REGISTERS (function code 3)
    if function_code == cst.READ_HOLDING_REGISTERS and len(request_pdu_with_mbap) >= 12:
        start_offset = int.from_bytes(request_pdu_with_mbap[8:10], byteorder="big")
        quantity = int.from_bytes(request_pdu_with_mbap[10:12], byteorder="big")
        start_reg = offset_to_register_number(start_offset)
        end_reg = offset_to_register_number(start_offset + quantity - 1)
        return (
            f"READ  unit={unit_id}  fc=3  range=#{start_reg}~#{end_reg} "
            f"(offset={start_offset}, qty={quantity})"
        )

    # WRITE_SINGLE_REGISTER (function code 6)
    if function_code == cst.WRITE_SINGLE_REGISTER and len(request_pdu_with_mbap) >= 12:
        offset = int.from_bytes(request_pdu_with_mbap[8:10], byteorder="big")
        value = int.from_bytes(request_pdu_with_mbap[10:12], byteorder="big")
        reg = offset_to_register_number(offset)
        return f"WRITE unit={unit_id}  fc=6  #{reg}={value}"

    # WRITE_MULTIPLE_REGISTERS (function code 16)
    if function_code == cst.WRITE_MULTIPLE_REGISTERS and len(request_pdu_with_mbap) >= 13:
        start_offset = int.from_bytes(request_pdu_with_mbap[8:10], byteorder="big")
        quantity = int.from_bytes(request_pdu_with_mbap[10:12], byteorder="big")
        start_reg = offset_to_register_number(start_offset)
        end_reg = offset_to_register_number(start_offset + quantity - 1)
        return (
            f"WRITE unit={unit_id}  fc=16 range=#{start_reg}~#{end_reg} "
            f"(offset={start_offset}, qty={quantity})"
        )

    return f"REQUEST unit={unit_id}  fc={function_code}"


def maybe_color(text: str, color: str, enabled: bool) -> str:
    """Wrap text with ANSI color only when color output is enabled."""
    if not enabled:
        return text
    return f"{color}{text}{RESET}"


def render_register_table(
    values: Sequence[int],
    changed_offsets: Set[int],
    color_enabled: bool,
    active_clients: Sequence[str],
) -> str:
    """
    Render #40001~#40040 in an ASCII table.

    The table has 4 register/value pairs per row to keep output compact,
    while still showing every register on each refresh.
    """
    col_count = 4
    row_count = 10  # 40 registers / 4 columns
    cell_width = 18

    horizontal = "+" + "+".join(["-" * cell_width] * col_count) + "+"
    title = "PLC Holding Register Monitor (#40001~#40040)"
    client_count = len(active_clients)
    client_status = f"Clients: {client_count}"
    client_ips = ", ".join(active_clients) if active_clients else "No connected clients"

    lines: List[str] = []
    lines.append(horizontal)
    lines.append("|" + title.center(cell_width * col_count + (col_count - 1)) + "|")
    lines.append("|" + client_status.center(cell_width * col_count + (col_count - 1)) + "|")
    lines.append("|" + client_ips.center(cell_width * col_count + (col_count - 1)) + "|")
    lines.append(horizontal)

    for row in range(row_count):
        row_cells: List[str] = []
        for col in range(col_count):
            offset = row + (row_count * col)
            reg_num = offset_to_register_number(offset)
            value = values[offset]
            # Pad first, then colorize. This avoids ANSI escape codes breaking
            # visible column width and keeps '|' separators aligned.
            cell_text = f"#{reg_num}: {value}".ljust(cell_width)

            if offset in changed_offsets:
                cell_text = maybe_color(cell_text, BRIGHT_RED, color_enabled)

            row_cells.append(cell_text)

        lines.append("|" + "|".join(row_cells) + "|")
        lines.append(horizontal)

    legend = (
        "Legend: "
        + maybe_color("Changed register", BRIGHT_RED, color_enabled)
        + ", normal register"
    )
    lines.append(legend)
    return "\n".join(lines)


def collect_changed_offsets(before: Iterable[int], after: Iterable[int]) -> Set[int]:
    """Return internal offsets where register values changed."""
    changed: Set[int] = set()
    for idx, (old_value, new_value) in enumerate(zip(before, after)):
        if old_value != new_value:
            changed.add(idx)
    return changed


def parse_args() -> argparse.Namespace:
    """Parse command-line options for host, port, and slave ID."""
    parser = argparse.ArgumentParser(
        description="Run a Modbus TCP server exposing holding registers #40001-#40040."
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="IP address to bind the server (default: 0.0.0.0).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=502,
        help="TCP port for Modbus (default: 502).",
    )
    parser.add_argument(
        "--slave-id",
        type=int,
        default=1,
        help="Slave ID (Unit ID) that clients should target (default: 1).",
    )
    return parser.parse_args()


def main() -> None:
    """Start Modbus TCP server and print PLC-style request/monitor output."""
    args = parse_args()

    # Enable ANSI support on Windows terminals so colored output works reliably.
    just_fix_windows_console()
    color_enabled = True

    # Create the Modbus TCP server socket listener.
    server = modbus_tcp.TcpServer(address=args.host, port=args.port)

    # Start network listener before defining slave blocks.
    server.start()
    print(f"[SERVER] Started at {args.host}:{args.port}")
    print(f"[SERVER] Slave ID: {args.slave_id}")

    # Create one slave device (unit) in this server.
    slave = server.add_slave(args.slave_id)

    # Add one holding-register block:
    # - Name: "hr"
    # - Type: HOLDING_REGISTERS (4xxxx)
    # - Start internal address: 0   -> corresponds to #40001
    # - Size: 40 registers          -> up to #40040
    slave.add_block("hr", cst.HOLDING_REGISTERS, 0, 40)

    # Initialize all 40 holding registers with zero.
    slave.set_values("hr", 0, [0] * 40)
    print("[SERVER] Exposed holding registers #40001 to #40040 for read/write")

    # Keep one baseline snapshot; we use it to detect value changes and refresh table.
    previous_values = tuple(slave.get_values("hr", 0, 40))
    print()
    print(render_register_table(
        previous_values,
        changed_offsets=set(),
        color_enabled=color_enabled,
        active_clients=[],
    ))

    def on_before_handle_request(hook_args):
        """Hook callback fired for each incoming Modbus request."""
        if not isinstance(hook_args, tuple) or len(hook_args) < 2:
            return

        raw_request = hook_args[1]
        if not isinstance(raw_request, (bytes, bytearray)):
            return

        action_text = decode_modbus_request(bytes(raw_request))
        print(maybe_color(f"[{timestamp()}] {action_text}", YELLOW, color_enabled))

    # Install request-level logging hook so every read/write request is printed.
    try:
        hooks.install_hook("modbus.Server.before_handle_request", on_before_handle_request)
        print(maybe_color("[SERVER] Request logging hook installed", GREEN, color_enabled))
    except Exception as exc:
        print(f"[SERVER] Warning: could not install request hook: {exc}")
        print("[SERVER] Register change table will still update on value changes")

    active_clients = {}
    CLIENT_IDLE_TIMEOUT = 30.0

    def on_client_connect(hook_args):
        if not isinstance(hook_args, tuple) or len(hook_args) != 3:
            return
        _server, client_sock, address = hook_args
        active_clients[client_sock.fileno()] = (address, time.monotonic(), client_sock)
        print(maybe_color(
            f"[{timestamp()}] CLIENT CONNECTED {address[0]}:{address[1]} total={len(active_clients)}",
            GREEN,
            color_enabled,
        ))

    def on_client_disconnect(hook_args):
        if not isinstance(hook_args, tuple) or len(hook_args) < 2:
            return
        _server, client_sock = hook_args
        fileno = client_sock.fileno()
        entry = active_clients.pop(fileno, None)
        count = len(active_clients)
        if entry is not None:
            address, _, _ = entry
            print(maybe_color(
                f"[{timestamp()}] CLIENT DISCONNECTED {address[0]}:{address[1]} total={count}",
                YELLOW,
                color_enabled,
            ))
        else:
            print(maybe_color(
                f"[{timestamp()}] CLIENT DISCONNECTED socket={fileno} total={count}",
                YELLOW,
                color_enabled,
            ))

    def on_after_recv(hook_args):
        if not isinstance(hook_args, tuple) or len(hook_args) != 3:
            return
        _server, client_sock, _request = hook_args
        fileno = client_sock.fileno()
        if fileno in active_clients:
            address, _, sock = active_clients[fileno]
            active_clients[fileno] = (address, time.monotonic(), sock)

    def cleanup_idle_clients() -> None:
        now = time.monotonic()
        for fileno, (address, last_seen, sock) in list(active_clients.items()):
            if now - last_seen > CLIENT_IDLE_TIMEOUT:
                try:
                    sock.close()
                except Exception:
                    pass
                active_clients.pop(fileno, None)
                try:
                    if sock in server._sockets:
                        server._sockets.remove(sock)
                except Exception:
                    pass
                print(maybe_color(
                    f"[{timestamp()}] CLIENT TIMEOUT {address[0]}:{address[1]} total={len(active_clients)}",
                    YELLOW,
                    color_enabled,
                ))

    try:
        hooks.install_hook("modbus_tcp.TcpServer.on_connect", on_client_connect)
        hooks.install_hook("modbus_tcp.TcpServer.on_disconnect", on_client_disconnect)
        hooks.install_hook("modbus_tcp.TcpServer.after_recv", on_after_recv)
        print(maybe_color("[SERVER] Connection hooks installed", GREEN, color_enabled))
    except Exception as exc:
        print(f"[SERVER] Warning: could not install connection hooks: {exc}")

    def shutdown_handler(signum, frame):
        """Gracefully stop server when Ctrl+C or termination signal is received."""
        del signum, frame
        print("\n[SERVER] Stopping...")
        server.stop()
        print("[SERVER] Stopped")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Keep the main thread alive while the server handles requests internally.
    try:
        while True:
            cleanup_idle_clients()
            current_values = tuple(slave.get_values("hr", 0, 40))
            changed_offsets = collect_changed_offsets(previous_values, current_values)

            # When any register changes, print a fresh full-table snapshot.
            if changed_offsets:
                changed_text = ", ".join(
                    f"#{offset_to_register_number(offset)}" for offset in sorted(changed_offsets)
                )
                print(maybe_color(f"[{timestamp()}] VALUE CHANGE -> {changed_text}", GREEN, color_enabled))
                active_list = [f"{addr[0]}:{addr[1]}" for addr in active_clients.values()]
                print(
                    render_register_table(
                        current_values,
                        changed_offsets,
                        color_enabled,
                        active_clients=active_list,
                    )
                )
                previous_values = current_values

            time.sleep(0.2)
    except KeyboardInterrupt:
        shutdown_handler(None, None)


if __name__ == "__main__":
    main()
