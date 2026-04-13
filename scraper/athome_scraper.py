import re
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode

from bs4 import BeautifulSoup
import requests

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class AthomeScraper(BaseScraper):
    """
    Real estate scraper for AtHome (athome.co.jp)
    Supports both rental (chintai) and purchase (kodate) modes across all 47 prefectures.
    """

    BASE_URL = "https://www.athome.co.jp"

    # All 47 Japanese prefectures with their URL paths
    PREFECTURE_PATHS = {
        '北海道': 'hokkaido', '青森県': 'aomori', '岩手県': 'iwate',
        '宮城県': 'miyagi', '秋田県': 'akita', '山形県': 'yamagata',
        '福島県': 'fukushima', '茨城県': 'ibaraki', '栃木県': 'tochigi',
        '群馬県': 'gunma', '埼玉県': 'saitama', '千葉県': 'chiba',
        '東京都': 'tokyo', '神奈川県': 'kanagawa', '新潟県': 'niigata',
        '富e��県': 'toyama', '石川県': 'ishikawa', '福井県': 'fukui',
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
        '東京都': '13', '神奈川県': '14', '新潟県': '15', '富e��県': '16',
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
        """
        Initialize AtHome scraper.

        Args:
            headless: Whether to run browser in headless mode
            timeout: Request timeout in seconds
        """
        super().__init__(site_name='アットホーム')
        self.headless = headless
        self.timeout = timeout

    def scrape(self, conditions: Dict[str, Any], mode: str = None, page: int = 1) -> List[Dict[str, Any]]:
        """
        Scrape AtHome listings for given conditions.

        Args:
            conditions: Dictionary with search criteria:
                - 'prefecture': Prefecture name (e.g., '東京都')
                - 'keyword': Search keyword (optional)
                - 'min_price': Minimum price/rent (optional)
                - 'max_price': Maximum price/rent (optional)
                - 'min_area': Minimum area in sqm (optional)
                - 'max_area': Maximum area in sqm (optional)
                - Other filters as needed
            mode: 'rental' for chintai (賃貸) or 'purchase' for kodate (購入)
            page: Page number to scrape (default: 1)

        Returns:
            List of property dictionaries
        """
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
                response.raise_for_status()
                response.encoding = 'utf-8'
            except requests.RequestException as e:
                logger.error(f"Failed to fetch URL {url}: {e}")
                continue

            soup = BeautifulSoup(response.content, 'html.parser')

            if mode == 'rental':
                all_properties.extend(self._parse_rental_page(soup, conditions))
            else:
                all_properties.extend(self._parse_purchase_page(soup, conditions))

            if pg < max_pages:
                import time
                time.sleep(1)

        return all_properties

    def _build_search_url(self, conditions: Dict[str, Any], mode: str, page: int = 1) -> str:
        """
        Build search URL for AtHome.

        Args:
            conditions: Search conditions
            mode: 'rental' or 'purchase'
            page: Page number

        Returns:
            Complete search URL
        """
        prefecture = conditions.get('prefecture', '')
        pref_path = self.PREFECTURE_PATHS.get(prefecture, '')

        if not pref_path:
            logger.warning(f"Unknown prefecture: {prefecture}")
            pref_path = 'tokyo'  # Default fallback

        mode_path = 'chintai' if mode == 'rental' else 'kodate'
        base_url = f"{self.BASE_URL}/{mode_path}/{pref_path}/"

        params = {}

        # Add keyword if provided
        if conditions.get('keyword'):
            params['keyword'] = conditions['keyword']

        # Add price filters
        if conditions.get('min_price'):
            if mode == 'rental':
                params['rent_min'] = conditions['min_price']
            else:
                params['price_min'] = conditions['min_price']

        if conditions.get('max_price'):
            if mode == 'rental':
                params['rent_max'] = conditions['max_price']
            else:
                params['price_max'] = conditions['max_price']

        # Add area filters
        if conditions.get('min_area'):
            params['area_min'] = conditions['min_area']
        if conditions.get('max_area'):
            params['area_max'] = conditions['max_area']

        # Add page parameter
        if page > 1:
            params['page'] = page

        # Build final URL
        if params:
            return base_url + '?' + urlencode(params)
        return base_url

    def _parse_rental_page(self, soup: BeautifulSoup, conditions: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse rental (chintai) listings from AtHome page.

        Args:
            soup: BeautifulSoup object
            conditions: Search conditions (contains prefecture)

        Returns:
            List of property dictionaries
        """
        properties = []
        prefecture = conditions.get('prefecture', '')

        # Try various selectors for property cards
        selectors = [
            '.cassetteitem',
            '[class*="bukken"]',
            '.property-card',
            '.bukken-card',
            '[class*="property"]',
            'div[data-id]',
        ]

        cards = []
        for selector in selectors:
            cards = soup.select(selector)
            if cards:
                logger.debug(f"Found {len(cards)} cards using selector: {selector}")
                break

        for card in cards:
            try:
                prop = self._extract_rental_property(card, prefecture)
                if prop:
                    properties.append(prop)
            except Exception as e:
                logger.debug(f"Error parsing rental property card: {e}")
                continue

        logger.info(f"Extracted {len(properties)} rental properties")
        return properties

    def _parse_purchase_page(self, soup: BeautifulSoup, conditions: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse purchase (kodate) listings from AtHome page.

        Args:
            soup: BeautifulSoup object
            conditions: Search conditions (contains prefecture)

        Returns:
            List of property dictionaries
        """
        properties = []
        prefecture = conditions.get('prefecture', '')

        # Try various selectors for property cards
        selectors = [
            '.cassetteitem',
            '[class*="bukken"]',
            '.property-card',
            '.bukken-card',
            '[class*="property"]',
            'div[data-id]',
        ]

        cards = []
        for selector in selectors:
            cards = soup.select(selector)
            if cards:
                logger.debug(f"Found {len(cards)} cards using selector: {selector}")
                break

        for card in cards:
            try:
                prop = self._extract_purchase_property(card, prefecture)
                if prop:
                    properties.append(prop)
            except Exception as e:
                logger.debug(f"Error parsing purchase property card: {e}")
                continue

        logger.info(f"Extracted {len(properties)} purchase properties")
        return properties

    def _extract_rental_property(self, card: BeautifulSoup, prefecture: str) -> Optional[Dict[str, Any]]:
        """
        Extract rental property data from a card element.

        Args:
            card: BeautifulSoup card element
            prefecture: Prefecture name

        Returns:
            Property dictionary or None
        """
        prop = self._make_property_dict()
        prop['source'] = 'athome'
        prop['mode'] = 'rental'
        prop['prefecture'] = prefecture
        prop['prefecture_code'] = self.PREFECTURE_CODES.get(prefecture, '')

        # Get all text content
        text = card.get_text()

        # Extract building name
        name_elem = card.select_one('[class*="bukkenname"], .bukken-name, h2, h3')
        if name_elem:
            prop['building_name'] = name_elem.get_text(strip=True)

        # Extract address
        address_elem = card.select_one('[class*="jyusyo"], .address, .jyusyo')
        if address_elem:
            prop['address'] = address_elem.get_text(strip=True)
        else:
            # Try to extract from text
            address_match = re.search(r'[都道府県][^　\n]*[区市町村][^　\n]*', text)
            if address_match:
                prop['address'] = address_match.group(0)

        # Extract layout (間取り) - e.g., 1K, 2LDK, 3LDK
        layout_match = re.search(r'(\d+[A-Z]+|\d+部屋)', text)
        if layout_match:
            prop['layout'] = layout_match.group(1)

        # Extract area (面積) - looking for "○○m²" or "○○平米"
        area_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:㎻|m²|平米)', text)
        if area_match:
            try:
                prop['area'] = float(area_match.group(1))
            except ValueError:
                pass

        # Extract age/construction year
        age_match = re.search(r'築(\d+)年|(\d+)年築', text)
        if age_match:
            year = age_match.group(1) or age_match.group(2)
            prop['age_text'] = f"築{year}年"
            try:
                prop['age_years'] = int(year)
            except ValueError:
                pass

        # Extract rent (賃料) - looking for "○万円/月" or "○○,○○○円"
        rent_match = re.search(r'(\d+(?:\.\d+)?)\s*万円(?:/月)?|(\d+(?:,\d+)*)\s*円', text)
        if rent_match:
            rent_str = rent_match.group(1) or rent_match.group(2).replace(',', '')
            try:
                # If it's in man-yen (万円), convert to yen
                if rent_match.group(1):
                    prop['rent'] = int(float(rent_match.group(1)) * 10000)
                else:
                    prop['rent'] = int(rent_str)
            except ValueError:
                pass

        # Extract management fee (管理費)
        mgmt_match = re.search(r'管理費[:\s]+(\d+(?:,\d+)*)\s*円|管理費[:\s]+(\d+(?:\.\d+)?)\s*万円', text)
        if mgmt_match:
            mgmt_str = mgmt_match.group(1) or mgmt_match.group(2)
            try:
                if mgmt_match.group(2):
                    prop['management_fee'] = int(float(mgmt_match.group(2)) * 10000)
                else:
                    prop['management_fee'] = int(mgmt_str.replace(',', ''))
            except ValueError:
                pass

        # Extract deposit (敷金)
        deposit_match = re.search(r'敷金[:\s]+(\d+(?:,\d+)*)\s*円|敷金[:\s]+(\d+(?:\.\d+)?)\s*万円|敷[\d\.]+', text)
        if deposit_match:
            if deposit_match.group(1):
                try:
                    prop['deposit'] = int(deposit_match.group(1).replace(',', ''))
                except ValueError:
                    pass
            elif deposit_match.group(2):
                try:
                    prop['deposit'] = int(float(deposit_match.group(2)) * 10000)
                except ValueError:
                    pass

        # Extract key money (礼金)
        key_match = re.search(r'礼金[:\s]+(\d+(?:,\d+)*)\s*円|礼金[:\s]+(\d+(?:\.\d+)?)\s*万円|礼[\d\.]+', text)
        if key_match:
            if key_match.group(1):
                try:
                    prop['key_money'] = int(key_match.group(1).replace(',', ''))
                except ValueError:
                    pass
            elif key_match.group(2):
                try:
                    prop['key_money'] = int(float(key_match.group(2)) * 10000)
                except ValueError:
                    pass

        # Extract transport (交通)
        transport_elem = card.select_one('[class*="kotsu"], .transport, .access')
        if transport_elem:
            prop['transport'] = transport_elem.get_text(strip=True)
        else:
            # Try to find from text - look for station names
            transport_match = re.search(r'([ぁ-ん亜-ん一-龥々〆〤ヵヶ]+(?:駅|線).*?)(?=\d+分|$)', text)
            if transport_match:
                prop['transport'] = transport_match.group(1)

        # Extract walk minutes (徒歩○分)
        walk_match = re.search(r'徒歩\s*(\d+)\s*分', text)
        if walk_match:
            try:
                prop['walk_minutes'] = int(walk_match.group(1))
            except ValueError:
                pass

        # Extract URL
        url_elem = card.select_one('a[href*="bukken"], a[href*="chintai"]')
        if url_elem and url_elem.get('href'):
            href = url_elem['href']
            if not href.startswith('http'):
                href = self.BASE_URL + href
            prop['url'] = href

        # Try to extract published date
        pub_match = re.search(r'公開日[:\s]+(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{2}-\d{2})', text)
        if pub_match:
            prop['published_date'] = pub_match.group(1)

        # Try to extract nearest school distance
        school_match = re.search(r'小学校\s*(?:まで\s*)?(\d+)\s*m', text)
        if school_match:
            try:
                prop['nearest_school_distance'] = int(school_match.group(1))
            except ValueError:
                pass

        # Return property if we extracted at least some key data
        if prop.get('building_name') or prop.get('address') or prop.get('rent'):
            return prop

        return None

    def _extract_purchase_property(self, card: BeautifulSoup, prefecture: str) -> Optional[Dict[str, Any]]:
        """
        Extract purchase property data from a card element.

        Args:
            card: BeautifulSoup card element
            prefecture: Prefecture name

        Returns:
            Property dictionary or None
        """
        prop = self._make_property_dict()
        prop['source'] = 'athome'
        prop['mode'] = 'purchase'
        prop['prefecture'] = prefecture
        prop['prefecture_code'] = self.PREFECTURE_CODES.get(prefecture, '')

        # Get all text content
        text = card.get_text()

        # Extract building name
        name_elem = card.select_one('[class*="bukkenname"], .bukken-name, h2, h3')
        if name_elem:
            prop['building_name'] = name_elem.get_text(strip=True)

        # Extract address
        address_elem = card.select_one('[class*="jyusyo"], .address, .jyusyo')
        if address_elem:
            prop['address'] = address_elem.get_text(strip=True)
        else:
            # Try to extract from text
            address_match = re.search(r'[都道府県][^　\n]*[区市町村][^　\n]*', text)
            if address_match:
                prop['address'] = address_match.group(0)

        # Extract layout (間取り) - e.g., 1K, 2LDK, 3LDK
        layout_match = re.search(r'(\d+[A-Z]+|\d+部屋)', text)
        if layout_match:
            prop['layout'] = layout_match.group(1)

        # Extract area (面積) - looking for "○○m²" or "○○平米"
        area_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:㎻|m²|平米)', text)
        if area_match:
            try:
                prop['area'] = float(area_match.group(1))
            except ValueError:
                pass

        # Extract land area (土地面積)
        land_match = re.search(r'土地面積[:\s]+(\d+(?:\.\d+)?)\s*(?:㎡|m²|平米)', text)
        if land_match:
            try:
                prop['land_area'] = float(land_match.group(1))
            except ValueError:
                pass

        # Extract age/construction year
        age_match = re.search(r'築(\d+)年|(\d+)年築', text)
        if age_match:
            year = age_match.group(1) or age_match.group(2)
            prop['age_text'] = f"築{year}年"
            try:
                prop['age_years'] = int(year)
            except ValueError:
                pass

        # Extract price (価格) - in man-yen (万円)
        price_match = re.search(r'(\d+(?:\.\d+)?)\s*万円(?=/日|\s|$)', text)
        if price_match:
            try:
                prop['price'] = float(price_match.group(1))
            except ValueError:
                pass

        # Extract transport (交通)
        transport_elem = card.select_one('[class*="kotsu"], .transport, .access')
        if transport_elem:
            prop['transport'] = transport_elem.get_text(strip=True)
        else:
            # Try to find from text - look for station names
            transport_match = re.search(r'([ぁ-ん亜-ん一-龥々〆〤ヵヶ]+(?:駅|線).*?)(?=\d+分|$)', text)
            if transport_match:
                prop['transport'] = transport_match.group(1)

        # Extract walk minutes (徒歩○分)
        walk_match = re.search(r'徒歩\s*(\d+)\s*分', text)
        if walk_match:
            try:
                prop['walk_minutes'] = int(walk_match.group(1))
            except ValueError:
                pass

        # Extract URL
        url_elem = card.select_one('a[href*="bukken"], a[href*="kodate"]')
        if url_elem and url_elem.get('href'):
            href = url_elem['href']
            if not href.startswith('http'):
                href = self.BASE_URL + href
            prop['url'] = href

        # Try to extract published date
        pub_match = re.search(r'公開日[:\s]+(\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{2}-\d{2})', text)
        if pub_match:
            prop['published_date'] = pub_match.group(1)

        # Try to extract city planning (用途地域)
        zoning_match = re.search(r'用途地域[:\s]+([^\n]+)', text)
        if zoning_match:
            prop['zoning'] = zoning_match.group(1).strip()

        # Try to extract land category (地目)
        category_match = re.search(r'地目[:\s]+([^\n]+)', text)
        if category_match:
            prop['land_category'] = category_match.group(1).strip()

        # Try to extract nearest school distance
        school_match = re.search(r'小学校\s*(?:まで\s*)?(\d+)\s*m', text)
        if school_match:
            try:
                prop['nearest_school_distance'] = int(school_match.group(1))
            except ValueError:
                pass

        # Return property if we extracted at least some key data
        if prop.get('building_name') or prop.get('address') or prop.get('price'):
            return prop

        return None

    def close(self):
        """Close the session."""
        if self.session:
            self.session.close()
