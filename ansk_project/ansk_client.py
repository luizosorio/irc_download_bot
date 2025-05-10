#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import sys
import os
import requests
from bs4 import BeautifulSoup
import time
import re
import json
import logging
from datetime import datetime
from pathlib import Path
import hashlib

# Server configuration
SERVER = os.getenv('SERVER_HOST', 'xdcc_download_server')
PORT = int(os.getenv('SERVER_PORT', 8080))
DATA_DIR = os.getenv('DATA_DIR', '/data')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Logging configuration
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('xdcc_client')

# Compiled regular expressions for better performance
HASH_PATTERN = re.compile(r'((?<=\()|(?<=\[))(\S{8})((?=\))|(?=\]))|\S+\.rar')
HASH_PATTERN_FILE = re.compile(r'((?<=\()|(?<=\[))(\S{8})((?=\)\.)|(?=\]\.))|\S+\.rar')


def clear_string_file(filename):
    """Remove specific strings from filenames"""
    to_remove = {
        "[AnimeNSK]": "",
        "[_AnimeNSK]": "",
        "[#AnimeNSK]": "",
        "[XvidRC4]": ""
    }

    try:
        for key, value in to_remove.items():
            filename = filename.replace(key, value)
        return filename
    except Exception as e:
        logger.warning(f"Error cleaning filename: {e}")
        return filename


