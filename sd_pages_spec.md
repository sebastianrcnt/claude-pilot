# ToLiss A321 ECAM SD Page Dataref Mapping Spec

This document is a pre-implementation mapping spec for future page-specific tools such as `read_sd_hyd()` and `read_sd_eng()`.

Assumptions:
- ToLiss draws ECAM SD pages graphically. `AirbusFBW/SDline*` byte-array datarefs may exist in the catalog, but they are not a reliable source for rendered SD page text.
- Page selectors such as `AirbusFBW/SDHYD`, `AirbusFBW/SDENG`, `AirbusFBW/SDFUEL`, and `AirbusFBW/SDELEC` are treated as page display or page button state datarefs, not as complete page content.
- Array index meanings are inferred from Airbus convention and dataref names. Index mappings marked medium or low need live validation.
- Units are estimated from Airbus SD conventions and dataref names. Unknown units are explicitly marked.
- STS page is intentionally out of scope: ToLiss does not expose STATUS line text via datarefs.
- Some datarefs are referenced by multiple pages (e.g., pack switches in BLEED and COND). The implementation should use a time-based shared cache (TTL ~1s) so consecutive `read_sd_*` calls do not re-fetch the same dataref.

## SD ENG page

### Proposed read_sd_eng() response structure

```json
{
  "engines": [
    {
      "n1_percent": 22.1,
      "epr": null,
      "egt_deg_c": 410,
      "fuel_flow": 320,
      "oil_pressure": 42,
      "oil_temperature_deg_c": null,
      "start_valve_open": false,
      "lp_fuel_valve_open": true,
      "reverse_deployed": false,
      "master_switch_on": true
    }
  ],
  "engine_mode": "norm",
  "thrust_rating": {"mode": "CLB", "n1_limit_percent": 88.5, "epr_limit": null},
  "page_active": true
}
```

### Dataref mappings

| Dataref | Field path | Estimated meaning | Unit | Confidence |
|---|---|---|---|---|
| AirbusFBW/SDENG | page_active | ENG SD page selected/available flag | bool/enum | medium |
| AirbusFBW/anim/ENGN1Speed | engines[i].n1_percent | Engine N1 indication, index 0/1 | % | high |
| AirbusFBW/ENGEPRArray | engines[i].epr | Engine pressure ratio, index 0/1 if engine variant uses EPR | ratio | high |
| AirbusFBW/ENGEGTArray | engines[i].egt_deg_c | Exhaust gas temperature, index 0/1 | deg C | high |
| AirbusFBW/ENGFuelFlowArray | engines[i].fuel_flow | Engine fuel flow, index 0/1 | kg/h or sim unit | medium |
| AirbusFBW/ENGOilPressArray | engines[i].oil_pressure | Oil pressure, index 0/1 | psi | medium |
| AirbusFBW/StartValveArray | engines[i].start_valve_open | Engine start valve state, index 0/1 | bool/0-1 | high |
| AirbusFBW/ENGFuelLPValveArray | engines[i].lp_fuel_valve_open | Engine LP fuel valve state, index 0/1 | bool/0-1 | high |
| AirbusFBW/ENGRevArray | engines[i].reverse_deployed | Thrust reverser deployed/position, index 0/1 | 0-1 | high |
| AirbusFBW/ENG1MasterSwitch | engines[0].master_switch_on | Engine 1 master switch state | bool/0-1 | high |
| AirbusFBW/ENG2MasterSwitch | engines[1].master_switch_on | Engine 2 master switch state | bool/0-1 | high |
| AirbusFBW/ENGModeSwitch | engine_mode | Engine mode selector | enum | high |
| AirbusFBW/ENGModeArray | engines[i].mode | Per-engine operating/start mode, index 0/1 | enum | medium |
| AirbusFBW/THRRatingN1 | thrust_rating.n1_limit_percent | N1 thrust limit/rating | % | high |
| AirbusFBW/THRRatingEPR | thrust_rating.epr_limit | EPR thrust limit/rating | ratio | high |
| AirbusFBW/THRRatingType | thrust_rating.mode | Thrust rating type | enum | medium |
| AirbusFBW/THRRatingType | thrust_rating.raw_type | Raw thrust rating enum | enum | high |
| AirbusFBW/EngineType | engine_type | Engine type selector/string candidate | enum/string | medium |
| AirbusFBW/EngineTypeIndex | engine_type_index | Engine type index | enum | medium |

### Open questions

- `ENGFuelFlowArray` units need live validation against the cockpit display.
- Oil temperature is expected on the ENG SD page, but the catalog candidate is not obvious. Standard X-Plane `sim/cockpit2/engine/indicators/oil_temperature_deg_C` can supplement later, but this spec only maps catalog datarefs.
- `ENGModeArray` versus `ENGModeSwitch` semantics need validation.
- EPR fields may be irrelevant for PW/CFM N1 variants but should remain nullable.

### Catalog gaps

- No clear ToLiss catalog dataref found for engine oil temperature.
- No clear ToLiss catalog dataref found for engine vibration.
- No clear dataref found for starter duct pressure or ignition A/B indications.

## SD BLEED page

### Proposed read_sd_bleed() response structure

```json
{
  "engines": [
    {"bleed_valve_open": true, "hp_valve_open": false, "anti_ice_on": false}
  ],
  "apu_bleed_open": false,
  "xbleed": {"position": "auto", "valve_open": false},
  "packs": [
    {"switch_on": true, "flow": 1.0, "fcv_open": true, "temperature_deg_c": 12}
  ],
  "duct_pressure": {"left_psi": 36, "right_psi": 36},
  "ram_air": {"switch_on": false, "valve_open": false},
  "page_active": true
}
```

