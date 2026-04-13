"""Base scraper class with common functionality."""
import requests
from bs4 import BeautifulSoup
import time
import logging
import random
from datetime import datetime
from typing import List, Dict, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class BaseScraper:
    """Base class for all real estate scrapers."""

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }

    def __init__(self, site_name: str):
        self.site_name = site_name
        self.logger = logging.getLogger(site_name)
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.request_count = 0
        self.max_requests_per_session = 200
        self.min_delay = 2.0
        self.max_delay = 4.0

    def _wait(self):
        """Wait between requests to be polite."""
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)

    def _fetch_page(self, url: str, retry_count: int = 3) -> Optional[BeautifulSoup]:
        """Fetch a page and return BeautifulSoup object."""
        if self.request_count >= self.max_requests_per_session:
            self.logger.warning("Maximum request limit reached for this session.")
            return None

        for attempt in range(retry_count):
            try:
                self._wait()
                self.logger.info(f"Fetching: {url} (attempt {attempt + 1})")
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                self.request_count += 1

                # Detect encoding
                if response.encoding and response.encoding.lower() != 'utf-8':
                    response.encoding = response.apparent_encoding

                return BeautifulSoup(response.text, 'lxml')

            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request error (attempt {attempt + 1}): {e}")
                if attempt < retry_count - 1:
                    time.sleep(5 * (attempt + 1))
                else:
                    self.logger.error(f"Failed to fetch {url} after {retry_count} attempts")
                    return None

    def scrape(self, conditions: Dict) -> List[Dict]:
        """Override in subclass. Scrape properties matching conditions."""
        raise NotImplementedError

    def _parse_price(self, text: str) -> Optional[float]:
        """Parse Japanese price text to float (in 万円)."""
        if not text:
            return None
        import re
        text = text.strip().replace(',', '').replace('　', '')
        # Match patterns like "6.9万円" or "69000円"
        match = re.search(r'([\d.]+)\s*万円', text)
        if match:
            return float(match.group(1))
        match = re.search(r'([\d,]+)\s*円', text)
        if match:
            return float(match.group(1).replace(',', '')) / 10000
        return None

    def _parse_area(self, text: str) -> Optional[float]:
        """Parse area text to float (in m²)."""
        if not text:
            return None
        import re
        text = text.strip()
        match = re.search(r'([\d.]+)\s*m', text)
        if match:
            return float(match.group(1))
        return None

    def _parse_age(self, text: str) -> Optional[int]:
        """Parse building age text to int (years)."""
        if not text:
            return None
        import re
        text = text.strip()
        if '新築' in text:
            return 0
        match = re.search(r'築?(\d+)\s*年', text)
        if match:
            return int(match.group(1))
        return None

    def _parse_walk_minutes(self, text: str) -> Optional[int]:
        """Parse walk minutes from transport text."""
        if not text:
            return None
        import re
        match = re.search(r'歩\s*(\d+)\s*分', text)
        if match:
            return int(match.group(1))
        match = re.search(r'徒歩\s*(\d+)\s*分', text)
        if match:
            return int(match.group(1))
        return None

    def _normalize_address(self, address: str) -> str:
        """Normalize address for dedup purposes."""
        if not address:
            return ""
        import re
        # Full-width to half-width numbers
        table = str.maketrans('０１２３４５６７８９', '0123456789')
        address = address.translate(table)
        # Remove spaces
        address = re.sub(r'\s+', '', address)
        return address
