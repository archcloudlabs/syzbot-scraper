#!/usr/bin/env python3
"""
Scrape syzkaller.appspot.com to obtain publicly available artifacts
"""

import argparse
import logging
import sys
import os

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError as ie:
    print(f"Error importing {ie}")
    sys.exit(1)

BASE_URL = 'https://syzkaller.appspot.com'
UPSTREAM = 'https://syzkaller.appspot.com/upstream'


def get_syzbot_upstream():
    """
    """
    try:
        resp = requests.get(UPSTREAM, timeout=10)
        return resp
    except:
        logging.critical("failed to obtain upstream URL")
        sys.exit(1)

def download_assets(url):
    resp = requests.get(url, timeout=10)
    html_content = resp.text
    soup = BeautifulSoup(html_content, "html.parser")

    dir_name = soup.title.text.replace(" ","_").replace("-","_")
    os.mkdir(f'./output/{dir_name}')

    # Find all asset links inside <td class="assets">
    asset_links = []
    for td in soup.find_all("td", class_="assets"):
        links = td.find_all("a", href=True)
        for link in links:
            asset_links.append(link["href"])

    for link in asset_links:
        print(link)

if __name__ == '__main__':
    raw_html = get_syzbot_upstream()
    soup = BeautifulSoup(raw_html.text, 'html.parser')
    rows = []
    links = []

    table = soup.find_all("tbody")[1]
    for row in table.find_all("tr")[1:]:  # Skip header row
        cells = row.find_all("td")
        embedded_links = row.find("td", class_="title").find("a", href=True)
        link = embedded_links["href"]
        #row_data = [cell.text for cell in cells]
        #rows.append(" ".join(row_data).replace('\n',' '))
        links.append(f"{BASE_URL}{link}")

    # links list now has bug links
    [download_assets(_url) for _url in links]
