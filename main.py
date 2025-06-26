import os
import asyncio
import yt_dlp
from telegram import Bot
from telegram.error import TelegramError
import logging

# Configure logging to see detailed output
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
# IMPORTANT: Replace these with your actual Telegram Bot Token and Channel ID
# It's highly recommended to use environment variables in production environments like Railway.
# Example: TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
# Example: TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')
TELEGRAM_BOT_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'  # Get this from BotFather
TELEGRAM_CHANNEL_ID = '-1001234567890'  # Get this from @RawDataBot (note the negative sign for channel IDs)

# Directory to save downloaded videos temporarily
DOWNLOAD_DIR = 'downloads'

# Create the download directory if it doesn't exist
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
logger.info(f"Download directory '{DOWNLOAD_DIR}' ensured.")

async def download_youtube_video(url: str, output_path: str) -> str | None:
    """
    Downloads a YouTube video using yt-dlp.
    Supports downloading videos of any length and merges audio/video if necessary.

    Args:
        url (str): The URL of the YouTube video.
        output_path (str): The directory where the video should be saved.

    Returns:
        str | None: The full path to the downloaded video file, or None if download fails.
    """
    # Options for yt-dlp
    ydl_opts = {
        # 'bestvideo[ext=mp4]+bestaudio[ext=m4a]' ensures best quality video and audio
        # are downloaded separately and then merged. 'best[ext=mp4]/best' is a fallback.
        # This is crucial for long videos as they often have separate audio/video streams.
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        # 'outtmpl' specifies the output filename template.
        # %(title)s will use the video's title, %(ext)s will use its extension.
        'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
        # 'merge_output_format' ensures the final output is an MP4 file.
        # Requires FFmpeg to be installed and in your system's PATH for merging.
        'merge_output_format': 'mp4',
        'noplaylist': True,  # Ensures only the single video is downloaded, not an entire playlist
        'concurrent_fragments': 5, # Number of fragments to download concurrently (can speed up downloads)
        'retries': 5, # Number of retries for failed downloads, useful for long downloads
        'postprocessors': [{
            'key': 'FFmpegMetadata', # Ensures metadata is embedded (like title)
        }],
    }

    try:
        logger.info(f"Attempting to download video from: {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # extract_info with download=True initiates the download
            info_dict = ydl.extract_info(url, download=True)
            # prepare_filename gets the actual file path that yt-dlp used
            filename = ydl.prepare_filename(info_dict)
            logger.info(f"Successfully downloaded: {filename}")
            return filename
    except yt_dlp.DownloadError as e:
        logger.error(f"yt-dlp Download Error for {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during video download from {url}: {e}")
        return None

async def send_video_to_telegram(bot: Bot, chat_id: str, video_path: str, caption: str = None):
    """
    Sends a video file to a Telegram chat/channel.
    Logs warnings for large files that might exceed Telegram's direct bot upload limit (50MB).

    Args:
        bot (telegram.Bot): The Telegram Bot instance.
        chat_id (str): The ID of the target chat or channel.
        video_path (str): The full path to the video file to send.
        caption (str, optional): A caption for the video. Defaults to None.
    """
    try:
        file_size = os.path.getsize(video_path)
        file_size_mb = file_size / (1024 * 1024)

        if file_size_mb > 50:
            logger.warning(
                f"Video '{os.path.basename(video_path)}' is {file_size_mb:.2f} MB. "
                "Telegram's direct bot video upload limit is around 50MB. "
                "For very large files, consider:\n"
                "  1. Sending as a document (`bot.send_document` instead of `send_video`). This allows up to 2GB.\n"
                "  2. Using a local Telegram Bot API server (removes the 50MB limit for direct uploads)."
                "  The current code will attempt to send as a video, which might fail."
            )
            # Example of sending as a document for larger files:
            # with open(video_path, 'rb') as video_file:
            #     await bot.send_document(chat_id=chat_id, document=video_file, caption=caption, filename=os.path.basename(video_path))
            #     logger.info(f"Video sent as document: {video_path}")
            #     return

        # Open the video file in binary read mode
        with open(video_path, 'rb') as video_file:
            # send_video supports streaming, which is good for larger videos
            await bot.send_video(chat_id=chat_id, video=video_file, caption=caption, supports_streaming=True)
            logger.info(f"Video '{os.path.basename(video_path)}' successfully sent to Telegram.")

    except FileNotFoundError:
        logger.error(f"Error: Video file not found at path: {video_path}")
    except TelegramError as e:
        logger.error(f"Telegram API error when sending video '{os.path.basename(video_path)}': {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred when sending '{os.path.basename(video_path)}' to Telegram: {e}")

async def main():
    """
    Main function to orchestrate video download and Telegram sending.
    """
    if TELEGRAM_BOT_TOKEN == 'YOUR_TELEGRAM_BOT_TOKEN' or TELEGRAM_CHANNEL_ID == '-1001234567890':
        logger.error("Please update TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID in the script with your actual values.")
        logger.error("Alternatively, set them as environment variables (recommended for Railway).")
        return

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    logger.info("Telegram Bot initialized.")

    # List of YouTube video URLs to process.
    # Replace these with the actual 1-hour and 2-hour YouTube video URLs you want.
    youtube_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Example: A short video (for testing)
        "https://www.youtube.com/watch?v=kYqg460iU-0",  # Example: A longer video (replace with your target videos)
        # Add more YouTube URLs here as needed for 1-hour and 2-hour videos
        # e.g., "https://www.youtube.com/watch?v=YOUR_1_HOUR_VIDEO_URL",
        # e.g., "https://www.youtube.com/watch?v=YOUR_2_HOUR_VIDEO_URL",
    ]

    for url in youtube_urls:
        logger.info(f"\n--- Starting processing for URL: {url} ---")
        downloaded_file_path = await download_youtube_video(url, DOWNLOAD_DIR)

        if downloaded_file_path:
            # Dynamically get video title for a good caption
            video_title = "YouTube Video"
            try:
                # Re-extract info without downloading to get metadata like title
                with yt_dlp.YoutubeDL({'skip_download': True, 'quiet': True}) as ydl:
                    info = ydl.extract_info(url, download=False)
                    video_title = info.get('title', video_title)
            except Exception as e:
                logger.warning(f"Could not extract video title for {url}: {e}")

            caption_text = f"Title: {video_title}\nSource: {url}"
            await send_video_to_telegram(bot, TELEGRAM_CHANNEL_ID, downloaded_file_path, caption=caption_text)

            # Optional: Remove the downloaded file after sending to save disk space
            try:
                os.remove(downloaded_file_path)
                logger.info(f"Successfully removed local file: {downloaded_file_path}")
            except OSError as e:
                logger.warning(f"Error removing file {downloaded_file_path}: {e}")
        else:
            logger.error(f"Skipping Telegram upload for URL {url} due to previous download failure.")
        logger.info(f"--- Finished processing for URL: {url} ---\n")

if __name__ == '__main__':
    # This is a common fix for asyncio on Windows.
    # If you are on Linux/macOS, this line is not strictly necessary but harmless.
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
