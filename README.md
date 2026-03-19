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

### 2. Install

```bash
git clone https://github.com/null-works/LifeTicket.git
cd LifeTicket
sudo ./install.sh
```

This handles everything: generates `.env`, builds the Docker container, configures Nginx, and obtains an SSL cert via Certbot.

The app will be live at **https://calendar.kylem.cc**

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
