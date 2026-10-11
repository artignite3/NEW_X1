"""Check local Markdown file and image targets without opening external URLs."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {"node_modules", ".next", "out", "env", "__pycache__", ".git"}
LINK = re.compile(r"!?\[[^\]]*\]\((?:<([^>]+)>|([^\s)]+))(?:\s+[^)]*)?\)")


def problems(paths: list[Path]) -> list[str]:
    missing = []
    for doc in paths:
        lines = doc.read_text(encoding="utf-8").splitlines()
        fenced = False
        for number, line in enumerate(lines, 1):
            if re.match(r"^\s*(```|~~~)", line):
                fenced = not fenced
                continue
            if fenced:
                continue
            for match in LINK.finditer(line):
                raw = (match.group(1) or match.group(2)).strip()
                parsed = urlsplit(raw)
                if parsed.scheme or parsed.netloc or raw.startswith(("#", "/", "mailto:")):
                    continue
                target = (doc.parent / unquote(parsed.path)).resolve()
                if not target.exists():
                    missing.append(f"{doc.relative_to(ROOT)}:{number}: {raw}")
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-archive", action="store_true", help="also check dated archival documents")
    args = parser.parse_args()
    paths = sorted(p for p in ROOT.rglob("*.md") if not SKIP_DIRS.intersection(p.relative_to(ROOT).parts)
                   and (args.include_archive or "archive" not in p.relative_to(ROOT).parts))
    missing = problems(paths)
    for item in missing:
        print(item)
    print(f"Checked {len(paths)} Markdown files; {len(missing)} missing local targets")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
