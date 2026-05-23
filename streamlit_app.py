import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import os
import warnings

warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="Zalopay NPU Campaign Dashboard",
    page_icon="📊",
    layout="wide"
)

# Color Palette (BI Style)
colors = {
    'primary': "#2C3E50",     
    'secondary': "#18BC9C",   
    'dark': "#2C3E50",
    'muted': "#95A5A6",
    'success': "#18BC9C",
    'warning': "#F39C12",
    'danger': "#E74C3C",
    'light_bg': "#ECF0F1",
    'card_bg': "#FFFFFF"
}

# Plotly Template setup
pio.templates["zalopay_flatly"] = go.layout.Template(
    layout=go.Layout(
        plot_bgcolor='white', paper_bgcolor='white',
        font=dict(family="Lato, sans-serif", color=colors['dark']),
        xaxis=dict(showgrid=True, gridcolor='#ECF0F1', gridwidth=1, zeroline=False, automargin=True),
        yaxis=dict(showgrid=True, gridcolor='#ECF0F1', gridwidth=1, zeroline=False, automargin=True),
        title=dict(font=dict(size=14, color=colors['dark'], family="Lato, sans-serif", weight="bold"), x=0.01),
        hoverlabel=dict(bgcolor='white', font_size=12),
        colorway=[
            "#3498DB", "#2ECC71", "#E74C3C", "#F1C40F", "#9B59B6", 
            "#1ABC9C", "#34495E", "#E67E22", "#E84393", "#00CEC9"
        ],
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5),
        margin=dict(l=60, r=40, t=60, b=60)
    )
)
pio.templates.default = "zalopay_flatly"

# Helper functions
def to_scalar_number(value):
    if value is None: return 0
    try:
        if pd.isna(value): return 0
    except Exception: pass
    try: return float(value)
    except Exception: return 0

def format_vnd(value):
    value = to_scalar_number(value)
    if value >= 1e9: return f"{value / 1e9:.1f}B"
    elif value >= 1e6: return f"{value / 1e6:.1f}M"
    elif value >= 1e3: return f"{value / 1e3:.1f}K"
    else: return f"{value:.0f}"

def format_number(value):
    value = to_scalar_number(value)
    return f"{value:,.0f}"

def format_pct(value):
    value = to_scalar_number(value)
    return f"{value * 100:.1f}%"

def safe_divide(a, b):
    a = to_scalar_number(a)
    b = to_scalar_number(b)
    return a / b if b != 0 else 0

cat_short_map = {
    "Access_Service": "Access",
    "Obligation_Payment": "Obligation",
    "Goods_Transaction": "Goods",
    "Interactive_Service": "Interactive",
    "Daily_Consumption": "Daily",
    "Unknown_Group": "Unknown"
}

def shorten_cat(cat):
    return cat_short_map.get(str(cat), str(cat))

@st.cache_data
def load_data():
    data = {}
    files = {
        "npu_acquisition": "outputs/npu_acquisition.csv",
        "user_post_behavior": "outputs/user_post_behavior.csv",
        "df_success": "outputs/df_success.csv"
    }
    
    for key, path in files.items():
        zip_path = path.replace('.csv', '.zip')
        
        if os.path.exists(path):
            data[key] = pd.read_csv(path, low_memory=False)
        elif os.path.exists(zip_path):
            data[key] = pd.read_csv(zip_path, low_memory=False)
        elif os.path.exists(os.path.basename(path)):
            data[key] = pd.read_csv(os.path.basename(path), low_memory=False)
        else:
            data[key] = None
            if key != "df_success":
                st.warning(f"File not found: {path}")
            
    if data["npu_acquisition"] is not None and 'first_success_date' in data["npu_acquisition"].columns:
        data["npu_acquisition"]['first_success_date'] = pd.to_datetime(data["npu_acquisition"]['first_success_date'], errors='coerce')
        
    if data["df_success"] is not None and 'reqDate' in data["df_success"].columns:
        data["df_success"]['reqDate'] = pd.to_datetime(data["df_success"]['reqDate'], errors='coerce')
        
    return data

def make_metric_card(title, value, border_color="#18BC9C", bg_color="#FFFFFF", text_color="#2C3E50"):
    st.markdown(f"""
    <div style="border-left: 5px solid {border_color}; border-top: 1px solid #E2E8F0; border-right: 1px solid #E2E8F0; border-bottom: 1px solid #E2E8F0; border-radius: 8px; padding: 15px; background-color: {bg_color}; box-shadow: 0 4px 6px rgba(0,0,0,0.05); height: 100%;">
        <div style="text-transform: uppercase; font-size: 11px; font-weight: 700; color: #7F8C8D; margin-bottom: 5px;">{title}</div>
        <div style="color: {text_color}; font-weight: 800; font-size: 26px; margin: 0;">{value}</div>
    </div>
    """, unsafe_allow_html=True)

