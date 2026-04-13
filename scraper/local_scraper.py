"""
Local Aso-area real estate company scraper supporting rental and purchase modes.
"""

import re
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import requests
from datetime import datetime

from .base_scraper import BaseScraper


LOCAL_COMPANIES = {
    'ハイトスコーポレーション': {
        'name': 'ハイトスコーポレーション',
        'url': 'https://www.hights.co.jp',
        'search_url': 'https://www.hights.co.jp/rent/list/',
        'buy_url': 'https://www.hights.co.jp/buy/list/',
        'area': '阿蘇市',
        'description': '阿蘇地域を中心とした不動産会社',
    },
    'アパマンショップ光の森店': {
        'name': 'アパマンショップ光の森店',
        'url': 'https://www.apamanshop.com',
        'search_url': 'https://www.apamanshop.com/ensen/03610/area/',
        'buy_url': 'https://www.apamanshop.com/sell/area/kumamoto/',
        'area': '熊本県全般',
        'description': '全国チェーン（熊本エリア）',
    },
    '大東建託リーシング熊本中央店': {
        'name': '大東建託リーシング',
        'url': 'https://www.eheya.net',
        'search_url': 'https://www.eheya.net/kumamoto/',
        'buy_url': 'https://www.eheya.net/kumamoto/buy/',
        'area': '犹礬県全域',
        'description': 'DK SELECT（大東建託）の賃貸物件',
    },
    '明和不動産': {
        'name': '明和不動産',
        'url': 'https://www.meiwa-fudosan.co.jp',
        'search_url': 'https://www.meiwa-fudosan.co.jp/rent/',
        'buy_url': 'https://www.meiwa-fudosan.co.jp/buy/',
        'area': '熊本県全域',
        'description': '熊本県を中心とした地域密着型不動産会社',
    },
}


