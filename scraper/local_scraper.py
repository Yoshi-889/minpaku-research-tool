"""Local real estate company scraper.

Scrapes individual real estate company websites in Aso area.
User can select which local companies to include.
"""
import re
from typing import List, Dict, Optional
from datetime import datetime
from .base_scraper import BaseScraper


# 阿蘇地域の不動産会社リスト（拡張可能）
LOCAL_COMPANIES = {
    'ハイトスコーポレーション': {
        'name': 'ハイトスコーポレーション',
        'url': 'https://www.hights.co.jp',
        'search_url': 'https://www.hights.co.jp/rent/list/',
        'area': '阿蘇市',
        'description': '阿蘇地域を中心とした不動産会社',
    },
    'アパマンショップ光の森店': {
        'name': 'アパマンショップ光の森店',
        'url': 'https://www.apamanshop.com',
        'search_url': 'https://www.apamanshop.com/ensen/03610/area/',
        'area': '犊本県全般',
        'description': '全国チェーン（犊本エリア）',
    },
    '大東建託リーシング犊本中央店': {
        'name': '大東建託リーシング',
        'url': 'https://www.eheya.net',
        'search_url': 'https://www.eheya.net/kumamoto/',
        'area': '熊本県全般',
        'description': 'DK SELECT（大東建託）の賃貸物件',
    },
    '明和不動産': {
        'name': '明和不動産',
        'url': 'https://www.meiwa-fudosan.co.jp',
        'search_url': 'https://www.meiwa-fudosan.co.jp/rent/',
        'area': '犊本県全般',
        'description': '犊本県を中心とした地域密着型不動産会社',
    },
}


class LocalScraper(BaseScraper):
    """Scraper for local real estate company websites."""

    def __init__(self, company_key: str):
        company = LOCAL_COMPANIES.get(company_key, {})
        self.company = company
        super().__init__(company.get('name', company_key))
        self.base_url = company.get('url', '')

    @staticmethod
    def get_available_companies() -> Dict[str, Dict]:
        """Return list of available local companies."""
        return LOCAL_COMPANIES

    def scrape(self, conditions: Dict) -> List[Dict]:
        """Scrape properties from local company website."""
        all_properties = []

        search_url = self.company.get('search_url', '')
        if not search_url:
            self.logger.warning(f"No search URL for {self.site_name}")
            return []

        soup = self._fetch_page(search_url)
        if soup is None:
            return []

        # Generic property extraction from any real estate page
        text = soup.get_text()

        # Try to find property cards/blocks
        # Look for common patterns in real estate websites
        property_blocks = self._find_property_blocks(soup)

        for block in property_blocks:
            prop = self._parse_generic_block(block, conditions)
            if prop and prop.get('rent'):
                all_properties.append(prop)

        # If no structured blocks found, try text extraction
        if not all_properties:
            self.logger.info(f"No structured data found for {self.site_name}, trying text extraction")
            props = self._extract_from_text(text, conditions)
            all_properties.extend(props)

        self.logger.info(f"Scraped {len(all_properties)} from {self.site_name}")
        return all_properties

    def _find_property_blocks(self, soup) -> list:
        """Find property listing blocks using common CSS patterns."""
        selectors = [
            '.property-item', '.bukken-item', '.room-item',
            '.property-card', '.bukken-card',
            'article.property', 'div.property',
            '[class*="bukken"]', '[class*="property"]',
            '.mod-building', '.cassetteitem',
            'table.result tr', '.listing-item',
        ]
        for selector in selectors:
            blocks = soup.select(selector)
            if blocks:
                return blocks
        return []

    def _parse_generic_block(self, block, conditions: Dict) -> Optional[Dict]:
        """Parse a generic property block."""
        try:
            text = block.get_text()
            city = conditions.get('city', '阿蘇市')

            # Filter by city if possible
            if city and city not in text and '阿蘇' not in text:
                return None

            rent = None
            rent_match = re.search(r'([\d.]+)\s*万円', text)
            if rent_match:
                rent = float(rent_match.group(1))

            if not rent:
                return None

            # Building name
            building_name = ''
            name_el = block.select_one('h2, h3, h4, .name, .title')
            if name_el:
                building_name = name_el.get_text(strip=True)

            # Address
            address = ''
            match = re.search(r'(犊本県[^\s\n]+)', text)
            if match:
                address = match.group(1)

            # Layout
            layout = ''
            layout_match = re.search(r'(\d[LDKS]{1,4})', text)
            if layout_match:
                layout = layout_match.group(1)

            # Area
            area = None
            area_match = re.search(r'([\d.]+)\s*m[²㎡]', text)
            if area_match:
                area = float(area_match.group(1))

            # Management fee
            mgmt_fee = None
            mgmt_match = re.search(r'管理費[等]?\s*([\d,]+)\s*円', text)
            if not mgmt_match:
                mgmt_match = re.search(r'/\s*([\d,]+)\s*円', text)
            if mgmt_match:
                mgmt_fee = float(mgmt_match.group(1).replace(',', '')) / 10000

            # Age
            age_text = ''
            age_match = re.search(r'(新築|築\d+年)', text)
            if age_match:
                age_text = age_match.group(1)

            # URL
            url = ''
            link = block.select_one('a[href]')
            if link:
                href = link.get('href', '')
                if href.startswith('/'):
                    url = self.base_url + href
                elif href.startswith('http'):
                    url = href

            return {
                'site': self.site_name,
                'building_name': building_name,
                'address': address,
                'transport': '',
                'rent': rent,
                'management_fee': mgmt_fee,
                'deposit': '',
                'key_money': '',
                'layout': layout,
                'area': area,
                'age': self._parse_age(age_text),
                'age_text': age_text,
                'floor': '',
                'walk_minutes': None,
                'url': url,
                'scraped_at': datetime.now().isoformat(),
            }
        except Exception as e:
            self.logger.error(f"Error parsing block: {e}")
            return None

    def _extract_from_text(self, text: str, conditions: Dict) -> List[Dict]:
        """Fallback: extract property info from page text."""
        properties = []
        city = conditions.get('city', '阿蘇市')

        # Find all rent mentions
        rent_matches = list(re.finditer(r'([\d.]+)\s*万円', text))

        for match in rent_matches[:20]:  # Limit to 20
            start = max(0, match.start() - 200)
            end = min(len(text), match.end() + 200)
            context = text[start:end]

            if city and city not in context and '阿蘇' not in context:
                continue

            rent = float(match.group(1))
            if rent < 1 or rent > 50:  # Sanity check
                continue

            # Try to extract other info from context
            layout = ''
            layout_match = re.search(r'(\d[LDKS]{1,4})', context)
            if layout_match:
                layout = layout_match.group(1)

            area = None
            area_match = re.search(r'([\d.]+)\s*m[²㎡]', context)
            if area_match:
                area = float(area_match.group(1))

            address = ''
            addr_match = re.search(r'(熊本県[^\s\n]+)', context)
            if addr_match:
                address = addr_match.group(1)

            properties.append({
                'site': self.site_name,
                'building_name': '',
                'address': address,
                'transport': '',
                'rent': rent,
                'management_fee': None,
                'deposit': '',
                'key_money': '',
                'layout': layout,
                'area': area,
                'age': None,
                'age_text': '',
                'floor': '',
                'walk_minutes': None,
                'url': self.company.get('search_url', ''),
                'scraped_at': datetime.now().isoformat(),
            })

        return properties