def make_insight(bullets):
    st.markdown(f"""
    <div style="border: 1px solid #FAD7A1; border-radius: 8px; padding: 15px; background-color: #FDF2E9;">
        <h6 style="font-weight: 700; color: #D35400; font-size: 13px; margin-top: 0;">💡 Business Insight</h6>
        <ul style="margin-bottom: 0; padding-left: 20px; font-size: 13px; color: #2C3E50;">
            {"".join([f"<li style='margin-bottom: 6px;'>{b}</li>" for b in bullets])}
        </ul>
    </div>
    """, unsafe_allow_html=True)

data = load_data()
df_npu_raw = data["npu_acquisition"]
df_post_raw = data["user_post_behavior"]
df_success = data["df_success"]

if df_npu_raw is None or df_npu_raw.empty:
    st.error("❌ DỮ LIỆU ĐẦU VÀO! Không thể load `npu_acquisition.csv`.")
    st.stop()
if df_post_raw is None or df_post_raw.empty:
    st.error("❌ DỮ LIỆU ĐẦU VÀO! Không thể load `user_post_behavior.csv`.")
    st.stop()

# Prepare User Master Dataset
user_master = pd.merge(
    df_npu_raw, 
    df_post_raw.drop(columns=['first_success_date'], errors='ignore'), 
    on=['userID', 'acquisition_campaignID'], 
    how='left'
)

post_metrics = ['repeat_flag', 'post_tx_count', 'post_gmv', 'post_discount', 'post_non_promo_tx_count', 'post_campaign_tx_count', 'post_category_count', 'post_merchant_count', 'd7_repeat_flag', 'd30_repeat_flag', 'd60_repeat_flag']
for col in post_metrics:
    if col in user_master.columns:
        user_master[col] = user_master[col].fillna(0)

user_master['first_success_month'] = user_master['first_success_date'].dt.to_period('M').astype(str)


merchant_candidates = ['first_report_sub_cat', 'report_sub_cat', 'first_appID', 'appID', 'first_merchant', 'merchant_name']
merchant_col = None
for col in merchant_candidates:
    if col in user_master.columns:
        merchant_col = col
        break

# Sidebar Filters
st.sidebar.markdown(f'<h4 style="font-weight: 800; font-size: 16px; letter-spacing: 1px; color: {colors["primary"]}; margin-bottom: 20px;">FILTERS</h4>', unsafe_allow_html=True)

df_filt = user_master.copy()

min_date = df_filt['first_success_date'].min().date() if not pd.isna(df_filt['first_success_date'].min()) else None
max_date = df_filt['first_success_date'].max().date() if not pd.isna(df_filt['first_success_date'].max()) else None

st.sidebar.markdown('**Date Range (First Success)**')
if min_date and max_date:
    date_range = st.sidebar.date_input("Date Range", [min_date, max_date], label_visibility="collapsed")
    if len(date_range) == 2:
        df_filt = df_filt[(df_filt['first_success_date'].dt.date >= date_range[0]) & (df_filt['first_success_date'].dt.date <= date_range[1])]

st.sidebar.markdown('**Min NPU Threshold**')
min_npu = st.sidebar.slider("Min NPU Threshold", 0, 500, 30, 10, label_visibility="collapsed")

def filter_dropdown(df, col_name, display_name):
    if col_name in df.columns:
        st.sidebar.markdown(f'**{display_name}**')
        options = sorted([str(x) for x in df[col_name].dropna().unique()])
        selected = st.sidebar.multiselect(f"Select {display_name}", options, placeholder=f"All {display_name}s", label_visibility="collapsed")
        if selected:
            return df[df[col_name].astype(str).isin(selected)]
    return df

df_filt = filter_dropdown(df_filt, 'first_report_cat', 'Report Category')
if merchant_col:
    df_filt = filter_dropdown(df_filt, merchant_col, 'Merchant / Sub-category')
df_filt = filter_dropdown(df_filt, 'first_promotion_type_clean', 'Promotion Type')
df_filt = filter_dropdown(df_filt, 'gender', 'Gender')
df_filt = filter_dropdown(df_filt, 'first_platform', 'Platform')
df_filt = filter_dropdown(df_filt, 'acquisition_campaignID', 'Campaign ID')

st.sidebar.markdown("---")
with st.sidebar.expander("📝 Methodology Note"):
    st.markdown("""
    - NPU = first successful promo payment.
    - Camp=0 is not acquisition.
    - Subsidy Rate = Discount / GMV.
    - Dashboard is for monitoring, not causal scoring.
    - D30/D60 retention are cumulative repeat indicators.
    """)

