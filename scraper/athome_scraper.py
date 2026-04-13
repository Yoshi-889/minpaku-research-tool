import re
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode, quote
from bs4 import BeautifulSoup
import requests
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class AthomeScraper(BaseScraper):
    """
    Real estate scraper for AtHome (athome.co.jp)
    Supports both rental (chintai) and purchase (kodate) modes
    across all 47 prefectures.
    """

    BASE_URL = "https://www.athome.co.jp"

    # All 47 Japanese prefectures with their URL paths
    PREFECTURE_PATHS = {
        '北海道': 'hokkaido', '青森県': 'aomori', '岩手県': 'iwate',
        '宮城県': 'miyagi', '秋田県': 'akita', '山形県': 'yamagata',
        '福島県': 'fukushima', '茨城県': 'ibaraki', '栃木県': 'tochigi',
        '群馬県': 'gunma', '埼玉県': 'saitama', '千葉県': 'chiba',
        '東京都': 'tokyo', '神奈川県': 'kanagawa', '新潟県': 'niigata',
        '富山県': 'toyama', '石川県': 'ishikawa', '福井県': 'fukui',
        '山梨県': 'yamanashi', '長野県': 'nagano', '岐阜県': 'gifu',
        '静岡県': 'shizuoka', '愛知県': 'aichi', '三重県': 'mie',
        '滋賀県': 'shiga', '京都府': 'kyoto', '大阪府': 'osaka',
        '兵庫県': 'hyogo', '奈良県': 'nara', '和歌山県': 'wakayama',
        '鳥取県': 'tottori', '島根県': 'shimane', '岡山県': 'okayama',
        '広島県': 'hiroshima', '山口県': 'yamaguchi', '徳島県': 'tokushima',
        '香川県': 'kagawa', '愛媛県': 'ehime', '高知県': 'kochi',
        '福岡県': 'fukuoka', '佐賀県': 'saga', '長崎県': 'nagasaki',
        '熊本県': 'kumamoto', '大分県': 'oita', '宮崎県': 'miyazaki',
        '鹿児島県': 'kagoshima', '沖縄県': 'okinawa',
    }

    # Prefecture codes (01-47)
    PREFECTURE_CODES = {
        '北海道': '01', '青森県': '02', '岩手県': '03', '宮城県': '04',
        '秋田県': '05', '山形県': '06', '福島県': '07', '茨城県': '08',
        '栃木県': '09', '群馬県': '10', '埼玉県': '11', '千葉県': '12',
        '東京都': '13', '神奈川県': '14', '新潟県': '15', '富山県': '16',
        '石川県': '17', '福井県': '18', '山梨県': '19', '長野県': '20',
        '岐阜県': '21', '静岡県': '22', '愛知県': '23', '三重県': '24',
        '滋賀県': '25', '京都府': '26', '大阪府': '27', '兵庫県': '28',
        '奈良県': '29', '和歌山県': '30', '鳥取県': '31', '島根県': '32',
        '岡山県': '33', '広島県': '34', '山口県': '35', '徳島県': '36',
        '香川県': '37', '愛媛県': '38', '高知県': '39', '福岡県': '40',
        '佐賀県': '41', '長崎県': '42', '熊本県': '43', '大分県': '44',
        '宮崎県': '45', '鹿児島県': '46', '沖縄県': '47',
    }

    def __init__(self, headless: bool = True, timeout: int = 30):
        """Initialize AtHome scraper."""
        super().__init__(site_name='アットホーム')
        self.headless = headless
        self.timeout = timeout
        # Enhanced headers to reduce bot detection
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })

    def scrape(self, conditions: Dict[str, Any], mode: str = None, page: int = 1) -> List[Dict[str, Any]]:
        """Scrape AtHome listings for given conditions."""
        if mode is None:
            mode = conditions.get('mode', 'rental')

        if mode not in ['rental', 'purchase']:
            logger.error(f"Invalid mode: {mode}. Must be 'rental' or 'purchase'")
            return []

        max_pages = conditions.get('max_pages', 1)
        all_properties = []

        for pg in range(1, max_pages + 1):
            url = self._build_search_url(conditions, mode, pg)
            logger.info(f"Scraping {mode} listings page {pg} from: {url}")

            try:
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code == 403:
                    logger.warning(f"403 Forbidden (bot detection) from AtHome: {url}")
                    break
                response.raise_for_status()
                response.encoding = 'utf-8'
            except requests.RequestException as e:
                logger.error(f"Failed to fetch URL {url}: {e}")
                continue

            soup = BeautifulSoup(response.content, 'html.parser')

            if mode == 'rental':
                page_props = self._parse_rental_page(soup, conditions)
            else:
                page_props = self._parse_purchase_page(soup, conditions)

            if not page_props:
                logger.info(f"No properties found on page {pg}")
                break

            all_properties.extend(page_props)
            logger.info(f"Page {pg}: found {len(page_props)} properties")

            if pg < max_pages:
                import time
                time.sleep(1)

        logger.info(f"Total AtHome properties: {len(all_properties)}")
        return all_properties

    def _build_search_url(self, conditions: Dict[str, Any], mode: str, page: int = 1) -> str:
        """Build search URL for AtHome."""
        prefecture = conditions.get('prefecture', '')
        city = conditions.get('city', '')
        pref_path = self.PREFECTURE_PATHS.get(prefecture, '')

        if not pref_path:
            logger.warning(f"Unknown prefecture: {prefecture}")
            pref_path = 'tokyo'

        mode_path = 'chintai' if mode == 'rental' else 'kodate'
        base_url = f"{self.BASE_URL}/{mode_path}/{pref_path}/"

        params = {}
        if city:
            params['keyword'] = city
        if conditions.get('min_price'):
            params['rent_min' if mode == 'rental' else 'price_min'] = conditions['min_price']
        if conditions.get('max_price'):
            params['rent_max' if mode == 'rental' else 'price_max'] = conditions['max_price']
        if conditions.get('min_area'):
            params['area_min'] = conditions['min_area']
        if conditions.get('max_area'):
            params['area_max'] = conditions['max_area']
        if page > 1:
            params['page'] = page

        if params:
            return base_url + '?' + urlencode(params)
        return base_url

    def _parse_rental_page(self, soup: BeautifulSoup, conditions: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse rental listings from AtHome page."""
        properties = []
        prefecture = conditions.get('prefecture', '')

        # Try multiple CSS selectors to find property cards
        selectors = [
            '.p-property-card',
            '.p-cassetteitem',
            '[class*="propertyCard"]',
            '[class*="cassette"]',
            '.cassetteitem',
            '[class*="bukken"]',
            '.property-card',
            '[data-property-id]',
            '.mod-property',
        ]

        cards = []
        for selector in selectors:
            cards = soup.select(selector)
            if cards:
                logger.debug(f"AtHome: Found {len(cards)} cards with selector: {selector}")
                break

        if not cards:
            logger.debug("AtHome: No cards found with any selector, trying fallback")
            return self._fallback_parse(soup, 'rental', prefecture)

        for card in cards:
            try:
                prop = self._extract_property_from_card(card, prefecture, 'rental')
                if prop:
                    properties.append(prop)
            except Exception as e:
                logger.debug(f"Error parsing rental property card: {e}")

        logger.info(f"Extracted {len(properties)} rental properties from AtHome")
        return properties

    def _parse_purchase_page(self, soup: BeautifulSoup, conditions: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse purchase listings from AtHome page."""
        properties = []
        prefecture = conditions.get('prefecture', '')

        selectors = [
            '.p-property-card',
            '.p-cassetteitem',
            '[class*="propertyCard"]',
            '[class*="cassette"]',
            '.cassetteitem',
            '[class*="bukken"]',
            '.property-card',
            '[data-property-id]',
            '.mod-property',
        ]

        cards = []
        for selector in selectors:
            cards = soup.select(selector)
            if cards:
                break

        if not cards:
            return self._fallback_parse(soup, 'purchase', prefecture)

        for card in cards:
            try:
                prop = self._extract_property_from_card(card, prefecture, 'purchase')
                if prop:
                    properties.append(prop)
            except Exception as e:
                logger.debug(f"Error parsing purchase property card: {e}")

        logger.info(f"Extracted {len(properties)} purchase properties from AtHome")
        return properties

    def _extract_property_from_card(self, card, prefecture: str, mode: str) -> Optional[Dict]:
        """Extract property data from a card element using text parsing."""
        text = card.get_text(separator=' ')

        # Building name
        building_name = ''
        name_el = card.select_one(
            '[class*="name"] a, [class*="title"] a, h2 a, h3 a, a[href*="bukken"]'
        )
        if name_el:
            building_name = name_el.get_text(strip=True)

        # URL
        url = ''
        link_el = card.select_one('a[href*="bukken"], a[href*="chintai"], a[href*="kodate"]')
        if link_el and link_el.get('href'):
            href = link_el['href']
            url = href if href.startswith('http') else self.BASE_URL + href

        # Address
        address = ''
        addr_el = card.select_one('[class*="address"], [class*="jyusho"]')
        if addr_el:
            address = addr_el.get_text(strip=True)
        else:
            addr_match = re.search(r'((?:北海道|(?:東京|京都|大阪)府|.{2,3}県)\S+(?:市|区|町|村)\S*)', text)
            if addr_match:
                address = addr_match.group(1)

        # Layout
        layout = ''
        layout_match = re.search(r'(\d[A-Z]*(?:SLDK|LDK|DK|K))', text)
        if layout_match:
            layout = layout_match.group(1)

        # Area
        area = self._parse_area(text)

        # Age
        age_years = self._parse_age(text)
        age_text = f"築{age_years}年" if age_years is not None else ''

        # Transport
        transport = ''
        trans_el = card.select_one('[class*="traffic"], [class*="access"], [class*="kotsu"]')
        if trans_el:
            transport = trans_el.get_text(strip=True)

        walk_minutes = self._parse_walk_minutes(text)

        # Price/Rent
        rent = None
        price = None
        if mode == 'rental':
            rent = self._parse_price(text)
        else:
            price = self._parse_price_yen(text)

        # Only return if we got some meaningful data
        if building_name or address or rent or price:
            return self._make_property_dict(
                listing_type=mode,
                building_name=building_name,
                address=self._normalize_address(address),
                transport=transport,
                rent=rent,
                price=price,
                layout=layout,
                area=area,
                age=age_years,
                age_text=age_text,
                walk_minutes=walk_minutes,
                url=url,
            )
        return None

    def _fallback_parse(self, soup: BeautifulSoup, mode: str, prefecture: str) -> List[Dict]:
        """Fallback parser using links to property detail pages."""
        properties = []
        seen_urls = set()

        # Find links to property pages
        if mode == 'rental':
            links = soup.select('a[href*="/chintai/"], a[href*="/rent/"]')
        else:
            links = soup.select('a[href*="/kodate/"], a[href*="/buy/"]')

        for link in links:
            href = link.get('href', '')
            if not href or href in seen_urls:
                continue

            # Filter out navigation/category links (keep only property detail links)
            if '/bukken/' not in href and re.search(r'/\d{5,}/', href) is None:
                continue

            seen_urls.add(href)
            name = link.get_text(strip=True)
            if not name or len(name) < 3:
                continue

            url = href if href.startswith('http') else self.BASE_URL + href

            prop = self._make_property_dict(
                listing_type=mode,
                building_name=name,
                url=url,
            )
            properties.append(prop)

        return properties

    def close(self):
        """Close the session."""
        if self.session:
            self.session.close()
