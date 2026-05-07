"""
Build the production dashboard snapshot from the local-good environment.

What this does
--------------
- Calls the same API payload builder used by the dashboard for:
  - default mode (`/top-trades`)
  - extended mode (`/top-trades?include_extended=true`)
- Packages both payloads into a single snapshot artifact.
- Writes:
  - `backend/data/production_snapshot.json`
  - `backend/production_snapshot_payload.py`

Why this exists
---------------
Production does not have the same local data environment as localhost.
Rather than partially rebuilding dashboard sections on Render, we ship a
complete snapshot that already contains the exact payloads the frontend needs.

CMD-friendly usage
------------------
From the repo root:

  C:\\Users\\umarm\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe post_processing\\build_production_snapshot.py

Optional pretty JSON:

  C:\\Users\\umarm\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe post_processing\\build_production_snapshot.py --indent 2
"""

from __future__ import annotations

import argparse
import json
import pprint
from urllib.parse import urlencode
from urllib.request import urlopen
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

SNAPSHOT_JSON_PATH = ROOT_DIR / "backend" / "data" / "production_snapshot.json"
SNAPSHOT_PY_PATH = ROOT_DIR / "backend" / "production_snapshot_payload.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the production dashboard snapshot.")
    parser.add_argument("--indent", type=int, default=2, help="JSON indent for the snapshot file.")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8011",
        help="Base URL for the local API used to capture the production snapshot.",
    )
    return parser.parse_args()


def fetch_payload(base_url: str, include_extended: bool) -> dict:
    query = urlencode({"include_extended": str(include_extended).lower()}) if include_extended else ""
    url = f"{base_url.rstrip('/')}/top-trades"
    if query:
        url = f"{url}?{query}"

    with urlopen(url) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    args = parse_args()

    default_payload = fetch_payload(args.base_url, include_extended=False)
    extended_payload = fetch_payload(args.base_url, include_extended=True)

    snapshot_bundle = {
        "snapshotVersion": 2,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "signalDate": default_payload.get("signalDate") if isinstance(default_payload, dict) else None,
        "defaultPayload": default_payload,
        "extendedPayload": extended_payload,
    }

    SNAPSHOT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_JSON_PATH.write_text(
        json.dumps(snapshot_bundle, indent=args.indent, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    SNAPSHOT_PY_PATH.write_text(
        "SNAPSHOT_PAYLOAD = " + pprint.pformat(snapshot_bundle, width=120, sort_dicts=False) + "\n",
        encoding="utf-8",
    )

    default_count = len((default_payload or {}).get("trades", [])) if isinstance(default_payload, dict) else 0
    extended_count = len((extended_payload or {}).get("trades", [])) if isinstance(extended_payload, dict) else 0

    print(f"Built production snapshot v2 for signal date: {snapshot_bundle['signalDate']}")
    print(f"Default trades: {default_count}")
    print(f"Extended trades: {extended_count}")
    print(f"Saved JSON: {SNAPSHOT_JSON_PATH}")
    print(f"Saved Python payload: {SNAPSHOT_PY_PATH}")


if __name__ == "__main__":
    main()
