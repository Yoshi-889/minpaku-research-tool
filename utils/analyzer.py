"""Property analysis utilities for æ°æ³ (vacation rental) research.

Evaluation criteria based on:
- æé¤¨æ¥­æ³ï¼ç°¡æå®¿æå¶æ¥­ï¼
- ä½å®å®¿æ³äºæ¥­æ³ï¼æ°æ³æ°æ³ï¼
- å»ºç¯åºæºæ³
- æ¶é²æ³
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# ========================================
# æ°æ³è©ä¾¡åºæºå®æ°
# ========================================
SHIN_TAISHIN_YEAR = 1981  # æ°èéåºæºã®å¢ç®

GOOD_YOTO_CHIIKI = [
    'ç¬¬ä¸ç¨®ä½å±å°å', 'ç¬¬äºç¨®ä½å±å°å', 'æºä½å±å°å',
    'è¿é£åæ¥­å°å', 'åæ¥­å°å', 'æºå·¥æ¥­å°å',
]
BAD_YOTO_CHIIKI = [
    'ç¬¬ä¸ç¨®ä½å±¤ä½å±å°ç¨å°å', 'ç¬¬äºç¨®ä½å±¤ä½å±å°ç¨å°å',
    'ç¬¬ä¸ç¨®ä¸­é«å±¤ä½å±å°ç¨å°å', 'ç¬¬äºç¨®ä¸­é«å±¤ä½å±å°ç¨å°å',
]
MIN_SCHOOL_DISTANCE_M = 100
MAX_AREA_NO_CHANGE = 200

ASO_TOURISM_DATA = {
    'annual_visitors': 18_000_000,
    'avg_daily_rate_minpaku': 8000,
    'avg_occupancy_rate': 0.45,
    'peak_months': [3, 4, 5, 7, 8, 9, 10, 11],
    'peak_occupancy': 0.70,
    'off_peak_occupancy': 0.25,
    'nearby_attractions': [
        'é¿èå±±ä¸­å²³ç«å£', 'èåéã¶æµ', 'å¤§è¦³å³°', 'é¿èç¥ç¤¾',
        'åç§æ¸©æ³', 'é»å·æ¸©æ³ï¼åå°å½çºï¼', 'é¿èãã¡ã¼ã ã©ã³ã'
    ],
}


# ========================================
# åå¥ç©ä»¶ã®æ°æ³é©æ§è©ä¾¡ï¼5æ®µé: S, A, B, C, Dï¼
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
    """æ°æ³ç©ä»¶ã®ç·åè©ä¾¡ãè¡ãã"""
    merits = []
    risks = []
    advice = []
    score = 50

    # 1. èéåºæº
    if building_year is not None:
        if building_year >= SHIN_TAISHIN_YEAR:
            merits.append(
                f"ãèéåºæº â­ï¸ã{building_year}å¹´ç¯ â æ°èéåºæºã«é©åãèè³å¯©æ»ã§ãæå©ã"
            )
            score += 15
        else:
            risks.append(
                f"ãèéåºæº âã{building_year}å¹´ç¯ â æ§èéåºæºã"
                "èéè¨ºæ­ã»è£å¼·å·¥äºã«å¤é¡ã®è²»ç¨ãªã¹ã¯ãèè³ãéãã«ããã"
            )
            advice.append("å»ºç¯å£«ã«ããèéè¨ºæ­ãå¿ãå®æ½ãèªæ²»ä½ã®èéæ¹ä¿®è£å©éãç¢ºèªãã")
            score -= 20
    else:
        risks.append("ãèéåºæº â ï¸ãç¯å¹´æ°ä¸æãå»ºç¯ç¢ºèªå¹´ææ¥ãå¿ãç¢ºèªãã¦ãã ããã")

    # 2. ç¨éå°å
    if yoto_chiiki:
        if yoto_chiiki in GOOD_YOTO_CHIIKI:
            merits.append(f"ãç¨éå°å â­ï¸ã{yoto_chiiki} â æé¤¨æ¥­æ³ã§365æ¥å¶æ¥­å¯è½ã")
            score += 15
        elif yoto_chiiki in BAD_YOTO_CHIIKI:
            risks.append(
                f"ãç¨éå°å âã{yoto_chiiki} â æé¤¨æ¥­æ³ã§ã®å¶æ¥­ä¸å¯ã"
                "æ°æ³ã§ã®180æ¥/å¹´å¶éã®ã¿ãåçæ§ãå¤§å¹ã«ä½ä¸ã"
            )
            score -= 15
        else:
            risks.append(f"ãç¨éå°å â ï¸ã{yoto_chiiki} â å¶æ¥­å¯å¦ãèªæ²»ä½ã«è¦ç¢ºèªã")
    else:
        risks.append("ãç¨éå°å â ï¸ãç¨éå°åä¸æãé½å¸è¨ç»å³ã§ç¢ºèªãã¦ãã ããã")

    # 3. å¸è¡åèª¿æ´åºå
    if is_shigaika_chosei is not None:
        if is_shigaika_chosei:
            risks.append("ãåå°åºå âãå¸è¡åèª¿æ´åºåãæ°æ³å¶æ¥­ã¯æ¥µãã¦å°é£ã")
            score -= 25
        else:
            merits.append("ãåå°åºå â­ï¸ãå¸è¡åèª¿æ´åºåå¤ãç¨éå¤æ´ã®å¶éãªãã")
            score += 5

    # 4. å¨è¾¹æ½è¨­
    if school_distance_m is not None:
        if school_distance_m >= MIN_SCHOOL_DISTANCE_M:
            merits.append(
                f"ãå¨è¾ºæ½è¨­ â­ï¸ãæå¯ãå­¦æ ¡ç­ãã{school_distance_m:.0f}m â 100mä»¥ä¸ã§åé¡ãªãã"
            )
            score += 10
        else:
            risks.append(
                f"ãå¨è¾ºæ½è¨­ âãæå¯ãå­¦æ ¡ç­ãã{school_distance_m:.0f}m â "
                "100mæªæºãæé¤¨æ¥­ã®è¨±å¯ãä¸ããªãå¯è½æ§ã"
            )
            score -= 15
    else:
        risks.append("ãå¨è¾¹æ½è¨­ â ï¸ãå­¦æ ¡ã»åç«¥ç¦ç¥æ½è¨­ã»å¬åããã®è·é¢ä¸æãè¦ç¢ºèªã")

    # 5. å»ºç©è¦æ¨¡
    if total_floor_area_m2 is not None:
        if total_floor_area_m2 < MAX_AREA_NO_CHANGE:
            merits.append(
                f"ãå»ºç©è¦æ¨¡ â­ï¸ã{total_floor_area_m2:.1f}ã¡ â "
                "200ã¡æªæºã§ç¨éå¤æ´æç¶ãä¸è¦ã"
            )
            score += 10
        else:
            risks.append(
                f"ãå»ºç©è¦æ¨¡ âã{total_floor_area_m2:.1f}ã¡ â "
                "200ã¡ä»¥ä¸ãç¨éå¤æ´ç³è«ãå¿è¦ï¼è¨­è¨è²»ç¨ï¼æéï¼ã"
            )
            score -= 10

    # 6. æ¶é²è¨­å
    if has_fire_equipment is not None:
        if has_fire_equipment:
            merits.append("ãæ¶é²è¨­å â­ï¸ãæ¶é²è¨­åãããè¿½å å·¥äºè²»ç¨ãæããããå¯è½æ§ã")
            score += 5
        else:
            risks.append("ãæ¶é²è¨­å âãæ¶é²è¨­åãªããè¨­ç½®å·¥äºãå¿è¦ï¼æ°ä¸åãæ°åä¸åï¼ã")
            score -= 5

    # å±éã¢ããã¤ã¹
    advice.append("ãå¿é ãç®¡è½ä¿å¥æã§ã®æé¤¨æ¥­è¨±å¯ï¼ã¾ãã¯æ°æ³å±åºï¼ã®äºåç¸è«ãå¿ãè¡ã£ã¦ãã ããã")
    advice.append("ãæ¡ä¾ç¢ºèªãèªæ²»ä½ç¬èªã®ä¸ä¹ãæ¡ä¾ï¼å¶æ¥­æ¥æ°å¶éã»åºåå¶éç­ï¼ãç¢ºèªãã¦ãã ããã")

    # Cap score to 100
    score = min(100, max(0, score))

    # ç·åè©ä¾¡
    if score >= 85:
        grade, summary = 'S', 'æ°æ³å¶æ¥­ã«æ¥µãã¦é©ããç©ä»¶ãéããã«äºæ¥­éå§ãè¦è¾¼ãã¾ãã'
    elif score >= 70:
        grade, summary = 'A', 'æ°æ³å¶æ¥­ã«é©ããç©ä»¶ãä¸é¨ç¢ºèªäºé ããã¾ããå¤§ããªéå®³ãªãã'
    elif score >= 55:
        grade, summary = 'B', 'æ°æ³å¶æ¥­ã¯å¯è½ã§ãããç¢ºèªã»å¯¾å¿ãå¿è¦ãªé ç®ãããã¾ãã'
    elif score >= 40:
        grade, summary = 'C', 'æ°æ³å¶æ¥­ã«ããã¤ãã®èª²é¡ãããè²»ç¨å¯¾å¹æãæéã«æ¤è¨ã'
    else:
        grade, summary = 'D', 'æ°æ³å¶æ¥­ã«éå¤§ãªéå®³ãããä»ã®ç©ä»¶ã®æ¤è¨ãæ¨å¥¨ã'

    return {
        'grade': grade, 'score': score, 'summary': summary,
        'merits': merits, 'risks': risks, 'advice': advice,
    }


def format_evaluation_report(eval_result: Dict) -> str:
    """Format evaluation result as readable report."""
    lines = [
        f"{'='*50}",
        f"  æ°æ³ç©ä»¶ ç·åè©ä¾¡: {eval_result['grade']} ({eval_result['score']}/100)",
        f"{'='*50}",
        f"\n{eval_result['summary']}\n",
    ]
    if eval_result['merits']:
        lines.append("âââ ã¡ãªãã âââ")
        for m in eval_result['merits']:
            lines.append(f"  {m}")
        lines.append("")
    if eval_result['risks']:
        lines.append("âââ æ¸å¿µç¹ã»ãªã¹ã¯ âââ")
        for r in eval_result['risks']:
            lines.append(f"  {r}")
        lines.append("")
    if eval_result['advice']:
        lines.append("âââ å°éå®¶ããã®ã¢ããã¤ã¹ âââ")
        for a in eval_result['advice']:
            lines.append(f"  {a}")
    return '\n'.join(lines)


# ========================================
# ç©ä»¶ãªã¹ãã®åçã·ãã¥ã¬ã¼ã·ã§ã³
# ========================================

def calculate_minpaku_metrics(
    properties: List[Dict],
    daily_rate: int = 8000,
    occupancy_rate: float = 0.45,
    setup_cost: int = 500000,
    monthly_utilities: int = 15000,
    management_rate: float = 0.20,
    is_365_days: bool = True,
) -> pd.DataFrame:
    """Calculate æ°æ³ investment metrics for each property."""
    if not properties:
        return pd.DataFrame()

    df = pd.DataFrame(properties)
    annual_days = 365 if is_365_days else 180

    df['monthly_rent_jpy'] = df['rent'].apply(lambda x: x * 10000 if pd.notna(x) else None)
    df['monthly_mgmt_jpy'] = df['management_fee'].apply(lambda x: x * 10000 if pd.notna(x) else 0)
    df['total_monthly_cost'] = df['monthly_rent_jpy'].fillna(0) + df['monthly_mgmt_jpy'].fillna(0) + monthly_utilities
    df['annual_fixed_cost'] = df['total_monthly_cost'] * 12
    df['est_annual_revenue'] = daily_rate * occupancy_rate * annual_days
    df['annual_mgmt_cost'] = df['est_annual_revenue'] * management_rate
    df['annual_profit'] = df['est_annual_revenue'] - df['annual_fixed_cost'] - df['annual_mgmt_cost']
    df['net_monthly_profit'] = df['annual_profit'] / 12

    df['roi_percent'] = df.apply(
        lambda r: (r['annual_profit'] / (r['annual_fixed_cost'] + setup_cost)) * 100
        if r['annual_fixed_cost'] > 0 else None, axis=1
    )
    df['breakeven_months'] = df.apply(
        lambda r: round(setup_cost / (r['annual_profit'] / 12), 1)
        if r['annual_profit'] > 0 else float('inf'), axis=1
    )

    df['minpaku_score'] = df.apply(_estimate_minpaku_score, axis=1)
    df['minpaku_grade'] = df['minpaku_score'].apply(_score_to_grade)

    return df


def _estimate_minpaku_score(row) -> int:
    """Estimate score from scraping data (limited info)."""
    score = 50

    profit = row.get('net_monthly_profit')
    if pd.notna(profit):
        if profit > 50000: score += 15
        elif profit > 30000: score += 10
        elif profit > 10000: score += 5
        elif profit <= 0: score -= 15

    area = row.get('area')
    if pd.notna(area):
        if 40 <= area < 200: score += 10
        elif area >= 200: score -= 5
        elif area >= 25: score += 3
        else: score -= 5

    layout = str(row.get('layout', ''))
    if any(x in layout for x in ['3LDK', '4LDK', '5LDK', '5DK']):
        score += 10
    elif any(x in layout for x in ['2LDK', '3DK']):
        score += 7
    elif any(x in layout for x in ['1LDK', '2DK']):
        score += 3
    elif any(x in layout for x in ['1R', '1K']):
        score -= 5

    age = row.get('age')
    if pd.notna(age):
        build_year = datetime.now().year - age
        if build_year >= SHIN_TAISHIN_YEAR:
            score += 10
        else:
            score -= 15

    rent = row.get('rent')
    if pd.notna(rent):
        if rent <= 4: score += 5
        elif rent <= 6: score += 3
        elif rent >= 10: score -= 5

    return max(0, min(100, score))


def _score_to_grade(score: int) -> str:
    if score >= 80: return 'S'
    elif score >= 65: return 'A'
    elif score >= 50: return 'B'
    elif score >= 35: return 'C'
    else: return 'D'


def generate_summary_stats(df: pd.DataFrame) -> Dict:
    """Generate summary statistics."""
    if df.empty:
        return {}
    stats = {
        'total_properties': len(df),
        'sites': df['site'].value_counts().to_dict() if 'site' in df.columns else {},
    }
    for col in ['rent', 'area', 'age']:
        if col in df.columns:
            vals = df[col].dropna()
            if not vals.empty:
                stats[f'{col}_avg'] = round(vals.mean(), 2)
                stats[f'{col}_min'] = vals.min()
                stats[f'{col}_max'] = vals.max()
                stats[f'{col}_median'] = round(vals.median(), 2)
    if 'layout' in df.columns:
        stats['layout_dist'] = df['layout'].value_counts().to_dict()
    if 'minpaku_score' in df.columns:
        scores = df['minpaku_score'].dropna()
        if not scores.empty:
            stats['avg_minpaku_score'] = round(scores.mean(), 1)
            stats['top_minpaku_count'] = int(len(scores[scores >= 65]))
    if 'roi_percent' in df.columns:
        roi = df['roi_percent'].dropna()
        roi = roi[roi != float('inf')]
        if not roi.empty:
            stats['avg_roi'] = round(roi.mean(), 1)
            stats['max_roi'] = round(roi.max(), 1)
    if 'annual_profit' in df.columns:
        profit = df['annual_profit'].dropna()
        if not profit.empty:
            stats['avg_annual_profit'] = round(profit.mean())
            stats['profitable_count'] = int(len(profit[profit > 0]))
    return stats
