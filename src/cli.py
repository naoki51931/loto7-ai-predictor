from __future__ import annotations

import argparse

from .predictor import backtest, load_data, predict, recent_window


def main() -> None:
    parser = argparse.ArgumentParser(description="LOTO7 short-term predictor")
    parser.add_argument("--data", required=True, help="CSV path")
    parser.add_argument("--target-date", help="Target draw date, e.g. 2026-10-23")
    parser.add_argument("--backtest", type=int, help="Run N random historical backtests")
    args = parser.parse_args()

    df = load_data(args.data)

    if args.target_date:
        window = recent_window(df, args.target_date, days=14)
        prediction = predict(window)
        print(f"Target: {args.target_date}")
        print(f"Input window: {len(window)} draws / 14 days")
        print("Prediction:", " ".join(f"{n:02d}" for n in prediction.numbers))

    if args.backtest:
        result = backtest(df, samples=args.backtest)
        if result.empty:
            print("Not enough historical data for backtesting.")
            return
        print(result.to_string(index=False))
        print(f"\nAverage matches: {result['matches'].mean():.3f}")
        for k in range(8):
            print(f"{k} matches: {(result['matches'] == k).sum()}")


if __name__ == "__main__":
    main()
