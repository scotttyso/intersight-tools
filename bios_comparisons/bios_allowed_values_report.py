#!/usr/bin/env python3
"""Generate BIOS allowed-values report from template, Redfish registry, and schema.

Outputs:
- JSON report with one row per BIOS key in the template
- Markdown table report for quick review
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _extract_attributes_block(text: str, template_path: Path) -> str:
    text = template_path.read_text(encoding="utf-8")

    # Extract only inside the Attributes object.
    m = re.search(r'"Attributes"\s*:\s*\{', text)
    if not m:
        raise ValueError(f"Could not locate Attributes object in {template_path}")

    # Slice from start of Attributes object and track braces.
    start = m.end() - 1  # points to '{'
    i = start
    depth = 0
    end = None
    while i < len(text):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
        i += 1

    if end is None:
        raise ValueError(f"Could not find end of Attributes object in {template_path}")

    return text[start + 1 : end]


def extract_template_key_items(template_path: Path) -> List[Tuple[str, str]]:
    attrs_block = _extract_attributes_block(template_path.read_text(encoding="utf-8"), template_path)

    results: List[Tuple[str, str]] = []
    current_key = ""
    current_item = ""

    for line in attrs_block.splitlines():
        m_key = re.match(r'^\s*"([^"]+)"\s*:\s*$', line)
        if m_key:
            if current_key:
                results.append((current_key, current_item))
            current_key = m_key.group(1)
            current_item = ""
            continue

        if current_key and not current_item:
            m_item = re.search(r'item\.([a-zA-Z0-9_]+)', line)
            if m_item:
                current_item = m_item.group(1)

    if current_key:
        results.append((current_key, current_item))

    if not results:
        # fallback for legacy one-line template style:
        # "Key": "{{ item.some_schema_key | ... }}"
        for m in re.finditer(
            r'^\s*"([^"]+)"\s*:\s*"\{\{\s*item\.([a-zA-Z0-9_]+)',
            attrs_block,
            flags=re.MULTILINE,
        ):
            results.append((m.group(1), m.group(2)))

    return results


def load_redfish_registry(filtered_registry_path: Path) -> Dict[str, Dict[str, Any]]:
    data = json.loads(filtered_registry_path.read_text(encoding="utf-8"))

    registry = data.get("/redfish/v1/Registries/BiosAttributeRegistry", {})
    attrs = registry.get("RegistryEntries", {}).get("Attributes", [])
    by_name: Dict[str, Dict[str, Any]] = {}
    for item in attrs:
        if isinstance(item, dict) and item.get("AttributeName"):
            by_name[item["AttributeName"]] = item
    return by_name


def redfish_allowed_values(entry: Dict[str, Any]) -> List[str]:
    values = entry.get("Value")
    if isinstance(values, list) and values:
        out: List[str] = []
        for v in values:
            if not isinstance(v, dict):
                continue
            if v.get("ValueName") is not None:
                out.append(str(v["ValueName"]))
            elif v.get("ValueDisplayName") is not None:
                out.append(str(v["ValueDisplayName"]))
        if out:
            return out

    lower = entry.get("LowerBound")
    upper = entry.get("UpperBound")
    if lower is not None or upper is not None:
        return [f"range[{lower},{upper}]"]

    return []


def load_schema_bios_props(schema_path: Path) -> Dict[str, Dict[str, Any]]:
    data = json.loads(schema_path.read_text(encoding="utf-8"))
    bios_def = data.get("definitions", {}).get("intersight.policies.bios", {})
    props: Dict[str, Dict[str, Any]] = {}
    for item in bios_def.get("allOf", []):
        if isinstance(item, dict) and isinstance(item.get("properties"), dict):
            props.update(item["properties"])
    return props


def find_registry_path(user_path: Optional[str], repo_root: Path) -> Path:
    candidates = []
    if user_path:
        candidates.append(Path(user_path))
    candidates.append(repo_root / "QA/885/885/885_bios_registry_filtered.json")
    candidates.append(repo_root / "QA/885/885_bios_registry_filtered.json")

    for p in candidates:
        if p.exists():
            return p

    raise FileNotFoundError(
        "Could not find filtered registry JSON. Tried: "
        + ", ".join(str(p) for p in candidates)
    )


def to_markdown(rows: List[Dict[str, Any]]) -> str:
    lines = []
    lines.append("# BIOS Allowed Values Report")
    lines.append("")
    lines.append("| Key | Schema Property | Display Name | Default Value | Redfish Allowed Values | Schema Allowed Values |")
    lines.append("|---|---|---|---|---|---|")

    for r in rows:
        redfish_vals = ", ".join(r.get("redfish_allowed_values", [])) or ""
        schema_vals = ", ".join(r.get("schema_enum_values", [])) or ""
        lines.append(
            "| "
            + r.get("key", "")
            + " | "
            + r.get("schema_property", "")
            + " | "
            + r.get("display_name", "")
            + " | "
            + r.get("default_value", "")
            + " | "
            + redfish_vals.replace("|", "\\|")
            + " | "
            + schema_vals.replace("|", "\\|")
            + " |"
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate allowed-values mapping for BIOS template keys")
    parser.add_argument(
        "--template",
        default="classes/templates/intersight/C800/bios.json.j2",
        help="Path to bios template file",
    )
    parser.add_argument(
        "--registry",
        default="",
        help="Path to filtered BIOS registry JSON (optional; auto-detect if omitted)",
    )
    parser.add_argument(
        "--schema",
        default="schema/cisco-ai-pods.json",
        help="Path to cisco-ai-pods schema JSON",
    )
    parser.add_argument(
        "--out-json",
        default="bios_allowed_values_report.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--out-md",
        default="bios_allowed_values_report.md",
        help="Output Markdown path",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent
    template_path = (repo_root / args.template).resolve()
    schema_path = (repo_root / args.schema).resolve()
    registry_path = find_registry_path(args.registry if args.registry else None, repo_root)
    out_json = (repo_root / args.out_json).resolve()
    out_md = (repo_root / args.out_md).resolve()

    template_key_items = extract_template_key_items(template_path)
    registry_by_name = load_redfish_registry(registry_path)
    schema_props = load_schema_bios_props(schema_path)

    rows: List[Dict[str, Any]] = []
    for key, item_value in template_key_items:
        entry = registry_by_name.get(key)
        redfish_vals = redfish_allowed_values(entry) if entry else []

        schema_property = ""
        schema_intersight_api = ""
        schema_enum_vals: List[str] = []
        schema_match_type = ""
        if item_value and item_value in schema_props:
            schema_property = item_value
            prop = schema_props[item_value]
            schema_match_type = "template_item"
            schema_intersight_api = str(prop.get("intersight_api", ""))
            if isinstance(prop.get("enum"), list):
                schema_enum_vals = [str(v) for v in prop["enum"]]

        rows.append(
            {
                "key": key,
                "display_name": str(entry.get("DisplayName", "")) if entry else "",
                "default_value": str(entry.get("DefaultValue", "")) if entry else "",
                "redfish_type": str(entry.get("Type", "")) if entry else "",
                "redfish_help_text": str(entry.get("HelpText", "")) if entry else "",
                "redfish_allowed_values": redfish_vals,
                "schema_property": schema_property,
                "schema_intersight_api": schema_intersight_api,
                "schema_match_type": schema_match_type,
                "schema_enum_values": schema_enum_vals,
                "template_item_value": item_value,
            }
        )

    report = {
        "inputs": {
            "template": str(template_path),
            "registry": str(registry_path),
            "schema": str(schema_path),
        },
        "counts": {
            "template_keys": len(template_key_items),
            "registry_matches": sum(1 for r in rows if r["display_name"]),
            "schema_matches": sum(1 for r in rows if r["schema_property"]),
        },
        "rows": rows,
    }

    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    out_md.write_text(to_markdown(rows), encoding="utf-8")

    print(f"Template keys: {len(template_key_items)}")
    print(f"Registry matches: {report['counts']['registry_matches']}")
    print(f"Schema matches: {report['counts']['schema_matches']}")
    print(f"Wrote JSON: {out_json}")
    print(f"Wrote Markdown: {out_md}")


if __name__ == "__main__":
    main()
