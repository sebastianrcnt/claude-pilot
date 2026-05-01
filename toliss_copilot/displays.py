from __future__ import annotations

import base64
from typing import Any, Literal

from .server import CATALOG, COMMANDS, MappingError, XP, _known, mcp

def _decode_toliss_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        try:
            raw = base64.b64decode(value, validate=True)
            return raw.rstrip(b"\x00").decode("ascii", errors="replace").rstrip()
        except Exception:
            return value.rstrip("\x00").rstrip()
    if isinstance(value, list):
        try:
            raw = bytes(int(item) & 0xFF for item in value)
            return raw.rstrip(b"\x00").decode("ascii", errors="replace").rstrip()
        except Exception:
            return ""
    if isinstance(value, bytes):
        return value.rstrip(b"\x00").decode("ascii", errors="replace").rstrip()
    return str(value).rstrip("\x00").rstrip()


ECAM_COLORS = {"w": "white", "g": "green", "b": "blue", "a": "amber", "r": "red"}


def _ecam_text_name(display: Literal["ewd", "sd"], line: int, suffix: str) -> str | None:
    if display == "ewd":
        name = f"AirbusFBW/EWD{line}{suffix}Text"
        return name if name in CATALOG else None
    candidates = (
        f"AirbusFBW/SDline{line}{suffix}",
        f"AirbusFBW/SDLine{line}{suffix}",
        f"AirbusFBW/SDtext{line}{suffix}",
        f"AirbusFBW/SDText{line}{suffix}",
        f"AirbusFBW/SD{line}{suffix}Text",
    )
    return next((name for name in candidates if name in CATALOG), None)


