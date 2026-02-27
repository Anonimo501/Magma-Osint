#!/usr/bin/env python3
# coding: utf-8
"""
OSINT Search Tool - DuckDuckGo + Bing with concurrent page analysis
Author: LimerBoy (original), expanded by ...
"""

import argparse
import concurrent.futures
import csv
import json
import logging
import random
import sys
import time
from urllib.parse import urljoin, urlparse, unquote

import requests
from bs4 import BeautifulSoup
from colorama import Back, Fore, Style, init
from fuzzywuzzy import fuzz

# Optional DuckDuckGo library
try:
    from duckduckgo_search import ddg
    DDG_LIB_AVAILABLE = True
except ImportError:
    DDG_LIB_AVAILABLE = False

# Initialize colorama
init(autoreset=True)

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
DEFAULT_MAX_RESULTS = 50
DEFAULT_THREADS = 5
REQUEST_TIMEOUT = 10
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0'
]

# ----------------------------------------------------------------------
# Logging setup
# ----------------------------------------------------------------------
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Utility functions
# ----------------------------------------------------------------------
def normalize_href(href, base=None):
    """Normalize href to absolute URL; filter out non‑http links."""
    if not href:
        return None
    href = href.strip()
    if href.startswith(('javascript:', 'mailto:', 'tel:', '#', 'data:')):
        return None
    if href.startswith('//'):
        return 'https:' + href
    if base and not href.startswith(('http://', 'https://')):
        try:
            return urljoin(base, href)
        except Exception:
            return None
    return href if href.startswith(('http://', 'https://')) else None

def get_session(proxy=None):
    """Create a requests Session with a random User‑Agent and optional proxy."""
    session = requests.Session()
    session.headers.update({'User-Agent': random.choice(USER_AGENTS)})
    if proxy:
        session.proxies.update({'http': proxy, 'https': proxy})
    # Retry adapter for transient errors
    adapter = requests.adapters.HTTPAdapter(max_retries=3)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# ----------------------------------------------------------------------
