import os
import json
import pandas as pd
import urllib.request
from datetime import datetime, timedelta, timezone

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
BRAND_KEYWORDS    = ["meitu", "메이투", "뷰티캠", "beautycam"]
KEYWORD_THRESHOLD = 5  # 한국 기준 동일 키워드 n건 이상 시 알람


def send_slack(blocks: list):
    payload = json.dumps({"blocks": blocks}).encode("utf-8")
    req = urllib.request.Request(
        SLACK_WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as res:
        print(f"슬랙 전송 완료: {res.status}")


def load_instagram() -> pd.DataFrame:
    df = pd.read_csv("data/latest_monitoring.csv", dtype=str)
    for col in ("likesCount", "commentsCount", "videoPlayCount"):
        df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0).astype(int)
    df["timestamp"] = pd.to_datetime(df.get("timestamp", ""), errors="coerce", utc=True)
    return df


def load_twitter() -> pd.DataFrame:
    try:
        df = pd.read_csv("data/latest_twitter.csv", dtype=str)
        for col in ("like_count", "retweet_count", "reply_count", "view_count"):
            df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0).astype(int)
        df["created_at"] = pd.to_datetime(df.get("created_at", ""), errors="coerce", utc=True)
        return df
    except FileNotFoundError:
        return pd.DataFrame()


def get_this_week(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    now         = datetime.now(timezone.utc)
    this_monday = now - timedelta(
        days=now.weekday(),
        hours=now.hour, minutes=now.minute,
        seconds=now.second, microseconds=now.microsecond
    )
    return df[df[date_col] >= this_monday].copy()


def notify_summary(ig_df: pd.DataFrame, tw_df: pd.DataFrame):
    """수집 완료 요약 리포트"""
    now_kst  = datetime.now(timezone.utc) + timedelta(hours=9)
    ig_week  = get_this_week(ig_df, "timestamp")
    tw_week  = get_this_week(tw_df, "created_at") if not tw_df.empty else pd.DataFrame()

    # 인스타 이번 주 통계
    ig_total   = len(ig_week)
    ig_reel    = (ig_week.get("content_type", pd.Series()) == "reel").sum() if "content_type" in ig_week.columns else "-"
    ig_feed    = ig_week["content_type"].isin(["feed", "video_feed"]).sum() if "content_type" in ig_week.columns else "-"
    ig_korean  = 0
    if "caption" in ig_week.columns:
        import re
        ig_korean = ig_week["caption"].apply(lambda x: bool(re.search(r'[가-힣]', str(x)))).sum()
    ig_ad      = (ig_week.get("ad_type", pd.Series()) == "📢 광고").sum() if "ad_type" in ig_week.columns else "-"

    # 트위터 이번 주 통계
    tw_total = len(tw_week) if not tw_week.empty else 0
    tw_meitu = len(tw_week[tw_week["search_keyword"].isin(["meitu", "메이투"])]) if not tw_week.empty and "search_keyword" in tw_week.columns else 0
    tw_beauty= len(tw_week[tw_week["search_keyword"] == "뷰티캠"]) if not tw_week.empty and "search_keyword" in tw_week.columns else 0

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "📊 Meitu 모니터링 — 수집 완료", "emoji": True}
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"수집 시각: *{now_kst.strftime('%Y-%m-%d %H:%M')} KST*"}]
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*📸 인스타그램 — 이번 주*"}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*전체*\n{ig_total}건"},
                {"type": "mrkdwn", "text": f"*🎬 릴스*\n{ig_reel}건"},
                {"type": "mrkdwn", "text": f"*🖼️ 피드*\n{ig_feed}건"},
                {"type": "mrkdwn", "text": f"*🇰🇷 한국*\n{ig_korean}건"},
                {"type": "mrkdwn", "text": f"*📢 광고*\n{ig_ad}건"},
                {"type": "mrkdwn", "text": f"*📋 누적*\n{len(ig_df):,}건"},
            ]
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*🐦 트위터 — 이번 주*"}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*전체*\n{tw_total}건"},
                {"type": "mrkdwn", "text": f"*meitu + 메이투*\n{tw_meitu}건"},
                {"type": "mrkdwn", "text": f"*뷰티캠*\n{tw_beauty}건"},
                {"type": "mrkdwn", "text": f"*📋 누적*\n{len(tw_df) if not tw_df.empty else 0:,}건"},
            ]
        },
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📊 대시보드 보기", "emoji": True},
                    "url": "https://meitu-monitoring.streamlit.app",
                    "style": "primary"
                }
            ]
        }
    ]

    send_slack(blocks)


def notify_keyword_spike(ig_df: pd.DataFrame):
    """한국 기준 동일 키워드 5건 이상 급증 감지"""
    if "search_keyword" not in ig_df.columns or "caption" not in ig_df.columns:
        print("⚠️ search_keyword 컬럼 없음 — 키워드 급증 감지 스킵")
        return

    import re
    ig_week   = get_this_week(ig_df, "timestamp")
    ig_korean = ig_week[ig_week["caption"].apply(lambda x: bool(re.search(r'[가-힣]', str(x))))]

    if ig_korean.empty:
        return

    kw_counts = ig_korean["search_keyword"].value_counts()
    spikes    = kw_counts[kw_counts >= KEYWORD_THRESHOLD]

    if spikes.empty:
        print("키워드 급증 없음")
        return

    spike_lines = "\n".join([f"• *#{kw}* — {cnt}건" for kw, cnt in spikes.items()])

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🚨 키워드 급증 감지!", "emoji": True}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"이번 주 🇰🇷 한국 콘텐츠에서 *{KEYWORD_THRESHOLD}건 이상* 언급된 키워드가 있어요!\n\n{spike_lines}"
            }
        },
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🔍 세부 페이지 보기", "emoji": True},
                    "url": "https://meitu-monitoring.streamlit.app/IG_Details",
                    "style": "primary"
                }
            ]
        }
    ]

    send_slack(blocks)
    print(f"🚨 키워드 급증 알람 전송: {list(spikes.index)}")


def main():
    print("📨 슬랙 알람 전송 시작...")
    ig_df = load_instagram()
    tw_df = load_twitter()

    notify_summary(ig_df, tw_df)
    notify_keyword_spike(ig_df)

    print("✅ 슬랙 알람 완료!")


if __name__ == "__main__":
    main()
