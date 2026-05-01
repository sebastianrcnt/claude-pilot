from __future__ import annotations

from typing import Any

from .common import MappingError
from .server import XP, _bool, _idx, _num, mcp

def _sd_read(name: str, default: Any = None) -> Any:
    try:
        return XP.read(name, default)
    except MappingError:
        return default


def _sd_bool(name: str) -> bool | None:
    value = _sd_read(name)
    return None if value is None else _bool(value)


def _sd_page_active(name: str) -> bool | None:
    return _sd_bool(name)


@mcp.tool
def read_sd_eng() -> dict[str, Any]:
    """Read ECAM SD ENG page datarefs. Units: %, ratio, deg C, fuel-flow/oil units as ToLiss exposes. Medium/low confidence mappings need validation."""
    n1 = _sd_read("AirbusFBW/anim/ENGN1Speed")
    epr = _sd_read("AirbusFBW/ENGEPRArray")
    egt = _sd_read("AirbusFBW/ENGEGTArray")
    fuel_flow = _sd_read("AirbusFBW/ENGFuelFlowArray")
    oil_press = _sd_read("AirbusFBW/ENGOilPressArray")
    start_valve = _sd_read("AirbusFBW/StartValveArray")
    lp_valve = _sd_read("AirbusFBW/ENGFuelLPValveArray")
    reverser = _sd_read("AirbusFBW/ENGRevArray")
    mode = _sd_read("AirbusFBW/ENGModeArray")
    engines = []
    for i in range(2):
        engines.append(
            {
                "n1_percent": _idx(n1, i),
                "epr": _idx(epr, i),
                "egt_deg_c": _idx(egt, i),
                "fuel_flow": _idx(fuel_flow, i),
                "oil_pressure": _idx(oil_press, i),
                "oil_temperature_deg_c": None,
                "start_valve_open": None if _idx(start_valve, i) is None else _bool(_idx(start_valve, i)),
                "lp_fuel_valve_open": None if _idx(lp_valve, i) is None else _bool(_idx(lp_valve, i)),
                "reverse_deployed": None if _idx(reverser, i) is None else _bool(_idx(reverser, i)),
                "master_switch_on": _sd_bool(f"AirbusFBW/ENG{i + 1}MasterSwitch"),
                "mode": _idx(mode, i),
            }
        )
    return {
        "engines": engines,
        "engine_mode": _sd_read("AirbusFBW/ENGModeSwitch"),
        "thrust_rating": {
            "mode": _sd_read("AirbusFBW/THRRatingType"),
            "n1_limit_percent": _sd_read("AirbusFBW/THRRatingN1"),
            "epr_limit": _sd_read("AirbusFBW/THRRatingEPR"),
            "raw_type": _sd_read("AirbusFBW/THRRatingType"),
        },
        "engine_type": _sd_read("AirbusFBW/EngineType"),
        "engine_type_index": _sd_read("AirbusFBW/EngineTypeIndex"),
        "page_active": _sd_page_active("AirbusFBW/SDENG"),
    }


