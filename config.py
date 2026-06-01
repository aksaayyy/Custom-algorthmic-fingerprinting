"""
Configuration constants for Instagram Reel Hazifier
"""

import os

# FFmpeg settings
FFMPEG_PRESET = "slow"
FFMPEG_CRF_DEFAULT = 15
FFMPEG_CRF_MIN = 12
FFMPEG_CRF_MAX = 23
FFMPEG_AUDIO_BITRATE = "320k"
HIGH_QUALITY_SCALE = "-2:3840"  # Upscale to 4K portrait (auto width, height=3840) for YouTube Shorts
FFMPEG_TIMEOUT = 600  # Max seconds per FFmpeg encode (10 min for 4K upscale)

# Processing parameters
ZOOM_MIN = 1.01
ZOOM_MAX = 1.03
ZOOM_DEFAULT = 1.02

COLOR_MIN = 0.005
COLOR_MAX = 0.02
COLOR_DEFAULT = 0.01

SPEED_MIN = 1.0
SPEED_MAX = 1.0
SPEED_DEFAULT = 1.0

INTRO_DURATION_DEFAULT = 1.0
INTRO_FADE_DURATION = 0.5

# File handling
TEMP_PREFIX = "ig_hazy_"
OUTPUT_EXTENSION = ".mp4"
HASH_LENGTH = 16  # Number of hex characters to use in filename

# Instagram URL patterns
INSTAGRAM_REEL_PATTERNS = [
    r"https?://(?:www\.)?instagram\.com/reel/[^/]+/?",
    r"https?://(?:www\.)?instagram\.com/p/[^/]+/?",  # Also handle regular posts
]

# Retry settings
MAX_DOWNLOAD_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2  # Exponential backoff multiplier

# Timestamp modification
TIMESTAMP_VARIATION_HOURS = 24  # Modify timestamps within ±24 hours

# Memory/buffer settings
DOWNLOAD_CHUNK_SIZE = 8192  # 8KB chunks for yt-dlp equivalent
FFMPEG_THREADS = 0  # 0 = auto-detect based on CPU cores

# Telegram bot settings
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_PROCESSED_URL_TTL = 3600  # 1 hour before clearing processed URL cache

# AI content generation
NVIDIA_API_KEY = os.getenv('NVIDIA_API_KEY')
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODEL = "meta/llama-3.1-8b-instruct"