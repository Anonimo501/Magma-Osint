# Magma-Osint (Enhanced)

**Search for information about a person using their name or nickname**  
*Original version by LimerBoy, enhanced with concurrency, proxy support, and output formats.*

[![YouTube Channel](https://img.shields.io/badge/YouTube-Anonimo501-red)](https://youtube.com/c/Anonimo501)
[![Telegram Group](https://img.shields.io/badge/Telegram-Pen7esting-blue)](https://t.me/Pen7esting)

![Screenshot_1](https://user-images.githubusercontent.com/67207446/151026681-5fdb670b-3b73-4e9c-a925-5a150be1bde5.png)

## Description

This OSINT script combines search results from **DuckDuckGo** and **Bing**, then analyzes each page to extract relevant links.  
The original version was created by [LimerBoy](https://github.com/LimerBoy) and later shared by **Anonimo501**.  
This enhanced version adds:

- ✅ **Command‑line arguments** for full customization.
- ✅ **Concurrent page analysis** (much faster).
- ✅ **Proxy support** (HTTP/HTTPS).
- ✅ **Save results** as JSON or CSV.
- ✅ **Real pagination** in both search engines (get more results).
- ✅ **Random User‑Agent rotation** to avoid blocking.
- ✅ **Better URL deduplication**.
- ✅ **Graceful Ctrl+C handling**.

## Installation

```bash
git clone https://github.com/Anonimo501/Magma-Osint.git
cd Magma-Osint
pip install -r requirements.txt
```

### Requirements (requirements.txt)

```
requests
beautifulsoup4
colorama
fuzzywuzzy
duckduckgo-search  # optional, improves DuckDuckGo results
```

> **Note:** If `duckduckgo-search` is not installed, the script automatically falls back to scraping.

## Usage

### Interactive mode (original style)
```bash
python3 osint_ddg_bing.py
```
You will be prompted for a query, and the search will start with default settings (50 results, 5 threads).

### Advanced mode (command line)
```bash
python3 osint_ddg_bing.py "John Doe" -m 100 -t 8 -o results.json --proxy http://127.0.0.1:8080
```

#### Available arguments
| Argument            | Description |
|---------------------|-------------|
| `query`             | Search query (if not provided, you'll be prompted). |
| `-m, --max-results` | Maximum number of URLs to collect (default: 50). |
| `-t, --threads`     | Concurrent threads for page analysis (default: 5). |
| `-o, --output`      | Output file (`.json` or `.csv`). |
| `--proxy`           | HTTP/HTTPS proxy (e.g., `http://127.0.0.1:8080`). |
| `--no-color`        | Disable colored output (useful for logging). |

### Examples

1. **Basic search with JSON output**
   ```bash
   python3 osint_ddg_bing.py "company Ltd." -m 30 -o company.json
   ```

2. **Use a proxy and 10 threads**
   ```bash
   python3 osint_ddg_bing.py "nickname" -t 10 --proxy socks5://localhost:9050
   ```

3. **Only DuckDuckGo** (if you prefer, you can comment out the Bing part in the code)

## Technical Features

- **DuckDuckGo**: uses the `duckduckgo-search` library if installed; otherwise scrapes `html.duckduckgo.com`.
- **Bing**: scrapes `www.bing.com` with pagination (`first` parameter).
- **Page analysis**: extracts the title and looks for links whose text or URL contain the query, or have a fuzzy similarity ≥60% (fuzzywuzzy).
- **Persistence**: HTTP session with retries and rotating user agents.
- **Structured output**: JSON with details of each page and relevant links found; CSV with summary.

## Credits

- **Original creator**: [LimerBoy](https://github.com/LimerBoy)
- **Sharing and enhancements**: [Anonimo501](https://github.com/Anonimo501)
- **Additional improvements**: *OSINT community*

## Legal Notice

This tool is intended for educational and security research purposes only. Misuse of the information obtained may violate local laws. Use it responsibly.

---

**Questions or suggestions?** Join the [Telegram group](https://t.me/Pen7esting) or the [YouTube channel](https://youtube.com/c/Anonimo501).
