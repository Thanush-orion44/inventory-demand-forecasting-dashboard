"""Vercel Python function and dependency-light local dashboard server."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import StringIO
from pathlib import Path
import sys
from urllib.parse import urlparse

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from inventory_forecast import build_report

PUBLIC = ROOT / "public"


def forecast_from_payload(payload: dict) -> dict:
    csv_text = payload.get("csv_text", "")
    if not csv_text.strip():
        raise ValueError("Choose a CSV file first")
    if len(csv_text.encode("utf-8")) > 4_000_000:
        raise ValueError("CSV must be smaller than 4 MB")
    date_column = str(payload.get("date_column", "date"))
    sales_column = str(payload.get("sales_column", "sales"))
    product_column = str(payload.get("product_column", "")).strip()
    product = str(payload.get("product", "")).strip()
    try:
        df = pd.read_csv(StringIO(csv_text))
    except Exception as error:
        raise ValueError(f"Could not read this CSV: {error}") from error
    needed = [date_column, sales_column] + ([product_column] if product_column else [])
    missing = [column for column in needed if column not in df.columns]
    if missing:
        raise ValueError(f"Missing column(s): {', '.join(missing)}")
    df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
    df[sales_column] = pd.to_numeric(df[sales_column], errors="coerce")
    df = df.dropna(subset=[date_column, sales_column])
    if product_column:
        if not product:
            choices = df[product_column].dropna().astype(str).unique()
            if len(choices) != 1:
                raise ValueError("Enter the name of the one product to forecast")
            product = choices[0]
        df = df[df[product_column].astype(str) == product]
    elif not product:
        product = "Single product"
    if df.empty:
        raise ValueError("No valid sales rows found for that product")
    if (df[sales_column] < 0).any():
        raise ValueError("Sales units cannot be negative")
    daily = df.groupby(df[date_column].dt.normalize())[sales_column].sum().sort_index()
    daily = daily.asfreq("D", fill_value=0).astype(float)
    try:
        summary, rows = build_report(
            daily, product, int(payload.get("stock", 0)),
            int(payload.get("lead_time_days", 7)), int(payload.get("safety_days", 3)),
            float(payload.get("discount_uplift_pct", 0)),
        )
    except (TypeError, ValueError) as error:
        raise ValueError(str(error)) from error
    return {"summary": summary, "daily_forecast": rows.to_dict(orient="records")}


class handler(BaseHTTPRequestHandler):
    """Vercel-compatible Python request handler; also serves local development."""

    def _send(self, status: int, content: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            target = PUBLIC / "index.html"
            content_type = "text/html; charset=utf-8"
        elif path == "/synthetic_lays_cream_onion_sales.csv":
            target = PUBLIC / "synthetic_lays_cream_onion_sales.csv"
            content_type = "text/csv; charset=utf-8"
        elif path == "/api/health":
            self._send(200, b'{"status":"ok"}', "application/json")
            return
        else:
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        try:
            self._send(200, target.read_bytes(), content_type)
        except FileNotFoundError:
            self._send(404, b"Dashboard file not found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/forecast":
            self._send(404, b'{"detail":"Not found"}', "application/json")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 4_200_000:
                raise ValueError("Upload is too large; use a CSV smaller than 4 MB")
            payload = json.loads(self.rfile.read(length))
            result = forecast_from_payload(payload)
            content = json.dumps(result, allow_nan=False).encode("utf-8")
            self._send(200, content, "application/json; charset=utf-8")
        except (json.JSONDecodeError, ValueError, TypeError) as error:
            content = json.dumps({"detail": str(error)}).encode("utf-8")
            self._send(400, content, "application/json; charset=utf-8")
        except Exception as error:
            content = json.dumps({"detail": f"Forecast failed: {error}"}).encode("utf-8")
            self._send(500, content, "application/json; charset=utf-8")

    def log_message(self, format: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8000), handler)
    print("Dashboard running at http://127.0.0.1:8000")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard...")
        server.server_close()
