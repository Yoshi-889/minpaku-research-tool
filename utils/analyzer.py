"""
Analysis module for minpaku property research tool.
Handles evaluation, metrics calculation, and report generation.
"""

import pandas as pd
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)

# Constants
SHIN_TAISHIN_YEAR = 1981
GOOD_YOTO_CHIIKI = ['第一種低層住居専用地域', '第二種低層住居専用地域', '第一種中高層住居専用地域', '第二種中高層住居専用地域', '第一種住居地域', '第二種住居地域']
BAD_YOTO_CHIIKI = ['工業地域', '工業専用地域']
RYOKAN_YOTO_CHIIKI = ['商業地域', '近隣商業地域', '準工業地域', '準住居地域']
MIN_SCHOOL_DISTANCE_M = 500
MAX_AREA_NO_CHANGE = 100
ASO_TOURISM_DATA = {
    'Aso': {'visitors': 1200000, 'avg_stay_days': 1.5}
}


def evaluate_minpaku_property(property_data: Dict) -> Dict:
    """
    Evaluate a minpaku property based on 5 criteria.

    Args:
        property_data: Dictionary containing property information

    Returns:
        Dictionary with evaluation results for each criterion
    """
    results = {}

    # Criterion 1: 耐震 (Seismic resistance)
    year_built = property_data.get('year_built', 0)
    results['seismic'] = {
        'score': 100 if year_built >= SHIN_TAISHIN_YEAR else 50,
        'description': 'Post-1981 construction' if year_built >= SHIN_TAISHIN_YEAR else 'Pre-1981 construction'
    }

    # Criterion 2: 用途地域 (Zoning)
    yoto_chiiki = property_data.get('yoto_chiiki', '')
    if yoto_chiiki in GOOD_YOTO_CHIIKI:
        results['zoning'] = {'score': 100, 'description': 'Residential zoning (excellent for minpaku)'}
    elif yoto_chiiki in RYOKAN_YOTO_CHIIKI:
        results['zoning'] = {'score': 80, 'description': 'Commercial/mixed zoning (suitable for 365-day operation)'}
    elif yoto_chiiki in BAD_YOTO_CHIIKI:
        results['zoning'] = {'score': 30, 'description': 'Industrial zoning (not suitable for minpaku)'}
    else:
        results['zoning'] = {'score': 60, 'description': 'Other zoning classification'}

    # Criterion 3: 市街化調整区域 (Urbanization promotion area)
    is_urbanization_control = property_data.get('urbanization_control_area', False)
    results['urbanization'] = {
        'score': 100 if not is_urbanization_control else 30,
        'description': 'Not in urbanization control area' if not is_urbanization_control else 'In urbanization control area (restrictions apply)'
    }

    # Criterion 4: 周辺施設 (Nearby facilities)
    school_distance_m = property_data.get('school_distance_m', float('inf'))
    facility_score = 100 if school_distance_m < MIN_SCHOOL_DISTANCE_M else 60
    results['facilities'] = {
        'score': facility_score,
        'description': f'School within {MIN_SCHOOL_DISTANCE_M}m' if school_distance_m < MIN_SCHOOL_DISTANCE_M else 'No school within {MIN_SCHOOL_DISTANCE_M}m'
    }

    # Criterion 5: 建物規模・消防設備 (Building size and fire equipment)
    building_area = property_data.get('building_area', 0)
    has_fire_equipment = property_data.get('fire_equipment', False)

    if building_area <= MAX_AREA_NO_CHANGE:
        size_score = 100 if has_fire_equipment else 70
    else:
        size_score = 80 if has_fire_equipment else 50

    results['building'] = {
        'score': size_score,
        'description': f'Building area {building_area}m²' + (' with fire equipment' if has_fire_equipment else '')
    }

    return results


def format_evaluation_report(evaluation: Dict) -> str:
    """
    Format evaluation results into a readable report.

    Args:
        evaluation: Dictionary from evaluate_minpaku_property()

    Returns:
        Formatted string report
    """
    report = "=== Minpaku Property Evaluation Report ===\n\n"

    criteria = [
        ('耐震 (Seismic)', 'seismic'),
        ('用途地域 (Zoning)', 'zoning'),
        ('市街化調整 (Urbanization)', 'urbanization'),
        ('周辺施設 (Facilities)', 'facilities'),
        ('建物規模・消防 (Building/Fire)', 'building')
    ]

    for label, key in criteria:
        result = evaluation.get(key, {})
        report += f"{label}: {result.get('score', 0)}/100\n"
        report += f"  {result.get('description', 'N/A')}\n\n"

    avg_score = sum(r.get('score', 0) for r in evaluation.values()) / len(evaluation)
    report += f"Average Score: {avg_score:.1f}/100\n"

    return report


