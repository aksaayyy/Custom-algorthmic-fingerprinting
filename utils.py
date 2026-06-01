"""
Utility functions for Instagram Reel Hazifier
"""

import os
import re
import hashlib
import tempfile
import shutil
from pathlib import Path
from typing import Optional
import datetime
import random


def validate_instagram_url(url: str) -> bool:
    """
    Validate if URL is a valid Instagram reel or post URL

    Args:
        url: URL string to validate

    Returns:
        bool: True if valid Instagram URL, False otherwise
    """
    patterns = [
        r"^https?://(?:www\.)?instagram\.com/reel/[^/]+/?$",
        r"^https?://(?:www\.)?instagram\.com/p/[^/]+/?$",
    ]

    for pattern in patterns:
        if re.match(pattern, url, re.IGNORECASE):
            return True
    return False


def ensure_directory(path: str) -> Path:
    """
    Ensure directory exists, create if it doesn't

    Args:
        path: Directory path

    Returns:
        Path object of the directory
    """
    if not path:
        path = "."

    dir_path = Path(path).resolve()
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_file_hash(filepath: str, algorithm: str = 'sha256') -> str:
    """
    Calculate hash of a file

    Args:
        filepath: Path to file
        algorithm: Hash algorithm to use (default: sha256)

    Returns:
        Hexadecimal hash string
    """
    hash_obj = hashlib.new(algorithm)

    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_obj.update(chunk)

    return hash_obj.hexdigest()


def modify_file_timestamps(filepath: str, max_hours_offset: int = 24) -> bool:
    """
    Modify file's access and modification times randomly within ±max_hours_offset

    Args:
        filepath: Path to file
        max_hours_offset: Maximum hours offset from current time (default: 24)

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get current timestamp
        now = datetime.datetime.now().timestamp()

        # Calculate random offset within ±max_hours_offset
        max_offset_seconds = max_hours_offset * 3600
        offset = random.uniform(-max_offset_seconds, max_offset_seconds)
        new_timestamp = now + offset

        # Set both access and modification times
        os.utime(filepath, (new_timestamp, new_timestamp))
        return True
    except Exception:
        return False


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe filesystem usage

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    # Remove or replace problematic characters
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
    # Remove leading/trailing spaces and dots
    filename = filename.strip(' .')
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255 - len(ext)] + ext
    return filename


def generate_unique_filename(content_hash: str, extension: str = ".mp4") -> str:
    """
    Generate unique filename using hash and timestamp

    Args:
        content_hash: Hash of the file content
        extension: File extension (default: .mp4)

    Returns:
        Unique filename string
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # Use first 16 characters of hash
    short_hash = content_hash[:16]
    return f"{short_hash}_{timestamp}{extension}"


def cleanup_temp_files(temp_dir: str, prefix: str = "ig_hazy_") -> bool:
    """
    Clean up temporary files with given prefix

    Args:
        temp_dir: Temporary directory path
        prefix: Prefix of files to clean up

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if not os.path.exists(temp_dir):
            return True

        for filename in os.listdir(temp_dir):
            if filename.startswith(prefix):
                filepath = os.path.join(temp_dir, filename)
                try:
                    if os.path.isfile(filepath):
                        os.unlink(filepath)
                    elif os.path.isdir(filepath):
                        shutil.rmtree(filepath)
                except Exception:
                    # Continue cleaning other files even if one fails
                    pass
        return True
    except Exception:
        return False


def get_available_space(path: str) -> int:
    """
    Get available disk space in bytes

    Args:
        path: Path to check

    Returns:
        Available space in bytes
    """
    try:
        stat = shutil.disk_usage(path)
        return stat.free
    except Exception:
        return 0