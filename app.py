#!/usr/bin/env python3
"""
Scrape syzkaller.appspot.com to obtain publicly available artifacts
"""

import argparse
import logging
import sys
import os
import json
from datetime import datetime
from typing import List, Optional, Tuple
import time
from functools import wraps
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError as ie:
    print(f"Error importing {ie}")
    sys.exit(1)

BASE_URL = 'https://syzkaller.appspot.com'
UPSTREAM = 'https://syzkaller.appspot.com/upstream'
LTS_5_15 = 'https://syzkaller.appspot.com/linux-5.15'
LTS_6_1  = 'https://syzkaller.appspot.com/linux-6.1'

def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured logging"""
    class CustomJsonFormatter(logging.Formatter):
        def format(self, record):
            record_dict = {
                "timestamp": datetime.utcnow().isoformat(),
                "level": record.levelname,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
            }
            if hasattr(record, "extra_data"):
                record_dict.update(record.extra_data)
            return json.dumps(record_dict)

    handler = logging.StreamHandler()
    handler.setFormatter(CustomJsonFormatter())
    logging.root.handlers = []
    logging.root.addHandler(handler)
    logging.root.setLevel(getattr(logging, log_level.upper()))

def rate_limit(min_interval: float = 1.0):
    """Rate limiting decorator"""
    last_called = {}
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            key = func.__name__
            if key in last_called:
                elapsed = now - last_called[key]
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)
            result = func(*args, **kwargs)
            last_called[key] = time.time()
            return result
        return wrapper
    return decorator

@rate_limit(min_interval=2.0)  # Wait at least 2 seconds between requests
def fetch_url(url: str, timeout: int = 10) -> Optional[requests.Response]:
    """
    Fetch content from a URL with error handling
    """
    try:
        return requests.get(url, timeout=timeout)
    except requests.exceptions.ConnectTimeout:
        logging.critical(f"timeout issue connecting to {url}")
        return None
    except requests.exceptions.RequestException as e:
        logging.critical(f"Error fetching {url}: {e}")
        return None

def sanitize_directory_name(title: str) -> str:
    """
    Convert a title into a safe directory name
    """
    return title.replace(" ","_")\
               .replace("-","_")\
               .replace("/","_")\
               .replace(":","_")

def create_output_directory(dir_name: str, release: str) -> str:
    """
    Create output directory and return its path
    Args:
        dir_name: Name of the directory for the specific crash
        release: Release type (upstream, lts-5.15, lts-6.1)
    Returns:
        Path to the created directory
    """
    # Convert release name to directory format
    release_dir = release.replace("-", "_")
    output_path = Path('./output') / release_dir / dir_name
    output_path.mkdir(parents=True, exist_ok=True)
    return str(output_path)

def extract_asset_links(soup: BeautifulSoup) -> List[str]:
    """
    Extract all asset links from the page
    """
    asset_links = []
    
    # Find asset links in assets class
    for td in soup.find_all("td", class_="assets"):
        links = td.find_all("a", href=True)
        asset_links.extend(link["href"] for link in links)
    
    # Find repro links
    for td in soup.find_all("td", class_="repro"):
        links = td.find_all("a", href=True)
        asset_links.extend(BASE_URL + link["href"] for link in links)
    
    return asset_links

def save_asset(output_dir: str, name: str, content: bytes, is_binary: bool = False) -> bool:
    """
    Save an asset to disk
    """
    try:
        mode = "wb+" if is_binary else "w+"
        filepath = os.path.join(output_dir, name.split('/')[-1])
        with open(filepath, mode) as fout:
            logging.info(f"writing {name} to {output_dir}")
            if is_binary:
                fout.write(content)
            else:
                fout.write(content.decode('utf-8', errors="ignore"))
        return True
    except IOError as io:
        logging.error(f"Error creating file {filepath}: {io}")
        return False

def download_single_asset(url: str, output_dir: str) -> bool:
    """
    Download a single asset and save it
    """
    logging.info(f"Downloading {url}")
    name = url.split("tag=")[-1].split("&")[0]
    
    resp = fetch_url(url)
    if resp is None or resp.content is None:
        logging.error(f"Could not download asset from {url}")
        return False

    is_binary = ".raw" in name or ".tar.gz" in name
    return save_asset(output_dir, name, resp.content, is_binary)

def download_assets(url: str, release: str, is_main_page: bool = False) -> bool:
    """
    Download all assets from a given URL
    Args:
        url: The URL to download assets from
        release: Release type (upstream, lts-5.15, lts-6.1)
        is_main_page: Whether this is the main release page
    """
    resp = fetch_url(url)
    if resp is None:
        return False

    soup = BeautifulSoup(resp.text, "html.parser")
    if soup.title is None:
        return False

    if is_main_page:
        dir_name = "main_page"
    else:
        dir_name = sanitize_directory_name(soup.title.text)
    
    output_dir = create_output_directory(dir_name, release)
    asset_links = extract_asset_links(soup)
    
    if not asset_links:
        logging.warning(f"No assets found for {url}")
        return True  # Not a failure if there are no assets
        
    success_count = 0
    for link in asset_links:
        if download_single_asset(link, output_dir):
            success_count += 1
        else:
            logging.warning(f"Failed to download asset {link}")
            
    if success_count == 0 and asset_links:
        logging.error(f"Failed to download any assets from {url}")
        return False
            
    return True  # Return true if we downloaded at least some assets

def extract_bug_links(soup: BeautifulSoup) -> Tuple[List[str], List[str]]:
    """
    Extract bug links and their associated data from the main table
    """
    rows = []
    links = []
    
    table = soup.find_all("tbody")[1]
    for row in table.find_all("tr")[1:]:  # Skip header row
        cells = row.find_all("td")
        embedded_links = row.find("td", class_="title").find("a", href=True)
        link = embedded_links["href"]
        row_data = [cell.text for cell in cells]

        rows.append(" ".join(row_data).replace('\n',' '))
        links.append(f"{BASE_URL}{link}")
    
    return rows, links

def main():
    """
    Main execution function
    """
    
    try:
        args = argparse.ArgumentParser()
        args.add_argument("--release", type=str, default="upstream", choices=["upstream", "lts-5.15", "lts-6.1"])
        args.add_argument("--output", type=str, default="output")
        args.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
        
        parser = args.parse_args()
        
        setup_logging(parser.log_level)
        logging.info("Starting syzbot scraper", extra={"release": parser.release, "output_dir": parser.output})
        
        if parser.release == "upstream":
            release_url = UPSTREAM
        elif parser.release == "lts-5.15":
            release_url = LTS_5_15
        elif parser.release == "lts-6.1":
            release_url = LTS_6_1
        else:
            logging.critical(f"Invalid release: {parser.release}")
            sys.exit(1)

        raw_html = fetch_url(release_url)
        if raw_html is None:
            msg = f"Could not fetch syzbot url {parser.release}"
            logging.critical(msg)
            sys.exit(1)

        soup = BeautifulSoup(raw_html.text, 'html.parser')
        
        if not download_assets(release_url, parser.release, is_main_page=True):
            logging.critical(f"Could not download: {release_url}. Quitting")
            sys.exit(1)

        # Extract and process bug links
        _, bug_links = extract_bug_links(soup)
        
        failed_urls = []
        for url in bug_links:
            logging.info(f"Processing bug URL: {url}")
            if not download_assets(url, parser.release):
                logging.error(f"Failed to download assets from {url}")
                failed_urls.append(url)
        
        if failed_urls:
            logging.warning(f"Failed to process {len(failed_urls)} URLs: {failed_urls}")
        
    except Exception as e:
        logging.exception(f"Unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
