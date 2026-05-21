# Modbus TCP PLC Simulator Example (modbus_tk)

This project provides a ready-to-run Modbus TCP example set:

- `modbus_server.py`: Modbus server that simulates a PLC
- `modbus_client.py`: cyclic read/write test client
- `doc/modbus_tk_tcp_tutorial.md`: detailed tutorial document

The goal is to quickly build a local PLC-like test environment for HMI/SCADA/integration validation.

## 1. Features

- Server simulates PLC holding registers `#40001 ~ #40040`
- Uses Modbus TCP port `502`
- Client tests one register every second (read -> write -> readback)
- Server prints every Modbus request
- Server redraws the full table when any register value changes
- Changed registers are highlighted in a different color

## 2. Project Structure

```text
modbus_example/
  README.md
  requirements.txt
  modbus_server.py
  modbus_client.py
  doc/
    modbus_tk_tcp_tutorial.md
```

## 3. Requirements

- Python 3.8+
- Packages:
  - `modbus-tk==1.1.5`
  - `colorama==0.4.6`

Install dependencies:

```bash
pip install -r requirements.txt
```

## 4. Quick Start

### Step A: Start Server (Terminal 1)

```bash
python modbus_server.py --host 127.0.0.1 --port 502 --slave-id 1
```

After startup, the server prints:

- listening address and port
- PLC register table (`#40001~#40040`)
- request logging hook status

### Step B: Start Client (Terminal 2)

```bash
python modbus_client.py --host 127.0.0.1 --port 502 --slave-id 1 --interval 1.0 --start-register 40001
```

Client behavior:

- reads all registers once at startup (startup snapshot)
- processes one register every `interval` seconds
- workflow: read current -> write new value -> readback
- cycles target register from `#40001` to `#40040`, then wraps to `#40001`

## 5. Modbus Address Mapping

This project uses common 4xxxx register notation; `modbus_tk` still uses zero-based offsets internally:

- `#40001` -> offset `0`
- `#40040` -> offset `39`

## 6. Server Output Behavior

The server is a PLC simulator with the following output behavior:

- prints timestamp + function code + range/value for every request
- prints `VALUE CHANGE -> #40xxx` when values change
- redraws the full 40-register table after changes
- uses red color to highlight changed cells

## 7. Development History (Summary)

1. Initial Modbus Server/Client implementation
- Server created holding register block `#40001~#40040`
- Client could read/write the same register range

2. Added tutorial documentation
- Added `doc/modbus_tk_tcp_tutorial.md`
- Documented setup, execution, mapping, and troubleshooting

3. Enhanced server as a PLC simulator
- Explicitly defined server role as PLC simulation
- Added request logs (read/write)
- Added table-based monitor output

4. Converted client to cyclic stress-test mode
- One-register cycle per second
- read -> write -> readback for each cycle
- Added `--interval` and `--start-register`

5. Clarified documentation wording
- Clearly documented server purpose as PLC simulation

6. Fixed table alignment issue caused by ANSI colors
- Problem: applying color then `ljust` broke visible column alignment
- Fix: apply `ljust` first, then wrap with color codes

7. Resolved common no-update confusion during testing
- Multiple Python processes could listen/connect on port `502`
- Client could target another server instance, not the visible one

## 8. Common Issues

### 1) `ModuleNotFoundError: No module named 'modbus_tk'`

Cause: running with a Python interpreter where dependencies are not installed.

Solution:

```bash
python -m pip install -r requirements.txt
```

If you have multiple Python environments (Anaconda / system Python / venv), make sure server and client use the same interpreter.

### 2) Server does not show value changes

Check first:

- whether multiple servers are running in different terminals
- whether client is connected to the same `host:port`
- whether `netstat -ano | findstr :502` shows duplicate listeners

### 3) Port 502 permission issue

- Windows may require Administrator privileges to bind port `502`
- For testing, you can use a non-privileged port (for example, `--port 1502`)

## 9. Stop Running Processes

Press `Ctrl + C` in server/client terminals to stop gracefully.

For forced termination on Windows:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'modbus_example' } |
  Select-Object ProcessId, CommandLine
```

Then stop by PID:

```powershell
Stop-Process -Id <PID> -Force
```

## 10. GitHub Upload Checklist

Recommended files:

- `README.md`
- `requirements.txt`
- `modbus_server.py`
- `modbus_client.py`
- `doc/modbus_tk_tcp_tutorial.md`

Recommended `.gitignore` entries:

```gitignore
.venv/
__pycache__/
*.pyc
```

---

If you want, I can also add a `.gitignore` file and a short release-style changelog section next.
