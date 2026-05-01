#!/usr/bin/env python3
"""Build a normalized ToLiss A321 dataref/command catalog from local sources.

Inputs are expected under:
  sources/TolissXKeyPadHelper
  sources/toliss-a430-datarefs

The script is intentionally offline and uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "toliss_a321_catalog.json"
DEFAULT_LOG = ROOT / "unmapped.log"
DEFAULT_SKIPPED_LOG = ROOT / "parse_skipped.log"
DEFAULT_COMPAT_LOG = ROOT / "compatibility_notes.log"

XKEYPAD_DIR = ROOT / "sources" / "TolissXKeyPadHelper"
A430_DIR = ROOT / "sources" / "toliss-a430-datarefs"

CATALOG_ORDER = [
    "name",
    "kind",
    "namespace",
    "category",
    "purpose",
    "writable",
    "data_type",
    "aircraft_compat",
    "sources",
]

AIRCRAFT_ORDER = ["A321", "A330", "A340"]

NAME_RE = re.compile(r"^[A-Za-z0-9_./-]+/[A-Za-z0-9_./-]+$")
LUA_STRING_RE = r'"((?:\\.|[^"\\])*)"|\'((?:\\.|[^\'\\])*)\''
LUA_CREATE_COMMAND_RE = re.compile(
    r"create_command\s*\(\s*" + LUA_STRING_RE + r"\s*,\s*" + LUA_STRING_RE,
    re.IGNORECASE,
)
LUA_CALL_RE = re.compile(
    r"(command_once|dataref_table|XPLMFindDataRef)\s*\(\s*" + LUA_STRING_RE,
    re.IGNORECASE,
)
LUA_ASSIGN_RE = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:dataref_table|XPLMFindDataRef)\s*\(\s*"
    + LUA_STRING_RE,
    re.IGNORECASE,
)


def lua_unquote(match: re.Match[str], start_index: int = 1) -> str:
    text = match.group(start_index) if match.group(start_index) is not None else match.group(start_index + 1)
    try:
        return ast.literal_eval('"' + text.replace('"', '\\"') + '"')
    except Exception:
        return text


def is_catalog_name(value: object) -> bool:
    if not isinstance(value, str):
        return False
    if not value or len(value) > 180:
        return False
    if value.endswith(".png") or value.endswith(".jpg"):
        return False
    return bool(NAME_RE.match(value))


def namespace_for(name: str) -> str:
    return name.split("/", 1)[0]


def classify_category(name: str) -> str:
    n = name.lower()
    checks = [
        ("MCDU", ["mcdu", "scratchpad", "lsk", "keyclr", "keyslash", "keydot"]),
        ("EFIS", ["efis", "/nd", "nd1", "nd2", "pfd", "wxradar", "wxswitch", "baro"]),
        ("FCU", ["fcu", "hdgtrk", "ias_mach", "spd_pull", "spd_push", "vs_push", "loc_push", "apprbutton"]),
        ("AP", ["autopilot", "athr", "ap1", "ap2", "ap_disc", "fd1", "fd2", "fma"]),
        ("Engine", ["engine", "/eng", "eng1", "eng2", "eng3", "eng4", "throttle", "thrust", "n1", "n2"]),
        ("Hyd", ["hyd", "ratrelease"]),
        ("Fuel", ["fuel", "pump", "xfeed"]),
        ("Lights", ["light", "beacon", "strobe", "landing", "dome", "annun", "sign", "flood"]),
        ("AntiIce", ["antiice", "aiswitch", "wingai", "probeheat"]),
        ("Pneumatic", ["bleed", "pack", "apu", "pressur", "pneum", "aircond", "cabvs"]),
        ("Electrical", ["elec", "bat", "extpow", "generator", "/gen", "acess"]),
        ("ECAM", ["ecam", "/ecp/", "selectenginepage", "selecthydraulicpage", "selectfuelpage"]),
    ]
    for category, needles in checks:
        if any(needle in n for needle in needles):
            return category
    return "Misc"


def looks_a330_a340_only(name: str) -> bool:
    n = name.lower()
    patterns = [
        r"eng(?:ine)?[34](?:\b|_|/|[a-z])",
        r"eng(?:ine)?(?:_|/)?[34](?:\b|_|/|[a-z])",
        r"(?:^|/)engine[34](?:\b|_|/|[a-z])",
        r"(?:^|/)eng[34](?:\b|_|/|[a-z])",
        r"firetesteng[34]",
    ]
    return any(re.search(pattern, n) for pattern in patterns)


def normalize_purpose(text: object) -> str | None:
    if not isinstance(text, str):
        return None
    clean = " ".join(text.split())
    return clean or None


class CatalogBuilder:
    def __init__(self) -> None:
        self.entries: dict[str, dict[str, object]] = {}
        self.unmapped: list[str] = []
        self.skipped: list[str] = []
        self.compat_notes: list[str] = []

    def add(
        self,
        *,
        name: str,
        kind: str,
        source: str,
        aircraft: list[str],
        purpose: str | None = None,
        writable: bool | None = None,
        data_type: str | None = None,
    ) -> None:
        if not is_catalog_name(name):
            self.unmapped.append(f"{source}: invalid {kind} name: {name!r}")
            return
        entry = self.entries.get(name)
        if entry is None:
            entry = {
                "name": name,
                "kind": kind,
                "namespace": namespace_for(name),
                "category": classify_category(name),
                "purpose": None,
                "writable": None,
                "data_type": None,
                "aircraft_compat": [],
                "sources": [],
            }
            self.entries[name] = entry
        elif entry["kind"] != kind:
            self.unmapped.append(
                f"{source}: kind conflict, existing {entry['kind']} vs {kind}: {name}"
            )
            return

        if purpose and entry["purpose"] is None:
            entry["purpose"] = purpose
        if writable is not None and entry["kind"] == "dataref":
            entry["writable"] = bool(writable)
        if data_type is not None and entry["data_type"] is None:
            entry["data_type"] = data_type

        compat = set(entry["aircraft_compat"])
        compat.update(aircraft)
        entry["aircraft_compat"] = [a for a in AIRCRAFT_ORDER if a in compat]

        sources = entry["sources"]
        if source not in sources:
            sources.append(source)

    def sorted_entries(self) -> list[dict[str, object]]:
        result = []
        for entry in sorted(self.entries.values(), key=lambda item: (item["kind"], item["name"])):
            ordered = {key: entry[key] for key in CATALOG_ORDER}
            ordered["sources"] = sorted(ordered["sources"])
            result.append(ordered)
        return result


def rel_source(path: Path, line: int) -> str:
    try:
        rel = path.relative_to(ROOT / "sources")
    except ValueError:
        rel = path.relative_to(ROOT)
    return f"{rel.as_posix()}:{line}"


def trim_for_log(raw: str, limit: int = 220) -> str:
    text = raw.rstrip("\n\r")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def add_skipped(builder: CatalogBuilder, path: Path, line_no: int, raw: str, reason: str) -> None:
    builder.skipped.append(f"{rel_source(path, line_no)}: {reason}: {trim_for_log(raw)}")


def compat_for_source(name: str, source_family: str, builder: CatalogBuilder, source: str) -> list[str]:
    if source_family == "xkeypad":
        return ["A321"]
    if looks_a330_a340_only(name):
        builder.compat_notes.append(f"{source}: A330/A340-only heuristic, A321 excluded: {name}")
        return ["A330", "A340"]
    return ["A321", "A330", "A340"]


def parse_spad_file(builder: CatalogBuilder, path: Path, kind: str) -> None:
    if not path.exists():
        builder.unmapped.append(f"{path}: missing input file")
        return
    for line_no, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        line = raw.strip()
        if not line:
            add_skipped(builder, path, line_no, raw, "blank")
            continue
        if line.startswith("#"):
            add_skipped(builder, path, line_no, raw, "comment")
            continue
        source = rel_source(path, line_no)
        if not is_catalog_name(line):
            builder.unmapped.append(f"{source}: parse failure: {raw}")
            add_skipped(builder, path, line_no, raw, "parse failure")
            continue
        compat = compat_for_source(line, "a430", builder, source)
        builder.add(name=line, kind=kind, source=source, aircraft=compat)


def strip_lua_comment(line: str) -> tuple[str, str | None]:
    if "--" not in line:
        return line, None
    code, comment = line.split("--", 1)
    return code, normalize_purpose(comment)


def parse_lua(builder: CatalogBuilder, path: Path) -> None:
    if not path.exists():
        builder.unmapped.append(f"{path}: missing input file")
        return
    variable_to_dataref: dict[str, str] = {}
    writable_names: set[str] = set()
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    for line_no, raw in enumerate(lines, 1):
        code, comment = strip_lua_comment(raw)
        source = rel_source(path, line_no)
        accepted = False

        assign = LUA_ASSIGN_RE.search(code)
        if assign:
            var = assign.group(1)
            name = lua_unquote(assign, 2)
            if is_catalog_name(name):
                variable_to_dataref[var] = name

        for var in re.findall(r"\bXPLMSetData[fi]\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)", code):
            if var in variable_to_dataref:
                writable_names.add(variable_to_dataref[var])
        for var in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\[[^\]]+\]\s*=", code):
            if var in variable_to_dataref:
                writable_names.add(variable_to_dataref[var])

        create = LUA_CREATE_COMMAND_RE.search(code)
        if create:
            name = lua_unquote(create, 1)
            purpose = normalize_purpose(lua_unquote(create, 3))
            builder.add(
                name=name,
                kind="command",
                source=source,
                aircraft=["A321"],
                purpose=purpose,
            )
            accepted = True
            continue

        call = LUA_CALL_RE.search(code)
        if call:
            function_name = call.group(1)
            name = lua_unquote(call, 2)
            if "command_once" in function_name:
                builder.add(
                    name=name,
                    kind="command",
                    source=source,
                    aircraft=["A321"],
                    purpose=comment,
                )
            else:
                builder.add(
                    name=name,
                    kind="dataref",
                    source=source,
                    aircraft=["A321"],
                    purpose=comment,
                )
            accepted = True

        if not accepted:
            reason = "blank" if not raw.strip() else "comment" if not code.strip() and comment else "no catalog entry"
            add_skipped(builder, path, line_no, raw, reason)

    for name in writable_names:
        entry = builder.entries.get(name)
        if entry and entry["kind"] == "dataref":
            entry["writable"] = True


def collect_json_line_index(path: Path) -> dict[str, int]:
    index: dict[str, int] = {}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line_no, line in enumerate(lines, 1):
        for value in re.findall(r'"(?:Name|Dataref Name)"\s*:\s*"([^"]+)"', line):
            if is_catalog_name(value):
                index.setdefault(value, line_no)
    return index


def collect_text_labels(node: object) -> list[str]:
    labels: list[str] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"Text", "Comment", "Comments", "Static Speech"}:
                    label = normalize_purpose(child)
                    if label and label not in labels:
                        labels.append(label)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(node)
    return labels


def purpose_from_labels(labels: list[str]) -> str | None:
    filtered = [label for label in labels if label and not is_catalog_name(label)]
    if not filtered:
        return None
    return " ".join(filtered[:6])


def iter_xkeypad_keys(node: object):
    if isinstance(node, dict):
        if "Default Command Set" in node or "Logic Dataref" in node or "Numeric Dataref" in node:
            yield node
        for child in node.values():
            yield from iter_xkeypad_keys(child)
    elif isinstance(node, list):
        for child in node:
            yield from iter_xkeypad_keys(child)


def extract_command_names_from_set(command_set: object) -> list[str]:
    names: list[str] = []
    if not isinstance(command_set, dict):
        return names
    commands = command_set.get("Commands")
    if isinstance(commands, dict):
        for command in commands.values():
            if isinstance(command, dict) and is_catalog_name(command.get("Name")):
                names.append(command["Name"])
    return names


def extract_dataref_names(node: object) -> list[str]:
    names: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "Dataref Name" and is_catalog_name(value):
                names.append(value)
            else:
                names.extend(extract_dataref_names(value))
    elif isinstance(node, list):
        for child in node:
            names.extend(extract_dataref_names(child))
    return names


def parse_xkeypad_json(builder: CatalogBuilder, path: Path) -> None:
    if not path.exists():
        builder.unmapped.append(f"{path}: missing input file")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        builder.unmapped.append(f"{path}:{exc.lineno}: JSON parse failure: {exc.msg}")
        return

    line_index = collect_json_line_index(path)
    seen: set[tuple[str, str]] = set()
    accepted_lines: set[int] = set()
    for key_config in iter_xkeypad_keys(data):
        labels = collect_text_labels(key_config)
        purpose = purpose_from_labels(labels)

        for command_set_name in ("Default Command Set", "True Command Set", "False Command Set"):
            for name in extract_command_names_from_set(key_config.get(command_set_name)):
                marker = ("command", name)
                if marker in seen:
                    continue
                seen.add(marker)
                line = line_index.get(name, 1)
                accepted_lines.add(line)
                builder.add(
                    name=name,
                    kind="command",
                    source=rel_source(path, line),
                    aircraft=["A321"],
                    purpose=purpose,
                )

        for name in extract_dataref_names(key_config):
            marker = ("dataref", name)
            if marker in seen:
                continue
            seen.add(marker)
            line = line_index.get(name, 1)
            accepted_lines.add(line)
            builder.add(
                name=name,
                kind="dataref",
                source=rel_source(path, line),
                aircraft=["A321"],
                purpose=purpose,
            )

    for line_no, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if line_no in accepted_lines:
            continue
        stripped = raw.strip()
        reason = "blank" if not stripped else "no catalog entry"
        add_skipped(builder, path, line_no, raw, reason)


def write_outputs(
    builder: CatalogBuilder,
    output: Path,
    log_path: Path,
    skipped_log_path: Path,
    compat_log_path: Path,
) -> list[dict[str, object]]:
    entries = builder.sorted_entries()
    output.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log_lines = sorted(dict.fromkeys(builder.unmapped))
    log_path.write_text("\n".join(log_lines) + ("\n" if log_lines else ""), encoding="utf-8")
    skipped_lines = list(dict.fromkeys(builder.skipped))
    skipped_log_path.write_text(
        "\n".join(skipped_lines) + ("\n" if skipped_lines else ""),
        encoding="utf-8",
    )
    compat_lines = sorted(dict.fromkeys(builder.compat_notes))
    compat_log_path.write_text(
        "\n".join(compat_lines) + ("\n" if compat_lines else ""),
        encoding="utf-8",
    )
    return entries


def print_summary(entries: list[dict[str, object]]) -> None:
    def show_counter(title: str, counter: Counter[str]) -> None:
        print(f"{title}:")
        for key, count in sorted(counter.items(), key=lambda item: (-item[1], item[0])):
            print(f"  {key}: {count}")

    print(f"total entries: {len(entries)}")
    show_counter("kind", Counter(entry["kind"] for entry in entries))
    show_counter("namespace", Counter(entry["namespace"] for entry in entries))
    show_counter("category", Counter(entry["category"] for entry in entries))
    compat_counter: Counter[str] = Counter()
    for entry in entries:
        compat_counter["+".join(entry["aircraft_compat"])] += 1
    show_counter("aircraft_compat", compat_counter)


def build(
    output: Path,
    log_path: Path,
    skipped_log_path: Path,
    compat_log_path: Path,
) -> list[dict[str, object]]:
    builder = CatalogBuilder()
    parse_lua(builder, XKEYPAD_DIR / "TolissCustom.lua")
    for json_path in sorted(XKEYPAD_DIR.glob("X-Keys_a321*.json")):
        parse_xkeypad_json(builder, json_path)
    parse_spad_file(builder, A430_DIR / "datarefs.txt", "dataref")
    parse_spad_file(builder, A430_DIR / "commands.txt", "command")
    return write_outputs(builder, output, log_path, skipped_log_path, compat_log_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--skipped-log", type=Path, default=DEFAULT_SKIPPED_LOG)
    parser.add_argument("--compat-log", type=Path, default=DEFAULT_COMPAT_LOG)
    args = parser.parse_args()

    entries = build(args.output, args.log, args.skipped_log, args.compat_log)
    print_summary(entries)
    print(f"wrote: {args.output}")
    print(f"wrote: {args.log}")
    print(f"wrote: {args.skipped_log}")
    print(f"wrote: {args.compat_log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