# Main Header
st.markdown(f"""
    <h2 style="font-weight: 800; color: {colors['dark']}; margin-bottom: 5px;">🚀 Zalopay NPU Campaign Performance</h2>
    <p style="color: {colors['muted']}; font-size: 15px; margin-bottom: 25px; padding-bottom: 15px; border-bottom: 1px solid #E2E8F0;">Dynamic Segment Analytics & Campaign Comparison</p>
""", unsafe_allow_html=True)

if df_filt.empty:
    st.error("No data matches the selected filters.")
    st.stop()

# Aggregate Data for Campaigns
df_camp = df_filt.groupby('acquisition_campaignID').agg(
    NPU_Count=('userID', 'nunique'),
    First_GMV=('first_amount', 'sum'),
    Total_First_Discount=('first_discountAmount', 'sum'),
    Post_GMV_Sum=('post_gmv', 'sum') if 'post_gmv' in df_filt.columns else ('acquisition_campaignID', 'sum'),
    Post_Discount_Sum=('post_discount', 'sum') if 'post_discount' in df_filt.columns else ('acquisition_campaignID', 'sum'),
    Post_Tx_Sum=('post_tx_count', 'sum') if 'post_tx_count' in df_filt.columns else ('acquisition_campaignID', 'sum'),
    Repeat_User_Count=('repeat_flag', 'sum') if 'repeat_flag' in df_filt.columns else ('acquisition_campaignID', 'sum'),
    D7_Repeat_Count=('d7_repeat_flag', 'sum') if 'd7_repeat_flag' in df_filt.columns else ('acquisition_campaignID', 'sum'),
    D30_Repeat_Count=('d30_repeat_flag', 'sum') if 'd30_repeat_flag' in df_filt.columns else ('acquisition_campaignID', 'sum'),
    D60_Repeat_Count=('d60_repeat_flag', 'sum') if 'd60_repeat_flag' in df_filt.columns else ('acquisition_campaignID', 'sum'),
    Non_Promo_Tx_Sum=('post_non_promo_tx_count', 'sum') if 'post_non_promo_tx_count' in df_filt.columns else ('acquisition_campaignID', 'sum')
).reset_index()

df_camp['Avg_First_Amount'] = df_camp.apply(lambda x: safe_divide(x['First_GMV'], x['NPU_Count']), axis=1)
df_camp['Avg_First_Discount'] = df_camp.apply(lambda x: safe_divide(x['Total_First_Discount'], x['NPU_Count']), axis=1)
df_camp['First_Subsidy_Rate'] = df_camp.apply(lambda x: safe_divide(x['Total_First_Discount'], x['First_GMV']), axis=1)
df_camp['Avg_Post_GMV'] = df_camp.apply(lambda x: safe_divide(x['Post_GMV_Sum'], x['NPU_Count']), axis=1)
df_camp['Avg_Post_Discount'] = df_camp.apply(lambda x: safe_divide(x['Post_Discount_Sum'], x['NPU_Count']), axis=1)
df_camp['Avg_Post_Tx'] = df_camp.apply(lambda x: safe_divide(x['Post_Tx_Sum'], x['NPU_Count']), axis=1)
df_camp['Repeat_Rate'] = df_camp.apply(lambda x: safe_divide(x['Repeat_User_Count'], x['NPU_Count']), axis=1)
df_camp['D7_Retention'] = df_camp.apply(lambda x: safe_divide(x['D7_Repeat_Count'], x['NPU_Count']), axis=1)
df_camp['D30_Retention'] = df_camp.apply(lambda x: safe_divide(x['D30_Repeat_Count'], x['NPU_Count']), axis=1)
df_camp['D60_Retention'] = df_camp.apply(lambda x: safe_divide(x['D60_Repeat_Count'], x['NPU_Count']), axis=1)
df_camp['Post_Non_Promo_Tx_Share'] = df_camp.apply(lambda x: safe_divide(x['Non_Promo_Tx_Sum'], x['Post_Tx_Sum']), axis=1)

df_camp["Campaign_Label"] = "Camp " + df_camp["acquisition_campaignID"].astype(str)

if 'first_report_cat' in df_filt.columns:
    dom_cat = df_filt.groupby('acquisition_campaignID')['first_report_cat'].agg(lambda x: x.mode()[0] if not x.empty else 'Unknown').reset_index(name='Dominant_Category')
    df_camp = pd.merge(df_camp, dom_cat, on='acquisition_campaignID', how='left')

