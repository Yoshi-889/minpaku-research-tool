北海道青森県岩手県宮城県秋田県山形県福島県茨城県栃木県群馬県埼玉県千葉県東京都神奈川県新潟県富山県石川県福井県山梨県長野県岐阜県静岡県愛知県三重県滋賀県京都府大阪府兵庫県奈良県和歌山県鳥取県島根県岡山県広島県山口県徳島県香川県愛媛県高知県福岡県佐賀県長崎県熊本県大分県宮崎県鹿児島県沖縄県北海道青森県岩手県宮城県秋田県山形県福島県茨城県栃木県群馬県埼玉県千葉県東京都神奈川県新潟県富山県石川県福井県山梨県長野県岐阜県静岡県愛知県三重県滋賀県京都府大阪府兵庫県奈良県和歌山県鳥取県島根県岡山県広島県山口県徳島県香川県愛媛県高知県福岡県佐賀県長崎県熊本県大分県宮崎県鹿児島県沖縄県アットホーム東京都都道府県市区町村郡分万円管理費等円円²㎡新築築年アットホーム万円"""AtHome scraper for rental properties."""
import re
from typing import List, Dict, Optional
from datetime import datetime
from .base_scraper import BaseScraper


class AthomeScraper(BaseScraper):
    """Scraper for AtHome rental property listings."""

    CITY_CODES = {
        'é¿èå¸': '43214',
        'çæ¬å¸ä¸­å¤®åº': '43101',
        'çæ¬å¸æ±åº': '43102',
        'åé¿èæ': '43432',
    }

    def __init__(self):
        super().__init__('ã¢ãããã¼ã ')
        self.base_url = 'https://www.athome.co.jp'

    def _build_search_url(self, conditions: Dict, page: int = 1) -> str:
        """Build AtHome search URL."""
        city = conditions.get('city', 'é¿èå¸')
        city_code = self.CITY_CODES.get(city, '43214')

        # AtHome uses a keyword-based search URL pattern
        url = f'{self.base_url}/chintai/theme/list/'

        params = {
            'areaCode': city_code,
            'prefCode': '43',  # Kumamoto
            'type': '9',  # Rental
        }

        if conditions.get('rent_min'):
            params['priceFrom'] = str(int(float(conditions['rent_min']) * 10000))
        if conditions.get('rent_max'):
            params['priceTo'] = str(int(float(conditions['rent_max']) * 10000))
        if conditions.get('area_min'):
            params['areaFrom'] = str(conditions['area_min'])

        if page > 1:
            params['page'] = str(page)

        param_str = '&'.join(f'{k}={v}' for k, v in params.items())
        return f'{url}?{param_str}'

    def scrape(self, conditions: Dict) -> List[Dict]:
        """Scrape AtHome rental listings."""
        all_properties = []
        page = 1
        max_pages = conditions.get('max_pages', 3)

        # Try direct area search first
        city = conditions.get('city', 'é¿èå¸')
        # AtHome URL patterns can vary; try multiple patterns
        urls_to_try = [
            f'{self.base_url}/chintai/kumamoto/aso-city/list/',
            f'{self.base_url}/chintai/kumamoto/aso-shi/list/',
        ]

        for base_search_url in urls_to_try:
            soup = self._fetch_page(base_search_url)
            if soup and 'è¦ã¤ããã¾ãã' not in soup.get_text():
                self.logger.info(f"Found working URL: {base_search_url}")
                properties = self._parse_listing_page(soup)
                all_properties.extend(properties)

                # Paginate
                for pg in range(2, max_pages + 1):
                    next_url = f"{base_search_url}?page={pg}"
                    soup = self._fetch_page(next_url)
                    if soup and 'è¦ã¤ããã¾ãã' not in soup.get_text():
                        props = self._parse_listing_page(soup)
                        if not props:
                            break
                        all_properties.extend(props)
                    else:
                        break
                break

        self.logger.info(f"Total properties scraped from AtHome: {len(all_properties)}")
        return all_properties

    def _parse_listing_page(self, soup) -> List[Dict]:
        """Parse a listing page for properties."""
        properties = []

        # AtHome uses various class patterns for property cards
        cards = soup.select('.p-property, .property-data, [class*="bukkenBlock"]')
        if not cards:
            cards = soup.select('article, .p-item, [data-prop-id]')
        if not cards:
            # Try to parse from table-like structure
            tables = soup.select('table.result-list, table.bukken-table')
            for table in tables:
                rows = table.select('tr')
                for row in rows:
                    prop = self._parse_table_row(row)
                    if prop:
                        properties.append(prop)
            return properties

        for card in cards:
            prop = self._parse_property_card(card)
            if prop and prop.get('rent'):
                properties.append(prop)

        return properties

    def _parse_property_card(self, card) -> Optional[Dict]:
        """Parse a single property card."""
        try:
            text = card.get_text()

            # Building name
            building_name = ''
            name_el = card.select_one('h2, h3, .p-property-title, [class*="name"]')
            if name_el:
                building_name = name_el.get_text(strip=True)

            # Address
            address = ''
            addr_el = card.select_one('[class*="address"], [class*="area"]')
            if addr_el:
                address = addr_el.get_text(strip=True)
            else:
                match = re.search(r'(çæ¬ç[^\s\n]+)', text)
                if match:
                    address = match.group(1)

            # Transport
            transport = ''
            trans_el = card.select_one('[class*="traffic"], [class*="access"]')
            if trans_el:
                transport = trans_el.get_text(strip=True)
            else:
                match = re.search(r'(JR[^\n]+å)', text)
                if match:
                    transport = match.group(1)

            # Rent
            rent = None
            rent_match = re.search(r'([\d.]+)\s*ä¸å', text)
            if rent_match:
                rent = float(rent_match.group(1))

            # Management fee
            mgmt_fee = None
            mgmt_match = re.search(r'ç®¡çè²»[ç­]?\s*([\d,]+)\s*å', text)
            if not mgmt_match:
                mgmt_match = re.search(r'/\s*([\d,]+)\s*å', text)
            if mgmt_match:
                mgmt_fee = float(mgmt_match.group(1).replace(',', '')) / 10000

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

            # Age
            age_text = ''
            age_match = re.search(r'(æ°ç¯|ç¯\d+å¹´)', text)
            if age_match:
                age_text = age_match.group(1)

            # URL
            url = ''
            link = card.select_one('a[href*="/chintai/"]')
            if link:
                href = link.get('href', '')
                if href.startswith('/'):
                    url = self.base_url + href
                elif href.startswith('http'):
                    url = href

            return {
                'site': 'ã¢ãããã¼ã ',
                'building_name': building_name,
                'address': address,
                'transport': transport,
                'rent': rent,
                'management_fee': mgmt_fee,
                'deposit': '',
                'key_money': '',
                'layout': layout,
                'area': area,
                'age': self._parse_age(age_text),
                'age_text': age_text,
                'floor': '',
                'walk_minutes': self._parse_walk_minutes(transport) or self._parse_walk_minutes(text),
                'url': url,
                'scraped_at': datetime.now().isoformat(),
            }
        except Exception as e:
            self.logger.error(f"Error parsing property card: {e}")
            return None

    def _parse_table_row(self, row) -> Optional[Dict]:
        """Parse a table row format property."""
        try:
            text = row.get_text()
            rent_match = re.search(r'([\d.]+)\s*ä¸å', text)
            if not rent_match:
                return None

            return self._parse_property_card(row)
        except Exception:
            return None
