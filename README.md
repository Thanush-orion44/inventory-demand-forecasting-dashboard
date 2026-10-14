# Stockwise inventory dashboard

This is a small, deploy-ready dashboard for forecasting one product at a time.
It uses a static HTML interface and a Python function, so there is no Node.js
build or frontend package installation.

## Run locally

Install the Python packages once:

```sh
python -m pip install -r requirements.txt
```

Start the dashboard and API together:

```sh
python api/forecast.py
```

Open <http://127.0.0.1:8000>. Use **Try sample data** to load the included
simulated Lays Cream & Onion CSV, or upload a CSV with date and units-sold
columns. The forecast can be downloaded as a CSV.

## Deploy on Vercel

The repo is configured with `vercel.json`: Vercel serves the `public/`
dashboard and builds `api/forecast.py` as a Python Function. `requirements.txt`
contains the runtime dependencies. The Python runtime is currently documented
by Vercel as Beta.

To deploy, put this project in a Git repository, import that repository in
Vercel, and deploy with the root directory selected. No build command or
environment variables are needed for this prototype. The same-origin API
endpoint is `/api/forecast`.

## Data notes

Uploaded CSV data is processed in memory and is not saved by the app. Keep CSV
uploads below 4 MB. Missing calendar dates are filled as zero sales, so use a
complete daily history or confirm that missing rows mean zero sales.

The included synthetic dataset and its promotion lift are invented for UI and
software testing. The dashboard's discount view uses an uplift percentage you
choose; it is not learned from synthetic discount rows or verified store data.
Stock recommendations use on-hand stock, lead time, and safety days; they do
not yet include incoming purchase orders, pack sizes, expiry, or multiple
locations.
