# Replay - Spotify Playlist Manager

A web application that creates and maintains auto-updating Spotify playlists with your recently played tracks.

## Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up Spotify App:
   - Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   - Create a new app
   - Set redirect URI to `http://localhost:8000/callback`
   - Copy Client ID and Client Secret

4. Set environment variables:
   Copy `.env.example` to `.env` and fill in your Spotify credentials:
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   ```
   
   Make sure the `SPOTIFY_REDIRECT_URI` matches exactly what you set in your Spotify app dashboard.

5. Initialize the database:
   ```bash
   python init_db.py
   ```

## Running the Application

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 in your browser.

**Important**: Make sure your Spotify app's redirect URI is set to `http://localhost:8000/callback` (exactly matching the `SPOTIFY_REDIRECT_URI` in your `.env` file).

## Features

- Login with Spotify
- Create auto-updating playlists
- Background job updates playlists with recently played tracks
- One playlist per user (create or update)
- Automatically adds currently playing track to top of playlist
- Maintains 100-track playlist limit

## Production Deployment with Systemd and Nginx

### Systemd Socket Configuration

Create `/etc/systemd/system/replay.socket`:

```ini
[Unit]
Description=Replay FastAPI Socket
Before=replay.service

[Socket]
ListenStream=%t/replay.sock
SocketMode=0660
User=replay
Group=www-data

[Install]
WantedBy=sockets.target
```

### Systemd Service Configuration

Create `/etc/systemd/system/replay.service`:

```ini
[Unit]
Description=Replay Spotify Playlist Manager
Requires=replay.socket
After=network.target

[Service]
Type=notify
User=replay
WorkingDirectory=/home/replay/replay
Environment="PATH=/home/replay/replay/venv/bin"
ExecStart=/home/replay/replay/venv/bin/uvicorn main:app --fd 0
StandardOutput=journal
StandardError=journal

# Restart policy
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

### Nginx Configuration

Add to `/etc/nginx/sites-available/replay`:

```nginx
upstream replay {
    server unix:/run/replay.sock fail_timeout=0;
}

server {
    listen 80;
    server_name replay.example.com;

    location / {
        proxy_pass http://replay;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/replay /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Systemd Management

Start and enable the services:
```bash
sudo systemctl daemon-reload
sudo systemctl enable replay.socket
sudo systemctl start replay.socket
sudo systemctl start replay.service
```

View service status:
```bash
sudo systemctl status replay.service
sudo systemctl status replay.socket
```

View logs:
```bash
sudo journalctl -u replay.service -f
```

Restart the service:
```bash
sudo systemctl restart replay.service
```

### Cron Job for Playlist Updates

Add to crontab:
```bash
crontab -e
```

Example: Update playlists every hour at the top of the hour:
```bash
0 * * * * cd /home/replay/replay && /home/replay/replay/venv/bin/python update_playlists.py >> /var/log/replay/update.log 2>&1
```

Or every 30 minutes:
```bash
*/30 * * * * cd /home/replay/replay && /home/replay/replay/venv/bin/python update_playlists.py >> /var/log/replay/update.log 2>&1
```

Create the log directory:
```bash
sudo mkdir -p /var/log/replay
sudo chown replay:www-data /var/log/replay
```

### User Setup

Create a dedicated user:
```bash
sudo useradd -r -s /bin/bash -d /home/replay -m replay
```

Set permissions:
```bash
sudo chown -R replay:www-data /home/replay/replay
sudo chmod -R 750 /home/replay/replay
```

### Environment Variables

Place your `.env` file in `/home/replay/replay/`:
```bash
sudo cp .env /home/replay/replay/.env
sudo chown replay:www-data /home/replay/replay/.env
sudo chmod 600 /home/replay/replay/.env
```

Update the `SPOTIFY_REDIRECT_URI` to match your production domain:
```
SPOTIFY_REDIRECT_URI=https://replay.example.com/callback
```

### SSL/TLS with Let's Encrypt

Install Certbot:
```bash
sudo apt-get install certbot python3-certbot-nginx
```

Get certificate:
```bash
sudo certbot certonly --nginx -d replay.example.com
```

Update Nginx config to use SSL:
```nginx
server {
    listen 80;
    server_name replay.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name replay.example.com;

    ssl_certificate /etc/letsencrypt/live/replay.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/replay.example.com/privkey.pem;

    location / {
        proxy_pass http://replay;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}
```

Auto-renew certificates:
```bash
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

### Troubleshooting

**Socket not found:**
```bash
ls -la /run/replay.sock
```

**Permission denied errors:**
```bash
sudo journalctl -u replay.service -n 50
```

**Nginx upstream errors:**
Check that the socket path in nginx matches the systemd socket configuration.