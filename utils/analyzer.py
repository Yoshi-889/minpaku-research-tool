"""
Analysis module for minpaku property research tool.
Handles evaluation, metrics calculation, and report generation.
"""

import pandas as pd
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Constants
SHIN_TAISHIN_YEAR = 1981
GOOD_YOTO_CHIIKI = [
    '第一種低層住居専用地域', '第二種低層住居専用地域',
    '第一種中高層住居専用地域', '第二種中高層住居専用地域',
    '第一種住居地域', '第二種住居地域',
]
BAD_YOTO_CHIIKI = ['工業地域', '工業専用地域']
RYOKAN_YOTO_CHIIKI = ['商業地域', '近隣商業地域', '準工業地域', '準住居地域']
MIN_SCHOOL_DISTANCE_M = 500
MAX_AREA_NO_CHANGE = 100
ASO_TOURISM_DATA = {
    'Aso': {'visitors': 1200000, 'avg_stay_days': 1.5}
}


# ========================================
# Individual Property Evaluation
# ========================================

def evaluate_minpaku_property(
    building_year: Optional[int] = None,
    yoto_chiiki: Optional[str] = None,
    is_shigaika_chosei: Optional[bool] = None,
    school_distance_m: Optional[float] = None,
    total_floor_area_m2: Optional[float] = None,
    has_fire_equipment: Optional[bool] = None,
    additional_notes: str = '',
) -> Dict:
    """
    Evaluate a property for minpaku suitability based on 5 criteria.

    Returns dict with: grade, score, summary, merits, risks, advice
    """
    scores = {}
    merits = []
    risks = []
    advice = []

    # 1. Seismic standard (耐震基準)
    if building_year is not None:
        if building_year >= 1981:
            scores['seismic'] = 100
            merits.append('新耐震基準（1981年6月以降）に適琈しています。')
        elif building_year >= 1970:
            scores['seismic'] = 70
            risks.append('旧耐震基準の建物です（1970年～1981年）。通常利用は可能ですが耐震診断の検討をお勧めします。')
        elif building_year >= 1960:
            scores['seismic'] = 45
            risks.append('1960年代の建物です。耐震診断・補強工事の検討が必要です。')
        else:
            scores['seismic'] = 25
            risks.append('1960年以前の建物です。耐震補強が強く推奨されます。')
    else:
        scores['seismic'] = 50
        advice.append('建築年が不明です。耐震診断を行うことをお勧めします。')

    # 2. Zoning (用途地域)
    if yoto_chiiki is not None:
        if yoto_chiiki in RYOKAN_YOTO_CHIIKI:
            scores['zoning'] = 100
            merits.append(f'用途地域「{yoto_chiiki}」は旅館業法（365日営業）に適合しています。')
        elif yoto_chiiki in GOOD_YOTO_CHIIKI:
            scores['zoning'] = 75
            merits.append(f'用途地域「{yoto_chiiki}」は住居系で民泊新法（180日）に適しています。')
            advice.append('旅館業法（365日営業）を希望する場合は、自治体への確認が必要です。')
        elif yoto_chiiki in BAD_YOTO_CHIIKI:
            scores['zoning'] = 20
            risks.append(f'用途地域「{yoto_chiiki}」は民泊運営に不向きです。')
        else:
            scores['zoning'] = 55
            advice.append(f'用途地域「{yoto_chiiki}」での民泊可否は自治体に確認してください。')
    else:
        scores['zoning'] = 50
        advice.append('用途地域が不明です。自治体に確認することをお勧めします。')

    # 3. Urbanization area (市街化区域)
    if is_shigaika_chosei is not None:
        if is_shigaika_chosei:
            scores['urbanization'] = 30
            risks.append('市街化調整区域内の物件です。開発制限があり、民泊許可が困難な場合があります。')
        else:
            scores['urbanization'] = 100
            merits.append('市街化区域内で、インフラ・利便性が整っています。')
    else:
        scores['urbanization'] = 60
        advice.append('都市計画区分が不明です。確認をお勧めします。')

    # 4. Nearby facilities (周辺施設)
    if school_distance_m is not None:
        if school_distance_m <= 300:
            scores['facilities'] = 100
            merits.append(f'最寄り学校まで{school_distance_m:.0f}mと非常に近く、利便性が高いです。')
        elif school_distance_m <= 500:
            scores['facilities'] = 85
            merits.append(f'最寄り学校まで{school_distance_m:.0f}mで利便性が良好です。')
        elif school_distance_m <= 1000:
            scores['facilities'] = 65
        else:
            scores['facilities'] = 40
            risks.append(f'最寄り学校まで{school_distance_m:.0f}mと距離があります。')
    else:
        scores['facilities'] = 50

    # 5. Building size & fire equipment (建物規模・消防設備)
    building_score = 60  # default
    if total_floor_area_m2 is not None:
        if 30 <= total_floor_area_m2 <= 150:
            building_score = 90
            merits.append(f'延床面積{total_floor_area_m2:.0f}㎡は民泊に最適な規模です。')
        elif total_floor_area_m2 < 30:
            building_score = 50
            risks.append(f'延床面積{total_floor_area_m2:.0f}㎡はやや狭い可能性があります。')
        else:
            building_score = 65
            advice.append(f'延床面積{total_floor_area_m2:.0f}㎡は大規模です。消防設備の追加対応が必要な場合があります。')

    if has_fire_equipment is True:
        building_score = min(building_score + 10, 100)
        merits.append('消防設備が整備されています。')
    elif has_fire_equipment is False:
        building_score = max(building_score - 10, 0)
        if total_floor_area_m2 and total_floor_area_m2 > 100:
            risks.append('消防設備がなく、大規模物件のため整備が法的に必要となる可能性があります。')
        else:
            advice.append('消防設備の整備を検討してください。')

    scores['building'] = building_score

    # Calculate total score (weighted)
    weights = {
        'seismic': 0.20,
        'zoning': 0.25,
        'urbanization': 0.20,
        'facilities': 0.15,
        'building': 0.20,
    }
    total_score = sum(scores.get(k, 50) * w for k, w in weights.items())
    total_score = round(total_score, 1)

    # Determine grade
    if total_score >= 90:
        grade = 'S'
    elif total_score >= 75:
        grade = 'A'
    elif total_score >= 60:
        grade = 'B'
    elif total_score >= 45:
        grade = 'C'
    else:
        grade = 'D'

    # Summary
    grade_desc = {
        'S': '民泊運営に非常に適した物件です。',
        'A': '民泊運営に適灗た物件です。',
        'B': '民泊運営に利用可能な物件です。いくつかの課題に対応が必要です。',
        'C': '民泊運営には工夫が必要な物件です。課題を慎重に検討してください。',
        'D': '民泊運営には不向きな物件です。他の物件の検討をお勧めします。',
    }
    summary = f"総合評価 {grade}（スコア: {total_score}/100）— {grade_desc.get(grade, '')}"

    if not advice:
        advice.append('専門家（不動産コンサルタント・行政書士等）への相談をお勧めします。')

    return {
        'grade': grade,
        'score': total_score,
        'summary': summary,
        'merits': merits,
        'risks': risks,
        'advice': advice,
        'details': scores,
    }


