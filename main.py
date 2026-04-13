"""ä¸åç£ç©ä»¶ã¹ã¯ã¬ã¤ãã³ã°ï¼æ°æ³é©æ§åæãã¼ã«ï¼åäººå©ç¨PoCçï¼

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
    page_title="æ°æ³ç©ä»¶ãªãµã¼ããã¼ã«",
    page_icon="ð ",
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
    st.title("ð  æ¤ç´¢è¨­å®")

    st.header("ð ã¨ãªã¢è¨­å®")
    prefecture = st.selectbox("é½éåºç", ['çæ¬ç', 'ç¦å²¡ç', 'å¤§åç'], index=0)
    city = st.text_input("å¸åºçºæ", value='é¿èå¸')

    st.header("ð° æ¡ä»¶ãã£ã«ã¿ã¼")
    col1, col2 = st.columns(2)
    with col1:
        rent_min = st.number_input("è³æä¸é (ä¸å)", min_value=0.0, value=0.0, step=0.5)
    with col2:
        rent_max = st.number_input("è³æä¸é (ä¸å)", min_value=0.0, value=20.0, step=0.5)

    col3, col4 = st.columns(2)
    with col3:
        area_min = st.number_input("é¢ç©ä¸é (ã¡)", min_value=0, value=0, step=5)
    with col4:
        area_max = st.number_input("é¢ç©ä¸é (ã¡)", min_value=0, value=200, step=5)

    max_pages = st.slider("æå¤§ãã¼ã¸æ°ï¼ãµã¤ããã¨ï¼", 1, 10, 3)

    st.header("ð ãã¼ã¿ã½ã¼ã¹é¸æ")
    st.caption("åå¾ãããµã¤ããé¸æãã¦ãã ãã")
    use_suumo = st.checkbox("SUUMO", value=True)
    use_homes = st.checkbox("LIFULL HOME'S", value=True)
    use_athome = st.checkbox("ã¢ãããã¼ã ", value=True)

    st.subheader("ð¢ å°åä¸åç£ä¼ç¤¾")
    st.caption("åå¥ã®ä¸åç£ä¼ç¤¾ãµã¤ãããããã¼ã¿ãåå¾")
    selected_locals = {}
    for key, company in LOCAL_COMPANIES.items():
        selected_locals[key] = st.checkbox(
            f"{company['name']}",
            value=False,
            help=company.get('description', ''),
        )

    st.header("ð æ°æ³ã·ãã¥ã¬ã¼ã·ã§ã³è¨­å®")
    daily_rate = st.number_input("æ³å®å®¿æ³åä¾¡ (å/æ³)", min_value=1000, value=8000, step=500)
    occupancy_rate = st.slider("æ³å®ç¨¼åç (%)", 10, 90, 45) / 100
    setup_cost = st.number_input("åæã»ããã¢ããè²»ç¨ (å)", min_value=0, value=500000, step=50000)
    monthly_utilities = st.number_input("æé¡åç±è²» (å)", min_value=0, value=15000, step=1000)
    management_rate = st.slider("ç®¡çè²»ç (%)", 0, 50, 20) / 100
    is_365_days = st.radio("å¶æ¥­å½¢æ", ['æé¤¨æ¥­æ³ï¼365æ¥ï¼', 'æ°æ³æ°æ³ï¼180æ¥ï¼']) == 'æé¤¨æ¥­æ³ï¼365æ¥ï¼'


# ========================================
# Main Content
# ========================================
st.title("ð  æ°æ³ç©ä»¶ãªãµã¼ããã¼ã«")
st.caption("ä¸åç£ç©ä»¶ã®ã¹ã¯ã¬ã¤ãã³ã°ï¼æ°æ³é©æ§åæ | åäººå©ç¨PoCç")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "ð ç©ä»¶æ¤ç´¢", "ð åæããã·ã¥ãã¼ã", "ðï¸ åå¥ç©ä»¶è©ä¾¡", "ð ãã¼ã¿ã¨ã¯ã¹ãã¼ã"
])

# ========================================
# Tab 1: Property Search
# ========================================
with tab1:
    st.header("ç©ä»¶æ¤ç´¢")
    st.info(
        "æ¤ç´¢æ¡ä»¶ããµã¤ããã¼ã§è¨­å®ããä¸ã®ãã¿ã³ãæ¼ãã¦æ¤ç´¢ãå®è¡ãã¦ãã ããã"
        "æ¤ç´¢ã¯ãªã¢ã«ã¿ã¤ã ã§åãµã¤ãã«ã¢ã¯ã»ã¹ãããããæ°åãããå ´åãããã¾ãã"
    )

    # Search button
    col_btn1, col_btn2 = st.columns([1, 3])
    with col_btn1:
        search_clicked = st.button("ð æ¤ç´¢å®è¡", type="primary", use_container_width=True)
    with col_btn2:
        if st.session_state.search_results is not None:
            st.success(
                f"ååã®æ¤ç´¢çµæ: {len(st.session_state.search_results)} ä»¶ "
                f"(éè¤æé¤æ¸ã¿)"
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

        progress_bar = st.progress(0, text="æ¤ç´¢æºåä»­...")
        status_text = st.empty()

        # Determine total steps
        sites = []
        if use_suumo: sites.append(('SUUMO', SuumoScraper))
        if use_homes: sites.append(("LIFULL HOME'S", HomesScraper))
        if use_athome: sites.append(('ã¢ãããã¼ã ', AthomeScraper))
        local_sites = [k for k, v in selected_locals.items() if v]
        total_steps = len(sites) + len(local_sites)
        step = 0

        # Scrape major sites
        for site_name, ScraperClass in sites:
            step += 1
            progress_bar.progress(step / max(total_steps, 1), text=f"{site_name} ãæ¤ç´¢ä»­...")
            status_text.text(f"ð {site_name} ãããã¼ã¿ãåå¾ãã¦ãã¾ã...")

            try:
                scraper = ScraperClass()
                results = scraper.scrape(conditions)
                if results:
                    all_results[site_name] = results
                    total_found += len(results)
                    status_text.text(f"â {site_name}: {len(results)} ä»¶åå¾")
                else:
                    status_text.text(f"â ï¸ {site_name}: ç©ä»¶ãè¦ã¤ããã¾ããã§ãã")
            except Exception as e:
                status_text.text(f"â {site_name}: ã¨ã©ã¼ - {str(e)[:100]}")

        # Scrape local companies
        for company_key in local_sites:
            step += 1
            company = LOCAL_COMPANIES[company_key]
            progress_bar.progress(step / max(total_steps, 1),
                                  text=f"{company['name']} ãæ¤ç´¢ä¸­...")
            status_text.text(f"ð {company['name']} ãããã¼ã¿ãåå¾ãã¦ãã¾ã...")

            try:
                scraper = LocalScraper(company_key)
                results = scraper.scrape(conditions)
                if results:
                    all_results[company['name']] = results
                    total_found += len(results)
                    status_text.text(f"â {company['name']}: {len(results)} ä»¶åå¾")
                else:
                    status_text.text(f"â ï¸ {company['name']}: ç©ä»¶ãè¦ã¤ããã¾ããã§ãã")
            except Exception as e:
                status_text.text(f"â {company['name']}: ã¨ã©ã¼ - {str(e)[:100]}")

        progress_bar.progress(1.0, text="ãã¼ã¿çµ±åã»éè¤æé¤ä¸­...")

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

            progress_bar.progress(1.0, text="å®äºï¼")
            st.success(
                f"æ¤ç´¢å®äºï¼ {total_found} ä»¶åå¾ â éè¤æé¤å¾ {len(merged)} ä»¶ "
                f"(æ°æ³åææ¸ã¿)"
            )
        else:
            progress_bar.progress(1.0, text="å®äº")
            st.warning("ç©ä»¶ãè¦ã¤ããã¾ããã§ãããæ¤ç´¢æ¡ä»¶ãå¤æ´ãã¦ã¿ã¦ãã ããã")

    # Display results
    if st.session_state.analyzed_df is not None and not st.session_state.analyzed_df.empty:
        df = st.session_state.analyzed_df

        st.subheader(f"æ¤ç´¢çµæ: {len(df)} ä»¶")

        # Sort options
        sort_col = st.selectbox(
            "ä¸¦ã³æ¿ã",
            ['minpaku_score', 'rent', 'area', 'roi_percent', 'net_monthly_profit'],
            format_func=lambda x: {
                'minpaku_score': 'æ°æ³ã¹ã³ã¢ï¼é«ãé ï¼',
                'rent': 'è³æï¼å®ãé ï¼',
                'area': 'é¢ç©ï¼åºãé ï¼',
                'roi_percent': 'ROIï¼é«ãé ï¼',
                'net_monthly_profit': 'æéå©çï¼é«ãé ï¼',
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
            'minpaku_grade': st.column_config.TextColumn('è©ä¾¡', width='small'),
            'minpaku_score': st.column_config.ProgressColumn('ã¹ã³ã¢', min_value=0, max_value=100),
            'site': st.column_config.TextColumn('ãµã¤ã', width='small'),
            'building_name': st.column_config.TextColumn('ç©ä»¶å'),
            'address': st.column_config.TextColumn('ä½æ'),
            'rent': st.column_config.NumberColumn('è³æ(ä¸å)', format="%.1fä¸å"),
            'management_fee': st.column_config.NumberColumn('ç®¡çè²»(ä¸å)', format="%.2fä¸å"),
            'layout': st.column_config.TextColumn('éåã', width='small'),
            'area': st.column_config.NumberColumn('é¢ç©(ã¡)', format="%.1fã¡"),
            'age': st.column_config.NumberColumn('ç¯å¹´æ°', format="%då¹´"),
            'net_monthly_profit': st.column_config.NumberColumn('æéå©ç(å)', format="Â¥%,.0f"),
            'roi_percent': st.column_config.NumberColumn('ROI', format="%.1f%%"),
            'breakeven_months': st.column_config.NumberColumn('ååæé(æ)', format="%.1fã¶æ"),
            'transport': st.column_config.TextColumn('äº¤é'),
            'url': st.column_config.LinkColumn('ãªã³ã¯', width='small'),
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
    st.header("ð åæããã·ã¥ãã¼ã")

    if st.session_state.analyzed_df is not None and not st.session_state.analyzed_df.empty:
        df = st.session_state.analyzed_df
        stats = generate_summary_stats(df)

        # KPI Cards
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("ç·ç©ä»¶æ°", f"{stats.get('total_properties', 0)} ä»¶")
        with col2:
            st.metric("å¹³åè³æ", f"{stats.get('rent_avg', 0):.1f} ä¸å")
        with col3:
            st.metric("å¹³åæ°æ³ã¹ã³ã¢", f"{stats.get('avg_minpaku_score', 0):.0f} / 100")
        with col4:
            profitable = stats.get('profitable_count', 0)
            total = stats.get('total_properties', 1)
            st.metric("é»å­ç©ä»¶æ¯ç", f"{profitable}/{total} ({profitable/total*100:.0f}%)")

        st.divider()

        # Charts
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            st.subheader("ãµã¤ãå¥ç©ä»¶æ°")
            if 'site' in df.columns:
                site_counts = df['site'].value_counts()
                fig = px.pie(values=site_counts.values, names=site_counts.index,
                             color_discrete_sequence=px.colors.qualitative.Set3)
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)

        with col_chart2:
            st.subheader("è³æåå¸")
            if 'rent' in df.columns:
                rent_data = df['rent'].dropna()
                fig = px.histogram(rent_data, nbins=20, labels={'value': 'è³æ (ä¸å)', 'count': 'ä»¶æ°'},
                                   color_discrete_sequence=['#4CAF50'])
                fig.update_layout(height=350, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

        col_chart3, col_chart4 = st.columns(2)

        with col_chart3:
            st.subheader("æ°æ³ã¹ã³ã¢åå¸")
            if 'minpaku_score' in df.columns:
                fig = px.histogram(df, x='minpaku_score', nbins=20,
                                   labels={'minpaku_score': 'ã¹ã³ã¢', 'count': 'ä»¶æ°'},
                                   color_discrete_sequence=['#2196F3'])
                fig.update_layout(height=350, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

        with col_chart4:
            st.subheader("è³æ vs é¢ç©")
            if 'rent' in df.columns and 'area' in df.columns:
                fig = px.scatter(df.dropna(subset=['rent', 'area']),
                                 x='area', y='rent',
                                 color='minpaku_grade' if 'minpaku_grade' in df.columns else None,
                                 hover_data=['building_name', 'layout'],
                                 labels={'area': 'é¢ç© (ã¡)', 'rent': 'è³æ (ä¸å)'},
                                 color_discrete_map={'S': '#FFD700', 'A': '#4CAF50',
                                                     'B': '#2196F3', 'C': '#FF9800', 'D': '#F44336'})
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)

        # Profitability chart
        st.subheader("æéå©çã©ã³ã­ã³ã° TOP 20")
        if 'net_monthly_profit' in df.columns:
            top20 = df.nlargest(20, 'net_monthly_profit')
            labels = top20.apply(
                lambda r: f"{r.get('building_name', 'ä¸æ')[:15]} ({r.get('layout', '')})", axis=1
            )
            fig = go.Figure(go.Bar(
                x=top20['net_monthly_profit'],
                y=labels,
                orientation='h',
                marker_color=top20['net_monthly_profit'].apply(
                    lambda x: '#4CAF50' if x > 0 else '#F44336'
                ),
                text=top20['net_monthly_profit'].apply(lambda x: f'Â¥{x:,.0f}'),
                textposition='outside',
            ))
            fig.update_layout(height=max(400, len(top20) * 30), yaxis={'autorange': 'reversed'},
                              xaxis_title='æéå©ç (å)', margin=dict(l=200))
            st.plotly_chart(fig, use_container_width=True)

        # Layout distribution
        if 'layout_dist' in stats:
            st.subheader("éåãåå¸")
            layout_dist = stats['layout_dist']
            fig = px.bar(x=list(layout_dist.keys()), y=list(layout_dist.values()),
                         labels={'x': 'éåã', 'y': 'ä»¶æ°'},
                         color_discrete_sequence=['#9C27B0'])
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("ã¾ããç©ä»¶æ¤ç´¢ãã¿ãã§æ¤ç´¢ãå®è¡ãã¦ãã ããã")


# ========================================
# Tab 3: Individual Property Evaluation
# ========================================
with tab3:
    st.header("ðï¸ åå¥ç©ä»¶ã®æ°æ³é©æ§è©ä¾¡")
    st.caption(
        "ç©ä»¶ã®è©³ç´°æå ±ãå¥åãã¦ãæ°æ³ï¼æé¤¨æ¥­æ³/æ°æ³æ°æ³ï¼ã§ã®å¶æ¥­é©æ§ãè©ä¾¡ãã¾ãã"
        "èéåºæºã»ç¨éå°åã»å¨è¾ºæ½è¨­ã»å»ºç©è¦æ¨¡ã»æ¶é²è¨­åã®5ã¤ã®è¦³ç¹ã§ç·åè©ä¾¡ãè¡ãã¾ãã"
    )

    with st.form("eval_form"):
        col1, col2 = st.columns(2)

        with col1:
            eval_year_input = st.text_input(
                "ç¯å¹´ææ¥",
                placeholder="ä¾: 1985, æ­å60å¹´, å¹³æ5å¹´",
                help="1981å¹´ï¼æ­å56å¹´ï¼6æä»¥éãªãæ°èéåºæº"
            )
            eval_yoto = st.selectbox(
                "ç¨éå°å",
                ['ä¸æ'] + GOOD_YOTO_CHIIKI + BAD_YOTO_CHIIKI + ['å·¥æ¥­å°å', 'å·¥æ¥­å°ç¨å°å'],
            )
            eval_shigaika = st.radio(
                "å¸è¡åèª¿æ´åºåãï¼",
                ['ä¸æ', 'ãããï¼å¸è¡ååºåç­ï¼', 'ã¯ãï¼èª¿æ´åºåï¼']
            )

        with col2:
            eval_school_dist = st.number_input(
                "æå¯ãå­¦æ ¡ã»ä¿è²åã»å¬åããã®è·é¢ (m)",
                min_value=0, value=0, step=10,
                help="0ã®å ´åã¯ãä¸æãã¨ãã¦æ±ãã¾ã"
            )
            eval_area = st.number_input(
                "å»¶åºé¢ç© (ã¡)",
                min_value=0.0, value=0.0, step=5.0,
                help="0ã®å ´åã¯ãä¸æãã¨ãã¦æ±ãã¾ã"
            )
            eval_fire = st.radio(
                "æ¶é²è¨­åã®æç¡",
                ['ä¸æ', 'ãã', 'ãªã']
            )

   ¾ã"
            )
            eval_area = st.number_input(
                "å»¶åºé¢ç© (ã¡)",
                min_value=0.0, value=0.0, step=5.0,
                help="0ã®å ´åã¯ãä¸æãã¨ãã¦æ±ãã¾ã"
            )
            eval_fire = st.radio(
                "æ¶é²è¨­åã®æç¡",
                ['ä¸æ', 'ãã', 'ãªã']
            )

        eval_notes = st.text_area("ãã®ä»ã®ç¹è¨äºé ", placeholder="ä¾: é§ãã¹å¾æ­©5åãé§è»å ´ãã")

        submitted = st.form_submit_button("ð è©ä¾¡å®è¡", type="primary")

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
                # æ­å
                m = re.search(r'æ­å\s*(\d+)', year_str)
                if m:
                    building_year = 1925 + int(m.group(1))
                # å¹³æ
                m = re.search(r'å¹³æ\s*(\d+)', year_str)
                if m:
                    building_year = 1988 + int(m.group(1))
                # ä»¤å
                m = re.search(r'ä»¤å\s*(\d+)', year_str)
                if m:
                    building_year = 2018 + int(m.group(1))
                # Just year number
                m = re.search(r'(\d{4})', year_str)
                if m and not building_year:
                    building_year = int(m.group(1))

        yoto = eval_yoto if eval_yoto != 'ä¸æ' else None
        shigaika = None
        if eval_shigaika == 'ã¯ãï¼èª¿æ´åºåï¼':
            shigaika = True
        elif eval_shigaika == 'ãããï¼å¸è¡ååºåç­ï¼':
            shigaika = False

        school_dist = eval_school_dist if eval_school_dist > 0 else None
        floor_area = eval_area if eval_area > 0 else None
        fire_equip = None
        if eval_fire == 'ãã':
            fire_equip = True
        elif eval_fire == 'ãªã':
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

        grade_colors = {'S': 'ð¥', 'A': 'ð¢', 'B': 'ðµ', 'C': 'ð ', 'D': 'ð´'}
        grade_icon = grade_colors.get(result['grade'], 'âª')

        col_grade, col_score, col_summary = st.columns([1, 1, 3])
        with col_grade:
            st.metric("ç·åè©ä¾¡", f"{grade_icon} {result['grade']}")
        with col_score:
            st.metric("ã¹ã³ã¢", f"{result['score']} / 100")
        with col_summary:
            st.info(result['summary'])

        col_left, col_right = st.columns(2)

        with col_left:
            if result['merits']:
                st.subheader("â ã¡ãªãã")
                for m in result['merits']:
                    st.success(m)

        with col_right:
            if result['risks']:
                st.subheader("â ï¸ æ¸å¿µç¹ã»ãªã¹ã¯")
                for r in result['risks']:
                    st.warning(r)

        if result['advice']:
            st.subheader("ð¡ å°éå®¶ããã®ã¢ããã¤ã¹")
            for a in result['advice']:
                st.info(a)

        # Full text report
        with st.expander("ð ãã­ã¹ãã¬ãã¼ãï¼ã³ãã¼ç¨ï¼"):
            st.code(format_evaluation_report(result), language=None)


# ========================================
# Tab 4: Data Export
# ========================================
with tab4:
    st.header("ð ãã¼ã¿ã¨ã¯ã¹ãã¼ã")

    if st.session_state.analyzed_df is not None and not st.session_state.analyzed_df.empty:
        df = st.session_state.analyzed_df

        # Export columns selection
        all_cols = list(df.columns)
        export_cols = st.multiselect(
            "ã¨ã¯ã¹ãã¼ãããåãé¸æ",
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
                    "ð¥ CSVãã¦ã³ã­ã¼ã",
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
                    export_df.to_excel(writer, index=False, sheet_name='ç©ä»¶ãªã¹ã')

                    # Add summary sheet
                    stats = generate_summary_stats(df)
                    summary_data = {
                        'é ç®': list(stats.keys()),
                        'å¤': [str(v) for v in stats.values()],
                    }
                    pd.DataFrame(summary_data).to_excel(writer, index=False, sheet_name='ãµããªã¼')

                st.download_button(
                    "ð¥ Excelãã¦ã³ã­ã¼ã",
                    buffer.getvalue(),
                    file_name=f"minpaku_properties_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                )

            st.subheader("ãã¬ãã¥ã¼")
            st.dataframe(export_df, use_container_width=True, height=400)
    else:
        st.info("ã¾ããç©ä»¶æ¤ç´¢ãã¿ãã§æ¤ç´¢ãå®è¡ãã¦ãã ããã")


# ========================================
# Footer
# ========================================
st.divider()
st.caption(
    "â ï¸ ãã®ãã¼ã«ã¯åäººå©ç¨ã»å­¦ç¿ç®çã«éå®ããã¾ãã"
    "åç¨åãå¤§è¦æ¨¡å©ç¨ãè¡ãå ´åã¯ãåãµã¤ãã®å¬å¼APIã¸ã®ç§»è¡ãæ¤è¨ãã¦ãã ããã"
    f" | æçµæ´æ°: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
)
