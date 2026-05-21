# Modbus TCP Example with modbus_tk

This tutorial explains how to run a Modbus TCP server and client using Python and `modbus_tk`.

**Important:** In this project, `modbus_server.py` is intentionally used as a **PLC simulator**.
It is not just a generic server sample. It behaves like a simple PLC register device so you can test HMI/SCADA/client read-write workflows.

The example is split into two parts:
1. A server (PLC simulator) exposing holding registers `#40001` to `#40040` for both read and write.
2. A client that can read and write all those registers.

## PLC Simulation Goal

`modbus_server.py` is designed to simulate a PLC communication endpoint:

- It listens on Modbus TCP standard port `502`.
- It provides a fixed holding-register area `#40001~#40040`.
- It accepts read and write requests from external clients.
- It prints request logs and register table updates like a monitoring panel.

Use this server when you need a controllable PLC-like target for development, integration, and communication testing.

## 1. Project Structure

Create or confirm the following structure:

```text
modbus_example/
  modbus_server.py
  modbus_client.py
  requirements.txt
  doc/
    modbus_tk_tcp_tutorial.md
```

## 2. Install Dependencies

From the project root:

```bash
pip install -r requirements.txt
```

## 3. Important Modbus Address Mapping

Modbus holding registers are often shown as `4xxxx` numbers in manuals.
Inside most libraries (including `modbus_tk`), addresses are zero-based offsets.

- `#40001` -> offset `0`
- `#40040` -> offset `39`

In this project, server block definition uses:
- start address: `0`
- quantity: `40`

That exactly matches `#40001` to `#40040`.

## 4. Run the Modbus Server

### Command

```bash
python modbus_server.py --host 0.0.0.0 --port 502 --slave-id 1
```

### What it does

- Starts a Modbus TCP server on port `502`.
- Creates slave ID `1`.
- Adds one holding-register block with 40 registers.
- Allows clients to read and write those registers.
- Prints every incoming Modbus read/write action in the console.
- Re-renders a full table of `#40001~#40040` whenever any value changes.
- Highlights changed registers with a different color.
- Simulates PLC register behavior for client-side testing.

### PLC-like Screen Behavior

The server is designed to look like a simple PLC monitor page in terminal output.

- Every request is logged with timestamp and function information.
   - Read example: function code `3` (read range)
   - Write example: function code `6` or `16`
- If internal values change, the server prints the complete register table again.
- Changed register cells are shown in red for quick visual inspection.

### Notes

- Port `502` is the standard Modbus TCP port.
- On many systems, opening port `502` requires administrator/root privileges.
  - On Windows, run terminal as Administrator if bind fails.

## 5. Run the Modbus Client

Open another terminal and run:

```bash
python modbus_client.py --host 127.0.0.1 --port 502 --slave-id 1
```

### What it does

- Connects to the Modbus server.
- Prints one startup snapshot for `#40001~#40040`.
- Enters a continuous test loop.
- Every second, it targets one register and performs:
   - read current value
   - write next value (`old + 1`, modulo `65536`)
   - read back for verification
- Cycles register target in order:
   - `#40001`, `#40002`, ..., `#40040`, then back to `#40001`.

### Useful Client Options

- `--interval 1.0`
   - Delay between each test cycle in seconds.
- `--start-register 40001`
   - First register to start cyclic test from (valid range `40001~40040`).

Example:

```bash
python modbus_client.py --host 127.0.0.1 --port 502 --slave-id 1 --interval 1.0 --start-register 40001
```

## 6. How to Adapt for Real Devices

- Change `--host` to the PLC/device IP.
- Keep `--slave-id` aligned with the target unit ID.
- Replace the demo write values with your real process values.
- Wrap reads/writes in loops and exception handling for production monitoring/control.

## 7. Quick Troubleshooting

1. Connection refused:
   - Make sure server is running.
   - Verify IP and port.
2. Timeout:
   - Check firewall rules and network route.
   - Increase client `--timeout` value.
3. Wrong data:
   - Re-check offset mapping (`#40001` = offset `0`).
4. Permission error on port 502:
   - Start terminal with administrator/root privileges.

## 8. Function Codes Used in This Example

- `3` (`READ_HOLDING_REGISTERS`) for reading holding registers.
- `6` (`WRITE_SINGLE_REGISTER`) for writing one register.
- `16` (`WRITE_MULTIPLE_REGISTERS`) for writing a register range.

This is enough for most basic Modbus register read/write workflows.
