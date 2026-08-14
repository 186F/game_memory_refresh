#!/usr/bin/env python3
"""Read-only extractor for Kingdom Come: Deliverance II .whs saves."""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


STEAM_APP_ID = "1771300"
PRINTABLE_RE = re.compile(rb"[\x20-\x7e]{4,}")
XML_TOKEN_RE = re.compile(
    rb"</?[A-Za-z_][A-Za-z0-9_.:-]*(?:\s+[^<>]*?)?/?>", re.DOTALL
)
STATE_WORDS = {
    "active", "available", "blocked", "completed", "disabled", "done",
    "enabled", "failed", "finished", "inactive", "started", "success",
    "unavailable", "unstreamed", "streamed",
}


class SaveFormatError(RuntimeError):
    pass


@dataclass
class UnpackedSave:
    header_text: str
    header: dict[str, str]
    payload: bytes
    chunks: list[dict[str, int | str | None]]
    footer_size: int


def _u32(data: bytes, offset: int) -> int:
    if offset + 4 > len(data):
        raise SaveFormatError(f"truncated uint32 at offset 0x{offset:x}")
    return struct.unpack_from("<I", data, offset)[0]


def _parse_chunks(
    data: bytes, start: int, end: int
) -> tuple[bytes, list[dict[str, int | str | None]]]:
    offset = start
    pieces: list[bytes] = []
    chunks: list[dict[str, int | str | None]] = []
    index = 0
    while offset < end:
        chunk_offset = offset
        if end - offset < 8:
            raise SaveFormatError(f"truncated chunk header at offset 0x{offset:x}")
        compressed_size = _u32(data, offset)
        uncompressed_size = _u32(data, offset + 4)
        offset += 8
        if compressed_size == 0xFFFFFFFF:
            # Newer saves can interleave stored (uncompressed) chunks with zlib
            # chunks. The marker replaces compressed_size; uncompressed_size is
            # both the stored byte count and the decoded byte count.
            encoding = "stored"
            stored_size = uncompressed_size
            if stored_size <= 0 or offset + stored_size > end:
                raise SaveFormatError(
                    f"invalid stored size {stored_size} at offset 0x{chunk_offset:x}"
                )
            decoded = data[offset : offset + stored_size]
        else:
            encoding = "zlib"
            stored_size = compressed_size
            if compressed_size <= 0 or offset + compressed_size > end:
                raise SaveFormatError(
                    f"invalid compressed size {compressed_size} at offset 0x{chunk_offset:x}"
                )
            compressed = data[offset : offset + compressed_size]
            try:
                decoded = zlib.decompress(compressed)
            except zlib.error as exc:
                raise SaveFormatError(f"zlib failure at offset 0x{offset:x}: {exc}") from exc
        if len(decoded) != uncompressed_size:
            raise SaveFormatError(
                f"chunk {index} at 0x{chunk_offset:x}: expected {uncompressed_size} "
                f"uncompressed bytes, got {len(decoded)}"
            )
        pieces.append(decoded)
        chunks.append(
            {
                "index": index,
                "file_offset": chunk_offset,
                "encoding": encoding,
                "size_marker": compressed_size,
                "stored_size": stored_size,
                "compressed_size": compressed_size if encoding == "zlib" else None,
                "uncompressed_size": uncompressed_size,
            }
        )
        offset += stored_size
        index += 1
    if offset != end:
        raise SaveFormatError(f"chunk stream ended at 0x{offset:x}, expected 0x{end:x}")
    return b"".join(pieces), chunks


