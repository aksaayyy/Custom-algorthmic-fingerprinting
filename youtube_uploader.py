"""
YouTube uploader module for Instagram Reel Hazifier
Handles uploading processed videos to YouTube with optimized metadata
"""

import os
import json
import pickle
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging
import time

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# YouTube API scopes
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

# AI content generators for metadata
try:
    from nvidia_generator import NvidiaGenerator
    NVIDIA_AVAILABLE = True
except ImportError:
    NVIDIA_AVAILABLE = False
    NvidiaGenerator = None

try:
    from grok_generator import GrokGenerator
    GROK_AVAILABLE = True
except ImportError:
    GROK_AVAILABLE = False
    GrokGenerator = None


class YouTubeUploader:
    def __init__(self, credentials_path: str = 'client_secrets.json', token_path: str = 'token.json', grok_api_key: Optional[str] = None, nvidia_api_key: Optional[str] = None):
        """
        Initialize the YouTube uploader

        Args:
            credentials_path: Path to Google API credentials JSON file
            token_path: Path to store/load OAuth token
            grok_api_key: Grok API key (fallback, can also be set via GROK_API_KEY env var)
            nvidia_api_key: NVIDIA API key (primary, can also be set via NVIDIA_API_KEY env var)
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.logger = logging.getLogger(__name__)
        self.youtube = None

        # Initialize AI generators (NVIDIA preferred, Grok as fallback)
        self.nvidia_generator = None
        self.grok_generator = None

        if NVIDIA_AVAILABLE:
            self.nvidia_generator = NvidiaGenerator(api_key=nvidia_api_key)
            if self.nvidia_generator.api_key:
                self.logger.info("NVIDIA AI (Kimi K2.6) integration enabled for enhanced metadata generation")
        elif GROK_AVAILABLE:
            self.grok_generator = GrokGenerator(api_key=grok_api_key)
            if self.grok_generator.api_key:
                self.logger.info("Grok AI integration enabled as fallback for metadata generation")
            else:
                self.logger.info("No AI API keys provided - using template-based generation")
        else:
            self.logger.info("No AI generators available - using template-based generation")

        self._authenticate()

    def _authenticate(self):
        """Authenticate with YouTube API using OAuth 2.0"""
        creds = None

        # Load existing token if available
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)

        # If there are no (valid) credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Credentials file not found: {self.credentials_path}\n"
                        "Please download OAuth 2.0 credentials from Google Cloud Console "
                        "and save as 'client_secrets.json' (or specify path with --youtube-credentials)"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)

        self.youtube = build(API_SERVICE_NAME, API_VERSION, credentials=creds)

    def _generate_optimized_title(self, video_path: str, custom_title: Optional[str] = None, context: str = "") -> str:
        if custom_title:
            return custom_title[:100]

        video_context = context or self._extract_context(video_path)

        if self.nvidia_generator and self.nvidia_generator.api_key:
            meta = self.nvidia_generator.generate_complete_metadata(video_context)
            if meta and meta.get('title'):
                return meta['title'][:100]
        elif self.grok_generator and self.grok_generator.api_key:
            ai_title = self.grok_generator.generate_engaging_title(video_context)
            if ai_title and len(ai_title) <= 100:
                return ai_title.strip('"\'')

        title = f"Amazing Clip! {video_context.replace('_', ' ').title()} 🔥 #Shorts"
        return title[:100]

    def _generate_optimized_description(self, video_path: str, custom_description: Optional[str] = None, context: str = "") -> str:
        if custom_description:
            return custom_description

        video_context = context or self._extract_context(video_path)

        if self.nvidia_generator and self.nvidia_generator.api_key:
            meta = self.nvidia_generator.generate_complete_metadata(video_context)
            if meta and meta.get('description'):
                return meta['description']
        elif self.grok_generator and self.grok_generator.api_key:
            ai_description = self.grok_generator.generate_engaging_description(video_context)
            if ai_description:
                return ai_description

        hashtags = ["#Shorts", "#Viral", "#Trending", "#FYP"]
        description = f"""Check out this amazing clip!

{' '.join(hashtags)}

👍 Like if you enjoyed!
💬 Comment your thoughts below!
🔔 Subscribe for more amazing content!
🔄 Share with your friends!

