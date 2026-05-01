#!/usr/bin/env python3
"""ToLiss A321 co-pilot MCP server backed by the X-Plane local Web API.

The module imports without X-Plane running. Actual tool calls connect to
http://127.0.0.1:8086 and raise clear runtime errors when the simulator,
ToLiss aircraft, or mapped datarefs/commands are unavailable.
"""

from __future__ import annotations

import base64
import asyncio
import json
import math
import time
from pathlib import Path
from typing import Any, Callable, Literal

from .common import MappingError, ToLissNotLoadedError, XPlaneUnavailableError

try:
    import httpx
except Exception:  # pragma: no cover - lets import succeed before deps install.
    httpx = None  # type: ignore[assignment]

try:
    from fastmcp import FastMCP
except Exception:  # pragma: no cover
    class FastMCP:  # minimal import-time fallback, not a real MCP server.
        def __init__(self, name: str):
            self.name = name
            self._tools: dict[str, Callable[..., Any]] = {}

        def tool(self, fn: Callable[..., Any] | None = None, **_: Any):
            def deco(func: Callable[..., Any]):
                self._tools[func.__name__] = func
                return func

            return deco(fn) if fn else deco

        def run(self) -> None:
            raise RuntimeError("fastmcp is not installed. Run: pip install -r requirements.txt")


BASE_URL = "http://127.0.0.1:8086/api/v3"
CAPABILITIES_URL = "http://127.0.0.1:8086/api/capabilities"
ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "toliss_a321_catalog.json"

mcp = FastMCP("toliss-a321-copilot")


def _load_catalog() -> dict[str, dict[str, Any]]:
    if not CATALOG_PATH.exists():
        return {}
    with CATALOG_PATH.open(encoding="utf-8") as f:
        return {entry["name"]: entry for entry in json.load(f)}


CATALOG = _load_catalog()

DATAREF_CACHE_TTL_SECONDS = 1.0
DATAREF_VALUE_CACHE: dict[str, tuple[float, Any]] = {}
DATAREF_CACHE_STATS = {"hits": 0, "misses": 0}


STANDARD_DREFS: dict[str, str] = {
    "groundspeed": "sim/flightmodel/position/groundspeed",
    "latitude": "sim/flightmodel/position/latitude",
    "longitude": "sim/flightmodel/position/longitude",
    "flap_request_ratio": "sim/flightmodel/controls/flaprqst",
    "flap_actual_ratio": "sim/flightmodel2/controls/flap_handle_deploy_ratio",
    "engine_n2": "sim/cockpit2/engine/indicators/N2_percent",
    "engine_oil_temp": "sim/cockpit2/engine/indicators/oil_temperature_deg_C",
    "com1_active": "sim/cockpit2/radios/actuators/com1_frequency_hz_833",
    "com1_stby": "sim/cockpit2/radios/actuators/com1_standby_frequency_hz_833",
    "com2_active": "sim/cockpit2/radios/actuators/com2_frequency_hz_833",
    "com2_stby": "sim/cockpit2/radios/actuators/com2_standby_frequency_hz_833",
    "nav1_active": "sim/cockpit/radios/nav1_freq_hz",
    "nav1_stby": "sim/cockpit/radios/nav1_stdby_freq_hz",
    "nav2_active": "sim/cockpit/radios/nav2_freq_hz",
    "nav2_stby": "sim/cockpit/radios/nav2_stdby_freq_hz",
    "adf1_active": "sim/cockpit/radios/adf1_freq_hz",
    "adf2_active": "sim/cockpit/radios/adf2_freq_hz",
    "tcas_mode": "sim/cockpit2/radios/actuators/tcas_sys_select",
    "tcas_filter": "sim/cockpit2/radios/actuators/tcas_filter",
    "instrument_brightness": "sim/cockpit2/electrical/instrument_brightness_ratio",
    "speedbrake_ratio": "sim/cockpit2/controls/speedbrake_ratio",
    "fcu_airspeed_dial": "sim/cockpit2/autopilot/airspeed_dial_kts_mach",
    "fcu_heading_dial": "sim/cockpit2/autopilot/heading_dial_deg_mag_pilot",
    "fcu_altitude_dial": "sim/cockpit2/autopilot/altitude_dial_ft",
    "fcu_vs_dial": "sim/cockpit2/autopilot/vvi_dial_fpm",
    "fcu_trk_fpa_mode": "sim/cockpit2/autopilot/trk_fpa",
}

STANDARD_COMMANDS: dict[str, str] = {
    "flaps_up": "sim/flight_controls/flaps_up",
    "flaps_down": "sim/flight_controls/flaps_down",
    "gear_up": "sim/flight_controls/landing_gear_up",
    "gear_down": "sim/flight_controls/landing_gear_down",
    "speedbrake_up_one": "sim/flight_controls/speed_brakes_up_one",
    "speedbrake_down_one": "sim/flight_controls/speed_brakes_down_one",
    "parking_brake_toggle": "sim/flight_controls/brakes_toggle_max",
}

DISPLAY_BRIGHTNESS_INDEX = {
    "pfd": 0,
    "nd_inner": 1,
    "nd_outer": 2,
    "ecam_upper": 3,
    "ecam_lower": 4,
}


def _known(name: str) -> str:
    if name not in CATALOG:
        raise MappingError(f"Catalog entry not found: {name}")
    return name


def _m(items: dict[str, str]) -> dict[str, str]:
    return {key: _known(value) for key, value in items.items()}


READ_DREFS: dict[str, dict[str, str]] = {
    "flight_state": _m(
        {
            "ias": "AirbusFBW/IASCapt",
            "mach": "AirbusFBW/MachCapt",
            "baro_alt": "AirbusFBW/ALTCapt",
            "radalt": "toliss_airbus/pfdoutputs/captain/show_land_ref_alt",
            "vs": "toliss_airbus/pfdoutputs/captain/vertical_speed",
            "pitch": "toliss_airbus/pfdoutputs/captain/pitch_angle",
            "roll": "toliss_airbus/pfdoutputs/captain/roll_angle",
            "hdg": "AirbusFBW/HDGCapt",
            "lat": "toliss_airbus/flightplan/latitude",
            "lon": "toliss_airbus/flightplan/longitude",
        }
    ),
    "fcu": _m(
        {
            "spd_value": "AirbusFBW/APSPD_Capt",
            "spd_managed": "AirbusFBW/SPDmanaged",
            "hdg_value": "AirbusFBW/APHDG_Capt",
            "hdg_managed": "AirbusFBW/HDGmanaged",
            "hdg_mode": "AirbusFBW/HDGTRKmode",
            "alt_value": "AirbusFBW/FCUALT_M",
            "alt_managed": "AirbusFBW/ALTmanaged",
            "alt_step": "AirbusFBW/ALT100_1000",
            "vs_value": "AirbusFBW/VS",
            "vs_managed": "AirbusFBW/VSdashed",
            "metric_alt": "AirbusFBW/MetricAlt",
        }
    ),
    "fma": _m(
        {
            # ToLiss exposes the PFD FMA as fixed-width text layers:
            # AirbusFBW/FMA{row}{color}, where row is 1..3 and colors are
            # w=white, g=green, b=blue/cyan, a=amber, m=magenta when present.
            # Current A321 catalog/runtime exposes row1 w/g/b, row2 w/b/m,
            # and row3 w/b/a. Each dataref is a 37-byte null-padded text row.
            "row1_w": "AirbusFBW/FMA1w",
            "row1_g": "AirbusFBW/FMA1g",
            "row1_b": "AirbusFBW/FMA1b",
            "row2_w": "AirbusFBW/FMA2w",
            "row2_b": "AirbusFBW/FMA2b",
            "row2_m": "AirbusFBW/FMA2m",
            "row3_w": "AirbusFBW/FMA3w",
            "row3_b": "AirbusFBW/FMA3b",
            "row3_a": "AirbusFBW/FMA3a",
        }
    ),
    "autoflight": _m(
        {
            "ap1": "AirbusFBW/AP1Engage",
            "ap2": "AirbusFBW/AP2Engage",
            "athr": "AirbusFBW/ATHRmode",
            "fd1": "AirbusFBW/FD1Engage",
            "fd2": "AirbusFBW/FD2Engage",
            "loc_armed": "AirbusFBW/LOCilluminated",
            "appr_armed": "AirbusFBW/APPRilluminated",
            "vertical_mode": "AirbusFBW/APVerticalMode",
            "trk_fpa_mode": "AirbusFBW/HDGTRKmode",
        }
    ),
    "engines": _m(
        {
            "n1": "AirbusFBW/anim/ENGN1Speed",
            "egt": "AirbusFBW/ENGEGTArray",
            "ff": "AirbusFBW/ENGFuelFlowArray",
            "oil_press": "AirbusFBW/ENGOilPressArray",
            "master_switch": "AirbusFBW/anim/ENGMasterSwitch",
            "mode_selector": "AirbusFBW/ENGModeSwitch",
        }
    ),
    "overhead": _m(
        {
            "ohp_lights": "AirbusFBW/OHPLightSwitches",
            "eng1_ai": "AirbusFBW/ENG1AISwitch",
            "eng2_ai": "AirbusFBW/ENG2AISwitch",
            "wing_ai": "AirbusFBW/WAISwitch",
            "pack1": "AirbusFBW/Pack1Switch",
            "pack2": "AirbusFBW/Pack2Switch",
            "bleed1": "AirbusFBW/ENG1BleedSwitch",
            "bleed2": "AirbusFBW/ENG2BleedSwitch",
            "xbleed": "AirbusFBW/XBleedSwitch",
            "apu_bleed": "AirbusFBW/APUBleedSwitch",
            "apu_master": "AirbusFBW/APUMaster",
            "apu_avail": "AirbusFBW/APUAvail",
            "bat": "AirbusFBW/BatOHPArray",
            "gen": "AirbusFBW/EngGenOHPArray",
            "apu_gen": "AirbusFBW/APUGenOHPArray",
            "ext_pwr": "AirbusFBW/ExtPowOHPArray",
            "ac_ess_feed": "AirbusFBW/AcEssAltn",
            "fuel_pumps": "AirbusFBW/FuelPumpOHPArray",
            "fuel_xfeed": "AirbusFBW/FuelXFVOHPArray",
            "hyd_pump": "AirbusFBW/HydPumpOHPArray",
            "hyd_press": "AirbusFBW/HydSysPressArray",
            "ptu": "AirbusFBW/HydPTUOHP",
            "rat": "AirbusFBW/HydRATMode",
        }
    ),
    "pedestal": _m(
        {
            "flap_handle": "AirbusFBW/FlapRequestPos",
            "flap_actual": "AirbusFBW/FlapLeverRatio",
            "slat_actual": "AirbusFBW/SlatRequestPos",
            "speedbrake_handle": "AirbusFBW/SpdBrakeDeployed",
            "parking_brake": "AirbusFBW/ParkBrake",
            "autobrake_lo": "AirbusFBW/ABrkLoButtonAnim",
            "autobrake_med": "AirbusFBW/ABrkMedButtonAnim",
            "autobrake_max": "AirbusFBW/ABrkMaxButtonAnim",
            "trim_stab": "AirbusFBW/PitchTrimPosition",
            "trim_rudder": "AirbusFBW/YawTrimPosition",
            "gear_lever": "AirbusFBW/GearLever",
            "gear_nose": "AirbusFBW/NoseGearPos",
            "gear_left": "AirbusFBW/LeftGearInd",
            "gear_right": "AirbusFBW/RightGearInd",
            "brake_fan": "AirbusFBW/BrakeFan",
        }
    ),
    "radios": _m(
        {
            "rmp1_on": "AirbusFBW/RMP1Switch",
            "rmp1_active": "AirbusFBW/RMP1Freq",
            "rmp1_stby": "AirbusFBW/RMP1StbyFreq",
            "rmp2_on": "AirbusFBW/RMP2Switch",
            "rmp2_active": "AirbusFBW/RMP2Freq",
            "rmp2_stby": "AirbusFBW/RMP2StbyFreq",
            "rmp3_on": "AirbusFBW/RMP3Switch",
            "rmp3_active": "AirbusFBW/RMP3Freq",
            "rmp3_stby": "AirbusFBW/RMP3StbyFreq",
            "acp1_switch": "AirbusFBW/ACP1Switch",
            "acp2_switch": "AirbusFBW/ACP2Switch",
        }
    ),
    "atc": _m(
        {
            "xpdr1": "AirbusFBW/XPDR1",
            "xpdr2": "AirbusFBW/XPDR2",
            "xpdr3": "AirbusFBW/XPDR3",
            "xpdr4": "AirbusFBW/XPDR4",
            "xpdr_mode": "AirbusFBW/XPDRTCASMode",
            "xpdr_alt": "AirbusFBW/XPDRTCASAltSelect",
            "tcas_status": "AirbusFBW/TCASStatus",
            "tcas_range_capt": "AirbusFBW/TCASSelectedND1",
            "tcas_range_fo": "AirbusFBW/TCASSelectedND2",
        }
    ),
    "efis": _m(
        {
            "capt_nd_mode": "AirbusFBW/NDmodeCapt",
            "fo_nd_mode": "AirbusFBW/NDmodeFO",
            "capt_nd_range": "AirbusFBW/NDrangeCapt",
            "fo_nd_range": "AirbusFBW/NDrangeFO",
            "capt_cstr": "AirbusFBW/NDShowCSTRCapt",
            "fo_cstr": "AirbusFBW/NDShowCSTRFO",
            "capt_wpt": "AirbusFBW/NDShowWPTCapt",
            "fo_wpt": "AirbusFBW/NDShowWPTFO",
            "capt_vord": "AirbusFBW/NDShowVORDCapt",
            "fo_vord": "AirbusFBW/NDShowVORDFO",
            "capt_ndb": "AirbusFBW/NDShowNDBCapt",
            "fo_ndb": "AirbusFBW/NDShowNDBFO",
            "capt_arpt": "AirbusFBW/NDShowARPTCapt",
            "fo_arpt": "AirbusFBW/NDShowARPTFO",
            "capt_baro": "AirbusFBW/BaroKnobRotationCapt",
            "fo_baro": "AirbusFBW/BaroKnobRotationFO",
            "capt_baro_std": "AirbusFBW/BaroStdCapt",
            "fo_baro_std": "AirbusFBW/BaroStdFO",
            "capt_baro_unit": "AirbusFBW/BaroUnitCapt",
            "fo_baro_unit": "AirbusFBW/BaroUnitFO",
            "capt_ls": "AirbusFBW/LOConCapt",
            "fo_ls": "AirbusFBW/LOConFO",
        }
    ),
    "weather_radar": _m(
        {
            "mode": "AirbusFBW/WXSwitchMode",
            "gain": "AirbusFBW/WXRadarGain",
            "tilt": "AirbusFBW/WXRadarTilt",
            "multiscan": "AirbusFBW/WXSwitchMultiscan",
            "gcs": "AirbusFBW/WXSwitchGCS",
            "pws": "AirbusFBW/WXSwitchPWS",
        }
    ),
}