if 'first_promotion_type_clean' in df_filt.columns:
    dom_promo = df_filt.groupby('acquisition_campaignID')['first_promotion_type_clean'].agg(lambda x: x.mode()[0] if not x.empty else 'Unknown').reset_index(name='Dominant_Promo')
    df_camp = pd.merge(df_camp, dom_promo, on='acquisition_campaignID', how='left')

if 'first_amount' in df_filt.columns:
    median_df = df_filt.groupby('acquisition_campaignID')['first_amount'].median().reset_index(name='Median_First_Amount')
    df_camp = pd.merge(df_camp, median_df, on='acquisition_campaignID', how='left')

df_camp = df_camp[df_camp['NPU_Count'] >= min_npu].copy()


tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Executive Overview", 
    "📈 Campaign Comparison", 
    "⭐ Post-Acquisition Quality", 
    "🧩 Use Case & Expansion"
])

with tab1:
    st.info("💡 This page provides a macro view of NPU acquisition volume and value over time. All metrics are dynamically calculated based on your sidebar filters.")
    
    tot_npu = df_filt['userID'].nunique()
    tot_campaigns = df_filt['acquisition_campaignID'].nunique() if 'acquisition_campaignID' in df_filt.columns else 0
    tot_gmv = df_filt['first_amount'].fillna(0).sum() if 'first_amount' in df_filt.columns else 0
    tot_disc = df_filt['first_discountAmount'].fillna(0).sum() if 'first_discountAmount' in df_filt.columns else 0
    segment_subsidy_rate = safe_divide(tot_disc, tot_gmv)
    avg_first_amount = safe_divide(tot_gmv, tot_npu)
    
    col1, col2, col3, col4, col5 = st.columns([3, 2, 3, 2, 2])
    with col1: make_metric_card("👤 Segment NPU Volume", format_number(tot_npu), border_color="#3498DB", bg_color="#EBF5FB", text_color="#2980B9")
    with col2: make_metric_card("📢 Segment Campaigns", format_number(tot_campaigns), border_color="#9B59B6", bg_color="#F4ECF7", text_color="#8E44AD")
    with col3: make_metric_card("💰 Segment First GMV", format_vnd(tot_gmv), border_color="#2ECC71", bg_color="#EAFAF1", text_color="#27AE60")
    with col4: make_metric_card("🔥 Segment Subsidy Rate", format_pct(segment_subsidy_rate), border_color="#E74C3C", bg_color="#FDEDEC", text_color="#C0392B")
    with col5: make_metric_card("💳 Avg First Amount/NPU", format_vnd(avg_first_amount), border_color="#F39C12", bg_color="#FEF9E7", text_color="#D35400")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    r1c1, r1c2 = st.columns(2)
    with r1c1:
        with st.container(border=True):
            st.markdown("###### 📊 NPU Acquisition Volume Trend")
            if 'first_success_month' in df_filt.columns:
                monthly = df_filt.groupby('first_success_month').agg(NPU_Count=('userID', 'nunique')).reset_index()
                fig_trend = px.area(monthly, x='first_success_month', y='NPU_Count', markers=True, color_discrete_sequence=["#3498DB"])
                fig_trend.update_layout(xaxis_title=None, yaxis_title="NPU Count", height=400, margin=dict(l=60, r=20, t=20, b=40))
                st.plotly_chart(fig_trend, use_container_width=True)
                st.caption("Tracks monthly NPU acquisition volume and helps detect spikes or drops over time.")
                
    with r1c2:
        with st.container(border=True):
            st.markdown("###### 📉 First GMV vs First Discount")
            if 'first_success_month' in df_filt.columns and 'first_amount' in df_filt.columns and 'first_discountAmount' in df_filt.columns:
                monthly_fin = df_filt.groupby('first_success_month').agg(GMV=('first_amount', 'sum'), Disc=('first_discountAmount', 'sum')).reset_index()
                fig_gmv_disc = go.Figure()
                fig_gmv_disc.add_trace(go.Bar(x=monthly_fin['first_success_month'], y=monthly_fin['GMV'], name='First GMV', marker_color="#2ECC71"))
                fig_gmv_disc.add_trace(go.Scatter(x=monthly_fin['first_success_month'], y=monthly_fin['Disc'], name='First Discount', marker_color="#E74C3C", yaxis='y2', mode='lines+markers'))
                fig_gmv_disc.update_layout(height=400, margin=dict(l=60, r=60, t=20, b=40), yaxis=dict(tickformat=".2s"), yaxis2=dict(overlaying='y', side='right', showgrid=False, tickformat=".2s"), barmode='group')
                st.plotly_chart(fig_gmv_disc, use_container_width=True)
                st.caption("Compares first transaction value with campaign subsidy to monitor subsidy efficiency.")
                
    r2c1, r2c2 = st.columns([5, 7])
    with r2c1:
        with st.container(border=True):
            st.markdown("###### 🏆 Top 5 Use Cases by NPU Volume")
            if 'first_report_cat' in df_filt.columns:
                uc_df = df_filt.groupby('first_report_cat')['userID'].nunique().reset_index(name='NPU')
                uc_df['first_report_cat'] = uc_df['first_report_cat'].apply(shorten_cat)
                uc_df = uc_df.sort_values('NPU', ascending=False)
                top_uc = uc_df.head(5)
                others_npu = uc_df.iloc[5:]['NPU'].sum()
                if others_npu > 0:
                    top_uc = pd.concat([top_uc, pd.DataFrame({'first_report_cat': ['Others'], 'NPU': [others_npu]})])
                fig_uc = px.bar(top_uc.sort_values('NPU', ascending=True), x='NPU', y='first_report_cat', orientation='h', color_discrete_sequence=["#9B59B6"])
                fig_uc.update_layout(xaxis_title="NPU Count", yaxis_title=None, height=350, margin=dict(l=10, r=10, t=10, b=40))
                st.plotly_chart(fig_uc, use_container_width=True)
                st.caption("Shows which first-use cases contribute the largest share of acquired NPUs.")
                
                top1_uc = top_uc.iloc[0]['first_report_cat'] if not top_uc.empty else "N/A"
                top2_uc = top_uc.iloc[1]['first_report_cat'] if len(top_uc) > 1 else "N/A"
    
    with r2c2:
        with st.container(border=True):
            st.markdown("###### 🏪 Top 10 Merchant/Sub-categories by NPU")
            if merchant_col:
                merch_df = df_filt.groupby(merchant_col)['userID'].nunique().reset_index(name='NPU')
                merch_df = merch_df.sort_values('NPU', ascending=False).head(10)
                fig_merch = px.bar(merch_df.sort_values('NPU', ascending=True), x='NPU', y=merchant_col, orientation='h', color_discrete_sequence=["#1ABC9C"])
                fig_merch.update_layout(xaxis_title="NPU Count", yaxis_title=None, height=350, margin=dict(l=10, r=10, t=10, b=40))
                st.plotly_chart(fig_merch, use_container_width=True)
                st.caption("This chart identifies which merchants or sub-categories contribute the most to NPU acquisition volume.")
            else:
                st.info("Merchant/Sub-category data is not available in current output files.")
        
        st.markdown("<br>", unsafe_allow_html=True)
        try:
            make_insight([
                f"[What happened?] {top1_uc} and {top2_uc} are the dominant first-use cases, contributing the majority of acquired NPUs.",
                f"[So what?] Total First GMV reaches {format_vnd(tot_gmv)} with an overall first subsidy rate of {format_pct(segment_subsidy_rate)}.",
                "[Next step?] Check the trends to see if volume correlates strongly with discount. Investigate budget allocation for declining periods."
            ])
        except Exception:
            pass

