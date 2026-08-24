"""Pinned SPSValidator adapter; stdout is one canonical JSON document."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from spsvalidator.domain.validation import validate_sps_zip


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    arguments = parser.parse_args()
    package_path = arguments.package.resolve(strict=True)
    if not package_path.is_file() or package_path.stat().st_size > 500 * 1024 * 1024:
        raise ValueError("package must be a regular ZIP file up to 500 MiB")
    payload = package_path.read_bytes()
    result = validate_sps_zip(str(package_path))
    output = {
        "adapter_contract": "1.0.0",
        "candidate_sha256": hashlib.sha256(payload).hexdigest(),
        "spsvalidator_version": "0.3.0+d1aa774d4e33",
        "result": result,
    }
    print(
        json.dumps(
            output,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
