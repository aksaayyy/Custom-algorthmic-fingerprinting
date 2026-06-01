"""
Video processor module for Instagram Reel Hazifier
Handles FFmpeg-based video processing pipeline
"""

import os
import subprocess
import tempfile
import json
from pathlib import Path
from typing import Optional, Dict, Any
import logging

from config import (
    FFMPEG_PRESET,
    FFMPEG_CRF_DEFAULT,
    FFMPEG_AUDIO_BITRATE,
    FFMPEG_THREADS,
    ZOOM_MIN,
    ZOOM_MAX,
    COLOR_MIN,
    COLOR_MAX,
    SPEED_MIN,
    SPEED_MAX,
    INTRO_DURATION_DEFAULT,
    INTRO_FADE_DURATION,
    HIGH_QUALITY_SCALE,
    FFMPEG_TIMEOUT,
)
from utils import (
    get_file_hash,
    modify_file_timestamps,
    generate_unique_filename,
    cleanup_temp_files
)


class VideoProcessor:
    def __init__(
        self,
        zoom_factor: float = 1.02,
        color_strength: float = 0.01,
        speed_factor: float = 1.005,
        add_intro: bool = True,
        intro_duration: float = 1.0,
        crf: int = FFMPEG_CRF_DEFAULT,
        high_quality: bool = True,
    ):
        """
        Initialize the video processor

        Args:
            zoom_factor: Zoom factor (1.01-1.03)
            color_strength: Color grading strength (0.005-0.02)
            speed_factor: Speed adjustment factor (0.995-1.005)
            add_intro: Whether to add intro sequence
            intro_duration: Intro duration in seconds
            crf: FFmpeg CRF value for quality (15-23)
            high_quality: Upscale to 4K with max quality settings
        """
        self.zoom_factor = zoom_factor
        self.color_strength = color_strength
        self.speed_factor = speed_factor
        self.add_intro = add_intro
        self.intro_duration = intro_duration
        self.crf = crf
        self.high_quality = high_quality
        self.logger = logging.getLogger(__name__)

        # Check if FFmpeg is available
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        """Check if FFmpeg is installed and available"""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                check=True,
                timeout=10
            )
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            raise RuntimeError(
                "FFmpeg is not installed or not available in PATH. "
                "Please install FFmpeg from https://ffmpeg.org/download.html"
            )

    def _get_video_info(self, video_path: str) -> Optional[Dict[str, Any]]:
        """
        Get video information using FFprobe

        Args:
            video_path: Path to video file

        Returns:
            Dictionary with video info or None if failed
        """
        try:
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                video_path
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                self.logger.error(f"FFprobe failed: {result.stderr}")
                return None
        except Exception as e:
            self.logger.error(f"Error getting video info: {str(e)}")
            return None

    def _build_filter_chain(
        self,
        width: int,
        height: int,
        has_audio: bool = True
    ) -> str:
        """
        Build FFmpeg filter chain for video processing

        Args:
            width: Video width
            height: Video height
            has_audio: Whether video has audio stream

        Returns:
            Filter chain string
        """
        filters = []

        # Zoom/crop filter
        if self.zoom_factor != 1.0:
            # Calculate crop dimensions
            crop_width = int(width / self.zoom_factor)
            crop_height = int(height / self.zoom_factor)
            # Calculate crop offsets (center crop)
            crop_x = (width - crop_width) // 2
            crop_y = (height - crop_height) // 2

            zoom_filter = (
                f"crop={crop_width}:{crop_height}:{crop_x}:{crop_y},"
                f"scale={width}:{height}"
            )
            filters.append(zoom_filter)

        # Color grading filter
        if self.color_strength != 0:
            # Randomly choose brightness adjustment direction
            brightness_adjust = self.color_strength if random.choice([True, False]) else -self.color_strength
            saturation_adjust = 1 + self.color_strength
            gamma_adjust = 1 - (self.color_strength * 0.5)

            color_filter = (
                f"eq=brightness={brightness_adjust}:"
                f"saturation={saturation_adjust}:"
                f"gamma={gamma_adjust}"
            )
            filters.append(color_filter)

        # Speed adjustment filter (for video)
        if self.speed_factor != 1.0:
            speed_filter = f"setpts={(1/self.speed_factor)}*PTS"
            filters.append(speed_filter)

        # 4K upscale for high quality YouTube Shorts
        if self.high_quality:
            filters.append(f"scale={HIGH_QUALITY_SCALE}:flags=lanczos")

        return ",".join(filters) if filters else None

    def _build_audio_filters(self) -> Optional[str]:
        """
        Build FFmpeg audio filters

        Returns:
            Audio filter chain string
        """
        audio_filters = []

        # Speed adjustment for audio (atempo has limitations, so we chain if needed)
        if self.speed_factor != 1.0:
            # atempo works best between 0.5 and 2.0, our range is fine
            audio_filters.append(f"atempo={self.speed_factor}")

        return ",".join(audio_filters) if audio_filters else None

    def _create_intro_clip(self, width: int, height: int, duration: float) -> str:
        """
        Create intro clip (black video with fade-in and silent audio)

        Args:
            width: Video width
            height: Video height
            duration: Duration of intro in seconds

        Returns:
            Path to intro clip file
        """
        temp_dir = tempfile.gettempdir()
        intro_path = os.path.join(temp_dir, f"intro_{os.getpid()}.mp4")

        # Create black video with silent audio
        cmd = [
            "ffmpeg",
            "-f", "lavfi",
            "-i", f"color=c=black:s={width}x{height}:d={duration}",
            "-f", "lavfi",
            "-i", f"anullsrc=r=44100:cl=stereo:d={duration}",  # Silent audio
            "-filter_complex", f"[0:v]fade=t=in:st=0:d={INTRO_FADE_DURATION}:alpha=1[vout]",
            "-map", "[vout]",
            "-map", "1:a",
            "-c:v", "libx264",
            "-preset", FFMPEG_PRESET,
            "-crf", str(self.crf),
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", FFMPEG_AUDIO_BITRATE,
            "-t", str(duration),
            "-y",  # Overwrite output file
            intro_path
        ]

        try:
            subprocess.run(
                cmd,
                capture_output=True,
                check=True,
                timeout=30
            )
            return intro_path
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to create intro clip: {e.stderr}")
            raise
        except Exception as e:
            self.logger.error(f"Error creating intro clip: {str(e)}")
            raise

    def process(
        self,
        video_path: str,
        output_dir: Path,
        original_url: str
    ) -> Optional[str]:
        """
        Process video through the full pipeline

        Args:
            video_path: Path to input video file
            output_dir: Output directory path
            original_url: Original Instagram URL (for logging)

        Returns:
            Path to processed video file, or None if failed
        """
        temp_files_to_clean = []

        try:
            self.logger.info(f"Processing video: {video_path}")

            # Get video information
            video_info = self._get_video_info(video_path)
            if not video_info:
                self.logger.error("Failed to get video information")
                return None

            # Find video stream
            video_stream = None
            audio_stream = None
            for stream in video_info.get('streams', []):
                if stream.get('codec_type') == 'video' and video_stream is None:
                    video_stream = stream
                elif stream.get('codec_type') == 'audio' and audio_stream is None:
                    audio_stream = stream

            if not video_stream:
                self.logger.error("No video stream found")
                return None

            width = int(video_stream.get('width', 0))
            height = int(video_stream.get('height', 0))
            has_audio = audio_stream is not None

            self.logger.info(f"Video dimensions: {width}x{height}, has_audio: {has_audio}")

            # Create temporary output file
            temp_dir = tempfile.gettempdir()
            temp_output = os.path.join(temp_dir, f"processed_{os.getpid()}_{int(time.time())}.mp4")
            temp_files_to_clean.append(temp_output)

            # Build FFmpeg command
            cmd = ["ffmpeg", "-y"]  # Overwrite output

            # Input
            cmd.extend(["-i", video_path])

            # Build filter chains
            video_filter = self._build_filter_chain(width, height, has_audio)
            audio_filter = self._build_audio_filters()

            # Add intro if requested
            if self.add_intro and self.intro_duration > 0:
                # Create intro clip
                intro_path = self._create_intro_clip(width, height, self.intro_duration)
                temp_files_to_clean.append(intro_path)

                # For intro, we need to concatenate: [intro] + [processed video]
                # We'll use a more complex filtergraph

                # Process main video first to temp file
                processed_temp = os.path.join(temp_dir, f"main_processed_{os.getpid()}.mp4")
                temp_files_to_clean.append(processed_temp)

                # Build filter for main video processing
                filter_parts = []
                if video_filter:
                    filter_parts.append(f"[0:v]{video_filter}[vout]")
                if has_audio and audio_filter:
                    filter_parts.append(f"[0:a]{audio_filter}[aout]")

                filter_complex = ";".join(filter_parts) if filter_parts else "null"

                # Process main video
                main_cmd = ["ffmpeg", "-y", "-i", video_path]
                if filter_complex and filter_complex != "null":
                    main_cmd.extend(["-filter_complex", filter_complex])
                    if video_filter:
                        main_cmd.extend(["-map", "[vout]"])
                    if has_audio and audio_filter:
                        main_cmd.extend(["-map", "[aout]"])
                elif not video_filter and not audio_filter:
                    # No filtering needed, just copy
                    main_cmd.extend(["-c:v", "copy", "-c:a", "copy"])
                else:
                    # Only video or only audio filtering
                    if video_filter:
                        main_cmd.extend(["-vf", video_filter])
                    if has_audio and audio_filter:
                        main_cmd.extend(["-af", audio_filter])

                # Encoding settings
                main_cmd.extend([
                    "-c:v", "libx264",
                    "-preset", FFMPEG_PRESET,
                    "-crf", str(self.crf),
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    "-b:a", FFMPEG_AUDIO_BITRATE,
                    processed_temp
                ])

                self.logger.info("Processing main video...")
                subprocess.run(main_cmd, capture_output=True, check=True, timeout=FFMPEG_TIMEOUT)

                # Now concatenate intro + processed video
                # Use concat demuxer instead of filter for more reliability
                concat_list_path = os.path.join(temp_dir, f"concat_list_{os.getpid()}.txt")
                temp_files_to_clean.append(concat_list_path)

                # Create concat demuxer file list
                with open(concat_list_path, 'w') as f:
                    f.write(f"file '{intro_path}'\n")
                    f.write(f"file '{processed_temp}'\n")

                concat_cmd = [
                    "ffmpeg", "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", concat_list_path,
                    "-c", "copy",
                    temp_output
                ]

                self.logger.info("Concatenating intro with processed video...")
                subprocess.run(concat_cmd, capture_output=True, check=True, timeout=FFMPEG_TIMEOUT)

            else:
                # No intro, direct processing
                filter_parts = []
                if video_filter:
                    filter_parts.append(f"[0:v]{video_filter}[vout]")
                if has_audio and audio_filter:
                    filter_parts.append(f"[0:a]{audio_filter}[aout]")

                filter_complex = ";".join(filter_parts) if filter_parts else "null"

                if filter_complex and filter_complex != "null":
                    cmd.extend(["-filter_complex", filter_complex])
                    if video_filter:
                        cmd.extend(["-map", "[vout]"])
                    if has_audio and audio_filter:
                        cmd.extend(["-map", "[aout]"])
                else:
                    # No filtering, copy streams
                    cmd.extend(["-c:v", "copy", "-c:a", "copy"])

                # Encoding settings (if we're encoding)
                if filter_complex and filter_complex != "null":
                    cmd.extend([
                        "-c:v", "libx264",
                        "-preset", FFMPEG_PRESET,
                        "-crf", str(self.crf),
                        "-pix_fmt", "yuv420p",
                        "-c:a", "aac",
                        "-b:a", FFMPEG_AUDIO_BITRATE
                    ])

                cmd.append(temp_output)

                self.logger.info("Processing video...")
                subprocess.run(cmd, capture_output=True, check=True, timeout=FFMPEG_TIMEOUT)

            # Strip metadata from output
            stripped_temp = os.path.join(temp_dir, f"stripped_{os.getpid()}.mp4")
            temp_files_to_clean.append(stripped_temp)

            strip_cmd = [
                "ffmpeg", "-y",
                "-i", temp_output,
                "-map_metadata", "-1",
                "-map_chapters", "-1",
                "-dn",  # Disable data streams
                "-c:v", "copy",
                "-c:a", "copy",
                stripped_temp
            ]

            self.logger.info("Stripping metadata...")
            subprocess.run(strip_cmd, capture_output=True, check=True, timeout=FFMPEG_TIMEOUT)

            # Generate unique filename based on content
            content_hash = get_file_hash(stripped_temp)
            unique_filename = generate_unique_filename(content_hash)
            final_output = output_dir / unique_filename

            # Move to output directory
            shutil.move(stripped_temp, str(final_output))

            # Modify file timestamps
            modify_file_timestamps(str(final_output))

            # Verify output exists and has content
            if not final_output.exists() or final_output.stat().st_size == 0:
                self.logger.error("Output file is missing or empty")
                return None

            self.logger.info(f"Processing complete: {final_output}")
            return str(final_output)

        except subprocess.CalledProcessError as e:
            self.logger.error(f"FFmpeg error: {e.stderr if e.stderr else str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error during processing: {str(e)}")
            return None
        finally:
            # Cleanup temporary files
            for temp_file in temp_files_to_clean:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except Exception:
                    pass  # Ignore cleanup errors

import time
import shutil
import random