from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

NUMBERS = tuple(range(1, 38))
NUMBER_COLUMNS = [f"n{i}" for i in range(1, 8)]


@dataclass
class Prediction:
    numbers: list[int]
    scores: dict[int, float]
    window_rows: int


def load_data(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"date", *NUMBER_COLUMNS}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    for col in NUMBER_COLUMNS:
        df[col] = df[col].astype(int)
    return df


def recent_window(df: pd.DataFrame, target_date: str | pd.Timestamp, days: int = 14) -> pd.DataFrame:
    target = pd.Timestamp(target_date)
    start = target - pd.Timedelta(days=days)
    # Strictly exclude the target day's result: only information known before the draw is allowed.
    return df[(df["date"] >= start) & (df["date"] < target)].copy()


def occurrence_counts(window: pd.DataFrame) -> np.ndarray:
    counts = np.zeros(38, dtype=float)
    for col in NUMBER_COLUMNS:
        for n in window[col].to_numpy(dtype=int):
            counts[n] += 1
    return counts


def gap_scores(window: pd.DataFrame) -> np.ndarray:
    scores = np.zeros(38, dtype=float)
    if window.empty:
        return scores
    for n in NUMBERS:
        rows = np.where(window[NUMBER_COLUMNS].eq(n).any(axis=1).to_numpy())[0]
        scores[n] = 1.0 / (1.0 + (len(window) - 1 - rows[-1])) if len(rows) else 0.0
    return scores


def pair_scores(window: pd.DataFrame) -> dict[tuple[int, int], float]:
    counts: dict[tuple[int, int], int] = {}
    for row in window[NUMBER_COLUMNS].itertuples(index=False, name=None):
        for pair in combinations(sorted(row), 2):
            counts[pair] = counts.get(pair, 0) + 1
    total = max(len(window), 1)
    return {pair: count / total for pair, count in counts.items()}


def build_number_scores(window: pd.DataFrame) -> np.ndarray:
    """Score numbers using only the recent window; no date is used as a model feature."""
    freq = occurrence_counts(window)
    gap = gap_scores(window)
    if freq.max() > 0:
        freq = freq / freq.max()
    return 0.75 * freq + 0.25 * gap


def predict(window: pd.DataFrame, n_candidates: int = 20000, seed: int = 42) -> Prediction:
    if window.empty:
        raise ValueError("No lottery results exist in the 14-day window.")

    rng = np.random.default_rng(seed)
    scores = build_number_scores(window)
    pairs = pair_scores(window)

    # Generate many valid combinations and rank them using only recent-window statistics.
    candidates = np.empty((n_candidates, 7), dtype=np.int16)
    candidate_scores = np.empty(n_candidates, dtype=float)
    weights = scores[1:] + 1e-6
    weights = weights / weights.sum()

    for i in range(n_candidates):
        choice = np.sort(rng.choice(np.arange(1, 38), size=7, replace=False, p=weights))
        candidates[i] = choice
        base = scores[choice].sum()
        pair_bonus = sum(pairs.get(pair, 0.0) for pair in combinations(choice, 2))
        candidate_scores[i] = base + 0.75 * pair_bonus

    best = int(np.argmax(candidate_scores))
    chosen = candidates[best].tolist()
    return Prediction(numbers=chosen, scores={int(n): float(scores[n]) for n in NUMBERS}, window_rows=len(window))


def score_prediction(predicted: Iterable[int], actual: Iterable[int]) -> int:
    return len(set(predicted) & set(actual))


def backtest(df: pd.DataFrame, samples: int = 100, seed: int = 42) -> pd.DataFrame:
    """Walk through randomly selected historical draws without leaking their results."""
    if len(df) < 2:
        return pd.DataFrame()

    rng = np.random.default_rng(seed)
    eligible = [i for i in range(len(df)) if not recent_window(df, df.loc[i, "date"]).empty]
    if not eligible:
        return pd.DataFrame()
    indices = rng.choice(eligible, size=min(samples, len(eligible)), replace=False)

    rows = []
    for idx in indices:
        target_date = df.loc[idx, "date"]
        window = recent_window(df.iloc[:idx + 1], target_date)
        prediction = predict(window, seed=seed + int(idx))
        actual = df.loc[idx, NUMBER_COLUMNS].tolist()
        rows.append({
            "target_date": target_date.date().isoformat(),
            "predicted": " ".join(f"{n:02d}" for n in prediction.numbers),
            "actual": " ".join(f"{n:02d}" for n in sorted(actual)),
            "matches": score_prediction(prediction.numbers, actual),
            "window_rows": prediction.window_rows,
        })
    return pd.DataFrame(rows).sort_values("target_date").reset_index(drop=True)
