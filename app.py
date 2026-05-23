import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import dash
import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html
from dash.dependencies import Input, Output
import os
import warnings
warnings.filterwarnings('ignore')

# Constants
MIN_NPU_FOR_AVG = 30
MIN_NPU_FOR_RETENTION = 100
TOP_N = 10

# Formatting functions
from numbers import Number

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

# Plotly Template
import plotly.io as pio
pio.templates["zalopay_flatly"] = go.layout.Template(
    layout=go.Layout(
        plot_bgcolor='white', paper_bgcolor='white',
        font=dict(family="Lato, sans-serif", color=colors['dark']),
        xaxis=dict(showgrid=True, gridcolor='#ECF0F1', gridwidth=1, zeroline=False, automargin=True),
        yaxis=dict(showgrid=True, gridcolor='#ECF0F1', gridwidth=1, zeroline=False, automargin=True),
        title=dict(font=dict(size=14, color=colors['dark'], family="Lato, sans-serif"), x=0.01),
        hoverlabel=dict(bgcolor='white', font_size=12),
        colorway=[colors['primary'], colors['secondary'], colors['warning'], colors['danger'], colors['muted']],
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5),
        margin=dict(l=60, r=40, t=60, b=60)
    )
)
pio.templates.default = "zalopay_flatly"

# Helper to shorten category names
cat_short_map = {
    "Access_Service": "Access",
    "Obligation_Payment": "Obligation",
    "Goods_Transaction": "Goods",
    "Interactive_Service": "Interactive",
    "Daily_Consumption": "Daily",
    "Unknown_Group": "Unknown"
}

def shorten_cat(cat):
    return cat_short_map.get(cat, str(cat))

print("✅ Setup completed.")


required_files = {
    'df_success': 'outputs/df_success.csv',
    'npu_acquisition': 'outputs/npu_acquisition.csv',
    'user_post_behavior': 'outputs/user_post_behavior.csv'
}

dataframes = {}
missing_files = []

for name, path in required_files.items():
    if os.path.exists(path):
        try:
            dataframes[name] = pd.read_csv(path, low_memory=False)
        except Exception as e:
            print(f"Error reading {path}: {e}")
            missing_files.append(path)
    else:
        missing_files.append(path)

if missing_files:
    print("❌ THIẾU DỮ LIỆU ĐẦU VÀO! Không thể load:")
    for f in missing_files: print(f"  - {f}")
else:
    print("✅ Đã load đủ dữ liệu.")
    df_success = dataframes['df_success']
    npu_acquisition = dataframes['npu_acquisition']
    user_post_behavior = dataframes['user_post_behavior']
    
    if 'reqDate' in df_success.columns: df_success['reqDate'] = pd.to_datetime(df_success['reqDate'], errors='coerce')
    if 'first_success_date' in npu_acquisition.columns: npu_acquisition['first_success_date'] = pd.to_datetime(npu_acquisition['first_success_date'], errors='coerce')
    print("✅ Converted datetime columns.")


if not missing_files:
    user_master = pd.merge(
        npu_acquisition, 
        user_post_behavior.drop(columns=['first_success_date'], errors='ignore'), 
        on=['userID', 'acquisition_campaignID'], 
        how='left'
    )
    
    post_metrics = ['repeat_flag', 'post_tx_count', 'post_gmv', 'post_discount', 'post_non_promo_tx_count', 'post_campaign_tx_count', 'post_category_count', 'post_merchant_count', 'd7_repeat_flag', 'd30_repeat_flag', 'd60_repeat_flag']
    for col in post_metrics:
        if col in user_master.columns:
            user_master[col] = user_master[col].fillna(0)
            
    user_master['first_success_month'] = user_master['first_success_date'].dt.to_period('M').dt.to_timestamp()
    
    # Category Transition
    npu_users = npu_acquisition[['userID', 'first_success_date', 'first_report_cat']].copy()
    df_post_tx = pd.merge(df_success[['userID', 'reqDate', 'report_cat']], npu_users, on='userID', how='inner')
    df_post_tx = df_post_tx[df_post_tx['reqDate'] > df_post_tx['first_success_date']]
    
    if not df_post_tx.empty:
        category_transition = df_post_tx.groupby(['first_report_cat', 'report_cat'])['userID'].nunique().reset_index()
        category_transition.rename(columns={'report_cat': 'post_report_cat', 'userID': 'user_count'}, inplace=True)
        top_cats = npu_users['first_report_cat'].value_counts().head(15).index
        category_transition = category_transition[category_transition['first_report_cat'].isin(top_cats) & category_transition['post_report_cat'].isin(top_cats)]
    else:
        category_transition = pd.DataFrame(columns=['first_report_cat', 'post_report_cat', 'user_count'])
        
    print("✅ Đã prepare xong Master User Dataset và Category Transition Dataset.")


