"""Generate clearly labelled example sales data for local development.

This is simulated data, not evidence about actual Lays sales or discount lift.
Run: python generate_synthetic_sales.py
"""

from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


def generate(start: str = "2024-01-01", end: str | None = None, seed: int = 42) -> pd.DataFrame:
    if end is None:
        end = (datetime.now(ZoneInfo("Asia/Kolkata")).date() - timedelta(days=1)).isoformat()
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, end, freq="D")
    rows = []
    for i, date in enumerate(dates):
        # Regular, scheduled promotions make it possible to compare marked
        # discount periods with ordinary days in a demo dataset.
        discount_pct = 20 if (date.month in (3, 6, 9, 12) and 10 <= date.day <= 14) else 0
        weekday_factor = [0.92, 0.95, 1.00, 1.03, 1.12, 1.30, 1.20][date.dayofweek]
        annual_factor = 1 + 0.10 * np.sin(2 * np.pi * (date.dayofyear - 30) / 365.25)
        trend_factor = 1 + 0.00015 * i
        # This uplift is intentionally simulated and must not be treated as
        # an estimate of real customer response to a promotion.
        simulated_discount_factor = 1.28 if discount_pct else 1.0
        expected_units = 18 * weekday_factor * annual_factor * trend_factor * simulated_discount_factor
        units = int(rng.poisson(expected_units))
        regular_price = 20.0
        price = round(regular_price * (1 - discount_pct / 100), 2)
        rows.append({
            "date": date.date().isoformat(),
            "product": "Lays Cream & Onion",
            "units_sold": units,
            "discount_pct": discount_pct,
            "unit_price": price,
            "synthetic_data": True,
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    output = Path(__file__).with_name("synthetic_lays_cream_onion_sales.csv")
    data = generate()
    data.to_csv(output, index=False)
    print(f"Created {len(data):,} synthetic daily rows: {output}")
    print("SIMULATED ONLY: discount response and demand patterns are invented for software testing.")