def format_evaluation_report(evaluation: Dict) -> str:
    """
    Format evaluation results into a readable text report.
    """
    lines = []
    lines.append("=" * 50)
    lines.append("  民泊適性評価レポート")
    lines.append("=" * 50)
    lines.append("")
    lines.append(f"総合評価: {evaluation['grade']}  (スコア: {evaluation['score']}/100)")
    lines.append(f"概要: {evaluation['summary']}")
    lines.append("")

    if evaluation.get('merits'):
        lines.append("【メリット】")
        for m in evaluation['merits']:
            lines.append(f"  ✅ {m}")
        lines.append("")

    if evaluation.get('risks'):
        lines.append("【懵念点・リスク】")
        for r in evaluation['risks']:
            lines.append(f"  ⚠️ {r}")
        lines.append("")

    if evaluation.get('advice'):
        lines.append("【アドバイス】")
        for a in evaluation['advice']:
            lines.append(f"  💡 {a}")
        lines.append("")

    details = evaluation.get('details', {})
    if details:
        lines.append("【項目別スコア】")
        labels = {
            'seismic': '耐震基準',
            'zoning': '用途地域',
            'urbanization': '市街化区域',
            'facilities': '周辺施設',
            'building': '建物規模・消防',
        }
        for key, label in labels.items():
            score = details.get(key, '-')
            lines.append(f"  {label}: {score}/100")
        lines.append("")

    lines.append("=" * 50)
    return "\n".join(lines)


