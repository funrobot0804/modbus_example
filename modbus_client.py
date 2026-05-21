"""
Modbus TCP Client Example using modbus_tk.

This client continuously performs test traffic against holding registers
#40001 to #40040 from a Modbus TCP server.

Behavior in this version:
- Every second, it targets exactly one register.
- For that register, it performs: read -> write -> read-back verification.
- It cycles through #40001, #40002, ..., #40040, then repeats.

Address mapping note:
- Register #40001 is internal offset 0.
- Register #40040 is internal offset 39.
"""

import argparse
import time
from typing import Tuple

from modbus_tk import defines as cst
from modbus_tk import modbus_tcp


def parse_args() -> argparse.Namespace:
    """Parse command-line options for server connection and slave ID."""
    parser = argparse.ArgumentParser(
        description="Modbus TCP cyclic read/write tester for #40001-#40040."
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
        "--timeout",
        type=float,
        default=5.0,
        help="Socket timeout in seconds (default: 5.0).",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between each register test cycle (default: 1.0).",
    )
    parser.add_argument(
        "--start-register",
        type=int,
        default=40001,
        help="Start register number in range 40001~40040 (default: 40001).",
    )
    return parser.parse_args()


def reg_number_to_offset(register_number: int) -> int:
    """
    Convert a human register number (e.g., 40001) into zero-based offset.

    Example:
    - 40001 -> 0
    - 40040 -> 39
    """
    return register_number - 40001


def read_all_registers(master: modbus_tcp.TcpMaster, slave_id: int) -> Tuple[int, ...]:
    """Read 40 holding registers corresponding to #40001-#40040."""
    return master.execute(
        slave=slave_id,
        function_code=cst.READ_HOLDING_REGISTERS,
        starting_address=0,
        quantity_of_x=40,
    )


def read_single_register(
    master: modbus_tcp.TcpMaster,
    slave_id: int,
    register_number: int,
) -> int:
    """Read one holding register and return the current value."""
    offset = reg_number_to_offset(register_number)
    result = master.execute(
        slave=slave_id,
        function_code=cst.READ_HOLDING_REGISTERS,
        starting_address=offset,
        quantity_of_x=1,
    )
    return int(result[0])


def write_single_register(
    master: modbus_tcp.TcpMaster,
    slave_id: int,
    register_number: int,
    value: int,
) -> None:
    """Write one holding register using function code 6 (Write Single Register)."""
    offset = reg_number_to_offset(register_number)
    master.execute(
        slave=slave_id,
        function_code=cst.WRITE_SINGLE_REGISTER,
        starting_address=offset,
        output_value=value,
    )


def print_registers(values: Tuple[int, ...]) -> None:
    """Display register values in a readable register-number format."""
    print("\n[CLIENT] Register Snapshot (#40001-#40040)")
    for i, value in enumerate(values):
        register_number = 40001 + i
        print(f"  #{register_number}: {value}")


def main() -> None:
    """Run continuous 1-second register read/write test loop."""
    args = parse_args()

    if not 40001 <= args.start_register <= 40040:
        raise ValueError("--start-register must be between 40001 and 40040")

    # Create a Modbus TCP master (client).
    master = modbus_tcp.TcpMaster(host=args.host, port=args.port)
    master.set_timeout(args.timeout)

    print(f"[CLIENT] Connected to {args.host}:{args.port}, slave ID {args.slave_id}")
    print(
        "[CLIENT] Continuous test mode: every "
        f"{args.interval:.3f}s read/write one register in #40001~#40040"
    )

    # Print startup snapshot once so test baseline is visible.
    startup_values = read_all_registers(master, args.slave_id)
    print("[CLIENT] Startup snapshot:")
    print_registers(startup_values)

    register_number = args.start_register

    try:
        while True:
            # 1) Read current value of exactly one target register.
            old_value = read_single_register(master, args.slave_id, register_number)

            # 2) Generate a deterministic next value for easy traceability.
            #    Limiting to 16-bit unsigned range keeps values valid for Modbus register.
            new_value = (old_value + 1) % 65536

            # 3) Write the new value.
            write_single_register(master, args.slave_id, register_number, new_value)

            # 4) Read back to verify what server now stores.
            verify_value = read_single_register(master, args.slave_id, register_number)

            print(
                f"[CLIENT] #{register_number} old={old_value} "
                f"write={new_value} readback={verify_value}"
            )

            # Move to next register in #40001~#40040 and wrap around.
            register_number += 1
            if register_number > 40040:
                register_number = 40001

            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[CLIENT] Stopped by user")
    finally:
        try:
            master.close()
            print("[CLIENT] Connection closed")
        except Exception as exc:
            print(f"[CLIENT] Error closing connection: {exc}")


if __name__ == "__main__":
    main()