def calculate_minpaku_metrics(
    properties: List[Dict],
    daily_rate: int = 8000,
    occupancy_rate: float = 0.45,
    is_365_days: bool = True
) -> pd.DataFrame:
    """
    Calculate minpaku-specific metrics for rental properties.

    Args:
        properties: List of property dictionaries with 'rent' field
        daily_rate: Daily rental rate in JPY
        occupancy_rate: Expected occupancy rate (0-1)
        is_365_days: Whether properties are rented 365 days (True) or just during peak season (False)

    Returns:
        DataFrame with calculated metrics
    """
    results = []

    annual_days = 365 if is_365_days else 150

    for prop in properties:
        rent = prop.get('rent', 0)
        if rent <= 0:
            continue

        rent_jpy = rent * 10000  # Convert from 万円 to JPY
        est_annual_revenue = daily_rate * occupancy_rate * annual_days
        annual_expenses = rent_jpy
        annual_profit = est_annual_revenue - annual_expenses

        metrics = {
            'name': prop.get('name', 'Unknown'),
            'rent_man_yen': rent,
            'rent_jpy': rent_jpy,
            'daily_rate': daily_rate,
            'occupancy_rate': occupancy_rate * 100,
            'est_annual_revenue': est_annual_revenue,
            'annual_expenses': annual_expenses,
            'annual_profit': annual_profit,
            'gross_yield': (est_annual_revenue / rent_jpy * 100) if rent_jpy > 0 else 0,
            'net_yield': (annual_profit / rent_jpy * 100) if rent_jpy > 0 else 0,
            'monthly_income': annual_profit / 12,
            'breakeven_years': rent_jpy / annual_profit if annual_profit > 0 else float('inf'),
            'minpaku_score': _estimate_minpaku_score(prop),
            'minpaku_grade': _score_to_grade(_estimate_minpaku_score(prop))
        }
        results.append(metrics)

    return pd.DataFrame(results)


def calculate_purchase_metrics(
    properties: List[Dict],
    daily_rate: int = 8000,
    occupancy_rate: float = 0.45,
    setup_cost: int = 500000,
    monthly_utilities: int = 15000,
    management_rate: float = 0.20,
    is_365_days: bool = True,
) -> pd.DataFrame:
    """
    Calculate metrics for PURCHASE properties.

    Args:
        properties: List of property dictionaries with 'price' field (in 万円)
        daily_rate: Daily rental rate in JPY
        occupancy_rate: Expected occupancy rate (0-1)
        setup_cost: Initial setup cost in JPY
        monthly_utilities: Monthly utility cost in JPY
        management_rate: Management/maintenance rate as percentage of revenue (0-1)
        is_365_days: Whether properties are rented 365 days (True) or just during peak season (False)

    Returns:
        DataFrame with calculated metrics
    """
    results = []

    annual_days = 365 if is_365_days else 150

    for prop in properties:
        price = prop.get('price', 0)
        if price <= 0:
            continue

        price_jpy = price * 10000  # Convert from 万円 to JPY
        est_annual_revenue = daily_rate * occupancy_rate * annual_days
        annual_utilities = monthly_utilities * 12
        annual_management_cost = est_annual_revenue * management_rate
        annual_expenses = annual_utilities + annual_management_cost
        annual_profit = est_annual_revenue - annual_expenses

        gross_yield = (est_annual_revenue / price_jpy * 100) if price_jpy > 0 else 0
        net_yield = (annual_profit / (price_jpy + setup_cost) * 100) if (price_jpy + setup_cost) > 0 else 0
        breakeven_years = price_jpy / annual_profit if annual_profit > 0 else float('ing')

        metrics = {
            'name': prop.get('name', 'Unknown'),
            'price_man_yen': price,
            'price_jpy': price_jpy,
            'daily_rate': daily_rate,
            'occupancy_rate': occupancy_rate * 100,
            'setup_cost': setup_cost,
            'monthly_utilities': monthly_utilities,
            'management_rate': management_rate * 100,
            'est_annual_revenue': est_annual_revenue,
            'annual_utilities': annual_utilities,
            'annual_management_cost': annual_management_cost,
            'annual_expenses': annual_expenses,
            'annual_profit': annual_profit,
            'gross_yield': gross_yield,
            'net_yield': net_yield,
            'monthly_income': annual_profit / 12,
            'breakeven_years': breakeven_years,
            'minpaku_score': _estimate_minpaku_score(prop),
            'minpaku_grade': _score_to_grade(_estimate_minpaku_score(prop))
        }
        results.append(metrics)

    return pd.DataFrame(results)


def _estimate_minpaku_score(property_data: Dict) -> float:
    """
    Estimate minpaku viability score for a property.

    Args:
        property_data: Property information dictionary

    Returns:
        Score from 0-100
    """
    evaluation = evaluate_minpaku_property(property_data)
    scores = [result.get('score', 0) for result in evaluation.values()]
    return sum(scores) / len(scores) if scores else 0


def _score_to_grade(score: float) -> str:
    """
    Convert numerical score to letter grade.

    Args:
        score: Numerical score (0-100)

    Returns:
        Letter grade string
    """
    if score >= 90:
        return 'A'
    elif score >= 80:
        return 'B'
    elif score >= 70:
        return 'C'
    elif score >= 60:
        return 'D'
    else:
        return 'F'


def generate_summary_stats(metrics_df: pd.DataFrame) -> Dict:
    """
    Generate summary statistics from metrics DataFrame.

    Args:
        metrics_df: DataFrame from calculate_minpaku_metrics() or calculate_purchase_metrics()

    Returns:
        Dictionary with summary statistics
    """
    if metrics_df.empty:
        return {
            'count': 0,
            'avg_gross_yield': 0,
            'avg_net_yield': 0,
            'avg_monthly_income': 0,
            'median_breakeven_years': 0,
            'grade_distribution': {}
        }

    # Filter out infinite values for breakeven years
    valid_breakeven = metrics_df[metrics_df['breakeven_years'] != float('inf')]['breakeven_years']
    median_breakeven = valid_breakeven.median() if len(valid_breakeven) > 0 else 0

    grade_dist = metrics_df['minpaku_grade'].value_counts().to_dict()

    return {
        'count': len(metrics_df),
        'avg_gross_yield': metrics_df['gross_yield'].mean(),
        'avg_net_yield': metrics_df['net_yield'].mean(),
        'avg_monthly_income': metrics_df['monthly_income'].mean(),
        'median_breakeven_years': median_breakeven,
        'grade_distribution': grade_dist
    }
