# Instagram Reel Hazifier

Download Instagram reels, apply anti-fingerprinting transforms, and auto-upload to YouTube Shorts with AI-generated titles & captions.

## Features

- **Anti-fingerprinting** — Zoom crop, color shift, 4K upscale to avoid algorithmic detection
- **YouTube Shorts upload** — Direct upload with AI-generated titles, descriptions, CTAs, and tags
- **Telegram bot mode** — Run 24/7: send an Instagram URL to the bot, it handles the rest
- **AI metadata** — NVIDIA Llama 3.1 (primary) / Grok (fallback) for engaging titles & CTAs
- **4K quality** — Lanczos upscale to 2160×3840 portrait for high-res Shorts
- **One-click run** — `run.bat` installs deps and starts the bot

## Quick Start

### Local (Windows)

```bash
# 1. Copy environment config
cp .env.example .env

# 2. Edit .env and add your keys:
#    - BOT1/BOT2/BOT3_TELEGRAM_TOKEN (from @BotFather)
#    - NVIDIA_API_KEY (for AI captions)
#    - GROK_API_KEY (fallback, optional)

# 3. Run all 3 bots
.\run.bat
```

### Docker / VPS (Linux)

```bash
# 1. Clone repo on VPS
git clone https://github.com/aksaayyy/Custom-algorthmic-fingerprinting.git
cd Custom-algorthmic-fingerprinting

# 2. Copy and edit .env with your keys
cp .env.example .env
nano .env

# 3. Copy your YouTube OAuth files
#    (credentials_bot*.json + token_bot*.json from your local machine)

# 4. Build and start all 3 bots
docker compose up -d --build

# 5. Check logs
docker compose logs -f
```

## Prerequisites

- **FFmpeg** — Download from https://ffmpeg.org/download.html, add to PATH
- **Python 3.7+**
- **YouTube API credentials** — One Google Cloud project per bot → `credentials_bot*.json` + `token_bot*.json`
- **Docker** (for VPS deployment)

## Usage

### Telegram Bot Mode (recommended)

```bash
.\run.bat
```

Send Instagram reel URLs to your Telegram bot. It will:
1. ⬇️ Download the video
2. 🔄 Apply anti-fingerprinting transforms + 4K upscale
3. 🤖 Generate title, description & CTAs via AI
4. 📤 Upload to YouTube Shorts
5. ✅ Reply with the YouTube link

### CLI Mode

```bash
# Process a single reel (no upload)
python cli.py https://www.instagram.com/reel/ABC123/

# Process and upload to YouTube
python cli.py --upload-to-youtube https://www.instagram.com/reel/ABC123/
```

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_TOKEN` | Yes (bot mode) | From @BotFather |
| `NVIDIA_API_KEY` | No | AI captions via Llama 3.1 |
| `GROK_API_KEY` | No | AI fallback |

## Docker Deployment

Each bot runs as its own container with auto-restart. Files are auto-deleted after YouTube + Telegram upload succeed.

### VPS Setup (from scratch)

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Clone repo
git clone https://github.com/aksaayyy/Custom-algorthmic-fingerprinting.git
cd Custom-algorthmic-fingerprinting

# Configure
cp .env.example .env
nano .env                              # Add your API keys & tokens

# Copy OAuth files from local machine (via SCP or similar)
# credentials_bot1.json + token_bot1.json
# credentials_bot2.json + token_bot2.json
# credentials_bot3.json + token_bot3.json

# Start
docker compose up -d --build

# Monitor
docker compose logs -f
```

### Useful commands

```bash
# View logs for a specific bot
docker compose logs -f alishabitch

# Restart a specific bot
docker compose restart nightnight

# Stop everything
docker compose down

# Update to latest code
git pull
docker compose up -d --build
```

## Project Structure

```
├── cli.py                 # CLI + Telegram bot
├── config.py              # Settings
├── downloader.py          # yt-dlp wrapper
├── processor.py           # FFmpeg video processing
├── youtube_uploader.py    # YouTube Data API upload
├── channel_uploader.py    # Telegram channel backup
├── nvidia_generator.py    # NVIDIA AI metadata
├── grok_generator.py      # Grok AI fallback
├── utils.py               # Helpers
├── run.bat                # One-click launcher (Windows)
├── Dockerfile             # Container image
├── docker-compose.yml     # Multi-bot orchestration
├── .dockerignore
├── .env.example           # Config template
├── bots_config.json       # Per-bot settings
└── requirements.txt
```
