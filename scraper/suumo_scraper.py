"""SUUMO scraper for rental properties."""
import re
from typing import List, Dict, Optional
from datetime import datetime
from .base_scraper import BaseScraper


class SuumoScraper(BaseScraper):
    """Scraper for SUUMO rental property listings."""

    # SUUMO area region codes
    REGION_CODES = {
        '010': ['北海道'],
        '020': ['青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県'],
        '030': ['茨城県', '栃木県', '群馬県'],
        '040': ['埼玉県', '千葉県', '東京都', '神奈巜県'],
        '050': ['新潟県', '富山県', '石巜県', '福井県', '山梨県', '長野県'],
        '060': ['岐阜県', '静岡県', '愛知県', '三重県'],
        '070': ['滋賀県', '京都府', '大阪府', '兵庫県', '奈良県', '和歌山県'],
        '080': ['鳥取県', '島根県', '岡山県', '広島県', '山口県', '徳島県', '香川県', '愛媛県', '高知県'],
        '090': ['福岡県', '佐賀県', '長崎県', '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県'],
    }

    # Prefecture name -> JIS code (ta parameter)
    PREFECTURE_CODES = {
        '北海道': '01', '青森県': '02', '岩手県': '03', '宮城県': '04',
        '秋田県': '05', '山形県': '06', '福島県': '07', '茨城県': '08',
        '栃木県': '09', '群馬県': '10', '埼玉県': '11', '千葉県': '12',
        '東京都': '13', '神奈巜県': '14', '新潟県': '15', '富山県': '16',
        '石巜県': '17', '福井県': '18', '山梨県': '19', '長野県': '20',
        '岐阜県': '21', '静岡県': '22', '愛知県': '23', '三重県': '24',
        '滋賀県': '25', '京都府': '26', '大阪府': '27', '兵庫県': '28',
        '奈良県': '29', '和歌山県': '30', '鳥取県': '31', '島根県': '32',
        '岡山県': '33', '広島県': '34', '山口県': '35', '徳島県': '36',
        '香巜県': '37', '愛媛県': '38', '高知県': '39', '福岡県': '40',
        '佐賀県': '41', '長崎県': '42', '熊本県': '43', '大分県': '44',
        '宮崎県': '45', '鹿児島県': '46', '沖縄県': '47',
    }

    @classmethod
    def _get_region(cls, prefecture: str) -> str:
        """Get SUUMO region code from prefecture name."""
        for region, prefs in cls.REGION_CODES.items():
            if prefecture in prefs:
                return region
        return '040'  # default: Kanto

    def __init__(self):
        super().__init__('SUUMO')
        self.base_url = 'https://suumo.jp'

    def _build_search_url(self, conditions: Dict, page: int = 1) -> str:
        """Build SUUMO search URL from conditions."""
        prefecture = conditions.get('prefecture', '東京都')
        city = conditions.get('city', '')

        ta_code = self.PREFECTURE_CODES.get(prefecture, '13')
        ar_code = self._get_region(prefecture)

        params = {
            'ar': ar_code,
            'bs': '040',  # rental
            'ta': ta_code,
            'cb': conditions.get('rent_min', '0.0'),
            'ct': conditions.get('rent_max', '9999999'),
            'et': conditions.get('walk_max', '9999999'),
            'cn': '9999999',
            'mb': conditions.get('area_min', '0'),
            'mt': conditions.get('area_max', '9999999'),
            'shkr1': '03',
            'shkr2': '03',
            'shkr3': '03',
            'shkr4': '03',
            'fw2': '',
        }

        # Add city keyword search if specified
        if city and city.strip():
            params['fw2'] = city.strip()

        if page > 1:
            params['pn'] = str(page)

        param_str = '&'.join(f'{k}={v}' for k, v in params.items())
        return f'{self.base_url}/jj/chintai/ichiran/FR301FC001/?{param_str}'

    def scrape(self, conditions: Dict) -> List[Dict]:
        """Scrape SUUMO rental listings."""
        all_properties = []
        page = 1
        max_pages = conditions.get('max_pages', 5)

        while page <= max_pages:
            url = self._build_search_url(conditions, page)
            soup = self._fetch_page(url)

            if soup is None:
                break

            # Find property cassette items
            cassettes = soup.select('.cassetteitem')
            if not cassettes:
                # Try alternative selectors
                cassettes = soup.select('div[class*="cassetteitem"]')

            if not cassettes:
                self.logger.info(f"No more properties found on page {page}")
                break

            self.logger.info(f"Found {len(cassettes)} buildings on page {page}")

            for cassette in cassettes:
                properties = self._parse_cassette(cassette)
                all_properties.extend(properties)

            # Check for next page
            pagination = soup.select('.pagination-parts a')
            has_next = False
            for link in pagination:
                if link.get_text(strip=True) == '次へ':
                    has_next = True
                    break

            if not has_next:
                break

            page += 1

        self.logger.info(f"Total properties scraped from SUUMO: {len(all_properties)}")
        return all_properties

    def _parse_cassette(self, cassette) -> List[Dict]:
        """Parse a cassette item (building) into individual room listings."""
        properties = []

        # Building-level info
        building_name = ''
        name_el = cassette.select_one('.cassetteitem_content-title')
        if name_el:
            building_name = name_el.get_text(strip=True)

        address = ''
        address_el = cassette.select_one('.cassetteitem_detail-col1')
        if address_el:
            address = address_el.get_text(strip=True)

        # Transport info
        transport_list = []
        transport_els = cassette.select('.cassetteitem_detail-col2 .cassetteitem_detail-text')
        for t in transport_els:
            transport_list.append(t.get_text(strip=True))
        transport_text = ' / '.join(transport_list) if transport_list else ''

        # Building age and floors
        age_text = ''
        col3 = cassette.select_one('.cassetteitem_detail-col3')
        if col3:
            divs = col3.select('div')
            for div in divs:
                text = div.get_text(strip=True)
                if '築' in text or '新築' in text:
                    age_text = text
                    break

        # Parse individual rooms (table rows)
        table_rows = cassette.select('.js-cassette_link')
        if not table_rows:
            table_rows = cassette.select('table tbody tr')

        for row in table_rows:
            prop = self._parse_room_row(row, building_name, address, transport_text, age_text)
            if prop:
                properties.append(prop)

        # If no table rows found, create a single entry from building info
        if not properties and building_name:
            prop = {
                'site': 'SUUMO',
                'building_name': building_name,
                'address': address,
                'transport': transport_text,
                'rent': None,
                'management_fee': None,
                'deposit': None,
                'key_money': None,
                'layout': '',
                'area': None,
                'age': self._parse_age(age_text),
                'age_text': age_text,
                'floor': '',
                'walk_minutes': self._parse_walk_minutes(transport_text),
                'url': '',
                'scraped_at': datetime.now().isoformat(),
            }
            properties.append(prop)

        return properties

    def _parse_room_row(self, row, building_name: str, address: str,
                        transport_text: str, age_text: str) -> Optional[Dict]:
        """Parse a single room row from the table."""
        try:
            # Floor
            floor = ''
            floor_el = row.select_one('td:nth-of-type(3)')
            if floor_el:
                floor = floor_el.get_text(strip=True)

            # Rent
            rent = None
            rent_el = row.select_one('.cassetteitem_price--rent')
            if rent_el:
                rent = self._parse_price(rent_el.get_text(strip=True))

            # Management fee
            mgmt_fee = None
            mgmt_el = row.select_one('.cassetteitem_price--administration')
            if mgmt_el:
                mgmt_fee = self._parse_price(mgmt_el.get_text(strip=True))

            # Deposit
            deposit = None
            dep_el = row.select_one('.cassetteitem_price--deposit')
            if dep_el:
                deposit = dep_el.get_text(strip=True)

            # Key money
            key_money = None
            key_el = row.select_one('.cassetteitem_price--gratuity')
            if key_el:
                key_money = key_el.get_text(strip=True)

            # Layout
            layout = ''
            layout_el = row.select_one('.cassetteitem_madori')
            if layout_el:
                layout = layout_el.get_text(strip=True)

            # Area
            area = None
            area_el = row.select_one('.cassetteitem_menseki')
            if area_el:
                area = self._parse_area(area_el.get_text(strip=True))

            # URL
            url = ''
            link_el = row.select_one('a[href*="/chintai/"]')
            if link_el:
                href = link_el.get('href', '')
                if href.startswith('/'):
                    url = self.base_url + href
                else:
                    url = href

            return {
                'site': 'SUUMO',
                'building_name': building_name,
                'address': address,
                'transport': transport_text,
                'rent': rent,
                'management_fee': mgmt_fee,
                'deposit': deposit if deposit else '',
                'key_money': key_money if key_money else '',
                'layout': layout,
                'area': area,
                'age': self._parse_age(age_text),
                'age_text': age_text,
                'floor': floor,
                'walk_minutes': self._parse_walk_minutes(transport_text),
                'url': url,
                'scraped_at': datetime.now().isoformat(),
            }
        except Exception as e:
            self.logger.error(f"Error parsing room row: {e}")
            return None
