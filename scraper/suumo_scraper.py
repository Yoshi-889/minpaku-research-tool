import re
import logging
from typing import Dict, List, Optional
from datetime import datetime
from urllib.parse import urljoin
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class SUUMOScraper(BaseScraper):
    """Scraper for SUUMO real estate listings (rental and purchase)."""

    # Region codes mapping (9 regions)
    REGION_CODES = {
        '北海道': '01',
        '東北': '02',
        '関東': '03',
        '甲信越・北陸': '04',
        '東海': '05',
        '関西': '06',
        '中国': '07',
        '四国': '08',
        '九州・沖縄': '09',
    }

    # Prefecture codes mapping (all 47 prefectures)
    PREFECTURE_CODES = {
        '北海道': '01',
        '青森県': '02',
        '岩手県': '03',
        '宮城県': '04',
        '秋田県': '05',
        '山形県': '06',
        '福島県': '07',
        '茨城県': '08',
        '栃木県': '09',
        '群馬県': '10',
        '埼玉県': '11',
        '千葉県': '12',
        '東京都': '13',
        '神奈川県': '14',
        '新潟県': '15',
        '富山県': '16',
        '石川県': '17',
        '福井県': '18',
        '山梨県': '19',
        '長野県': '20',
        '岐阜県': '21',
        '静岡県': '22',
        '愛知県': '23',
        '三重県': '24',
        '滋賀県': '25',
        '京都府': '26',
        '大阪府': '27',
        '兵庫県': '28',
        '奈良県': '29',
        '和歌山県': '30',
        '鳥取県': '31',
        '島根県': '32',
        '岡山県': '33',
        '広島県': '34',
        '山口県': '35',
        '徳島県': '36',
        '香川県': '37',
        '愛媛県': '38',
        '高知県': '39',
        '福岡県': '40',
        '佐賀県': '41',
        '長崎県': '42',
        '熊本県': '43',
        '大分県': '44',
        '宮崎県': '45',
        '鹿児島県': '46',
        '沖縄県': '47',
    }

    # Prefecture to region mapping
    _PREF_REGION = {
        '北海道': '北海道',
        '青森県': '東北',
        '岩手県': '東北',
        '宮城県': '東北',
        '秋田県': '東北',
        '山形県': '東北',
        '福島県': '東北',
        '茨城県': '関東',
        '栃木県': '関東',
        '群馬県': '関東',
        '埼玉県': '関東',
        '千葉県': '関東',
        '東京都': '関東',
        '神奈川県': '関東',
        '新潟県': '甲信越・北陸',
        '富山県': '甲信越・北陸',
        '石川県': '甲信越・北陸',
        '福���県': '甲信越・北陸',
        '山梨県': '甲信越・北陸',
        '長野県': '甲信越・北陸',
        '岐阜県': '東海',
        '静岡県': '東海',
        '愛知県': '東海',
        '三重県': '東海',
        '滋賀県': '関西',
        '京都府': '関西',
        '大阪府': '関西',
        '兵庫県': '関西',
        '奈良県': '関西',
        '和歌山県': '関西',
        '鳥取県': '中国',
        '島根県': '中国',
        '岡山県': '中国',
        '広島県': '中国',
        '山口県': '中国',
        '徳島県': '四国',
        '香川県': '四国',
        '愛媛県': '四国',
        '高知県': '四国',
        '福岡県': '九州・沖縄',
        '佐賀県': '九州・沖縄',
        '長崎県': '九州・沖縄',
        '熊本県': '九州・沖縄',
        '大分県': '九州・沖縄',
        '宮崎県': '九州・沖縄',
        '鹿児島県': '九州・沖縄',
        '沖縄県': '九州・沖縄',
    }

    def __init__(self):
        super().__init__()
        self.source = 'suumo'

    def _get_region(self, prefecture: str) -> Optional[str]:
        """Get region code from prefecture name."""
        if prefecture not in self._PREF_REGION:
            logger.warning(f"Unknown prefecture: {prefecture}")
            return None
        region_name = self._PREF_REGION[prefecture]
        return self.REGION_CODES.get(region_name)

    def _build_search_url(self, conditions: Dict, mode: str = 'rental') -> str:
        """
        Build search URL for SUUMO.

        Args:
            conditions: Search conditions dict with 'prefecture', 'keyword', etc.
            mode: 'rental' or 'purchase'

        Returns:
            URL string for search
        """
        prefecture = conditions.get('prefecture', '')
        keyword = conditions.get('keyword', '')

        if not prefecture:
            raise ValueError("Prefecture is required in conditions")

        # Get region and prefecture codes
        region_code = self._get_region(prefecture)
        pref_code = self.PREFECTURE_CODES.get(prefecture)

        if not region_code or not pref_code:
            raise ValueError(f"Invalid prefecture: {prefecture}")

        if mode == 'rental':
            # Rental URL: https://suumo.jp/chintai/{region}/
            base_url = f"https://suumo.jp/chintai/{region_code}/"
            params = {
                'ar': region_code,
                'ta': pref_code,
                'fw2': keyword if keyword else '',
            }
            # Build query string
            query_parts = [f"{k}={v}" for k, v in params.items() if v]
            url = base_url + ('?' + '&'.join(query_parts) if query_parts else '')
            return url

        elif mode == 'purchase':
            # Purchase URL: https://suumo.jp/jj/bukken/ichiran/JJ010FJ001/
            base_url = "https://suumo.jp/jj/bukken/ichiran/JJ010FJ001/"
            params = {
                'ar': region_code,
                'bs': '021',  # 中古一戸建て (used houses)
                'ta': pref_code,
                'fw2': keyword if keyword else '',
            }
            # Build query string
            query_parts = [f"{k}={v}" for k, v in params.items() if v]
            url = base_url + ('?' + '&'.join(query_parts) if query_parts else '')
            return url

        else:
            raise ValueError(f"Invalid mode: {mode}. Must be 'rental' or 'purchase'")

    def scrape(self, conditions: Dict, mode: str = 'rental') -> List[Dict]:
        """
        Scrape SUUMO listings.

        Args:
            conditions: Search conditions dict with:
                - prefecture: Prefecture name (required)
                - keyword: Search keyword (optional)
            mode: 'rental' or 'purchase' (default: 'rental')

        Returns:
            List of property dictionaries
        """
        url = self._build_search_url(conditions, mode=mode)
        logger.info(f"Scraping {mode} listings from: {url}")

        try:
            response = self.session.get(url)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return []

        properties = []

        if mode == 'rental':
            properties = self._parse_rental_listings(response.text, url)
        elif mode == 'purchase':
            properties = self._parse_purchase_listings(response.text, url)

        logger.info(f"Found {len(properties)} properties")
        return properties

    def _parse_rental_listings(self, html: str, base_url: str) -> List[Dict]:
        """Parse rental listings from HTML."""
        properties = []

        # Parse cassettes (property cards)
        cassette_pattern = r'<div class="cassette[^"]*"[^>]*>.*?</div>(?=\s*<div class="cassette|\s*$)'
        cassettes = re.findall(cassette_pattern, html, re.DOTALL | re.IGNORECASE)

        for cassette_html in cassettes:
            try:
                prop = self._parse_room_row(cassette_html, base_url)
                if prop:
                    prop['listing_type'] = 'rental'
                    properties.append(prop)
            except Exception as e:
                logger.warning(f"Error parsing cassette: {e}")

        return properties

    def _parse_purchase_listings(self, html: str, base_url: str) -> List[Dict]:
        """Parse purchase listings from HTML."""
        properties = []

        # Parse property cards from purchase listings
        # Look for property containers in the purchase page
        card_pattern = r'<div class="[^"]*bukken[^"]*"[^>]*>.*?</div>(?=\s*<div class=|</div>\s*</|$)'
        cards = re.findall(card_pattern, html, re.DOTALL | re.IGNORECASE)

        if not cards:
            # Try alternative pattern for property listings
            card_pattern = r'<div class="[^"]*object[^"]*"[^>]*>.*?(?=<div class=|$)'
            cards = re.findall(card_pattern, html, re.DOTALL | re.IGNORECASE)

        for card_html in cards:
            try:
                prop = self._parse_purchase_card(card_html, base_url)
                if prop:
                    prop['listing_type'] = 'purchase'
                    properties.append(prop)
            except Exception as e:
                logger.debug(f"Error parsing purchase card: {e}")

        return properties

    def _parse_room_row(self, cassette_html: str, base_url: str) -> Optional[Dict]:
        """
        Parse a single rental listing (cassette).

        Returns a property dictionary with:
        - building_name, address, layout, area, rent, deposit, key_money, etc.
        """
        prop = {}

        # Extract building name
        name_match = re.search(r'<a[^>]*class="[^"]*cassette_title[^"]*"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', cassette_html)
        if name_match:
            prop['building_name'] = name_match.group(2).strip()
            prop_url = name_match.group(1)
            prop['url'] = urljoin(base_url, prop_url) if not prop_url.startswith('http') else prop_url

        # Extract address
        address_match = re.search(r'<span class="[^"]*cassette_location[^"]*"[^>]*>([^<]*)</span>', cassette_html)
        if address_match:
            prop['address'] = address_match.group(1).strip()

        # Extract layout (e.g., "1LDK")
        layout_match = re.search(r'>(\d[A-Z]*(?:LDK|DK|K)?)<', cassette_html)
        if layout_match:
            prop['layout'] = layout_match.group(1).strip()

        # Extract area (建物面積)
        area_match = re.search(r'(\d+(?:\.\d+)?)\s*m[²m]', cassette_html)
        if area_match:
            prop['area'] = area_match.group(1)

        # Extract rent price (賃料)
        rent_match = re.search(r'(\d+(?:,\d+)?)\s*万円|(\d+(?:,\d+)?)\s*円', cassette_html)
        if rent_match:
            price_str = rent_match.group(1) or rent_match.group(2)
            prop['rent'] = price_str.replace(',', '')

        # Extract deposit (敷金) and key money (礼金) if present
        deposit_match = re.search(r'敷金[:：]?\s*(\d+(?:,\d+)?)', cassette_html)
        if deposit_match:
            prop['deposit'] = deposit_match.group(1).replace(',', '')

        key_money_match = re.search(r'礼金[:：]?\s*(\d+(?:,\d+)?)', cassette_html)
        if key_money_match:
            prop['key_money'] = key_money_match.group(1).replace(',', '')

        # Extract transport/access info
        transport_match = re.search(r'<span class="[^"]*cassette_station[^"]*"[^>]*>([^<]*)</span>', cassette_html)
        if transport_match:
            prop['transport'] = transport_match.group(1).strip()

        # Extract age/building age info
        age_match = re.search(r'築(\d+)年', cassette_html)
        if age_match:
            prop['age_text'] = f"築{age_match.group(1)}年"

        # Set empty strings for optional detail fields
        prop['published_date'] = ''
        prop['next_update_date'] = ''
        prop['nearest_school_distance'] = ''
        prop['city_planning'] = ''
        prop['zoning'] = ''
        prop['land_category'] = ''

        return self._make_property_dict(prop, listing_type='rental')

    def _parse_purchase_card(self, card_html: str, base_url: str) -> Optional[Dict]:
        """
        Parse a single purchase listing card.

        Returns a property dictionary with:
        - price, building_name, address, area, land_area, age_text, layout, transport, url
        """
        prop = {}

        # Extract property name/title
        name_match = re.search(r'<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', card_html)
        if name_match:
            prop['building_name'] = name_match.group(2).strip()
            prop_url = name_match.group(1)
            prop['url'] = urljoin(base_url, prop_url) if not prop_url.startswith('http') else prop_url

        # Extract address
        address_match = re.search(r'<span[^>]*>([^<]*(?:県|都|道|府)[^<]*)</span>', card_html)
        if address_match:
            prop['address'] = address_match.group(1).strip()

        # Extract price (万円 or 億円)
        price_match = re.search(r'(\d+(?:,\d+)?)\s*億\s*(\d+(?:,\d+)?)?万円|(\d+(?:,\d+)?)\s*万円', card_html)
        if price_match:
            if price_match.group(1):  # 億 format
                oku = price_match.group(1).replace(',', '')
                man = price_match.group(2).replace(',', '') if price_match.group(2) else '0'
                prop['price'] = f"{oku}0000{man}"
            else:  # 万円 format
                prop['price'] = price_match.group(3).replace(',', '')

        # Extract building area (建物面積)
        area_match = re.search(r'建物面積[:：]?\s*(\d+(?:\.\d+)?)\s*m[²m]|(\d+(?:\.\d+)?)\s*m[²m]', card_html)
        if area_match:
            prop['area'] = area_match.group(1) or area_match.group(2)

        # Extract land area (土地面積)
        land_area_match = re.search(r'土地面積[:：]?\s*(\d+(?:\.\d+)?)\s*m[²m]', card_html)
        if land_area_match:
            prop['land_area'] = land_area_match.group(1)

        # Extract building age
        age_match = re.search(r'築(\d+)年', card_html)
        if age_match:
            prop['age_text'] = f"築{age_match.group(1)}年"

        # Extract layout (間取り)
        layout_match = re.search(r'>(\d[A-Z]*(?:LDK|DK|K)?)<', card_html)
        if layout_match:
            prop['layout'] = layout_match.group(1).strip()

        # Extract transport/access info
        transport_match = re.search(r'<span[^>]*>([^<]*(?:駅|停留所)[^<]*)</span>', card_html)
        if transport_match:
            prop['transport'] = transport_match.group(1).strip()

        # Set empty strings for optional detail fields
        prop['published_date'] = ''
        prop['next_update_date'] = ''
        prop['nearest_school_distance'] = ''
        prop['city_planning'] = ''
        prop['zoning'] = ''
        prop['land_category'] = ''

        return self._make_property_dict(prop, listing_type='purchase')

    def extract_detail_info(self, property_dict: Dict, html: str) -> Dict:
        """
        Extract additional details from property detail page.

        Updates property_dict with:
        - published_date, next_update_date, nearest_school_distance
        - city_planning, zoning, land_category
        """
        # Extract published date (情報公開日/情報登録日/掲載開始日)
        pub_date_match = re.search(
            r'(?:情報公開日|情報登録日|掲載開始日)[:：]?\s*(\d{4}[年/]\d{1,2}[月/]\d{1,2})',
            html
        )
        if pub_date_match:
            property_dict['published_date'] = pub_date_match.group(1)

        # Extract next update date (次回更新予定日/情報更新日)
        next_update_match = re.search(
            r'(?:次回更新予定日|情報更新日)[:：]?\s*(\d{4}[年/]\d{1,2}[月/]\d{1,2})',
            html
        )
        if next_update_match:
            property_dict['next_update_date'] = next_update_match.group(1)

        # Extract nearest school distance (小学校)
        school_match = re.search(r'小学校[:：]?\s*([^<\n]+(?:\d+[km])?)', html)
        if school_match:
            property_dict['nearest_school_distance'] = school_match.group(1).strip()

        # Extract city planning (都市計画)
        city_planning_match = re.search(r'都市計画[:：]?\s*([^<\n]+)', html)
        if city_planning_match:
            property_dict['city_planning'] = city_planning_match.group(1).strip()

        # Extract zoning (用途地域)
        zoning_match = re.search(r'用途地域[:：]?\s*([^<\n]+)', html)
        if zoning_match:
            property_dict['zoning'] = zoning_match.group(1).strip()

        # Extract land category (地目)
        land_cat_match = re.search(r'地目[:：]?\s*([^<\n]+)', html)
        if land_cat_match:
            property_dict['land_category'] = land_cat_match.group(1).strip()

        return property_dict


# Alias for main.py compatibility
SuumoScraper = SUUMOScraper
