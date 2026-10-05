#!/usr/bin/env python3
import csv
import io
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://www.mizuhobank.co.jp/retail/takarakuji/loto/loto7/csv/A103{round:04d}.CSV"
OUT = Path("app/src/main/assets/loto7.csv")


def normalize_date(value: str) -> str:
    value = value.strip()
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", value)
    if not m:
        raise ValueError(f"Unknown date: {value!r}")
    y, mo, d = map(int, m.groups())
    return f"{y:04d}-{mo:02d}-{d:02d}"


def fetch_round(round_no: int):
    req = urllib.request.Request(
        BASE.format(round=round_no),
        headers={"User-Agent": "Mozilla/5.0 Loto7AiPredictor/1.0"},
    )
    with urllib.request.urlopen(req, timeout=20) as res:
        raw = res.read()
    text = raw.decode("shift_jis", errors="replace")
    fields = [x.strip() for x in text.replace("\r", "").replace("\n", ",").split(",")]
    if len(fields) < 18:
        raise ValueError(f"Unexpected CSV for round {round_no}")
    date = normalize_date(fields[3])
    nums = [int(x) for x in fields[8:15]]
    if len(nums) != 7 or len(set(nums)) != 7 or not all(1 <= n <= 37 for n in nums):
        raise ValueError(f"Invalid numbers for round {round_no}: {nums}")
    return [round_no, date, *nums]


def main():
    rows = []
    misses = 0
    for round_no in range(1, 1001):
        try:
            rows.append(fetch_round(round_no))
            misses = 0
            print(f"Fetched Loto7 round {round_no}")
            time.sleep(0.03)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as e:
            print(f"Stop candidate at round {round_no}: {e}")
            misses += 1
            if misses >= 2:
                break
    if len(rows) < 600:
        raise RuntimeError(f"Only {len(rows)} rounds fetched; refusing to build incomplete bundled data")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["round", "date", "n1", "n2", "n3", "n4", "n5", "n6", "n7"])
        w.writerows(rows)
    print(f"Bundled {len(rows)} Loto7 draws into {OUT}")


if __name__ == "__main__":
    main()
