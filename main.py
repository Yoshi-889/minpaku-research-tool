"""不動産物件スクレイピング＆民泊適性分析ツール（個人利用PoC版）

Streamlit UI for real estate property scraping and minpaku analysis.
Usage: streamlit run main.py
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os
import sys
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper.suumo_scraper import SuumoScraper
from scraper.homes_scraper import HomesScraper
from scraper.athome_scraper import AthomeScraper
from scraper.local_scraper import LocalScraper, LOCAL_COMPANIES
from utils.data_cleaner import remove_duplicates, merge_properties
from utils.analyzer import (
    calculate_minpaku_metrics,
    evaluate_minpaku_property,
    format_evaluation_report,
    generate_summary_stats,
    ASO_TOURISM_DATA,
    GOOD_YOTO_CHIIKI,
    BAD_YOTO_CHIIKI,
)

# ========================================
# Page Config
# ========================================
st.set_page_config(
    page_title="民泊物件リサーチツール",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ========================================
# Custom CSS
# ========================================
st.markdown("""
<style>
    .grade-S { color: #FFD700; font-size: 2em; font-weight: bold; }
    .grade-A { color: #4CAF50; font-size: 2em; font-weight: bold; }
    .grade-B { color: #2196F3; font-size: 2em; font-weight: bold; }
    .grade-C { color: #FF9800; font-size: 2em; font-weight: bold; }
    .grade-D { color: #F44336; font-size: 2em; font-weight: bold; }
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 16px;
        margin: 4px 0;
        border-left: 4px solid #4CAF50;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
</style>
""", unsafe_allow_html=True)

# ========================================
# Session State
# ========================================
if 'search_results' not in st.session_state:
    st.session_state.search_results = None
if 'analyzed_df' not in st.session_state:
    st.session_state.analyzed_df = None
if 'search_running' not in st.session_state:
    st.session_state.search_running = False


# ========================================
# Sidebar - Search Settings
# ========================================
with st.sidebar:
    st.title("🏠 検索設定")

    st.header("📍 エリア設定")
    prefecture = st.selectbox("都道府県", ['熊本県', '福岡県', '大分県'], index=0)
    city = st.text_input("市区町村", value='阿蘇市')

    st.header("💰 条件フィルター")
    col1, col2 = st.columns(2)
    with col1:
        rent_min = st.number_input("賃料下限 (万円)", min_value=0.0, value=0.0, step=0.5)
    with col2:
        rent_max = st.number_input("賃料上限 (万円)", min_value=0.0, value=20.0, step=0.5)

    col3, col4 = st.columns(2)
    with col3:
        area_min = st.number_input("面積下限 (㎡)", min_value=0, value=0, step=5)
    with col4:
        area_max = st.number_input("面積上限 (㎡)", min_value=0, value=200, step=5)

    max_pages = st.slider("最大ページ数（サイトごと）", 1, 10, 3)

    st.header("🌐 データソース選択")
    st.caption("取得するサイトを選択してください")
    use_suumo = st.checkbox("SUUMO", value=True)
    use_homes = st.checkbox("LIFULL HOME'S", value=True)
    use_athome = st.checkbox("アットホーム", value=True)

    st.subheader("🏢 地元不動産会社")
    st.caption("個別の不動産会社サイトからもデータを取得")
    selected_locals = {}
    for key, company in LOCAL_COMPANIES.items():
        selected_locals[key] = st.checkbox(
            f"{company['name']}",
            value=False,
            help=company.get('description', ''),
        )

    st.header("📊 民泊シミュレーション設定")
    daily_rate = st.number_input("想定宿泊単価 (円/泊)", min_value=1000, value=8000, step=500)
    occupancy_rate = st.slider("想定稼働率 (%)", 10, 90, 45) / 100
    setup_cost = st.number_input("初期セットアップ費用 (円)", min_value=0, value=500000, step=50000)
    monthly_utilities = st.number_input("月額光熱費 (円)", min_value=0, value=15000, step=1000)
    management_rate = st.slider("管理費率 (%)", 0, 50, 20) / 100
    is_365_days = st.radio("営業形態", ['旅館業法（365日）', '民泊新法（180日）']) == '旅館業法（365日）'


# ========================================
# Main Content
# ========================================
st.title("🏠 民泊物件リサーチツール")
st.caption("不動産物件のスクレイピング＆民泊適性分析 | 個人利用PoC版")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 物件検索", "📊 分析ダッシュボード", "🏛️ 個別物件評価", "📋 データエクスポート"
])

# ========================================
# Tab 1: Property Search
# ========================================
with tab1:
    st.header("物件検索")
    st.info(
        "検索条件をサイドバーで設定し、下のボタンを押して検索を実行してください。"
        "検索はリアルタイムで各サイトにアクセスするため、数分かかる場合があります。"
    )

    # Search button
    col_btn1, col_btn2 = st.columns([1, 3])
    with col_btn1:
        search_clicked = st.button("🔍 検索実行", type="primary", use_container_width=True)
    with col_btn2:
        if st.session_state.search_results is not None:
            st.success(
                f"前回の検索結果: {len(st.session_state.search_results)} 件 "
                f"(重複排除済み)"
            )

    if search_clicked:
        conditions = {
            'prefecture': prefecture,
            'city': city,
            'rent_min': rent_min if rent_min > 0 else None,
            'rent_max': rent_max if rent_max > 0 else None,
            'area_min': area_min if area_min > 0 else None,
            'area_max': area_max if area_max > 0 else None,
            'max_pages': max_pages,
        }

        all_results = {}
        total_found = 0

        progress_bar = st.progress(0, text="検索準備中...")
        status_text = st.empty()

        # Determine total steps
        sites = []
        if use_suumo: sites.append(('SUUMO', SuumoScraper))
        if use_homes: sites.append(("LIFULL HOME'S", HomesScraper))
        if use_athome: sites.append(('アットホーム', AthomeScraper))
        local_sites = [k for k, v in selected_locals.items() if v]
        total_steps = len(sites) + len(local_sites)
        step = 0

        # Scrape major sites
        for site_name, ScraperClass in sites:
            step += 1
            progress_bar.progress(step / max(total_steps, 1), text=f"{site_name} を検索仭...")
            status_text.text(f"🔄 {site_name} からデータを取得しています...")

            try:
                scraper = ScraperClass()
                results = scraper.scrape(conditions)
                if results:
                    all_results[site_name] = results
                    total_found += len(results)
                    status_text.text(f"✅ {site_name}: {len(results)} 件取得")
                else:
                    status_text.text(f"⚠️ {site_name}: 物件が見つかりませんでした")
            except Exception as e:
                status_text.text(f"❌ {site_name}: エラー - {str(e)[:100]}")

        # Scrape local companies
        for company_key in local_sites:
            step += 1
            company = LOCAL_COMPANIES[company_key]
            progress_bar.progress(step / max(total_steps, 1),
                                  text=f"{company['name']} を検索仭...")
            status_text.text(f"🔄 {company['name']} からデータを取得しています...")

            try:
                scraper = LocalScraper(company_key)
                results = scraper.scrape(conditions)
                if results:
                    all_results[company['name']] = results
                    total_found += len(results)
                    status_text.text(f"✅ {company['name']}: {len(results)} 件取得")
                else:
                    status_text.text(f"⚠️ {company['name']}: 物件が見つかりませんでした")
            except Exception as e:
                status_text.text(f"❌ {company['name']}: エラー - {str(e)[:100]}")

        progress_bar.progress(1.0, text="データ統合・重複排除中...")

        # Merge and dedup
        if all_results:
            merged = merge_properties(all_results)
            st.session_state.search_results = merged

            # Calculate metrics
            analyzed_df = calculate_minpaku_metrics(
                merged,
                daily_rate=daily_rate,
                occupancy_rate=occupancy_rate,
                setup_cost=setup_cost,
                monthly_utilities=monthly_utilities,
                management_rate=management_rate,
                is_365_days=is_365_days,
            )
            st.session_state.analyzed_df = analyzed_df

            progress_bar.progress(1.0, text="完了！")
            st.success(
                f"検索完了！ {total_found} 件取得 → 重複排除後 {len(merged)} 件 "
                f"(民泊分析済み)"
            )
        else:
            progress_bar.progress(1.0, text="完了")
            st.warning("物件が見つかりませんでした。検索条件を変更してみてください。")

    # Display results
    if st.session_state.analyzed_df is not None and not st.session_state.analyzed_df.empty:
        df = st.session_state.analyzed_df

        st.subheader(f"検索結果: {len(df)} 件")

        # Sort options
        sort_col = st.selectbox(
            "並び替え",
            ['minpaku_score', 'rent', 'area', 'roi_percent', 'net_monthly_profit'],
            format_func=lambda x: {
                'minpaku_score': '民泊スコア（高い順）',
                'rent': '賃料（安い順）',
                'area': '面積（広い順）',
                'roi_percent': 'ROI（高い順）',
                'net_monthly_profit': '月間利益（高い順）',
            }.get(x, x)
        )

        ascending = sort_col == 'rent'
        display_df = df.sort_values(sort_col, ascending=ascending, na_position='last')

        # Display columns
        display_cols = [
            'minpaku_grade', 'minpaku_score', 'site', 'building_name', 'address',
            'rent', 'management_fee', 'layout', 'area', 'age',
            'net_monthly_profit', 'roi_percent', 'breakeven_months',
            'transport', 'url',
        ]
        available_cols = [c for c in display_cols if c in display_df.columns]

        col_config = {
            'minpaku_grade': st.column_config.TextColumn('評価', width='small'),
            'minpaku_score': st.column_config.ProgressColumn('スコア', min_value=0, max_value=100),
            'site': st.column_config.TextColumn('サイト', width='small'),
            'building_name': st.column_config.TextColumn('物件名'),
            'address': st.column_config.TextColumn('住所'),
            'rent': st.column_config.NumberColumn('賃料(万円)', format="%.1f万円"),
            'management_fee': st.column_config.NumberColumn('管理費(万円)', format="%.2f万円"),
            'layout': st.column_config.TextColumn('間取り', width='small'),
            'area': st.column_config.NumberColumn('面積(㎡)', format="%.1f㎡"),
            'age': st.column_config.NumberColumn('築年数', format="%d年"),
            'net_monthly_profit': st.column_config.NumberColumn('月間利益(円)', format="¥%,.0f"),
            'roi_percent': st.column_config.NumberColumn('ROI', format="%.1f%%"),
            'breakeven_months': st.column_config.NumberColumn('回収期間(月)', format="%.1fヶ月"),
            'transport': st.column_config.TextColumn('交通'),
            'url': st.column_config.LinkColumn('リンク', width='small'),
        }

        st.dataframe(
            display_df[available_cols],
            column_config=col_config,
            use_container_width=True,
            height=500,
        )


# ========================================
# Tab 2: Analysis Dashboard
# ========================================
with tab2:
    st.header("📊 分析ダッシュボード")

    if st.session_state.analyzed_df is not None and not st.session_state.analyzed_df.empty:
        df = st.session_state.analyzed_df
        stats = generate_summary_stats(df)

        # KPI Cards
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("総物件数", f"{stats.get('total_properties', 0)} 件")
        with col2:
            st.metric("平均賃料", f"{stats.get('rent_avg', 0):.1f} 万円")
        with col3:
            st.metric("平均民泊スコア", f"{stats.get('avg_minpaku_score', 0):.0f} / 100")
        with col4:
            profitable = stats.get('profitable_count', 0)
            total = stats.get('total_properties', 1)
            st.metric("黒字物件比率", f"{profitable}/{total} ({profitable/total*100:.0f}%)")

        st.divider()

        # Charts
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            st.subheader("サイト別物件数")
            if 'site' in df.columns:
                site_counts = df['site'].value_counts()
                fig = px.pie(values=site_counts.values, names=site_counts.index,
                             color_discrete_sequence=px.colors.qualitative.Set3)
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)

        with col_chart2:
            st.subheader("賃料分布")
            if 'rent' in df.columns:
                rent_data = df['rent'].dropna()
                fig = px.histogram(rent_data, nbins=20, labels={'value': '賃料 (万円)', 'count': '件数'},
                                   color_discrete_sequence=['#4CAF50'])
                fig.update_layout(height=350, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

        col_chart3, col_chart4 = st.columns(2)

        with col_chart3:
            st.subheader("民泊スコア分布")
            if 'minpaku_score' in df.columns:
                fig = px.histogram(df, x='minpaku_score', nbins=20,
                                   labels={'minpaku_score': 'スコア', 'count': '件数'},
                                   color_discrete_sequence=['#2196F3'])
                fig.update_layout(height=350, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

        with col_chart4:
            st.subheader("賃料 vs 面積")
            if 'rent' in df.columns and 'area' in df.columns:
                fig = px.scatter(df.dropna(subset=['rent', 'area']),
                                 x='area', y='rent',
                                 color='minpaku_grade' if 'minpaku_grade' in df.columns else None,
                                 hover_data=['building_name', 'layout'],
                                 labels={'area': '面積 (㎡)', 'rent': '賃料 (万円)'},
                                 color_discrete_map={'S': '#FFD700', 'A': '#4CAF50',
                                                     'B': '#2196F3', 'C': '#FF9800', 'D': '#F44336'})
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)

        # Profitability chart
        st.subheader("月間利益ランキング TOP 20")
        if 'net_monthly_profit' in df.columns:
            top20 = df.nlargest(20, 'net_monthly_profit')
            labels = top20.apply(
                lambda r: f"{r.get('building_name', '不明')[:15]} ({r.get('layout', '')})", axis=1
            )
            fig = go.Figure(go.Bar(
                x=top20['net_monthly_profit'],
                y=labels,
                orientation='h',
                marker_color=top20['net_monthly_profit'].apply(
                    lambda x: '#4CAF50' if x > 0 else '#F44336'
                ),
                text=top20['net_monthly_profit'].apply(lambda x: f'¥{x:,.0f}'),
                textposition='outside',
            ))
            fig.update_layout(height=max(400, len(top20) * 30), yaxis={'autorange': 'reversed'},
                              xaxis_title='月間利益 (円)', margin=dict(l=200))
            st.plotly_chart(fig, use_container_width=True)

        # Layout distribution
        if 'layout_dist' in stats:
            st.subheader("間取り分布")
            layout_dist = stats['layout_dist']
            fig = px.bar(x=list(layout_dist.keys()), y=list(layout_dist.values()),
                         labels={'x': '間取り', 'y': '件数'},
                         color_discrete_sequence=['#9C27B0'])
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("まず「物件検索」タブで検索を実行してください。")


# ========================================
# Tab 3: Individual Property Evaluation
# ========================================
with tab3:
    st.header("🏛️ 個別物件の民泊適性評価")
    st.caption(
        "物件の詳細情報を入力して、民泊（旅館業法/民泊新法）での営業適性を評価します。"
        "耐震基準・用途地域・周辺施設・建物規模・消防設備の5つの観点で総合評価を行います。"
    )

    with st.form("eval_form"):
        col1, col2 = st.columns(2)

        with col1:
            eval_year_input = st.text_input(
                "築年月日",
                placeholder="例: 1985, 昭和60年, 平成5年",
                help="1981年（昭和56年）6月以降なら新耐震基準"
            )
            eval_yoto = st.selectbox(
                "用途地域",
                ['不明'] + GOOD_YOTO_CHIIKI + BAD_YOTO_CHIIKI + ['工業地域', '工業専用地域'],
            )
            eval_shigaika = st.radio(
                "市街化調整区域か？",
                ['不明', 'いいえ（市街化区域等）', 'はい（調整区域）']
            )

        with col2:
            eval_school_dist = st.number_input(
                "最寄り学校・保育園・公園からの距離 (m)",
                min_value=0, value=0, step=10,
                help="0の場合は「不明」として扱います"
            )
            eval_area = st.number_input(
                "延床面積 (㎡)",
                min_value=0.0, value=0.0, step=5.0,
                help="0の場合は「不明」として扱います"
            )
            eval_fire = st.radio(
                "消防設備の有無",
                ['不明', 'あり', 'なし']
            )

        eval_notes = st.text_area("その他の特記事項", placeholder="例: 駅から徒歩5分、駐車場あり")

        submitted = st.form_submit_button("📋 評価実行", type="primary")

    if submitted:
        # Parse building year
        import re
        building_year = None
        if eval_year_input:
            year_str = eval_year_input.strip()
            # Try direct number
            if year_str.isdigit():
                building_year = int(year_str)
            else:
                # 昭和
                m = re.search(r'昭和\s*(\d+)', year_str)
                if m:
                    building_year = 1925 + int(m.group(1))
                # 平成
                m = re.search(r'平成\s*(\d+)', year_str)
                if m:
                    building_year = 1988 + int(m.group(1))
                # 令和
                m = re.search(r'令和\s*(\d+)', year_str)
                if m:
                    building_year = 2018 + int(m.group(1))
                # Just year number
                m = re.search(r'(\d{4})', year_str)
                if m and not building_year:
                    building_year = int(m.group(1))

        yoto = eval_yoto if eval_yoto != '不明' else None
        shigaika = None
        if eval_shigaika == 'はい（調整区域）':
            shigaika = True
        elif eval_shigaika == 'いいえ（市街化区域等）':
            shigaika = False

        school_dist = eval_school_dist if eval_school_dist > 0 else None
        floor_area = eval_area if eval_area > 0 else None
        fire_equip = None
        if eval_fire == 'あり':
            fire_equip = True
        elif eval_fire == 'なし':
            fire_equip = False

        result = evaluate_minpaku_property(
            building_year=building_year,
            yoto_chiiki=yoto,
            is_shigaika_chosei=shigaika,
            school_distance_m=school_dist,
            total_floor_area_m2=floor_area,
            has_fire_equipment=fire_equip,
            additional_notes=eval_notes,
        )

        # Display result
        st.divider()

        grade_colors = {'S': '🥇', 'A': '🟢', 'B': '🔵', 'C': '🟠', 'D': '🔴'}
        grade_icon = grade_colors.get(result['grade'], '⚪')

        col_grade, col_score, col_summary = st.columns([1, 1, 3])
        with col_grade:
            st.metric("総合評価", f"{grade_icon} {result['grade']}")
        with col_score:
            st.metric("スコア", f"{result['score']} / 100")
        with col_summary:
            st.info(result['summary'])

        col_left, col_right = st.columns(2)

        with col_left:
            if result['merits']:
                st.subheader("✅ メリット")
                for m in result['merits']:
                    st.success(m)

        with col_right:
            if result['risks']:
                st.subheader("⚠️ 懵念点・リスク")
                for r in result['risks']:
                    st.warning(r)

        if result['advice']:
            st.subheader("💡 専門家からのアドバイス")
            for a in result['advice']:
                st.info(a)

        # Full text report
        with st.expander("📄 テキストレポート（コピー用）"):
            st.code(format_evaluation_report(result), language=None)


# ========================================
# Tab 4: Data Export
# ========================================
with tab4:
    st.header("📋 データエクスポート")

    if st.session_state.analyzed_df is not None and not st.session_state.analyzed_df.empty:
        df = st.session_state.analyzed_df

        # Export columns selection
        all_cols = list(df.columns)
        export_cols = st.multiselect(
            "エクスポートする列を選択",
            all_cols,
            default=[c for c in [
                'minpaku_grade', 'minpaku_score', 'site', 'building_name', 'address',
                'rent', 'management_fee', 'layout', 'area', 'age', 'age_text',
                'transport', 'net_monthly_profit', 'roi_percent', 'breakeven_months', 'url',
            ] if c in all_cols]
        )

        if export_cols:
            export_df = df[export_cols]

            col1, col2 = st.columns(2)
            with col1:
                # CSV Export
                csv_data = export_df.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    "📥 CSVダウンロード",
                    csv_data,
                    file_name=f"minpaku_properties_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime='text/csv',
                    type="primary",
                )

            with col2:
                # Excel Export
                import io
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    export_df.to_excel(writer, index=False, sheet_name='物件リスト')

                    # Add summary sheet
                    stats = generate_summary_stats(df)
                    summary_data = {
                        '項目': list(stats.keys()),
                        '値': [str(v) for v in stats.values()],
                    }
                    pd.DataFrame(summary_data).to_excel(writer, index=False, sheet_name='サマリー')

                st.download_button(
                    "📥 Excelダウンロード",
                    buffer.getvalue(),
                    file_name=f"minpaku_properties_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                )

            st.subheader("プレビュー")
            st.dataframe(export_df, use_container_width=True, height=400)
    else:
        st.info("まず「物件検索」タブで検索を実行してください。")


# ========================================
# Footer
# ========================================
st.divider()
st.caption(
    "⚠️ このツールは個人利用・学習目的に限定されます。"
    "商用化や大規模利用を行う場合は、各サイトの公式APIへの移行を検討してください。"
    f" | 最終更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
)
