from __future__ import annotations

import sys

from app.security import hash_passcode


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python -m tools.hash_passcode \"plainpass\"")
        raise SystemExit(1)

    print(hash_passcode(sys.argv[1]))


if __name__ == "__main__":
    main()