def unpack_save(path: Path) -> UnpackedSave:
    data = path.read_bytes()
    if len(data) < 12:
        raise SaveFormatError("file is too short to be a WHS save")
    if _u32(data, 0) != 0xFFFFFFFF:
        raise SaveFormatError("missing 0xffffffff WHS marker at offset 0")
    header_size = _u32(data, 4)
    header_end = 8 + header_size
    if header_size <= 0 or header_end > len(data):
        raise SaveFormatError(f"invalid XML header length {header_size}")
    header_text = data[8:header_end].rstrip(b"\0").decode("utf-8", "strict")
    try:
        header_root = ET.fromstring(header_text)
    except ET.ParseError as exc:
        raise SaveFormatError(f"invalid XML header: {exc}") from exc

    errors: list[str] = []
    for footer_size in (64, 0):
        stream_end = len(data) - footer_size
        if stream_end <= header_end:
            continue
        try:
            payload, chunks = _parse_chunks(data, header_end, stream_end)
            return UnpackedSave(
                header_text=header_text,
                header=dict(header_root.attrib),
                payload=payload,
                chunks=chunks,
                footer_size=footer_size,
            )
        except SaveFormatError as exc:
            errors.append(f"footer={footer_size}: {exc}")
    raise SaveFormatError("could not validate chunk stream; " + "; ".join(errors))


def extract_strings(payload: bytes) -> list[str]:
    return [m.group().decode("ascii", "replace") for m in PRINTABLE_RE.finditer(payload)]


def reconstruct_concept_state(payload: bytes) -> tuple[str, ET.Element]:
    tokens = [m.group() for m in XML_TOKEN_RE.finditer(payload)]
    start = next((i for i, token in enumerate(tokens) if token == b"<Roots>"), None)
    if start is None:
        raise SaveFormatError("ConceptState <Roots> token was not found in payload")
    depth = 0
    selected: list[bytes] = []
    for token in tokens[start:]:
        selected.append(token)
        if token.startswith(b"</"):
            depth -= 1
        elif not token.endswith(b"/>"):
            depth += 1
        if depth == 0:
            break
    if not selected or selected[-1] != b"</Roots>":
        raise SaveFormatError("ConceptState token stream did not close </Roots>")
    xml_text = b"".join(selected).decode("utf-8", "replace")
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise SaveFormatError(f"reconstructed ConceptState XML is invalid: {exc}") from exc
    return xml_text, root


def find_game_dir(explicit: str | None) -> Path | None:
    if explicit:
        candidate = Path(explicit).expanduser()
        return candidate.resolve() if candidate.is_dir() else None
    if sys.platform == "win32":
        try:
            import winreg

            keys = (
                rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {STEAM_APP_ID}",
                rf"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {STEAM_APP_ID}",
            )
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                for key_name in keys:
                    try:
                        with winreg.OpenKey(hive, key_name) as key:
                            value, _ = winreg.QueryValueEx(key, "InstallLocation")
                        candidate = Path(value)
                        if candidate.is_dir():
                            return candidate.resolve()
                    except OSError:
                        pass
        except ImportError:
            pass
    return None


def find_localization_pack(game_dir: Path, language: str) -> Path | None:
    loc_dir = game_dir / "Localization"
    exact = loc_dir / f"{language}_xml.pak"
    if exact.is_file():
        return exact
    wanted = language.casefold()
    for candidate in loc_dir.glob("*_xml.pak"):
        if candidate.stem.casefold().startswith(wanted):
            return candidate
    return None


def load_localization(game_dir: Path, language: str = "English") -> dict[str, str]:
    pack = find_localization_pack(game_dir, language)
    if pack is None:
        return {}
    result: dict[str, str] = {}
    with zipfile.ZipFile(pack) as archive:
        for name in archive.namelist():
            if not name.lower().endswith(".xml"):
                continue
            try:
                root = ET.fromstring(archive.read(name))
            except (ET.ParseError, KeyError):
                continue
            for row in root.iter():
                cells = [cell.text or "" for cell in list(row) if cell.tag.lower().endswith("cell")]
                if len(cells) >= 2 and cells[0]:
                    result.setdefault(cells[0].casefold(), cells[1])
    return result


def header_quest_key(header: dict[str, str]) -> str | None:
    for part in header.get("UIDescription", "").split("|"):
        if part.startswith("@qname_"):
            return part[1:]
    return None


