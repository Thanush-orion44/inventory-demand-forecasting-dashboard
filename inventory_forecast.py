"""Single-product daily demand forecast and inventory planner.

Input CSV needs a date and units-sold column. Optional discount columns are
not used to train a discount effect: use --discount-uplift-pct to explore a
clearly labelled assumption until real promotion data is available.

Example:
    python inventory_forecast.py sales.csv --date-column date \
        --sales-column quantity --product "Lays Cream & Onion" \
        --stock 120 --lead-time-days 5 --discount-uplift-pct 20
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor


LAGS = (1, 2, 3, 7, 14, 28)


def load_daily_sales(path: Path, date_column: str, sales_column: str,
                     product_column: str | None, product: str | None) -> pd.Series:
    df = pd.read_csv(path)
    missing = [c for c in (date_column, sales_column) if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required column(s) {missing}. Available: {list(df.columns)}")
    if product_column:
        if product_column not in df.columns:
            raise ValueError(f"Product column {product_column!r} not found")
        if product is None:
            values = df[product_column].dropna().astype(str).unique()
            if len(values) != 1:
                raise ValueError("This tool forecasts one product. Pass --product to select it.")
            product = values[0]
        df = df[df[product_column].astype(str) == product]
        if df.empty:
            raise ValueError(f"No rows found for product {product!r}")
    df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
    df[sales_column] = pd.to_numeric(df[sales_column], errors="coerce")
    df = df.dropna(subset=[date_column, sales_column])
    if df.empty:
        raise ValueError("No valid date and sales rows remain after cleaning")
    if (df[sales_column] < 0).any():
        raise ValueError("Sales/units must be non-negative")
    daily = df.groupby(df[date_column].dt.normalize())[sales_column].sum().sort_index()
    # Missing dates become zero sales, the standard interpretation for a daily
    # sales ledger. If missing dates mean missing collection, clean the source first.
    daily = daily.asfreq("D", fill_value=0).astype(float)
    return daily


def features(series: pd.Series, position: int, date: pd.Timestamp | None = None) -> list[float]:
    date = date if date is not None else series.index[position]
    values = [float(series.iloc[position - lag]) for lag in LAGS]
    values += [float(series.iloc[max(0, position - 7):position].mean()),
               float(series.iloc[max(0, position - 28):position].mean())]
    values += [float(date.dayofweek), float(date.day), float(date.month),
               float(date.dayofyear), float(date.dayofweek >= 5)]
    return values


def forecast(daily: pd.Series, horizon: int) -> tuple[pd.Series, str]:
    if horizon < 1:
        raise ValueError("Forecast horizon must be positive")
    future_dates = pd.date_range(daily.index[-1] + pd.Timedelta(days=1), periods=horizon, freq="D")
    if len(daily) < 35:
        # A weekday seasonal baseline is more stable than fitting a model to
        # very little history.
        weekday_means = daily.groupby(daily.index.dayofweek).mean()
        preds = [max(0.0, float(weekday_means.get(day.dayofweek, daily.mean()))) for day in future_dates]
        return pd.Series(preds, index=future_dates), "weekday average (short-history fallback)"

    x, y = [], []
    for i in range(28, len(daily)):
        x.append(features(daily, i))
        y.append(float(daily.iloc[i]))
    model = RandomForestRegressor(n_estimators=250, min_samples_leaf=2,
                                  max_features=0.9, random_state=42, n_jobs=1)
    model.fit(np.asarray(x), np.asarray(y))
    extended = daily.copy()
    preds = []
    for day in future_dates:
        row = features(extended, len(extended), day)
        pred = max(0.0, float(model.predict([row])[0]))
        preds.append(pred)
        extended.loc[day] = pred
    return pd.Series(preds, index=future_dates), "random forest with recursive lag features"


def inventory_status(stock: int | None, lead_time: int, forecast_daily: pd.Series,
                     safety_days: int) -> dict[str, Any] | None:
    if stock is None:
        return None
    daily_rate = float(forecast_daily.mean()) if len(forecast_daily) else 0.0
    lead_demand = float(forecast_daily.head(lead_time).sum())
    safety_stock = daily_rate * safety_days
    reorder_point = lead_demand + safety_stock
    gap = max(0.0, reorder_point - stock)
    if stock < lead_demand:
        status = "UNDERSTOCKED: current stock is below forecast lead-time demand"
    elif stock < reorder_point:
        status = "REORDER: stock covers lead time but is below the safety-stock target"
    else:
        status = "OK: stock covers lead time and the safety-stock target"
    return {"on_hand_units": stock, "lead_time_days": lead_time,
            "forecast_demand_during_lead_time": round(lead_demand, 1),
            "safety_stock_units": round(safety_stock, 1),
            "reorder_point_units": int(np.ceil(reorder_point)),
            "suggested_order_units_to_reach_reorder_point": int(np.ceil(gap)),
            "status": status}


def build_report(daily: pd.Series, product: str, stock: int | None,
                 lead_time_days: int, safety_days: int,
                 discount_uplift_pct: float, forecast_days: int = 35
                 ) -> tuple[dict[str, Any], pd.DataFrame]:
    """Build JSON-safe dashboard summary and daily rows from cleaned sales."""
    if daily.empty:
        raise ValueError("No sales data available to forecast")
    if forecast_days < 1 or lead_time_days < 1 or safety_days < 0:
        raise ValueError("Forecast and lead time must be positive; safety days cannot be negative")
    if discount_uplift_pct < 0:
        raise ValueError("Discount uplift cannot be negative")
    next_month = (daily.index[-1] + pd.offsets.MonthBegin(1)).to_period("M")
    days_through_next_month = (next_month.end_time.normalize() - daily.index[-1]).days
    horizon = max(forecast_days, 7, days_through_next_month)
    base, method = forecast(daily, horizon)
    discount = base * (1 + discount_uplift_pct / 100.0)
    result = pd.DataFrame({"date": base.index, "baseline_units": base.values,
                           "discount_scenario_units": discount.values})
    result["month"] = result["date"].dt.to_period("M").astype(str)
    monthly = result[result["date"].dt.to_period("M") == next_month]
    summary = {
        "product": product,
        "history_start": daily.index[0].date().isoformat(),
        "history_end": daily.index[-1].date().isoformat(),
        "history_days": int(len(daily)), "forecast_method": method,
        "next_7_days_baseline_units": round(float(base.head(7).sum()), 1),
        "next_7_days_discount_scenario_units": round(float(discount.head(7).sum()), 1),
        "next_calendar_month": str(next_month),
        "next_calendar_month_baseline_units": round(float(monthly["baseline_units"].sum()), 1),
        "next_calendar_month_discount_scenario_units": round(float(monthly["discount_scenario_units"].sum()), 1),
        "discount_uplift_assumption_pct": discount_uplift_pct,
        "discount_note": "Scenario assumption only; no historical promotion data was used to learn uplift.",
        "inventory": inventory_status(stock, lead_time_days, base, safety_days),
    }
    rows = result.copy()
    rows["date"] = rows["date"].dt.strftime("%Y-%m-%d")
    return summary, rows


def run(args: argparse.Namespace) -> dict[str, Any]:
    daily = load_daily_sales(args.csv, args.date_column, args.sales_column,
                             args.product_column, args.product)
    summary, result = build_report(daily, args.product or "single product", args.stock,
                                   args.lead_time_days, args.safety_days,
                                   args.discount_uplift_pct, args.forecast_days)
    result.to_csv(args.output, index=False)
    summary["forecast_csv"] = str(args.output)
    summary_path = args.output.with_name(args.output.stem + "_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"\nDaily forecast saved to {args.output}")
    print(f"Summary saved to {summary_path}")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="Daily sales CSV")
    parser.add_argument("--date-column", default="date")
    parser.add_argument("--sales-column", default="sales")
    parser.add_argument("--product-column", default=None)
    parser.add_argument("--product", default=None, help="One product identifier/name")
    parser.add_argument("--forecast-days", type=int, default=35,
                        help="Daily output horizon; at least 35 days are generated for monthly totals")
    parser.add_argument("--stock", type=int, default=None, help="Current warehouse/store stock units")
    parser.add_argument("--lead-time-days", type=int, default=7)
    parser.add_argument("--safety-days", type=int, default=3)
    parser.add_argument("--discount-uplift-pct", type=float, default=0,
                        help="Assumed demand uplift for a discount scenario; not learned from data")
    parser.add_argument("--output", type=Path, default=Path("demand_forecast_output.csv"))
    args = parser.parse_args()
    if args.forecast_days < 1 or args.lead_time_days < 1 or args.safety_days < 0:
        parser.error("forecast and lead-time days must be positive; safety days cannot be negative")
    if args.stock is not None and args.stock < 0:
        parser.error("stock cannot be negative")
    if args.discount_uplift_pct < 0:
        parser.error("discount uplift cannot be negative")
    if args.product and not args.product_column:
        parser.error("--product requires --product-column")
    return args


if __name__ == "__main__":
    run(parse_args())