### Dataref mappings

| Dataref | Field path | Estimated meaning | Unit | Confidence |
|---|---|---|---|---|
| AirbusFBW/SDBLEED | page_active | BLEED SD page selected/available flag | bool/enum | medium |
| AirbusFBW/ENG1BleedSwitch | engines[0].bleed_switch_on | Engine 1 bleed pushbutton/switch state | bool/0-1 | high |
| AirbusFBW/ENG2BleedSwitch | engines[1].bleed_switch_on | Engine 2 bleed pushbutton/switch state | bool/0-1 | high |
| AirbusFBW/ENG1BleedInd | engines[0].bleed_valve_open | Engine 1 bleed indication/valve state | bool/0-1 | high |
| AirbusFBW/ENG2BleedInd | engines[1].bleed_valve_open | Engine 2 bleed indication/valve state | bool/0-1 | high |
| AirbusFBW/ENG1HPBleedInd | engines[0].hp_valve_open | Engine 1 high-pressure bleed valve indication | bool/0-1 | high |
| AirbusFBW/ENG2HPBleedInd | engines[1].hp_valve_open | Engine 2 high-pressure bleed valve indication | bool/0-1 | high |
| AirbusFBW/ENG1AISwitch | engines[0].anti_ice_on | Engine 1 anti-ice switch state | bool/0-1 | high |
| AirbusFBW/ENG2AISwitch | engines[1].anti_ice_on | Engine 2 anti-ice switch state | bool/0-1 | high |
| AirbusFBW/ENG1AILights | engines[0].anti_ice_light | Engine 1 anti-ice light/indication | bool/enum | medium |
| AirbusFBW/ENG2AILights | engines[1].anti_ice_light | Engine 2 anti-ice light/indication | bool/enum | medium |
| AirbusFBW/APUBleedSwitch | apu_bleed_switch_on | APU bleed pushbutton/switch state | bool/0-1 | high |
| AirbusFBW/APUBleedInd | apu_bleed_open | APU bleed valve indication | bool/0-1 | high |
| AirbusFBW/XBleedSwitch | xbleed.position | Crossbleed selector/switch position | enum | high |
| AirbusFBW/XBleedInd | xbleed.valve_open | Crossbleed valve indication | bool/0-1 | high |
| AirbusFBW/BleedIntercon | xbleed.interconnect_open | Bleed interconnect state | bool/0-1 | medium |
| AirbusFBW/LeftBleedPress | duct_pressure.left_psi | Left bleed duct pressure | psi | high |
| AirbusFBW/RightBleedPress | duct_pressure.right_psi | Right bleed duct pressure | psi | high |
| AirbusFBW/Pack1Switch | packs[0].switch_on | Pack 1 switch state (shared with: COND) | bool/0-1 | high |
| AirbusFBW/Pack2Switch | packs[1].switch_on | Pack 2 switch state (shared with: COND) | bool/0-1 | high |
| AirbusFBW/Pack1FCVInd | packs[0].fcv_open | Pack 1 flow control valve indication | bool/0-1 | high |
| AirbusFBW/Pack2FCVInd | packs[1].fcv_open | Pack 2 flow control valve indication | bool/0-1 | high |
| AirbusFBW/Pack1Flow | packs[0].flow | Pack 1 flow (shared with: COND) | normalized/unknown | medium |
| AirbusFBW/Pack2Flow | packs[1].flow | Pack 2 flow (shared with: COND) | normalized/unknown | medium |
| AirbusFBW/Pack1Temp | packs[0].temperature_deg_c | Pack 1 temperature (shared with: COND) | deg C | high |
| AirbusFBW/Pack2Temp | packs[1].temperature_deg_c | Pack 2 temperature (shared with: COND) | deg C | high |
| AirbusFBW/PackFlowSel | pack_flow_selector | Pack flow selector | enum | high |
| AirbusFBW/RamAirSwitch | ram_air.switch_on | Ram air switch state | bool/0-1 | high |
| AirbusFBW/RamAirValveSD | ram_air.valve_open | Ram air valve indication on SD | bool/0-1 | high |
| AirbusFBW/RamAirSwitchLights | ram_air.switch_lights | Ram air switch light state | enum | medium |

### Open questions

- Confirm whether `ENG*BleedInd` is valve position or light/availability indication.
- `Pack*Flow` scaling is unknown and needs comparison to the SD graphic.
- `XBleedSwitch` position enum needs exact decoding, likely shut/auto/open.

### Catalog gaps

- No explicit precooler temperature dataref found.
- No explicit leak/fault state datarefs found for bleed ducts.
- No clear pack outlet/inlet pressure split beyond flow and temperature.

## SD PRESS page

### Proposed read_sd_press() response structure

```json
{
  "cabin_altitude_ft": 2500,
  "cabin_vs_fpm": 0,
  "delta_p_psi": 7.8,
  "landing_elevation_ft": 120,
  "outflow_valves": {"forward_position": 0.2, "aft_position": 0.2},
  "mode": "auto",
  "manual_vs_switch": 0,
  "page_active": true
}
```

### Dataref mappings

