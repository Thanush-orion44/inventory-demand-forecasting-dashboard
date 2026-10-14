"""Generate clearly labelled example sales data for local development.

This is simulated data, not evidence about actual Lays sales or discount lift.
Run: python generate_synthetic_sales.py
"""

from pathlib import Path
from datetime import datetime, timedelta
import re
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

PRODUCTS = [
    {"id": "SNK-001", "name": "Lays Cream & Onion", "base": 18, "weekend": 1.30, "season": 0.10, "phase": 30, "trend": 0.00015, "discount": 20, "months": (3, 6, 9, 12), "lift": 1.28, "price": 20.0},
    {"id": "BEV-001", "name": "Coca-Cola 500ml", "base": 29, "weekend": 1.38, "season": 0.18, "phase": 170, "trend": 0.00010, "discount": 15, "months": (2, 5, 8, 11), "lift": 1.22, "price": 40.0},
    {"id": "INS-001", "name": "Maggi Masala Noodles 70g", "base": 24, "weekend": 1.08, "season": 0.07, "phase": 240, "trend": 0.00012, "discount": 10, "months": (1, 4, 7, 10), "lift": 1.16, "price": 14.0},
    {"id": "CHO-001", "name": "Dairy Milk 40g", "base": 16, "weekend": 1.42, "season": 0.22, "phase": 330, "trend": 0.00008, "discount": 25, "months": (2, 5, 8, 11), "lift": 1.35, "price": 45.0},
    {"id": "BIS-001", "name": "Parle-G Biscuits", "base": 35, "weekend": 0.94, "season": 0.05, "phase": 80, "trend": 0.00005, "discount": 10, "months": (3, 6, 9, 12), "lift": 1.12, "price": 10.0},
    {"id": "SNK-002", "name": "Kurkure Masala Munch", "base": 21, "weekend": 1.24, "season": 0.13, "phase": 115, "trend": 0.00018, "discount": 20, "months": (1, 4, 7, 10), "lift": 1.25, "price": 20.0},
]


def _end_date(end: str | None) -> str:
    if end is None:
        end = (datetime.now(ZoneInfo("Asia/Kolkata")).date() - timedelta(days=1)).isoformat()
    return end


def generate(start: str = "2024-01-01", end: str | None = None, seed: int = 42,
             product: str = "Lays Cream & Onion") -> pd.DataFrame:
    """Generate daily synthetic sales for one product from the product catalog."""
    spec = next((item for item in PRODUCTS if item["name"] == product), None)
    if spec is None:
        raise ValueError(f"Unknown product {product!r}. Choose one of: {[p['name'] for p in PRODUCTS]}")
    end = _end_date(end)
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start, end, freq="D")
    rows = []
    for i, date in enumerate(dates):
        # Regular, scheduled promotions make it possible to compare marked
        # discount periods with ordinary days in a demo dataset.
        discount_pct = spec["discount"] if (date.month in spec["months"] and 10 <= date.day <= 14) else 0
        weekday_factor = [0.92, 0.95, 1.00, 1.03, 1.12, spec["weekend"], (spec["weekend"] + 1.20) / 2][date.dayofweek]
        annual_factor = 1 + spec["season"] * np.sin(2 * np.pi * (date.dayofyear - spec["phase"]) / 365.25)
        trend_factor = 1 + spec["trend"] * i
        # This uplift is intentionally simulated and must not be treated as
        # an estimate of real customer response to a promotion.
        simulated_discount_factor = spec["lift"] if discount_pct else 1.0
        expected_units = spec["base"] * weekday_factor * annual_factor * trend_factor * simulated_discount_factor
        units = int(rng.poisson(expected_units))
        price = round(spec["price"] * (1 - discount_pct / 100), 2)
        rows.append({
            "date": date.date().isoformat(),
            "product_id": spec["id"],
            "product": spec["name"],
            "units_sold": units,
            "discount_pct": discount_pct,
            "unit_price": price,
            "synthetic_data": True,
        })
    return pd.DataFrame(rows)


def generate_product_datasets(start: str = "2024-01-01", end: str | None = None,
                              seed: int = 42) -> dict[str, pd.DataFrame]:
    """Generate one reproducible daily sales frame per catalog product."""
    end = _end_date(end)
    return {
        spec["id"]: generate(start, end, seed + (index * 137), product=spec["name"])
        for index, spec in enumerate(PRODUCTS)
    }


def generate_multi_product(start: str = "2024-01-01", end: str | None = None,
                           seed: int = 42) -> pd.DataFrame:
    """Generate a combined daily sales ledger for every sample product."""
    frames = list(generate_product_datasets(start, end, seed).values())
    return pd.concat(frames, ignore_index=True).sort_values(["date", "product_id"]).reset_index(drop=True)


if __name__ == "__main__":
    folder = Path(__file__).parent
    single = generate()
    single_path = folder / "synthetic_lays_cream_onion_sales.csv"
    single.to_csv(single_path, index=False)
    print(f"Created {len(single):,} single-product daily rows: {single_path}")

    product_data = generate_product_datasets()
    multi = pd.concat(product_data.values(), ignore_index=True).sort_values(
        ["date", "product_id"]).reset_index(drop=True)
    multi_path = folder / "synthetic_multi_product_sales.csv"
    multi.to_csv(multi_path, index=False)
    print(f"Created {len(multi):,} multi-product daily rows for {multi['product'].nunique()} products: {multi_path}")

    separate_folder = folder / "sample_data"
    public_separate_folder = folder / "public" / "sample_data"
    separate_folder.mkdir(exist_ok=True)
    public_separate_folder.mkdir(exist_ok=True)
    for spec in PRODUCTS:
        slug = re.sub(r"[^a-z0-9]+", "_", spec["name"].lower()).strip("_")
        filename = f"{spec['id'].lower()}_{slug}.csv"
        separate_path = separate_folder / filename
        product_data[spec["id"]].to_csv(separate_path, index=False)
        product_data[spec["id"]].to_csv(public_separate_folder / filename, index=False)
        print(f"Created individual sample: {separate_path}")
    print("SIMULATED ONLY: discount response and demand patterns are invented for software testing.")