def _colored_lines(display: Literal["ewd", "sd"], max_lines: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i in range(1, max_lines + 1):
        for suffix, color in ECAM_COLORS.items():
            name = _ecam_text_name(display, i, suffix)
            if not name:
                continue
            try:
                text = _decode_toliss_text(XP.read(name))
            except Exception:
                text = ""
            if text:
                out.append({"line": i, "color": color, "text": text})
    return out


MCDU_COLORS = {
    "w": "white",
    "g": "green",
    "b": "blue",
    "a": "amber",
    "m": "magenta",
    "s": "cyan",
    "y": "yellow",
}


MCDU_KEY_SUFFIXES: dict[str, str] = {
    **{chr(code): f"Key{chr(code)}" for code in range(ord("A"), ord("Z") + 1)},
    **{str(digit): f"Key{digit}" for digit in range(10)},
    "DOT": "KeyDecimal",
    "SLASH": "KeySlash",
    "SP": "KeySpace",
    "PLUSMINUS": "KeyPM",
    "CLR": "KeyClear",
    "OVFY": "KeyOverfly",
    "DIR": "DirTo",
    "PROG": "Prog",
    "PERF": "Perf",
    "INIT": "Init",
    "DATA": "Data",
    "FPLN": "Fpln",
    "RADNAV": "RadNav",
    "FUELPRED": "FuelPred",
    "SECFPL": "SecFpln",
    "ATCCOMM": "ATC",
    "MENU": "Menu",
    "AIRPORT": "Airport",
    "NEXTPAGE": "SlewRight",
    "PREVPAGE": "SlewLeft",
    "UP": "SlewUp",
    "DOWN": "SlewDown",
    "BRTUP": "KeyBright",
    "BRTDN": "KeyDim",
}
for _side in ("L", "R"):
    for _index in range(1, 7):
        MCDU_KEY_SUFFIXES[f"LSK{_index}{_side}"] = f"LSK{_index}{_side}"


def _mcdu_segments(mcdu: int, parts: list[str]) -> list[dict[str, str]]:
    segments: list[dict[str, str]] = []
    for part in parts:
        for suffix, color in MCDU_COLORS.items():
            name = f"AirbusFBW/MCDU{mcdu}{part}{suffix}"
            if name not in CATALOG:
                continue
            try:
                text = _decode_toliss_text(XP.read(name))
            except Exception:
                text = ""
            if text:
                segments.append({"text": text, "color": color})
    return segments


def _segments_text(segments: list[dict[str, str]]) -> str:
    return "".join(segment["text"] for segment in segments)


def _normalize_lsk(value: str) -> str:
    normalized = value.upper()
    if len(normalized) == 2 and normalized[0] in {"L", "R"} and normalized[1] in "123456":
        return f"LSK{normalized[1]}{normalized[0]}"
    return normalized


def _mcdu_text_to_keys(text: str) -> list[str]:
    keys: list[str] = []
    for char in text.upper():
        if "A" <= char <= "Z" or "0" <= char <= "9":
            keys.append(char)
        elif char == ".":
            keys.append("DOT")
        elif char == "/":
            keys.append("SLASH")
        elif char == " ":
            keys.append("SP")
        elif char == "-":
            keys.append("PLUSMINUS")
        else:
            raise ValueError(f"Unsupported MCDU text character: {char!r}")
    return keys


def _mcdu_command(side: Literal["capt", "fo"], key: str) -> str:
    mcdu = 1 if side == "capt" else 2
    normalized = _normalize_lsk(key)
    suffix = MCDU_KEY_SUFFIXES.get(normalized)
    if suffix is None:
        raise ValueError(f"Unsupported MCDU key: {key}")
    command = f"AirbusFBW/MCDU{mcdu}{suffix}"
    if CATALOG.get(command, {}).get("kind") != "command":
        raise MappingError(f"MCDU command not found in catalog: {command}")
    return command


@mcp.tool
def read_ecam(side: Literal["ewd", "sd"]) -> dict[str, Any]:
    """Read ECAM text. Units: decoded ASCII text and color names. side='ewd' or 'sd'. Returns lines with line,color,text and current_sd_page for sd. Example: {'lines': [{'line': 1, 'text': 'APU AVAIL', 'color': 'green'}]}."""
    if side == "ewd":
        return {"lines": _colored_lines("ewd", 7), "current_sd_page": None}
    page = XP.read(_known("AirbusFBW/SDPage"))
    return {"lines": _colored_lines("sd", 18), "current_sd_page": page}


@mcp.tool
def read_mcdu(side: Literal["capt", "fo"]) -> dict[str, Any]:
    """Read MCDU display text only. Units: decoded ASCII, 0-based screen lines, color names. side='capt' for MCDU1 or 'fo' for MCDU2. Returns side, 14 line objects with type/text/color segments, and scratchpad text. Example: {'side': 'capt', 'scratchpad': 'ENTER DEST'}."""
    mcdu = 1 if side == "capt" else 2
    lines: list[dict[str, Any]] = [
        {"line": 0, "type": "title", "segments": _mcdu_segments(mcdu, ["title", "stitle"])},
    ]
    for pair in range(1, 7):
        lines.append(
            {
                "line": pair * 2 - 1,
                "type": "label",
                "segments": _mcdu_segments(mcdu, [f"label{pair}"]),
            }
        )
        lines.append(
            {
                "line": pair * 2,
                "type": "content",
                "segments": _mcdu_segments(mcdu, [f"cont{pair}", f"scont{pair}"]),
            }
        )
    scratchpad_segments = _mcdu_segments(mcdu, ["sp"])
    lines.append({"line": 13, "type": "scratchpad", "segments": scratchpad_segments})
    return {"side": side, "lines": lines, "scratchpad": _segments_text(scratchpad_segments)}


@mcp.tool
def mcdu_press(
    side: Literal["capt", "fo"],
    keys: list[str] | None = None,
    text: str | None = None,
    followup_lsk: str | None = None,
) -> dict[str, Any]:
    """Press MCDU keys. Units: command sequence with 50 ms spacing. Provide exactly one of keys or text; text supports A-Z, 0-9, '.', '/', space, '-'. followup_lsk accepts L1-L6 or R1-R6. Returns success, keys_pressed, scratchpad_after. Example: mcdu_press('capt', text='AA1912', followup_lsk='L1')."""
    if (keys is None) == (text is None):
        raise ValueError("Specify exactly one of keys or text")
    sequence = [_normalize_lsk(key.upper()) for key in keys] if keys is not None else _mcdu_text_to_keys(text or "")
    if followup_lsk:
        sequence.append(_normalize_lsk(followup_lsk))
    if not sequence:
        raise ValueError("MCDU key sequence is empty")
    commands = [_mcdu_command(side, key) for key in sequence]
    for command in commands:
        XP.command(command)
        time.sleep(0.05)
    after = read_mcdu(side)
    return {"success": True, "keys_pressed": sequence, "scratchpad_after": after["scratchpad"], "command_used": commands}



