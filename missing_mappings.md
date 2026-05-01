# Missing Mappings

The server uses `toliss_a321_catalog.json` for ToLiss/AirbusFBW names and direct X-Plane Web API lookup for verified standard `sim/*` names. Items marked ✅ were previously missing and are now covered.

## Newly Covered ✅

- ✅ `read_flight_state.GS`: `sim/flightmodel/position/groundspeed`, converted from m/s to kt with `* 1.94384`.
- ✅ `read_flight_state.lat/lon`: standard `sim/flightmodel/position/latitude` and `sim/flightmodel/position/longitude`.
- ✅ `read_engines.n2`: `sim/cockpit2/engine/indicators/N2_percent`, array index 0/1.
- ✅ `read_engines.oil_temp`: `sim/cockpit2/engine/indicators/oil_temperature_deg_C`, array index 0/1.
- ✅ `read_radios` COM/NAV/ADF active/standby where standard refs exist.
- ✅ `set_radio` COM/NAV/ADF active/standby where standard refs exist. `set_active` writes standby then swaps by exchanging active/stby values.
- ✅ `read_atc.tcas.mode`: `sim/cockpit2/radios/actuators/tcas_sys_select`.
- ✅ `read_atc.tcas.filter`: `sim/cockpit2/radios/actuators/tcas_filter`.
- ✅ `set_atc(tcas_mode)`: writes `tcas_sys_select`.
- ✅ `set_atc(tcas_filter)`: writes `tcas_filter`.
- ✅ `set_brightness` pfd/nd/ecam best-effort: tries `AirbusFBW/DUBrightness` first, falls back to `sim/cockpit2/electrical/instrument_brightness_ratio`.
- ✅ `read_pedestal.flap_handle`: `sim/flightmodel/controls/flaprqst * 4`, rounded to integer 0-4.
- ✅ `read_pedestal.flap_actual`: `sim/flightmodel2/controls/flap_handle_deploy_ratio`.
- ✅ `read_pedestal.slat_actual`: average of `AirbusFBW/SlatPositionLWing` and `AirbusFBW/SlatPositionRWing`; avoids `SlatRequestPos` sentinel `-1`.
- ✅ `set_pedestal.flap`: command sequence using `sim/flight_controls/flaps_up` / `sim/flight_controls/flaps_down`; no direct PATCH to read-only flap indicator.
- ✅ `set_pedestal.gear`: command-first using `sim/flight_controls/landing_gear_up` / `landing_gear_down`.
- ✅ `set_pedestal.autobrake`: command-only indicator/button pattern using `AirbusFBW/AbrkLo`, `AirbusFBW/AbrkMed`, `AirbusFBW/AbrkMax`, and `toliss_airbus/abrk/pos_disarm`.
- ✅ `set_pedestal.speedbrake`: command sequence using `sim/flight_controls/speed_brakes_up_one` / `speed_brakes_down_one`.
- ✅ `set_pedestal.parking_brake`: command-first using ToLiss park brake commands.
- ✅ `set_pedestal.engine_master_1/2`: command-only using ToLiss engine master commands.
- ✅ X-Plane dataref cache stores `is_writable`; direct PATCH paths reject read-only datarefs before writing.
- ✅ `read_ecam`: decodes ToLiss fixed-length byte-array ECAM text datarefs returned by the Web API as base64, including EWD `AirbusFBW/EWD{N}{color}Text` and SD `AirbusFBW/SDline{N}{color}` patterns. It strips null padding, omits empty color slots, preserves multiple color segments per line, and keeps `current_sd_page`.
- ✅ `read_mcdu`: MCDU1/MCDU2 display decoding from `AirbusFBW/MCDU{1|2}{title|stitle|labelN|contN|scontN|sp}{color}` datarefs, including top-level scratchpad text.
- ✅ `mcdu_press`: MCDU1/MCDU2 key command mapping from catalog entries such as `AirbusFBW/MCDU1KeyA`, `AirbusFBW/MCDU1LSK1L`, `AirbusFBW/MCDU1DirTo`, and `AirbusFBW/MCDU1SlewRight`. Supports text decomposition, LSK follow-up, and 50 ms command spacing.

## Remaining

## read_flight_state

- `radalt`: mapped to `toliss_airbus/pfdoutputs/captain/show_land_ref_alt`, which appears to be a display flag/value candidate rather than a clear radio-altitude value.

## read_overhead_full