@mcp.tool
def read_sd_bleed() -> dict[str, Any]:
    """Read ECAM SD BLEED page datarefs. Units: psi, deg C, normalized flow, booleans/enums. Medium/low confidence mappings need validation."""
    return {
        "engines": [
            {
                "bleed_switch_on": _sd_bool("AirbusFBW/ENG1BleedSwitch"),
                "bleed_valve_open": _sd_bool("AirbusFBW/ENG1BleedInd"),
                "hp_valve_open": _sd_bool("AirbusFBW/ENG1HPBleedInd"),
                "anti_ice_on": _sd_bool("AirbusFBW/ENG1AISwitch"),
                "anti_ice_light": _sd_read("AirbusFBW/ENG1AILights"),
            },
            {
                "bleed_switch_on": _sd_bool("AirbusFBW/ENG2BleedSwitch"),
                "bleed_valve_open": _sd_bool("AirbusFBW/ENG2BleedInd"),
                "hp_valve_open": _sd_bool("AirbusFBW/ENG2HPBleedInd"),
                "anti_ice_on": _sd_bool("AirbusFBW/ENG2AISwitch"),
                "anti_ice_light": _sd_read("AirbusFBW/ENG2AILights"),
            },
        ],
        "apu_bleed_open": _sd_bool("AirbusFBW/APUBleedInd"),
        "apu_bleed_switch_on": _sd_bool("AirbusFBW/APUBleedSwitch"),
        "xbleed": {"position": _sd_read("AirbusFBW/XBleedSwitch"), "valve_open": _sd_bool("AirbusFBW/XBleedInd"), "interconnect_open": _sd_bool("AirbusFBW/BleedIntercon")},
        "packs": [
            {"switch_on": _sd_bool("AirbusFBW/Pack1Switch"), "flow": _sd_read("AirbusFBW/Pack1Flow"), "fcv_open": _sd_bool("AirbusFBW/Pack1FCVInd"), "temperature_deg_c": _sd_read("AirbusFBW/Pack1Temp")},
            {"switch_on": _sd_bool("AirbusFBW/Pack2Switch"), "flow": _sd_read("AirbusFBW/Pack2Flow"), "fcv_open": _sd_bool("AirbusFBW/Pack2FCVInd"), "temperature_deg_c": _sd_read("AirbusFBW/Pack2Temp")},
        ],
        "duct_pressure": {"left_psi": _sd_read("AirbusFBW/LeftBleedPress"), "right_psi": _sd_read("AirbusFBW/RightBleedPress")},
        "pack_flow_selector": _sd_read("AirbusFBW/PackFlowSel"),
        "ram_air": {"switch_on": _sd_bool("AirbusFBW/RamAirSwitch"), "valve_open": _sd_bool("AirbusFBW/RamAirValveSD"), "switch_lights": _sd_read("AirbusFBW/RamAirSwitchLights")},
        "page_active": _sd_page_active("AirbusFBW/SDBLEED"),
    }


@mcp.tool
def read_sd_press() -> dict[str, Any]:
    """Read ECAM SD PRESS page datarefs. Units: ft, fpm, psi, valve ratio/enums. Medium confidence mappings need validation."""
    return {
        "cabin_altitude_ft": _sd_read("AirbusFBW/CabinAlt"),
        "cabin_vs_fpm": _sd_read("AirbusFBW/CabinVS"),
        "delta_p_psi": _sd_read("AirbusFBW/CabinDeltaP"),
        "landing_elevation_ft": _sd_read("AirbusFBW/LandElev"),
        "landing_elevation_ft_alt": _sd_read("toliss_airbus/pfdoutputs/general/landing_elev"),
        "outflow_valves": {"forward_position": _sd_read("AirbusFBW/OutflowValve"), "aft_position": _sd_read("AirbusFBW/OutFlowValveAft")},
        "mode": _sd_read("AirbusFBW/CabPressMode"),
        "mode_lights": _sd_read("AirbusFBW/CabPressModeLights"),
        "manual_vs_switch": _sd_read("AirbusFBW/ManVSSwitch"),
        "page_active": _sd_page_active("AirbusFBW/SDPRESS"),
    }


@mcp.tool
def read_sd_elec() -> dict[str, Any]:
    """Read ECAM SD ELEC page datarefs. Units: volts, booleans/enums, raw connector arrays. Medium/low confidence mappings need validation."""
    eng_gen = _sd_read("AirbusFBW/EngGenOHPArray")
    bat = _sd_read("AirbusFBW/BatOHPArray")
    bat_volts = _sd_read("AirbusFBW/BatVolts")
    return {
        "ac": {
            "gen": [{"pushbutton_state": _idx(eng_gen, 0)}, {"pushbutton_state": _idx(eng_gen, 1)}],
            "apu_gen": {"pushbutton_state": _sd_read("AirbusFBW/APUGenOHPArray")},
            "external_power": {"pushbutton_state": _sd_read("AirbusFBW/ExtPowOHPArray"), "available": _sd_bool("AirbusFBW/EnableExternalPower"), "box_visible_or_connected": _sd_read("AirbusFBW/SDExtPowBox")},
            "external_power_b": {"available": _sd_bool("AirbusFBW/EnableExternalPowerB")},
            "bus_tie": _sd_read("AirbusFBW/BusCrossTie"),
            "ac_ess_feed": _sd_read("AirbusFBW/AcEssAltn"),
        },
        "dc": {
            "batteries": [{"pushbutton_state": _idx(bat, 0), "voltage": _idx(bat_volts, 0)}, {"pushbutton_state": _idx(bat, 1), "voltage": _idx(bat_volts, 1)}],
            "battery_supply": _sd_read("AirbusFBW/SDELBatterySupply"),
            "connectors": {"left": _sd_read("AirbusFBW/SDELConnectLeft"), "center": _sd_read("AirbusFBW/SDELConnectCenter"), "right": _sd_read("AirbusFBW/SDELConnectRight")},
        },
        "overhead": {"raw": _sd_read("AirbusFBW/ElecOHPArray"), "switch_animations": _sd_read("AirbusFBW/ElecOHPSwitchAnimations")},
        "connectors": {"raw": _sd_read("AirbusFBW/ElecConnectors")},
        "galley": {"pushbutton_light": _sd_read("AirbusFBW/GalleyPBLight")},
        "page_active": _sd_page_active("AirbusFBW/SDELEC"),
        "page_active_ac": _sd_page_active("AirbusFBW/SDELEC"),
        "page_active_dc": _sd_page_active("AirbusFBW/SDELECDC"),
    }


