#!/usr/bin/env python3
"""
Scrape syzkaller.appspot.com to obtain publicly available artifacts
"""

import argparse
import logging
import sys
import os
from typing import List, Optional, Tuple

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

def create_output_directory(dir_name: str) -> str:
    """
    Create output directory and return its path
    """
    output_path = f'./output/{dir_name}'
    os.makedirs(output_path, exist_ok=True)
    return output_path

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
            if is_binary:
                fout.write(content)
            else:
                fout.write(content.decode('utf-8'))
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

def download_assets(url: str) -> bool:
    """
    Download all assets from a given URL
    """
    resp = fetch_url(url)
    if resp is None:
        return False

    soup = BeautifulSoup(resp.text, "html.parser")
    if soup.title is None:
        return False


    release_dir = url.split("/")[-1]
    dir_name = sanitize_directory_name(soup.title.text)
    output_dir = create_output_directory(release_dir + "/" + dir_name)
    asset_links = extract_asset_links(soup)

    for link in asset_links:
        if not download_single_asset(link, output_dir):
            return False
            
    return True

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

    args = argparse.ArgumentParser()
    args.add_argument("--release", type=str, default="upstream", choices=["upstream", "lts-5.15", "lts-6.1"])
    args.add_argument("--output", type=str, default="output")

    parser = args.parse_args()

    if parser.release == "upstream":
        release_url = UPSTREAM
    elif parser.release == "lts-5.15":
        release_url = LTS_5_15
    elif parser.release == "lts-6.1":
        release_url = LTS_6_1
    else:
        logging.critical(f"Invalid release: {release_url}")
        sys.exit(1)

    raw_html = fetch_url(release_url)
    if raw_html is None:
        logging.critical(f"Could not fetch syzbot upstream url {parser.release}")
        sys.exit(1)
    soup = BeautifulSoup(raw_html.text, 'html.parser')
    

    # Download assets from main page
    if not download_assets(release_url):
        logging.warning("Failed to download some assets from main page")

    # Extract and process bug links
    _, bug_links = extract_bug_links(soup)
    
    # Download assets from each bug page
    for url in bug_links:
        if not download_assets(url):
            logging.warning(f"Failed to download some assets from {url}")

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