# ========================================
# Minpaku Metrics (Rental properties)
# ========================================

def calculate_minpaku_metrics(
    properties,
    daily_rate: int = 8000,
    occupancy_rate: float = 0.45,
    setup_cost: int = 500000,
    monthly_utilities: int = 15000,
    management_rate: float = 0.20,
    is_365_days: bool = True,
) -> pd.DataFrame:
    """
    Calculate minpaku metrics for RENTAL properties.
    properties can be a list of dicts or a DataFrame.
    """
    if isinstance(properties, pd.DataFrame):
        prop_list = properties.to_dict('records')
    else:
        prop_list = list(properties)

    annual_days = 365 if is_365_days else 180

    results = []
    for prop in prop_list:
        rent = prop.get('rent', 0)
        if not rent or rent <= 0:
            # Copy property but skip metrics
            row = dict(prop)
            row.update({
                'monthly_revenue': 0, 'net_monthly_profit': 0,
                'roi_percent': 0, 'breakeven_months': float('inf'),
                'minpaku_score': 0, 'minpaku_grade': 'D',
            })
            results.append(row)
            continue

        rent_yen = rent * 10000  # 万円 -> 円
        mgmt_fee = prop.get('management_fee', 0) or 0
        mgmt_fee_yen = mgmt_fee * 10000

        monthly_revenue = daily_rate * occupancy_rate * annual_days / 12
        monthly_cost = rent_yen + mgmt_fee_yen + monthly_utilities
        monthly_mgmt_cost = monthly_revenue * management_rate
        net_monthly_profit = monthly_revenue - monthly_cost - monthly_mgmt_cost

        annual_profit = net_monthly_profit * 12
        annual_fixed = (rent_yen + mgmt_fee_yen + monthly_utilities) * 12
        roi = (annual_profit / (annual_fixed + setup_cost) * 100) if (annual_fixed + setup_cost) > 0 else 0
        breakeven_months = setup_cost / net_monthly_profit if net_monthly_profit > 0 else float('inf')

        # Score
        score = _calc_rental_minpaku_score(prop, net_monthly_profit)
        grade = _score_to_grade(score)

        row = dict(prop)
        row.update({
            'monthly_revenue': round(monthly_revenue),
            'net_monthly_profit': round(net_monthly_profit),
            'roi_percent': round(roi, 1),
            'breakeven_months': round(breakeven_months, 1) if breakeven_months != float('inf') else float('inf'),
            'minpaku_score': round(score, 1),
            'minpaku_grade': grade,
        })
        results.append(row)

    return pd.DataFrame(results)


# ========================================
# Purchase Metrics
# ========================================

