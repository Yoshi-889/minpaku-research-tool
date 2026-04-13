"""SUUMO scraper for rental properties."""
import re
from typing import List, Dict, Optional
from datetime import datetime
from .base_scraper import BaseScraper


class SuumoScraper(BaseScraper):
    """Scraper for SUUMO rental property listings."""

    # Area codes for SUUMO
    PREFECTURE_CODES = {
        'çæ¬ç': {'ar': '090', 'ta': '43'},
        'ç¦å²¡ç': {'ar': '090', 'ta': '40'},
        'å¤§åç': {'ar': '090', 'ta': '44'},
    }

    # City codes for SUUMO (sc parameter)
    CITY_CODES = {
        'é¿èå¸': '43214',
        'çæ¬å¸ä¸­å¤®åº': '43101',
        'çæ¬å¸æ±åº': '43102',
        'çæ¬å¸è¥¿åº': '43103',
        'çæ¬å¸ååº': '43104',
        'çæ¬å¸ååº': '43105',
    }

    def __init__(self):
        super().__init__('SUUMO')
        self.base_url = 'https://suumo.jp'

    def _build_search_url(self, conditions: Dict, page: int = 1) -> str:
        """Build SUUMO search URL from conditions."""
        prefecture = conditions.get('prefecture', 'çæ¬ç')
        city = conditions.get('city', 'é¿èå¸')

        pref_code = self.PREFECTURE_CODES.get(prefecture, self.PREFECTURE_CODES['çæ¬ç'])
        city_code = self.CITY_CODES.get(city, self.CITY_CODES['é¿èå¸'])

        params = {
            'ar': pref_code['ar'],
            'bs': '040',  # rental
            'ta': pref_code['ta'],
            'sc': city_code,
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
                if link.get_text(strip=True) == 'æ¬¡ã¸':
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
                if 'ç¯' in text or 'æ°ç¯' in text:
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
