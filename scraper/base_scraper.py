"""Base scraper class with shared HTTP/parsing utilities."""
import requests
from bs4 import BeautifulSoup
import logging
import re
import time
from typing import Optional
from datetime import datetime


class BaseScraper:
    """Base class for all real estate site scrapers."""

    HEADERS = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        ),
        'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
    }

    def __init__(self, site_name: str):
        self.site_name = site_name
        self.logger = logging.getLogger(f'scraper.{site_name}')
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def _fetch_page(self, url: str, retry: int = 2) -> Optional[BeautifulSoup]:
        """Fetch page and return BeautifulSoup object."""
        for attempt in range(retry + 1):
            try:
                resp = self.session.get(url, timeout=15)
                resp.raise_for_status()
                resp.encoding = resp.apparent_encoding or 'utf-8'
                return BeautifulSoup(resp.text, 'html.parser')
            except Exception as e:
                self.logger.warning(f"Fetch error ({attempt+1}/{retry+1}): {url} - {e}")
                if attempt < retry:
                    time.sleep(2)
        return None

    def _parse_price(self, text: str) -> Optional[float]:
        """万円 to float (万円 unit)."""
        if not text:
            return None
        m = re.search(r'([\d,.]+)\s*万円', text)
        if m:
            return float(m.group(1).replace(',', ''))
        m = re.search(r'([\d,]+)\s*円', text)
        if m:
            return float(m.group(1).replace(',', '')) / 10000
        return None

    def _parse_price_yen(self, text: str) -> Optional[float]:
        """Parse purchase price: handles 億円 and 万円."""
        if not text:
            return None
        total = 0.0
        m_oku = re.search(r'([\d,.]+)\s*億', text)
        if m_oku:
            total += float(m_oku.group(1).replace(',', '')) * 10000
        m_man = re.search(r'([\d,.]+)\s*万', text)
        if m_man:
            total += float(m_man.group(1).replace(',', ''))
        if total > 0:
            return total
        return self._parse_price(text)

    def _parse_area(self, text: str) -> Optional[float]:
        """Parse area in m2."""
        if not text:
            return None
        m = re.search(r'([\d.]+)\s*m[²㎡]', text)
        if m:
            return float(m.group(1))
        return None

    def _parse_age(self, text: str) -> Optional[int]:
        """Parse building age from text like 築5年 or 新築."""
        if not text:
            return None
        if '新築' in text:
            return 0
        m = re.search(r'築(\d+)年', text)
        if m:
            return int(m.group(1))
        return None

    def _parse_walk_minutes(self, text: str) -> Optional[int]:
        """Parse walk minutes from text like 徒歩5分."""
        if not text:
            return None
        m = re.search(r'徒歩(\d+)分', text)
        if m:
            return int(m.group(1))
        return None

    def _normalize_address(self, text: str) -> str:
        """Normalize Japanese address."""
        if not text:
            return ''
        text = re.sub(r'\s+', '', text.strip())
        return text

    def _make_property_dict(self, **kwargs):
        """Create standardized property dict with all fields."""
        base = {
            'site': self.site_name,
            'listing_type': kwargs.get('listing_type', 'rental'),
            'building_name': '',
            'address': '',
            'transport': '',
            'rent': None,
            'price': None,
            'management_fee': None,
            'deposit': '',
            'key_money': '',
            'layout': '',
            'area': None,
            'land_area': None,
            'age': None,
            'age_text': '',
            'floor': '',
            'walk_minutes': None,
            'url': '',
            'published_date': '',
            'next_update_date': '',
            'nearest_school_distance': None,
            'city_planning': '',
            'zoning': '',
            'land_category': '',
            'scraped_at': datetime.now().isoformat(),
        }
        base.update(kwargs)
        return base
