from __future__ import annotations

import os
import sys

# Ensure project root is in sys.path when running as a script
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core import health_api


def main() -> None:
    report = health_api.get_runtime_sanity_report()
    print(report)


if __name__ == "__main__":
    main()