def _estimate_daily_rate(base_rate: int, prop: dict) -> int:
    """
    Estimate daily accommodation rate based on property characteristics.
    Larger properties with more rooms can charge more per night.
    """
    area = prop.get('area', 0) or 0
    layout = str(prop.get('layout', ''))

    # Area-based multiplier: base_rate is for ~30m² (1-room)
    # Scale up for larger properties, cap at 4x
    if area > 0:
        area_mult = max(1.0, min(area / 30.0, 4.0))
    else:
        area_mult = 1.0

    # Layout-based adjustment
    layout_mult = 1.0
    if re.search(r'5[LDK]|6[LDK]|7[LDK]|8[LDK]', layout):
        layout_mult = 2.0
    elif re.search(r'4[LDK]', layout):
        layout_mult = 1.7
    elif re.search(r'3[LDK]', layout):
        layout_mult = 1.4
    elif re.search(r'2[LDK]', layout):
        layout_mult = 1.2
    elif re.search(r'1[LDK]|ワンルーム|1R', layout):
        layout_mult = 1.0

    # Use the larger of area or layout multiplier (avoid double-counting)
    effective_mult = max(area_mult, layout_mult)

    # Age discount: older properties get slight discount
    age = prop.get('age', None)
    if age is not None:
        if age > 40:
            effective_mult *= 0.7
        elif age > 25:
            effective_mult *= 0.8
        elif age > 15:
            effective_mult *= 0.9

    return int(base_rate * effective_mult)


def _calc_building_year(prop: dict) -> int:
    """Calculate building year from age. Returns None if unknown."""
    age = prop.get('age', None)
    if age is not None and age >= 0:
        return datetime.now().year - age
    return None


def _calc_purchase_minpaku_score(prop: dict, monthly_income: float, capitalization_rate: float) -> float:
    """Calculate minpaku score for a purchase property (0-100)."""
    score = 0.0

    # Profitability - capitalization rate (30%)
    if capitalization_rate >= 15:
        score += 30
    elif capitalization_rate >= 10:
        score += 25
    elif capitalization_rate >= 5:
        score += 18
    elif capitalization_rate > 0:
        score += 10
    else:
        score += 0

    # Area suitability (20%)
    area = prop.get('area', 0) or 0
    if 30 <= area <= 120:
        score += 20
    elif 20 <= area <= 200:
        score += 14
    elif area > 0:
        score += 8

    # Layout (15%)
    layout = str(prop.get('layout', ''))
    if re.search(r'2[LDK]|3[LDK]', layout):
        score += 15
    elif re.search(r'1[LDK]|ワンルーム|1R', layout):
        score += 12
    elif re.search(r'4[LDK]|5[LDK]', layout):
        score += 10
    elif layout:
        score += 5

    # Age / seismic safety (20%)
    age = prop.get('age', None)
    if age is not None:
        if age <= 5:
            score += 20
        elif age <= 15:
            score += 16
        elif age <= 25:
            score += 12
        elif age <= 40:
            score += 6
        else:
            score += 2

    # Price efficiency (15%) — lower price = easier to recoup
    price = prop.get('price', 0) or 0
    if 0 < price <= 500:
        score += 15
    elif price <= 1000:
        score += 12
    elif price <= 2000:
        score += 8
    elif price <= 5000:
        score += 5
    elif price > 5000:
        score += 2

    return min(score, 100)