COMMANDS = _m(
    {
        "spd_push": "AirbusFBW/PushSPDSel",
        "spd_pull": "AirbusFBW/PullSPDSel",
        "hdg_push": "AirbusFBW/PushHDGSel",
        "hdg_pull": "AirbusFBW/PullHDGSel",
        "alt_push": "AirbusFBW/PushAltitude",
        "alt_pull": "AirbusFBW/PullAltitude",
        "vs_push": "AirbusFBW/PushVSSel",
        "vs_pull": "AirbusFBW/PullVSSel",
        "ap1": "toliss_airbus/ap1_push",
        "ap2": "toliss_airbus/ap2_push",
        "athr": "AirbusFBW/ATHRbutton",
        "fd1": "toliss_airbus/fd1_push",
        "fd2": "toliss_airbus/fd2_push",
        "loc": "toliss_airbus/loc_push",
        "appr": "AirbusFBW/APPRbutton",
        "exped": "AirbusFBW/EXPEDbutton",
        "trk_fpa": "toliss_airbus/hdgtrk_button_push",
        "metric_alt": "toliss_airbus/metric_alt_button_push",
        "athr_disconnect": "AirbusFBW/ATHRbutton",
        "iscs_open": "toliss_airbus/iscs_open",
    }
)

STATE_COMMANDS: dict[str, dict[str, str]] = {
    "antiice": _m(
        {
            "eng1_on": "toliss_airbus/antiicecommands/ENG1On",
            "eng1_off": "toliss_airbus/antiicecommands/ENG1Off",
            "eng1_toggle": "toliss_airbus/antiicecommands/ENG1Toggle",
            "eng2_on": "toliss_airbus/antiicecommands/ENG2On",
            "eng2_off": "toliss_airbus/antiicecommands/ENG2Off",
            "eng2_toggle": "toliss_airbus/antiicecommands/ENG2Toggle",
            "wing_on": "toliss_airbus/antiicecommands/WingOn",
            "wing_off": "toliss_airbus/antiicecommands/WingOff",
            "wing_toggle": "toliss_airbus/antiicecommands/WingToggle",
        }
    ),
    "pneumatic": _m(
        {
            "pack1_on": "toliss_airbus/aircondcommands/Pack1On",
            "pack1_off": "toliss_airbus/aircondcommands/Pack1Off",
            "pack1_toggle": "toliss_airbus/aircondcommands/Pack1Toggle",
            "pack2_on": "toliss_airbus/aircondcommands/Pack2On",
            "pack2_off": "toliss_airbus/aircondcommands/Pack2Off",
            "pack2_toggle": "toliss_airbus/aircondcommands/Pack2Toggle",
            "apu_bleed_on": "toliss_airbus/apucommands/BleedOn",
            "apu_bleed_off": "toliss_airbus/apucommands/BleedOff",
            "apu_bleed_toggle": "toliss_airbus/apucommands/BleedToggle",
        }
    ),
    "electrical": _m(
        {
            "bat1_on": "toliss_airbus/eleccommands/Bat1On",
            "bat1_off": "toliss_airbus/eleccommands/Bat1Off",
            "bat1_toggle": "toliss_airbus/eleccommands/Bat1Toggle",
            "bat2_on": "toliss_airbus/eleccommands/Bat2On",
            "bat2_off": "toliss_airbus/eleccommands/Bat2Off",
            "bat2_toggle": "toliss_airbus/eleccommands/Bat2Toggle",
            "ext_pwr_toggle": "toliss_airbus/eleccommands/ExtPowToggle",
        }
    ),
    "fuel": _m(
        {
            "lp1_on": "toliss_airbus/fuelcommands/PumpLWing1On",
            "lp1_off": "toliss_airbus/fuelcommands/PumpLWing1Off",
            "lp1_toggle": "toliss_airbus/fuelcommands/PumpLWing1Toggle",
            "lp2_on": "toliss_airbus/fuelcommands/PumpLWing2On",
            "lp2_off": "toliss_airbus/fuelcommands/PumpLWing2Off",
            "lp2_toggle": "toliss_airbus/fuelcommands/PumpLWing2Toggle",
            "cp1_on": "toliss_airbus/fuelcommands/PumpLCenterOn",
            "cp1_off": "toliss_airbus/fuelcommands/PumpLCenterOff",
            "cp1_toggle": "toliss_airbus/fuelcommands/PumpLCenterToggle",
            "rp1_on": "toliss_airbus/fuelcommands/PumpRWing1On",
            "rp1_off": "toliss_airbus/fuelcommands/PumpRWing1Off",
            "rp1_toggle": "toliss_airbus/fuelcommands/PumpRWing1Toggle",
            "rp2_on": "toliss_airbus/fuelcommands/PumpRWing2On",
            "rp2_off": "toliss_airbus/fuelcommands/PumpRWing2Off",
            "rp2_toggle": "toliss_airbus/fuelcommands/PumpRWing2Toggle",
        }
    ),
    "lights": _m(
        {
            "beacon_on": "toliss_airbus/lightcommands/BeaconOn",
            "beacon_off": "toliss_airbus/lightcommands/BeaconOff",
            "beacon_toggle": "toliss_airbus/lightcommands/BeaconToggle",
            "strobe_up": "toliss_airbus/lightcommands/StrobeLightUp",
            "strobe_down": "toliss_airbus/lightcommands/StrobeLightDown",
            "nav_up": "toliss_airbus/lightcommands/NavLightUp",
            "nav_down": "toliss_airbus/lightcommands/NavLightDown",
            "wing_on": "toliss_airbus/lightcommands/WingLightOn",
            "wing_off": "toliss_airbus/lightcommands/WingLightOff",
            "wing_toggle": "toliss_airbus/lightcommands/WingLightToggle",
            "landing_l_up": "toliss_airbus/lightcommands/LLandLightUp",
            "landing_l_down": "toliss_airbus/lightcommands/LLandLightDown",
            "landing_r_up": "toliss_airbus/lightcommands/RLandLightUp",
            "landing_r_down": "toliss_airbus/lightcommands/RLandLightDown",
            "nose_up": "toliss_airbus/lightcommands/NoseLightUp",
            "nose_down": "toliss_airbus/lightcommands/NoseLightDown",
            "rwy_turnoff_on": "toliss_airbus/lightcommands/TurnoffLightOn",
            "rwy_turnoff_off": "toliss_airbus/lightcommands/TurnoffLightOff",
            "rwy_turnoff_toggle": "toliss_airbus/lightcommands/TurnoffLightToggle",
            "dome_up": "toliss_airbus/lightcommands/DomeLightUp",
            "dome_down": "toliss_airbus/lightcommands/DomeLightDown",
            "seatbelt_on": "toliss_airbus/lightcommands/FSBSignOn",
            "seatbelt_off": "toliss_airbus/lightcommands/FSBSignOff",
            "seatbelt_toggle": "toliss_airbus/lightcommands/FSBSignToggle",
            "nosmoking_up": "toliss_airbus/lightcommands/NSSignUp",
            "nosmoking_down": "toliss_airbus/lightcommands/NSSignDown",
            "emer_exit_up": "toliss_airbus/lightcommands/EmerExitLightUp",
            "emer_exit_down": "toliss_airbus/lightcommands/EmerExitLightDown",
        }
    ),
}