#Shorts #Viral #Trending"""

        return description

    def _generate_optimized_tags(self, video_path: str = None, custom_tags: Optional[str] = None, context: str = "") -> List[str]:
        if custom_tags:
            tags = [tag.strip() for tag in custom_tags.split(',') if tag.strip()]
            return tags[:15]

        video_context = context or (self._extract_context(video_path) if video_path else "")

        if self.nvidia_generator and self.nvidia_generator.api_key:
            meta = self.nvidia_generator.generate_complete_metadata(video_context)
            if meta and meta.get('tags') and len(meta['tags']) >= 3:
                return meta['tags']
        elif self.grok_generator and self.grok_generator.api_key:
            ai_hashtags = self.grok_generator.generate_hashtags(video_context, count=8)
            if ai_hashtags and len(ai_hashtags) >= 3:
                return ai_hashtags

        return ["Shorts", "Viral", "Trending", "FYP", "Amazing", "Clip", "Entertainment"]

    def _extract_context(self, video_path: str) -> str:
        filename = os.path.basename(video_path)
        name_part = filename.split('_')[0] if '_' in filename else filename
        name_part = name_part.replace('.mp4', '')
        return name_part.replace('_', ' ')

    def _detect_shorts_format(self, video_path: str) -> bool:
        """
        Detect if video is in Shorts format (vertical 9:16 aspect ratio)

        Args:
            video_path: Path to video file

        Returns:
            True if video appears to be Shorts format
        """
        try:
            import subprocess
            import json

            # Use ffprobe to get video dimensions
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                "-select_streams", "v:0",
                video_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                data = json.loads(result.stdout)
                if data.get('streams'):
                    stream = data['streams'][0]
                    width = int(stream.get('width', 0))
                    height = int(stream.get('height', 0))

                    if width > 0 and height > 0:
                        ratio = width / height
                        # Shorts is typically 9:16 (0.5625) or close to vertical
                        return 0.5 <= ratio <= 0.7  # Allow some tolerance

            return False
        except Exception:
            # If detection fails, assume it's Shorts since that's our target use case
            return True

    def upload_video(self, video_path: str, title: Optional[str] = None,
                     description: Optional[str] = None, tags: Optional[List[str]] = None,
                     privacy_status: str = 'unlisted',
                     context: str = "") -> Optional[Dict[str, Any]]:
        """
        Upload video to YouTube

        Args:
            video_path: Path to video file to upload
            title: Video title (auto-generated if None)
            description: Video description (auto-generated if None)
            tags: List of tags (auto-generated if None)
            privacy_status: Privacy setting (public/unlisted/private)
            context: Original Instagram URL or content description for AI generation

        Returns:
            Dictionary with upload response (including video ID) or None if failed
        """
        if not os.path.exists(video_path):
            self.logger.error(f"Video file not found: {video_path}")
            return None

        file_size = os.path.getsize(video_path)
        if file_size > 256 * 1024 * 1024 * 1024:
            self.logger.error(f"Video file too large: {file_size} bytes (max 256GB)")
            return None

        try:
            if not title:
                title = self._generate_optimized_title(video_path, context=context)
            if not description:
                description = self._generate_optimized_description(video_path, context=context)
            if tags is None:
                tags = self._generate_optimized_tags(video_path, context=context)

            # Force Shorts for Instagram content (all reels are vertical 9:16)
            if "#Shorts" not in title:
                title = title.rstrip() + " #Shorts"
            if "#Shorts" not in description:
                description = "#Shorts\n" + description
            # Ensure 'Shorts' is first tag
            tags = ['Shorts'] + [t for t in tags if t.lower() != 'shorts']

            # Prepare upload request body
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': tags,
                    'categoryId': '24'  # Entertainment category
                },
                'status': {
                    'privacyStatus': privacy_status,
                    'selfDeclaredMadeForKids': False
                }
            }

            # Create media upload object
            media = MediaFileUpload(
                video_path,
                chunksize=-1,  # Upload in single chunk
                resumable=True
            )

            # Execute upload request
            self.logger.info(f"Starting upload: {title}")
            insert_request = self.youtube.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )

            # Resumable upload with exponential backoff
            response = None
            error = None
            retry = 0
            max_retries = 3

            while response is None:
                try:
                    status, response = insert_request.next_chunk()
                    if status:
                        self.logger.info(f"Upload progress: {int(status.progress() * 100)}%")
                except HttpError as e:
                    if e.resp.status in [500, 502, 503, 504]:
                        # Retryable errors
                        error = e
                        retry += 1
                        if retry > max_retries:
                            self.logger.error(f"Max retries exceeded: {e}")
                            return None

                        # Exponential backoff
                        wait_time = 2 ** retry
                        self.logger.warning(f"Retryable error: {e}. Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        self.logger.error(f"HTTP error {e.resp.status}: {e.content}")
                        return None
                except Exception as e:
                    self.logger.error(f"Upload error: {e}")
                    return None

            if response:
                video_id = response.get('id')
                self.logger.info(f"Upload successful! Video ID: {video_id}")
                return response
            else:
                self.logger.error("Upload failed: No response received")
                return None

        except HttpError as e:
            self.logger.error(f"YouTube API error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error during upload: {e}")
            return None


# Convenience function for simple usage
def upload_to_youtube(video_path: str, title: Optional[str] = None,
                     description: Optional[str] = None, tags: Optional[List[str]] = None,
                     privacy_status: str = 'unlisted',
                     credentials_path: str = 'client_secrets.json') -> Optional[Dict[str, Any]]:
    """
    Convenience function to upload a video to YouTube

    Args:
        video_path: Path to video file
        title: Video title
        description: Video description
        tags: List of tags
        privacy_status: Privacy setting
        credentials_path: Path to OAuth credentials

    Returns:
        Upload response dictionary or None if failed
    """
    uploader = YouTubeUploader(credentials_path=credentials_path)
    return uploader.upload_video(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        privacy_status=privacy_status
    )