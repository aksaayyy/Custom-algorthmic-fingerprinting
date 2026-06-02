#!/usr/bin/env python3
"""
Instagram Reel Hazifier CLI Tool
Downloads and processes Instagram reels to avoid algorithmic fingerprinting
Optionally uploads processed videos to YouTube Shorts
Can run continuously as a Telegram bot to process URLs from messages
"""

import argparse
import sys
import os
import logging
import shutil
import signal
import re
import time
from pathlib import Path
from typing import List, Optional, Set
from datetime import datetime, timedelta

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from downloader import InstagramDownloader
from processor import VideoProcessor
from utils import validate_instagram_url, ensure_directory, get_file_hash

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def process_url_pipeline(url, downloader, processor, output_dir, args, notify=None):
    """
    Process a single URL through the download -> process -> upload pipeline

    Args:
        notify: Optional async callable for progress updates

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Processing: {url}")
        if notify:
            await notify(f"⬇️ Downloading video...")

        # Download video
        video_path = downloader.download(url)
        if not video_path:
            logger.error(f"Failed to download video from {url}")
            if notify:
                await notify(f"❌ Failed to download video")
            return False

        # Extract video metadata for AI context
        video_info = downloader.extract_info(url)
        if video_info:
            uploader_context = f"Instagram reel by @{video_info.get('uploader', 'unknown')}: {video_info.get('title', '')}"
        else:
            uploader_context = url

        if notify:
            await notify(f"🔄 Processing video (zoom, color, 4K upscale)...")

        # Process video
        output_path = processor.process(
            video_path,
            output_dir=output_dir,
            original_url=url
        )

        if output_path and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            file_hash = get_file_hash(output_path)
            logger.info(f"Success: {os.path.basename(output_path)}")
            logger.info(f"Size: {file_size:,} bytes")
            logger.info(f"Hash: {file_hash[:16]}...")

            # YouTube upload integration
            if args.upload_to_youtube:
                if notify:
                    await notify(f"📤 Uploading to YouTube...")
                logger.info("Attempting YouTube upload...")
                try:
                    from youtube_uploader import YouTubeUploader
                    from config import NVIDIA_API_KEY
                    uploader = YouTubeUploader(
                        credentials_path=args.youtube_credentials,
                        token_path=args.youtube_token,
                        grok_api_key=args.grok_api_key,
                        nvidia_api_key=NVIDIA_API_KEY
                    )

                    upload_result = uploader.upload_video(
                        video_path=output_path,
                        title=args.youtube_title,
                        description=args.youtube_description,
                        tags=args.youtube_tags.split(',') if args.youtube_tags else None,
                        privacy_status=args.youtube_privacy,
                        context=uploader_context
                    )

                    if upload_result:
                        video_id = upload_result.get('id', 'unknown')
                        video_url = f"https://youtu.be/{video_id}"
                        logger.info(f"YouTube Upload: SUCCESS (Video ID: {video_id})")
                        if notify:
                            await notify(f"✅ Uploaded to YouTube Shorts!\n{video_url}")

                        if args.delete_after_upload:
                            try:
                                os.remove(output_path)
                                logger.info("Cleanup: Deleted local file after upload")
                            except Exception as e:
                                logger.warning(f"Cleanup Warning: Could not delete file: {e}")
                    else:
                        logger.error("YouTube Upload: FAILED")
                        if notify:
                            await notify(f"⚠️ YouTube upload failed")

                except ImportError:
                    logger.error("YouTube Upload: SKIPPED (google-api-python-client not installed)")
                    logger.info("    Install with: pip install google-auth google-auth-oauthlib google-api-python-client")
                except Exception as e:
                    logger.error(f"YouTube Upload: ERROR - {str(e)}")
                    if notify:
                        await notify(f"⚠️ YouTube upload error: {str(e)[:100]}")

            return True
        else:
            logger.error(f"Failed to process video from {url}")
            if notify:
                await notify(f"❌ Failed to process video")
            return False

    except Exception as e:
        logger.error(f"Error processing {url}: {str(e)}")
        if notify:
            await notify(f"❌ Error: {str(e)[:100]}")
        return False
    finally:
        downloader.cleanup()


def run_telegram_bot_mode(args, output_dir):
    """
    Run the tool continuously as a Telegram bot
    """
    try:
        from telegram import Update
        from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
    except ImportError:
        logger.error("Telegram bot functionality requires python-telegram-bot")
        logger.error("Install with: pip install python-telegram-bot>=20.0")
        sys.exit(1)

    logger.info("Starting Instagram Reel Hazifier in Telegram bot mode...")

    # Track processed URLs to avoid duplicates
    processed_urls: Set[str] = set()
    url_timestamps: dict = {}

    from config import TELEGRAM_PROCESSED_URL_TTL
    url_ttl = TELEGRAM_PROCESSED_URL_TTL

    # Regex to extract Instagram URLs from text
    instagram_url_pattern = re.compile(
        r'https?://(?:www\.)?instagram\.com/(?:reel|p)/[^\s/?]+'
    )

    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming Telegram messages"""
        if not update.message or not update.message.text:
            return

        chat_id = update.message.chat_id
        text = update.message.text

        # Extract Instagram URLs from message
        urls = instagram_url_pattern.findall(text)

        if not urls:
            # No URLs found, optionally respond
            await update.message.reply_text(
                "Send me Instagram reel URLs to process and upload to YouTube Shorts!"
            )
            return

        logger.info(f"Received {len(urls)} URL(s) from chat {chat_id}")

        # Process each URL
        for url in urls:
            # Skip if already processed recently (within last hour)
            if url in processed_urls:
                logger.info(f"Skipping already processed URL: {url}")
                await update.message.reply_text(f"⏭️ Already processed: {url}")
                continue

            logger.info(f"Processing URL: {url}")
            await update.message.reply_text(f"📥 Processing: {url}")

            # Process the URL with progress notifications
            async def notify_progress(msg):
                await update.message.reply_text(msg)
            success = await process_url_pipeline(url, downloader, processor, output_dir, args, notify=notify_progress)

            if success:
                processed_urls.add(url)
                url_timestamps[url] = time.time()
                await update.message.reply_text(f"✅ Successfully processed and uploaded: {url}")
            else:
                await update.message.reply_text(f"❌ Failed to process: {url}")

            # Cleanup old entries from processed_urls
            current_time = time.time()
            expired_urls = [
                u for u, ts in url_timestamps.items()
                if current_time - ts > url_ttl
            ]
            for u in expired_urls:
                processed_urls.discard(u)
                del url_timestamps[u]

    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log the error and send a telegram message to notify the developer."""
        logger.error(msg="Exception while handling an update:", exc_info=context.error)

        # Notify user if possible
        if update and hasattr(update, 'effective_chat') and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="⚠️ An internal error occurred. The bot administrators have been notified."
                )
            except Exception:
                pass  # Ignore errors in error handling

    def signal_handler(signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down...")
        application.stop_running()

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Create the Application with job queue disabled to avoid weak reference issues
    application = Application.builder().token(args.telegram_token).job_queue(None).build()

    # Add handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    # Add command handlers
    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 Instagram Reel Hazifier Bot is online!\n\n"
            "Send me Instagram reel URLs and I'll:\n"
            "1. Download the video\n"
            "2. Process it to avoid algorithmic fingerprinting\n"
            "3. Upload it to YouTube Shorts (public by default)\n"
            "4. Optionally delete the local file\n\n"
            "Use /help for more information."
        )

    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "📋 Available commands:\n"
            "/start - Start the bot and see welcome message\n"
            "/help - Show this help message\n"
            "/status - Show bot status\n\n"
            "Just send Instagram reel URLs to process them automatically!"
        )

    async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uptime = time.time() - start_time
        hours, remainder = divmod(uptime, 3600)
        minutes, seconds = divmod(remainder, 60)
        await update.message.reply_text(
            f"📊 Bot Status:\n"
            f"⏱️ Uptime: {int(hours)}h {int(minutes)}m {int(seconds)}s\n"
            f"📝 Recent URLs processed: {len(processed_urls)}\n"
            f"🎯 Ready to process URLs"
        )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))

    # Start the bot
    start_time = time.time()
    logger.info("Telegram bot started. Waiting for messages...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    logger.info("Telegram bot stopped.")


def main():
    parser = argparse.ArgumentParser(
        description="Download and process Instagram reels to avoid algorithmic fingerprinting",
        formatter_class= argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ig_hazy https://www.instagram.com/reel/ABC123/
  ig_hazy -o ./processed https://www.instagram.com/reel/ABC123/ https://www.instagram.com/reel/DEF456/
  ig_hazy --zoom 1.015 --color 0.008 --speed 1.002 https://www.instagram.com/reel/ABC123/
  ig_hazy --telegram  # Run as Telegram bot
        """
    )

    parser.add_argument(
        'urls',
        metavar='URL',
        nargs='*',  # Changed from '+' to '*' to allow zero URLs in telegram mode
        help='Instagram reel URL(s) to process'
    )

    parser.add_argument(
        '-o', '--output-dir',
        type=str,
        default='.',
        help='Output directory for processed videos (default: current directory)'
    )

    parser.add_argument(
        '--temp-dir',
        type=str,
        default=None,
        help='Temporary directory for downloads (default: system temp)'
    )

    parser.add_argument(
        '--no-intro',
        action='store_true',
        help='Skip adding intro sequence'
    )

    parser.add_argument(
        '--zoom',
        type=float,
        default=1.02,
        help='Zoom factor (1.01-1.03, default: 1.02)'
    )

    parser.add_argument(
        '--color',
        type=float,
        default=0.01,
        help='Color grading strength (0.005-0.02, default: 0.01)'
    )

    parser.add_argument(
        '--speed',
        type=float,
        default=1.0,
        help='Speed adjustment factor (default: 1.0 - no change)'
    )

    parser.add_argument(
        '--intro-duration',
        type=float,
        default=1.0,
        help='Intro duration in seconds (default: 1.0)'
    )

    parser.add_argument(
        '--crf',
        type=int,
        default=18,
        help='FFmpeg CRF value for quality (15-23, default: 18)'
    )

    # YouTube upload arguments
    parser.add_argument(
        '--upload-to-youtube',
        action='store_true',
        help='Enable uploading processed videos to YouTube'
    )

    parser.add_argument(
        '--youtube-title',
        type=str,
        help='Title for YouTube video (auto-generated if not provided)'
    )

    parser.add_argument(
        '--youtube-description',
        type=str,
        help='Description for YouTube video'
    )

    parser.add_argument(
        '--youtube-tags',
        type=str,
        help='Comma-separated tags for YouTube video'
    )

    parser.add_argument(
        '--youtube-privacy',
        choices=['public', 'unlisted', 'private'],
        default='public',
        help='Privacy setting for YouTube video (default: public)'
    )

    parser.add_argument(
        '--youtube-credentials',
        type=str,
        default='client_secrets.json',
        help='Path to YouTube API credentials JSON file (default: client_secrets.json)'
    )

    parser.add_argument(
        '--youtube-token',
        type=str,
        default='token.json',
        help='Path to YouTube OAuth token file (default: token.json)'
    )

    parser.add_argument(
        '--grok-api-key',
        type=str,
        help='Grok API key for generating engaging titles, descriptions, and hashtags (can also be set via GROK_API_KEY env var)'
    )

    parser.add_argument(
        '--delete-after-upload',
        action='store_true',
        help='Delete local video files after successful YouTube upload to save storage'
    )

    # Telegram bot arguments
    parser.add_argument(
        '--telegram',
        action='store_true',
        help='Run continuously as a Telegram bot to process URLs from messages'
    )

    parser.add_argument(
        '--telegram-token',
        type=str,
        default=None,
        help='Telegram bot token (overrides env var)'
    )

    parser.add_argument(
        '--bot',
        type=str,
        default=None,
        help='Bot name from bots_config.json (e.g. alishabitch_bot, NIghtNightBoii, GuardianAngle_bot)'
    )

    args = parser.parse_args()

    # Validate arguments
    if not (1.01 <= args.zoom <= 1.03):
        parser.error("--zoom must be between 1.01 and 1.03")

    if not (0.005 <= args.color <= 0.02):
        parser.error("--color must be between 0.005 and 0.02")

    if not (0.5 <= args.speed <= 2.0):
        parser.error("--speed must be between 0.5 and 2.0")

    if not (15 <= args.crf <= 23):
        parser.error("--crf must be between 15 and 23")

    # Load bot config from bots_config.json if --bot is specified
    from config import TELEGRAM_TOKEN, load_bot_config
    if args.bot:
        bot_cfg = load_bot_config(args.bot)
        bot_token = bot_cfg.get("telegram_token") or args.telegram_token or TELEGRAM_TOKEN
        args.telegram_token = bot_token
        if args.upload_to_youtube:
            args.youtube_credentials = bot_cfg.get("youtube_credentials", args.youtube_credentials)
            args.youtube_token = bot_cfg.get("youtube_token", "token.json")
            args.output_dir = bot_cfg.get("output_dir", args.output_dir)
            logger.info(f"Loaded bot '{args.bot}' — niche: {bot_cfg.get('niche', 'N/A')}")
    else:
        # Resolve Telegram token: CLI arg > env var
        if args.telegram_token:
            args.telegram_token = args.telegram_token
        elif TELEGRAM_TOKEN:
            args.telegram_token = TELEGRAM_TOKEN
        else:
            args.telegram_token = None

    # Handle telegram mode
    if args.telegram:
        if not args.telegram_token:
            parser.error("Telegram token is required. Set in .env, bots_config.json, or pass --telegram-token")
        if not args.upload_to_youtube:
            logger.warning("Running Telegram bot without YouTube upload enabled - videos will be processed but not uploaded")

        if args.upload_to_youtube and not os.path.exists(args.youtube_credentials):
            parser.error(f"YouTube credentials file not found: {args.youtube_credentials}")

        output_dir = ensure_directory(args.output_dir)
        temp_dir = ensure_directory(args.temp_dir) if args.temp_dir else None

        global downloader, processor
        downloader = InstagramDownloader(temp_dir=temp_dir)
        processor = VideoProcessor(
            zoom_factor=args.zoom,
            color_strength=args.color,
            speed_factor=args.speed,
            add_intro=not args.no_intro,
            intro_duration=args.intro_duration,
            crf=args.crf
        )

        run_telegram_bot_mode(args, output_dir)
        return

    # Validate URLs (only in non-telegram mode)
    if not args.urls:
        print("Error: No Instagram reel URLs provided")
        print("Use --telegram flag to run in continuous bot mode, or provide URLs as arguments")
        sys.exit(1)

    valid_urls = []
    invalid_urls = []

    for url in args.urls:
        if validate_instagram_url(url):
            valid_urls.append(url)
        else:
            invalid_urls.append(url)

    if invalid_urls:
        print(f"Warning: Skipping {len(invalid_urls)} invalid URL(s):")
        for url in invalid_urls:
            print(f"  {url}")

    if not valid_urls:
        print("Error: No valid Instagram reel URLs provided")
        sys.exit(1)

    # Setup directories
    output_dir = ensure_directory(args.output_dir)
    temp_dir = ensure_directory(args.temp_dir) if args.temp_dir else None

    # Initialize components
    downloader = InstagramDownloader(temp_dir=temp_dir)
    processor = VideoProcessor(
        zoom_factor=args.zoom,
        color_strength=args.color,
        speed_factor=args.speed,
        add_intro=not args.no_intro,
        intro_duration=args.intro_duration,
        crf=args.crf
    )

    # Process each URL
    successful = 0
    failed = 0

    for url in valid_urls:
        try:
            print(f"\nProcessing: {url}")

            # Download video
            video_path = downloader.download(url)
            if not video_path:
                print(f"  Failed to download video from {url}")
                failed += 1
                continue

            # Extract video metadata for AI context
            video_info = downloader.extract_info(url)
            if video_info:
                uploader_context = f"Instagram reel by @{video_info.get('uploader', 'unknown')}: {video_info.get('title', '')}"
            else:
                uploader_context = url

            # Process video
            output_path = processor.process(
                video_path,
                output_dir=output_dir,
                original_url=url
            )

            if output_path and os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                file_hash = get_file_hash(output_path)
                print(f"  Success: {os.path.basename(output_path)}")
                print(f"  Size: {file_size:,} bytes")
                print(f"  Hash: {file_hash[:16]}...")

                # YouTube upload integration
                if args.upload_to_youtube:
                    print(f"  Attempting YouTube upload...")
                    try:
                        from youtube_uploader import YouTubeUploader
                        from config import NVIDIA_API_KEY
                        uploader = YouTubeUploader(
                            credentials_path=args.youtube_credentials,
                            token_path=args.youtube_token,
                            grok_api_key=args.grok_api_key,
                            nvidia_api_key=NVIDIA_API_KEY
                        )

                        upload_result = uploader.upload_video(
                            video_path=output_path,
                            title=args.youtube_title,
                            description=args.youtube_description,
                            tags=args.youtube_tags.split(',') if args.youtube_tags else None,
                            privacy_status=args.youtube_privacy,
                            context=uploader_context
                        )

                        if upload_result:
                            video_id = upload_result.get('id', 'unknown')
                            print(f"  YouTube Upload: SUCCESS (Video ID: {video_id})")

                            # Delete file after successful upload if requested
                            if args.delete_after_upload:
                                try:
                                    os.remove(output_path)
                                    print(f"  Cleanup: Deleted local file after upload")
                                except Exception as e:
                                    print(f"  Cleanup Warning: Could not delete file: {e}")
                        else:
                            print(f"  YouTube Upload: FAILED")

                    except ImportError:
                        print("  YouTube Upload: SKIPPED (google-api-python-client not installed)")
                        print("    Install with: pip install google-auth google-auth-oauthlib google-api-python-client")
                    except Exception as e:
                        print(f"  YouTube Upload: ERROR - {str(e)}")

                successful += 1
            else:
                print(f"  Failed to process video from {url}")
                failed += 1

        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
            break
        except Exception as e:
            print(f"  Error processing {url}: {str(e)}")
            failed += 1
        finally:
            # Cleanup any temporary files from this iteration
            downloader.cleanup()

    # Final summary
    print(f"\n{'='*50}")
    print(f"Processing complete!")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total: {len(valid_urls)}")
    print(f"{'='*50}")

    if failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()