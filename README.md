# Custom Algorithmic Fingerprinting

Automated short-form media processing pipeline: download, transform and republish video with AI-generated metadata.

## Overview

This project is an end-to-end media processing and publishing pipeline. It downloads short-form video from Instagram, applies configurable video transformations (crop/zoom, color grading, speed, intro sequence), re-encodes at high resolution for quality, generates YouTube metadata via LLM providers (NVIDIA Llama and Grok), and publishes the result to YouTube Shorts. An optional Telegram bot mode runs the pipeline continuously, processing video URLs sent as chat messages.

The project demonstrates practical engineering across video processing, media pipelines, automation, and API integration.

## Pipeline / How it works

The pipeline is a modular chain with clearly separated responsibilities:

```
Download -> Transform -> Re-encode -> Generate metadata -> Upload -> (optional) Cleanup
```

1. **Download** — `downloader.py` fetches the video with `yt-dlp`, preferring MP4 and falling back to the best available format, with retry and exponential backoff.
2. **Transform** — `processor.py` drives FFmpeg: center crop/zoom, color grading (brightness, saturation, gamma), optional speed adjustment, and an optional intro clip with fade-in.
3. **Re-encode** — Output is re-encoded with libx264 (configurable CRF) and optionally upscaled to 4K portrait (2160x3840) with Lanczos scaling, then stripped of embedded metadata for a clean output.
4. **Generate metadata** — `nvidia_generator.py` (primary) and `grok_generator.py` (fallback) produce titles, descriptions, and tags via LLM APIs, with template-based generation as an offline fallback.
5. **Upload** — `youtube_uploader.py` authenticates via OAuth 2.0 and publishes with resumable uploads and exponential-backoff retry.
6. **Cleanup** — Temporary files are removed automatically; `--delete-after-upload` also removes the local copy after a successful publish.

## Features

- **Video downloads** — Instagram reel/post download via `yt-dlp` with retries and backoff.
- **Video transformations** — Center crop/zoom, color grading, speed adjustment, and optional intro clip, all configurable via CLI flags.
- **High-quality processing** — libx264 re-encode with adjustable CRF and optional 4K portrait upscale.
- **AI-generated metadata** — Titles, descriptions, and tags from LLM providers (NVIDIA Llama primary, Grok fallback), with template fallbacks.
- **Multi-provider generation** — Provider abstraction so metadata generation degrades gracefully when a provider is unavailable.
- **YouTube Shorts publishing** — OAuth 2.0 auth, resumable uploads, automatic Shorts metadata, and public/unlisted/private visibility.
- **Telegram bot mode** — Continuous operation: send an Instagram URL to the bot and it runs the full pipeline and replies with the published link.
- **Batch CLI mode** — Process multiple URLs in one invocation with per-run processing parameters.

## Tech stack

- Python 3.7+
- FFmpeg / ffprobe (video processing and probing)
- yt-dlp (media download)
- YouTube Data API v3 (google-api-python-client, OAuth 2.0)
- NVIDIA NIM / Grok API (LLM metadata generation)
- python-telegram-bot (bot mode)
- python-dotenv (configuration)

## Quick Start

### Prerequisites

- Python 3.7+
- FFmpeg (add `ffmpeg`/`ffprobe` to your PATH) — https://ffmpeg.org/download.html
- Google Cloud OAuth credentials for YouTube uploads (desktop app, `youtube.upload` scope) saved as `client_secrets.json`

### Setup

```bash
# 1. Copy the environment template and fill in your keys
cp .env.example .env

# 2. Install dependencies
pip install -r requirements.txt

# 3. Process a single reel (download + transform only)
python cli.py https://www.instagram.com/reel/ABC123/

# 4. Process and upload to YouTube Shorts
python cli.py --upload-to-youtube https://www.instagram.com/reel/ABC123/

# 5. Run in Telegram bot mode (process URLs from chat messages)
python cli.py --telegram --upload-to-youtube
```

### Examples

```bash
# Multiple URLs with custom transforms
python cli.py -o ./processed --zoom 1.015 --color 0.008 --speed 1.002 URL1 URL2

# Skip intro sequence, lower encode quality
python cli.py --no-intro --crf 20 https://www.instagram.com/reel/ABC123/

# Custom YouTube metadata
python cli.py --upload-to-youtube \
  --youtube-title "My Title" \
  --youtube-description "Description" \
  --youtube-tags "Shorts,Clip" \
  --youtube-privacy unlisted \
  https://www.instagram.com/reel/ABC123/

# Delete the local file after a successful upload
python cli.py --upload-to-youtube --delete-after-upload https://www.instagram.com/reel/ABC123/
```

## Configuration

Create a `.env` file from `.env.example`. API keys are never required: without LLM keys the pipeline uses template-based metadata generation, and without Telegram keys only CLI mode is available.

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT1_TELEGRAM_TOKEN` | For bot mode | Telegram bot token (BotFather) |
| `BOT2_TELEGRAM_TOKEN` | Optional | Additional bot token |
| `BOT3_TELEGRAM_TOKEN` | Optional | Additional bot token |
| `NVIDIA_API_KEY` | No | NVIDIA NIM API key (primary metadata generator) |
| `GROK_API_KEY` | No | xAI Grok API key (fallback metadata generator) |

Processing parameters (zoom, color, speed, intro, CRF, etc.) are CLI flags; see `python cli.py --help`.

## Project structure

```
├── cli.py                 # CLI entrypoint + Telegram bot mode
├── config.py              # Constants and environment configuration
├── downloader.py          # yt-dlp download with retries
├── processor.py           # FFmpeg transform/re-encode pipeline
├── youtube_uploader.py    # YouTube Data API v3 upload
├── nvidia_generator.py    # NVIDIA Llama metadata generation
├── grok_generator.py      # Grok metadata generation (fallback)
├── utils.py               # Helpers (hashing, filenames, cleanup)
├── requirements.txt       # Python dependencies
├── .env.example           # Environment template
└── .gitignore
```

## License

MIT