| Dataref | Field path | Estimated meaning | Unit | Confidence |
|---|---|---|---|---|
| AirbusFBW/SDPRESS | page_active | PRESS SD page selected/available flag | bool/enum | medium |
| AirbusFBW/CabinAlt | cabin_altitude_ft | Cabin altitude | ft | high |
| AirbusFBW/CabinVS | cabin_vs_fpm | Cabin vertical speed | ft/min | high |
| AirbusFBW/CabinDeltaP | delta_p_psi | Cabin differential pressure | psi | high |
| AirbusFBW/LandElev | landing_elevation_ft | Landing elevation used by pressurization | ft | high |
| toliss_airbus/pfdoutputs/general/landing_elev | landing_elevation_ft_alt | Alternate landing elevation output | ft | medium |
| AirbusFBW/OutflowValve | outflow_valves.forward_position | Main/forward outflow valve position | 0-1 | medium |
| AirbusFBW/OutFlowValveAft | outflow_valves.aft_position | Aft outflow valve position | 0-1 | high |
| AirbusFBW/CabPressMode | mode_raw | Cabin pressurization mode | enum | high |
| AirbusFBW/CabPressModeLights | mode_lights | Cabin press mode lights/faults | enum/array | medium |
| AirbusFBW/ManVSSwitch | manual_vs_switch | Manual vertical speed switch position | enum | high |

### Open questions

- Exact `CabPressMode` enum values are unknown.
- `OutflowValve` spelling and direction need live validation against the graphic.
- Need determine whether A321 variant uses one or two outflow valve displays.

### Catalog gaps

- No clear safety valve dataref was found in the focused catalog grep.
- No clear LDG ELEV AUTO/MAN discrete indication beyond `LandElev` and press mode.
- No explicit pack contribution or ventilation extraction datarefs on the PRESS page.

## SD ELEC page

### Proposed read_sd_elec() response structure

```json
{
  "ac": {
    "gen": [{"available": true, "connected": true}],
    "apu_gen": {"available": false, "connected": false},
    "external_power": {"available": true, "connected": false},
    "bus_tie": "auto",
    "ac_ess_feed": "normal"
  },
  "dc": {
    "batteries": [{"voltage": 25.5, "connected": true}],
    "battery_supply": false,
    "connectors": {"left": true, "center": true, "right": true}
  },
  "page_active": true
}
```

### Dataref mappings

| Dataref | Field path | Estimated meaning | Unit | Confidence |
|---|---|---|---|---|
| AirbusFBW/SDELEC | page_active_ac | ELEC AC SD page selected/available flag | bool/enum | medium |
| AirbusFBW/SDELECDC | page_active_dc | ELEC DC SD page selected/available flag | bool/enum | medium |
| AirbusFBW/ElecOHPArray | overhead.raw | Electrical overhead array | array/enum | medium |
| AirbusFBW/ElecOHPSwitchAnimations | overhead.switch_animations | Electrical overhead switch animations | array | low |
| AirbusFBW/EngGenOHPArray | ac.gen[i].pushbutton_state | Engine generator overhead states | array bool/enum | high |
| AirbusFBW/APUGenOHPArray | ac.apu_gen.pushbutton_state | APU generator overhead state | array bool/enum | high |
| AirbusFBW/ExtPowOHPArray | ac.external_power.pushbutton_state | External power overhead state | array bool/enum | high |
| AirbusFBW/EnableExternalPower | ac.external_power.available | External power A availability | bool/0-1 | medium |
| AirbusFBW/EnableExternalPowerB | ac.external_power_b.available | External power B availability | bool/0-1 | medium |
| AirbusFBW/SDExtPowBox | ac.external_power.box_visible_or_connected | External power box indication on SD | bool/enum | medium |
| AirbusFBW/BusCrossTie | ac.bus_tie.raw | AC bus tie/cross-tie state | enum | medium |
| AirbusFBW/AcEssAltn | ac.ac_ess_feed.raw | AC ESS feed alternate/normal | enum | high |
| AirbusFBW/BatOHPArray | dc.batteries[i].pushbutton_state | Battery 1/2 overhead pushbutton states | array bool/enum | high |
| AirbusFBW/BatVolts | dc.batteries[i].voltage | Battery voltages | volts | high |
| AirbusFBW/SDELBatterySupply | dc.battery_supply | Battery supply indication on SD | bool/enum | medium |
| AirbusFBW/SDELConnectLeft | dc.connectors.left | SD electrical connector left state | bool/enum | medium |
| AirbusFBW/SDELConnectCenter | dc.connectors.center | SD electrical connector center state | bool/enum | medium |
| AirbusFBW/SDELConnectRight | dc.connectors.right | SD electrical connector right state | bool/enum | medium |
| AirbusFBW/ElecConnectors | connectors.raw | Electrical connector state array | array/enum | medium |
| AirbusFBW/GalleyPBLight | galley.pushbutton_light | Galley pushbutton/light state | enum | medium |

### Open questions

- Need exact `EngGenOHPArray`, `APUGenOHPArray`, `ExtPowOHPArray`, and `BatOHPArray` index semantics.
- `SDELConnect*` likely maps to line/contactors in the DC graphic, but exact bus identity needs visual validation.
- AC and DC page split may need two tools or a `section` key if `SDELEC` and `SDELECDC` are mutually exclusive.

### Catalog gaps

- No obvious generator volts/frequency/load datarefs found.
- No obvious TR1/TR2 voltage/current datarefs found.
- No clear AC BUS 1/2, DC BUS 1/2, DC BAT BUS, HOT BUS discrete status names found.

## SD HYD page

### Proposed read_sd_hyd() response structure