def make_kpi_card(title, value, subtitle=None, is_currency=False, is_pct=False):
    if is_currency: formatted_val = format_vnd(value)
    elif is_pct: formatted_val = format_pct(value)
    else: formatted_val = format_number(value)
        
    return dbc.Card([
        dbc.CardBody([
            html.H6(title, className="text-uppercase mb-1", style={"fontSize": "11px", "fontWeight": "600", "color": colors['muted']}),
            html.H3(formatted_val, className="mb-0", style={"color": colors['primary'], "fontWeight": "700"}),
            html.Small(subtitle, style={"color": colors['muted'], "fontSize": "11px"}) if subtitle else html.Span()
        ])
    ], style={"border": "1px solid #E2E8F0", "borderRadius": "8px", "boxShadow": "0 2px 4px rgba(0,0,0,0.02)"}, className="mb-4")

def make_chart_card(title, figure, height=480):
    if figure is not None: figure.update_layout(margin=dict(l=60, r=40, t=60, b=60), height=height)
    return dbc.Card([
        dbc.CardBody([
            html.H6(title, style={"fontWeight": "700", "color": colors['dark'], "marginBottom": "15px", "fontSize": "14px"}),
            dcc.Graph(figure=figure, config={'displayModeBar': False}) if figure else html.Div("No Data", style={'height': f'{height}px'})
        ])
    ], style={"border": "1px solid #E2E8F0", "borderRadius": "8px", "boxShadow": "0 2px 4px rgba(0,0,0,0.02)"}, className="mb-4")

def make_insight_card(bullets):
    return dbc.Card([
        dbc.CardBody([
            html.H6("💡 Business Insight", style={"fontWeight": "700", "color": "#D35400", "fontSize": "13px"}),
            html.Ul([
                html.Li(b, style={"fontSize": "13px", "color": colors['dark'], "marginBottom": "6px"}) for b in bullets
            ], className="mb-0 pl-3")
        ], style={"backgroundColor": "#FDF2E9", "borderRadius": "8px"})
    ], style={"border": "1px solid #FAD7A1", "borderRadius": "8px"}, className="mb-4")

def make_guide_card(text):
    return html.Div([
        html.I(className="fas fa-info-circle", style={"marginRight": "8px", "color": colors['secondary']}),
        html.Span(text, style={"fontSize": "13px", "color": colors['muted'], "fontStyle": "italic"})
    ], style={"marginBottom": "20px", "padding": "10px", "backgroundColor": "#F8F9FA", "borderRadius": "6px", "borderLeft": f"4px solid {colors['secondary']}"})


