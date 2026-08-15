from __future__ import annotations

import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from analyze_whs import SaveFormatError, unpack_save  # noqa: E402


HEADER_XML = (
    b'<C_SaveGameDescription SaveType="ManualSave" LevelName="test" '
    b'UIDescription="0|0|@qname_test_AbCd|" />\0'
)
FOOTER = b"fixture-footer-data!" + bytes(44)


def whs_prefix() -> bytes:
    return struct.pack("<II", 0xFFFFFFFF, len(HEADER_XML)) + HEADER_XML


def zlib_chunk(payload: bytes) -> bytes:
    compressed = zlib.compress(payload)
    return struct.pack("<II", len(compressed), len(payload)) + compressed


def stored_chunk(payload: bytes) -> bytes:
    return struct.pack("<II", 0xFFFFFFFF, len(payload)) + payload


class UnpackSaveTests(unittest.TestCase):
    def write_save(self, data: bytes, directory: str) -> Path:
        path = Path(directory) / "fixture.whs"
        path.write_bytes(data)
        return path

    def test_legacy_zlib_stream(self) -> None:
        first = b"legacy payload" * 250
        second = b"second chunk"
        data = whs_prefix() + zlib_chunk(first) + zlib_chunk(second) + FOOTER

        with tempfile.TemporaryDirectory() as directory:
            unpacked = unpack_save(self.write_save(data, directory))

        self.assertEqual(unpacked.payload, first + second)
        self.assertEqual(unpacked.footer_size, 64)
        self.assertEqual([chunk["encoding"] for chunk in unpacked.chunks], ["zlib", "zlib"])

    def test_mixed_zlib_and_stored_stream(self) -> None:
        compressed_payload = bytes(range(256)) * 128
        stored_payload = b"raw-chunk-boundary" * 1820
        final_payload = b"tail"
        data = (
            whs_prefix()
            + zlib_chunk(compressed_payload)
            + stored_chunk(stored_payload)
            + zlib_chunk(final_payload)
            + FOOTER
        )

        with tempfile.TemporaryDirectory() as directory:
            unpacked = unpack_save(self.write_save(data, directory))

        self.assertEqual(unpacked.payload, compressed_payload + stored_payload + final_payload)
        self.assertEqual(
            [chunk["encoding"] for chunk in unpacked.chunks],
            ["zlib", "stored", "zlib"],
        )
        raw_chunk = unpacked.chunks[1]
        self.assertEqual(raw_chunk["size_marker"], 0xFFFFFFFF)
        self.assertEqual(raw_chunk["stored_size"], len(stored_payload))
        self.assertIsNone(raw_chunk["compressed_size"])

    def test_invalid_stored_chunk_boundary_is_rejected(self) -> None:
        declared_size = 4096
        data = (
            whs_prefix()
            + struct.pack("<II", 0xFFFFFFFF, declared_size)
            + b"too short"
            + FOOTER
        )

        with tempfile.TemporaryDirectory() as directory:
            path = self.write_save(data, directory)
            with self.assertRaisesRegex(SaveFormatError, "invalid stored size 4096"):
                unpack_save(path)


if __name__ == "__main__":
    unittest.main()