```json
{
  "green": {"pressure_psi": 3000, "quantity": 0.85, "pump_on": true},
  "blue": {"pressure_psi": 3000, "quantity": 0.82, "pump_on": true},
  "yellow": {"pressure_psi": 3000, "quantity": 0.80, "pump_on": true, "elec_mode": "auto"},
  "ptu": {"mode": "auto", "ohp_state": true},
  "rat": {"mode": "stowed", "position": 0.0, "rotation_speed": 0},
  "page_active": true
}
```

### Dataref mappings

| Dataref | Field path | Estimated meaning | Unit | Confidence |
|---|---|---|---|---|
| AirbusFBW/SDHYD | page_active | HYD SD page selected/available flag | bool/enum | medium |
| AirbusFBW/HydSysPressArray | green.pressure_psi (index 0) | Green hydraulic pressure | psi | high |
| AirbusFBW/HydSysPressArray | blue.pressure_psi (index 1) | Blue hydraulic pressure | psi | high |
| AirbusFBW/HydSysPressArray | yellow.pressure_psi (index 2) | Yellow hydraulic pressure | psi | high |
| AirbusFBW/HydSysQtyArray | green.quantity (index 0) | Green hydraulic reservoir quantity | normalized or liters | medium |
| AirbusFBW/HydSysQtyArray | blue.quantity (index 1) | Blue hydraulic reservoir quantity | normalized or liters | medium |
| AirbusFBW/HydSysQtyArray | yellow.quantity (index 2) | Yellow hydraulic reservoir quantity | normalized or liters | medium |
| AirbusFBW/HydPumpArray | pumps.raw | Hydraulic pump state array | array bool/enum | medium |
| AirbusFBW/HydPumpOHPArray | pumps.ohp_raw | Hydraulic pump overhead pushbutton array | array bool/enum | medium |
| AirbusFBW/HydOHPArray | overhead.raw | Hydraulic overhead state array | array bool/enum | medium |
| AirbusFBW/HydPTUMode | ptu.mode | PTU mode/state | enum | high |
| AirbusFBW/HydPTUOHP | ptu.ohp_state | PTU overhead switch/pushbutton state | bool/enum | high |
| AirbusFBW/HydYElecMode | yellow.elec_mode | Yellow electric pump mode/state | enum | high |
| AirbusFBW/HydRATMode | rat.mode | RAT hydraulic mode/state | enum | high |
| AirbusFBW/RATposition | rat.position | RAT deployment position | 0-1 | high |
| AirbusFBW/RATRotationSpeed | rat.rotation_speed | RAT rotation speed | rpm or rad/s | medium |
| AirbusFBW/RATRotationalPosition_deg | rat.rotational_position_deg | RAT blade rotational position | deg | high |
| AirbusFBW/HydOHPSwitchAnimations | overhead.switch_animations | Hydraulic overhead switch animations | array | low |

### Open questions

- `HydSysQtyArray` units are unknown; likely normalized quantity rather than liters.
- `HydPumpArray` index mapping to green/blue/yellow engine/electric pumps needs live validation.
- PTU running state may be encoded in `HydPTUMode` or inferred from pressures; exact enum required.

### Catalog gaps

- No explicit green/yellow engine pump low-pressure datarefs found.
- No explicit blue electric pump low-pressure dataref found.
- No explicit fire valve open status mapped to hydraulic page.

## SD FUEL page

### Proposed read_sd_fuel() response structure

```json
{
  "fuel_on_board_kg": null,
  "block_fuel_kg": 7200,
  "tank_quantity": {"left_kg": null, "right_kg": null, "center_kg": null, "raw": []},
  "engine_fuel_flow": [320, 320],
  "lp_valves_open": [true, true],
  "pumps": {"ohp_raw": [], "sd_auto_raw": []},
  "transfer_valves": [],
  "crossfeed_valves": [],
  "act_transfer": false,
  "page_active": true
}
```

### Dataref mappings

| Dataref | Field path | Estimated meaning | Unit | Confidence |
|---|---|---|---|---|
| AirbusFBW/SDFUEL | page_active | FUEL SD page selected/available flag | bool/enum | medium |
| toliss_airbus/init/BlockFuel | block_fuel_kg | Init block fuel | kg | medium |
| sim/cockpit2/fuel/fuel_quantity | tank_quantity.raw | Standard X-Plane per-tank fuel quantity fallback; array index mapping aircraft-dependent | kg or lb per X-Plane config | medium |
| sim/flightmodel/weight/m_fuel | tank_quantity.raw_alt | Standard X-Plane per-tank fuel mass fallback; array index mapping aircraft-dependent | kg | medium |
| AirbusFBW/ENGFuelFlowArray | engine_fuel_flow[i] | Engine fuel flow, index 0/1 | kg/h or sim unit | medium |
| AirbusFBW/ENGFuelLPValveArray | lp_valves_open[i] | Engine LP fuel valve state, index 0/1 | bool/0-1 | high |
| AirbusFBW/FuelPumpOHPArray | pumps.ohp_raw | Fuel pump overhead pushbutton/state array | array bool/enum | high |
| AirbusFBW/FuelAutoPumpOHPArray | pumps.ohp_auto_raw | Auto pump overhead state array | array bool/enum | medium |
| AirbusFBW/FuelAutoPumpSDArray | pumps.sd_auto_raw | Auto pump indication on SD | array bool/enum | high |
| AirbusFBW/FuelOHPArray | overhead.raw | Fuel overhead state array | array bool/enum | medium |
| AirbusFBW/FuelOHPAutoSwitch | overhead.auto_switch | Fuel automatic switch state | bool/enum | medium |
| AirbusFBW/FuelTVSDArray | transfer_valves | Fuel transfer valve states on SD | array bool/enum | high |
| AirbusFBW/FuelXFVSDArray | crossfeed_valves | Fuel crossfeed valve states on SD | array bool/enum | high |
| AirbusFBW/FuelXFVOHPArray | crossfeed_overhead | Crossfeed valve overhead state array | array bool/enum | high |
| AirbusFBW/FuelSDACTXFR | act_transfer | Active transfer indication on SD | bool/enum | high |
| AirbusFBW/FuelNumExtraTanks | extra_tanks_count | Number of extra tanks | count | high |
| AirbusFBW/FuelJettisonRate | jettison_rate | Fuel jettison rate if installed | kg/min or unknown | low |
| AirbusFBW/WriteFOB | fuel_on_board_candidate | Fuel on board candidate | kg/unknown | low |

