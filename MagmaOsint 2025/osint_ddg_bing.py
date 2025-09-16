#!/usr/bin/env python3
# coding: utf-8
"""
osint_ddg_bing.py
Búsqueda OSINT combinada: DuckDuckGo (librería o scraping) + Bing (scraping).
Maneja Ctrl+C para terminar limpio sin errores.
"""

import time
import sys
from requests import get
from bs4 import BeautifulSoup
from colorama import Fore, Back, Style, init
from fuzzywuzzy import fuzz
from urllib.parse import urlparse, urljoin, unquote

# Inicializar colorama
init(autoreset=True)

BASIC_LOGO = '''
  █▀▄▀█ █▀▀█ █▀▀▀ █▀▄▀█ █▀▀█   █▀▀█ █▀▀ ░▀░ █▀▀▄ ▀▀█▀▀
  █░▀░█ █▄▄█ █░▀█ █░▀░█ █▄▄█   █░░█ ▀▀█ ▀█▀ █░░█ ░░█░░
  ▀░░░▀ ▀░░▀ ▀▀▀▀ ▀░░░▀ ▀░░▀   ▀▀▀▀ ▀▀▀ ▀▀▀ ▀░░▀ ░░▀░░
                                   Created by LimerBoy
'''
print(Fore.YELLOW + BASIC_LOGO)

query = input(Back.BLACK + Fore.YELLOW + 'Find > ' + Back.RESET + Fore.WHITE)
MAX_RESULTS = 100
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36'
}
print(Fore.GREEN + '[~] Searching ' + query)


def normalize_href(href, base=None):
    """Normaliza hrefs: añade esquema si falta y resuelve URLs relativas."""
    if not href:
        return None
    href = href.strip()
    if href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
        return None
    if href.startswith('//'):
        return 'https:' + href
    if base and not href.startswith('http'):
        try:
            return urljoin(base, href)
        except Exception:
            return None
    return href


def duckduckgo_results(q, max_results=100):
    """Usa duckduckgo_search si está instalada, si no hace scraping."""
    try:
        from duckduckgo_search import ddg
        results = ddg(q, max_results=max_results)
        if results:
            for r in results:
                url = None
                if isinstance(r, dict):
                    url = r.get('href') or r.get('link') or r.get('url')
                else:
                    url = r
                if url:
                    yield unquote(url)
            return
    except Exception:
        pass

    # fallback scraping
    try:
        resp = get('https://html.duckduckgo.com/html/', params={'q': q}, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        anchors = soup.select('a.result__a') or soup.select('a')
        count = 0
        for a in anchors:
            if count >= max_results:
                break
            href = normalize_href(a.get('href'), base='https://duckduckgo.com')
            if href:
                yield href
                count += 1
    except Exception:
        return


def bing_results(q, max_results=50):
    """Scraping simple de Bing."""
    try:
        resp = get('https://www.bing.com/search', params={'q': q, 'count': max_results}, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select('li.b_algo h2 a')
        count = 0
        seen = set()
        for a in items:
            if count >= max_results:
                break
            href = normalize_href(a.get('href'), base='https://www.bing.com')
            if href and href not in seen:
                seen.add(href)
                yield href
                count += 1
    except Exception:
        return


def analyze_page(url, query):
    """Descarga la página y analiza <a> buscando enlaces relevantes."""
    print('\n' + Fore.CYAN + '[+] Url detected: ' + url)
    try:
        page = get(url, headers=HEADERS, timeout=8)
        text = page.text
    except Exception as e:
        print(Fore.RED + f'   (fetch error: {e})')
        return

    soup = BeautifulSoup(text, "html.parser")
    try:
        title = soup.title.text.replace('\n', '').strip()
        print(Fore.MAGENTA + '[?] Title: ' + title)
    except Exception:
        print(Fore.RED + '[?] Title: null')

    links_detected = []
    for link in soup.find_all('a'):
        href = normalize_href(link.get('href'), base=url)
        if not href or not href.startswith('http') or href in links_detected:
            continue
        try:
            if urlparse(url).netloc and urlparse(url).netloc in href:
                links_detected.append(href)
            elif query.lower() in href.lower():
                print(Fore.GREEN + '--- Requested data found at link : ' + href)
                links_detected.append(href)
            elif fuzz.ratio((link.text or '').strip(), href) >= 60:
                print(Fore.GREEN + '--- Text and link are similar : ' + href)
                links_detected.append(href)
        except Exception:
            continue

    if not links_detected:
        print(Fore.RED + '--- No data found')


# ==============================
# Main con manejo de Ctrl+C
# ==============================
try:
    # DuckDuckGo
    count = 0
    for url in duckduckgo_results(query, MAX_RESULTS):
        url = normalize_href(url, base='https://duckduckgo.com') or url
        analyze_page(url, query)
        count += 1
        time.sleep(0.6)
        if count >= MAX_RESULTS:
            break

    # Bing
    print('\n' + Fore.YELLOW + '[~] Now searching Bing for additional results...')
    count = 0
    for url in bing_results(query, max_results=MAX_RESULTS):
        analyze_page(url, query)
        count += 1
        time.sleep(0.8)
        if count >= MAX_RESULTS:
            break

    print('\n' + Fore.GREEN + '[+] Search finished.')

except KeyboardInterrupt:
    print(Fore.RED + "\n[!] Búsqueda interrumpida por el usuario (Ctrl+C).")
    sys.exit(0)
