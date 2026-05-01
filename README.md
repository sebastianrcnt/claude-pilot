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

Write tools: `fcu_dial_turn`, `fcu_dial_pull`, `fcu_dial_push`, `set_fcu` (deprecated compatibility wrapper), `set_autoflight`, `set_lights`, `set_brightness`, `set_antiice`, `set_pneumatic`, `set_electrical`, `set_fuel`, `set_hydraulic`, `set_radio`, `set_acp`, `set_atc`, `set_pedestal`, `set_efis`, `set_ecam`, `set_weather_radar`.

The original task text says "26 tools" but also corrects the read list to 12 and keeps 16 writes. This implementation exposes all 28 requested tools.
