from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from .data_fetch import download_scats_zip


MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def iter_years(start: int, end: int) -> Iterable[int]:
    step = 1 if end >= start else -1
    for y in range(start, end + step, step):
        yield y


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download all available SCATS monthly ZIPs for a year range.")
    parser.add_argument("--start-year", type=int, default=2020,
                        help="First year to attempt (inclusive), default 2020")
    parser.add_argument("--end-year", type=int, default=2025,
                        help="Last year to attempt (inclusive), default 2025")
    parser.add_argument("--out", type=Path, default=Path("data/raw/scats"),
                        help="Base output directory, default data/raw/scats")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip download if a file for that month already exists")
    args = parser.parse_args()

    base_out: Path = args.out
    base_out.mkdir(parents=True, exist_ok=True)

    total_ok = 0
    total_err = 0

    for year in iter_years(args.start_year, args.end_year):
        year_dir = base_out / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        for month in MONTHS:
            try:
                # Expected default filename pattern from URL; if unknown, rely on returned path
                # We let download_scats_zip decide the best candidate and name
                if args.skip_existing:
                    # quick heuristic filename that often matches resource name
                    expected = [
                        year_dir / f"scats{month.lower()}{year}.zip",
                        year_dir / f"{month.lower()}_{year}.zip",
                    ]
                    if any(p.exists() for p in expected):
                        print(f"[skip] {month} {year} (exists)")
                        continue

                out_path = download_scats_zip(month, year, dest_dir=year_dir)
                # Ensure the file was saved under the target year dir and has the stable name pattern
                if out_path.parent != year_dir:
                    # Move into the year directory with stable name
                    target = year_dir / f"scats_{year}_{month.strip().lower()}.zip"
                    out_path.replace(target)
                    out_path = target
                print(f"[ok]   {month} {year} -> {out_path}")
                total_ok += 1
            except Exception as e:
                print(f"[err]  {month} {year}: {e}")
                total_err += 1

    print(f"Done. Success: {total_ok}, Errors: {total_err}")


if __name__ == "__main__":
    main()