WRITE_DREFS = _m(
    {
        "fcu_alt": "AirbusFBW/FCUALT_M",
        # Do not use smartCopilotSync or FCU knob counter datarefs as target-value controls.
        "panel_brightness": "AirbusFBW/PanelBrightnessLevel",
        "flood_brightness": "AirbusFBW/FloodLightLevels",
        "integral_brightness": "AirbusFBW/FCUIntegralBrightness",
        "wx_mode": "AirbusFBW/WXSwitchMode",
        "wx_gain": "AirbusFBW/WXRadarGain",
        "wx_tilt": "AirbusFBW/WXRadarTilt",
        "wx_multiscan": "AirbusFBW/WXSwitchMultiscan",
        "wx_gcs": "AirbusFBW/WXSwitchGCS",
        "baro_capt": "AirbusFBW/BaroKnobRotationCapt",
        "baro_fo": "AirbusFBW/BaroKnobRotationFO",
        "xpdr_mode": "AirbusFBW/XPDRTCASMode",
        "xpdr_alt": "AirbusFBW/XPDRTCASAltSelect",
        "gear": "AirbusFBW/GearLever",
        "flap": "AirbusFBW/FlapRequestPos",
        "speedbrake": "AirbusFBW/SpdBrakeDeployed",
        "trim_stab": "AirbusFBW/PitchTrimPosition",
        "trim_rudder": "AirbusFBW/YawTrimPosition",
        "engine_mode": "AirbusFBW/ENGModeSwitch",
    }
)


class XPlaneClient:
    def __init__(self) -> None:
        self.datarefs: dict[str, int] = {}
        self.dataref_meta: dict[str, dict[str, Any]] = {}
        self.commands: dict[str, int] = {}
        self._loaded = False

    def _http(self):
        if httpx is None:
            raise XPlaneUnavailableError("httpx is not installed. Run: pip install -r requirements.txt")
        timeout = httpx.Timeout(2.0, connect=1.0)
        return httpx.Client(timeout=timeout, headers={"Accept": "application/json", "Content-Type": "application/json"})

    def ensure_cache(self) -> None:
        if self._loaded:
            return
        try:
            with self._http() as client:
                client.get(CAPABILITIES_URL).raise_for_status()
                datarefs = client.get(f"{BASE_URL}/datarefs").json().get("data", [])
                commands = client.get(f"{BASE_URL}/commands").json().get("data", [])
        except Exception as exc:
            raise XPlaneUnavailableError(
                "X-Plane Web API is unavailable at 127.0.0.1:8086. Start X-Plane 12.1.4+ with incoming traffic enabled."
            ) from exc
        self.datarefs = {item["name"]: int(item["id"]) for item in datarefs if item and item.get("name")}
        self.dataref_meta = {item["name"]: item for item in datarefs if item and item.get("name")}
        self.commands = {item["name"]: int(item["id"]) for item in commands if item and item.get("name")}
        self._loaded = True

    def require_toliss(self) -> None:
        # PLANE_ICAO is provided by FlyWithLua; X-Plane itself may not expose it.
        if "AirbusFBW/FCUAvail" not in self.datarefs and not any(n.startswith("AirbusFBW/") for n in self.datarefs):
            raise ToLissNotLoadedError("ToLiss A321 does not appear loaded: no AirbusFBW datarefs are registered.")

    def dataref_id(self, name: str) -> int:
        self.ensure_cache()
        self.require_toliss()
        if name not in self.datarefs:
            raise MappingError(f"Dataref not found in X-Plane session: {name}")
        return self.datarefs[name]

    def command_id(self, name: str) -> int:
        self.ensure_cache()
        self.require_toliss()
        if name not in self.commands:
            raise KeyError(f"Command not found in X-Plane session: {name}")
        return self.commands[name]

    def is_writable(self, name: str) -> bool:
        self.ensure_cache()
        return bool(self.dataref_meta.get(name, {}).get("is_writable"))

    def read(self, name: str, default: Any = None) -> Any:
        now = time.monotonic()
        cached = DATAREF_VALUE_CACHE.get(name)
        if cached and now - cached[0] < DATAREF_CACHE_TTL_SECONDS:
            DATAREF_CACHE_STATS["hits"] += 1
            return cached[1]
        DATAREF_CACHE_STATS["misses"] += 1
        did = self.dataref_id(name)
        with self._http() as client:
            payload = client.get(f"{BASE_URL}/datarefs/{did}/value").json()
        data = payload.get("data")
        if isinstance(data, dict):
            value = data.get("value", data.get("data", default))
        else:
            value = data if data is not None else default
        DATAREF_VALUE_CACHE[name] = (time.monotonic(), value)
        return value

    def write(self, name: str, value: Any) -> None:
        if not self.is_writable(name):
            raise MappingError(f"Dataref is read-only or not writable via Web API: {name}")
        did = self.dataref_id(name)
        with self._http() as client:
            response = client.patch(f"{BASE_URL}/datarefs/{did}/value", json={"data": value})
            response.raise_for_status()
        DATAREF_VALUE_CACHE.pop(name, None)

    def command(self, name: str, duration: float = 0.0) -> None:
        cid = self.command_id(name)
        with self._http() as client:
            response = client.post(f"{BASE_URL}/command/{cid}/activate", json={"duration": duration})
            response.raise_for_status()
        DATAREF_VALUE_CACHE.clear()


XP = XPlaneClient()


def _num(value: Any) -> float | int | None:
    if isinstance(value, list):
        return value[0] if value else None
    if isinstance(value, (int, float)):
        return value
    try:
        return float(value)
    except Exception:
        return None


def _idx(value: Any, index: int, default: Any = None) -> Any:
    if isinstance(value, list) and len(value) > index:
        return value[index]
    return default


def _bool(value: Any) -> bool:
    n = _num(value)
    return bool(n and n > 0.5)


def _read_std(key: str) -> Any:
    return XP.read(STANDARD_DREFS[key])


def _write_std(key: str, value: Any) -> None:
    XP.write(STANDARD_DREFS[key], value)


def _mhz_from_com_raw(value: Any) -> float | None:
    n = _num(value)
    return None if n is None else n / 1000.0


def _com_raw_from_mhz(value: float) -> int:
    return int(round(value * 1000))


def _mhz_from_nav_raw(value: Any) -> float | None:
    n = _num(value)
    return None if n is None else n / 100.0


def _nav_raw_from_mhz(value: float) -> int:
    return int(round(value * 100))


def _radio_keys(channel: str) -> tuple[str, str | None, Callable[[Any], Any], Callable[[float], Any]]:
    if channel in {"com1", "com2"}:
        return f"{channel}_active", f"{channel}_stby", _mhz_from_com_raw, _com_raw_from_mhz
    if channel in {"nav1", "nav2"}:
        return f"{channel}_active", f"{channel}_stby", _mhz_from_nav_raw, _nav_raw_from_mhz
    if channel in {"adf1", "adf2"}:
        return f"{channel}_active", None, _num, lambda value: int(round(value))
    raise ValueError(f"Unsupported radio channel: {channel}")


TCAS_MODE_LABELS = {0: "ta_ra", 1: "ta", 2: "stby", 3: "test"}
TCAS_MODE_VALUES = {"tara": 0, "ta_ra": 0, "ta/ra": 0, "ta-ra": 0, "ta": 1, "stby": 2, "standby": 2, "test": 3}


def _tcas_mode_value(value: Any) -> int:
    if isinstance(value, str):
        key = value.strip().lower()
        if key not in TCAS_MODE_VALUES:
            raise ValueError(f"Unsupported TCAS mode: {value}")
        return TCAS_MODE_VALUES[key]
    raw = int(value)
    if raw not in TCAS_MODE_LABELS:
        raise ValueError("TCAS mode numeric value must be 0, 1, 2, or 3")
    return raw


def _read_map(mapping: dict[str, str]) -> dict[str, Any]:
    return {key: XP.read(name) for key, name in mapping.items()}


def _read_flap_handle() -> int | None:
    flap_ratio = _num(_read_std("flap_request_ratio"))
    return None if flap_ratio is None else int(round(max(0.0, min(1.0, float(flap_ratio))) * 4))


def _speedbrake_armed_dref() -> str | None:
    return _catalog_dataref(
        "AirbusFBW/SpeedbrakeArmed",
        "AirbusFBW/SpdBrakeArmed",
        "AirbusFBW/SpeedBrakeArmed",
        "AirbusFBW/SpoilersArmed",
        "AirbusFBW/SpoilerArmed",
        "AirbusFBW/SpeedbrakeArm",
        "AirbusFBW/SpdBrakeArm",
    )


def _read_speedbrake_armed() -> bool | None:
    dref = _speedbrake_armed_dref()
    if not dref:
        return None
    return _bool(XP.read(dref))


def _read_speedbrake_raw_ratio() -> float | None:
    value = _num(_read_std("speedbrake_ratio"))
    return None if value is None else float(value)


def _normalize_heading(value: float) -> float:
    return float(value) % 360.0


def _decode_fcu_heading(value: Any) -> float | None:
    raw = _num(value)
    if raw is None:
        return None
    raw_float = float(raw)
    if abs(raw_float) <= (2.0 * math.pi + 0.5):
        return _normalize_heading(math.degrees(raw_float))
    return _normalize_heading(raw_float)


def _read_fcu_heading_value() -> float | None:
    try:
        return _normalize_heading(float(_num(_read_std("fcu_heading_dial"))))
    except Exception:
        try:
            return _decode_fcu_heading(XP.read(READ_DREFS["fcu"]["hdg_value"]))
        except Exception:
            return None


