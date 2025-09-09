from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

import pandas as pd


def resample_hourly(df: pd.DataFrame, ts_col: str = "timestamp", group_cols: Iterable[str] | None = None, how: str = "sum") -> pd.DataFrame:
    """Resample to hourly per group.

    how in {"sum","mean"}.
    """
    if group_cols is None:
        group_cols = ["site_id"]
    df2 = df.copy()
    df2[ts_col] = pd.to_datetime(df2[ts_col], utc=True, errors="coerce")
    df2 = df2.dropna(subset=[ts_col])
    agg = {c: how for c in df2.columns if c not in set(group_cols) | {ts_col}}
    out = (
        df2.set_index(ts_col)
        .groupby(list(group_cols))
        .resample("1H")
        .agg(agg)
        .reset_index()
        .sort_values(list(group_cols) + [ts_col])
    )
    return out


def clip_negatives(df: pd.DataFrame, cols: Iterable[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = out[c].clip(lower=0)
    return out


def drop_sparse(df: pd.DataFrame, min_points: int = 24, key_col: str = "site_id", ts_col: str = "timestamp") -> pd.DataFrame:
    counts = df.groupby(key_col)[ts_col].count()
    keep = set(counts[counts >= min_points].index)
    return df[df[key_col].isin(keep)].copy()


def merge_sites_with_graph(df: pd.DataFrame, site_to_node: Dict[int, int]) -> pd.DataFrame:
    out = df.copy()
    out["node_id"] = out["site_id"].map(site_to_node)
    return out


def to_flow_series(df: pd.DataFrame, key_col: str, ts_col: str, val_col: str) -> Dict[int, List[Tuple[pd.Timestamp, float]]]:
    series: Dict[int, List[Tuple[pd.Timestamp, float]]] = {}
    for key, g in df[[key_col, ts_col, val_col]].dropna().groupby(key_col):
        pairs = [(pd.to_datetime(t), float(v)) for t, v in zip(g[ts_col], g[val_col])]
        series[int(key)] = sorted(pairs, key=lambda x: x[0])
    return series


