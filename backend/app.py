import os
from datetime import datetime, timezone
from functools import lru_cache
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import bigquery

app = FastAPI(title="GCP Billing Monitor")
origins = [x.strip() for x in os.getenv("ALLOWED_ORIGINS", "").split(",") if x.strip()]
if origins:
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET"], allow_headers=["X-API-Key"])

SOURCES = {
    "tesla": ("Tesla Charging Management", "tesla-charge-hub", "gcp_billing_monitor"),
    "mymap": ("マイマップ", "taycan-evcc", "gcp_billing_monitor"),
}

def authorized(key):
    secret = os.getenv("BILLING_READ_TOKEN")
    if not secret:
        raise HTTPException(503, "BILLING_READ_TOKEN is not configured")
    import hmac
    if not key or not hmac.compare_digest(key, secret):
        raise HTTPException(401, "Unauthorized")

@lru_cache(maxsize=1)
def client():
    return bigquery.Client()

def read_account(name, project, dataset):
    # BigQuery exports use one table per billing account; discover by prefix.
    tables = list(client().list_tables(f"{project}.{dataset}"))
    ids = [t.table_id for t in tables if t.table_id.startswith("gcp_billing_export_v1_")]
    if not ids:
        return {"name": name, "status": "pending", "currency": None, "month": None, "previous_month": None, "daily": []}
    # Restrict discovered table IDs to the known export naming convention.
    import re
    daily = {}
    currencies = set()
    previous = {}
    for table in ids:
        if not re.fullmatch(r"gcp_billing_export_v1_[A-F0-9_]+", table):
            continue
        sql = f"""
        SELECT FORMAT_DATE('%Y-%m', DATE(usage_start_time, 'Asia/Tokyo')) AS month,
               FORMAT_DATE('%Y-%m-%d', DATE(usage_start_time, 'Asia/Tokyo')) AS day,
               currency,
               SUM(cost + IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS net
        FROM `{project}.{dataset}.{table}`
        WHERE DATE(usage_start_time, 'Asia/Tokyo') >= DATE_SUB(DATE_TRUNC(CURRENT_DATE('Asia/Tokyo'), MONTH), INTERVAL 1 MONTH)
          AND DATE(usage_start_time, 'Asia/Tokyo') <= CURRENT_DATE('Asia/Tokyo')
        GROUP BY 1,2,3
        """
        job = client().query(sql, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=100_000_000))
        for row in job.result():
            currencies.add(row.currency)
            month = row.month
            if month == datetime.now(timezone.utc).astimezone(__import__("zoneinfo").ZoneInfo("Asia/Tokyo")).strftime("%Y-%m"):
                daily[row.day] = daily.get(row.day, 0) + float(row.net)
            else:
                previous[month] = previous.get(month, 0) + float(row.net)
    if len(currencies) != 1:
        return {"name": name, "status": "currency_mismatch", "currencies": sorted(currencies)}
    return {"name": name, "status": "ready", "currency": next(iter(currencies)), "month": round(sum(daily.values()), 2), "previous_month": round(sum(previous.values()), 2), "daily": [{"date": d, "amount": round(v, 2)} for d,v in sorted(daily.items())]}

@app.get("/api/billing")
def billing(x_api_key: str | None = Header(default=None)):
    authorized(x_api_key)
    accounts = {}
    for key, (name, project, dataset) in SOURCES.items():
        try:
            accounts[key] = read_account(name, project, dataset)
        except Exception:
            # Avoid exposing Google API internals to public clients.
            accounts[key] = {"name": name, "status": "error"}
    ready = [v for v in accounts.values() if v["status"] == "ready"]
    currencies = {v["currency"] for v in ready}
    total = round(sum(v["month"] for v in ready), 2) if len(ready) == len(accounts) and len(currencies) == 1 else None
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "accounts": accounts, "total_month": total, "currency": next(iter(currencies)) if len(currencies) == 1 else None}
