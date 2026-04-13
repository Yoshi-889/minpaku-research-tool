import re
import logging
from typing import Dict, List, Optional
from datetime import datetime
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class SUUMOScraper(BaseScraper):
    """Scraper for SUUMO real estate listings (rental and purchase)."""

    # Region codes mapping (3-digit format used in SUUMO URLs)
    REGION_CODES = {
        '北海道': '010',
        '東北': '020',
        '関東': '030',
        '甲信越・北陸': '040',
        '東海': '050',
        '関西': '060',
        '中国': '070',
        '四国': '080',
        '九州・沖縄': '090',
    }

    # Prefecture codes mapping (all 47 prefectures)
    PREFECTURE_CODES = {
        '北海道': '01', '青森県': '02', '岩手県': '03', '宮城県': '04',
        '秋田県': '05', '山形県': '06', '福島県': '07', '茨城県': '08',
        '栃木県': '09', '群馬県': '10', '埼玉県': '11', '千葉県': '12',
        '東京都': '13', '神奈川県': '14', '新潟県': '15', '富山県': '16',
        '石川県': '17', '福井県': '18', '山梨県': '19', '長野県': '20',
        '岐阜県': '21', '静岡県': '22', '愛知県': '23', '三重県': '24',
        '滋覀県': '25', '京都府': '26', '大阪府': '27', '兵庫県': '28',
        '奈良県': '29', '和歌山県': '30', '鳥取県': '31', '島根県': '32',
        '岡山県': '33', '広島県': '34', '山口県': '35', '徳島県': '36',
        '香川県': '37', '愛媛県': '38', '高知県': '39', '福岡県': '40',
        '佐賀県': '41', '長崎県': '42', '熊本県': '43', '大分県': '44',
        '宮崎県': '45', '鹿児島県': '46', '沖縄県': '47',
    }

    # Prefecture to region mapping
    _PREF_REGION = {
        '北海道': '北海道',
        '青森県': '東北', '岩手県': '東北', '宮城県': '東北',
        '秋田県': '東北', '山形県': '東北', '福島県': '東北',
        '茨城県': '関東', '栃木県': '関東', '群馬県': '関東',
        '埼玉県': '関東', '千葉県': '関東', '東京都': '関東', '神奈川県': '関東',
        '新潟県': '甲信越・北陸', '富山県': '甲信越・北陸', '石川県': '甲信越・北陸',
        '福井県': '甲信越・北陸', '山梨県': '甲信越・北陸', '長野県': '甲信越・北陸',
        '岐阜県': '東海', '静岡県': '東海', '愛知県': '東海', '三重県': '東海',
        '滋覀県': '関西', '京都府': '関西', '大阪府': '関西',
        '兵庫県': '関西', '奈良県': '関西', '和歌山県': '関西',
        '鳥取県': '中国', '島根県': '中国', '岡山県': '中国',
        '広島県': '中国', '山口県': '中国',
        '徳島県': '四国', '香川県': '四国', '愛媛県': '四国', '高知県': '四国',
        '福岡県': '九州・沖縄', '佐賀県': '九州・沖縄', '長崎県': '九已・沖縄',
        '熊本県': '九州・沖縄', '大分県': '九已・沖縄', '宮崎県': '九州・沖縄',
        '鹿児島県': '九已・沖縄', '沖縄県': '九州・沖縄',
    }

    def __init__(self):
        super().__init__(site_name='SUUMO')
        self.source = 'suumo'

    def _get_region_code(self, prefecture: str) -> Optional[str]:
        """Get 3-digit region code from prefecture name."""
        region_name = self._PREF_REGION.get(prefecture)
        if not region_name:
            logger.warning(f"Unknown prefecture: {prefecture}")
            return None
        return self.REGION_CODES.get(region_name)

    def _build_search_url(self, conditions: Dict, mode: str = 'rental', page: int = 1) -> str:
        """Build SUUMO search URL with correct endpoint and parameters."""
        prefecture = conditions.get('prefecture', '')
        city = conditions.get('city', '')
        keyword = conditions.get('keyword', '')

        if not prefecture:
            raise ValueError("Prefecture is required in conditions")

        region_code = self._get_region_code(prefecture)
        pref_code = self.PREFECTURE_CODES.get(prefecture)

        if not region_code or not pref_code:
            raise ValueError(f"Invalid prefecture: {prefecture}")

        # Use city name as keyword filter
        search_keyword = city if city else keyword

        if mode == 'rental':
            base_url = "https://suumo.jp/jj/chintai/ichiran/FR301FC001/"
            params = [
                ('ar', region_code),
                ('bs', '040'),
                ('ta', pref_code),
                ('pc', '50'),
            ]
        else:
            # Purchase (used houses)
            base_url = "https://suumo.jp/jj/bukken/ichiran/JJ010FJ001/"
            params = [
                ('ar', region_code),
                ('bs', '021'),
                ('ta', pref_code),
                ('pc', '50'),
            ]

        if search_keyword:
            params.append(('fw2', search_keyword))

        if page > 1:
            params.append(('pn', str(page)))

        query = '&'.join(f"{k}={quote(str(v))}" for k, v in params)
        return f"{base_url}?{query}"

    def scrape(self, conditions: Dict, mode: str = None) -> List[Dict]:
        """Scrape SUUMO listings.

        Args:
            conditions: Search conditions dict with prefecture, city, etc.
            mode: 'rental' or 'purchase' (default from conditions or 'rental')
        """
        if mode is None:
            mode = conditions.get('mode', 'rental')

        max_pages = conditions.get('max_pages', 3)
        properties = []

        for page in range(1, max_pages + 1):
            url = self._build_search_url(conditions, mode=mode, page=page)
            logger.info(f"Scraping {mode} page {page} from: {url}")

            try:
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                response.encoding = 'utf-8'
            except Exception as e:
                logger.error(f"Failed to fetch {url}: {e}")
                break

            soup = BeautifulSoup(response.text, 'html.parser')

            if mode == 'rental':
                page_props = self._parse_rental_listings(soup, url)
            else:
                page_props = self._parse_purchase_listings(soup, url)

            if not page_props:
                logger.info(f"No listings found on page {page}, stopping.")
                break

            properties.extend(page_props)
            logger.info(f"Page {page}: found {len(page_props)} listings")

        logger.info(f"Total: {len(properties)} properties found from SUUMO")
        return properties

    def _parse_rental_listings(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Parse rental listings from SUUMO search results page."""
        properties = []
        items = soup.select('.cassetteitem')

        for item in items:
            try:
                # Building info
                title_el = item.select_one('.cassetteitem_content-title')
                building_name = title_el.get_text(strip=True) if title_el else ''

                label_el = item.select_one('.cassetteitem_content-label span')
                building_type = label_el.get_text(strip=True) if label_el else ''

                body_items = item.select('.cassetteitem_content-body li')
                address = body_items[0].get_text(strip=True) if len(body_items) > 0 else ''
                transport = body_items[1].get_text(strip=True) if len(body_items) > 1 else ''
                age_info = body_items[2].get_text(strip=True) if len(body_items) > 2 else ''

                # Parse age
                age_years = self._parse_age(age_info)
                age_text = ''
                if age_years is not None:
                    age_text = f"築{age_years}年"
                elif '新築' in age_info:
                    age_text = '新築'
                    age_years = 0

                # Parse walk minutes from transport
                walk_minutes = self._parse_walk_minutes(transport)

                # Room rows from table
                rows = item.select('table tbody tr')
                for row in rows:
                    rent_el = row.select_one('.cassetteitem_price--rent')
                    admin_el = row.select_one('.cassetteitem_price--administration')
                    deposit_el = row.select_one('.cassetteitem_price--deposit')
                    gratuity_el = row.select_one('.cassetteitem_price--gratuity')
                    layout_el = row.select_one('.cassetteitem_madori')
                    area_el = row.select_one('.cassetteitem_menseki')

                    rent_text = rent_el.get_text(strip=True) if rent_el else ''
                    admin_text = admin_el.get_text(strip=True) if admin_el else ''
                    deposit_text = deposit_el.get_text(strip=True) if deposit_el else ''
                    key_money_text = gratuity_el.get_text(strip=True) if gratuity_el else ''
                    layout = layout_el.get_text(strip=True) if layout_el else ''
                    area_text = area_el.get_text(strip=True) if area_el else ''

                    # Parse numeric values
                    rent = self._parse_price(rent_text)
                    management_fee = self._parse_price(admin_text)
                    area = self._parse_area(area_text)

                    # Get detail link
                    link_el = row.select_one('a[href*="/chintai/"]')
                    prop_url = ''
                    if link_el and link_el.get('href'):
                        href = link_el['href']
                        if not href.startswith('http'):
                            prop_url = urljoin('https://suumo.jp', href)
                        else:
                            prop_url = href

                    prop = self._make_property_dict(
                        listing_type='rental',
                        building_name=building_name,
                        address=self._normalize_address(address),
                        transport=transport,
                        age=age_years,
                        age_text=age_text,
                        rent=rent,
                        management_fee=management_fee,
                        deposit=deposit_text,
                        key_money=key_money_text,
                        layout=layout,
                        area=area,
                        walk_minutes=walk_minutes,
                        url=prop_url,
                    )
                    properties.append(prop)

            except Exception as e:
                logger.warning(f"Error parsing cassetteitem: {e}")
                continue

        return properties

    def _parse_purchase_listings(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Parse purchase listings from SUUMO search results page."""
        properties = []

        # Purchase pages may use different container classes
        items = soup.select('.cassetteitem') or soup.select('.property_unit')

        for item in items:
            try:
                text = item.get_text()

                # Title / building name
                title_el = item.select_one('a[href*="/tochi/"], a[href*="/kodate/"], a[href*="/chukoikkodate/"], a')
                building_name = ''
                prop_url = ''
                if title_el:
                    building_name = title_el.get_text(strip=True)[:80]
                    href = title_el.get('href', '')
                    if href:
                        prop_url = urljoin('https://suumo.jp', href) if not href.startswith('http') else href

                # Address
                address = ''
                address_match = re.search(
                    r'((?:北海道|(?:東京|京都|大阪)府|.{2,3}県).+?(?:市|区|町|村)\S*)',
                    text
                )
                if address_match:
                    address = address_match.group(1)

                # Price
                price = self._parse_price_yen(text)

                # Area
                area = self._parse_area(text)

                # Land area
                land_area = None
                land_match = re.search(r'土地面積\s*([\d.]+)\s*m[²㎡]', text)
                if land_match:
                    land_area = float(land_match.group(1))

                # Layout
                layout = ''
                layout_match = re.search(r'(\d[A-Z]*(?:SLDK|LDK|DK|K))', text)
                if layout_match:
                    layout = layout_match.group(1)

                # Age
                age_years = self._parse_age(text)
                age_text = f"築{age_years}年" if age_years is not None else ''

                # Transport
                transport = ''
                transport_match = re.search(r'(.+?(?:騅|停留所)\s*(?:歩|徒歩)?\s*\d+分)', text)
                if transport_match:
                    transport = transport_match.group(1).strip()

                walk_minutes = self._parse_walk_minutes(text)

                prop = self._make_property_dict(
                    listing_type='purchase',
                    building_name=building_name,
                    address=self._normalize_address(address),
                    transport=transport,
                    age=age_years,
                    age_text=age_text,
                    price=price,
                    layout=layout,
                    area=area,
                    land_area=land_area,
                    walk_minutes=walk_minutes,
                    url=prop_url,
                )
                properties.append(prop)

            except Exception as e:
                logger.debug(f"Error parsing purchase card: {e}")

        return properties

    def extract_detail_info(self, property_dict: Dict, html: str) -> Dict:
        """Extract additional details from property detail page."""
        # Published date
        pub_match = re.search(
            r'(?:情報公開日|情報登録日|掲載開始日)[：:\s]*(\d{4}[年/]\d{1,2}[月/]\d{1,2})',
            html
        )
        if pub_match:
            property_dict['published_date'] = pub_match.group(1)

        # Next update date
        next_match = re.search(
            r'(?:次回更新予定日|情報更新日)[：:\s]*(\d{4}[年/]\d{1,2}[月/]\d{1,2})',
            html
        )
        if next_match:
            property_dict['next_update_date'] = next_match.group(1)

        # City planning
        cp_match = re.search(r'都市計画[：:\s]*([^\n<]+)', html)
        if cp_match:
            property_dict['city_planning'] = cp_match.group(1).strip()

        # Zoning
        zoning_match = re.search(r'用途地域[：:\s]*([^\n<]+)', html)
        if zoning_match:
            property_dict['zoning'] = zoning_match.group(1).strip()

        # Land category
        land_match = re.search(r'地目[：:\s]*([^\n<]+)', html)
        if land_match:
            property_dict['land_category'] = land_match.group(1).strip()

        # School distance
        school_match = re.search(r'小学校[：:\s]*([^\n<]+)', html)
        if school_match:
            property_dict['nearest_school_distance'] = school_match.group(1).strip()

        return property_dict


# Alias for main.py compatibility
SuumoScraper = SUUMOScraper
