# LifeTicket

Personal ticketing system for managing chores, gig work, and life tasks.

## Deployment

### 1. DNS Setup

Add an **A record** for `calendar.kylem.cc` pointing to the `inklit.ch` server IP:

```
Type: A
Name: calendar
Value: <inklit.ch server IP>
TTL: 300
```

Verify propagation:
```bash
dig calendar.kylem.cc +short
```

### 2. Server Setup (on inklit.ch)

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

The app runs on `127.0.0.1:5050` (localhost only).

### 5. Nginx + SSL Setup

Create an Nginx site config:

```bash
sudo nano /etc/nginx/sites-available/calendar.kylem.cc
```

```nginx
server {
    listen 80;
    server_name calendar.kylem.cc;

    location / {
        proxy_pass http://127.0.0.1:5050;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site and get an SSL cert:

```bash
sudo ln -s /etc/nginx/sites-available/calendar.kylem.cc /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d calendar.kylem.cc
```

The app will be live at **https://calendar.kylem.cc**

### 6. Verify

```bash
docker compose ps
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
```

## Local Development

```bash
pip install -r requirements.txt
python run.py
# Open http://localhost:5000
```
