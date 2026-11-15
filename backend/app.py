import os
from datetime import datetime, timezone, timedelta
from functools import lru_cache
from threading import Lock
from time import monotonic
from calendar import monthrange
from zoneinfo import ZoneInfo
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
    services = {}
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    current_month = now.strftime("%Y-%m")
    previous_month = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    for table in ids:
        if not re.fullmatch(r"gcp_billing_export_v1_[A-F0-9_]+", table):
            continue
        sql = f"""
        SELECT FORMAT_DATE('%Y-%m', DATE(usage_start_time, 'Asia/Tokyo')) AS month,
               FORMAT_DATE('%Y-%m-%d', DATE(usage_start_time, 'Asia/Tokyo')) AS day,
               currency,
               service.description AS service_name,
               SUM(cost + IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS net
        FROM `{project}.{dataset}.{table}`
        WHERE DATE(usage_start_time, 'Asia/Tokyo') >= DATE_SUB(DATE_TRUNC(CURRENT_DATE('Asia/Tokyo'), MONTH), INTERVAL 1 MONTH)
          AND DATE(usage_start_time, 'Asia/Tokyo') <= CURRENT_DATE('Asia/Tokyo')
        GROUP BY 1,2,3,4
        """
        job = client().query(sql, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=100_000_000))
        for row in job.result():
            currencies.add(row.currency)
            value = float(row.net)
            if row.month == current_month:
                services[row.service_name or "Unknown"] = services.get(row.service_name or "Unknown", 0) + value
                daily[row.day] = daily.get(row.day, 0) + value
            elif row.month == previous_month:
                previous[row.month] = previous.get(row.month, 0) + value
    if not currencies:
        return {"name": name, "status": "pending", "currency": None, "month": None, "previous_month": None, "daily": []}
    if len(currencies) != 1:
        return {"name": name, "status": "currency_mismatch", "currencies": sorted(currencies)}
    days = monthrange(now.year, now.month)[1]
    # Forecast assumes uniform daily usage; it is not a Google Cloud invoice forecast.
    forecast = round(sum(daily.values()) / now.day * days, 2) if daily else None
    return {"name": name, "status": "ready", "currency": next(iter(currencies)), "month": round(sum(daily.values()), 2), "previous_month": round(sum(previous.values()), 2), "forecast": forecast, "services": [{"name": k, "amount": round(v, 2)} for k,v in sorted(services.items(), key=lambda p: -p[1])], "daily": [{"date": d, "amount": round(v, 2)} for d,v in sorted(daily.items())]}

_cache_lock = Lock()
_cache_until = 0.0
_cache_value = None

@app.get("/api/billing")
def billing(x_api_key: str | None = Header(default=None)):
    authorized(x_api_key)
    global _cache_until, _cache_value
    with _cache_lock:
        if _cache_value is not None and monotonic() < _cache_until:
            return _cache_value
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
        forecast = round(sum(v["forecast"] for v in ready), 2) if total is not None and all(v.get("forecast") is not None for v in ready) else None
        budget = float(os.getenv("MONTHLY_BUDGET", "0"))
        _cache_value = {"generated_at": datetime.now(timezone.utc).isoformat(), "accounts": accounts, "total_month": total, "forecast": forecast, "budget": budget or None, "over_budget": forecast > budget if forecast is not None and budget > 0 else None, "currency": next(iter(currencies)) if len(currencies) == 1 else None}
        ttl = max(300, int(os.getenv("CACHE_SECONDS", "3600")))
        # Retry transient failures sooner; never cache an error for a full hour.
        _cache_until = monotonic() + (min(ttl, 300) if any(a["status"] == "error" for a in accounts.values()) else ttl)
        return _cache_value