### Open questions

- The catalog grep for `FuelQty`, `FuelQuantity`, `TankQty`, `LeftTank`, `RightTank`, `CenterTank`, `OuterTank`, `InnerTank`, `FuelLeft`, `FuelRight`, `FuelCenter`, and `ACT` did not expose ToLiss per-tank quantity datarefs. Use the standard `sim/*` fallbacks until a ToLiss-specific quantity ref is found.
- Standard fuel quantity array index order must be validated for the A321 tank layout before assigning left/right/center/ACT fields.
- `FuelPumpOHPArray` and `FuelAutoPumpSDArray` index order needs visual validation.
- `WriteFOB` naming suggests internal/write candidate; do not use without live validation.

### Catalog gaps

- No clear left/right/center/ACT tank quantity datarefs found in the ToLiss catalog; use `sim/cockpit2/fuel/fuel_quantity` or `sim/flightmodel/weight/m_fuel` as fallback.
- No clear FOB, used fuel, or total fuel display dataref found other than low-confidence `WriteFOB`.
- No explicit fuel temperature dataref found.

## SD APU page

### Proposed read_sd_apu() response structure

```json
{
  "n_percent": 100,
  "egt_deg_c": 460,
  "egt_limit_deg_c": 675,
  "fuel_flow": 85,
  "master_on": true,
  "starter_on": false,
  "available": true,
  "bleed_open": false,
  "gen": {"pushbutton_state": true},
  "flap_open_ratio": 1.0,
  "fire": false,
  "page_active": true
}
```

### Dataref mappings

| Dataref | Field path | Estimated meaning | Unit | Confidence |
|---|---|---|---|---|
| AirbusFBW/SDAPU | page_active | APU SD page selected/available flag | bool/enum | medium |
| AirbusFBW/SDAPUBox | apu_box_visible_or_active | APU box indication on SD | bool/enum | medium |
| AirbusFBW/APUN | n_percent | APU N speed | % | high |
| AirbusFBW/APUEGT | egt_deg_c | APU EGT | deg C | high |
| AirbusFBW/APUEGTLimit | egt_limit_deg_c | APU EGT limit | deg C | high |
| AirbusFBW/APUFuelFlow | fuel_flow | APU fuel flow | kg/h or sim unit | medium |
| AirbusFBW/APUMaster | master_on | APU master switch state | bool/0-1 | high |
| AirbusFBW/APUStarter | starter_on | APU starter state | bool/0-1 | high |
| AirbusFBW/APUAvail | available | APU AVAIL indication | bool/0-1 | high |
| AirbusFBW/APUBleedSwitch | bleed_switch_on | APU bleed switch state | bool/0-1 | high |
| AirbusFBW/APUBleedInd | bleed_open | APU bleed valve indication | bool/0-1 | high |
| AirbusFBW/APUGenOHPArray | gen.pushbutton_state | APU generator overhead state | array bool/enum | high |
| AirbusFBW/APUFlapOpenRatio | flap_open_ratio | APU air inlet flap open ratio | 0-1 | high |
| AirbusFBW/APUOnFire | fire | APU fire indication | bool/0-1 | high |
| AirbusFBW/APUExhaustType | exhaust_type | APU exhaust visual/type state | enum | low |
| AirbusFBW/APUSwitchAnims | switch_animations | APU switch animation array | array | low |

### Open questions

- `APUFuelFlow` units need comparison with cockpit display.
- `APUGenOHPArray` index structure is likely overkill for a single APU gen; verify shape.
- `SDAPUBox` exact meaning needs live validation.

### Catalog gaps

- No clear APU generator volts/frequency/load datarefs found.
- No explicit APU low oil pressure or flap fault datarefs found.
- No clear APU page message/warning discrete datarefs found.

## SD COND page

### Proposed read_sd_cond() response structure

```json
{
  "zones": {
    "cockpit": {"temperature_deg_c": 22, "trim": 0.0},
    "forward_cabin": {"temperature_deg_c": 23, "trim": 0.0},
    "aft_cabin": {"temperature_deg_c": 23, "trim": 0.0}
  },
  "cargo": {"forward_temp_deg_c": 18, "aft_temp_deg_c": 18, "bulk_temp_deg_c": null, "hot_air_on": false},
  "packs": [{"switch_on": true, "flow": 1.0, "temperature_deg_c": 12}],
  "hot_air": {"switch1": true, "switch2": true, "valve_open": true},
  "page_active": true
}
```

### Dataref mappings