@mcp.tool
def read_sd_hyd() -> dict[str, Any]:
    """Read ECAM SD HYD page datarefs. Units: psi, quantity unknown, RAT speed unknown. Medium/low confidence mappings need validation."""
    press = _sd_read("AirbusFBW/HydSysPressArray")
    qty = _sd_read("AirbusFBW/HydSysQtyArray")
    pump = _sd_read("AirbusFBW/HydPumpArray")
    return {
        "green": {"pressure_psi": _idx(press, 0), "quantity": _idx(qty, 0), "pump_on": None if _idx(pump, 0) is None else _bool(_idx(pump, 0))},
        "blue": {"pressure_psi": _idx(press, 1), "quantity": _idx(qty, 1), "pump_on": None if _idx(pump, 1) is None else _bool(_idx(pump, 1))},
        "yellow": {"pressure_psi": _idx(press, 2), "quantity": _idx(qty, 2), "pump_on": None if _idx(pump, 2) is None else _bool(_idx(pump, 2)), "elec_mode": _sd_read("AirbusFBW/HydYElecMode")},
        "pumps": {"raw": pump, "ohp_raw": _sd_read("AirbusFBW/HydPumpOHPArray")},
        "overhead": {"raw": _sd_read("AirbusFBW/HydOHPArray"), "switch_animations": _sd_read("AirbusFBW/HydOHPSwitchAnimations")},
        "ptu": {"mode": _sd_read("AirbusFBW/HydPTUMode"), "ohp_state": _sd_read("AirbusFBW/HydPTUOHP")},
        "rat": {"mode": _sd_read("AirbusFBW/HydRATMode"), "position": _sd_read("AirbusFBW/RATposition"), "rotation_speed": _sd_read("AirbusFBW/RATRotationSpeed"), "rotational_position_deg": _sd_read("AirbusFBW/RATRotationalPosition_deg")},
        "page_active": _sd_page_active("AirbusFBW/SDHYD"),
    }


@mcp.tool
def read_sd_fuel() -> dict[str, Any]:
    """Read ECAM SD FUEL page datarefs. Units: kg or X-Plane fuel units, kg/h or sim flow units. Medium/low confidence mappings need validation."""
    tank_qty = _sd_read("sim/cockpit2/fuel/fuel_quantity")
    tank_mass = _sd_read("sim/flightmodel/weight/m_fuel")
    return {
        "fuel_on_board_kg": None,
        "fuel_on_board_candidate": _sd_read("AirbusFBW/WriteFOB"),
        "block_fuel_kg": _sd_read("toliss_airbus/init/BlockFuel"),
        "tank_quantity": {"left_kg": None, "right_kg": None, "center_kg": None, "raw": tank_qty, "raw_alt": tank_mass},
        "engine_fuel_flow": _sd_read("AirbusFBW/ENGFuelFlowArray"),
        "lp_valves_open": _sd_read("AirbusFBW/ENGFuelLPValveArray"),
        "pumps": {"ohp_raw": _sd_read("AirbusFBW/FuelPumpOHPArray"), "ohp_auto_raw": _sd_read("AirbusFBW/FuelAutoPumpOHPArray"), "sd_auto_raw": _sd_read("AirbusFBW/FuelAutoPumpSDArray")},
        "overhead": {"raw": _sd_read("AirbusFBW/FuelOHPArray"), "auto_switch": _sd_read("AirbusFBW/FuelOHPAutoSwitch")},
        "transfer_valves": _sd_read("AirbusFBW/FuelTVSDArray"),
        "crossfeed_valves": _sd_read("AirbusFBW/FuelXFVSDArray"),
        "crossfeed_overhead": _sd_read("AirbusFBW/FuelXFVOHPArray"),
        "act_transfer": _sd_read("AirbusFBW/FuelSDACTXFR"),
        "extra_tanks_count": _sd_read("AirbusFBW/FuelNumExtraTanks"),
        "jettison_rate": _sd_read("AirbusFBW/FuelJettisonRate"),
        "page_active": _sd_page_active("AirbusFBW/SDFUEL"),
    }