if not missing_files:
    app = dash.Dash(__name__, external_stylesheets=[dbc.themes.FLATLY, "https://use.fontawesome.com/releases/v5.15.4/css/all.css"])
    
    min_date = user_master['first_success_date'].min()
    max_date = user_master['first_success_date'].max()
    
    camp_options = [{'label': f"Camp {c}", 'value': c} for c in user_master['acquisition_campaignID'].dropna().unique()]
    cat_options = [{'label': str(c), 'value': str(c)} for c in user_master['first_report_cat'].dropna().unique()] if 'first_report_cat' in user_master.columns else []
    promo_options = [{'label': str(c), 'value': str(c)} for c in user_master['first_promotion_type_clean'].dropna().unique()] if 'first_promotion_type_clean' in user_master.columns else []
    gender_options = [{'label': str(c), 'value': str(c)} for c in user_master['gender'].dropna().unique()] if 'gender' in user_master.columns else []
    platform_options = [{'label': str(c), 'value': str(c)} for c in user_master['first_platform'].dropna().unique()] if 'first_platform' in user_master.columns else []
    sof_options = [{'label': str(c), 'value': str(c)} for c in user_master['first_sof'].dropna().unique()] if 'first_sof' in user_master.columns else []

    sidebar = html.Div([
        html.H4("FILTERS", className="mb-4", style={"fontWeight": "800", "fontSize": "16px", "letterSpacing": "1px", "color": colors['primary']}),
        html.Label("Date Range (First Success)", style={"fontWeight": "600", "fontSize": "11px", "textTransform": "uppercase"}),
        dcc.DatePickerRange(id='date-filter', min_date_allowed=min_date, max_date_allowed=max_date, start_date=min_date, end_date=max_date, style={"width": "100%", "marginBottom": "20px"}),
        
        html.Label("Min NPU Threshold", style={"fontWeight": "600", "fontSize": "11px", "textTransform": "uppercase"}),
        dcc.Slider(id='npu-threshold', min=0, max=500, step=10, value=30, marks={0: '0', 100: '100', 500: '500'}, className="mb-4"),
        
        html.Label("Report Category", style={"fontWeight": "600", "fontSize": "11px", "textTransform": "uppercase"}),
        dcc.Dropdown(id='cat-filter', options=cat_options, multi=True, placeholder="All Categories", className="mb-3", style={"fontSize": "12px"}),
        html.Label("Promotion Type", style={"fontWeight": "600", "fontSize": "11px", "textTransform": "uppercase"}),
        dcc.Dropdown(id='promo-filter', options=promo_options, multi=True, placeholder="All Promo Types", className="mb-3", style={"fontSize": "12px"}),
        html.Label("Gender", style={"fontWeight": "600", "fontSize": "11px", "textTransform": "uppercase"}),
        dcc.Dropdown(id='gender-filter', options=gender_options, multi=True, placeholder="All Genders", className="mb-3", style={"fontSize": "12px"}),
        html.Label("Platform", style={"fontWeight": "600", "fontSize": "11px", "textTransform": "uppercase"}),
        dcc.Dropdown(id='platform-filter', options=platform_options, multi=True, placeholder="All Platforms", className="mb-3", style={"fontSize": "12px"}),
        html.Label("Campaign ID", style={"fontWeight": "600", "fontSize": "11px", "textTransform": "uppercase"}),
        dcc.Dropdown(id='camp-filter', options=camp_options, multi=True, placeholder="All Campaigns", className="mb-4", style={"fontSize": "12px"}),
        
        html.Hr(),
        dbc.Button("Methodology Note", id="collapse-button", className="mb-2", color="light", size="sm", style={"width": "100%", "textAlign": "left", "fontWeight": "600"}),
        dbc.Collapse(
            dbc.Card(dbc.CardBody([
                html.Ul([
                    html.Li("NPU = first successful promo payment.", style={"fontSize": "11px"}),
                    html.Li("Camp=0 is not acquisition.", style={"fontSize": "11px"}),
                    html.Li("Subsidy Rate = Discount / GMV.", style={"fontSize": "11px"}),
                    html.Li("Dashboard is for monitoring, not causal scoring.", style={"fontSize": "11px"}),
                    html.Li("D30/D60 retention are cumulative repeat indicators.", style={"fontSize": "11px"})
                ], style={"paddingLeft": "15px", "marginBottom": "0", "color": colors['muted']})
            ]), style={"border": "none", "backgroundColor": "transparent"}), id="collapse", is_open=False,
        ),
    ], style={"padding": "25px", "backgroundColor": "#F8F9FA", "height": "100vh", "position": "fixed", "width": "280px", "overflowY": "auto", "borderRight": "1px solid #E2E8F0"})
    
    @app.callback(Output("collapse", "is_open"), [Input("collapse-button", "n_clicks")], [dash.dependencies.State("collapse", "is_open")])
    def toggle_collapse(n, is_open): return not is_open if n else is_open

    content = html.Div([
        html.Div([
            html.H2("Zalopay NPU Campaign Performance", style={"fontWeight": "800", "color": colors['dark'], "marginBottom": "5px"}),
            html.P("Dynamic Segment Analytics & Campaign Comparison", style={"color": colors['muted'], "fontSize": "15px"})
        ], style={"marginBottom": "25px", "paddingBottom": "15px", "borderBottom": "1px solid #E2E8F0"}),
        
        dcc.Tabs(id="tabs", value="tab-1", children=[
            dcc.Tab(label="Executive Overview", value="tab-1", selected_style={"fontWeight": "700", "color": colors['primary'], "borderTop": f"3px solid {colors['primary']}"}),
            dcc.Tab(label="Campaign Comparison", value="tab-2", selected_style={"fontWeight": "700", "color": colors['primary'], "borderTop": f"3px solid {colors['primary']}"}),
            dcc.Tab(label="Post-Acquisition Quality", value="tab-3", selected_style={"fontWeight": "700", "color": colors['primary'], "borderTop": f"3px solid {colors['primary']}"}),
            dcc.Tab(label="Use Case & Expansion", value="tab-4", selected_style={"fontWeight": "700", "color": colors['primary'], "borderTop": f"3px solid {colors['primary']}"})
        ], style={"marginBottom": "30px"}),
        
        html.Div(id="tab-content")
    ], style={"marginLeft": "300px", "padding": "40px", "backgroundColor": colors['card_bg'], "minHeight": "100vh"})
    
    app.layout = html.Div([sidebar, content])
    
    @app.callback(
        Output("tab-content", "children"),
        [Input("tabs", "value"), Input("date-filter", "start_date"), Input("date-filter", "end_date"),
         Input("npu-threshold", "value"), Input("cat-filter", "value"), Input("promo-filter", "value"),
         Input("gender-filter", "value"), Input("platform-filter", "value"), Input("camp-filter", "value")]
    )
    def render_tab(tab, start_date, end_date, min_npu, cats, promos, genders, platforms, camps):
        df_filt = user_master.copy()
        if start_date and end_date:
            df_filt = df_filt[(df_filt['first_success_date'] >= start_date) & (df_filt['first_success_date'] <= pd.to_datetime(end_date) + pd.Timedelta(days=1))]
        if cats: df_filt = df_filt[df_filt['first_report_cat'].isin(cats)]
        if promos: df_filt = df_filt[df_filt['first_promotion_type_clean'].isin(promos)]
        if genders: df_filt = df_filt[df_filt['gender'].isin(genders)]
        if platforms: df_filt = df_filt[df_filt['first_platform'].isin(platforms)]
        if camps: df_filt = df_filt[df_filt['acquisition_campaignID'].isin(camps)]
        
        if df_filt.empty: return html.Div("No data matches the selected filters.", style={"padding": "20px", "color": colors['danger']})

        df_camp = df_filt.groupby('acquisition_campaignID').agg(
            NPU_Count=('userID', 'nunique'),
            First_GMV=('first_amount', 'sum'),
            Total_First_Discount=('first_discountAmount', 'sum'),
            Post_GMV_Sum=('post_gmv', 'sum'),
            Post_Discount_Sum=('post_discount', 'sum'),
            Post_Tx_Sum=('post_tx_count', 'sum'),
            Repeat_User_Count=('repeat_flag', 'sum'),
            D7_Repeat_Count=('d7_repeat_flag', 'sum'),
            D30_Repeat_Count=('d30_repeat_flag', 'sum'),
            D60_Repeat_Count=('d60_repeat_flag', 'sum'),
            Non_Promo_Tx_Sum=('post_non_promo_tx_count', 'sum')
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
        
        # Format label
        df_camp["Campaign_Label"] = "Camp " + df_camp["acquisition_campaignID"].astype(str)
        
        dom_cat = df_filt.groupby('acquisition_campaignID')['first_report_cat'].agg(lambda x: x.mode()[0] if not x.empty else 'Unknown').reset_index(name='Dominant_Category')
        dom_promo = df_filt.groupby('acquisition_campaignID')['first_promotion_type_clean'].agg(lambda x: x.mode()[0] if not x.empty else 'Unknown').reset_index(name='Dominant_Promo')
        df_camp = pd.merge(df_camp, dom_cat, on='acquisition_campaignID', how='left')
        df_camp = pd.merge(df_camp, dom_promo, on='acquisition_campaignID', how='left')
        
        median_df = df_filt.groupby('acquisition_campaignID')['first_amount'].median().reset_index(name='Median_First_Amount')
        df_camp = pd.merge(df_camp, median_df, on='acquisition_campaignID', how='left')
        
        df_camp = df_camp[df_camp['NPU_Count'] >= min_npu].copy()
        if df_camp.empty: return html.Div("No campaigns meet the NPU threshold within this filtered segment.", style={"padding": "20px"})

        if tab == "tab-1":
            overview_df = df_filt.copy()
            tot_npu = overview_df['userID'].nunique()
            tot_campaigns = overview_df['acquisition_campaignID'].nunique()
            tot_gmv = overview_df['first_amount'].fillna(0).sum()
            tot_disc = overview_df['first_discountAmount'].fillna(0).sum()
            
            segment_subsidy_rate = safe_divide(tot_disc, tot_gmv)
            avg_first_amount = safe_divide(tot_gmv, tot_npu)
            
            monthly = overview_df.groupby('first_success_month').agg(NPU_Count=('userID', 'nunique'), GMV=('first_amount', 'sum'), Disc=('first_discountAmount', 'sum')).reset_index()
            fig_trend = px.area(monthly, x='first_success_month', y='NPU_Count', markers=True, color_discrete_sequence=[colors['primary']])
            fig_trend.update_layout(xaxis_title=None, yaxis_title="NPU Count", height=480, margin=dict(l=80, r=40, t=70, b=70), yaxis=dict(tickformat=",", automargin=True))
            
            fig_gmv_disc = go.Figure()
            fig_gmv_disc.add_trace(go.Bar(x=monthly['first_success_month'], y=monthly['GMV'], name='First GMV (VND)', marker_color=colors['muted']))
            fig_gmv_disc.add_trace(go.Scatter(x=monthly['first_success_month'], y=monthly['Disc'], name='First Discount (VND)', marker_color=colors['warning'], yaxis='y2', mode='lines+markers'))
            fig_gmv_disc.update_layout(xaxis_title=None, height=480, margin=dict(l=80, r=80, t=70, b=70), yaxis=dict(tickformat=".2s", automargin=True), yaxis2=dict(overlaying='y', side='right', showgrid=False, tickformat=".2s", automargin=True), barmode='group')
            
            # Horizontal Bar instead of Donut
            uc_df = overview_df.groupby('first_report_cat')['userID'].nunique().reset_index(name='NPU')
            uc_df['first_report_cat'] = uc_df['first_report_cat'].apply(shorten_cat)
            uc_df = uc_df.sort_values('NPU', ascending=False)
            top_uc = uc_df.head(5)
            others_npu = uc_df.iloc[5:]['NPU'].sum()
            if others_npu > 0: top_uc = pd.concat([top_uc, pd.DataFrame({'first_report_cat': ['Others'], 'NPU': [others_npu]})])
            
            fig_uc = px.bar(top_uc.sort_values('NPU', ascending=True), x='NPU', y='first_report_cat', orientation='h', color_discrete_sequence=[colors['secondary']])
            fig_uc.update_layout(xaxis_title="NPU Count", yaxis_title=None, height=350, margin=dict(l=100, r=40, t=40, b=60))
            
            # Calculate dynamic insights
            top1_uc = top_uc.iloc[0]['first_report_cat'] if not top_uc.empty else "N/A"
            top2_uc = top_uc.iloc[1]['first_report_cat'] if len(top_uc) > 1 else "N/A"
            
            return html.Div([
                make_guide_card("This page provides a macro view of NPU acquisition volume and value over time. All metrics are dynamically calculated based on your sidebar filters."),
                dbc.Row([
                    dbc.Col(make_kpi_card("Segment NPU Volume", tot_npu), width=3),
                    dbc.Col(make_kpi_card("Segment Campaigns", tot_campaigns), width=2),
                    dbc.Col(make_kpi_card("Segment First GMV", tot_gmv, is_currency=True), width=3),
                    dbc.Col(make_kpi_card("Segment Subsidy Rate", segment_subsidy_rate, is_pct=True), width=2),
                    dbc.Col(make_kpi_card("Avg First Amount/NPU", avg_first_amount, is_currency=True), width=2),
                ]),
                dbc.Row([
                    dbc.Col(make_chart_card("NPU Acquisition Volume Trend", fig_trend, height=480), width=6),
                    dbc.Col(make_chart_card("First GMV vs First Discount", fig_gmv_disc, height=480), width=6)
                ]),
                dbc.Row([
                    dbc.Col(make_chart_card("Top 5 Use Cases by NPU Volume", fig_uc, height=350), width=5),
                    dbc.Col(make_insight_card([
                        f"[What happened?] {top1_uc} and {top2_uc} are the dominant first-use cases, contributing the majority of acquired NPUs.",
                        f"[So what?] Total First GMV reaches {format_vnd(tot_gmv)} VND with an overall first subsidy rate of {format_pct(segment_subsidy_rate)}.",
                        "[Next step?] Check the trends to see if volume correlates strongly with discount. Investigate budget allocation for declining periods."
                    ]), width=7)
                ])
            ])
            
        elif tab == "tab-2":
            fig_scatter = px.scatter(df_camp, x="NPU_Count", y="Avg_First_Amount", size="First_GMV", 
                                     color="First_Subsidy_Rate", hover_name="Campaign_Label",
                                     color_continuous_scale="RdYlGn_r", size_max=40)
            fig_scatter.update_layout(xaxis_title="NPU Count (log scale)", yaxis_title="Average First Transaction Amount", coloraxis_colorbar_title="First Subsidy Rate", height=500, margin=dict(l=80, r=40, t=60, b=80))
            fig_scatter.update_xaxes(type="log")
            
            fig_bar_npu = px.bar(df_camp.nlargest(10, 'NPU_Count').sort_values('NPU_Count'), x='NPU_Count', y='Campaign_Label', orientation='h', color_discrete_sequence=[colors['primary']])
            fig_bar_npu.update_layout(yaxis_title=None, xaxis_title="NPU Count", height=400, margin=dict(l=100, r=40, t=40, b=60))
            
            fig_bar_gmv = px.bar(df_camp.nlargest(10, 'First_GMV').sort_values('First_GMV'), x='First_GMV', y='Campaign_Label', orientation='h', color_discrete_sequence=[colors['secondary']])
            fig_bar_gmv.update_layout(yaxis_title=None, xaxis_title="First GMV", height=400, margin=dict(l=100, r=40, t=40, b=60))
            
            fig_bar_sub = px.bar(df_camp.nlargest(10, 'First_Subsidy_Rate').sort_values('First_Subsidy_Rate'), x='First_Subsidy_Rate', y='Campaign_Label', orientation='h', color_discrete_sequence=[colors['danger']])
            fig_bar_sub.update_layout(yaxis_title=None, xaxis_title="Subsidy Rate", xaxis=dict(tickformat=".0%"), height=400, margin=dict(l=100, r=40, t=40, b=60))

            from dash.dash_table.Format import Format, Scheme
            df_table = df_camp.sort_values('NPU_Count', ascending=False).head(50)
            cols = [
                {'name': 'Campaign Label', 'id': 'Campaign_Label'},
                {'name': 'NPU Count', 'id': 'NPU_Count', 'type': 'numeric', 'format': Format(group=',')},
                {'name': 'First GMV', 'id': 'First_GMV', 'type': 'numeric', 'format': Format(group=',')},
                {'name': 'Avg Amount', 'id': 'Avg_First_Amount', 'type': 'numeric', 'format': Format(group=',')},
                {'name': 'Median Amount', 'id': 'Median_First_Amount', 'type': 'numeric', 'format': Format(group=',')},
                {'name': 'Total Discount', 'id': 'Total_First_Discount', 'type': 'numeric', 'format': Format(group=',')},
                {'name': 'Subsidy Rate', 'id': 'First_Subsidy_Rate', 'type': 'numeric', 'format': Format(scheme=Scheme.percentage, precision=1)},
                {'name': 'Dominant Cat', 'id': 'Dominant_Category'},
                {'name': 'Dominant Promo', 'id': 'Dominant_Promo'}
            ]
            
            cond_styles = [
                {'if': {'row_index': 'odd'}, 'backgroundColor': '#F8F9FA'},
                {'if': {'filter_query': '{First_Subsidy_Rate} > 0.5', 'column_id': 'First_Subsidy_Rate'}, 'color': colors['danger'], 'fontWeight': 'bold'},
                {'if': {'filter_query': '{First_Subsidy_Rate} < 0.1', 'column_id': 'First_Subsidy_Rate'}, 'color': colors['success'], 'fontWeight': 'bold'},
                {'if': {'filter_query': '{Avg_First_Amount} > 100000', 'column_id': 'Avg_First_Amount'}, 'color': colors['success'], 'fontWeight': 'bold'},
                {'if': {'filter_query': '{NPU_Count} < 50', 'column_id': 'NPU_Count'}, 'backgroundColor': '#FEF9E7', 'color': colors['warning']}
            ]
            
            top_npu_camp = df_camp.loc[df_camp['NPU_Count'].idxmax()]['Campaign_Label'] if not df_camp.empty else "N/A"
            
            return html.Div([
                make_guide_card("This page compares campaigns by acquisition scale, transaction value, and subsidy intensity. Scatter plot uses log scale to handle high-volume outliers."),
                dbc.Row([
                    dbc.Col(make_chart_card("Volume vs Value Portfolio (log scale)", fig_scatter, height=500), width=12),
                ]),
                dbc.Row([
                    dbc.Col(make_chart_card("Top 10 Campaigns by NPU", fig_bar_npu, height=400), width=4),
                    dbc.Col(make_chart_card("Top 10 Campaigns by First GMV", fig_bar_gmv, height=400), width=4),
                    dbc.Col(make_chart_card("Top 10 Campaigns by Subsidy Rate", fig_bar_sub, height=400), width=4),
                ]),
                html.H6("Campaign Acquisition Ranking Table", style={"fontWeight": "700", "color": colors['dark'], "marginBottom": "15px"}),
                dash_table.DataTable(
                    data=df_table.to_dict('records'), columns=cols,
                    style_table={'overflowX': 'auto', 'borderRadius': '8px', 'border': '1px solid #E2E8F0'},
                    style_header={'backgroundColor': '#ECF0F1', 'fontWeight': '700', 'color': colors['dark'], 'padding': '12px'},
                    style_cell={'padding': '10px', 'fontFamily': 'Lato, sans-serif', 'fontSize': '13px'},
                    sort_action='native', style_data_conditional=cond_styles
                ),
                html.Br(),
                make_insight_card([
                    f"[What happened?] {top_npu_camp} dominates acquisition volume, while other campaigns show stronger value signals.",
                    "[So what?] High-volume campaigns often pull the overall average value down. We must balance volume drivers and value drivers in the portfolio.",
                    "[Next step?] Identify campaigns in the top right of the scatter plot (high volume and high value) and scale them."
                ])
            ])
            
        elif tab == "tab-3":
            df_ret = df_camp[df_camp['NPU_Count'] >= max(min_npu, MIN_NPU_FOR_RETENTION)].copy()
            if df_ret.empty: return html.Div("Not enough NPU per campaign to calculate reliable retention metrics (Increase min_npu filter).", style={"padding": "20px", "color": colors['danger']})
            
            tot_npu_ret = df_ret['NPU_Count'].sum()
            w_rep = (df_ret['Repeat_Rate'] * df_ret['NPU_Count']).sum() / tot_npu_ret
            w_d30 = (df_ret['D30_Retention'] * df_ret['NPU_Count']).sum() / tot_npu_ret
            w_d60 = (df_ret['D60_Retention'] * df_ret['NPU_Count']).sum() / tot_npu_ret
            w_post_gmv = (df_ret['Avg_Post_GMV'] * df_ret['NPU_Count']).sum() / tot_npu_ret
            
            fig_ret = px.scatter(df_ret, x="NPU_Count", y="D30_Retention", size="Avg_Post_GMV", color="Post_Non_Promo_Tx_Share", hover_name="Campaign_Label", color_continuous_scale="Blues", size_max=40)
            fig_ret.update_layout(height=520, margin=dict(l=90, r=80, t=70, b=80), xaxis_title="NPU Count", yaxis_title="Repeat within 30 Days", yaxis=dict(tickformat=".0%"))
            
            fig_d30_bar = px.bar(df_ret.nlargest(10, 'D30_Retention').sort_values('D30_Retention'), x='D30_Retention', y='Campaign_Label', orientation='h', color_discrete_sequence=[colors['success']])
            fig_d30_bar.update_layout(height=480, margin=dict(l=100, r=40, t=40, b=60), xaxis_title="Repeat within 30 Days", yaxis_title=None, xaxis=dict(tickformat=".0%"))
            
            from dash.dash_table.Format import Format, Scheme
            ret_cols = [
                {'name': 'Campaign Label', 'id': 'Campaign_Label'},
                {'name': 'NPU Count', 'id': 'NPU_Count', 'type': 'numeric', 'format': Format(group=',')},
                {'name': 'Repeat within 7 Days', 'id': 'D7_Retention', 'type': 'numeric', 'format': Format(scheme=Scheme.percentage, precision=1)},
                {'name': 'Repeat within 30 Days', 'id': 'D30_Retention', 'type': 'numeric', 'format': Format(scheme=Scheme.percentage, precision=1)},
                {'name': 'Repeat within 60 Days', 'id': 'D60_Retention', 'type': 'numeric', 'format': Format(scheme=Scheme.percentage, precision=1)},
                {'name': 'Avg Post Tx', 'id': 'Avg_Post_Tx', 'type': 'numeric', 'format': Format(precision=2)},
                {'name': 'Avg Post GMV', 'id': 'Avg_Post_GMV', 'type': 'numeric', 'format': Format(group=',')},
                {'name': 'Non Promo Share', 'id': 'Post_Non_Promo_Tx_Share', 'type': 'numeric', 'format': Format(scheme=Scheme.percentage, precision=1)},
            ]
            
            cond_styles = [
                {'if': {'row_index': 'odd'}, 'backgroundColor': '#F8F9FA'},
                {'if': {'filter_query': '{D30_Retention} > 0.3', 'column_id': 'D30_Retention'}, 'color': colors['success'], 'fontWeight': 'bold'},
                {'if': {'filter_query': '{Post_Non_Promo_Tx_Share} > 0.7', 'column_id': 'Post_Non_Promo_Tx_Share'}, 'color': colors['success'], 'fontWeight': 'bold'}
            ]
            
            return html.Div([
                make_guide_card("This page shifts focus to post-first behavior. Retention metrics represent 'User has at least 1 repeat transaction within X days' (cumulative)."),
                dbc.Row([
                    dbc.Col(make_kpi_card("Overall Repeat Rate", w_rep, is_pct=True), width=3),
                    dbc.Col(make_kpi_card("Repeat within 30 Days", w_d30, is_pct=True), width=3),
                    dbc.Col(make_kpi_card("Repeat within 60 Days", w_d60, is_pct=True), width=3),
                    dbc.Col(make_kpi_card("Weighted Avg Post GMV", w_post_gmv, is_currency=True), width=3),
                ]),
                dbc.Row([
                    dbc.Col(make_chart_card("Volume vs D30 Repeat (Size=Post GMV, Color=Non-Promo Share)", fig_ret, height=520), width=8),
                    dbc.Col(make_chart_card("Top 10 Campaigns by D30 Repeat", fig_d30_bar, height=520), width=4),
                ]),
                html.H6("Quality Signals Table", style={"fontWeight": "700", "color": colors['dark'], "marginBottom": "15px"}),
                dash_table.DataTable(
                    data=df_ret.sort_values('D30_Retention', ascending=False).head(50).to_dict('records'), columns=ret_cols,
                    style_table={'overflowX': 'auto', 'borderRadius': '8px', 'border': '1px solid #E2E8F0', 'height': '500px'},
                    style_header={'backgroundColor': '#ECF0F1', 'fontWeight': '700', 'color': colors['dark'], 'padding': '12px'},
                    style_cell={'padding': '10px', 'fontFamily': 'Lato, sans-serif', 'fontSize': '13px'},
                    sort_action='native', style_data_conditional=cond_styles
                ),
                html.Br(),
                make_insight_card([
                    "[What happened?] There is a significant gap between short-term acquisition and long-term retention.",
                    "[So what?] Retention and Non-Promo Share (dark blue dots) indicate true user stickiness rather than just subsidy hunting.",
                    "[Next step?] Highlight campaigns with high 'Repeat within 30 Days' and high Non-Promo share as top quality candidates."
                ])
            ])
            
        elif tab == "tab-4":
            uc_summary = df_filt.groupby('first_report_cat').agg(NPU_Count=('userID', 'nunique'), GMV=('first_amount', 'sum')).reset_index()
            uc_summary['Avg_Amount'] = uc_summary.apply(lambda x: safe_divide(x['GMV'], x['NPU_Count']), axis=1)
            uc_summary['first_report_cat_short'] = uc_summary['first_report_cat'].apply(shorten_cat)
            
            fig_uc_scatter = px.scatter(uc_summary, x="NPU_Count", y="Avg_Amount", size="GMV", hover_name="first_report_cat", color="first_report_cat_short", size_max=50)
            fig_uc_scatter.update_layout(height=650, legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5), xaxis_title="NPU Count", yaxis_title="Avg First Amount", margin=dict(l=80, r=40, t=60, b=120))
            
            fig_transition = None
            if not category_transition.empty:
                cat_trans = category_transition.copy()
                cat_trans['first_report_cat'] = cat_trans['first_report_cat'].apply(shorten_cat)
                cat_trans['post_report_cat'] = cat_trans['post_report_cat'].apply(shorten_cat)
                pivot_trans = cat_trans.pivot(index='first_report_cat', columns='post_report_cat', values='user_count').fillna(0)
                fig_transition = go.Figure(data=go.Heatmap(z=pivot_trans.values, x=pivot_trans.columns, y=pivot_trans.index, colorscale='Blues'))
                fig_transition.update_layout(height=650, xaxis_title="Subsequent Post Category", yaxis_title="First Acquired Category", margin=dict(l=150, r=60, t=60, b=150), xaxis=dict(tickangle=-45, automargin=True), yaxis=dict(automargin=True))

            return html.Div([
                make_guide_card("This page analyzes Use Case behavior and Category Expansion. The Heatmap answers: 'If a user is acquired via category A, do they expand to category B?'"),
                dbc.Row([
                    dbc.Col(make_chart_card("First Use Case: Volume vs Value Matrix", fig_uc_scatter, height=650), width=6),
                    dbc.Col(make_chart_card("Behavioral Expansion Heatmap (First Cat -> Post Cat)", fig_transition, height=650), width=6),
                ]),
                make_insight_card([
                    "[What happened?] The Heatmap reveals how users cross-sell into other categories post-acquisition.",
                    "[So what?] A bright diagonal means users stick to their first category. Bright spots off-diagonal show strong cross-category expansion.",
                    "[Next step?] If users from 'Telco' often transition to 'Food', design campaigns that explicitly bundle Telco with Food vouchers."
                ])
            ])

        return html.Div("Please select a valid tab.")

    try: app.run(jupyter_mode="external", debug=False)
    except Exception as e:
        print("External mode failed. Running on port 8050...")
        app.run(debug=False, port=8050)



# --- Production Server Expose ---
server = app.server  # For Gunicorn deployment

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=False)