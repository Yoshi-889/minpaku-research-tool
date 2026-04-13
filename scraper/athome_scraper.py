"""AtHome scraper for rental properties."""
import re
from typing import List, Dict, Optional
from datetime import datetime
from .base_scraper import BaseScraper


class AthomeScraper(BaseScraper):
    """Scraper for AtHome rental property listings."""

    PREFECTURE_PATHS = {
        '北海道': 'hokkaido', '青森県': 'aomori', '岩手県': 'iwate', '宮城県': 'miyagi',
        '秋田県': 'akita', '山形県': 'yamagata', '福島県': 'fukushima', '茨城県': 'ibaraki',
        '栃木県': 'tochigi', '群馬県': 'gunma', '埼玉県': 'saitama', '千葉県': 'chiba',
        '東京都': 'tokyo', '神奈川県': 'kanagawa', '新潟県': 'niigata', '富山県': 'toyama',
        '石川県': 'ishikawa', '福井県': 'fukui', '山梨県': 'yamanashi', '長野県': 'nagano',
        '岐阜県': 'gifu', '静岡県': 'shizuoka', '愛知県': 'aichi', '三重県': 'mie',
        '滋賀県': 'shiga', '京都府': 'kyoto', '大阪府': 'osaka', '兵庫県': 'hyogo',
        '奈良県': 'nara', '和歌山県': 'wakayama', '鳥取県': 'tottori', '島根県': 'shimane',
        '岡山県': 'okayama', '広島県': 'hiroshima', '山口県': 'yamaguchi', '徳島県': 'tokushima',
        '香川県': 'kagawa', '愛媛県': 'ehime', '高知県': 'kochi', '福岡県': 'fukuoka',
        '佐賀県': 'saga', '長崎県': 'nagasaki', '犊本県': 'kumamoto', '大分県': 'oita',
        '宮崎県': 'miyazaki', '鹿児島県': 'kagoshima', '沖縄県': 'okinawa',
    }

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
        '佐賀県': '41', '長崎県': '42', '犊本県': '43', '大分県': '44',
        '宮崎県': '45', '鹿児島県': '46', '沖縄県': '47',
    }

    def __init__(self):
        super().__init__('アットホーム')
        self.base_url = 'https://www.athome.co.jp'

    def _build_search_url(self, conditions: Dict, page: int = 1) -> str:
        """Build AtHome search URL."""
        prefecture = conditions.get('prefecture', '東京都')
        city = conditions.get('city', '')

        pref_path = self.PREFECTURE_PATHS.get(prefecture, 'tokyo')
        pref_code = self.PREFECTURE_CODES.get(prefecture, '13')

        # Use prefecture-level search URL
        url = f'{self.base_url}/chintai/{pref_path}/'

        params = {}
        if conditions.get('rent_min'):
            params['priceFrom'] = str(int(float(conditions['rent_min']) * 10000))
        if conditions.get('rent_max'):
            params['priceTo'] = str(int(float(conditions['rent_max']) * 10000))
        if conditions.get('area_min'):
            params['areaFrom'] = str(conditions['area_min'])

        # Add city keyword
        if city and city.strip():
            params['keyword'] = city.strip()

        if page > 1:
            params['page'] = str(page)

        if params:
            param_str = '&'.join(f'{k}={v}' for k, v in params.items())
            url += '?' + param_str

        return url

    def scrape(self, conditions: Dict) -> List[Dict]:
        """Scrape AtHome rental listings."""
        all_properties = []
        max_pages = conditions.get('max_pages', 3)

        for page in range(1, max_pages + 1):
            url = self._build_search_url(conditions, page)
            soup = self._fetch_page(url)

            if soup is None:
                break

            properties = self._parse_listing_page(soup)
            if not properties:
                self.logger.info(f"No more properties found on page {page}")
                break

            all_properties.extend(properties)
            self.logger.info(f"Found {len(properties)} properties on page {page}")

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
                match = re.search(r'(.+?[都道府県].+?[市区町村郡][^\s\n]*)', text)
                if match:
                    address = match.group(1)

            # Transport
            transport = ''
            trans_el = card.select_one('[class*="traffic"], [class*="access"]')
            if trans_el:
                transport = trans_el.get_text(strip=True)
            else:
                match = re.search(r'(JR[^\n]+分)', text)
                if match:
                    transport = match.group(1)

            # Rent
            rent = None
            rent_match = re.search(r'([\d.]+)\s*万円', text)
            if rent_match:
                rent = float(rent_match.group(1))

            # Management fee
            mgmt_fee = None
            mgmt_match = re.search(r'管理費[等]?\s*([\d,]+)\s*円', text)
            if not mgmt_match:
                mgmt_match = re.search(r'/\s*([\d,]+)\s*円', text)
            if mgmt_match:
                mgmt_fee = float(mgmt_match.group(1).replace(',', '')) / 10000

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

            # Age
            age_text = ''
            age_match = re.search(r'(新築|築\d+年)', text)
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
                'site': 'アットホーム',
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
            rent_match = re.search(r'([\d.]+)\s*万円', text)
            if not rent_match:
                return None

            return self._parse_property_card(row)
        except Exception:
            return None
