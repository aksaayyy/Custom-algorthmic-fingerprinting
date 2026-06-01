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

```bash
# 1. Copy environment config
cp .env.example .env

# 2. Edit .env and add your keys:
#    - TELEGRAM_TOKEN (from @BotFather)
#    - NVIDIA_API_KEY (for AI captions)
#    - GROK_API_KEY (fallback, optional)

# 3. Run the bot
.\run.bat
```

## Prerequisites

- **FFmpeg** — Download from https://ffmpeg.org/download.html, add to PATH
- **Python 3.7+**
- **Google API credentials** (for YouTube upload) — Save as `client_secrets.json`

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

## Project Structure

```
├── cli.py                 # CLI + Telegram bot
├── config.py              # Settings
├── downloader.py          # yt-dlp wrapper
├── processor.py           # FFmpeg video processing
├── youtube_uploader.py    # YouTube Data API upload
├── nvidia_generator.py    # NVIDIA AI metadata
├── grok_generator.py      # Grok AI fallback
├── utils.py               # Helpers
├── run.bat                # One-click launcher
├── .env.example           # Config template
└── requirements.txt
```