def _read_fcu_direct_value(std_key: str, fallback: Any = None) -> float | int | None:
    try:
        return _num(_read_std(std_key))
    except Exception:
        return _num(fallback)


def _shortest_heading_delta(current: float, target: float) -> float:
    return (target - current + 540.0) % 360.0 - 180.0


def _fcu_value_close(channel: str, actual: float | None, target: float | None) -> bool:
    if actual is None or target is None:
        return False
    if channel == "hdg":
        return abs(_shortest_heading_delta(actual, target)) <= 1.0
    if channel == "spd":
        return abs(actual - target) <= 1.0
    if channel == "vs":
        return abs(actual - target) <= 100.0
    if channel == "alt":
        return abs(actual - target) <= 100.0
    return actual == target


def _fcu_numeric_disabled(channel: str) -> MappingError:
    return MappingError(
        f"set_fcu('{channel}') numeric target is disabled because no verified ToLiss FCU control path is available. "
        "The old SmartCopilotSync mapping was removed because it does not drive the actual FCU."
    )


def _fcu_direct_target(channel: str, current: float, target: float, dial_value: float) -> float:
    if channel == "hdg":
        display_offset = _shortest_heading_delta(dial_value, current)
        return _normalize_heading(target - display_offset)
    return target - (current - dial_value)


def _set_fcu_direct(
    channel: Literal["spd", "hdg", "alt", "vs"],
    target: float,
    desired_managed: bool,
    dial_dref: str,
    *,
    normalize: Callable[[float], float] | None = None,
    command_after_dial: bool = False,
) -> dict[str, Any]:
    original_before = read_fcu()
    before = original_before
    command_used: list[str] = []
    dataref_used: list[str] = []
    target = normalize(target) if normalize else float(target)
    current = _num(before[channel]["value"])
    if current is None:
        raise MappingError(f"set_fcu('{channel}') requires a working FCU readback before direct control can be used.")
    current = normalize(float(current)) if normalize else float(current)

    cmd = COMMANDS[f"{channel}_{'push' if desired_managed else 'pull'}"]
    if not command_after_dial:
        # FCU push/pull is a physical action, not just a request for the managed
        # flag to equal a target state. Never skip it based only on managed
        # readback.
        XP.command(cmd)
        command_used.append(cmd)
        DATAREF_VALUE_CACHE.clear()
        time.sleep(0.15)
        before = read_fcu()
        current = _num(before[channel]["value"])
        if current is None:
            raise MappingError(f"set_fcu('{channel}') requires a working FCU readback before direct control can be used.")
        current = normalize(float(current)) if normalize else float(current)

    if _fcu_value_close(channel, current, target):
        if command_after_dial:
            XP.command(cmd)
            command_used.append(cmd)
            DATAREF_VALUE_CACHE.clear()
            time.sleep(0.15)
            before = read_fcu()
        return {
            "success": True,
            "before": original_before,
            "after": before,
            "dataref_used": [],
            "command_used": command_used,
        }

    dial_raw = _num(XP.read(dial_dref))
    if dial_raw is None:
        raise MappingError(f"set_fcu('{channel}') requires a working dial dataref: {dial_dref}")
    dial_value = normalize(float(dial_raw)) if normalize else float(dial_raw)
    dial_target = _fcu_direct_target(channel, current, target, dial_value)
    XP.write(dial_dref, dial_target)
    dataref_used.append(dial_dref)
    DATAREF_VALUE_CACHE.clear()
    if command_after_dial:
        # ALT hold needs the selected altitude changed before the pull/push
        # action; pulling at the old target can leave the FMA in ALT.
        XP.command(cmd)
        command_used.append(cmd)
        DATAREF_VALUE_CACHE.clear()
    time.sleep(0.25)
    after = read_fcu()
    actual = _num(after[channel]["value"])
    actual = None if actual is None else (normalize(float(actual)) if normalize else float(actual))
    if _fcu_value_close(channel, actual, target):
        result = {
            "success": True,
            "before": original_before,
            "after": after,
            "dataref_used": dataref_used,
            "command_used": command_used,
        }
        result["dial"] = {"before": dial_value, "after": dial_target, "display_offset": current - dial_value}
        return result
    raise MappingError(f"set_fcu('{channel}') wrote {dial_target} to {dial_dref} but readback was {actual}, not target {target}.")


def _set_fcu_hdg(target: float, desired_managed: bool) -> dict[str, Any]:
    return _set_fcu_direct("hdg", target, desired_managed, STANDARD_DREFS["fcu_heading_dial"], normalize=_normalize_heading)


def _set_fcu_alt(target: float, desired_managed: bool) -> dict[str, Any]:
    step_dref = READ_DREFS["fcu"].get("alt_step")
    step_used: list[str] = []
    if step_dref:
        XP.write(step_dref, 1 if float(target) % 1000 == 0 else 0)
        DATAREF_VALUE_CACHE.clear()
        step_used.append(step_dref)
    result = _set_fcu_direct("alt", target, desired_managed, STANDARD_DREFS["fcu_altitude_dial"], command_after_dial=True)
    result["dataref_used"] = step_used + result["dataref_used"]
    return result


def _not_impl(tool: str, missing: list[str]) -> None:
    raise MappingError(f"{tool} is not implemented because catalog mappings are missing: {', '.join(missing)}")


def _decode_fixed_text(value: Any, width: int = 37) -> str:
    if value is None:
        return " " * width
    if isinstance(value, str):
        try:
            raw = base64.b64decode(value, validate=True)
            return raw.rstrip(b"\x00").decode("ascii", errors="replace").ljust(width)[:width]
        except Exception:
            return value.rstrip("\x00").ljust(width)[:width]
    if isinstance(value, list):
        try:
            raw = bytes(int(item) & 0xFF for item in value)
            return raw.rstrip(b"\x00").decode("ascii", errors="replace").ljust(width)[:width]
        except Exception:
            return " " * width
    if isinstance(value, bytes):
        return value.rstrip(b"\x00").decode("ascii", errors="replace").ljust(width)[:width]
    return str(value).ljust(width)[:width]


FMA_WIDTH = 37
FMA_COLUMNS = {
    # Measured live on ToLiss A321: 37 characters split into five fixed cells.
    # Positional convention only: col1 often contains A/THR modes, col2
    # vertical modes, col3 lateral modes, col4 approach/common annunciations,
    # and col5 AP/FD/A-THR/CAT status. Do not treat the labels as semantics.
    "col1": slice(0, 7),
    "col2": slice(7, 17),
    "col3": slice(17, 27),
    "col4": slice(27, 32),
    "col5": slice(32, 37),
}
FMA_COLORS = {"w": "white", "g": "green", "b": "cyan", "a": "amber", "m": "magenta"}
FMA_COLOR_PRIORITY = ("g", "b", "w", "a", "m")


def _fma_cell(layer_text: str, column: str) -> str:
    return layer_text[FMA_COLUMNS[column]].strip()


def _fma_raw_layers(d: dict[str, Any]) -> dict[str, str]:
    raw: dict[str, str] = {}
    for row in (1, 2, 3):
        for suffix, color in FMA_COLORS.items():
            key = f"row{row}_{suffix}"
            if key in d:
                raw[f"row{row}_{color}"] = _decode_fixed_text(d[key], FMA_WIDTH)
    return raw


