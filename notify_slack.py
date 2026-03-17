import os
import re
import json
import pandas as pd
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
KEYWORD_THRESHOLD = 5
REEL_VIEW_MIN     = 10000
FEED_LIKE_MIN     = 500

BRAND_KEYWORDS = ["meitu", "메이투", "뷰티캠", "beautycam"]

DASHBOARD_URL = "https://meitu-monitoring.streamlit.app"
DETAILS_URL   = "https://meitu-monitoring.streamlit.app/details"


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
    if "content_type" not in df.columns:
        df["content_type"] = df.apply(classify_content_type, axis=1)
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


def classify_content_type(row) -> str:
    product_type = str(row.get("productType", "")).lower().strip()
    media_type   = str(row.get("type", "")).lower().strip()
    url          = str(row.get("url", ""))
    video_url    = str(row.get("videoUrl", ""))
    if product_type == "clips":                         return "reel"
    if product_type == "carousel_item":                 return "carousel_item"
    if product_type in ("feed", "carousel_container"):  return "feed"
    if video_url and video_url not in ("nan", ""):      return "reel"
    if media_type == "video":
        return "reel" if "/reel/" in url else "video_feed"
    if media_type in ("image", "sidecar"):              return "feed"
    return "unknown"


def is_korean(text: str) -> bool:
    return bool(re.search(r'[가-힣]', str(text)))


def fmt(n) -> str:
    n = int(n)
    if n >= 10000: return f"{n/10000:.1f}만"
    if n >= 1000:  return f"{n/1000:.1f}천"
    return str(n)


def delta_str(cur: int, prev: int) -> str:
    diff = cur - prev
    if diff > 0:  return f"+{diff}건"
    if diff < 0:  return f"{diff}건"
    return "±0건"


def get_monday(weeks_ago: int = 0) -> datetime:
    now         = datetime.now(timezone.utc)
    this_monday = now - timedelta(
        days=now.weekday(),
        hours=now.hour, minutes=now.minute,
        seconds=now.second, microseconds=now.microsecond
    )
    return this_monday - timedelta(weeks=weeks_ago)


def get_report_range():
    now     = datetime.now(timezone.utc)
    weekday = now.weekday()
    if weekday == 0:
        start = get_monday(weeks_ago=1)
        end   = get_monday(weeks_ago=0)
        label = f"지난 주 ({start.strftime('%m/%d')} ~ {(end - timedelta(days=1)).strftime('%m/%d')})"
    else:
        start = get_monday(weeks_ago=0)
        end   = now
        label = f"이번 주 ({start.strftime('%m/%d')} ~ {now.strftime('%m/%d %H:%M')})"
    return start, end, label


def get_prev_range():
    now     = datetime.now(timezone.utc)
    weekday = now.weekday()
    if weekday == 0:
        start = get_monday(weeks_ago=2)
        end   = get_monday(weeks_ago=1)
    else:
        this_start   = get_monday(weeks_ago=0)
        days_elapsed = now - this_start
        start        = this_start - timedelta(weeks=1)
        end          = start + days_elapsed
    return start, end


def filter_range(df: pd.DataFrame, date_col: str, start, end) -> pd.DataFrame:
    return df[(df[date_col] >= start) & (df[date_col] < end)].copy()


def build_ig_top3_blocks(df_kr: pd.DataFrame) -> list:
    """브랜드 키워드 수집 콘텐츠만 TOP3"""
    blocks = []

    # 브랜드 키워드 필터
    if "search_keyword" in df_kr.columns:
        df_brand = df_kr[df_kr["search_keyword"].isin(BRAND_KEYWORDS)]
    else:
        df_brand = df_kr

    # 릴스 TOP3 (조회수 1만 이상)
    reels = df_brand[df_brand["content_type"] == "reel"].copy()
    reels = reels[reels["videoPlayCount"] >= REEL_VIEW_MIN].nlargest(3, "videoPlayCount")

    reel_lines = []
    for i, (_, row) in enumerate(reels.iterrows(), 1):
        url      = str(row.get("url", ""))
        username = str(row.get("ownerUsername", "-"))
        views    = fmt(row["videoPlayCount"])
        reel_lines.append(f"*{i}위* @{username}  |  조회수 {views}\n{url}")

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*릴스 TOP 3* (조회수 1만 이상 · 브랜드 키워드 기준)\n" + (
                "\n".join(reel_lines) if reel_lines else "_조건에 해당하는 콘텐츠 없음_"
            )
        }
    })

    # 피드 TOP3 (좋아요 500 이상)
    feeds = df_brand[df_brand["content_type"].isin(["feed", "video_feed"])].copy()
    feeds = feeds[feeds["likesCount"] >= FEED_LIKE_MIN].nlargest(3, "likesCount")

    feed_lines = []
    for i, (_, row) in enumerate(feeds.iterrows(), 1):
        url      = str(row.get("url", ""))
        username = str(row.get("ownerUsername", "-"))
        likes    = fmt(row["likesCount"])
        feed_lines.append(f"*{i}위* @{username}  |  좋아요 {likes}\n{url}")

    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*피드 TOP 3* (좋아요 500 이상 · 브랜드 키워드 기준)\n" + (
                "\n".join(feed_lines) if feed_lines else "_조건에 해당하는 콘텐츠 없음_"
            )
        }
    })

    return blocks