| Dataref | Field path | Estimated meaning | Unit | Confidence |
|---|---|---|---|---|
| AirbusFBW/SDCOND | page_active | COND SD page selected/available flag | bool/enum | medium |
| AirbusFBW/CockpitTemp | zones.cockpit.temperature_deg_c | Cockpit zone temperature | deg C | high |
| AirbusFBW/FwdCabinTemp | zones.forward_cabin.temperature_deg_c | Forward cabin zone temperature | deg C | high |
| AirbusFBW/AftCabinTemp | zones.aft_cabin.temperature_deg_c | Aft cabin zone temperature | deg C | high |
| AirbusFBW/Zone1Trim | zones.cockpit.trim | Zone 1 trim/temperature demand; standard A321 convention maps Zone 1 to cockpit | unknown | medium |
| AirbusFBW/Zone2Trim | zones.forward_cabin.trim | Zone 2 trim/temperature demand; standard A321 convention maps Zone 2 to forward cabin | unknown | medium |
| AirbusFBW/FwdCargoTemp | cargo.forward_temp_deg_c | Forward cargo temperature | deg C | high |
| AirbusFBW/AftCargoTemp | cargo.aft_temp_deg_c | Aft cargo temperature | deg C | high |
| AirbusFBW/BulkCargoTemp | cargo.bulk_temp_deg_c | Bulk cargo temperature | deg C | high |
| AirbusFBW/CargoHotAir | cargo.hot_air_on | Cargo hot air state | bool/0-1 | high |
| AirbusFBW/HotAirSwitch | hot_air.switch1 | Hot air switch 1 state | bool/enum | high |
| AirbusFBW/HotAirSwitch2 | hot_air.switch2 | Hot air switch 2 state | bool/enum | high |
| AirbusFBW/HotAirValve | hot_air.valve_open | Hot air valve state | bool/0-1 | high |
| AirbusFBW/HotAirSwitchIllum | hot_air.switch_lights | Hot air switch illumination/fault | enum | medium |
| AirbusFBW/Pack1Switch | packs[0].switch_on | Pack 1 switch state (shared with: BLEED) | bool/0-1 | high |
| AirbusFBW/Pack2Switch | packs[1].switch_on | Pack 2 switch state (shared with: BLEED) | bool/0-1 | high |
| AirbusFBW/Pack1Flow | packs[0].flow | Pack 1 flow (shared with: BLEED) | normalized/unknown | medium |
| AirbusFBW/Pack2Flow | packs[1].flow | Pack 2 flow (shared with: BLEED) | normalized/unknown | medium |
| AirbusFBW/Pack1Temp | packs[0].temperature_deg_c | Pack 1 temperature (shared with: BLEED) | deg C | high |
| AirbusFBW/Pack2Temp | packs[1].temperature_deg_c | Pack 2 temperature (shared with: BLEED) | deg C | high |
| AirbusFBW/airCondPanelConfig | panel_config | Air conditioning panel configuration | enum | low |

### Open questions

- `Zone1Trim` and `Zone2Trim` are mapped by standard A321 convention to cockpit and forward cabin, but live validation is still required.
- No `AirbusFBW/Zone3Trim` catalog entry was found for aft cabin trim; determine whether aft cabin trim is hidden, derived, or represented by another dataref.
- Whether the A321 has separate bulk cargo display depends on option/config.
- `Pack*Temp` may be pack outlet temp rather than displayed zone supply temp.

### Catalog gaps

- No clear cabin fan speed or valve position datarefs for each trim air valve.
- No clear selected temperature knobs per zone found.
- No clear exact SD duct temperature labels beyond pack temperatures.

## SD DOOR page

### Proposed read_sd_door() response structure

```json
{
  "passenger_doors": [],
  "cargo_doors": [],
  "slides": {"passenger_raw": [], "emergency_ratio": 0.0},
  "oxygen": {"crew_mask_on": false, "passenger_mask_deployed": false},
  "cockpit_door": {"angle": 0.0, "locked": true},
  "landing_gear_doors": {"nose_closed": true, "left_mlg": 0.0, "right_mlg": 0.0},
  "page_active": true
}
```

### Dataref mappings

| Dataref | Field path | Estimated meaning | Unit | Confidence |
|---|---|---|---|---|
| AirbusFBW/SDDOOR | page_active | DOOR SD page selected/available flag | bool/enum | medium |
| AirbusFBW/PaxDoorArray | passenger_doors.raw | Passenger door positions/states | array | high |
| AirbusFBW/PaxDoorModeArray | passenger_doors.mode_raw | Passenger door mode array | array enum | high |
| AirbusFBW/CargoDoorArray | cargo_doors.raw | Cargo door positions/states | array | high |
| AirbusFBW/CargoDoorModeArray | cargo_doors.mode_raw | Cargo door mode array | array enum | high |
| AirbusFBW/SlideArmedArray | slides.armed_raw | Slide armed status array | array bool/enum | high |
| AirbusFBW/PaxDoorSlidesDeployRatio | slides.passenger_deploy_ratio | Passenger door slide deploy ratio | 0-1/array | high |
| AirbusFBW/EmerSlidesDeployRatio | slides.emergency_deploy_ratio | Emergency slide deploy ratio | 0-1/array | high |
| AirbusFBW/CrewOxyMask | oxygen.crew_mask_on | Crew oxygen mask state | bool/0-1 | high |
| AirbusFBW/CrewOxySwitch | oxygen.crew_switch_on | Crew oxygen switch state | bool/0-1 | high |
| AirbusFBW/PaxOxyMask | oxygen.passenger_mask_deployed | Passenger oxygen mask state | bool/0-1 | high |
| AirbusFBW/PaxOxySwitch | oxygen.passenger_switch_on | Passenger oxygen switch state | bool/0-1 | high |
| AirbusFBW/CockpitDoorAngle | cockpit_door.angle | Cockpit door angle | deg or 0-1 | medium |
| AirbusFBW/CockpitDoorLockState | cockpit_door.locked | Cockpit door lock state | enum/bool | high |
| AirbusFBW/BulkDoor | cargo_doors.bulk | Bulk door state | bool/0-1 | high |
| AirbusFBW/CLGDoor | landing_gear_doors.center | Center landing gear door candidate | bool/0-1 | low |
| AirbusFBW/LeftMLGDoor | landing_gear_doors.left_mlg | Left MLG door state | bool/0-1 | high |
| AirbusFBW/RightMLGDoor | landing_gear_doors.right_mlg | Right MLG door state | bool/0-1 | high |
| AirbusFBW/NoseGearDoorsClosed | landing_gear_doors.nose_closed | Nose gear doors closed indication | bool/0-1 | high |
| AirbusFBW/NoseGearDoorsOpen | landing_gear_doors.nose_open | Nose gear doors open indication | bool/0-1 | high |

