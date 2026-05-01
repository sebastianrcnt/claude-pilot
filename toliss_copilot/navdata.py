"""X-Plane nav data loader: airports (earth_aptmeta.dat), fixes (earth_fix.dat), navaids (earth_nav.dat)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


NavType = Literal["airport", "fix", "navaid"]

NAV_TYPE_NAMES = {
    2: "NDB", 3: "VOR", 4: "ILS-LOC", 5: "LOC", 6: "GS",
    7: "OM", 8: "MM", 9: "IM", 12: "DME", 13: "DME",
}


@dataclass
class NavEntry:
    ident: str
    lat: float
    lon: float
    type: NavType
    name: str = ""
    freq_mhz: float | None = None
    nav_subtype: str | None = None  # VOR/NDB/ILS etc.
    course_deg: float | None = None  # runway course for ILS localizers
    runway: str | None = None  # runway designator e.g. "34R"


@dataclass
class NavDatabase:
    airports: dict[str, NavEntry] = field(default_factory=dict)
    fixes: dict[str, list[NavEntry]] = field(default_factory=dict)
    navaids: dict[str, list[NavEntry]] = field(default_factory=dict)
    ils: dict[str, list[NavEntry]] = field(default_factory=dict)

    def search(self, query: str, types: list[NavType] | None = None) -> list[NavEntry]:
        """Search by exact ident (case-insensitive). Returns up to 10 results."""
        q = query.strip().upper()
        results: list[NavEntry] = []
        if types is None or "airport" in types:
            if q in self.airports:
                results.append(self.airports[q])
        if types is None or "fix" in types:
            results.extend(self.fixes.get(q, []))
        if types is None or "navaid" in types:
            results.extend(self.navaids.get(q, []))
        return results[:10]

    def search_ils(self, airport_icao: str) -> list[dict]:
        """Return ILS localizer entries for the given airport ICAO code."""
        icao = airport_icao.strip().upper()
        entries = self.ils.get(icao, [])
        return [
            {
                "ident": e.ident,
                "lat": e.lat,
                "lon": e.lon,
                "freq_mhz": e.freq_mhz,
                "course_deg": e.course_deg,
                "name": e.name,
                "runway": e.runway,
            }
            for e in entries
        ]


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    """Returns (distance_nm, bearing_deg_true) from point 1 to point 2."""
    R_NM = 3440.065
    lat1r, lon1r, lat2r, lon2r = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2r - lat1r
    dlon = lon2r - lon1r
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1r) * math.cos(lat2r) * math.sin(dlon / 2) ** 2
    distance = 2 * R_NM * math.asin(math.sqrt(a))
    y = math.sin(dlon) * math.cos(lat2r)
    x = math.cos(lat1r) * math.sin(lat2r) - math.sin(lat1r) * math.cos(lat2r) * math.cos(dlon)
    bearing = (math.degrees(math.atan2(y, x)) + 360) % 360
    return round(distance, 1), round(bearing, 1)


def bearing_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> dict:
    dist, brg = _haversine(lat1, lon1, lat2, lon2)
    return {"distance_nm": dist, "bearing_deg": brg}


def _load_aptmeta(path: Path) -> dict[str, NavEntry]:
    airports: dict[str, NavEntry] = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line[0] in ("I", "A") or line.startswith("1"):
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            try:
                icao = parts[0].strip()
                lat = float(parts[2])
                lon = float(parts[3])
                airports[icao] = NavEntry(ident=icao, lat=lat, lon=lon, type="airport")
            except (ValueError, IndexError):
                continue
    return airports


def _load_fixes(path: Path) -> dict[str, list[NavEntry]]:
    fixes: dict[str, list[NavEntry]] = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line[0] in ("I", "A") or line.startswith("1"):
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            try:
                lat = float(parts[0])
                lon = float(parts[1])
                ident = parts[2].strip()
                entry = NavEntry(ident=ident, lat=lat, lon=lon, type="fix")
                fixes.setdefault(ident, []).append(entry)
            except (ValueError, IndexError):
                continue
    return fixes


def _load_navaids(path: Path) -> dict[str, list[NavEntry]]:
    navaids: dict[str, list[NavEntry]] = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line[0] in ("I", "A") or line.startswith("1"):
                continue
            parts = line.split(None, 10)
            if len(parts) < 8:
                continue
            try:
                nav_type_code = int(parts[0])
                lat = float(parts[1])
                lon = float(parts[2])
                freq_raw = int(parts[4])
                freq_mhz = freq_raw / 100.0
                ident = parts[7].strip()
                name = parts[10].strip() if len(parts) > 10 else ""
                subtype = NAV_TYPE_NAMES.get(nav_type_code, str(nav_type_code))
                entry = NavEntry(
                    ident=ident, lat=lat, lon=lon, type="navaid",
                    name=name, freq_mhz=freq_mhz, nav_subtype=subtype,
                )
                navaids.setdefault(ident, []).append(entry)
            except (ValueError, IndexError):
                continue
    return navaids


def _load_ils(path: Path) -> dict[str, list[NavEntry]]:
    """Load type-4 ILS localizer entries from earth_nav.dat, keyed by airport ICAO."""
    ils: dict[str, list[NavEntry]] = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.split(None, 11)
            if not parts or parts[0] != "4":
                continue
            if len(parts) < 11:
                continue
            try:
                lat = float(parts[1])
                lon = float(parts[2])
                freq_mhz = int(parts[4]) / 100.0
                course_deg = round(float(parts[6]) % 360, 2)
                ident = parts[7].strip()
                airport_icao = parts[8].strip()
                # parts[10] is e.g. "34R ILS-cat-III" or "16L ILS-cat-I"
                remainder = parts[10].strip()
                rwy_parts = remainder.split(None, 1)
                runway = rwy_parts[0] if rwy_parts else ""
                ils_cat = rwy_parts[1] if len(rwy_parts) > 1 else ""
                name = f"{airport_icao} {runway} {ils_cat}".strip()
                entry = NavEntry(
                    ident=ident, lat=lat, lon=lon, type="navaid",
                    name=name, freq_mhz=freq_mhz, nav_subtype="ILS-LOC",
                    course_deg=course_deg, runway=runway,
                )
                ils.setdefault(airport_icao, []).append(entry)
            except (ValueError, IndexError):
                continue
    return ils


def load(xplane_path: str) -> NavDatabase:
    root = Path(xplane_path)
    default_data = root / "Resources" / "default data"
    aptmeta = default_data / "earth_aptmeta.dat"
    fix_path = default_data / "earth_fix.dat"
    nav_path = default_data / "earth_nav.dat"

    db = NavDatabase()
    if aptmeta.exists():
        db.airports = _load_aptmeta(aptmeta)
    if fix_path.exists():
        db.fixes = _load_fixes(fix_path)
    if nav_path.exists():
        db.navaids = _load_navaids(nav_path)
        db.ils = _load_ils(nav_path)
    return db
