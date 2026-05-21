"""
Modbus TCP Register Monitor using modbus_tk.

This monitor reads all holding registers #40001-#40040 from a Modbus TCP server
and prints them in a neatly aligned ASCII table on each polling interval.
"""

import argparse
import time
from datetime import datetime
from typing import Sequence, Tuple

from modbus_tk import defines as cst
from modbus_tk import modbus_tcp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitor all Modbus holding registers #40001-#40040."
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Modbus server IP address (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=502,
        help="Modbus server port (default: 502).",
    )
    parser.add_argument(
        "--slave-id",
        type=int,
        default=1,
        help="Target slave ID (default: 1).",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds (default: 1.0).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Socket timeout in seconds (default: 5.0).",
    )
    return parser.parse_args()


def read_all_registers(
    master: modbus_tcp.TcpMaster, slave_id: int
) -> Tuple[int, ...]:
    return tuple(
        master.execute(
            slave=slave_id,
            function_code=cst.READ_HOLDING_REGISTERS,
            starting_address=0,
            quantity_of_x=40,
        )
    )


def render_register_table(title: str, values: Sequence[int]) -> str:
    col_count = 4
    row_count = 10
    cell_width = 18

    horizontal = "+" + "+".join(["-" * cell_width] * col_count) + "+"
    lines = [horizontal]
    lines.append("|" + title.center(cell_width * col_count + (col_count - 1)) + "|")
    lines.append(horizontal)

    for row in range(row_count):
        row_cells = []
        for col in range(col_count):
            offset = row + (row_count * col)
            reg_num = 40001 + offset
            cell_text = f"#{reg_num}: {values[offset]}".ljust(cell_width)
            row_cells.append(cell_text)

        lines.append("|" + "|".join(row_cells) + "|")
        lines.append(horizontal)

    return "\n".join(lines)


def main() -> None:
    args = parse_args()

    master = modbus_tcp.TcpMaster(host=args.host, port=args.port)
    master.set_timeout(args.timeout)

    print(
        f"[MONITOR] Connecting to {args.host}:{args.port}, slave ID {args.slave_id}"
    )
    print(f"[MONITOR] Polling interval: {args.interval:.2f}s")

    initial_values = read_all_registers(master, args.slave_id)
    print(render_register_table("[MONITOR] Startup snapshot of #40001-#40040", initial_values))

    try:
        while True:
            time.sleep(args.interval)
            current_values = read_all_registers(master, args.slave_id)
            print(render_register_table(
                f"[MONITOR] Polled snapshot at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                current_values,
            ))
    except KeyboardInterrupt:
        print("\n[MONITOR] Stopped by user")
    except Exception as exc:
        print(f"[MONITOR] Error: {exc}")
    finally:
        try:
            master.close()
            print("[MONITOR] Connection closed")
        except Exception as exc:
            print(f"[MONITOR] Error closing connection: {exc}")


if __name__ == "__main__":
    main()
