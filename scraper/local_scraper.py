阿蘇地域の不動産会社リスト（拡張可能）ハイトスコーポレーションハイトスコーポレーション阿蘇市阿蘇地域を中心とした不動産会社アパマンショップ光の森店アパマンショップ光の森店熊本県全般全国チェーン（熊本エリア）大東建託リーシング熊本中央店大東建託リーシング熊本県全般（大東建託）の賃貸物件明和不動産明和不動産熊本県全般熊本県を中心とした地域密着型不動産会社阿蘇市阿蘇万円熊本県²㎡管理費等円円新築築年阿蘇市万円阿蘇²㎡熊本県"""Local real estate company scraper.

Scrapes individual real estate company websites in Aso area.
User can select which local companies to include.
"""
import re
from typing import List, Dict, Optional
from datetime import datetime
from .base_scraper import BaseScraper


# é¿èå°åã®ä¸åç£ä¼ç¤¾ãªã¹ãï¼æ¡å¼µå¯è½ï¼
LOCAL_COMPANIES = {
    'ãã¤ãã¹ã³ã¼ãã¬ã¼ã·ã§ã³': {
        'name': 'ãã¤ãã¹ã³ã¼ãã¬ã¼ã·ã§ã³',
        'url': 'https://www.hights.co.jp',
        'search_url': 'https://www.hights.co.jp/rent/list/',
        'area': 'é¿èå¸',
        'description': 'é¿èå°åãä¸­å¿ã¨ããä¸åç£ä¼ç¤¾',
    },
    'ã¢ããã³ã·ã§ããåã®æ£®åº': {
        'name': 'ã¢ããã³ã·ã§ããåã®æ£®åº',
        'url': 'https://www.apamanshop.com',
        'search_url': 'https://www.apamanshop.com/ensen/03610/area/',
        'area': 'çæ¬çå¨è¬',
        'description': 'å¨å½ãã§ã¼ã³ï¼çæ¬ã¨ãªã¢ï¼',
    },
    'å¤§æ±å»ºè¨ãªã¼ã·ã³ã°çæ¬ä¸­å¤®åº': {
        'name': 'å¤§æ±å»ºè¨ãªã¼ã·ã³ã°',
        'url': 'https://www.eheya.net',
        'search_url': 'https://www.eheya.net/kumamoto/',
        'area': 'çæ¬çå¨è¬',
        'description': 'DK SELECTï¼å¤§æ±å»ºè¨ï¼ã®è³è²¸ç©ä»¶',
    },
    'æåä¸åç£': {
        'name': 'æåä¸åç£',
        'url': 'https://www.meiwa-fudosan.co.jp',
        'search_url': 'https://www.meiwa-fudosan.co.jp/rent/',
        'area': 'çæ¬çå¨è¬',
        'description': 'çæ¬çãä¸­å¿ã¨ããå°åå¯çåä¸åç£ä¼ç¤¾',
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
            city = conditions.get('city', 'é¿èå¸')

            # Filter by city if possible
            if city and city not in text and 'é¿è' not in text:
                return None

            rent = None
            rent_match = re.search(r'([\d.]+)\s*ä¸å', text)
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
            match = re.search(r'(çæ¬ç[^\s\n]+)', text)
            if match:
                address = match.group(1)

            # Layout
            layout = ''
            layout_match = re.search(r'(\d[LDKS]{1,4})', text)
            if layout_match:
                layout = layout_match.group(1)

            # Area
            area = None
            area_match = re.search(r'([\d.]+)\s*m[Â²ã¡]', text)
            if area_match:
                area = float(area_match.group(1))

            # Management fee
            mgmt_fee = None
            mgmt_match = re.search(r'ç®¡çè²»[ç­]?\s*([\d,]+)\s*å', text)
            if not mgmt_match:
                mgmt_match = re.search(r'/\s*([\d,]+)\s*å', text)
            if mgmt_match:
                mgmt_fee = float(mgmt_match.group(1).replace(',', '')) / 10000

            # Age
            age_text = ''
            age_match = re.search(r'(æ°ç¯|ç¯\d+å¹´)', text)
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
        city = conditions.get('city', 'é¿èå¸')

        # Find all rent mentions
        rent_matches = list(re.finditer(r'([\d.]+)\s*ä¸å', text))

        for match in rent_matches[:20]:  # Limit to 20
            start = max(0, match.start() - 200)
            end = min(len(text), match.end() + 200)
            context = text[start:end]

            if city and city not in context and 'é¿è' not in context:
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
            area_match = re.search(r'([\d.]+)\s*m[Â²ã¡]', context)
            if area_match:
                area = float(area_match.group(1))

            address = ''
            addr_match = re.search(r'(çæ¬ç[^\s\n]+)', context)
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
