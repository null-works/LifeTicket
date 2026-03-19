# LifeTicket

Personal ticketing system for managing chores, gig work, and life tasks.

## Deployment

### 1. DNS Setup

Add an **A record** (or AAAA for IPv6) for `calendar.kylem.cc` pointing to the `inklit.ch` server IP:

```
Type: A
Name: calendar
Value: <inklit.ch server IP>
TTL: 300
```

Set this in whatever manages DNS for `kylem.cc` (Cloudflare, Namecheap, etc). Do **not** use Cloudflare proxy (orange cloud) if you want Let's Encrypt to work via HTTP challenge — use DNS-only (grey cloud).

Verify propagation:
```bash
dig calendar.kylem.cc +short
```

### 2. Server Setup (on inklit.ch)

SSH into the server and clone the repo:

```bash
git clone https://github.com/null-works/LifeTicket.git
cd LifeTicket
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env and set a real secret key:
#   SECRET_KEY=<random string>
```

Generate a secret key:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Launch

```bash
docker compose up -d --build
```

This starts:
- **LifeTicket** app on port 5000 (internal)
- **Caddy** reverse proxy on ports 80/443 with automatic HTTPS via Let's Encrypt

The app will be live at **https://calendar.kylem.cc**

### 5. Verify

```bash
# Check containers are running
docker compose ps

# Check logs
docker compose logs -f

# Test HTTPS
curl -I https://calendar.kylem.cc
```

## Maintenance

```bash
# Pull updates and redeploy
cd LifeTicket
git pull
docker compose up -d --build

# Backup the database
docker compose cp lifeticket:/data/lifeticket.db ./backup-$(date +%Y%m%d).db

# View logs
docker compose logs -f lifeticket
docker compose logs -f caddy
```

## Local Development

```bash
pip install -r requirements.txt
python run.py
# Open http://localhost:5000
```
