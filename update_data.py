import os
import pandas as pd
from apify_client import ApifyClient

# 설정
APIFY_TOKEN = os.getenv('APIFY_API_TOKEN')
ACTOR_ID = "apify/instagram-hashtag-scraper"
KEYWORDS = ["메이투", "뷰티캠", "meitu", "beautycam"]

def fetch_data():
    client = ApifyClient(APIFY_TOKEN)
    
    run_input = {
        "hashtags": KEYWORDS,
        "resultsLimit": 200,  # 넉넉하게 수집하여 필터링
    }
    
    print("🚀 Apify 데이터 수집 시작 (릴스+피드 통합)...")
    run = client.actor(ACTOR_ID).call(run_input=run_input)
    
    results = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    raw_df = pd.DataFrame(results)
    
    if not raw_df.empty:
        # 데이터 정제 (숫자형 변환)
        view_col = next((c for c in ['videoPlayCount', 'playCount'] if c in raw_df.columns), None)
        like_col = 'likesCount' if 'likesCount' in raw_df.columns else 'likes'
        
        if view_col: raw_df[view_col] = pd.to_numeric(raw_df[view_col], errors='coerce').fillna(0)
        raw_df[like_col] = pd.to_numeric(raw_df[like_col], errors='coerce').fillna(0)

        # 1. 릴스(동영상) 추출 및 조회수 순 정렬
        is_video = raw_df['isVideo'] == True if 'isVideo' in raw_df.columns else raw_df['type'].str.contains('Video', na=False)
        reels_df = raw_df[is_video].copy()
        if view_col:
            reels_df = reels_df.sort_values(by=view_col, ascending=False)

        # 2. 일반 피드(사진) 추출 및 좋아요 순 정렬
        feed_df = raw_df[~is_video].copy()
        feed_df = feed_df.sort_values(by=like_col, ascending=False)

        # 3. 두 데이터 합치기 (릴스 상위 + 피드 상위)
        final_df = pd.concat([reels_df.head(50), feed_df.head(50)])

        # 파일 저장
        os.makedirs('data', exist_ok=True)
        final_df.to_csv('data/latest_monitoring.csv', index=False)
        print(f"✅ 수집 완료: 릴스 {len(reels_df)}개, 피드 {len(feed_df)}개")
    else:
        print("❌ 수집된 데이터가 없습니다.")

if __name__ == "__main__":
    fetch_data()
