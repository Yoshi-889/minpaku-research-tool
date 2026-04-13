"""Data cleaning, deduplication, and integration utilities."""
import re
import pandas as pd
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


def normalize_address(address: str) -> str:
    """Normalize address for comparison."""
    if not address:
        return ""
    # Full-width to half-width
    table = str.maketrans(
        '０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ',
        '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    )
    address = address.translate(table)
    address = re.sub(r'[\s　]+', '', address)
    # Remove common suffixes
    address = re.sub(r'番地?$', '', address)
    return address


def remove_duplicates(properties: List[Dict], rent_tolerance: float = 0.05,
                      area_tolerance: float = 2.0) -> List[Dict]:
    """Remove duplicate properties across sites.

    Dedup logic:
    - Same normalized address AND same layout → likely same property
    - Same building name AND similar rent (±5%) AND similar area (±2㎡) → likely same
    """
    if not properties:
        return []

    df = pd.DataFrame(properties)
    df['_norm_addr'] = df['address'].apply(normalize_address)
    df['_norm_name'] = df['building_name'].apply(
        lambda x: re.sub(r'[\s　\u3000]+', '', str(x).lower()) if x else ''
    )

    # Mark duplicates
    seen = set()
    keep_indices = []

    for idx, row in df.iterrows():
        # Create a fingerprint
        addr = row['_norm_addr']
        name = row['_norm_name']
        layout = str(row.get('layout', '')).strip()
        rent = row.get('rent')
        area = row.get('area')

        # Key 1: Address + Layout
        key1 = f"{addr}_{layout}" if addr and layout else None

        # Key 2: Building name + approximate rent + approximate area
        key2 = None
        if name and rent:
            rent_rounded = round(rent * 2) / 2  # Round to 0.5万円
            area_rounded = round(area / 5) * 5 if area else 0  # Round to 5㎡
            key2 = f"{name}_{rent_rounded}_{area_rounded}"

        is_dup = False
        if key1 and key1 in seen:
            is_dup = True
        if key2 and key2 in seen:
            is_dup = True

        if not is_dup:
            keep_indices.append(idx)
            if key1:
                seen.add(key1)
            if key2:
                seen.add(key2)

    result_df = df.loc[keep_indices].drop(columns=['_norm_addr', '_norm_name'])
    logger.info(f"Deduplication: {len(properties)} → {len(result_df)} properties "
                f"({len(properties) - len(result_df)} duplicates removed)")

    return result_df.to_dict('records')


def merge_properties(properties_by_site: Dict[str, List[Dict]]) -> List[Dict]:
    """Merge properties from multiple sites."""
    all_properties = []
    for site_name, props in properties_by_site.items():
        all_properties.extend(props)

    return remove_duplicates(all_properties)