# Search engine functions (generators)
# ----------------------------------------------------------------------
def duckduckgo_results(session, query, max_results):
    """
    Yield URLs from DuckDuckGo.
    Uses the duckduckgo_search library if available, otherwise scrapes HTML.
    Attempts to get more results via pagination.
    """
    count = 0
    if DDG_LIB_AVAILABLE:
        try:
            results = ddg(query, max_results=max_results)
            for r in results:
                if count >= max_results:
                    break
                url = r.get('href') or r.get('link') or r.get('url')
                if url:
                    yield unquote(url)
                    count += 1
            return
        except Exception as e:
            log.warning(f"DuckDuckGo library failed, falling back to scraping: {e}")

    # Fallback scraping (may return fewer than max_results)
    params = {'q': query}
    pages = (max_results // 30) + 1  # typical results per page
    for page in range(pages):
        if count >= max_results:
            break
        params['s'] = page * 30  # offset parameter
        try:
            resp = session.get('https://html.duckduckgo.com/html/', params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            # DuckDuckGo uses class 'result__a' for links
            for a in soup.select('a.result__a'):
                if count >= max_results:
                    break
                href = normalize_href(a.get('href'), base='https://duckduckgo.com')
                if href:
                    yield href
                    count += 1
            # If no results on this page, stop
            if not soup.select('a.result__a'):
                break
        except Exception as e:
            log.error(f"DuckDuckGo scraping error: {e}")
            break

def bing_results(session, query, max_results):
    """Yield URLs from Bing scraping (simple pagination)."""
    count = 0
    # Bing uses 'first' parameter for pagination (first=1, first=11, ...)
    for first in range(1, max_results, 10):
        if count >= max_results:
            break
        params = {'q': query, 'first': first, 'count': 10}
        try:
            resp = session.get('https://www.bing.com/search', params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            for a in soup.select('li.b_algo h2 a'):
                if count >= max_results:
                    break
                href = normalize_href(a.get('href'))
                if href:
                    yield href
                    count += 1
        except Exception as e:
            log.error(f"Bing scraping error: {e}")
            break

# ----------------------------------------------------------------------
# Page analysis
# ----------------------------------------------------------------------
def analyze_page(session, url, query, results_list):
    """
    Download a page and extract relevant links.
    Returns a dictionary with page info and detected links.
    """
    log.info(Fore.CYAN + f"Analyzing: {url}")
    page_data = {
        'url': url,
        'title': None,
        'links_found': []
    }
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except Exception as e:
        log.error(Fore.RED + f"   Fetch error for {url}: {e}")
        return page_data  # title remains None

    soup = BeautifulSoup(resp.text, 'html.parser')
    try:
        title = soup.title.string.strip() if soup.title else ''
        page_data['title'] = title
        log.info(Fore.MAGENTA + f"[?] Title: {title}")
    except Exception:
        log.warning(Fore.RED + "[?] Title: null")

    # Scan all links on the page
    for link in soup.find_all('a', href=True):
        href = normalize_href(link.get('href'), base=url)
        if not href or href in page_data['links_found']:
            continue

        link_text = (link.get_text() or '').strip()
        # Check relevance: query in URL, query in text, or high similarity between text and query
        relevant = False
        reason = ""
        if query.lower() in href.lower():
            relevant = True
            reason = "query in URL"
        elif query.lower() in link_text.lower():
            relevant = True
            reason = "query in link text"
        elif fuzz.partial_ratio(query.lower(), link_text.lower()) >= 60:
            relevant = True
            reason = "fuzzy text match"

        if relevant:
            page_data['links_found'].append({
                'url': href,
                'text': link_text,
                'reason': reason
            })
            log.info(Fore.GREEN + f"--- Relevant link: {href} ({reason})")

    results_list.append(page_data)
    return page_data

# ----------------------------------------------------------------------
# Main orchestration
# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description='OSINT search across DuckDuckGo and Bing')
    parser.add_argument('query', nargs='?', help='Search query (if not provided, will prompt)')
    parser.add_argument('-m', '--max-results', type=int, default=DEFAULT_MAX_RESULTS,
                        help=f'Maximum total URLs to fetch (default: {DEFAULT_MAX_RESULTS})')
    parser.add_argument('-t', '--threads', type=int, default=DEFAULT_THREADS,
                        help=f'Number of concurrent page analysis threads (default: {DEFAULT_THREADS})')
    parser.add_argument('-o', '--output', help='Output file (JSON or CSV, extension decides format)')
    parser.add_argument('--proxy', help='HTTP/HTTPS proxy (e.g., http://127.0.0.1:8080)')
    parser.add_argument('--no-color', action='store_true', help='Disable colored output')
    args = parser.parse_args()

    if args.no_color:
        init(strip=True)  # colorama without colours

    # Print logo
    logo = '''
  █▀▄▀█ █▀▀█ █▀▀▀ █▀▄▀█ █▀▀█   █▀▀█ █▀▀ ░▀░ █▀▀▄ ▀▀█▀▀
  █░▀░█ █▄▄█ █░▀█ █░▀░█ █▄▄█   █░░█ ▀▀█ ▀█▀ █░░█ ░░█░░
  ▀░░░▀ ▀░░▀ ▀▀▀▀ ▀░░░▀ ▀░░▀   ▀▀▀▀ ▀▀▀ ▀▀▀ ▀░░▀ ░░▀░░
                                   Created by LimerBoy
    '''
    print(Fore.YELLOW + logo)

    # Get query
    query = args.query
    if not query:
        query = input(Back.BLACK + Fore.YELLOW + 'Find > ' + Back.RESET + Fore.WHITE)
    log.info(Fore.GREEN + f'[~] Searching for: {query}')

    # Prepare session
    session = get_session(proxy=args.proxy)

    # Collect unique URLs from both engines
    all_urls = set()
    # DuckDuckGo
    log.info(Fore.CYAN + "[*] Fetching from DuckDuckGo...")
    for url in duckduckgo_results(session, query, args.max_results):
        if url not in all_urls:
            all_urls.add(url)
        if len(all_urls) >= args.max_results:
            break
    # Bing
    log.info(Fore.CYAN + "[*] Fetching from Bing...")
    for url in bing_results(session, query, args.max_results):
        if url not in all_urls:
            all_urls.add(url)
        if len(all_urls) >= args.max_results:
            break

    if not all_urls:
        log.warning(Fore.RED + "[!] No URLs found.")
        return

    log.info(Fore.GREEN + f"[+] Collected {len(all_urls)} unique URLs. Starting analysis...")

    # Analyze pages concurrently
    all_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as executor:
        future_to_url = {
            executor.submit(analyze_page, session, url, query, all_results): url
            for url in all_urls
        }
        # Optional: show progress as they complete
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                future.result()  # we already appended inside, but check for exceptions
            except Exception as e:
                log.error(Fore.RED + f"Error analyzing {url}: {e}")

    log.info(Fore.GREEN + f"[+] Analysis finished. Processed {len(all_results)} pages.")

    # Save results if output file specified
    if args.output:
        save_results(all_results, args.output)
        log.info(Fore.GREEN + f"[+] Results saved to {args.output}")

def save_results(data, filename):
    """Save results to JSON or CSV based on file extension."""
    if filename.endswith('.json'):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    elif filename.endswith('.csv'):
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['URL', 'Title', 'Relevant Links Count'])
            for item in data:
                writer.writerow([item['url'], item['title'] or '', len(item['links_found'])])
            # Optionally write a second sheet with all links? For simplicity, just summary.
    else:
        log.warning(f"Unsupported output format: {filename}. Use .json or .csv")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log.info(Fore.RED + "\n[!] Search interrupted by user (Ctrl+C).")
        sys.exit(0)