def calculate_purchase_metrics(
    properties,
    daily_rate: int = 8000,
    occupancy_rate: float = 0.45,
    setup_cost: int = 500000,
    monthly_utilities: int = 15000,
    management_rate: float = 0.20,
    is_365_days: bool = True,
) -> pd.DataFrame:
    """
    Calculate metrics for PURCHASE properties.
    daily_rate is the BASE rate per night for a ~30m² property.
    Actual rate scales with area and layout.
    properties can be a list of dicts or a DataFrame.
    """
    if isinstance(properties, pd.DataFrame):
        prop_list = properties.to_dict('records')
    else:
        prop_list = list(properties)

    annual_days = 365 if is_365_days else 180

    results = []
    for prop in prop_list:
        # Calculate building year from age
        building_year = _calc_building_year(prop)
        if building_year is not None:
            prop['building_year'] = building_year

        price = prop.get('price', 0)
        if not price or price <= 0:
            row = dict(prop)
            row.update({
                'monthly_income': 0, 'capitalization_rate': 0,
                'net_yield': 0, 'breakeven_years': float('inf'),
                'estimated_daily_rate': 0,
                'minpaku_score': 0, 'minpaku_grade': 'D',
            })
            results.append(row)
            continue

        # Estimate property-specific daily rate
        prop_daily_rate = _estimate_daily_rate(daily_rate, prop)

        price_yen = price * 10000  # 万円 -> 円
        annual_revenue = prop_daily_rate * occupancy_rate * annual_days
        annual_utilities = monthly_utilities * 12
        annual_mgmt = annual_revenue * management_rate
        annual_expenses = annual_utilities + annual_mgmt
        annual_profit = annual_revenue - annual_expenses

        monthly_income = annual_profit / 12
        capitalization_rate = (annual_revenue / price_yen * 100) if price_yen > 0 else 0
        net_yield = (annual_profit / (price_yen + setup_cost) * 100) if (price_yen + setup_cost) > 0 else 0
        breakeven_years = price_yen / annual_profit if annual_profit > 0 else float('inf')

        # Calculate minpaku score
        score = _calc_purchase_minpaku_score(prop, monthly_income, capitalization_rate)
        grade = _score_to_grade(score)

        row = dict(prop)
        row.update({
            'monthly_income': round(monthly_income),
            'capitalization_rate': round(capitalization_rate, 2),
            'net_yield': round(net_yield, 2),
            'breakeven_years': round(breakeven_years, 1) if breakeven_years != float('inf') else float('inf'),
            'estimated_daily_rate': prop_daily_rate,
            'minpaku_score': round(score, 1),
            'minpaku_grade': grade,
        })
        results.append(row)

    return pd.DataFrame(results)


# ========================================
# Score helpers
# ========================================

def _calc_rental_minpaku_score(prop: Dict, net_monthly_profit: float) -> float:
    """Calculate minpaku score for a rental property (0-100)."""
    score = 0.0

    # Profitability (30%)
    if net_monthly_profit > 100000:
        score += 30
    elif net_monthly_profit > 50000:
        score += 25
    elif net_monthly_profit > 0:
        score += 15
    else:
        score += 0

    # Area (20%)
    area = prop.get('area', 0) or 0
    if 30 <= area <= 80:
        score += 20
    elif 20 <= area <= 120:
        score += 14
    elif area > 0:
        score += 8

    # Layout (15%)
    layout = str(prop.get('layout', ''))
    if re.search(r'1[LDK]|ワンルーム|1R', layout):
        score += 15
    elif re.search(r'2[LDK]', layout):
        score += 12
    elif re.search(r'3[LDK]', layout):
        score += 8
    elif layout:
        score += 5

    # Age (20%)
    age = prop.get('age', None)
    if age is not None:
        if age <= 5:
            score += 20
        elif age <= 15:
            score += 16
        elif age <= 25:
            score += 10
        elif age <= 40:
            score += 5
        else:
            score += 2

    # Rent efficiency (15%)
    rent = prop.get('rent', 0) or 0
    if area > 0 and rent > 0:
        rent_per_m2 = (rent * 10000) / area
        if 1000 <= rent_per_m2 <= 3000:
            score += 15
        elif 500 <= rent_per_m2 <= 5000:
            score += 10
        else:
            score += 5

    return min(score, 100)


def _score_to_grade(score: float) -> str:
    """Convert score to letter grade."""
    if score >= 90:
        return 'S'
    elif score >= 75:
        return 'A'
    elif score >= 60:
        return 'B'
    elif score >= 45:
        return 'C'
    else:
        return 'D'


# ========================================
# Summary Statistics
# ========================================

def generate_summary_stats(df: pd.DataFrame) -> Dict:
    """Generate summary statistics from analyzed DataFrame."""
    if df is None or df.empty:
        return {
            'total_properties': 0,
            'avg_minpaku_score': 0,
            'profitable_count': 0,
        }