@mcp.tool
def read_sd_apu() -> dict[str, Any]:
    """Read ECAM SD APU page datarefs. Units: %, deg C, flow units, booleans/enums. Medium/low confidence mappings need validation."""
    return {
        "n_percent": _sd_read("AirbusFBW/APUN"),
        "egt_deg_c": _sd_read("AirbusFBW/APUEGT"),
        "egt_limit_deg_c": _sd_read("AirbusFBW/APUEGTLimit"),
        "fuel_flow": _sd_read("AirbusFBW/APUFuelFlow"),
        "master_on": _sd_bool("AirbusFBW/APUMaster"),
        "starter_on": _sd_bool("AirbusFBW/APUStarter"),
        "available": _sd_bool("AirbusFBW/APUAvail"),
        "bleed_switch_on": _sd_bool("AirbusFBW/APUBleedSwitch"),
        "bleed_open": _sd_bool("AirbusFBW/APUBleedInd"),
        "gen": {"pushbutton_state": _sd_read("AirbusFBW/APUGenOHPArray")},
        "flap_open_ratio": _sd_read("AirbusFBW/APUFlapOpenRatio"),
        "fire": _sd_bool("AirbusFBW/APUOnFire"),
        "exhaust_type": _sd_read("AirbusFBW/APUExhaustType"),
        "switch_animations": _sd_read("AirbusFBW/APUSwitchAnims"),
        "apu_box_visible_or_active": _sd_read("AirbusFBW/SDAPUBox"),
        "page_active": _sd_page_active("AirbusFBW/SDAPU"),
    }


@mcp.tool
def read_sd_cond() -> dict[str, Any]:
    """Read ECAM SD COND page datarefs. Units: deg C, trim units unknown, booleans/enums. Medium/low confidence mappings need validation."""
    return {
        "zones": {
            "cockpit": {"temperature_deg_c": _sd_read("AirbusFBW/CockpitTemp"), "trim": _sd_read("AirbusFBW/Zone1Trim")},
            "forward_cabin": {"temperature_deg_c": _sd_read("AirbusFBW/FwdCabinTemp"), "trim": _sd_read("AirbusFBW/Zone2Trim")},
            "aft_cabin": {"temperature_deg_c": _sd_read("AirbusFBW/AftCabinTemp"), "trim": None},
        },
        "cargo": {"forward_temp_deg_c": _sd_read("AirbusFBW/FwdCargoTemp"), "aft_temp_deg_c": _sd_read("AirbusFBW/AftCargoTemp"), "bulk_temp_deg_c": _sd_read("AirbusFBW/BulkCargoTemp"), "hot_air_on": _sd_bool("AirbusFBW/CargoHotAir")},
        "packs": [
            {"switch_on": _sd_bool("AirbusFBW/Pack1Switch"), "flow": _sd_read("AirbusFBW/Pack1Flow"), "temperature_deg_c": _sd_read("AirbusFBW/Pack1Temp")},
            {"switch_on": _sd_bool("AirbusFBW/Pack2Switch"), "flow": _sd_read("AirbusFBW/Pack2Flow"), "temperature_deg_c": _sd_read("AirbusFBW/Pack2Temp")},
        ],
        "hot_air": {"switch1": _sd_read("AirbusFBW/HotAirSwitch"), "switch2": _sd_read("AirbusFBW/HotAirSwitch2"), "valve_open": _sd_bool("AirbusFBW/HotAirValve"), "switch_lights": _sd_read("AirbusFBW/HotAirSwitchIllum")},
        "panel_config": _sd_read("AirbusFBW/airCondPanelConfig"),
        "page_active": _sd_page_active("AirbusFBW/SDCOND"),
    }


