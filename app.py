import re
import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import datetime, timedelta, timezone

st.set_page_config(page_title="Meitu 모니터링", page_icon="📊", layout="wide")

TYPE_COLOR = {
    "reel":       "#E1306C",
    "feed":       "#405DE6",
    "video_feed": "#833AB4",
}
TYPE_LABEL = {
    "reel":       "릴스",
    "feed":       "피드",
    "video_feed": "피드(동영상)",
}

AD_KEYWORDS = [
    "광고", "유료광고", "유료_광고", "ad", "sponsored", "collaboration",
    "콜라보", "협찬", "제공", "paid", "promotion"
]


def detect_country(text: str) -> str:
    t = str(text)
    if re.search(r'[가-힣]', t):           return "🇰🇷 한국"
    if re.search(r'[\u3040-\u30FF]', t):   return "🇯🇵 일본"
    if re.search(r'[\u4E00-\u9FFF]', t):   return "🇨🇳 중국/대만"
    if re.search(r'[\u0E00-\u0E7F]', t):   return "🇹🇭 태국"
    if re.search(r'[\u0600-\u06FF]', t):   return "🇸🇦 아랍"
    if re.search(r'[à-öø-ÿÀ-ÖØ-ß]', t):   return "🇪🇺 유럽"
    if re.search(r'[a-zA-Z]', t):          return "🌐 영어권"
    return "🌏 기타"


def detect_ad(text: str) -> str:
    t = str(text).lower()
    for kw in AD_KEYWORDS:
        if f"#{kw.lower()}" in t or f" {kw.lower()} " in t or t.startswith(kw.lower()):
            return "📢 광고"
    return "🌱 오가닉"


@st.cache_data(ttl=300)
def load_data():
    df = pd.read_csv("data/latest_monitoring.csv", dtype=str)

    for col in ("likesCount", "commentsCount", "videoPlayCount"):
        df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0).astype(int)

    df["timestamp"]    = pd.to_datetime(df.get("timestamp", ""), errors="coerce", utc=True)
    df["last_updated"] = pd.to_datetime(df.get("last_updated", ""), errors="coerce")
    df["engagement"]   = df["likesCount"] + df["commentsCount"]

    def classify(row):
        product_type = str(row.get("productType", "")).lower().strip()
        media_type   = str(row.get("type", "")).