with tab2:
    st.info("💡 This page compares campaigns by acquisition scale, transaction value, and subsidy intensity. Scatter plot uses log scale to handle high-volume outliers.")
    if df_camp.empty:
        st.warning("No campaigns meet the NPU threshold within this filtered segment.")
    else:
        with st.container(border=True):
            st.markdown("###### 🌌 Volume vs Value Portfolio (log scale)")
            fig_scatter = px.scatter(df_camp, x="NPU_Count", y="Avg_First_Amount", size="First_GMV", 
                                     color="First_Subsidy_Rate", hover_name="Campaign_Label",
                                     color_continuous_scale="Viridis", size_max=40)
            fig_scatter.update_layout(xaxis_title="NPU Count (log scale)", yaxis_title="Average First Transaction Amount", coloraxis_colorbar_title="Subsidy Rate", height=500, margin=dict(l=60, r=40, t=20, b=60))
            fig_scatter.update_xaxes(type="log")
            st.plotly_chart(fig_scatter, use_container_width=True)
            st.caption("Compares campaigns by acquisition volume, first transaction value, and subsidy intensity.")
            
        r3c1, r3c2, r3c3 = st.columns(3)
        with r3c1:
            with st.container(border=True):
                st.markdown("###### 🥇 Top 10 Campaigns by NPU")
                fig_bar_npu = px.bar(df_camp.nlargest(10, 'NPU_Count').sort_values('NPU_Count'), x='NPU_Count', y='Campaign_Label', orientation='h', color_discrete_sequence=["#3498DB"])
                fig_bar_npu.update_layout(yaxis_title=None, xaxis_title="NPU Count", height=400, margin=dict(l=10, r=10, t=10, b=40))
                st.plotly_chart(fig_bar_npu, use_container_width=True)
                st.caption("Identifies the largest acquisition drivers.")
        with r3c2:
            with st.container(border=True):
                st.markdown("###### 💰 Top 10 Campaigns by First GMV")
                fig_bar_gmv = px.bar(df_camp.nlargest(10, 'First_GMV').sort_values('First_GMV'), x='First_GMV', y='Campaign_Label', orientation='h', color_discrete_sequence=["#2ECC71"])
                fig_bar_gmv.update_layout(yaxis_title=None, xaxis_title="First GMV", height=400, margin=dict(l=10, r=10, t=10, b=40))
                st.plotly_chart(fig_bar_gmv, use_container_width=True)
                st.caption("Identifies campaigns generating the highest first transaction value.")
        with r3c3:
            with st.container(border=True):
                st.markdown("###### 🔥 Top 10 by Subsidy Rate")
                fig_bar_sub = px.bar(df_camp.nlargest(10, 'First_Subsidy_Rate').sort_values('First_Subsidy_Rate'), x='First_Subsidy_Rate', y='Campaign_Label', orientation='h', color_discrete_sequence=["#E74C3C"])
                fig_bar_sub.update_layout(yaxis_title=None, xaxis_title="Subsidy Rate", xaxis=dict(tickformat=".0%"), height=400, margin=dict(l=10, r=10, t=10, b=40))
                st.plotly_chart(fig_bar_sub, use_container_width=True)
                st.caption("Highlights campaigns with high subsidy intensity after applying the NPU threshold.")
                
        st.markdown("###### 📋 Campaign Acquisition Ranking Table")
        df_table = df_camp.sort_values('NPU_Count', ascending=False).head(50)
        display_cols = ['Campaign_Label', 'NPU_Count', 'First_GMV', 'Avg_First_Amount', 'Total_First_Discount', 'First_Subsidy_Rate']
        if 'Dominant_Category' in df_table.columns: display_cols.append('Dominant_Category')
        if 'Dominant_Promo' in df_table.columns: display_cols.append('Dominant_Promo')
        
        show_df = df_table[display_cols].copy()
        show_df['First_GMV'] = show_df['First_GMV'].apply(lambda x: f"{x:,.0f}")
        show_df['Avg_First_Amount'] = show_df['Avg_First_Amount'].apply(lambda x: f"{x:,.0f}")
        show_df['Total_First_Discount'] = show_df['Total_First_Discount'].apply(lambda x: f"{x:,.0f}")
        show_df['First_Subsidy_Rate'] = show_df['First_Subsidy_Rate'].apply(format_pct)
        st.dataframe(show_df, use_container_width=True, hide_index=True)
        
        top_npu_camp = df_camp.loc[df_camp['NPU_Count'].idxmax()]['Campaign_Label'] if not df_camp.empty else "N/A"
        make_insight([
            f"[What happened?] {top_npu_camp} dominates acquisition volume, while other campaigns show stronger value signals.",
            "[So what?] High-volume campaigns often pull the overall average value down. We must balance volume drivers and value drivers in the portfolio.",
            "[Next step?] Identify campaigns in the top right of the scatter plot (high volume and high value) and scale them."
        ])