def _fma_rows(raw: dict[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in (1, 2, 3):
        cells: list[dict[str, Any]] = []
        row_layers = {suffix: raw.get(f"row{row}_{color}", " " * FMA_WIDTH) for suffix, color in FMA_COLORS.items()}
        for col in FMA_COLUMNS:
            selected_text = ""
            selected_color = None
            for suffix in FMA_COLOR_PRIORITY:
                text = _fma_cell(row_layers[suffix], col)
                if text:
                    selected_text = text
                    selected_color = FMA_COLORS[suffix]
                    break
            cells.append({"col": col, "text": selected_text, "color": selected_color})
        rows.append({"row": row, "cells": cells})
    return rows


def _write_result(read_fn: Callable[[], dict[str, Any]], action: Callable[[], None], used: list[str]) -> dict[str, Any]:
    before = read_fn()
    action()
    time.sleep(0.15)
    after = read_fn()
    return {"success": before != after, "before": before, "after": after, "dataref_used": used, "command_used": []}


def _noop_success(before: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": True,
        "noop": True,
        "before": before,
        "after": before,
        "dataref_used": [],
        "command_used": [],
    }


def _write_result_with_commands(
    read_fn: Callable[[], dict[str, Any]],
    action: Callable[[], None],
    *,
    datarefs: list[str] | None = None,
    commands: list[str] | None = None,
) -> dict[str, Any]:
    before = read_fn()
    action()
    time.sleep(0.15)
    after = read_fn()
    return {
        "success": before != after,
        "before": before,
        "after": after,
        "dataref_used": datarefs or [],
        "command_used": commands or [],
    }


def _pedestal_target_result(
    action: Callable[[], None],
    target_check: Callable[[dict[str, Any]], bool],
    *,
    datarefs: list[str] | None = None,
    commands: list[str] | None = None,
) -> dict[str, Any]:
    before = read_pedestal()
    action()
    time.sleep(0.15)
    after = read_pedestal()
    return {
        "success": target_check(after),
        "before": before,
        "after": after,
        "dataref_used": datarefs or [],
        "command_used": commands or [],
    }


def _write_array_index(dref: str, index: int, value: float) -> None:
    current = XP.read(dref)
    if not isinstance(current, list):
        raise MappingError(f"Dataref is not an array: {dref}")
    if index >= len(current):
        raise MappingError(f"Dataref array index {index} unavailable for {dref}")
    updated = list(current)
    updated[index] = value
    XP.write(dref, updated)


def _catalog_command(*names: str) -> str | None:
    for name in names:
        meta = CATALOG.get(name)
        if meta and meta.get("kind") == "command":
            return name
    return None


def _catalog_dataref(*names: str) -> str | None:
    for name in names:
        meta = CATALOG.get(name)
        if meta and meta.get("kind") == "dataref":
            return name
    return None


def _command_available(name: str) -> bool:
    XP.ensure_cache()
    return name in XP.commands


def _command_duration(command: str) -> float:
    if command == "toliss_airbus/speedbrake/hold_armed":
        return 0.5
    return 0.0


def _run_command_sequence(command: str, count: int, delay: float = 0.1) -> None:
    for _ in range(max(0, count)):
        XP.command(command, duration=_command_duration(command))
        time.sleep(delay)


def _state_command(group: str, name: str, state: str) -> str:
    commands = STATE_COMMANDS[group]
    key = f"{name}_{state}"
    if key in commands:
        return commands[key]
    key = f"{name}_toggle"
    if state == "toggle" and key in commands:
        return commands[key]
    raise MappingError(f"No command mapping for {group}.{name}.{state}")


@mcp.tool
def read_flight_state() -> dict[str, Any]:
    """Read flight state. Units: kt, Mach, ft, fpm, degrees, lat/lon degrees. Returns keys IAS, GS, Mach, baro_alt, radalt, vs, pitch, roll, hdg, lat, lon. Example: {'IAS': 250, 'baro_alt': 12000}."""
    m = READ_DREFS["flight_state"]
    d = _read_map(m)
    gs_ms = _read_std("groundspeed")
    gs = None if _num(gs_ms) is None else float(_num(gs_ms)) * 1.94384
    return {
        "IAS": d["ias"],
        "GS": gs,
        "Mach": d["mach"],
        "baro_alt": d["baro_alt"],
        "radalt": d["radalt"],
        "vs": d["vs"],
        "pitch": d["pitch"],
        "roll": d["roll"],
        "hdg": d["hdg"],
        "lat": _read_std("latitude"),
        "lon": _read_std("longitude"),
    }


@mcp.tool
def read_fcu() -> dict[str, Any]:
    """Read FCU selected/managed targets. Units: kt/Mach as displayed, degrees, ft, fpm. Returns spd, hdg, alt, vs, metric_alt. Example: {'spd': {'value': 250, 'managed': False}}."""
    d = _read_map(READ_DREFS["fcu"])
    spd_value = _read_fcu_direct_value("fcu_airspeed_dial", d["spd_value"])
    hdg_value = _read_fcu_heading_value()
    alt_value = _read_fcu_direct_value("fcu_altitude_dial", d["alt_value"])
    vs_value = _read_fcu_direct_value("fcu_vs_dial", d["vs_value"])
    trk_fpa = _bool(d["hdg_mode"])
    return {
        "spd": {"value": spd_value, "managed": _bool(d["spd_managed"])},
        "hdg": {"value": hdg_value, "managed": _bool(d["hdg_managed"]), "mode": "trk" if trk_fpa else "hdg"},
        "alt": {"value": alt_value, "managed": _bool(d["alt_managed"]), "step": 1000 if _bool(d["alt_step"]) else 100},
        "vs": {"value": vs_value, "managed": _bool(d["vs_managed"]), "mode": "fpa" if trk_fpa else "vs"},
        "metric_alt": _bool(d["metric_alt"]),
    }


@mcp.tool
def read_fma() -> dict[str, Any]:
    """Read raw ToLiss PFD FMA text grid. Returns rows with 3 fixed-width display rows, 5 positional columns (col1..col5), decoded text, and display color; raw preserves each ToLiss color-layer dataref as fixed-width text for debugging/reparsing. General Airbus FMA convention: col1 often carries A/THR modes, col2 vertical modes, col3 lateral modes, col4 approach/common annunciations, and col5 AP/FD/A-THR/CAT status, but callers should interpret text rather than rely on column names as semantics. Colors usually mean green=active, cyan/blue=armed/constraint, white=info/status, amber=warning/caution, magenta=managed/target guidance. Common texts include SPEED/MACH, HDG/TRK/NAV/LOC, ALT/ALT*/VS/FPA/CLB/DES/G/S, AP1/AP2, FD, A/THR, CAT. ap_status is a convenience field derived from AP1/AP2 engage readbacks, not parsed from the grid. Example: {'rows': [{'row': 1, 'cells': [{'col': 'col1', 'text': 'SPEED', 'color': 'green'}]}], 'ap_status': {'active': 'AP1'}}."""
    d = _read_map(READ_DREFS["fma"])
    raw = _fma_raw_layers(d)
    ap1 = _bool(XP.read(READ_DREFS["autoflight"]["ap1"]))
    ap2 = _bool(XP.read(READ_DREFS["autoflight"]["ap2"]))
    if ap1 and ap2:
        ap_active = "AP1+2"
    elif ap1:
        ap_active = "AP1"
    elif ap2:
        ap_active = "AP2"
    else:
        ap_active = ""

    return {
        "rows": _fma_rows(raw),
        "raw": raw,
        "ap_status": {"active": ap_active, "armed": ""},
    }


@mcp.tool
def read_autoflight() -> dict[str, Any]:
    """Read autoflight states. Units: booleans/mode integers. Returns ap1, ap2, athr, fd1, fd2, loc_armed, appr_armed, exped, trk_fpa_mode. Example: {'ap1': True, 'athr': True}."""
    d = _read_map(READ_DREFS["autoflight"])
    result = {k: (_bool(v) if k not in {"trk_fpa_mode", "vertical_mode"} else v) for k, v in d.items() if k != "vertical_mode"}
    vertical_mode = _num(d["vertical_mode"])
    result["exped"] = bool(vertical_mode is not None and vertical_mode > 110)
    return result


@mcp.tool
def read_engines() -> dict[str, Any]:
    """Read engine 1/2 indications. Units: percent, deg C, kg/h or ToLiss units, psi. Returns eng list with n1, n2, egt, ff, oil_temp, oil_press, master_switch, mode_selector. Example: {'eng': [{'n1': 22.1}]}."""
    d = _read_map(READ_DREFS["engines"])
    n2 = _read_std("engine_n2")
    oil_temp = _read_std("engine_oil_temp")
    engines = []
    for i in range(2):
        engines.append(
            {
                "n1": _idx(d["n1"], i),
                "n2": _idx(n2, i),
                "egt": _idx(d["egt"], i),
                "ff": _idx(d["ff"], i),
                "oil_temp": _idx(oil_temp, i),
                "oil_press": _idx(d["oil_press"], i),
                "master_switch": _idx(d["master_switch"], i),
                "mode_selector": d["mode_selector"],
            }
        )
    return {"eng": engines}


@mcp.tool
def read_overhead_full() -> dict[str, Any]:
    """Read overhead panels. Units: booleans/selector integers. Returns lights, antiice, packs, bleed, apu, electrical, fuel, hydraulic. Example: {'packs': {'1': True, '2': True}}."""
    d = _read_map(READ_DREFS["overhead"])
    return {
        "lights": {"raw_ohp": d["ohp_lights"]},
        "antiice": {"eng1": d["eng1_ai"], "eng2": d["eng2_ai"], "wing": d["wing_ai"]},
        "packs": {"1": d["pack1"], "2": d["pack2"]},
        "bleed": {"eng1": d["bleed1"], "eng2": d["bleed2"], "xbleed": d["xbleed"], "apu": d["apu_bleed"]},
        "apu": {"master": d["apu_master"], "start": None, "avail": d["apu_avail"]},
        "electrical": {"bat1": _idx(d["bat"], 0), "bat2": _idx(d["bat"], 1), "gen1": _idx(d["gen"], 0), "gen2": _idx(d["gen"], 1), "apu_gen": d["apu_gen"], "ext_pwr": d["ext_pwr"], "ac_ess_feed": d["ac_ess_feed"]},
        "fuel": {"pumps": d["fuel_pumps"], "xfeed": d["fuel_xfeed"]},
        "hydraulic": {"green": _idx(d["hyd_press"], 0), "blue": _idx(d["hyd_press"], 1), "yellow": _idx(d["hyd_press"], 2), "ptu": d["ptu"], "rat": d["rat"], "pumps": d["hyd_pump"]},
    }


@mcp.tool
def read_pedestal() -> dict[str, Any]:
    """Read pedestal controls. Units: selector positions, ratios 0-1, trim degrees. Returns flap_handle, flap_actual, slat_actual, speedbrake, parking_brake, autobrake, trim, gear, brake_fan. Example: {'gear': {'lever': 'down'}}."""
    d = _read_map(READ_DREFS["pedestal"])
    flap_handle = _read_flap_handle()
    flap_actual = _read_std("flap_actual_ratio")
    slat_left = _num(XP.read(_known("AirbusFBW/SlatPositionLWing")))
    slat_right = _num(XP.read(_known("AirbusFBW/SlatPositionRWing")))
    slat_actual = None
    if slat_left is not None and slat_right is not None:
        slat_actual = (float(slat_left) + float(slat_right)) / 2.0
    if _bool(d["autobrake_max"]):
        autobrake = "max"
    elif _bool(d["autobrake_med"]):
        autobrake = "med"
    elif _bool(d["autobrake_lo"]):
        autobrake = "lo"
    else:
        autobrake = "off"
    speedbrake_raw_ratio = _read_speedbrake_raw_ratio()
    return {
        "flap_handle": flap_handle,
        "flap_actual": flap_actual,
        "slat_actual": slat_actual,
        "speedbrake": {
            "handle": None if speedbrake_raw_ratio is None else max(speedbrake_raw_ratio, 0.0),
            "raw_ratio": speedbrake_raw_ratio,
            "armed": None if speedbrake_raw_ratio is None else speedbrake_raw_ratio < -0.25,
        },
        "parking_brake": d["parking_brake"],
        "autobrake": autobrake,
        "trim": {"stab": d["trim_stab"], "rudder": d["trim_rudder"]},
        "gear": {"lever": "down" if _bool(d["gear_lever"]) else "up", "position": {"nose": d["gear_nose"], "left": d["gear_left"], "right": d["gear_right"]}},
        "brake_fan": d["brake_fan"],
    }


@mcp.tool
def read_radios() -> dict[str, Any]:
    """Read RMP/ACP radio state. Units: MHz/kHz as ToLiss stores them, selector integers. Returns com, nav, adf, rmp, acp. Example: {'rmp': [{'on': True, 'active_freq': 118.0}]}."""
    d = _read_map(READ_DREFS["radios"])
    radio: dict[str, dict[str, Any]] = {}
    for channel in ("com1", "com2", "nav1", "nav2", "adf1", "adf2"):
        active_key, stby_key, from_raw, _ = _radio_keys(channel)
        radio[channel] = {
            "active": from_raw(_read_std(active_key)),
            "stby": from_raw(_read_std(stby_key)) if stby_key else None,
        }
    return {
        "com": [radio["com1"], radio["com2"]],
        "nav": [radio["nav1"], radio["nav2"]],
        "adf": [radio["adf1"], radio["adf2"]],
        "rmp": [
            {"on": _bool(d["rmp1_on"]), "active_freq": d["rmp1_active"]},
            {"on": _bool(d["rmp2_on"]), "active_freq": d["rmp2_active"]},
            {"on": _bool(d["rmp3_on"]), "active_freq": d["rmp3_active"]},
        ],
        "acp": {"capt": {"raw": d["acp1_switch"]}, "fo": {"raw": d["acp2_switch"]}},
    }


@mcp.tool
def read_atc() -> dict[str, Any]:
    """Read transponder and TCAS. Units: squawk digits, selector integers. Returns xpdr and tcas. Example: {'xpdr': {'code': '2200', 'mode': 'auto'}}."""
    d = _read_map(READ_DREFS["atc"])
    code = "".join(str(int(_num(d[f"xpdr{i}"]) or 0)) for i in range(1, 5))
    mode_raw = int(_num(d["xpdr_mode"]) or 0)
    tcas_mode_raw = int(_num(d["xpdr_mode"]) or 0)
    tcas_filter_raw = int(_num(_read_std("tcas_filter")) or 0)
    return {
        "xpdr": {"code": code, "mode": {0: "stby", 1: "auto", 2: "on"}.get(mode_raw, str(mode_raw)), "ident": None},
        "tcas": {
            "mode": TCAS_MODE_LABELS.get(tcas_mode_raw, str(tcas_mode_raw)),
            "range": d["tcas_range_capt"],
            "filter": {0: "all", 1: "abv", 2: "blw", 3: "n"}.get(tcas_filter_raw, str(tcas_filter_raw)),
            "status": d["tcas_status"],
        },
    }


# Display tools are registered by toliss_copilot.displays.
from .displays import mcdu_press, read_ecam, read_mcdu  # noqa: F401


@mcp.tool
def read_efis(side: Literal["capt", "fo"]) -> dict[str, Any]:
    """Read EFIS/ND controls. Units: selector integers, hPa/inHg raw value. side='capt'|'fo'. Returns nd, baro, ls_button. Example: {'nd': {'mode': 'arc', 'range': 20}}."""
    d = _read_map(READ_DREFS["efis"])
    p = "capt" if side == "capt" else "fo"
    mode_raw = int(_num(d[f"{p}_nd_mode"]) or 0)
    return {
        "nd": {
            "mode": {0: "rose", 1: "arc", 2: "plan", 3: "ils", 4: "vor"}.get(mode_raw, str(mode_raw)),
            "range": d[f"{p}_nd_range"],
            "options": {"cstr": _bool(d[f"{p}_cstr"]), "wpt": _bool(d[f"{p}_wpt"]), "vord": _bool(d[f"{p}_vord"]), "ndb": _bool(d[f"{p}_ndb"]), "arpt": _bool(d[f"{p}_arpt"])},
        },
        "baro": {"value": d[f"{p}_baro"], "std": _bool(d[f"{p}_baro_std"]), "unit": "inhg" if _bool(d[f"{p}_baro_unit"]) else "hpa"},
        "ls_button": _bool(d[f"{p}_ls"]),
    }


@mcp.tool
def read_weather_radar() -> dict[str, Any]:
    """Read weather radar panel. Units: selector integers, gain/tilt raw values. Returns mode, gain, tilt, multiscan, gcs. Example: {'mode': 'wx+t', 'tilt': 1.5}."""
    d = _read_map(READ_DREFS["weather_radar"])
    mode = int(_num(d["mode"]) or 0)
    return {"mode": {0: "off", 1: "std", 2: "wx", 3: "wx+t", 4: "turb", 5: "map"}.get(mode, str(mode)), "gain": d["gain"], "tilt": d["tilt"], "multiscan": _bool(d["multiscan"]), "gcs": _bool(d["gcs"])}


# SD page tools are registered by toliss_copilot.sd_pages.
from . import sd_pages as _sd_pages  # noqa: F401


@mcp.tool
def debug_search_xplane_names(term: str) -> dict[str, Any]:
    """Search loaded X-Plane Web API dataref and command names by substring. Units: raw names only. Returns matching datarefs and commands. Example: debug_search_xplane_names('speedbrake')."""
    if not term:
        raise ValueError("term is required")
    XP.ensure_cache()
    needle = term.lower()
    datarefs = sorted(name for name in XP.datarefs if needle in name.lower())
    commands = sorted(name for name in XP.commands if needle in name.lower())
    return {"term": term, "datarefs": datarefs, "commands": commands}


@mcp.tool
def set_fcu(channel: Literal["spd", "hdg", "alt", "vs"], value: float, managed: bool) -> dict[str, Any]:
    """Set FCU selected target. Units: spd kt/Mach raw, hdg deg, alt ft, vs fpm. managed=True always sends the FCU push command, False always sends the pull command; ALT writes the dial before push/pull so OP CLB/OP DES sees the new target. Changing an FCU dial does not guarantee aircraft response; AP engagement, side-stick input, current modes, and other external conditions can prevent or alter the actual flight-path response. After calling set_fcu, verify real aircraft motion with read_flight_state, especially hdg, vs, and baro_alt trending toward the target. read_fma mode confirmation is currently not reliable due to known dataref mapping issues, so use read_flight_state as the primary verification method until FMA mapping is fixed. Returns success,before,after,dataref_used,command_used. Example: set_fcu('spd', 250, False)."""
    if channel == "hdg":
        return _set_fcu_hdg(float(value), managed)
    if channel == "spd":
        return _set_fcu_direct("spd", float(value), managed, STANDARD_DREFS["fcu_airspeed_dial"])
    if channel == "vs":
        return _set_fcu_direct("vs", float(value), managed, STANDARD_DREFS["fcu_vs_dial"])
    return _set_fcu_alt(float(value), managed)


@mcp.tool
def set_autoflight(action: Literal["ap1", "ap2", "athr", "fd1", "fd2", "loc", "appr", "exped", "trk_fpa", "metric_alt", "athr_disconnect"], state: Literal["toggle", "on", "off"] = "toggle") -> dict[str, Any]:
    """Set autoflight button state. Units: state is toggle/on/off; on/off use current read then command if needed. Returns success,before,after,dataref_used. Example: set_autoflight('ap1','on')."""
    cmd = COMMANDS[action]
    read_key = {"trk_fpa": "trk_fpa_mode", "metric_alt": "metric_alt", "athr_disconnect": "athr"}.get(action, action)

    def current() -> bool:
        try:
            return _bool(read_autoflight().get(read_key))
        except Exception:
            return False

    def do() -> None:
        if state == "toggle" or (state == "on" and not current()) or (state == "off" and current()):
            XP.command(cmd)

    return _write_result(read_autoflight, do, [cmd])


@mcp.tool
def set_lights(name: str, state: str) -> dict[str, Any]:
    """Set lights. name examples: beacon, strobe, nav, wing, landing_l, landing_r, nose, rwy_turnoff, dome, seatbelt, nosmoking, emer_exit. state: on/off/auto/bright/dim/toggle where mapped. Returns success,before,after,dataref_used. Example: set_lights('beacon','on')."""
    aliases = {"on": "on", "off": "off", "auto": "toggle", "bright": "up", "dim": "down", "up": "up", "down": "down", "toggle": "toggle"}
    suffix = aliases.get(state, state)
    key = f"{name}_{suffix}"
    if key not in STATE_COMMANDS["lights"]:
        raise MappingError(f"Light command not mapped: {name}.{state}")
    cmd = STATE_COMMANDS["lights"][key]
    return _write_result(read_overhead_full, lambda: XP.command(cmd), [cmd])


@mcp.tool
def set_brightness(display: Literal["pfd", "nd_inner", "nd_outer", "ecam_upper", "ecam_lower", "mcdu", "integral", "panel", "flood"], value: float, side: Literal["capt", "fo"] = "capt") -> dict[str, Any]:
    """Set brightness 0-1. display supports pfd, nd_inner, nd_outer, ecam_upper, ecam_lower, mcdu, integral, panel, flood; side capt/fo where applicable. Returns success,before,after,dataref_used. Example: set_brightness('panel',0.7)."""
    value = max(0.0, min(1.0, value))
    if display in {"integral", "panel", "flood"}:
        dref = WRITE_DREFS[{"integral": "integral_brightness", "panel": "panel_brightness", "flood": "flood_brightness"}[display]]
        return _write_result(lambda: {"value": XP.read(dref)}, lambda: XP.write(dref, value), [dref])
    if display == "mcdu":
        _not_impl("set_brightness", ["mcdu brightness is out of scope"])

    index = DISPLAY_BRIGHTNESS_INDEX[display]
    airbus_dref = "AirbusFBW/DUBrightness"
    sim_dref = STANDARD_DREFS["instrument_brightness"]

    def read_display_brightness() -> dict[str, Any]:
        try:
            source = airbus_dref
            values = XP.read(airbus_dref)
        except MappingError:
            source = sim_dref
            values = XP.read(sim_dref)
        return {"source": source, "index": index, "values": values, "value": _idx(values, index)}

    def action() -> None:
        try:
            _write_array_index(airbus_dref, index, value)
        except MappingError:
            _write_array_index(sim_dref, index, value)

    return _write_result(read_display_brightness, action, [airbus_dref, sim_dref])


@mcp.tool
def set_antiice(name: Literal["eng1", "eng2", "wing", "probe"], state: Literal["on", "off", "auto", "toggle"]) -> dict[str, Any]:
    """Set anti-ice. name eng1/eng2/wing/probe; state on/off/auto/toggle. Probe is not mapped in catalog. Returns success,before,after,dataref_used. Example: set_antiice('eng1','on')."""
    if name == "probe":
        _not_impl("set_antiice", ["probe anti-ice command"])
    cmd = _state_command("antiice", name, "toggle" if state == "auto" else state)
    return _write_result(read_overhead_full, lambda: XP.command(cmd), [cmd])


@mcp.tool
def set_pneumatic(name: Literal["pack1", "pack2", "bleed1", "bleed2", "xbleed", "apu_bleed", "ram_air"], value: Any) -> dict[str, Any]:
    """Set pneumatic item. name pack1/pack2/bleed1/bleed2/xbleed/apu_bleed/ram_air; value on/off/toggle or raw value if direct mapped. Returns success,before,after,dataref_used. Example: set_pneumatic('pack1','off')."""
    state = str(value)
    if name in {"pack1", "pack2", "apu_bleed"}:
        cmd = _state_command("pneumatic", name, state)
        return _write_result(read_overhead_full, lambda: XP.command(cmd), [cmd])
    drefs = {"bleed1": "AirbusFBW/ENG1BleedSwitch", "bleed2": "AirbusFBW/ENG2BleedSwitch", "xbleed": "AirbusFBW/XBleedSwitch", "ram_air": "AirbusFBW/RamAirValveSD"}
    dref = _known(drefs[name])
    return _write_result(read_overhead_full, lambda: XP.write(dref, 1 if state == "on" else 0 if state == "off" else value), [dref])


@mcp.tool
def set_electrical(name: Literal["bat1", "bat2", "gen1", "gen2", "apu_gen", "ext_pwr", "ac_ess_feed", "galley"], state: str) -> dict[str, Any]:
    """Set electrical item. name bat1/bat2/gen1/gen2/apu_gen/ext_pwr/ac_ess_feed/galley; state on/off/toggle where mapped. Returns success,before,after,dataref_used. Example: set_electrical('bat1','on')."""
    if name in {"bat1", "bat2"}:
        cmd = _state_command("electrical", name, state)
        return _write_result(read_overhead_full, lambda: XP.command(cmd), [cmd])
    if name == "ext_pwr":
        cmd = STATE_COMMANDS["electrical"]["ext_pwr_toggle"]
        return _write_result(read_overhead_full, lambda: XP.command(cmd), [cmd])
    _not_impl("set_electrical", [f"{name} command"])


@mcp.tool
def set_fuel(name: Literal["lp1", "lp2", "cp1", "cp2", "rp1", "rp2", "xfeed", "acttrns", "actmode"], state: str) -> dict[str, Any]:
    """Set fuel item. name lp1/lp2/cp1/cp2/rp1/rp2/xfeed/acttrns/actmode; state on/off/toggle where mapped. Returns success,before,after,dataref_used. Example: set_fuel('lp1','on')."""
    if name == "cp2":
        name = "rp1"  # catalog has left/right center, no cp2 name.
    if f"{name}_{state}" in STATE_COMMANDS["fuel"]:
        cmd = STATE_COMMANDS["fuel"][f"{name}_{state}"]
        return _write_result(read_overhead_full, lambda: XP.command(cmd), [cmd])
    _not_impl("set_fuel", [f"{name}.{state}"])


@mcp.tool
def set_hydraulic(name: Literal["g_eng1", "g_eng2", "b_eng1", "b_eng2", "y_eng1", "y_eng2", "ptu", "rat"], state: str) -> dict[str, Any]:
    """Set hydraulic item. name g_eng1/g_eng2/b_eng1/b_eng2/y_eng1/y_eng2/ptu/rat; state on/off/toggle. Only RAT command is catalog mapped. Returns success,before,after,dataref_used. Example: set_hydraulic('rat','on')."""
    if name == "rat":
        cmd = _known("toliss_airbus/hydcommands/PressRATReleaseButton")
        return _write_result(read_overhead_full, lambda: XP.command(cmd), [cmd])
    _not_impl("set_hydraulic", [f"{name} hydraulic command"])


@mcp.tool
def set_radio(channel: Literal["com1", "com2", "nav1", "nav2", "adf1", "adf2"], action: Literal["set_stby", "swap", "set_active"], value: float | None = None) -> dict[str, Any]:
    """Set radio. Units: MHz/kHz as ToLiss RMP raw value. channel com1/com2/nav1/nav2/adf1/adf2; action set_stby/swap/set_active. Returns success,before,after,dataref_used. Example: set_radio('com1','set_stby',118.7)."""
    active_key, stby_key, _, to_raw = _radio_keys(channel)
    active_dref = STANDARD_DREFS[active_key]
    stby_dref = STANDARD_DREFS[stby_key] if stby_key else None

    def swap_values() -> None:
        if stby_dref is None:
            _not_impl("set_radio", [f"{channel} standby frequency for swap"])
        active_raw = XP.read(active_dref)
        stby_raw = XP.read(stby_dref)
        XP.write(active_dref, stby_raw)
        XP.write(stby_dref, active_raw)

    if action == "swap":
        return _write_result(read_radios, swap_values, [active_dref, stby_dref or ""])
    if value is None:
        raise ValueError("value is required for set_stby/set_active")
    raw_value = to_raw(value)
    if action == "set_stby":
        if stby_dref is None:
            _not_impl("set_radio", [f"{channel} standby frequency"])
        return _write_result(read_radios, lambda: XP.write(stby_dref, raw_value), [stby_dref])
    if action == "set_active":
        if stby_dref is None:
            return _write_result(read_radios, lambda: XP.write(active_dref, raw_value), [active_dref])

        def set_active_via_stby_swap() -> None:
            XP.write(stby_dref, raw_value)
            swap_values()

        return _write_result(read_radios, set_active_via_stby_swap, [stby_dref, active_dref])
    raise ValueError(f"Unsupported radio action: {action}")


@mcp.tool
def set_acp(side: Literal["capt", "fo"], action: Literal["select_rx", "toggle_tx", "toggle_int_rad", "loudspeaker", "volume"], channel: str | None = None, value: float | None = None) -> dict[str, Any]:
    """Set ACP. side capt/fo; action select_rx/toggle_tx/toggle_int_rad/loudspeaker/volume; channel vhf1/vhf2/vhf3/hf1/hf2/int/cab/pa/nav1/nav2/adf1/adf2/mkr. Returns success,before,after,dataref_used. Example: set_acp('capt','select_rx','vhf1')."""
    acp = "ACP1" if side == "capt" else "ACP2"
    if action == "select_rx" and channel in {"vhf1", "vhf2", "vhf3"}:
        cmd = _known(f"AirbusFBW/{acp}/{channel.upper()}Press")
        return _write_result(read_radios, lambda: XP.command(cmd), [cmd])
    _not_impl("set_acp", [f"{side}.{action}.{channel}"])


@mcp.tool
def set_atc(name: Literal["code", "mode", "ident", "tcas_mode", "tcas_range", "tcas_filter", "alt_rptg"], value: Any) -> dict[str, Any]:
    """Set ATC/TCAS. name code/mode/ident/tcas_mode/tcas_range/tcas_filter/alt_rptg. code is four digits, mode stby/auto/on, ident triggers ident. Returns success,before,after,dataref_used. Example: set_atc('code','2200')."""
    if name == "ident":
        cmd = _known("sim/transponder/transponder_ident")
        return _write_result(read_atc, lambda: XP.command(cmd), [cmd])
    if name == "code":
        code = str(value).zfill(4)
        drefs = [_known(f"AirbusFBW/XPDR{i}") for i in range(1, 5)]
        return _write_result(read_atc, lambda: [XP.write(d, int(v)) for d, v in zip(drefs, code)], drefs)
    if name in {"mode", "tcas_mode"}:
        if name == "tcas_mode":
            val = _tcas_mode_value(value)
            dref = WRITE_DREFS["xpdr_mode"]
            target = TCAS_MODE_LABELS[val]
            before = read_atc()
            if before["tcas"]["mode"] == target:
                return _noop_success(before)
            XP.write(dref, val)
            time.sleep(0.15)
            after = read_atc()
            return {"success": after["tcas"]["mode"] == target, "before": before, "after": after, "dataref_used": [dref], "command_used": []}
        else:
            val = {"stby": 0, "auto": 1, "on": 2}.get(str(value), value)
            dref = WRITE_DREFS["xpdr_mode"]
        return _write_result(read_atc, lambda: XP.write(dref, val), [dref])
    if name == "tcas_filter":
        val = {"all": 0, "abv": 1, "blw": 2, "n": 3}.get(str(value), value)
        dref = STANDARD_DREFS["tcas_filter"]
        return _write_result(read_atc, lambda: XP.write(dref, val), [dref])
    if name == "tcas_range":
        _not_impl("set_atc", ["tcas_range: standard dataref unavailable; coupled to ND range in ToLiss"])
    if name == "alt_rptg":
        dref = WRITE_DREFS["xpdr_alt"]
        return _write_result(read_atc, lambda: XP.write(dref, 1 if str(value) == "on" else 0), [dref])
    _not_impl("set_atc", [name])


@mcp.tool
def set_pedestal(name: str, value: Any) -> dict[str, Any]:
    """Set pedestal item. name flap, speedbrake, parking_brake, autobrake, trim_stab, trim_rudder, gear, brake_fan, engine_master_1/2, engine_mode. Returns success,before,after,dataref_used. Example: set_pedestal('gear','down')."""
    if name == "parking_brake":
        cmd = _known("toliss_airbus/park_brake_set" if value == "on" else "toliss_airbus/park_brake_release")
        return _write_result_with_commands(read_pedestal, lambda: XP.command(cmd), commands=[cmd])
    if name == "brake_fan":
        cmd = _known("toliss_airbus/gear/brake_fan")
        return _write_result_with_commands(read_pedestal, lambda: XP.command(cmd), commands=[cmd])
    if name == "autobrake":
        target = str(value).lower()
        before = read_pedestal()
        if before.get("autobrake") == target:
            return _noop_success(before)
        command_map = {
            "off": _catalog_command("toliss_airbus/abrk/pos_disarm"),
            "lo": _catalog_command("toliss_airbus/abrk/pos_lo", "AirbusFBW/AbrkLo"),
            "med": _catalog_command("toliss_airbus/abrk/pos_2", "AirbusFBW/AbrkMed"),
            "max": _catalog_command("toliss_airbus/abrk/pos_hi", "AirbusFBW/AbrkMax"),
        }
        cmd = command_map.get(target)
        if not cmd:
            _not_impl("set_pedestal", [f"autobrake.{value} command"])
        return _pedestal_target_result(lambda: XP.command(cmd), lambda after: after["autobrake"] == target, commands=[cmd])
    if name == "flap":
        target = int(value)
        if target < 0 or target > 4:
            raise ValueError("flap value must be an integer 0-4")
        up_cmd = _catalog_command("toliss_airbus/FlapsUp", "AirbusFBW/FlapsUp") or STANDARD_COMMANDS["flaps_up"]
        down_cmd = _catalog_command("toliss_airbus/FlapsDown", "AirbusFBW/FlapsDown") or STANDARD_COMMANDS["flaps_down"]

        def move_flaps() -> None:
            for _ in range(8):
                current = _read_flap_handle()
                if current is None:
                    _not_impl("set_pedestal", ["flap handle readback"])
                if current == target:
                    return
                XP.command(down_cmd if target > int(current) else up_cmd)
                time.sleep(0.1)

        return _pedestal_target_result(move_flaps, lambda after: after["flap_handle"] == target, commands=[up_cmd, down_cmd])
    if name == "gear":
        cmd = _catalog_command("toliss_airbus/GearDown", "AirbusFBW/GearDown") if value == "down" else _catalog_command("toliss_airbus/GearUp", "AirbusFBW/GearUp")
        cmd = cmd or (STANDARD_COMMANDS["gear_down"] if value == "down" else STANDARD_COMMANDS["gear_up"])
        return _pedestal_target_result(lambda: XP.command(cmd), lambda after: after["gear"]["lever"] == value, commands=[cmd])
    if name == "speedbrake":
        if isinstance(value, str):
            target = value.lower()
            if target not in {"armed", "disarmed"}:
                raise ValueError("speedbrake string value must be 'armed' or 'disarmed'")
            before = read_pedestal()
            current = before["speedbrake"].get("armed")
            if current is None:
                raise MappingError(
                    "Cannot set speedbrake armed state idempotently: no speedbrake armed readback dataref is available."
                )
            desired = target == "armed"
            if current == desired:
                return _noop_success(before)
            if target == "armed":
                cmd = _known("toliss_airbus/speedbrake/hold_armed")
                return _pedestal_target_result(
                    lambda: XP.command(cmd, duration=_command_duration(cmd)),
                    lambda after: after["speedbrake"].get("armed") is True,
                    commands=[cmd],
                )
            ratio_dref = STANDARD_DREFS["speedbrake_ratio"]
            if XP.is_writable(ratio_dref):
                return _pedestal_target_result(
                    lambda: XP.write(ratio_dref, 0.0),
                    lambda after: after["speedbrake"].get("armed") is False,
                    datarefs=[ratio_dref],
                )
            down_cmd = STANDARD_COMMANDS["speedbrake_down_one"]

            def disarm_speedbrake() -> None:
                for _ in range(10):
                    state = read_pedestal()["speedbrake"]
                    if state.get("armed") is False and (_num(state.get("handle")) or 0.0) <= 0.05:
                        return
                    XP.command(down_cmd)
                    time.sleep(0.1)

            return _pedestal_target_result(disarm_speedbrake, lambda after: after["speedbrake"].get("armed") is False, commands=[down_cmd])
        target = max(0.0, min(1.0, float(value)))
        up_cmd = STANDARD_COMMANDS["speedbrake_up_one"]
        down_cmd = STANDARD_COMMANDS["speedbrake_down_one"]

        def move_speedbrake() -> None:
            for _ in range(10):
                current = _num(read_pedestal()["speedbrake"]["handle"])
                if current is not None and abs(float(current) - target) < 0.11:
                    return
                XP.command(up_cmd if target > float(current or 0) else down_cmd)
                time.sleep(0.1)

        return _pedestal_target_result(
            move_speedbrake,
            lambda after: _num(after["speedbrake"]["handle"]) is not None and abs(float(_num(after["speedbrake"]["handle"])) - target) < 0.11,
            commands=[up_cmd, down_cmd],
        )
    if name == "engine_mode":
        command_map = {
            "crank": _known("toliss_airbus/engcommands/EngineModeSwitchToCrank"),
            "norm": _known("toliss_airbus/engcommands/EngineModeSwitchToNorm"),
            "ign_start": _known("toliss_airbus/engcommands/EngineModeSwitchToStart"),
        }
        cmd = command_map[str(value)]
        return _write_result_with_commands(read_pedestal, lambda: XP.command(cmd), commands=[cmd])
    if name in {"trim_stab", "trim_rudder"}:
        dref = WRITE_DREFS[name]
        if not XP.is_writable(dref):
            _not_impl("set_pedestal", [f"{name}: no command mapping and dataref is read-only"])
        return _write_result_with_commands(read_pedestal, lambda: XP.write(dref, value), datarefs=[dref])
    if name in {"engine_master_1", "engine_master_2"}:
        eng = "1" if name.endswith("_1") else "2"
        cmd = _known(f"toliss_airbus/engcommands/Master{eng}{'On' if value == 'on' else 'Off'}")
        return _write_result_with_commands(read_engines, lambda: XP.command(cmd), commands=[cmd])
    _not_impl("set_pedestal", [name])


@mcp.tool
def set_efis(side: Literal["capt", "fo"], name: str, value: Any) -> dict[str, Any]:
    """Set EFIS. side capt/fo; name nd_mode, nd_range, option_cstr/wpt/vord/ndb/arpt, baro_value, baro_std, baro_unit, ls. Returns success,before,after,dataref_used. Example: set_efis('capt','option_wpt','toggle')."""
    p = "capt" if side == "capt" else "fo"
    if name.startswith("option_"):
        opt = name.removeprefix("option_")
        cmd_name = {"capt": "Capt", "fo": "Co"}[p] + {"cstr": "Cstr", "wpt": "Wpt", "vord": "VorD", "ndb": "Ndb", "arpt": "Arpt"}[opt] + "PushButton"
        cmd = _known(f"toliss_airbus/dispcommands/{cmd_name}")
        return _write_result(lambda: read_efis(side), lambda: XP.command(cmd), [cmd])
    if name == "ls":
        cmd = _known(f"toliss_airbus/dispcommands/{'Capt' if p == 'capt' else 'Co'}LSButtonPush")
        return _write_result(lambda: read_efis(side), lambda: XP.command(cmd), [cmd])
    if name == "baro_std":
        cmd = _known("toliss_airbus/capt_baro_push" if p == "capt" else "toliss_airbus/copilot_baro_push")
        return _write_result(lambda: read_efis(side), lambda: XP.command(cmd), [cmd])
    if name == "baro_value":
        dref = WRITE_DREFS["baro_capt" if p == "capt" else "baro_fo"]
        return _write_result(lambda: read_efis(side), lambda: XP.write(dref, value), [dref])
    drefs = {"nd_mode": f"AirbusFBW/NDmode{'Capt' if p == 'capt' else 'FO'}", "nd_range": f"AirbusFBW/NDrange{'Capt' if p == 'capt' else 'FO'}", "baro_unit": f"AirbusFBW/BaroUnit{'Capt' if p == 'capt' else 'FO'}"}
    if name in drefs:
        dref = _known(drefs[name])
        return _write_result(lambda: read_efis(side), lambda: XP.write(dref, value if name != "baro_unit" else {"hpa": 0, "inhg": 1, "toggle": 1}.get(str(value), value)), [dref])
    _not_impl("set_efis", [name])


@mcp.tool
def set_ecam(action: Literal["clr", "rcl", "emer_canc", "sts", "all", "page"], page: str | None = None) -> dict[str, Any]:
    """Set ECAM/ECP. action clr/rcl/emer_canc/sts/all/page; page eng/bleed/press/elec/hyd/fuel/apu/cond/door/wheel/fctl. Returns success,before,after,dataref_used. Example: set_ecam('page','hyd')."""
    if action == "all":
        cmd = _known("AirbusFBW/ECAMAll")
    elif action == "rcl":
        cmd = _known("AirbusFBW/ECAMRecall")
    elif action == "clr":
        cmd = _known("AirbusFBW/ECP/CaptainClear")
    elif action == "sts":
        cmd = _known("AirbusFBW/ECP/SelectStatusPage")
    elif action == "page":
        if not page:
            raise ValueError("page is required when action='page'")
        page_map = {"eng": "Engine", "bleed": "Bleed", "press": "Press", "elec": "ElecAC", "hyd": "Hydraulic", "fuel": "Fuel", "apu": "APU", "cond": "Conditioning", "door": "DoorOxy", "wheel": "Wheel", "fctl": "FlightControl"}
        cmd = _known(f"AirbusFBW/ECP/Select{page_map[page]}Page")
    else:
        _not_impl("set_ecam", [action])
    return _write_result(lambda: read_ecam("sd"), lambda: XP.command(cmd), [cmd])


@mcp.tool
def set_weather_radar(name: Literal["mode", "gain", "tilt", "multiscan", "gcs"], value: Any) -> dict[str, Any]:
    """Set weather radar. name mode/gain/tilt/multiscan/gcs; mode off/std/wx/wx+t/turb/map or raw int; gain/tilt numeric. Returns success,before,after,dataref_used. Example: set_weather_radar('mode','wx+t')."""
    key = {"mode": "wx_mode", "gain": "wx_gain", "tilt": "wx_tilt", "multiscan": "wx_multiscan", "gcs": "wx_gcs"}[name]
    dref = WRITE_DREFS[key]
    val = {"off": 0, "std": 1, "wx": 2, "wx+t": 3, "turb": 4, "map": 5, "on": 1, "true": 1, "off": 0, "false": 0}.get(str(value).lower(), value)
    return _write_result(read_weather_radar, lambda: XP.write(dref, val), [dref])


def smoke_test(live: bool = False) -> dict[str, Any]:
    """Import/list-tool smoke test, with optional live read_* calls when X-Plane is running."""
    from . import displays, sd_pages

    async def list_tool_names() -> list[str]:
        tools = await mcp.list_tools()
        return sorted(getattr(tool, "name", "") for tool in tools)

    tool_names = asyncio.run(list_tool_names())
    result: dict[str, Any] = {"import_ok": True, "tool_count": len(tool_names), "tools": tool_names}
    if not live:
        return result

    read_calls: dict[str, Callable[[], Any]] = {
        "read_flight_state": read_flight_state,
        "read_fcu": read_fcu,
        "read_fma": read_fma,
        "read_autoflight": read_autoflight,
        "read_engines": read_engines,
        "read_overhead_full": read_overhead_full,
        "read_pedestal": read_pedestal,
        "read_radios": read_radios,
        "read_atc": read_atc,
        "read_ecam_ewd": lambda: displays.read_ecam("ewd"),
        "read_ecam_sd": lambda: displays.read_ecam("sd"),
        "read_mcdu_capt": lambda: displays.read_mcdu("capt"),
        "read_mcdu_fo": lambda: displays.read_mcdu("fo"),
        "read_efis_capt": lambda: read_efis("capt"),
        "read_efis_fo": lambda: read_efis("fo"),
        "read_weather_radar": read_weather_radar,
        "read_sd_eng": sd_pages.read_sd_eng,
        "read_sd_bleed": sd_pages.read_sd_bleed,
        "read_sd_press": sd_pages.read_sd_press,
        "read_sd_elec": sd_pages.read_sd_elec,
        "read_sd_hyd": sd_pages.read_sd_hyd,
        "read_sd_fuel": sd_pages.read_sd_fuel,
        "read_sd_apu": sd_pages.read_sd_apu,
        "read_sd_cond": sd_pages.read_sd_cond,
        "read_sd_door": sd_pages.read_sd_door,
        "read_sd_wheel": sd_pages.read_sd_wheel,
        "read_sd_fctl": sd_pages.read_sd_fctl,
        "read_sd_crz": sd_pages.read_sd_crz,
    }
    live_results: dict[str, str] = {}
    for name, fn in read_calls.items():
        try:
            fn()
            live_results[name] = "ok"
        except Exception as exc:
            live_results[name] = f"{type(exc).__name__}: {exc}"
    result["live_reads"] = live_results
    return result


if __name__ == "__main__":
    mcp.run()


