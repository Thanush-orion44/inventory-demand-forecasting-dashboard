# Stockwise inventory dashboard

This is a small, deploy-ready dashboard for forecasting one product at a time.
It uses a static HTML interface and a Python function, so there is no Node.js
build or frontend package installation.

**Live dashboard:** <https://inventory-demand-forecasting-dashbo.vercel.app/>

**Source repository:** <https://github.com/Thanush-orion44/inventory-demand-forecasting-dashboard>

## Run locally

Install the Python packages once:

```sh
python -m pip install -r requirements.txt
```

Start the dashboard and API together:

```sh
python api/forecast.py
```

Open <http://127.0.0.1:8000>. Use **Try 6-product sample** to load the
combined synthetic sales ledger. Choose one product from the product-name
suggestions, then generate its forecast. You can also upload your own CSV with
date and units-sold columns. Forecasts can be downloaded as CSV.

The sample includes Lays Cream & Onion, Coca-Cola 500ml, Maggi Masala Noodles
70g, Dairy Milk 40g, Parle-G Biscuits, and Kurkure Masala Munch. The combined
The [combined six-product dataset](synthetic_multi_product_sales.csv) and the
original [single-product sample](synthetic_lays_cream_onion_sales.csv) are
included. Run `python generate_synthetic_sales.py` to recreate both files with
daily data through yesterday.

## Deployment

The project is deployed on Vercel. Vercel serves the static dashboard from
`public/` and runs `api/forecast.py` as a Python Function, using the entrypoint
declared in `pyproject.toml`. Dependencies are listed in `pyproject.toml` and
`requirements.txt`. There is no frontend build command or required environment
variable. The dashboard calls the same-origin endpoint `/api/forecast`.

The Vercel project is connected to the GitHub repository above; pushes to the
`main` branch trigger deployments.

## Data notes

Uploaded CSV data is processed in memory and is not saved by the app. Keep CSV
uploads below 4 MB. Missing calendar dates are filled as zero sales, so use a
complete daily history or confirm that missing rows mean zero sales.

The included synthetic products, demand patterns, and promotion responses are
invented for UI and software testing. The dashboard's discount view uses an
uplift percentage you choose; it is not learned from synthetic discount rows
or verified store data.
Stock recommendations use on-hand stock, lead time, and safety days; they do
not yet include incoming purchase orders, pack sizes, expiry, or multiple
locations.
