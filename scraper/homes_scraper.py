"""LIFULL HOME'S scraper for rental properties."""
import re
from typing import List, Dict, Optional
from datetime import datetime
from .base_scraper import BaseScraper


class HomesScraper(BaseScraper):
    """Scraper for LIFULL HOME'S rental property listings."""

    CITY_PATHS = {
        'é¿èå¸': 'aso-city',
        'çæ¬å¸ä¸­å¤®åº': 'kumamoto-chuou-city',
        'çæ¬å¸æ±åº': 'kumamoto-higashi-city',
        'åé¿èæ': 'minamiaso-town',
    }

    def __init__(self):
        super().__init__("LIFULL HOME'S")
        self.base_url = 'https://www.homes.co.jp'

    def _build_search_url(self, conditions: Dict, page: int = 1) -> str:
        """Build HOME'S search URL."""
        prefecture = conditions.get('prefecture', 'çæ¬ç')
        city = conditions.get('city', 'é¿èå¸')

        pref_path = 'kumamoto'  # Default
        city_path = self.CITY_PATHS.get(city, 'aso-city')

        url = f'{self.base_url}/chintai/{pref_path}/{city_path}/list/'

        params = []
        if conditions.get('rent_min'):
            params.append(f"priceMin={int(float(conditions['rent_min']) * 10000)}")
        if conditions.get('rent_max'):
            params.append(f"priceMax={int(float(conditions['rent_max']) * 10000)}")
        if conditions.get('area_min'):
            params.append(f"areaMin={conditions['area_min']}")

        if page > 1:
            params.append(f"page={page}")

        if params:
            url += '?' + '&'.join(params)

        return url

    def scrape(self, conditions: Dict) -> List[Dict]:
        """Scrape HOME'S rental listings."""
        all_properties = []
        page = 1
        max_pages = conditions.get('max_pages', 5)

        while page <= max_pages:
            url = self._build_search_url(conditions, page)
            soup = self._fetch_page(url)

            if soup is None:
                break

            # Find property modules
            modules = soup.select('.mod-mergeBuilding')
            if not modules:
                modules = soup.select('[class*="mod-mergeBuilding"]')
            if not modules:
                # Try alternative: individual property cards
                modules = soup.select('.prg-building')

            if not modules:
                self.logger.info(f"No more properties found on page {page}")
                break

            self.logger.info(f"Found {len(modules)} buildings on page {page}")

            for module in modules:
                properties = self._parse_building(module)
                all_properties.extend(properties)

            # Check for next page
            next_link = soup.select_one('.pagination a[rel="next"]')
            if not next_link:
                next_link = soup.select_one('a.nextPage')
            if not next_link:
                # Also check text-based pagination
                pagers = soup.select('.mod-pagination a')
                has_next = False
                for p in pagers:
                    if 'æ¬¡ã¸' in p.get_text():
                        has_next = True
                        break
                if not has_next:
                    break
            page += 1

        self.logger.info(f"Total properties scraped from HOME'S: {len(all_properties)}")
        return all_properties

    def _parse_building(self, module) -> List[Dict]:
        """Parse a building module into property listings."""
        properties = []

        # Building name
        building_name = ''
        name_el = module.select_one('.prg-buildingName, .bukkenName, h2 a, h3 a')
        if name_el:
            building_name = name_el.get_text(strip=True)

        # Address
        address = ''
        addr_el = module.select_one('.prg-address, [class*="address"]')
        if addr_el:
            address = addr_el.get_text(strip=True)
        else:
            # Try to find from text content
            text = module.get_text()
            match = re.search(r'æå¨å°\s*(çæ¬ç[^\säº¤é]+)', text)
            if match:
                address = match.group(1).strip()

        # Transport
        transport = ''
        transport_el = module.select_one('.prg-route, [class*="traffic"], [class*="transport"]')
        if transport_el:
            transport = transport_el.get_text(strip=True)
        else:
            text = module.get_text()
            match = re.search(r'äº¤é\s*([^\sç¯å¹´]+)', text)
            if match:
                transport = match.group(1).strip()

        # Age
        age_text = ''
        age_el = module.select_one('.prg-age, [class*="age"]')
        if age_el:
            age_text = age_el.get_text(strip=True)
        else:
            text = module.get_text()
            match = re.search(r'ç¯å¹´æ°/éæ°\s*([^\sé]+)', text)
            if match:
                age_text = match.group(1).strip()

        # Parse individual rooms
        room_rows = module.select('table tbody tr')
        if not room_rows:
            room_rows = module.select('.prg-roomTable tr, .mod-roomList tr')

        for row in room_rows:
            prop = self._parse_room(row, building_name, address, transport, age_text)
            if prop and prop.get('rent'):
                properties.append(prop)

        # If no room rows, try to parse the module as a whole
        if not properties:
            text = module.get_text()
            # Try extracting rent from text
            rent_match = re.search(r'([\d.]+)\s*ä¸å', text)
            if rent_match and building_name:
                # Management fee
                mgmt_match = re.search(r'/\s*([\d,]+)\s*å', text)
                mgmt_fee = None
                if mgmt_match:
                    mgmt_fee = float(mgmt_match.group(1).replace(',', '')) / 10000

                # Area
                area_match = re.search(r'([\d.]+)\s*mÂ²', text)
                area = float(area_match.group(1)) if area_match else None

                # Layout
                layout_match = re.search(r'(\d[LDKS]{1,4})', text)
                layout = layout_match.group(1) if layout_match else ''

                prop = {
                    'site': "LIFULL HOME'S",
                    'building_name': building_name,
                    'address': address,
                    'transport': transport,
                    'rent': float(rent_match.group(1)),
                    'management_fee': mgmt_fee,
                    'deposit': '',
                    'key_money': '',
                    'layout': layout,
                    'area': area,
                    'age': self._parse_age(age_text),
                    'age_text': age_text,
                    'floor': '',
                    'walk_minutes': self._parse_walk_minutes(transport),
                    'url': '',
                    'scraped_at': datetime.now().isoformat(),
                }
                properties.append(prop)

        return properties

    def _parse_room(self, row, building_name: str, address: str,
                    transport: str, age_text: str) -> Optional[Dict]:
        """Parse a room row."""
        try:
            cells = row.select('td')
            if len(cells) < 4:
                return None

            text = row.get_text()

            # Rent
            rent = None
            rent_match = re.search(r'([\d.]+)\s*ä¸å', text)
            if rent_match:
                rent = float(rent_match.group(1))

            if not rent:
                return None

            # Management fee
            mgmt_fee = None
            mgmt_match = re.search(r'/\s*([\d,]+)\s*å', text)
            if mgmt_match:
                mgmt_fee = float(mgmt_match.group(1).replace(',', '')) / 10000

            # Area
            area = None
            area_match = re.search(r'([\d.]+)\s*mÂ²', text)
            if area_match:
                area = float(area_match.group(1))

            # Layout
            layout = ''
            layout_match = re.search(r'(\d[LDKS]{1,4})', text)
            if layout_match:
                layout = layout_match.group(1)

            # Floor
            floor = ''
            floor_match = re.search(r'(\d+)\s*é', text)
            if floor_match:
                floor = floor_match.group(0)

            # Deposit / Key money
            deposit = ''
            key_money = ''
            dep_match = re.search(r'æ·é[/:]?\s*([\d.]+ä¸å|ç¡)', text)
            if dep_match:
                deposit = dep_match.group(1)
            key_match = re.search(r'ç¤¼é[/:]?\s*([\d.]+ä¸å|ç¡|\d+ã¶æ)', text)
            if key_match:
                key_money = key_match.group(1)

            # URL
            url = ''
            link = row.select_one('a[href]')
            if link:
                href = link.get('href', '')
                if href.startswith('/'):
                    url = self.base_url + href
                elif href.startswith('http'):
                    url = href

            return {
                'site': "LIFULL HOME'S",
                'building_name': building_name,
                'address': address,
                'transport': transport,
                'rent': rent,
                'management_fee': mgmt_fee,
                'deposit': deposit,
                'key_money': key_money,
                'layout': layout,
                'area': area,
                'age': self._parse_age(age_text),
                'age_text': age_text,
                'floor': floor,
                'walk_minutes': self._parse_walk_minutes(transport),
                'url': url,
                'scraped_at': datetime.now().isoformat(),
            }
        except Exception as e:
            self.logger.error(f"Error parsing room: {e}")
            return None
