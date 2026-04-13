import logging
from typing import Dict, List, Optional
from datetime import datetime
from bs4 import BeautifulSoup
import requests
import re
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class HomesScraper(BaseScraper):
    """
    Scraper for LIFULL HOME'S real estate portal.
    Supports both rental (chintai) and purchase (kodate) modes
    for all 47 prefectures.
    """

    BASE_URL = "https://www.homes.co.jp"

    # All 47 Japanese prefectures with URL path segments
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

    def __init__(self, headless: bool = True, timeout: int = 15):
        """Initialize the LIFULL HOME'S scraper."""
        super().__init__(site_name="LIFULL HOME'S")
        self.headless = headless
        self.timeout = timeout
        # Enhanced headers to reduce bot detection
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })

    def _get_prefecture_path(self, prefecture: str) -> str:
        """Get URL path segment for given prefecture."""
        if prefecture not in self.PREFECTURE_PATHS:
            raise ValueError(f"Prefecture '{prefecture}' not found.")
        return self.PREFECTURE_PATHS[prefecture]

    def _build_search_url(self, conditions: Dict, mode: str = 'rental', page: int = 1) -> str:
        """Build search URL for rental or purchase mode."""
        if mode not in ['rental', 'purchase']:
            raise ValueError(f"Mode must be 'rental' or 'purchase', got '{mode}'")
        if 'prefecture' not in conditions:
            raise ValueError("'prefecture' is required in conditions")

        pref_path = self._get_prefecture_path(conditions['prefecture'])
        city = conditions.get('city', '')

        if mode == 'rental':
            # Try city-specific URL first, fallback to prefecture
            if city:
                url = f"{self.BASE_URL}/chintai/{pref_path}/city/{city}/list/"
            else:
                url = f"{self.BASE_URL}/chintai/{pref_path}/list/"
        else:
            if city:
                url = f"{self.BASE_URL}/kodate/b-{pref_path}/city/{city}/list/"
            else:
                url = f"{self.BASE_URL}/kodate/b-{pref_path}/list/"

        params = {}
        if conditions.get('keyword'):
            params['key'] = conditions['keyword']
        if page > 1:
            params['page'] = page

        if params:
            query = '&'.join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query}"

        return url

    def scrape(self, conditions: Dict, mode: str = None) -> List[Dict]:
        """Scrape real estate listings from LIFULL HOME'S."""
        if mode is None:
            mode = conditions.get('mode', 'rental')

        if mode not in ['rental', 'purchase']:
            raise ValueError(f"Mode must be 'rental' or 'purchase', got '{mode}'")

        listings = []
        max_pages = conditions.get('max_pages', 3)

        # Try city-specific URL first, then prefecture-level fallback
        urls_to_try = []

        city = conditions.get('city', '')
        pref_path = self._get_prefecture_path(conditions['prefecture'])

        if mode == 'rental':
            if city:
                # HOMES uses prefecture-level listing, city filtering via keyword
                urls_to_try.append(f"{self.BASE_URL}/chintai/{pref_path}/list/?key={city}")
            urls_to_try.append(f"{self.BASE_URL}/chintai/{pref_path}/list/")
        else:
            if city:
                urls_to_try.append(f"{self.BASE_URL}/kodate/b-{pref_path}/list/?key={city}")
            urls_to_try.append(f"{self.BASE_URL}/kodate/b-{pref_path}/list/")

        for base_url in urls_to_try:
            try:
                for page in range(1, max_pages + 1):
                    url = base_url if page == 1 else f"{base_url}{'&' if '?' in base_url else '?'}page={page}"
                    logger.info(f"Scraping {mode} page {page} from: {url}")

                    try:
                        response = self.session.get(url, timeout=self.timeout)
                        if response.status_code == 403:
                            logger.warning(f"403 Forbidden (bot detection) from HOMES: {url}")
                            break
                        response.raise_for_status()
                    except requests.RequestException as e:
                        logger.error(f"Failed to fetch page {page}: {e}")
                        break

                    soup = BeautifulSoup(response.content, 'html.parser')

                    if mode == 'rental':
                        page_listings = self._scrape_rental_page(soup, conditions)
                    else:
                        page_listings = self._scrape_purchase_page(soup, conditions)

                    if not page_listings:
                        logger.info(f"No listings found on page {page}, stopping.")
                        break

                    listings.extend(page_listings)
                    logger.info(f"Found {len(page_listings)} listings on page {page}")

                if listings:
                    break  # Got results, no need to try fallback URL

            except Exception as e:
                logger.error(f"Error scraping {base_url}: {e}")
                continue

        logger.info(f"Total listings scraped from HOMES: {len(listings)}")
        return listings

    def _scrape_rental_page(self, soup: BeautifulSoup, conditions: Dict) -> List[Dict]:
        """Parse rental listings from page soup."""
        listings = []

        # Try multiple selectors for property containers
        selectors = [
            'div.mod-mergeBuilding',
            'div.mod-buildingAnchor',
            '.bukkenbox',
            '.prg-building',
            '[class*="building"]',
            '[class*="bukken"]',
        ]

        building_elements = []
        for selector in selectors:
            building_elements = soup.select(selector)
            if building_elements:
                logger.debug(f"Found {len(building_elements)} buildings with selector: {selector}")
                break

        if not building_elements:
            # Fallback: try to find any property-like elements
            building_elements = soup.select('[data-building-id]')
            if not building_elements:
                logger.debug("No building elements found with any selector")
                # Try generic parsing from page text
                return self._fallback_parse(soup, 'rental')

        for building_el in building_elements:
            try:
                text = building_el.get_text()

                # Building name
                name_el = (building_el.select_one('[class*="name"] a') or
                           building_el.select_one('h2 a') or
                           building_el.select_one('a[href*="/chintai/"]'))
                name = name_el.get_text(strip=True) if name_el else ''
                url = ''
                if name_el and name_el.get('href'):
                    href = name_el['href']
                    url = href if href.startswith('http') else self.BASE_URL + href

                # Address
                address = ''
                addr_el = building_el.select_one('[class*="address"], [class*="jyusho"]')
                if addr_el:
                    address = addr_el.get_text(strip=True)
                else:
                    addr_match = re.search(r'((?:北海道|(?:東京|京都|大阪)府|.{2,3}県)\S+(?:市|区|町|村)\S*)', text)
                    if addr_match:
                        address = addr_match.group(1)

                # Transport
                transport = ''
                trans_el = building_el.select_one('[class*="traffic"], [class*="access"]')
                if trans_el:
                    transport = trans_el.get_text(strip=True)

                walk_minutes = self._parse_walk_minutes(text)
                age_years = self._parse_age(text)

                # Rent
                rent = self._parse_price(text)

                # Layout
                layout = ''
                layout_match = re.search(r'(\d[A-Z]*(?:SLDK|LDK|DK|K))', text)
                if layout_match:
                    layout = layout_match.group(1)

                # Area
                area = self._parse_area(text)

                if name or address or rent:
                    prop = self._make_property_dict(
                        listing_type='rental',
                        building_name=name,
                        address=self._normalize_address(address),
                        transport=transport,
                        rent=rent,
                        layout=layout,
                        area=area,
                        age=age_years,
                        age_text=f"築{age_years}年" if age_years is not None else '',
                        walk_minutes=walk_minutes,
                        url=url,
                    )
                    listings.append(prop)

            except Exception as e:
                logger.warning(f"Error parsing rental building: {e}")

        return listings

    def _scrape_purchase_page(self, soup: BeautifulSoup, conditions: Dict) -> List[Dict]:
        """Parse purchase listings from page soup."""
        listings = []

        selectors = [
            'div.mod-mergeBuilding',
            '.bukkencard',
            '.property',
            '[class*="building"]',
            '[class*="bukken"]',
        ]

        card_elements = []
        for selector in selectors:
            card_elements = soup.select(selector)
            if card_elements:
                break

        if not card_elements:
            return self._fallback_parse(soup, 'purchase')

        for card_el in card_elements:
            try:
                text = card_el.get_text()

                # Title
                title_el = (card_el.select_one('[class*="name"] a') or
                            card_el.select_one('h2 a') or
                            card_el.select_one('a'))
                title = title_el.get_text(strip=True) if title_el else ''
                url = ''
                if title_el and title_el.get('href'):
                    href = title_el['href']
                    url = href if href.startswith('http') else self.BASE_URL + href

                # Address
                address = ''
                addr_el = card_el.select_one('[class*="address"]')
                if addr_el:
                    address = addr_el.get_text(strip=True)

                price = self._parse_price_yen(text)
                area = self._parse_area(text)
                age_years = self._parse_age(text)
                walk_minutes = self._parse_walk_minutes(text)

                layout = ''
                layout_match = re.search(r'(\d[A-Z]*(?:SLDK|LDK|DK|K))', text)
                if layout_match:
                    layout = layout_match.group(1)

                if title or address or price:
                    prop = self._make_property_dict(
                        listing_type='purchase',
                        building_name=title,
                        address=self._normalize_address(address),
                        price=price,
                        layout=layout,
                        area=area,
                        age=age_years,
                        age_text=f"築{age_years}年" if age_years is not None else '',
                        walk_minutes=walk_minutes,
                        url=url,
                    )
                    listings.append(prop)

            except Exception as e:
                logger.warning(f"Error parsing purchase card: {e}")

        return listings

    def _fallback_parse(self, soup: BeautifulSoup, mode: str) -> List[Dict]:
        """Fallback parser when specific selectors fail.
        Tries to extract property data from any structured elements on the page.
        """
        properties = []
        # Look for any links that point to property detail pages
        if mode == 'rental':
            links = soup.select('a[href*="/chintai/b-"]')
        else:
            links = soup.select('a[href*="/kodate/b-"]')

        seen_urls = set()
        for link in links:
            href = link.get('href', '')
            if href in seen_urls:
                continue
            seen_urls.add(href)

            name = link.get_text(strip=True)
            if not name or len(name) < 2:
                continue

            url = href if href.startswith('http') else self.BASE_URL + href

            prop = self._make_property_dict(
                listing_type=mode,
                building_name=name,
                url=url,
            )
            properties.append(prop)

        return properties