def fetch_webpage(url, retries=3, timeout=10):
    """Fetch a webpage with error handling and retries"""
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.warning(f"Attempt {attempt + 1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(2)  # Wait before retrying
            else:
                logger.error(f"Failed to access {url}: {e}")
                raise
    return None


def find_new_downloads(bot):
    """Find the most recent downloads available for a bot"""
    try:
        url = f"https://packs.ansktracker.net/?Modo=Packs&bot={bot}"
        page = fetch_webpage(url)
        soup = BeautifulSoup(page.content, "html.parser")
        results = soup.find(id="menu2")
        if not results:
            logger.error(f"Could not find 'menu2' section on the page for bot {bot}")
            return 0

        job_elements = results.find_all("tr", class_="L1")
        files_list = []

        for job_element in job_elements:
            line = job_element.find_all("td")
            if line and len(line) > 0:
                try:
                    files_list.append(int(line[0].text.strip("#")))
                except (ValueError, IndexError) as e:
                    logger.warning(f"Error processing line: {e}")

        return max(files_list) if files_list else 0
    except Exception as e:
        logger.error(f"Error finding new downloads for {bot}: {e}")
        return 0


def find_miss_download(bot):
    """Find missing downloads for a bot"""
    try:
        url = f"https://packs.ansktracker.net/?Modo=Packs&bot={bot}"
        page = fetch_webpage(url)
        soup = BeautifulSoup(page.content, "html.parser")
        results = soup.find(id="menu2")
        if not results:
            logger.error(f"Could not find 'menu2' section on the page for bot {bot}")
            return []

        job_elements = results.find_all("tr", class_="L1")
        files_list = []
        files_indir = files_in_dir(bot)

        for job_element in job_elements:
            line = job_element.find_all("td")
            if len(line) >= 5:  # Make sure there are enough elements
                try:
                    pack_id = int(line[0].text.strip("#"))
                    file_name = str(line[4].text if hasattr(line[4], 'text') else line[4])
                    file_name_cleaned = clear_string_file(file_name)

                    match = HASH_PATTERN.search(file_name_cleaned)
                    if match:
                        file_hash = match.group().upper()
                        if file_hash not in files_indir:
                            logger.info(f"Missing file: {bot} - {file_name}")
                            files_list.append((pack_id, match))
                    else:
                        logger.warning(f"No hash found for: {file_name}")
                        files_list.append((pack_id, None))
                except Exception as e:
                    logger.warning(f"Error processing line: {e}")

        return files_list
    except Exception as e:
        logger.error(f"Error finding missing downloads for {bot}: {e}")
        return []


def files_in_dir(bot):
    """Returns a list of file hashes in the bot's directory"""
    try:
        bot_dir = Path(f"{DATA_DIR}/{bot}")
        if not bot_dir.exists():
            logger.warning(f"Directory {bot_dir} does not exist. Creating...")
            bot_dir.mkdir(parents=True, exist_ok=True)
            return []

        files_list = []
        for file_path in bot_dir.glob('*'):
            if file_path.is_file() and not file_path.name == 'log.txt':
                file_name = clear_string_file(file_path.name)
                match = HASH_PATTERN_FILE.search(file_name)
                if match:
                    files_list.append(match.group().upper())

        return files_list
    except Exception as e:
        logger.error(f"Error listing files in {bot}: {e}")
        return []


def last_downloaded(bot):
    """Returns the ID of the last file downloaded for a bot"""
    try:
        log_file = Path(f"{DATA_DIR}/{bot}/log.txt")

        # Make sure the directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)

        if not log_file.exists():
            logger.warning(f"Log file not found for {bot}. Returning 0.")
            return 0

        with log_file.open('r') as f:
            for line in f:
                try:
                    return int(line.strip())
                except ValueError as err:
                    logger.warning(f'Error reading log: {err}')

        return 0
    except Exception as e:
        logger.error(f"Error reading last download for {bot}: {e}")
        return 0


def write_log_file(bot, log_id):
    """Writes the ID of the last downloaded file to the log"""
    try:
        log_file = Path(f"{DATA_DIR}/{bot}/log.txt")

        # Make sure the directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)

        with log_file.open('w') as f:
            f.write(f"{log_id}")
        logger.info(f'Log updated for {bot}: {log_id}')
    except Exception as e:
        logger.error(f"Error writing log for {bot}: {e}")


def xdcc_download(bot, file_id_list, w_log=True):
    """
    Request XDCC downloads using the new API.

    Args:
        bot: XDCC bot name
        file_id_list: List of file IDs to download
        w_log: Whether to update the log file after download

    Returns:
        bool: True if successful, False otherwise
    """
    if not isinstance(file_id_list, list) or not file_id_list:
        logger.warning("Empty or invalid ID list")
        return False

    # Convert all IDs to strings
    file_id_list = [str(fid) for fid in file_id_list]
    logger.info(f"Starting downloads from bot {bot}, packages: {file_id_list}")

    # Extract bot name for creating the download path
    bot_name = bot.split("|")[1] if "|" in bot else bot
    custom_path = f"{bot_name}"  # Path relative to DATA_DIR

    for pack_id in file_id_list:
        try:
            # Create a new connection for each download
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)  # Timeout for initial connection

            logger.info(f'Connecting to {SERVER}:{PORT}')
            sock.connect((SERVER, PORT))

            # Prepare request in the new format, including custom path
            request = {
                "bot_name": bot,
                "pack_number": pack_id,
                "send_progress": True,
                "download_path": custom_path
            }

            request_json = json.dumps(request)
            logger.info(f'Sending request: {request_json}')

            sock.sendall(request_json.encode('utf-8'))

            # Receive and process responses
            buffer = b""
            start_time = time.time()
            last_activity = time.time()
            download_completed = False
            last_progress = 0

            while True:
                try:
                    # Use a longer timeout for downloads
                    sock.settimeout(300)  # 5 minutes

                    # Receive data
                    chunk = sock.recv(4096)
                    if not chunk:
                        # Connection closed by server
                        logger.info("Server closed the connection")
                        if last_progress > 90:
                            logger.info(f"Download likely completed (progress: {last_progress}%)")
                            download_completed = True
                        break

                    # Update activity time
                    last_activity = time.time()
                    buffer += chunk

                    # Process buffer to find complete JSON messages
                    while True:
                        try:
                            # Find start and end of JSON object
                            start = buffer.find(b"{")
                            if start == -1:
                                break

                            end = buffer.find(b"}", start)
                            if end == -1:
                                break

                            # Extract and process JSON
                            json_data = buffer[start:end + 1]
                            response = json.loads(json_data)

                            # Remove processed data from buffer
                            buffer = buffer[end + 1:]

                            # Handle response based on status
                            status = response.get("status", "unknown")

                            if status == "downloading":
                                logger.info(f"Download started: {response.get('message', '')}")

                            elif status == "progress":
                                progress = response.get("progress", 0)
                                filename = response.get("filename", "unknown")
                                received = response.get("received", 0)
                                total = response.get("total", 0)

                                last_progress = progress

                                # Log progress less frequently
                                if progress % 10 == 0 or progress == 100:
                                    elapsed = time.time() - start_time
                                    speed = received / elapsed if elapsed > 0 else 0
                                    logger.info(
                                        f"Progress: {progress}% | {format_size(received)}/{format_size(total)} | {format_size(speed)}/s")

                            elif status == "success":
                                logger.info(f"Download complete: {response.get('filename', 'unknown')}")
                                logger.info(f"Size: {format_size(response.get('size', 0))}")
                                logger.info(f"Saved to: {response.get('path', 'unknown')}")
                                download_completed = True
                                break

                            elif status == "error":
                                logger.error(f"Download error: {response.get('message', 'Unknown error')}")
                                break

                        except json.JSONDecodeError:
                            # Incomplete JSON, wait for more data
                            break

                        except Exception as e:
                            logger.error(f"Error processing response: {e}")
                            break

                    # Check timeout
                    if time.time() - last_activity > 300:  # 5 minutes without activity
                        logger.warning(f"Timeout after {last_progress}% progress")
                        if last_progress > 90:
                            download_completed = True
                        break

                except socket.timeout:
                    logger.warning("Socket read timeout")
                    # Check if it's been a long time since last activity
                    if time.time() - last_activity > 300:
                        logger.warning("No activity for too long, closing connection")
                        break
                    continue

                except Exception as e:
                    logger.error(f"Connection error: {e}")
                    break

            # Close socket
            try:
                sock.close()
            except:
                pass

            # Update log if download was successful
            if download_completed and w_log:
                write_log_file(bot_name, pack_id)
                logger.info(f"Log updated for {bot_name}: {pack_id}")

            # Wait a bit before starting the next download
            if download_completed:
                logger.info("Waiting 10 seconds before next download...")
                time.sleep(10)

        except Exception as e:
            logger.error(f"Error processing download {pack_id} from bot {bot}: {e}")
            return False

    return True