def build_tw_top_blocks(df_tw: pd.DataFrame) -> list:
    """브랜드 키워드 트윗만 좋아요/리트윗 최다 1건씩"""
    if df_tw.empty:
        return [{"type": "section", "text": {"type": "mrkdwn", "text": "_데이터 없음_"}}]

    # 브랜드 키워드 필터
    if "search_keyword" in df_tw.columns:
        df_brand = df_tw[df_tw["search_keyword"].isin(BRAND_KEYWORDS)]
    else:
        df_brand = df_tw

    if df_brand.empty:
        return [{"type": "section", "text": {"type": "mrkdwn", "text": "_브랜드 키워드 트윗 없음_"}}]

    # 좋아요 최다
    top_like    = df_brand.nlargest(1, "like_count").iloc[0]
    text_like   = re.sub(r'https?://\S+', '', str(top_like.get("text", ""))).strip()[:60] + "..."
    url_like    = str(top_like.get("url", ""))
    handle_like = str(top_like.get("author_handle", "-"))
    kw_like     = str(top_like.get("search_keyword", ""))

    # 리트윗 최다
    top_rt    = df_brand.nlargest(1, "retweet_count").iloc[0]
    text_rt   = re.sub(r'https?://\S+', '', str(top_rt.get("text", ""))).strip()[:60] + "..."
    url_rt    = str(top_rt.get("url", ""))
    handle_rt = str(top_rt.get("author_handle", "-"))
    kw_rt     = str(top_rt.get("search_keyword", ""))

    return [{
        "type": "section",
        "fields": [
            {
                "type": "mrkdwn",
                "text": f"*좋아요 최다* (#{kw_like})\n@{handle_like}  |  좋아요 {fmt(top_like['like_count'])}\n_{text_like}_\n{url_like}"
            },
            {
                "type": "mrkdwn",
                "text": f"*리트윗 최다* (#{kw_rt})\n@{handle_rt}  |  리트윗 {fmt(top_rt['retweet_count'])}\n_{text_rt}_\n{url_rt}"
            }
        ]
    }]


def notify_weekly_report(ig_df: pd.DataFrame, tw_df: pd.DataFrame):
    now_kst           = datetime.now(timezone.utc) + timedelta(hours=9)
    start, end, label = get_report_range()
    prev_start, prev_end = get_prev_range()

    weekday   = datetime.now(timezone.utc).weekday()
    day_label = "월요일" if weekday == 0 else "목요일"

    # 인스타 한국 콘텐츠
    ig_cur     = filter_range(ig_df, "timestamp", start, end)
    ig_prev    = filter_range(ig_df, "timestamp", prev_start, prev_end)
    ig_cur_kr  = ig_cur[ig_cur["caption"].apply(is_korean)]  if "caption" in ig_cur.columns  else ig_cur
    ig_prev_kr = ig_prev[ig_prev["caption"].apply(is_korean)] if "caption" in ig_prev.columns else ig_prev

    # 인스타 통계도 브랜드 키워드 기준
    ig_cur_brand  = ig_cur_kr[ig_cur_kr["search_keyword"].isin(BRAND_KEYWORDS)]  if "search_keyword" in ig_cur_kr.columns  else ig_cur_kr
    ig_prev_brand = ig_prev_kr[ig_prev_kr["search_keyword"].isin(BRAND_KEYWORDS)] if "search_keyword" in ig_prev_kr.columns else ig_prev_kr

    cur_reel  = (ig_cur_brand["content_type"] == "reel").sum()
    prev_reel = (ig_prev_brand["content_type"] == "reel").sum()
    cur_feed  = ig_cur_brand["content_type"].isin(["feed", "video_feed"]).sum()
    prev_feed = ig_prev_brand["content_type"].isin(["feed", "video_feed"]).sum()

    # 트위터
    tw_cur  = filter_range(tw_df, "created_at", start, end)  if not tw_df.empty else pd.DataFrame()
    tw_prev = filter_range(tw_df, "created_at", prev_start, prev_end) if not tw_df.empty else pd.DataFrame()

    def tw_cnt(df, kws):
        return len(df[df["search_keyword"].isin(kws)]) if not df.empty and "search_keyword" in df.columns else 0

    cur_meitu   = tw_cnt(tw_cur,  ["meitu", "메이투"])
    prev_meitu  = tw_cnt(tw_prev, ["meitu", "메이투"])
    cur_beauty  = tw_cnt(tw_cur,  ["뷰티캠"])
    prev_beauty = tw_cnt(tw_prev, ["뷰티캠"])

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Meitu 주간 리포트 ({day_label})", "emoji": True}
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"발송: *{now_kst.strftime('%Y-%m-%d %H:%M')} KST*  |  기간: {label}  |  한국 · 브랜드 키워드 기준"}]
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*인스타그램 (한국 · 브랜드)*\n"
                    f"릴스: *{cur_reel}건* ({delta_str(cur_reel, prev_reel)})  |  "
                    f"피드: *{cur_feed}건* ({delta_str(cur_feed, prev_feed)})"
                )
            }
        },
    ]

    blocks += build_ig_top3_blocks(ig_cur_kr)
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                f"*트위터 (한국 · 브랜드)*\n"
                f"meitu+메이투: *{cur_meitu}건* ({delta_str(cur_meitu, prev_meitu)})  |  "
                f"뷰티캠: *{cur_beauty}건* ({delta_str(cur_beauty, prev_beauty)})"
            )
        }
    })
    blocks += build_tw_top_blocks(tw_cur)
    blocks += [
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "대시보드 보기", "emoji": True},
                    "url": DASHBOARD_URL,
                    "style": "primary"
                }
            ]
        }
    ]

    send_slack(blocks)
    print(f"주간 리포트 전송 완료 ({day_label})")


