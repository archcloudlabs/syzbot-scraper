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
UPSTREAM = "https://syzkaller.appspot.com/bug?extid=9f6d080dece587cfdd4c"

def get_syzbot_upstream():
    """
    Obtain syzbot entries on main page.
    return: string data to be parsed
    """
    try:
        resp = requests.get(UPSTREAM, timeout=10)
    except requests.exceptions.ConnectTimeout as timeout:
        logging.CRITICAL(f"timeout issue connecting to {UPSTREAM}")
        sys.exit(1)

    return resp

def download_assets(url):

    resp = requests.get(url, timeout=10)
    html_content = resp.text
    soup = BeautifulSoup(html_content, "html.parser")

    if soup.title is None:
        return

    dir_name = soup.title.text\
        .replace(" ","_")\
        .replace("-","_")\
        .replace("/","_")\
        .replace(":","_")

    os.makedirs(f'./output/{dir_name}', exist_ok=True)

    # Find all asset links inside <td class="assets">
    asset_links = []
    for td in soup.find_all("td", class_="assets"):
        links = td.find_all("a", href=True)
        for link in links:
            asset_links.append(link["href"])

    for td in soup.find_all("td", class_="repro"):
        links = td.find_all("a", href=True)
        for link in links:
            asset_links.append(BASE_URL + link["href"])

    for link in asset_links:
        logging.info(f"Download {link}")
        name = link.split("tag=")[-1].split("&")[0]
        resp = requests.get(link)
        if resp.text is None:
            print("[!] could not download assets")
            break

        if resp.text:
            print(f"[+] Downloading {name}")
            if ".raw" or ".tar.gz" in name:
                try:
                    with open(f"./output/{dir_name}/{name.split('/')[-1]}", "wb+") as fout:
                        fout.write(resp.content)
                except IOError as io:
                    print(f"[!] error, could not create file {dir_name}/{name}")
                    break
            else: # not .raw or .tar.gz file....
                try:
                    with open(f"./output/{dir_name}/{name}", "wb+") as fout:
                        fout.write(bytes(resp.text, encoding="utf-8"))
                except IOError as io:
                    print(f"[!] error, could not create file {dir_name}/{name}")
                    break
        else:
            logging.critical(f"could not download {link}")
            pass

if __name__ == '__main__':
    raw_html = get_syzbot_upstream()
    if raw_html is None:
        print(f"[!] could not fetch syzbot upstream url {UPSTREAM}")
        sys.exiit(1)

    soup = BeautifulSoup(raw_html.text, 'html.parser')
    rows = []
    links = []

    download_assets(UPSTREAM)

    table = soup.find_all("tbody")[1]
    for row in table.find_all("tr")[1:]:  # Skip header row
        cells = row.find_all("td")
        embedded_links = row.find("td", class_="title").find("a", href=True)
        link = embedded_links["href"]
        row_data = [cell.text for cell in cells]

        rows.append(" ".join(row_data).replace('\n',' '))
        links.append(f"{BASE_URL}{link}")

    # links list now has bug links
    [download_assets(_url) for _url in links]