@mcp.tool
def read_sd_door() -> dict[str, Any]:
    """Read ECAM SD DOOR page datarefs. Units: arrays, ratios, booleans/enums. Medium/low confidence mappings need validation."""
    return {
        "passenger_doors": {"raw": _sd_read("AirbusFBW/PaxDoorArray"), "mode_raw": _sd_read("AirbusFBW/PaxDoorModeArray")},
        "cargo_doors": {"raw": _sd_read("AirbusFBW/CargoDoorArray"), "mode_raw": _sd_read("AirbusFBW/CargoDoorModeArray"), "bulk": _sd_read("AirbusFBW/BulkDoor")},
        "slides": {"armed_raw": _sd_read("AirbusFBW/SlideArmedArray"), "passenger_deploy_ratio": _sd_read("AirbusFBW/PaxDoorSlidesDeployRatio"), "emergency_deploy_ratio": _sd_read("AirbusFBW/EmerSlidesDeployRatio")},
        "oxygen": {"crew_mask_on": _sd_bool("AirbusFBW/CrewOxyMask"), "crew_switch_on": _sd_bool("AirbusFBW/CrewOxySwitch"), "passenger_mask_deployed": _sd_bool("AirbusFBW/PaxOxyMask"), "passenger_switch_on": _sd_bool("AirbusFBW/PaxOxySwitch")},
        "cockpit_door": {"angle": _sd_read("AirbusFBW/CockpitDoorAngle"), "locked": _sd_read("AirbusFBW/CockpitDoorLockState")},
        "landing_gear_doors": {"center": _sd_read("AirbusFBW/CLGDoor"), "nose_closed": _sd_bool("AirbusFBW/NoseGearDoorsClosed"), "nose_open": _sd_bool("AirbusFBW/NoseGearDoorsOpen"), "left_mlg": _sd_read("AirbusFBW/LeftMLGDoor"), "right_mlg": _sd_read("AirbusFBW/RightMLGDoor")},
        "page_active": _sd_page_active("AirbusFBW/SDDOOR"),
    }


@mcp.tool
def read_sd_wheel() -> dict[str, Any]:
    """Read ECAM SD WHEEL page datarefs. Units: deg C, psi, ratios, rad/s, booleans/enums. Medium confidence mappings need validation."""
    return {
        "gear": {
            "lever": _sd_read("AirbusFBW/GearLever"),
            "nose": _sd_read("AirbusFBW/NoseGearPos"),
            "nose_indication": _sd_read("AirbusFBW/NoseGearInd"),
            "left_indication": _sd_read("AirbusFBW/LeftGearInd"),
            "right_indication": _sd_read("AirbusFBW/RightGearInd"),
            "doors": {"nose_open": _sd_bool("AirbusFBW/NoseGearDoorsOpen"), "nose_closed": _sd_bool("AirbusFBW/NoseGearDoorsClosed"), "left_mlg": _sd_read("AirbusFBW/LeftMLGDoor"), "right_mlg": _sd_read("AirbusFBW/RightMLGDoor")},
        },
        "brakes": {"temperatures_deg_c": _sd_read("AirbusFBW/BrakeTemperatureArray"), "fan_on": _sd_bool("AirbusFBW/BrakeFan"), "accumulator_pressure": _sd_read("AirbusFBW/BrakeAccu"), "left_release": _sd_bool("AirbusFBW/LeftBrakeRelease"), "right_release": _sd_bool("AirbusFBW/RightBrakeRelease"), "parking_brake": _sd_bool("AirbusFBW/ParkBrake"), "alternate_brake": _sd_read("AirbusFBW/AltnBrake")},
        "tires": {"pressure": _sd_read("AirbusFBW/TirePressureArray")},
        "nose_wheel_steering": {"available": _sd_bool("AirbusFBW/NWSAvail"), "anti_skid": _sd_read("AirbusFBW/NWSnAntiSkid"), "angle_deg": _sd_read("AirbusFBW/NoseWheelSteeringAngle")},
        "wheels": {"skid_ratio": _sd_read("AirbusFBW/WheelSkidRatio"), "rotation_speed": _sd_read("AirbusFBW/WheelRotationSpeed_rads")},
        "page_active": _sd_page_active("AirbusFBW/SDWHEEL"),
    }


