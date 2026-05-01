# ToLiss A321 Co-pilot MCP

Python MCP server exposing high-level ToLiss A321 co-pilot tools over the X-Plane 12.1.4+ local Web API.

## Requirements

- Python 3.11+
- X-Plane 12.1.4+ running on the same machine
- X-Plane Web API enabled on `localhost:8086`
- ToLiss A321 loaded before invoking tools

Install:

```powershell
python -m pip install -r requirements.txt
```

Run:

```powershell
python toliss_copilot_mcp.py
```

By default this runs on stdio for MCP client compatibility.

Useful run options:

```powershell
python toliss_copilot_mcp.py --transport streamable-http --host 0.0.0.0 --port 8000 --path /mcp
python toliss_copilot_mcp.py --transport streamable-http --ssl-certfile cert.pem --ssl-keyfile key.pem
```

The module imports without X-Plane running. Tool calls load the Web API dataref/command ID cache once and then use IDs directly.

## Refactor Smoke Tests

After moving tools between modules, run the import/tool-registration smoke test:

```powershell
python -c "import toliss_copilot_mcp; print(toliss_copilot_mcp.smoke_test())"
```

With X-Plane and the ToLiss aircraft running, run live read-tool smoke checks:

```powershell
python -c "import toliss_copilot_mcp; print(toliss_copilot_mcp.smoke_test(live=True))"
```

For undefined-name static checks:

```powershell
python -m pip install ruff
python -m ruff check --select F821 .
```

## Claude Code MCP

Example registration:

```json
{
  "mcpServers": {
    "toliss-a321-copilot": {
      "command": "python",
      "args": ["C:\\Users\\coolguy\\xplane-claude\\toliss_copilot_mcp.py"],
      "cwd": "C:\\Users\\coolguy\\xplane-claude"
    }
  }
}
```

## Claude Desktop MCP

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "toliss-a321-copilot": {
      "command": "python",
      "args": ["C:\\Users\\coolguy\\xplane-claude\\toliss_copilot_mcp.py"]
    }
  }
}
```

## Exposed Tools

Read tools: `read_flight_state`, `read_fcu`, `read_fma`, `read_autoflight`, `read_engines`, `read_overhead_full`, `read_pedestal`, `read_radios`, `read_atc`, `read_ecam`, `read_efis`, `read_weather_radar`.

Write tools: `grab_sidestick`, `release_sidestick`, `set_sidestick`, `fcu_dial_turn`, `fcu_dial_pull`, `fcu_dial_push`, `set_fcu_mode`, `set_fcu` (deprecated compatibility wrapper), `set_autoflight`, `set_lights`, `set_brightness`, `set_antiice`, `set_pneumatic`, `set_apu`, `set_electrical`, `set_fuel`, `set_hydraulic`, `set_flight_computer`, `set_trim_stab`, `set_speedbrake_inflight`, `set_radio`, `set_acp`, `set_atc`, `set_pedestal`, `set_efis`, `set_ecam`, `set_weather_radar`.

The implementation also exposes dedicated ECAM SD page read tools such as `read_sd_apu`, `read_sd_bleed`, and related system pages.