def internal_quest_name(key: str | None) -> str | None:
    if not key or not key.casefold().startswith("qname_"):
        return None
    name = key[len("qname_") :]
    name = re.sub(r"_[A-Za-z0-9]{4}$", "", name)
    return "_" + name


def _label(element: ET.Element) -> str:
    return (
        element.attrib.get("Name")
        or element.attrib.get("name")
        or element.attrib.get("Id")
        or element.tag
    )


def _walk(element: ET.Element, path: tuple[str, ...] = ()) -> Iterable[tuple[ET.Element, tuple[str, ...]]]:
    label = _label(element)
    next_path = path if label.casefold() in {"roots", "nodes", "children", "items"} else path + (label,)
    yield element, next_path
    for child in element:
        yield from _walk(child, next_path)


def find_named_element(root: ET.Element, wanted: str | None) -> tuple[ET.Element | None, tuple[str, ...]]:
    if not wanted:
        return None, ()
    matches = [
        (element, path)
        for element, path in _walk(root)
        if _label(element).casefold() == wanted.casefold()
    ]
    if not matches:
        return None, ()
    return max(matches, key=lambda item: sum(1 for _ in item[0].iter()))


def collect_evidence(root: ET.Element) -> dict[str, list[dict[str, Any]]]:
    states: list[dict[str, Any]] = []
    objective_updates: list[dict[str, Any]] = []
    used_sequences: list[dict[str, Any]] = []
    for element, path in _walk(root):
        attrs = dict(element.attrib)
        lowered = {key.casefold(): value for key, value in attrs.items()}
        for key, value in attrs.items():
            if value.casefold() in STATE_WORDS and key.casefold() in {
                "state", "status", "value", "phase", "result"
            }:
                states.append({"path": "/".join(path), "field": key, "value": value})
        update_key = next(
            (key for key in attrs if key.casefold() in {"updatetime", "update_time"}), None
        )
        if update_key:
            objective_updates.append(
                {"path": "/".join(path), "update_time": attrs[update_key], "attributes": attrs}
            )
        used_key = next(
            (key for key in attrs if key.casefold() in {"lastusedtime", "last_used_time"}), None
        )
        if used_key:
            used_sequences.append(
                {"path": "/".join(path), "last_used_time": attrs[used_key], "attributes": attrs}
            )
        # Some builds store the time in a child value next to a semantic node name.
        if "updatetime" in lowered and not update_key:
            objective_updates.append(
                {"path": "/".join(path), "update_time": lowered["updatetime"], "attributes": attrs}
            )
    return {
        "states": states,
        "objective_updates": objective_updates,
        "used_sequences": used_sequences,
    }


def _time_key(record: dict[str, Any]) -> tuple[int, Any]:
    raw = str(record.get("update_time") or record.get("last_used_time") or "")
    try:
        return 1, float(raw)
    except ValueError:
        return 0, raw