with tab3:
    st.info("💡 This page shifts focus to post-first behavior. Retention metrics represent 'User has at least 1 repeat transaction within X days' (cumulative).")
    df_ret = df_camp[df_camp['NPU_Count'] >= max(min_npu, 100)].copy()
    if df_ret.empty:
        st.warning("Not enough NPU per campaign to calculate reliable retention metrics (Increase min_npu filter).")
    else:
        tot_npu_ret = df_ret['NPU_Count'].sum()
        w_rep = (df_ret['Repeat_Rate'] * df_ret['NPU_Count']).sum() / tot_npu_ret
        w_d30 = (df_ret['D30_Retention'] * df_ret['NPU_Count']).sum() / tot_npu_ret
        w_d60 = (df_ret['D60_Retention'] * df_ret['NPU_Count']).sum() / tot_npu_ret
        w_post_gmv = (df_ret['Avg_Post_GMV'] * df_ret['NPU_Count']).sum() / tot_npu_ret
        
        c1, c2, c3, c4 = st.columns(4)
        with c1: make_metric_card("🔄 Overall Repeat Rate", format_pct(w_rep), border_color="#9B59B6", bg_color="#F4ECF7", text_color="#8E44AD")
        with c2: make_metric_card("📅 Repeat within 30 Days", format_pct(w_d30), border_color="#3498DB", bg_color="#EBF5FB", text_color="#2980B9")
        with c3: make_metric_card("📆 Repeat within 60 Days", format_pct(w_d60), border_color="#1ABC9C", bg_color="#E8F8F5", text_color="#16A085")
        with c4: make_metric_card("🛍️ Weighted Avg Post GMV", format_vnd(w_post_gmv), border_color="#2ECC71", bg_color="#EAFAF1", text_color="#27AE60")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        r4c1, r4c2 = st.columns([8, 4])
        with r4c1:
            with st.container(border=True):
                st.markdown("###### 🎯 Volume vs D30 Repeat (Size=Post GMV, Color=Non-Promo Share)")
                fig_ret = px.scatter(df_ret, x="NPU_Count", y="D30_Retention", size="Avg_Post_GMV", color="Post_Non_Promo_Tx_Share", hover_name="Campaign_Label", color_continuous_scale="Plasma", size_max=40)
                fig_ret.update_layout(height=450, margin=dict(l=60, r=40, t=20, b=40), xaxis_title="NPU Count", yaxis_title="Repeat within 30 Days", yaxis=dict(tickformat=".0%"))
                st.plotly_chart(fig_ret, use_container_width=True)
                st.caption("Evaluates whether high-volume campaigns also generate repeat behavior within 30 days.")
        with r4c2:
            with st.container(border=True):
                st.markdown("###### 🏆 Top 10 by D30 Repeat")
                fig_d30_bar = px.bar(df_ret.nlargest(10, 'D30_Retention').sort_values('D30_Retention'), x='D30_Retention', y='Campaign_Label', orientation='h', color_discrete_sequence=["#F1C40F"])
                fig_d30_bar.update_layout(height=450, margin=dict(l=10, r=10, t=10, b=40), xaxis_title="Repeat within 30 Days", yaxis_title=None, xaxis=dict(tickformat=".0%"))
                st.plotly_chart(fig_d30_bar, use_container_width=True)
                st.caption("Ranks campaigns by post-acquisition repeat quality.")
                
        st.markdown("###### 📈 Quality Signals Table")
        ret_cols = ['Campaign_Label', 'NPU_Count', 'D7_Retention', 'D30_Retention', 'D60_Retention', 'Avg_Post_Tx', 'Avg_Post_GMV', 'Post_Non_Promo_Tx_Share']
        show_ret = df_ret.sort_values('D30_Retention', ascending=False).head(50)[ret_cols].copy()
        show_ret['D7_Retention'] = show_ret['D7_Retention'].apply(format_pct)
        show_ret['D30_Retention'] = show_ret['D30_Retention'].apply(format_pct)
        show_ret['D60_Retention'] = show_ret['D60_Retention'].apply(format_pct)
        show_ret['Avg_Post_Tx'] = show_ret['Avg_Post_Tx'].apply(lambda x: f"{x:.2f}")
        show_ret['Avg_Post_GMV'] = show_ret['Avg_Post_GMV'].apply(lambda x: f"{x:,.0f}")
        show_ret['Post_Non_Promo_Tx_Share'] = show_ret['Post_Non_Promo_Tx_Share'].apply(format_pct)
        st.dataframe(show_ret, use_container_width=True, hide_index=True)
        
        make_insight([
            "[What happened?] There is a significant gap between short-term acquisition and long-term retention.",
            "[So what?] Retention and Non-Promo Share (dark blue dots) indicate true user stickiness rather than just subsidy hunting.",
            "[Next step?] Highlight campaigns with high 'Repeat within 30 Days' and high Non-Promo share as top quality candidates."
        ])

