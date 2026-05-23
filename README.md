# Zalopay NPU Campaign Dashboard

## Description
This dashboard provides comprehensive insights into Zalopay's New Paying User (NPU) acquisition campaigns. It tracks NPU acquisition trends, campaign performance, user retention, and post-acquisition quality across various use cases and promotion types.

## Dashboard Tabs
1. **Executive Overview**: High-level metrics, acquisition trends, and overall campaign portfolio.
2. **Campaign Comparison**: Detailed comparison of campaigns based on NPU count, GMV, discount, and subsidy rates.
3. **Post-Acquisition Quality**: Analysis of user retention (Repeat within 7/30/60 days), post-campaign GMV, and non-promotional transaction share.
4. **Use Case & Expansion**: Breakdown of NPU acquisition by first use case, and their transition behaviors.

## How to run locally
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## How to deploy to Streamlit Community Cloud
1. Push this repository to GitHub.
2. Go to [Streamlit Community Cloud](https://share.streamlit.io/).
3. Create a new app and select the repository.
4. Set the Main file path to `streamlit_app.py`.
5. Click "Deploy".