def _json_dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare_output(path: Path, force: bool) -> None:
    known = {
        "metadata.json", "safe_summary.json", "evidence.json", "strings.tsv",
        "concept_state.xml", "payload.bin",
    }
    if path.exists() and not path.is_dir():
        raise SaveFormatError(f"output path is not a directory: {path}")
    if path.is_dir() and any((path / name).exists() for name in known) and not force:
        raise SaveFormatError(
            f"analysis output already exists in {path}; choose a new directory or pass --force"
        )
    path.mkdir(parents=True, exist_ok=True)


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    save_path = Path(args.save).expanduser().resolve()
    if not save_path.is_file():
        raise SaveFormatError(f"save file not found: {save_path}")
    output = Path(args.output).expanduser().resolve()
    if output == save_path.parent:
        raise SaveFormatError("use a dedicated analysis directory, not the save directory")
    prepare_output(output, args.force)

    unpacked = unpack_save(save_path)
    strings = extract_strings(unpacked.payload)
    concept_xml, concept_root = reconstruct_concept_state(unpacked.payload)
    quest_key = header_quest_key(unpacked.header)
    internal_name = internal_quest_name(quest_key)
    quest_element, quest_path = find_named_element(concept_root, internal_name)
    current_evidence = collect_evidence(quest_element) if quest_element is not None else {
        "states": [], "objective_updates": [], "used_sequences": []
    }
    all_evidence = collect_evidence(concept_root)

    game_dir = find_game_dir(args.game_dir)
    localization = load_localization(game_dir, args.language) if game_dir else {}
    title = localization.get(quest_key.casefold(), "") if quest_key else ""
    description_key = quest_key.replace("qname_", "qdesc_", 1) if quest_key else None
    description = localization.get(description_key.casefold(), "") if description_key else ""
    latest = (
        max(current_evidence["objective_updates"], key=_time_key)
        if current_evidence["objective_updates"] else None
    )

    warnings: list[str] = []
    if game_dir is None:
        warnings.append("Game installation was not found; localization keys remain partially unresolved.")
    elif not localization:
        warnings.append(f"No {args.language} localization pack could be read from {game_dir}.")
    if quest_element is None:
        warnings.append(f"Current quest root {internal_name!r} was not found in ConceptState.")
    if not current_evidence["objective_updates"]:
        warnings.append("No timestamped objective update was recovered beneath the current quest root.")

    metadata = {
        "source": str(save_path),
        "source_size": save_path.stat().st_size,
        "header": unpacked.header,
        "header_xml": unpacked.header_text,
        "chunk_count": len(unpacked.chunks),
        "chunk_encodings": {
            "zlib": sum(chunk["encoding"] == "zlib" for chunk in unpacked.chunks),
            "stored": sum(chunk["encoding"] == "stored" for chunk in unpacked.chunks),
        },
        "chunks": unpacked.chunks,
        "uncompressed_payload_size": len(unpacked.payload),
        "footer_size": unpacked.footer_size,
        "game_dir": str(game_dir) if game_dir else None,
        "language": args.language,
    }
    safe_summary = {
        "current_checkpoint": {
            "quest_key": quest_key,
            "quest_title": title or None,
            "quest_description": description or None,
            "internal_quest_root": internal_name,
            "concept_path": "/".join(quest_path) if quest_path else None,
            "map": unpacked.header.get("LevelName"),
            "save_type": unpacked.header.get("SaveType"),
            "build": unpacked.header.get("BuildInfo"),
            "latest_objective_update": latest,
        },
        "evidence_counts": {
            key: len(value) for key, value in current_evidence.items()
        },
        "warnings": warnings,
        "source_was_modified": False,
    }
    evidence = {
        "current_quest": current_evidence,
        "all_timestamped_objective_updates": all_evidence["objective_updates"],
        "all_used_sequences": all_evidence["used_sequences"],
        "interpretation_warning": (
            "ConceptState contains dormant and future state. Only narrate records after "
            "localization/script mapping and chronology verification."
        ),
    }

    _json_dump(output / "metadata.json", metadata)
    _json_dump(output / "safe_summary.json", safe_summary)
    _json_dump(output / "evidence.json", evidence)
    (output / "concept_state.xml").write_text(concept_xml + "\n", encoding="utf-8")
    with (output / "strings.tsv").open("w", encoding="utf-8", newline="") as handle:
        handle.write("index\tvalue\n")
        for index, value in enumerate(strings):
            handle.write(f"{index}\t{value.replace(chr(9), ' ')}\n")
    if args.include_payload:
        (output / "payload.bin").write_bytes(unpacked.payload)
    return safe_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract a KCD2 WHS save into spoiler-aware analysis artifacts without modifying it."
    )
    parser.add_argument("save", help="Path to the .whs save")
    parser.add_argument("--output", required=True, help="Dedicated output directory")
    parser.add_argument("--game-dir", help="KCD2 installation directory")
    parser.add_argument("--language", default="English", help="Localization language (default: English)")
    parser.add_argument("--include-payload", action="store_true", help="Also write decompressed payload.bin")
    parser.add_argument("--force", action="store_true", help="Overwrite known artifacts in the output directory")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = analyze(args)
    except (OSError, SaveFormatError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
