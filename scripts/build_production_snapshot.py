from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.main import SNAPSHOT_PATH, build_top_trades_payload  # noqa: E402


def main() -> int:
    payload = build_top_trades_payload(include_pass=True)

    if not isinstance(payload, dict):
        print("[SNAPSHOT] Unexpected payload type.")
        return 1

    if payload.get("error"):
        print("[SNAPSHOT] Failed to build live payload:")
        print(payload.get("error"))
        if payload.get("trace"):
            print(payload.get("trace"))
        return 1

    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SNAPSHOT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)

    size_bytes = SNAPSHOT_PATH.stat().st_size
    print(f"[SNAPSHOT] Wrote {SNAPSHOT_PATH}")
    print(f"[SNAPSHOT] Size: {size_bytes} bytes")
    print(f"[SNAPSHOT] Trades: {len(payload.get('trades', []))}")
    print(f"[SNAPSHOT] Sectors: {len(payload.get('sectorOutlook', []))}")
    print(f"[SNAPSHOT] Yesterday status items: {len(payload.get('yesterdayStatus', []))}")
    print(f"[SNAPSHOT] Source files: {payload.get('sourceFiles')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
