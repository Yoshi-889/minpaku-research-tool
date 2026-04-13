"""Property analysis utilities for 民泊 (vacation rental) research.

Evaluation criteria based on:
- 旅館業法（簡易宿所営業）
- 住宅宿泊事業法（民泊新法）
- 建築基準法
- 消防法
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# ========================================
# 民泊評価基準定数
# ========================================
SHIN_TAISHIN_YEAR = 1981  # 新耐震基準の境目

GOOD_YOTO_CHIIKI = [
    '第一種住居地域', '第二種住居地域', '準住居地域',
    '近隣商業地域', '商業地域', '準工業地域',
]
BAD_YOTO_CHIIKI = [
    '第一種低層住居専用地域', '第二種低層住居専用地域',
    '第一種中高層住居専用地域', '第二種中高層住居専用地域',
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
        '阿蘇山中岳火口', '草千里ヶ浜', '大観峰', '阿蘇神社',
        '内牧温泉', '黒川温泉（南小国町）', '阿蘇ファームランド'
    ],
}


# ========================================
# 個別物件の民泊適性評価（5段階: S, A, B, C, D）
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
    """民泊物件の総合評価を行う。"""
    merits = []
    risks = []
    advice = []
    score = 50

    # 1. 耐震基準
    if building_year is not None:
        if building_year >= SHIN_TAISHIN_YEAR:
            merits.append(
                f"【耐震基準 ⭕️】{building_year}年築 → 新耐震基準に適合。融資寯査でも有利。"
            )
            score += 15
        else:
            risks.append(
                f"【耐震基準 ❌】{building_year}年築 → 旧耐震基準。"
                "耐震診断・補強工事に多額の費用リスク。融資も通りにくい。"
            )
            advice.append("建築士による耐震診断を必ず実施。自治体の耐震改修補助金も確認を。")
            score -= 20
    else:
        risks.append("【耐震基準 ⚠️】築年数不明。建築確認年月日を必ず確認してください。")

    # 2. 用途地域
    if yoto_chiiki:
        if yoto_chiiki in GOOD_YOTO_CHIIKI:
            merits.append(f"【用途地域 ⭕️】{yoto_chiiki} → 旅館業法で365日営業可能。")
            score += 15
        elif yoto_chiiki in BAD_YOTO_CHIIKI:
            risks.append(
                f"【用途地域 ❌】{yoto_chiiki} → 旅館業法での営業不可。"
                "新法での180日/年制限のみ。収益���が大幅に低下。"
            )
            score -= 15
        else:
            risks.append(f"【用途地域 ⚠️】{yoto_chiiki} → 営業可否を自治体に要確認。")
    else:
        risks.append("【用途地域 ⚠️】用途地域不明。都市計画図で確認してください。")

    # 3. 市街化調整区域
    if is_shigaika_chosei is not None:
        if is_shigaika_chosei:
            risks.append("【土地区分 ❌】市街化調整区域。民泊営業は極めて困難。")
            score -= 25
        else:
            merits.append("【土地区分 ⭕️】市街化調整区域外。用途変更の制限なし。")
            score += 5

    # 4. 周边施設
    if school_distance_m is not None:
        if school_distance_m >= MIN_SCHOOL_DISTANCE_M:
            merits.append(
                f"【周辺施設 ⭕️】最寄り学校等から{school_distance_m:.0f}m → 100m以上で問題なし。"
            )
            score += 10
        else:
            risks.append(
                f"【周辺施設 ❌】最寄り学校等から{school_distance_m:.0f}m → "
                "100m未満。旅館業の許可が下りない可能性。"
            )
            score -= 15
    else:
        risks.append("【周边施設 ⚠️】学校・児童福祉施設・公園からの距離不明。要確認。")

    # 5. 建物規模
    if total_floor_area_m2 is not None:
        if total_floor_area_m2 < MAX_AREA_NO_CHANGE:
            merits.append(
                f"【建物規模 ⭕️】{total_floor_area_m2:.1f}㎡ → "
                "200㎡未満で用途変更手続き不要。"
            )
            score += 10
        else:
            risks.append(
                f"【建物規模 ❌】{total_floor_area_m2:.1f}㎡ → "
                "200㎡以上。用途変更申請が必要（設計費用＋時間）。"
            )
            score -= 10

    # 6. 消防設備
    if has_fire_equipment is not None:
        if has_fire_equipment:
            merits.append("【消防設備 ⭕️】消防設備あり。追加工事費用を抑えられる可能性。")
            score += 5
        else:
            risks.append("【消防設備 ❌】消防設備なし。設置工事が必要（数万円〜数十万円）。")
            score -= 5

    # 共通アドバイス
    advice.append("【必須】管轄保健所での旅館業許可（または民泊届出）の事前相談を必ず行ってください。")
    advice.append("【条例確認】自治体独自の上乗せ条例（営業日数制限・区域制限等）を確認してください。")

    # Cap score to 100
    score = min(100, max(0, score))

    # 総合評価
    if score >= 85:
        grade, summary = 'S', '民泊営業に極めて適した物件。速やかに事業開始が見込めます。'
    elif score >= 70:
        grade, summary = 'A', '民泊営業に適した物件。一部確認事項ありますが大きな障害なし。'
    elif score >= 55:
        grade, summary = 'B', '民泊営業は可能ですが、確認・対応が必要な項目があります。'
    elif score >= 40:
        grade, summary = 'C', '民泊営業にいくつかの課題あり。費用対効果を慎重に検討。'
    else:
        grade, summary = 'D', '民泊営業に重大な障害あり。他の物件の検討を推奨。'

    return {
        'grade': grade, 'score': score, 'summary': summary,
        'merits': merits, 'risks': risks, 'advice': advice,
    }


def format_evaluation_report(eval_result: Dict) -> str:
    """Format evaluation result as readable report."""
    lines = [
        f"{'='*50}",
        f"  民泊物件 総合評価: {eval_result['grade']} ({eval_result['score']}/100)",
        f"{'='*50}",
        f"\n{eval_result['summary']}\n",
    ]
    if eval_result['merits']:
        lines.append("─── メリット ───")
        for m in eval_result['merits']:
            lines.append(f"  {m}")
        lines.append("")
    if eval_result['risks']:
        lines.append("─── 懸念点・リスク ───")
        for r in eval_result['risks']:
            lines.append(f"  {r}")
        lines.append("")
    if eval_result['advice']:
        lines.append("─── 専門家からのアドバイス ───")
        for a in eval_result['advice']:
            lines.append(f"  {a}")
    return '\n'.join(lines)


# ========================================
# 物件リストの収益シミュレーション
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
    """Calculate 民泊 investment metrics for each property."""
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
