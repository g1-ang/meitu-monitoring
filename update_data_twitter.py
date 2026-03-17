import os
import re
import pandas as pd
from apify_client import ApifyClient
from datetime import datetime

APIFY_TOKEN = os.getenv('APIFY_API_TOKEN')
ACTOR_ID    = "apidojo/tweet-scraper"
OUTPUT_PATH = "data/latest_twitter.csv"

# 수집할 키워드
KEYWORDS = ["meitu", "메이투", "뷰티캠"]


def normalize_tweet(item: dict, keyword: str) -> dict:
    """트윗 데이터 정규화"""
    author = item.get("author", {}) or {}

    return {
        "tweet_id":      item.get("id", ""),
        "search_keyword": keyword,
        "text":          item.get("text", ""),
        "created_at":    item.get("createdAt", ""),
        "author_id":     author.get("id", ""),
        "author_name":   author.get("name", ""),
        "author_handle": author.get("userName", ""),
        "view_count":    item.get("viewCount", 0) or 0,
        "like_count":    item.get("likeCount", 0) or 0,
        "retweet_count": item.get("retweetCount", 0) or 0,
        "reply_count":   item.get("replyCount", 0) or 0,
        "url":           item.get("url", ""),
        "lang":          item.get("lang", ""),
        "is_retweet":    item.get("isRetweet", False) or False,
        "last_updated":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def detect_country(lang: str, text: str) -> str:
    """언어 코드 + 텍스트로 국가 추정"""
    if lang == "ko" or re.search(r'[가-힣]', str(text)):
        return "🇰🇷 한국"
    if lang == "ja" or re.search(r'[\u3040-\u30FF]', str(text)):
        return "🇯🇵 일본"
    if lang == "zh" or re.search(r'[\u4E00-\u9FFF]', str(text)):
        return "🇨🇳 중국/대만"
    if lang == "th" or re.search(r'[\u0E00-\u0E7F]', str(text)):
        return "🇹🇭 태국"
    if lang == "en":
        return "🌐 영어권"
    return "🌏 기타"


def append_and_dedup(new_df: pd.DataFrame) -> pd.DataFrame:
    os.makedirs("data", exist_ok=True)
    if os.path.exists(OUTPUT_PATH):
        existing = pd.read_csv(OUTPUT_PATH, dtype=str)
        print(f"📂 기존 트윗: {len(existing):,}건")
        combined = pd.concat([existing, new_df.astype(str)], ignore_index=True)
    else:
        print("📂 신규 파일 생성")
        combined = new_df.astype(str)

    before = len(combined)
    combined = (
        combined
        .sort_values("last_updated", ascending=False)
        .drop_duplicates(subset=["tweet_id"], keep="first")
        .reset_index(drop=True)
    )
    print(f"🗑️  중복 제거 후 최종: {len(combined):,}건 (제거 {before - len(combined):,}건)")
    return combined


def fetch_twitter():
    try:
        client      = ApifyClient(APIFY_TOKEN)
        all_tweets  = []

        for keyword in KEYWORDS:
            print(f"🐦 '{keyword}' 트윗 수집 중...")
            run = client.actor(ACTOR_ID).call(run_input={
                "searchTerms":  [keyword],
                "maxItems":     50,           # 키워드당 50건
                "sort":         "Latest",     # 최신순
                "tweetLanguage": "",          # 전체 언어
            })
            results = list(client.dataset(run["defaultDatasetId"]).iterate_items())

            for item in results:
                # 리트윗 제외
                if item.get("isRetweet", False):
                    continue
                tweet = normalize_tweet(item, keyword)
                tweet["country"] = detect_country(tweet["lang"], tweet["text"])
                all_tweets.append(tweet)

            print(f"   → {len(results)}건 수집 (리트윗 제외 후 저장)")

        if not all_tweets:
            print("⚠️ 수집된 트윗이 없습니다.")
            return

        df = pd.DataFrame(all_tweets)

        # 수치형 변환
        for col in ("view_count", "like_count", "retweet_count", "reply_count"):
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

        print(f"\n✅ 수집 완료: {len(df)}건")
        print(f"   🇰🇷 한국: {(df['country'] == '🇰🇷 한국').sum()}건")
        print(f"   🌐 영어권: {(df['country'] == '🌐 영어권').sum()}건")

        final = append_and_dedup(df)
        final.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
        print(f"💾 저장 완료: {OUTPUT_PATH} ({len(final):,}건 누적)")

    except Exception as e:
        print(f"❌ 오류: {e}")
        raise


if __name__ == "__main__":
    fetch_twitter()
