import os
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


def send_video_to_channel(
    video_path: str,
    bot_token: str,
    channel_id: str,
    caption: str = ""
) -> bool:
    """Upload a video file to a Telegram channel.

    Args:
        video_path: Path to the video file
        bot_token: Telegram bot token that is admin in the channel
        channel_id: Channel ID (e.g. -1001234567890 or @username)
        caption: Optional caption for the video

    Returns:
        True if upload succeeded, False otherwise
    """
    if not bot_token or not channel_id:
        logger.warning("Telegram channel bot token or channel ID not configured")
        return False

    if not os.path.exists(video_path):
        logger.error(f"Video file not found for channel upload: {video_path}")
        return False

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
        file_size = os.path.getsize(video_path)
        logger.info(f"Uploading {file_size:,} bytes to Telegram channel {channel_id}...")

        with open(video_path, "rb") as f:
            data = {
                "chat_id": channel_id,
                "caption": caption[:1024],
                "parse_mode": "HTML",
            }
            files = {"video": f}
            resp = requests.post(url, data=data, files=files, timeout=300)

        if resp.status_code == 200:
            result = resp.json()
            if result.get("ok"):
                logger.info("Telegram channel upload successful")
                return True

        logger.warning(f"Telegram channel upload failed: {resp.status_code} {resp.text[:200]}")
        return False

    except requests.exceptions.Timeout:
        logger.warning("Telegram channel upload timed out (video may be too large)")
        return False
    except Exception as e:
        logger.warning(f"Telegram channel upload error: {e}")
        return False
