# Deploy the backend on Oracle Cloud Always Free

The API and its saved models run in Docker on one free Ampere VM. Caddy in front of it obtains and renews the HTTPS certificate. On start the API downloads the latest verified release (models and serving data) from the release bucket and checks every file's checksum. It then polls for newer releases every five minutes.

## 1. Create the VM

1. Sign up at [cloud.oracle.com](https://cloud.oracle.com). A card is needed for verification; Always Free resources are not charged.
2. **Compute → Instances → Create instance**
   - Image: **Canonical Ubuntu 22.04** (or 24.04)
   - Shape: **Ampere → VM.Standard.A1.Flex**, 2 OCPU and 12 GB memory (the free allowance is 4 OCPU and 24 GB in total)
   - Add your SSH public key, keep "Assign a public IPv4 address" on
   - If you see *Out of capacity*, try another availability domain or retry later
3. Note the instance's **public IP**.
4. **Networking → Virtual cloud networks → your VCN → Security lists → Default security list → Add ingress rules**: source `0.0.0.0/0`, TCP, destination ports `80` and `443` (one rule each).

## 2. Prepare the server

```bash
ssh ubuntu@<public-ip>
git clone https://github.com/artignite3/NEW_X1.git && cd NEW_X1
sudo bash deploy/oracle/setup.sh
exit            # log back in so Docker works without sudo
```

## 3. Configure and start

```bash
ssh ubuntu@<public-ip>
cd NEW_X1/deploy/oracle
cp server.env.example server.env
nano server.env
docker compose up -d --build
```

In `server.env`:

- `API_DOMAIN`: your own domain pointed at the IP, or `<ip-with-dashes>.sslip.io` (for IP `129.146.10.20` use `129-146-10-20.sslip.io`)
- Supabase URL and publishable key
- Bucket name, prefix and region, plus **read-only** keys for that prefix

The first build takes 10 to 20 minutes on ARM. Then:

```bash
docker compose ps                          # api should become "healthy"
docker compose logs -f api                 # release restore and startup
curl https://<API_DOMAIN>/health           # "models": all true
```

## 4. Point the website at it

1. GitHub → repository → **Settings → Secrets and variables → Actions → Variables**: set `NEXT_PUBLIC_API_BASE` to `https://<API_DOMAIN>`.
2. Re-run the **Deploy website to Cloudflare Pages** workflow, or push to `main`.

The site only sends sign-in tokens to this configured address, tunnel hosts or localhost.

## 5. Keep data fresh (optional)

The refresh worker downloads new matches, rebuilds features and publishes a release that the API picks up automatically. It needs write-capable keys, kept apart from the API's:

```bash
cp worker.env.example worker.env && nano worker.env
docker compose --profile worker run --rm worker          # run once now
crontab -e
# daily at 02:30 UTC:
30 2 * * * cd /home/ubuntu/NEW_X1/deploy/oracle && docker compose --profile worker run --rm worker >> /home/ubuntu/worker.log 2>&1
```

## Updating

```bash
cd ~/NEW_X1 && git pull && cd deploy/oracle && docker compose up -d --build
```

## Notes

- Written analyst reports need a local language model, which this server does not run, so reports use the rule-based summary.
- `server.env` and `worker.env` hold secrets and are git-ignored. Never commit them.
- `/live` is the liveness check. `/ready` also requires a release newer than 72 hours, so it reports not ready until the worker has run recently.
