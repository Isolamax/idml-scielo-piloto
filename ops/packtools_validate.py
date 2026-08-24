"""Isolated Packtools 4.16.11 adapter; stdout is one canonical JSON document."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import packtools
from packtools.stylechecker import get_xmlvalidator, summarize


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("xml", type=Path)
    arguments = parser.parse_args()
    xml_path = arguments.xml.resolve(strict=True)
    if not xml_path.is_file() or xml_path.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("XML input must be a regular file up to 100 MiB")
    payload = xml_path.read_bytes()
    validator = get_xmlvalidator(str(xml_path), True, [])
    result = summarize(validator, assets_basedir=str(xml_path.parent))
    output = {
        "adapter_contract": "1.0.0",
        "candidate_sha256": hashlib.sha256(payload).hexdigest(),
        "packtools_version": getattr(packtools, "__version__", "4.16.11"),
        "result": result,
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

