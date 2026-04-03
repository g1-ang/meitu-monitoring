import os
import re
import pandas as pd
from apify_client import ApifyClient
from datetime import datetime

APIFY_TOKEN = os.getenv('APIFY_API_TOKEN')
ACTOR_ID = "apidojo/tweet-scraper"
OUTPUT_PATH = "data/latest_twitter.csv"
KEYWORDS = ["meitu", "메이투", "뷰티캠"]

def extract_image_url(item: dict) -> str:
    extended = item.get("extendedEntities", {}) or {}
    media_list = extended.get("media", []) or []
    for m in media_list:
        if m.get("type") in ("photo", "animated_gif"):
            return m.get("mediaUrlHttps", m.get("media_url_https", ""))

    entities = item.get("entities", {}) or {}
    media_list = entities.get("media", []) or []
    for m in media_list:
        if m.get("type") == "photo":
            return m.get("mediaUrlHttps", m.get("media_url_https", ""))

    media = item.get("media", []) or []
    if isinstance(media, list) and media:
        m = media[0]
        if isinstance(m, dict):
            return m.get("mediaUrlHttps", m.get("url", ""))
    return ""

def normalize_tweet(item: dict, keyword: str) -> dict:
    author = item.get("author", {}) or {}
    return {
        "tweet_id": item.get("id", ""),
        "search_keyword": keyword,
        "text": item.get("text", ""),
        "created_at": item.get("createdAt", ""),
        "author_id": author.get("id", ""),
        "author_name": author.get("name", ""),
        "author_handle": author.get("userName", ""),
        "view_count": item.get("viewCount", 0) or 0,
        "like_count": item.get("likeCount", 0) or 0,
        "retweet_count": item.get("retweetCount", 0) or 0,
        "reply_count": item.get("replyCount", 0) or 0,
        "url": item.get("url", ""),
        "lang": item.get("lang", ""),
        "is_retweet": item.get("isRetweet", False) or False,
        "media_url": extract_image_url(item),
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "country": "한국",
    }

def append_and_dedup(new_df: pd.DataFrame) -> pd.DataFrame:
    os.makedirs("data", exist_ok=True)
    if os.path.exists(OUTPUT_PATH):
        existing = pd.read_csv(OUTPUT_PATH, dtype=str)
        print(f"기존 트윗: {len(existing):,}건")
        combined = pd.concat([existing, new_df.astype(str)], ignore_index=True)
    else:
        print("신규 파일 생성")
        combined = new_df.astype(str)

    before = len(combined)
    combined = (
        combined
        .sort_values("last_updated", ascending=False)
        .drop_duplicates(subset=["tweet_id"], keep="first")
        .reset_index(drop=True)
    )
    print(f"중복 제거 후 최종: {len(combined):,}건 (제거 {before - len(combined):,}건)")
    return combined

def fetch_twitter():
    try:
        client = ApifyClient(APIFY_TOKEN)
        all_tweets = []

        for keyword in KEYWORDS:
            print(f"'{keyword}' 한국어 트윗 수집 중...")
            run = client.actor(ACTOR_ID).call(run_input={
                "searchTerms": [keyword],
                "maxItems": 50,
                "sort": "Latest",
                "tweetLanguage": "ko",
                "_triggeredBy": "지원",
                "_project": "메이투 모니터링",
            })
            results = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            count = 0
            for item in results:
                if item.get("isRetweet", False):
                    continue
                all_tweets.append(normalize_tweet(item, keyword))
                count += 1
            print(f" -> {count}건 저장 (리트윗 제외)")

        if not all_tweets:
            print("수집된 트윗이 없습니다.")
            return

        df = pd.DataFrame(all_tweets)
        for col in ("view_count", "like_count", "retweet_count", "reply_count"):
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

        img_count = (df["media_url"] != "").sum()
        print(f"\n트위터 수집 완료: {len(df)}건 (이미지 포함: {img_count}건)")

        final = append_and_dedup(df)
        final.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
        print(f"저장 완료: {OUTPUT_PATH} ({len(final):,}건 누적)")

    except Exception as e:
        print(f"오류: {e}")
        raise

if __name__ == "__main__":
    fetch_twitter()
