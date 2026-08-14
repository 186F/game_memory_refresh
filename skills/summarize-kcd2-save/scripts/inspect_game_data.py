#!/usr/bin/env python3
"""Narrow, read-only lookups in installed KCD2 localization and quest scripts."""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

from analyze_whs import find_game_dir, load_localization


def scripts_pack(game_dir: Path) -> Path:
    candidate = game_dir / "Data" / "Scripts.pak"
    if not candidate.is_file():
        raise FileNotFoundError(f"Scripts.pak not found at {candidate}")
    return candidate


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1].casefold()


def _resolve(value: str | None, localization: dict[str, str]) -> dict[str, str] | None:
    if not value:
        return None
    source = value.strip()
    lookup = source[1:] if source.startswith("@") else source
    resolved = localization.get(lookup.casefold())
    return {"source": source, "english": resolved or source}


def _resolve_node(element: ET.Element, localization: dict[str, str]) -> dict[str, str] | None:
    key = (
        element.attrib.get("StringName")
        or element.attrib.get("stringName")
        or element.attrib.get("LocalizationKey")
    )
    source = (
        element.attrib.get("Text")
        or element.attrib.get("text")
        or element.attrib.get("Value")
        or element.text
        or key
    )
    if not source:
        return None
    result = {"source": source, "english": localization.get((key or "").casefold(), source)}
    if key:
        result["key"] = key
    return result


def _emit(value: Any) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _matching_xml_names(archive: zipfile.ZipFile, path_hint: str | None) -> list[str]:
    names = [name for name in archive.namelist() if name.lower().endswith(".xml")]
    if not path_hint:
        return names
    fragments = [part.casefold() for part in re.split(r"[\\/]+", path_hint) if part]
    return [name for name in names if all(part in name.casefold() for part in fragments)]


def cmd_localize(args: argparse.Namespace, game_dir: Path) -> int:
    localization = load_localization(game_dir, args.language)
    key = args.key[1:] if args.key.startswith("@") else args.key
    value = localization.get(key.casefold())
    _emit({"key": key, "text": value, "found": value is not None})
    return 0 if value is not None else 1


def cmd_list_scripts(args: argparse.Namespace, game_dir: Path) -> int:
    fragment = args.fragment.casefold()
    with zipfile.ZipFile(scripts_pack(game_dir)) as archive:
        matches = [
            name for name in archive.namelist()
            if fragment in name.casefold() and name.lower().endswith(".xml")
        ][: args.limit]
    _emit({"fragment": args.fragment, "matches": matches, "truncated": len(matches) >= args.limit})
    return 0 if matches else 1


def _direct_sequence_text(
    sequence: ET.Element, localization: dict[str, str]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    prompts: list[dict[str, str]] = []
    responses: list[dict[str, str]] = []
    for child in list(sequence):
        if _tag(child) == "uiprompt":
            resolved = _resolve_node(child, localization)
            if resolved:
                prompts.append(resolved)
        if _tag(child) != "elements":
            continue
        for response in list(child):
            if _tag(response) not in {"response", "element"}:
                continue
            for text_node in list(response):
                if _tag(text_node) != "text":
                    continue
                resolved = _resolve_node(text_node, localization)
                if resolved:
                    responses.append(resolved)
    return prompts, responses


def cmd_sequence(args: argparse.Namespace, game_dir: Path) -> int:
    localization = load_localization(game_dir, args.language)
    found: list[dict[str, Any]] = []
    with zipfile.ZipFile(scripts_pack(game_dir)) as archive:
        for name in _matching_xml_names(archive, args.path_hint):
            try:
                root = ET.fromstring(archive.read(name))
            except (ET.ParseError, KeyError):
                continue
            for element in root.iter():
                sequence_name = element.attrib.get("Name") or element.attrib.get("name")
                if _tag(element) != "sequence" or not sequence_name:
                    continue
                if sequence_name.casefold() != args.sequence_name.casefold():
                    continue
                prompts, responses = _direct_sequence_text(element, localization)
                found.append(
                    {
                        "archive_path": name,
                        "sequence": sequence_name,
                        "attributes": dict(element.attrib),
                        "direct_ui_prompts": prompts,
                        "direct_response_text": responses,
                    }
                )
                if len(found) >= args.limit:
                    break
            if len(found) >= args.limit:
                break
    _emit({"query": args.sequence_name, "path_hint": args.path_hint, "matches": found})
    return 0 if found else 1


def cmd_search_content(args: argparse.Namespace, game_dir: Path) -> int:
    needle = args.text.casefold()
    results: list[dict[str, Any]] = []
    with zipfile.ZipFile(scripts_pack(game_dir)) as archive:
        for name in _matching_xml_names(archive, args.path_hint):
            try:
                text = archive.read(name).decode("utf-8", "replace")
            except KeyError:
                continue
            for line_number, line in enumerate(text.splitlines(), 1):
                if needle in line.casefold():
                    results.append(
                        {"archive_path": name, "line": line_number, "text": line.strip()[:1000]}
                    )
                    if len(results) >= args.limit:
                        break
            if len(results) >= args.limit:
                break
    _emit({"query": args.text, "path_hint": args.path_hint, "matches": results})
    return 0 if results else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect installed KCD2 localization and Scripts.pak.")
    parser.add_argument("--game-dir", help="KCD2 installation directory; otherwise discover Steam App 1771300")
    parser.add_argument("--language", default="English", help="Localization language (default: English)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    localize = subparsers.add_parser("localize", help="Resolve one exact localization key")
    localize.add_argument("key")

    listing = subparsers.add_parser("list-scripts", help="List quest XML paths containing a fragment")
    listing.add_argument("fragment")
    listing.add_argument("--limit", type=int, default=50)

    sequence = subparsers.add_parser("sequence", help="Inspect one exact saved sequence name")
    sequence.add_argument("sequence_name")
    sequence.add_argument("--path-hint", required=True, help="Quest archive path fragment(s)")
    sequence.add_argument("--limit", type=int, default=20)

    search = subparsers.add_parser("search-content", help="Search quest XML content narrowly")
    search.add_argument("text")
    search.add_argument("--path-hint", help="Quest archive path fragment(s)")
    search.add_argument("--limit", type=int, default=50)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    game_dir = find_game_dir(args.game_dir)
    if game_dir is None:
        print("error: KCD2 installation not found; pass --game-dir", file=sys.stderr)
        return 2
    try:
        if args.command == "localize":
            return cmd_localize(args, game_dir)
        if args.command == "list-scripts":
            return cmd_list_scripts(args, game_dir)
        if args.command == "sequence":
            return cmd_sequence(args, game_dir)
        if args.command == "search-content":
            return cmd_search_content(args, game_dir)
    except (OSError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