with tab4:
    st.info("💡 This page analyzes Use Case behavior and Category Expansion. The Heatmap answers: 'If a user is acquired via category A, do they expand to category B?'")
    if 'first_report_cat' in df_filt.columns:
        uc_summary = df_filt.groupby('first_report_cat').agg(NPU_Count=('userID', 'nunique'), GMV=('first_amount', 'sum')).reset_index()
        uc_summary['Avg_Amount'] = uc_summary.apply(lambda x: safe_divide(x['GMV'], x['NPU_Count']), axis=1)
        uc_summary['first_report_cat_short'] = uc_summary['first_report_cat'].apply(shorten_cat)
        
        r5c1, r5c2 = st.columns(2)
        with r5c1:
            with st.container(border=True):
                st.markdown("###### 💠 First Use Case: Volume vs Value Matrix")
                fig_uc_scatter = px.scatter(uc_summary, x="NPU_Count", y="Avg_Amount", size="GMV", hover_name="first_report_cat", color="first_report_cat_short", size_max=50, color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_uc_scatter.update_layout(height=600, legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5), xaxis_title="NPU Count", yaxis_title="Avg First Amount", margin=dict(l=60, r=40, t=20, b=100))
                st.plotly_chart(fig_uc_scatter, use_container_width=True)
                st.caption("Compares first-use cases by NPU scale, average first transaction amount, and GMV.")
                
        with r5c2:
            with st.container(border=True):
                st.markdown("###### 🌡️ Behavioral Expansion Heatmap (First Cat -> Post Cat)")
                if df_success is not None and not df_success.empty and 'report_cat' in df_success.columns:
                    npu_users = df_filt[['userID', 'first_success_date', 'first_report_cat']].copy()
                    df_post_tx = pd.merge(df_success[['userID', 'reqDate', 'report_cat']], npu_users, on='userID', how='inner')
                    df_post_tx = df_post_tx[df_post_tx['reqDate'].dt.date > df_post_tx['first_success_date'].dt.date]
                    
                    if not df_post_tx.empty:
                        category_transition = df_post_tx.groupby(['first_report_cat', 'report_cat'])['userID'].nunique().reset_index()
                        category_transition.rename(columns={'report_cat': 'post_report_cat', 'userID': 'user_count'}, inplace=True)
                        top_cats = npu_users['first_report_cat'].value_counts().head(15).index
                        category_transition = category_transition[category_transition['first_report_cat'].isin(top_cats) & category_transition['post_report_cat'].isin(top_cats)]
                        
                        cat_trans = category_transition.copy()
                        cat_trans['first_report_cat'] = cat_trans['first_report_cat'].apply(shorten_cat)
                        cat_trans['post_report_cat'] = cat_trans['post_report_cat'].apply(shorten_cat)
                        pivot_trans = cat_trans.pivot(index='first_report_cat', columns='post_report_cat', values='user_count').fillna(0)
                        
                        fig_transition = go.Figure(data=go.Heatmap(z=pivot_trans.values, x=pivot_trans.columns, y=pivot_trans.index, colorscale='Magma'))
                        fig_transition.update_layout(height=600, xaxis_title="Subsequent Post Category", yaxis_title="First Acquired Category", margin=dict(l=100, r=40, t=20, b=100), xaxis=dict(tickangle=-45, automargin=True), yaxis=dict(automargin=True))
                        st.plotly_chart(fig_transition, use_container_width=True)
                        st.caption("Shows whether users acquired from one category expand to other categories after acquisition.")
                    else:
                        st.info("No transition data found.")
                else:
                    st.info("No df_success data available for heatmap.")
        
        make_insight([
            "[What happened?] The Heatmap reveals how users cross-sell into other categories post-acquisition.",
            "[So what?] A bright diagonal means users stick to their first category. Bright spots off-diagonal show strong cross-category expansion.",
            "[Next step?] If users from 'Telco' often transition to 'Food', design campaigns that explicitly bundle Telco with Food vouchers."
        ])
        
        st.markdown("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("###### 🏪 Merchant/Sub-category Volume vs Value")
            if merchant_col:
                if 'first_amount' in df_filt.columns and 'first_discountAmount' in df_filt.columns:
                    merch_scatter = df_filt.groupby(merchant_col).agg(
                        NPU_Count=('userID', 'nunique'),
                        First_GMV=('first_amount', 'sum'),
                        First_Discount=('first_discountAmount', 'sum')
                    ).reset_index()
                    merch_scatter['Avg_First_Amount'] = merch_scatter.apply(lambda x: safe_divide(x['First_GMV'], x['NPU_Count']), axis=1)
                    merch_scatter['First_Subsidy_Rate'] = merch_scatter.apply(lambda x: safe_divide(x['First_Discount'], x['First_GMV']), axis=1)
                    
                    fig_merch_scat = px.scatter(
                        merch_scatter, x="NPU_Count", y="Avg_First_Amount", size="First_GMV", 
                        color="First_Subsidy_Rate", hover_name=merchant_col,
                        color_continuous_scale="Viridis", size_max=50
                    )
                    fig_merch_scat.update_layout(
                        xaxis_title="NPU Count", 
                        yaxis_title="Average First Transaction Amount", 
                        coloraxis_colorbar_title="First Subsidy Rate", 
                        height=500, margin=dict(l=60, r=40, t=20, b=60)
                    )
                    st.plotly_chart(fig_merch_scat, use_container_width=True)
                    st.caption("This chart compares merchant/sub-category segments by acquisition scale, transaction value, and subsidy intensity.")
                else:
                    st.warning("First amount or discount data missing for this chart.")
            else:
                st.info("Merchant/Sub-category data is not available in current output files.")

    else:
        st.warning("Category data not available.")