def notify_keyword_spike(ig_df: pd.DataFrame, tw_df: pd.DataFrame):
    start, end, _ = get_report_range()

    ig_cur = filter_range(ig_df, "timestamp", start, end)
    tw_cur = filter_range(tw_df, "created_at", start, end) if not tw_df.empty else pd.DataFrame()

    STOPWORDS = {
        "meitu", "메이투", "뷰티캠", "beautycam", "beauty", "cam",
        "fyp", "foryou", "viral", "reels", "reel", "love", "like",
        "follow", "share", "instagram", "insta", "photo", "video",
        "좋아요", "팔로우", "댓글", "공유", "인스타", "인스타그램",
    }

    ig_spike_lines = []
    if "caption" in ig_cur.columns:
        ig_kr   = ig_cur[ig_cur["caption"].apply(is_korean)]
        counter = Counter()
        for caption in ig_kr["caption"].dropna():
            for tag in re.findall(r'#(\w+)', str(caption).lower()):
                if tag not in STOPWORDS and len(tag) >= 2:
                    counter[tag] += 1
        ig_spikes      = {k: v for k, v in counter.items() if v >= KEYWORD_THRESHOLD}
        ig_spike_lines = [f"• *#{kw}* — {cnt}건" for kw, cnt in sorted(ig_spikes.items(), key=lambda x: -x[1])]

    tw_spike_lines = []
    if not tw_cur.empty and "text" in tw_cur.columns:
        counter = Counter()
        for text in tw_cur["text"].dropna():
            for tag in re.findall(r'#(\w+)', str(text).lower()):
                if tag not in STOPWORDS and len(tag) >= 2:
                    counter[tag] += 1
            for word in re.findall(r'[가-힣]{2,}', str(text)):
                if word not in STOPWORDS:
                    counter[word] += 1
        tw_spikes      = {k: v for k, v in counter.items() if v >= KEYWORD_THRESHOLD}
        tw_spike_lines = [f"• *#{kw}* — {cnt}건" for kw, cnt in sorted(tw_spikes.items(), key=lambda x: -x[1])]

    if not ig_spike_lines and not tw_spike_lines:
        print("키워드 급증 없음")
        return

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "키워드 급증 감지!", "emoji": True}
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"기준: 한국 콘텐츠 캡션  |  {KEYWORD_THRESHOLD}건 이상 언급"}]
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*인스타그램*\n" + ("\n".join(ig_spike_lines) if ig_spike_lines else "_해당 없음_")
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*트위터*\n" + ("\n".join(tw_spike_lines) if tw_spike_lines else "_해당 없음_")
            }
        },
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "세부 페이지 보기", "emoji": True},
                    "url": DETAILS_URL,
                    "style": "primary"
                }
            ]
        }
    ]

    send_slack(blocks)
    print("키워드 급증 알람 전송 완료")


def main():
    print("슬랙 알람 전송 시작...")
    ig_df = load_instagram()
    tw_df = load_twitter()
    notify_weekly_report(ig_df, tw_df)
    notify_keyword_spike(ig_df, tw_df)
    print("슬랙 알람 완료!")


if __name__ == "__main__":
    main()
