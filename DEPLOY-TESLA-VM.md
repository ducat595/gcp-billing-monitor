# Tesla VM deployment (approved configuration)

Target: existing VM `tesla-charge-collector`. New service only; do not restart or edit `tesla-charge-api.service`, `tesla-charge-collector.service`, or port 8088.

## Installation — run in the VM SSH shell

These steps add a new dedicated application, Python virtual environment, and systemd service. They do not alter existing Tesla services.

```bash
set -e
sudo mkdir -p /opt/gcp-billing-monitor
sudo chown "$(id -un):$(id -gn)" /opt/gcp-billing-monitor
git clone --branch develop/billing-dashboard --single-branch https://github.com/ducat595/gcp-billing-monitor.git /opt/gcp-billing-monitor/source
python3 -m venv /opt/gcp-billing-monitor/venv
/opt/gcp-billing-monitor/venv/bin/python -m pip install -r /opt/gcp-billing-monitor/source/backend/requirements.txt
/opt/gcp-billing-monitor/venv/bin/python -m unittest discover -s /opt/gcp-billing-monitor/source/backend/tests -v
```

If `git clone` fails because the directory already exists, stop and inspect before modifying it.

## API token and service

```bash
set -e
sudo install -d -m 700 /etc/gcp-billing-monitor
TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
printf 'BILLING_READ_TOKEN=%s\nCACHE_SECONDS=3600\n' "$TOKEN" | sudo tee /etc/gcp-billing-monitor/billing.env >/dev/null
sudo chmod 600 /etc/gcp-billing-monitor/billing.env
unset TOKEN
sudo tee /etc/systemd/system/gcp-billing-monitor.service >/dev/null <<'UNIT'
[Unit]
Description=GCP Billing Monitor dashboard and API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/gcp-billing-monitor/source
EnvironmentFile=/etc/gcp-billing-monitor/billing.env
ExecStart=/opt/gcp-billing-monitor/venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8767
Restart=on-failure
RestartSec=10
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now gcp-billing-monitor.service
curl -fsSI http://127.0.0.1:8767/
```

The service runs as root initially to use the VM's existing application default credentials if configured; this is not the intended final least-privilege setup. Prefer a dedicated service identity and Unix user after checking BigQuery access. Never copy Google Cloud credentials to the public repository. Without BigQuery access, the dashboard displays per-account `error`, not `pending`.

## Tailnet-only HTTPS (not public Funnel)

First verify `sudo tailscale serve status` still says `No serve config`, then:

```bash
sudo tailscale serve --bg --https=443 http://127.0.0.1:8767
sudo tailscale serve status
tailscale status --self
```

Do not run `tailscale funnel`. The dashboard should be accessible to authenticated devices on the same tailnet at the HTTPS URL printed by `tailscale serve status`. Enter the token stored in `/etc/gcp-billing-monitor/billing.env` in the dashboard. Do not paste that token into chat.

## Rollback (only the new app)

```bash
sudo tailscale serve --https=443 off
sudo systemctl disable --now gcp-billing-monitor.service
sudo rm -f /etc/systemd/system/gcp-billing-monitor.service
sudo systemctl daemon-reload
```

The application directory and private token file can be removed separately after confirming no data is needed. Do not reset unrelated Tailscale configurations.

## Notes

- Billing export may be delayed; the UI shows pending for empty export tables.
- BigQuery access is not yet granted; permissions must be scoped to the two export datasets and tested.
- BigQuery reads can incur charges; the app caps individual query bytes and caches responses.
- No firewall or existing service ports need to change.
