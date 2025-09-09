from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import pandas as pd

from .scats import discover_scats_resources, rank_resources, load_month
from .tii import fetch_tii_portal_metadata, load_tii_counts_export


app = typer.Typer(add_completion=False)


@app.command()
def scats_list(verbose: bool = False, timeout: float = 20.0, retries: int = 3) -> None:
    slugs = [
        "dcc-scats-detector-volume-jan-jun-2024",
        "dcc-scats-detector-volume-jul-dec-2024",
        "dcc-scats-detector-volume-jan-jun-2025",
    ]
    resources = discover_scats_resources(slugs, timeout=timeout, retries=retries)
    for r in resources:
        if verbose:
            typer.echo(f"{r.get('slug')} | {r.get('name')} | {r.get('created')} | {r.get('url')}")
        else:
            typer.echo(f"{r.get('slug')} | {r.get('url')}")


@app.command()
def scats_get(month: str, year: int, out: str = "data/raw") -> None:
    df = load_month(month, year, dest_dir=out)
    typer.echo(f"Loaded SCATS: shape={df.shape}")
    typer.echo(df.head().to_string(index=False))


@app.command()
def tii_list() -> None:
    meta = fetch_tii_portal_metadata()
    for title, href in meta.items():
        typer.echo(f"{title} | {href}")


@app.command()
def tii_load(export: str) -> None:
    df = load_tii_counts_export(export)
    typer.echo(f"Loaded TII export: shape={df.shape}")
    typer.echo(df.head().to_string(index=False))


def main() -> None:
    app()


if __name__ == "__main__":
    main()