- Interior/exterior light details are partly exposed as raw arrays because per-light dataref semantics are not clear in the catalog.
- `apu.start`: no clear APU start-state dataref found, only commands and APU availability/master related datarefs.
- Some electrical/fuel/hydraulic values are raw ToLiss arrays because index semantics are not documented in the catalog.

## read_radios

- ADF standby frequencies are not exposed by the verified mappings, so ADF `stby` remains `None`.
- ACP detailed fields `channel`, `rx`, `tx`, `int_rad`, `volume`, `loudspeaker` are exposed only as raw ACP arrays/switch data.

## read_atc

- `ident`: no clear readable ident-state dataref found.
- `tcas.range`: standard dataref unavailable; ND range appears coupled to ToLiss ND/range state and needs aircraft-specific confirmation.

## read_autoflight

- `exped`: catalog exposes `AirbusFBW/EXPEDbutton` as a command only; no readable EXPED active/armed dataref found.

## set_brightness

- pfd/nd/ecam index mapping uses best-effort indexes and needs cockpit validation: `pfd=0`, `nd_inner=1`, `nd_outer=2`, `ecam_upper=3`, `ecam_lower=4`.
- `mcdu`: brightness via `set_brightness(display="mcdu")` is still intentionally not implemented; use `mcdu_press(..., keys=["BRTUP"])` or `["BRTDN"]` for cockpit MCDU brightness keys.

## set_antiice

- `probe`: catalog has `AirbusFBW/PRobeHeatLights` but no clear probe anti-ice write command/dataref.
- `auto` state for engine/wing anti-ice uses toggle where no explicit auto command exists.

## set_pneumatic

- `ram_air`: only `AirbusFBW/RamAirValveSD` was found; direct write behavior may not match cockpit switch control.
- `bleed1`, `bleed2`, `xbleed`: direct datarefs are used because explicit ToLiss commands were not found.

## set_electrical

- `gen1`, `gen2`, `apu_gen`, `ac_ess_feed`, `galley`: no clear explicit write command found.
- `ext_pwr`: only toggle command is used; explicit on/off for A/B external power exists but not a single obvious `ext_pwr` state mapping.

## set_fuel

- `cp2`, `xfeed`, `acttrns`, `actmode`: no clear direct command mapping found for the requested names.

## set_hydraulic

- `g_eng1`, `g_eng2`, `b_eng1`, `b_eng2`, `y_eng1`, `y_eng2`, `ptu`: no clear explicit hydraulic pump/PTU write command found.
- `rat`: mapped to `toliss_airbus/hydcommands/PressRATReleaseButton`.

## set_radio

- ADF `set_stby` and `swap`: no verified ADF standby dataref provided.

## set_acp

- Only VHF receive button commands for ACP1/ACP2 are mapped.
- `toggle_tx`, `toggle_int_rad`, `loudspeaker`, `volume`, and non-VHF channels lack clear command/dataref mappings.

## set_atc

- `tcas_range`: standard dataref unavailable; ND range and ToLiss TCAS display range appear coupled, ToLiss-specific mapping still needs confirmation.
- `ident` uses `sim/transponder/transponder_ident` command found in catalog.

## set_pedestal

- `speedbrake.armed`: no confirmed armed-state readback dataref is mapped. `set_pedestal("speedbrake", "armed"|"disarmed")` intentionally raises `MappingError` until `debug_search_xplane_names("speedbrake")` or `"spoiler"` identifies a reliable readback dataref.
- `speedbrake`: numeric handle readback still uses deployed-state dataref candidate rather than a confirmed handle-position dataref.
- Autobrake uses the ToLiss indicator/button pattern. The only readable indicators found are `AirbusFBW/ABrkLoButtonAnim`, `AirbusFBW/ABrkMedButtonAnim`, and `AirbusFBW/ABrkMaxButtonAnim`. Local verification fired commands successfully, but indicators stayed off in the current aircraft state, likely due ToLiss logic/condition gating.

## set_efis

- `baro_unit`: direct dataref write used; no explicit toggle command found.
- `nd_mode`, `nd_range`: direct dataref writes used; no explicit knob rotation sequence implemented from catalog.

## set_ecam

- `emer_canc`: no clear emergency cancel command found.
- `elec` maps to AC electrical page (`SelectElecACPage`) because both AC/DC page commands exist and the high-level page name is ambiguous.

## set_weather_radar

- Weather radar mode/gain/tilt/multiscan/gcs use direct datarefs. Catalog also has left/right radar switch commands, but no complete high-level command sequence was inferable.