@mcp.tool
def read_sd_fctl() -> dict[str, Any]:
    """Read ECAM SD F/CTL page datarefs. Units: arrays, deg, ratios, booleans/enums. Medium/low confidence mappings need validation."""
    return {
        "ailerons": {"left_avail": _sd_read("AirbusFBW/LAilAvailArray"), "right_avail": _sd_read("AirbusFBW/RAilAvailArray")},
        "elevators": {"left_avail": _sd_read("AirbusFBW/LElevAvailArray"), "right_avail": _sd_read("AirbusFBW/RElevAvailArray"), "fcc_elev_avail": _sd_read("AirbusFBW/FCCElevAvail")},
        "rudder": {"available": _sd_read("AirbusFBW/RudderAvailArray"), "yaw_trim_deg": _sd_read("AirbusFBW/YawTrimPosition"), "yaw_trim_alt": _sd_read("toliss_airbus/smartCopilotSync/ATA27/YawTrim"), "config": _sd_read("AirbusFBW/eRudderConfig")},
        "spoilers": {"positions": _sd_read("AirbusFBW/SDSpoilerArray")},
        "flaps": {"handle_ratio": _sd_read("AirbusFBW/FlapLeverRatio"), "request_pos": _sd_read("AirbusFBW/FlapRequestPos"), "left_inner_rotation": _sd_read("AirbusFBW/FlapLIRotation"), "left_outer_rotation": _sd_read("AirbusFBW/FlapLORotation"), "right_inner_rotation": _sd_read("AirbusFBW/FlapRIRotation"), "right_outer_rotation": _sd_read("AirbusFBW/FlapRORotation")},
        "slats": {"request_pos": _sd_read("AirbusFBW/SlatRequestPos"), "left_position": _sd_read("AirbusFBW/SlatPositionLWing"), "right_position": _sd_read("AirbusFBW/SlatPositionRWing")},
        "pitch_trim_deg": _sd_read("AirbusFBW/PitchTrimPosition"),
        "law": {"manual_pitch_trim_only": _sd_bool("toliss_airbus/pfdoutputs/general/manual_pitch_trim_only")},
        "computers": {"fcc_avail": _sd_read("AirbusFBW/FCCAvailArray")},
        "page_active": _sd_page_active("AirbusFBW/SDFCTL"),
    }


@mcp.tool
def read_sd_crz() -> dict[str, Any]:
    """Read synthetic ECAM SD CRZ page as a composition of PRESS, COND, FUEL, and ENG data. No direct CRZ dataref mapping; medium/low source mappings need validation."""
    press = read_sd_press()
    cond = read_sd_cond()
    fuel = read_sd_fuel()
    eng = read_sd_eng()
    engine_flow = fuel["engine_fuel_flow"] or [engine.get("fuel_flow") for engine in eng["engines"]]
    return {
        "cabin": {"altitude_ft": press["cabin_altitude_ft"], "vertical_speed_fpm": press["cabin_vs_fpm"], "delta_p_psi": press["delta_p_psi"]},
        "temperatures": {
            "cockpit_deg_c": cond["zones"]["cockpit"]["temperature_deg_c"],
            "forward_cabin_deg_c": cond["zones"]["forward_cabin"]["temperature_deg_c"],
            "aft_cabin_deg_c": cond["zones"]["aft_cabin"]["temperature_deg_c"],
        },
        "fuel": {"block_fuel_kg": fuel["block_fuel_kg"], "engine_flow": engine_flow},
        "weight_balance": {"cg_percent": None, "fms_cg_percent": None, "zfwcg_percent": None},
        "cruise": {"init_cruise_alt_ft": None, "cas_presel": None, "mach_presel": None},
    }