### Open questions

- Door array index order needs visual validation against A321 door layout.
- Door states may be continuous ratios or enum states; decoding must be validated.
- `CLGDoor` may be irrelevant for A321 if it is inherited from other ToLiss variants.

### Catalog gaps

- No explicit DOOR page textual labels or warnings beyond arrays.
- No clear overwing emergency exit discrete names outside passenger door arrays.
- No clear individual slide bottle pressure/status datarefs found.

## SD WHEEL page

### Proposed read_sd_wheel() response structure

```json
{
  "gear": {
    "lever": "down",
    "nose": 1.0,
    "left": 1.0,
    "right": 1.0,
    "doors": {"nose_open": false, "nose_closed": true}
  },
  "brakes": {
    "temperatures_deg_c": [],
    "fan_on": false,
    "accumulator_pressure": 3000,
    "left_release": false,
    "right_release": false
  },
  "tires": {"pressure": []},
  "nose_wheel_steering": {"available": true, "anti_skid": true},
  "page_active": true
}
```

### Dataref mappings

| Dataref | Field path | Estimated meaning | Unit | Confidence |
|---|---|---|---|---|
| AirbusFBW/SDWHEEL | page_active | WHEEL SD page selected/available flag | bool/enum | medium |
| AirbusFBW/GearLever | gear.lever_raw | Landing gear lever position | enum | high |
| AirbusFBW/NoseGearPos | gear.nose | Nose gear position | 0-1 | high |
| AirbusFBW/NoseGearInd | gear.nose_indication | Nose gear indication | enum/bool | high |
| AirbusFBW/LeftGearInd | gear.left_indication | Left main gear indication | enum/bool | high |
| AirbusFBW/RightGearInd | gear.right_indication | Right main gear indication | enum/bool | high |
| AirbusFBW/NoseGearDoorsClosed | gear.doors.nose_closed | Nose gear doors closed | bool/0-1 | high |
| AirbusFBW/NoseGearDoorsOpen | gear.doors.nose_open | Nose gear doors open | bool/0-1 | high |
| AirbusFBW/LeftMLGDoor | gear.doors.left_mlg | Left MLG door state | bool/0-1 | high |
| AirbusFBW/RightMLGDoor | gear.doors.right_mlg | Right MLG door state | bool/0-1 | high |
| AirbusFBW/BrakeTemperatureArray | brakes.temperatures_deg_c | Brake temperatures | deg C | high |
| AirbusFBW/BrakeFan | brakes.fan_on | Brake fan state | bool/0-1 | high |
| AirbusFBW/BrakeAccu | brakes.accumulator_pressure | Brake accumulator pressure | psi | high |
| AirbusFBW/LeftBrakeRelease | brakes.left_release | Left brake release indication | bool/0-1 | medium |
| AirbusFBW/RightBrakeRelease | brakes.right_release | Right brake release indication | bool/0-1 | medium |
| AirbusFBW/TirePressureArray | tires.pressure | Tire pressure array | psi | high |
| AirbusFBW/NWSnAntiSkid | nose_wheel_steering.anti_skid | NWS/anti-skid switch/status | bool/enum | high |
| AirbusFBW/NWSAvail | nose_wheel_steering.available | Nose wheel steering available | bool/0-1 | high |
| AirbusFBW/NoseWheelSteeringAngle | nose_wheel_steering.angle_deg | Nose wheel steering angle | deg | high |
| AirbusFBW/ParkBrake | brakes.parking_brake | Parking brake state | bool/0-1 | high |
| AirbusFBW/AltnBrake | brakes.alternate_brake | Alternate brake state | bool/enum | high |
| AirbusFBW/WheelSkidRatio | wheels.skid_ratio | Wheel skid ratio | 0-1/array | high |
| AirbusFBW/WheelRotationSpeed_rads | wheels.rotation_speed | Wheel rotation speed | rad/s | high |

### Open questions

- Brake temperature index order for A321 wheel positions must be validated.
- `LeftBrakeRelease` and `RightBrakeRelease` may indicate anti-skid release rather than pilot command.
- Tire pressure availability may depend on aircraft option/version.

### Catalog gaps

- No explicit green triangle/amber gear indication decoded values beyond gear indication datarefs.
- No clear normal/alternate brake system pressure split beyond accumulator and alternate brake state.
- No explicit brake fan fault dataref found.

## SD F/CTL page

### Proposed read_sd_fctl() response structure

