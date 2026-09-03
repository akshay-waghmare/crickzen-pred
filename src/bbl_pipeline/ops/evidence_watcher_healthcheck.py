"""Container healthcheck for the evidence watcher.

Warnings are actionable evidence gaps but not watcher-process failures. The
container should become unhealthy only when the audit is critical or the
report is unreadable/missing.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


def main() -> int:
    report_path = Path("/app/data/model_reviews/evidence_watcher.json")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 1

    return 0 if report.get("status") in {"healthy", "warning"} else 1


if __name__ == "__main__":
    sys.exit(main())