class LocalScraper(BaseScraper):
    """Scraper for local Kumamoto/Aso-area real estate companies."""

    def __init__(self, company_key: str):
        """
        Initialize the scraper with a company key.

        Args:
            company_key: Key from LOCAL_COMPANIES dict
        """
        if company_key not in LOCAL_COMPANIES:
            raise ValueError(f"Unknown company: {company_key}")

        company_info = LOCAL_COMPANIES[company_key]
        super().__init__(
            name=company_info['name'],
            base_url=company_info['url'],
            area=company_info['area']
        )
        self.company_key = company_key
        self.company_info = company_info

    @staticmethod
    def get_available_companies() -> Dict[str, Dict]:
        """Get all available local companies."""
        return LOCAL_COMPANIES

    def scrape(self, conditions: Dict, mode: str = 'rental') -> List[Dict]:
        """
        Scrape properties from the company website.

        Args:
            conditions: Search conditions (e.g., max_rent, min_area, etc.)
            mode: 'rental' or 'purchase'

        Returns:
            List of property dictionaries
        """
        # Select appropriate URL based on mode
        if mode == 'rental':
            search_url = self.company_info.get('search_url')
        elif mode == 'purchase':
            search_url = self.company_info.get('buy_url')
        else:
            raise ValueError(f"Unknown mode: {mode}")

        if not search_url:
            self.logger.warning(f"No {mode} URL available for {self.company_key}")
            return []

        try:
            response = requests.get(search_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            properties = []

            # Try to find property blocks
            blocks = self._find_property_blocks(soup)

            if blocks:
                for block in blocks:
                    prop = self._parse_generic_block(block, conditions, mode)
                    if prop:
                        properties.append(prop)

            # Fallback to text extraction if no blocks found
            if not properties:
                text_content = soup.get_text()
                properties = self._extract_from_text(text_content, conditions, mode)

            return properties

        except requests.RequestException as e:
            self.logger.error(f"Error scraping {self.company_key}: {e}")
            return []

    def _find_property_blocks(self, soup: BeautifulSoup) -> list:
        """
        Find property blocks using generic CSS selectors.

        Args:
            soup: BeautifulSoup object

        Returns:
            List of property block elements
        """
        # Common CSS selectors for property listings
        selectors = [
            '.property-item',
            '.bukken-item',
            '.room-item',
            '.property-card',
            '.listing-item',
            '.bukken',
            '[class*="property"]',
            '[class*="bukken"]',
            'div.item',
            'li.item',
        ]

        for selector in selectors:
            blocks = soup.select(selector)
            if blocks:
                self.logger.info(f"Found {len(blocks)} blocks with selector: {selector}")
                return blocks

        return []

    def _parse_generic_block(self, block, conditions: Dict, mode: str) -> Optional[Dict]:
        """
        Parse a property block generically.

        Args:
            block: BeautifulSoup element
            conditions: Search conditions
            mode: 'rental' or 'purchase'

        Returns:
            Property dictionary or None
        """
        try:
            # Extract text content
            text = block.get_text(separator=' ', strip=True)

            # Extract property URL if available
            url = None
            link = block.find('a', href=True)
            if link:
                href = link.get('href')
                if href:
                    url = href if href.startswith('http') else self.company_info['url'].rstrip('/') + '/' + href.lstrip('/')

            # Parse common patterns
            property_dict = {}

            # Extract building name (usually first or prominent text)
            property_dict['building_name'] = self._extract_building_name(text, block)

            # Extract layout (1LDK, 2K, etc.)
            layout = self._extract_layout(text)
            property_dict['layout'] = layout

            # Extract area in square meters
            area = self._extract_area(text)
            property_dict['area'] = area

            # Extract age/築年数
            age_match = re.search(r'築(\d+)年', text)
            if age_match:
                property_dict['age'] = int(age_match.group(1))
                property_dict['age_text'] = age_match.group(0)

            # Extract address (preferably with 熊本県 prefix)
            address = self._extract_address(text, block)
            property_dict['address'] = address

            # Extract walk minutes
            walk_match = re.search(r'(?:徒歩|駅から)?(\d+)分', text)
            if walk_match:
                property_dict['walk_minutes'] = int(walk_match.group(1))

            # Extract price information based on mode
            if mode == 'rental':
                # Extract rent (万円)
                rent_match = re.search(r'(\d+(?:\.\d+)?)万円', text)
                if rent_match:
                    property_dict['rent'] = float(rent_match.group(1))

                # Try to extract management fee if available
                mgmt_match = re.search(r'管理費[：:]\s*(\d+(?:\.\d+)?)万?円', text)
                if mgmt_match:
                    property_dict['management_fee'] = float(mgmt_match.group(1))

            elif mode == 'purchase':
                # Extract purchase price (万円 or 億)
                price_match = re.search(r'(\d+(?:\.\d+)?)(?:万|億)円', text)
                if price_match:
                    price_str = price_match.group(1)
                    if '億' in text[max(0, text.find(price_str)-10):text.find(price_str)+20]:
                        property_dict['price'] = float(price_str) * 10000000
                    else:
                        property_dict['price'] = float(price_str) * 10000

                # Extract land area
                land_area = self._extract_land_area(text)
                if land_area:
                    property_dict['land_area'] = land_area

            # Optional fields
            published_date = self._extract_published_date(text)
            if published_date:
                property_dict['published_date'] = published_date

            next_update = self._extract_next_update_date(text)
            if next_update:
                property_dict['next_update_date'] = next_update

            school_distance = self._extract_school_distance(text)
            if school_distance:
                property_dict['nearest_school_distance'] = school_distance

            city_planning = self._extract_city_planning(text)
            if city_planning:
                property_dict['city_planning'] = city_planning

            zoning = self._extract_zoning(text)
            if zoning:
                property_dict['zoning'] = zoning

            land_category = self._extract_land_category(text)
            if land_category:
                property_dict['land_category'] = land_category

            if url:
                property_dict['url'] = url

            # Use BaseScraper's make_property_dict method
            return self._make_property_dict(property_dict)

        except Exception as e:
            self.logger.error(f"Error parsing block: {e}")
            return None

    def _extract_from_text(self, text: str, conditions: Dict, mode: str) -> List[Dict]:
        """
        Fallback text extraction method.

        Args:
            text: Full text content from page
            conditions: Search conditions
            mode: 'rental' or 'purchase'

        Returns:
            List of property dictionaries
        """
        properties = []

        # Split text into potential property entries
        # This is a fallback, so we look for price patterns
        if mode == 'rental':
            price_pattern = r'(\d+(?:\.\d+)?)万円'
        else:
            price_pattern = r'(\d+(?:\.\d+)?)(?:万|億)円'

        matches = list(re.finditer(price_pattern, text))

        # Try to extract property info around each match
        for match in matches:
            start = max(0, match.start() - 500)
            end = min(len(text), match.end() + 500)
            snippet = text[start:end]

            prop_dict = {}

            # Extract from snippet
            layout = self._extract_layout(snippet)
            if layout:
                prop_dict['layout'] = layout

            area = self._extract_area(snippet)
            if area:
                prop_dict['area'] = area

            address = self._extract_address(snippet, None)
            if address:
                prop_dict['address'] = address

            if mode == 'rental':
                rent_match = re.search(r'(\d+(?:\.\d+)?)万円', snippet)
                if rent_match:
                    prop_dict['rent'] = float(rent_match.group(1))
            else:
                price_str = match.group(1)
                if '億' in snippet[max(0, match.start()-20):match.end()]:
                    prop_dict['price'] = float(price_str) * 10000000
                else:
                    prop_dict['price'] = float(price_str) * 10000

            if prop_dict:
                result = self._make_property_dict(prop_dict)
                if result:
                    properties.append(result)

        return properties

    def _extract_building_name(self, text: str, block) -> Optional[str]:
        """Extract building name from text or block."""
        # Try to get from heading or title element
        if block:
            for tag in ['h1', 'h2', 'h3', 'strong', 'b']:
                heading = block.find(tag)
                if heading:
                    name = heading.get_text(strip=True)
                    if name and len(name) < 100:
                        return name

        # Fallback to first line or prominent text
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if lines:
            first_line = lines[0]
            if len(first_line) < 100 and not any(keyword in first_line for keyword in ['万円', '㎡', '秒']):
                return first_line

        return None

    def _extract_layout(self, text: str) -> Optional[str]:
        """Extract layout (1LDK, 2K, etc.)."""
        match = re.search(r'(\d+[DLK]+)', text)
        if match:
            return match.group(1)
        return None

    def _extract_area(self, text: str) -> Optional[float]:
        """Extract area in square meters."""
        match = re.search(r'(\d+(?:\.\d+)?)(?:㎡|m²|平方メートル)', text)
        if match:
            return float(match.group(1))
        return None

    def _extract_address(self, text: str, block) -> Optional[str]:
        """Extract address, preferably with 熊本県 prefix."""
        # Look for address pattern with 熊本県
        match = re.search(r'(熊本県[^\n]*(?:市|郡)[^\n]*)', text)
        if match:
            return match.group(1).strip()

        # Fallback to any address-like text
        match = re.search(r'((?:熊本|阿蘇)[^\n]*?(?:市|郡|町|村)?[^\n]*?(?:区|町|丁目)?[^\n]*)', text)
        if match:
            return match.group(1).strip()

        return None

    def _extract_land_area(self, text: str) -> Optional[float]:
        """Extract land area."""
        # Look for patterns like "土地面積: 123.45㎡"
        match = re.search(r'土地(?:面積)?[：:]\s*(\d+(?:\.\d+)?)(?:㎡|m²)', text)
        if match:
            return float(match.group(1))
        return None

    def _extract_published_date(self, text: str) -> Optional[str]:
        """Extract published date."""
        match = re.search(r'(?:掲載|公開)?(?:日付|日時)[：:]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})', text)
        if match:
            return match.group(1)
        return None

    def _extract_next_update_date(self, text: str) -> Optional[str]:
        """Extract next update date."""
        match = re.search(r'次(?:回)?(?:更新|掲載)[：:]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})', text)
        if match:
            return match.group(1)
        return None

    def _extract_school_distance(self, text: str) -> Optional[str]:
        """Extract nearest school distance."""
        match = re.search(r'(?:最寄り)?(?:小学校|中学校)[：:]\s*([^\n]*)', text)
        if match:
            return match.group(1).strip()
        return None

    def _extract_city_planning(self, text: str) -> Optional[str]:
        """Extract city planning info."""
        match = re.search(r'(?:都市計画|用途地域)[：:]\s*([^\n]*)', text)
        if match:
            return match.group(1).strip()
        return None

    def _extract_zoning(self, text: str) -> Optional[str]:
        """Extract zoning info."""
        match = re.search(r'(?:建蔽率|容積率)[：:]\s*([^\n]*)', text)
        if match:
            return match.group(1).strip()
        return None

    def _extract_land_category(self, text: str) -> Optional[str]:
        """Extract land category."""
        match = re.search(r'(?:地目|地種)[：:]\s*([^\n]*)', text)
        if match:
            return match.group(1).strip()
        return None