```json
{
  "ailerons": {"left_avail": [], "right_avail": []},
  "elevators": {"left_avail": [], "right_avail": []},
  "rudder": {"available": [], "yaw_trim_deg": 0.0},
  "spoilers": {"positions": []},
  "flaps": {"handle_ratio": 0.0, "request_pos": 0, "left_position": 0.0, "right_position": 0.0},
  "slats": {"request_pos": 0, "left_position": 0.0, "right_position": 0.0},
  "pitch_trim_deg": 0.0,
  "law": {"manual_pitch_trim_only": false},
  "page_active": true
}
```

### Dataref mappings

| Dataref | Field path | Estimated meaning | Unit | Confidence |
|---|---|---|---|---|
| AirbusFBW/SDFCTL | page_active | F/CTL SD page selected/available flag | bool/enum | medium |
| AirbusFBW/LAilAvailArray | ailerons.left_avail | Left aileron availability array | array bool/enum | high |
| AirbusFBW/RAilAvailArray | ailerons.right_avail | Right aileron availability array | array bool/enum | high |
| AirbusFBW/LElevAvailArray | elevators.left_avail | Left elevator availability array | array bool/enum | high |
| AirbusFBW/RElevAvailArray | elevators.right_avail | Right elevator availability array | array bool/enum | high |
| AirbusFBW/RudderAvailArray | rudder.available | Rudder availability array | array bool/enum | high |
| AirbusFBW/SDSpoilerArray | spoilers.positions | Spoiler indication array on SD | array 0-1 | high |
| AirbusFBW/FlapLeverRatio | flaps.handle_ratio | Flap lever/handle ratio | 0-1 | high |
| AirbusFBW/FlapRequestPos | flaps.request_pos | Requested flap handle position | 0-4 | high |
| AirbusFBW/FlapLIRotation | flaps.left_inner_rotation | Left inner flap rotation | deg | medium |
| AirbusFBW/FlapLORotation | flaps.left_outer_rotation | Left outer flap rotation | deg | medium |
| AirbusFBW/FlapRIRotation | flaps.right_inner_rotation | Right inner flap rotation | deg | medium |
| AirbusFBW/FlapRORotation | flaps.right_outer_rotation | Right outer flap rotation | deg | medium |
| AirbusFBW/SlatRequestPos | slats.request_pos | Requested slat position | enum | high |
| AirbusFBW/SlatPositionLWing | slats.left_position | Left slat position | 0-1 or deg | high |
| AirbusFBW/SlatPositionRWing | slats.right_position | Right slat position | 0-1 or deg | high |
| AirbusFBW/PitchTrimPosition | pitch_trim_deg | Stabilizer pitch trim | deg | high |
| AirbusFBW/YawTrimPosition | rudder.yaw_trim_deg | Rudder trim | deg | high |
| toliss_airbus/smartCopilotSync/ATA27/YawTrim | rudder.yaw_trim_alt | Alternate yaw trim sync value | deg/unknown | medium |
| toliss_airbus/pfdoutputs/general/manual_pitch_trim_only | law.manual_pitch_trim_only | Manual pitch trim only indication | bool/0-1 | high |
| AirbusFBW/FCCAvailArray | computers.fcc_avail | Flight control computer availability | array bool/enum | medium |
| AirbusFBW/FCCElevAvail | elevators.fcc_elev_avail | Elevator-related FCC availability | bool/enum | medium |
| AirbusFBW/eRudderConfig | rudder.config | eRudder configuration | enum | low |

### Open questions

- Availability arrays need index decoding to ELAC/SEC/FAC channels.
- Flap and slat position units must be normalized before exposing to tools.
- Spoiler array order and which panels correspond to speedbrake/ground spoiler need validation.

### Catalog gaps

- No clear direct left/right aileron/elevator surface deflection datarefs beyond availability arrays.
- No clear ELAC/SEC/FAC named status datarefs; only generic arrays.
- No explicit flight control law status dataref in the SD page candidates.

## SD CRZ page

### Proposed read_sd_crz() response structure

```json
{
  "cabin": {"altitude_ft": 2500, "vertical_speed_fpm": 0, "delta_p_psi": 7.8},
  "temperatures": {"cockpit_deg_c": 22, "forward_cabin_deg_c": 23, "aft_cabin_deg_c": 23},
  "fuel": {"block_fuel_kg": 7200, "engine_flow": [320, 320]},
  "weight_balance": {"cg_percent": 28.0, "fms_cg_percent": 28.0, "zfwcg_percent": 27.5},
  "cruise": {"init_cruise_alt_ft": 35000, "cas_presel": null, "mach_presel": null}
}
```

### Implementation note

`read_sd_crz()` should be implemented as a composition of other `read_sd_*` calls (`read_sd_press`, `read_sd_cond`, `read_sd_fuel`, `read_sd_eng`), not direct dataref mapping. Reuse cached values to avoid redundant reads.

### Open questions

- Confirm which composed fields best match the ToLiss CRZ graphic in cruise versus non-cruise phases.
- Decide whether `read_sd_crz()` should expose a `page_active` field. CRZ has no ECP button and is normally phase-driven, so a direct active flag is likely unavailable.
- Ensure composed calls share a TTL cache so cabin pressure, pack temperatures, fuel, and engine flow are not fetched repeatedly.

### Catalog gaps

- No `AirbusFBW/SDCRZ` selector dataref found, which is expected because CRZ is not an ECP button page.
- No standalone CRZ page content datarefs found; use composed page readers.
- Any missing values should be inherited from the source page gaps, especially FUEL total/per-tank quantities and ENG oil/vibration details.