def format_size(bytes_size):
    """Format size in bytes to human-readable format"""
    if not isinstance(bytes_size, (int, float)):
        return "0 B"

    bytes_size = float(bytes_size)
    if bytes_size < 1024:
        return f"{bytes_size:.2f} B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.2f} KB"
    elif bytes_size < 1024 * 1024 * 1024:
        return f"{bytes_size / (1024 * 1024):.2f} MB"
    else:
        return f"{bytes_size / (1024 * 1024 * 1024):.2f} GB"


def main():
    """Main function"""
    logger.info("Starting XDCC client")

    # Check environment for specific download
    e_id = os.getenv('IDS')
    e_bot = os.environ.get('BOT')

    if e_id and e_bot:
        logger.info(f'Specific download requested: {e_bot} - {e_id}')
        file_ids = e_id.split(",")
        xdcc_download(e_bot, file_ids, False)
    else:
        # List of bots to check
        bot_list = [
            "ANSK|Laura",
            "ANSK|Kuroneko",
            "ANSK|Victorique",
            "ANSK|Sora",
            "ANSK|Kobato"
        ]

        for bot in bot_list:
            try:
                bot_name = bot.split("|")[1]

                # Ensure bot directory exists
                bot_dir = Path(f"{DATA_DIR}/{bot_name}")
                bot_dir.mkdir(parents=True, exist_ok=True)

                # Find the latest available download
                log_pos = find_new_downloads(bot_name)
                logger.info(f'ANSK - Updated files: {bot} - {log_pos}')

                # Increment to include the next file
                next_pos = log_pos + 1 if log_pos > 0 else 0

                # Find the last downloaded file
                last_down_pos = last_downloaded(bot_name)
                logger.info(f'Last downloaded file: {bot} - {last_down_pos}')

                # Create list of pending downloads
                to_download = list(range(last_down_pos, next_pos))

                # Filter to remove invalid IDs
                to_download = [i for i in to_download if i > 0]

                logger.info(f'Files to download: {bot} - {to_download}')

                # Start downloads if there are pending files
                if len(to_download) > 0:
                    xdcc_download(bot, to_download, True)

                # Check for missed downloads
                logger.info(f'=== Checking missed downloads - BOT: {bot} ===')
                missed_list = find_miss_download(bot_name)

                if missed_list:
                    missed_ids = [str(missed_id[0]) for missed_id in missed_list]
                    logger.info(f'Missed downloads found: {missed_ids}')
                    xdcc_download(bot, missed_ids, False)
                else:
                    logger.info('No missed downloads found')

            except Exception as e:
                logger.error(f"Error processing bot {bot}: {e}")

    logger.info("XDCC client finished")


if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        sys.exit(1)