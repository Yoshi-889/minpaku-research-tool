import logging
from typing import Dict, List, Optional
from datetime import datetime
from bs4 import BeautifulSoup
import requests

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class HomesScraper(BaseScraper):
    """
    Scraper for LIFULL HOME'S real estate portal.
    Supports both rental (chintai) and purchase (kodate) modes for all 47 prefectures.
    """

    BASE_URL = "https://www.homes.co.jp"

    # All 47 Japanese prefectures with URL path segments
    PREFECTURE_PATHS = {
        '北海道': 'hokkaido',
        '青森県': 'aomori',
        '岩手県': 'iwate',
        '宮城県': 'miyagi',
        '秋田県': 'akita',
        '山形県': 'yamagata',
        '福島県': 'fukushima',
        '茨城県': 'ibaraki',
        '栃木県': 'tochigi',
        '群馬県': 'gunma',
        '埼玉県': 'saitama',
        '千葉県': 'chiba',
        '東京都': 'tokyo',
        '神奈川県': 'kanagawa',
        '新潟県': 'niigata',
        '富山県': 'toyama',
        '石川県': 'ishikawa',
        '福井県': 'fukui',
        '山梨県': 'yamanashi',
        '長野県': 'nagano',
        '岐阜県': 'gifu',
        '静岡県': 'shizuoka',
        '愛知県': 'aichi',
        '三重県': 'mie',
        '滋賀県': 'shiga',
        '京都府': 'kyoto',
        '大阪府': 'osaka',
        '兵庫県': 'hyogo',
        '奈良県': 'nara',
        '和歌山県': 'wakayama',
        '鳥取県': 'tottori',
        '島根県': 'shimane',
        '岡山県': 'okayama',
        '広島県': 'hiroshima',
        '山口県': 'yamaguchi',
        '徳島県': 'tokushima',
        '香川県': 'kagawa',
        '愛媛県': 'ehime',
        '高知県': 'kochi',
        '福岡県': 'fukuoka',
        '佐賀県': 'saga',
        '長崎県': 'nagasaki',
        '熊本県': 'kumamoto',
        '大分県': 'oita',
        '宮崎県': 'miyazaki',
        '鹿児島県': 'kagoshima',
        '沖縄県': 'okinawa',
    }

    def __init__(self, headless: bool = True, timeout: int = 10):
        """Initialize the LIFULL HOME'S scraper."""
        super().__init__(site_name='LIFULL HOME\'S')
        self.headless = headless
        self.timeout = timeout
        self.site_name = "LIFULL HOME'S"

    def _get_prefecture_path(self, prefecture: str) -> str:
        """
        Get URL path segment for given prefecture.

        Args:
            prefecture: Prefecture name in Japanese (e.g., '東京都')

        Returns:
            URL path segment (e.g., 'tokyo')

        Raises:
            ValueError: If prefecture not found
        """
        if prefecture not in self.PREFECTURE_PATHS:
            raise ValueError(
                f"Prefecture '{prefecture}' not found. "
                f"Valid prefectures: {', '.join(self.PREFECTURE_PATHS.keys())}"
            )
        return self.PREFECTURE_PATHS[prefecture]

    def _build_search_url(
        self,
        conditions: Dict,
        mode: str = 'rental',
        page: int = 1
    ) -> str:
        """
        Build search URL for rental or purchase mode.

        Args:
            conditions: Search conditions dict with 'prefecture' and optionally 'keyword'
            mode: 'rental' or 'purchase'
            page: Page number (1-indexed)

        Returns:
            Full search URL with query parameters

        Raises:
            ValueError: If mode is invalid or required conditions missing
        """
        if mode not in ['rental', 'purchase']:
            raise ValueError(f"Mode must be 'rental' or 'purchase', got '{mode}'")

        if 'prefecture' not in conditions:
            raise ValueError("'prefecture' is required in conditions")

        pref_path = self._get_prefecture_path(conditions['prefecture'])

        # Build base URL based on mode
        if mode == 'rental':
            url = f"{self.BASE_URL}/chintai/{pref_path}/list/"
        else:  # purchase
            url = f"{self.BASE_URL}/kodate/b-{pref_path}/list/"

        # Add keyword if provided
        params = {}
        if 'keyword' in conditions and conditions['keyword']:
            params['key'] = conditions['keyword']

        # Add page parameter if not first page
        if page > 1:
            params['page'] = page

        # Build query string
        if params:
            query_string = '&'.join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query_string}"

        return url

    def scrape(self, conditions: Dict, mode: str = 'rental') -> List[Dict]:
        """
        Scrape real estate listings from LIFULL HOME'S.

        Args:
            conditions: Search conditions with 'prefecture' and optional 'keyword'
            mode: 'rental' or 'purchase' (default: 'rental')

        Returns:
            List of property dictionaries with standardized fields

        Raises:
            ValueError: If invalid mode or missing required conditions
        """
        if mode not in ['rental', 'purchase']:
            raise ValueError(f"Mode must be 'rental' or 'purchase', got '{mode}'")

        listings = []
        page = 1
        max_pages = conditions.get('max_pages', 5)

        try:
            while page <= max_pages:
                url = self._build_search_url(conditions, mode, page)
                logger.info(f"Scraping {mode} listings from: {url}")

                try:
                    response = requests.get(
                        url,
                        headers=self.headers,
                        timeout=self.timeout
                    )
                    response.raise_for_status()
                except requests.RequestException as e:
                    logger.error(f"Failed to fetch page {page}: {e}")
                    break

                soup = BeautifulSoup(response.content, 'html.parser')

                # Parse listings based on mode
                if mode == 'rental':
                    page_listings = self._scrape_rental_page(soup, conditions)
                else:
                    page_listings = self._scrape_purchase_page(soup, conditions)

                if not page_listings:
                    logger.info(f"No listings found on page {page}, stopping.")
                    break

                listings.extend(page_listings)
                logger.info(f"Found {len(page_listings)} listings on page {page}")

                page += 1

        except Exception as e:
            logger.error(f"Error during scraping: {e}")

        logger.info(f"Total listings scraped: {len(listings)}")
        return listings

    def _scrape_rental_page(self, soup: BeautifulSoup, conditions: Dict) -> List[Dict]:
        """
        Parse rental listings from page soup.

        Args:
            soup: BeautifulSoup object of rental listings page
            conditions: Search conditions

        Returns:
            List of rental property dictionaries
        """
        listings = []

        # Find building blocks (typically contain multiple rooms)
        building_elements = soup.find_all('div', class_='bukkenbox')

        for building_el in building_elements:
            try:
                building_info = self._parse_rental_building(building_el)
                if not building_info:
                    continue

                # Find room elements within building
                room_elements = building_el.find_all('div', class_='heyadiv')

                if room_elements:
                    # Multiple rooms in one building
                    for room_el in room_elements:
                        try:
                            room_data = self._parse_rental_room(room_el, building_info)
                            if room_data:
                                listings.append(room_data)
                        except Exception as e:
                            logger.warning(f"Error parsing rental room: {e}")
                else:
                    # No separate room elements, treat building as single listing
                    listings.append(building_info)

            except Exception as e:
                logger.warning(f"Error parsing rental building: {e}")

        return listings

    def _parse_rental_building(self, building_el) -> Optional[Dict]:
        """
        Parse rental building/property information.

        Args:
            building_el: BeautifulSoup element for building

        Returns:
            Dictionary with building information or None if parsing fails
        """
        try:
            # Extract building name
            name_el = building_el.find('a', class_='bukkenname')
            if not name_el:
                return None

            name = name_el.get_text(strip=True)

            # Extract address
            address_el = building_el.find('span', class_='address')
            address = address_el.get_text(strip=True) if address_el else None

            # Extract building details
            details_el = building_el.find('div', class_='gaiyou')
            building_type = None
            age = None
            layout = None

            if details_el:
                details_text = details_el.get_text()
                # Try to extract building type, age, layout from details
                # Format may vary, this is a best-effort extraction
                parts = [p.strip() for p in details_text.split('・')]
                if len(parts) > 0:
                    building_type = parts[0]
                if len(parts) > 1:
                    age = parts[1]
                if len(parts) > 2:
                    layout = parts[2]

            # Extract image URL
            img_el = building_el.find('img', class_='bukkenphoto')
            image_url = img_el.get('src') if img_el else None

            building_info = {
                'name': name,
                'address': address,
                'building_type': building_type,
                'age': age,
                'layout': layout,
                'image_url': image_url,
            }

            return building_info

        except Exception as e:
            logger.warning(f"Error parsing rental building details: {e}")
            return None

    def _parse_rental_room(self, room_el, building_info: Dict) -> Optional[Dict]:
        """
        Parse rental room information.

        Args:
            room_el: BeautifulSoup element for room
            building_info: Building information dictionary

        Returns:
            Standardized property dictionary or None if parsing fails
        """
        try:
            # Extract room details (price, floor, etc.)
            price_el = room_el.find('span', class_='yachin')
            price_text = price_el.get_text(strip=True) if price_el else None
            price = self._parse_price(price_text)

            # Extract room layout/spec
            spec_el = room_el.find('span', class_='madori')
            layout = spec_el.get_text(strip=True) if spec_el else building_info.get('layout')

            # Extract floor info
            floor_el = room_el.find('span', class_='kai')
            floor = floor_el.get_text(strip=True) if floor_el else None

            # Extract area
            area_el = room_el.find('span', class_='menseki')
            area_text = area_el.get_text(strip=True) if area_el else None
            area = self._parse_area(area_text)

            # Extract nearest station info
            station_el = room_el.find('span', class_='station')
            nearest_station = None
            nearest_station_distance = None

            if station_el:
                station_text = station_el.get_text(strip=True)
                # Parse station name and distance (e.g., "渋谷駅 徒歩5分")
                parts = station_text.split()
                if len(parts) >= 1:
                    nearest_station = parts[0]
                if len(parts) >= 2:
                    nearest_station_distance = parts[1]

            property_dict = self._make_property_dict(
                url=room_el.find('a').get('href') if room_el.find('a') else None,
                title=building_info.get('name'),
                address=building_info.get('address'),
                price=price,
                price_unit='万円' if price else None,
                layout=layout,
                area_sqm=area,
                building_type=building_info.get('building_type'),
                age=building_info.get('age'),
                floor=floor,
                nearest_station=nearest_station,
                nearest_station_distance=nearest_station_distance,
                image_url=building_info.get('image_url'),
                mode='rental',
            )

            return property_dict

        except Exception as e:
            logger.warning(f"Error parsing rental room: {e}")
            return None

    def _scrape_purchase_page(self, soup: BeautifulSoup, conditions: Dict) -> List[Dict]:
        """
        Parse purchase listings from page soup.

        Args:
            soup: BeautifulSoup object of purchase listings page
            conditions: Search conditions

        Returns:
            List of purchase property dictionaries
        """
        listings = []

        # Find property cards (typically class='property' or 'bukkencard')
        card_elements = soup.find_all('div', class_=['bukkencard', 'property'])

        for card_el in card_elements:
            try:
                property_data = self._parse_purchase_card(card_el)
                if property_data:
                    listings.append(property_data)
            except Exception as e:
                logger.warning(f"Error parsing purchase card: {e}")

        return listings

    def _parse_purchase_card(self, card_el) -> Optional[Dict]:
        """
        Parse purchase property card information.

        Args:
            card_el: BeautifulSoup element for property card

        Returns:
            Standardized property dictionary or None if parsing fails
        """
        try:
            # Extract property name/title
            title_el = card_el.find('a', class_='bukkenname')
            if not title_el:
                title_el = card_el.find('a')
            title = title_el.get_text(strip=True) if title_el else None
            url = title_el.get('href') if title_el else None

            # Extract price (万円)
            price_el = card_el.find('span', class_='price')
            if not price_el:
                price_el = card_el.find('span', class_='kakaku')
            price_text = price_el.get_text(strip=True) if price_el else None
            price = self._parse_price(price_text)

            # Extract address
            address_el = card_el.find('span', class_='address')
            address = address_el.get_text(strip=True) if address_el else None

            # Extract building area (建物面積)
            building_area_el = card_el.find('span', class_='tatemonomenseki')
            building_area_text = building_area_el.get_text(strip=True) if building_area_el else None
            building_area = self._parse_area(building_area_text)

            # Extract land area (土地面積)
            land_area_el = card_el.find('span', class_='tochimenseki')
            land_area_text = land_area_el.get_text(strip=True) if land_area_el else None
            land_area = self._parse_area(land_area_text)

            # Extract age (築年月日)
            age_el = card_el.find('span', class_='age')
            age = age_el.get_text(strip=True) if age_el else None

            # Extract layout (間取り)
            layout_el = card_el.find('span', class_='madori')
            layout = layout_el.get_text(strip=True) if layout_el else None

            # Extract nearest station
            station_el = card_el.find('span', class_='station')
            nearest_station = None
            nearest_station_distance = None

            if station_el:
                station_text = station_el.get_text(strip=True)
                parts = station_text.split()
                if len(parts) >= 1:
                    nearest_station = parts[0]
                if len(parts) >= 2:
                    nearest_station_distance = parts[1]

            # Extract published date
            published_date = None
            date_el = card_el.find('span', class_='published_date')
            if date_el:
                published_date = date_el.get_text(strip=True)

            # Extract next update date
            next_update_date = None
            update_el = card_el.find('span', class_='next_update_date')
            if update_el:
                next_update_date = update_el.get_text(strip=True)

            # Extract city planning (都市計画)
            city_planning = None
            planning_el = card_el.find('span', class_='city_planning')
            if planning_el:
                city_planning = planning_el.get_text(strip=True)

            # Extract zoning (用途地域)
            zoning = None
            zoning_el = card_el.find('span', class_='zoning')
            if zoning_el:
                zoning = zoning_el.get_text(strip=True)

            # Extract land category (地目)
            land_category = None
            category_el = card_el.find('span', class_='land_category')
            if category_el:
                land_category = category_el.get_text(strip=True)

            # Extract image URL
            img_el = card_el.find('img')
            image_url = img_el.get('src') if img_el else None

            property_dict = self._make_property_dict(
                url=url,
                title=title,
                address=address,
                price=price,
                price_unit='万円' if price else None,
                layout=layout,
                building_area_sqm=building_area,
                land_area_sqm=land_area,
                age=age,
                nearest_station=nearest_station,
                nearest_station_distance=nearest_station_distance,
                image_url=image_url,
                mode='purchase',
                published_date=published_date,
                next_update_date=next_update_date,
                city_planning=city_planning,
                zoning=zoning,
                land_category=land_category,
            )

            return property_dict

        except Exception as e:
            logger.warning(f"Error parsing purchase card: {e}")
            return None

    def _parse_price(self, price_text: Optional[str]) -> Optional[float]:
        """
        Parse price from text (handle 万円 format).

        Args:
            price_text: Price text (e.g., "10万円", "1,500万円")

        Returns:
            Numeric price value or None
        """
        if not price_text:
            return None

        try:
            # Remove 万円 and other non-numeric characters except decimal point
            cleaned = price_text.replace('万円', '').replace(',', '').strip()
            if cleaned:
                return float(cleaned)
        except ValueError:
            logger.warning(f"Could not parse price: {price_text}")

        return None

    def _parse_area(self, area_text: Optional[str]) -> Optional[float]:
        """
        Parse area from text (handle m² format).

        Args:
            area_text: Area text (e.g., "50.5m²", "50.5㎡")

        Returns:
            Numeric area value or None
        """
        if not area_text:
            return None

        try:
            # Remove m², ㎡ and other non-numeric characters except decimal point
            cleaned = area_text.replace('m²', '').replace('㎡', '').replace(',', '').strip()
            if cleaned:
                return float(cleaned)
        except ValueError:
            logger.warning(f"Could not parse area: {area_text}")

        return None
