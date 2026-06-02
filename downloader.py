"""
Downloader module for Instagram Reel Hazifier
Handles downloading videos using yt-dlp with retry logic
"""

import os
import tempfile
import time
import subprocess
from pathlib import Path
from typing import Optional
import logging

from config import (
    MAX_DOWNLOAD_RETRIES,
    RETRY_BACKOFF_FACTOR,
    TEMP_PREFIX
)
from utils import sanitize_filename


class InstagramDownloader:
    def __init__(self, temp_dir: Optional[str] = None):
        """
        Initialize the downloader

        Args:
            temp_dir: Temporary directory for downloads (optional)
        """
        self.temp_dir = temp_dir
        self.logger = logging.getLogger(__name__)
        # Check if yt-dlp is available
        self._check_yt_dlp()

    def _check_yt_dlp(self):
        """Check if yt-dlp is installed and available"""
        try:
            subprocess.run(
                ["yt-dlp", "--version"],
                capture_output=True,
                check=True,
                timeout=10
            )
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            raise RuntimeError(
                "yt-dlp is not installed or not available in PATH. "
                "Please install it using: pip install yt-dlp"
            )

    def download(self, url: str) -> Optional[str]:
        """
        Download video from Instagram URL

        Args:
            url: Instagram reel/post URL

        Returns:
            Path to downloaded video file, or None if failed
        """
        if not self.temp_dir:
            # Create a temporary directory
            temp_dir = tempfile.mkdtemp(prefix=TEMP_PREFIX)
        else:
            temp_dir = self.temp_dir
            os.makedirs(temp_dir, exist_ok=True)

        # Prepare output template
        output_template = os.path.join(temp_dir, "%(title)s.%(ext)s")

        # Try downloading with retries
        for attempt in range(MAX_DOWNLOAD_RETRIES):
            try:
                self.logger.info(f"Downloading from {url} (attempt {attempt + 1})")

                # Build yt-dlp command
                cmd = [
                    "yt-dlp",
                    "--format", "best[ext=mp4]/best",  # Prefer MP4, fallback to best
                    "--output", output_template,
                    "--no-warnings",
                    "--no-playlist",
                    "--quiet",  # We'll handle our own logging
                    url
                ]

                # Run yt-dlp
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout per download
                )

                if result.returncode == 0:
                    # Find the downloaded file
                    downloaded_files = []
                    for file in os.listdir(temp_dir):
                        if file.startswith(TEMP_PREFIX) or not file.startswith('.'):
                            # Check if it's a video file
                            if file.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
                                downloaded_files.append(os.path.join(temp_dir, file))

                    if downloaded_files:
                        # If multiple files, take the largest one (likely the video)
                        downloaded_files.sort(key=lambda x: os.path.getsize(x), reverse=True)
                        video_path = downloaded_files[0]
                        self.logger.info(f"Download successful: {video_path}")
                        return video_path
                    else:
                        self.logger.warning("No video file found after download")
                else:
                    self.logger.warning(
                        f"yt-dlp failed with return code {result.returncode}: {result.stderr}"
                    )

            except subprocess.TimeoutExpired:
                self.logger.warning(f"Download timed out (attempt {attempt + 1})")
            except Exception as e:
                self.logger.warning(f"Unexpected error during download: {str(e)}")

            # If we have retries left, wait before next attempt
            if attempt < MAX_DOWNLOAD_RETRIES - 1:
                wait_time = RETRY_BACKOFF_FACTOR ** attempt
                self.logger.info(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)

        self.logger.error(f"Failed to download video from {url} after {MAX_DOWNLOAD_RETRIES} attempts")
        return None

    def extract_info(self, url: str) -> Optional[dict]:
        """Extract video metadata (title, uploader) using yt-dlp --dump-json"""
        try:
            cmd = [
                "yt-dlp",
                "--dump-json",
                "--no-warnings",
                "--no-playlist",
                "--quiet",
                url
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and result.stdout.strip():
                import json
                info = json.loads(result.stdout.strip().split('\n')[0])
                return info
        except Exception as e:
            self.logger.warning(f"Failed to extract video info: {e}")
        return None

    def cleanup(self):
        """Clean up temporary files created by this downloader"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            from utils import cleanup_temp_files
            cleanup_temp_files(self.temp_dir, TEMP_PREFIX)