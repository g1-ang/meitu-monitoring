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
        "resultsLimit": 200, 
    }
    
    print("🚀 Apify 데이터 수집 시작 (릴스 탐지 강화 버전)...")
    run = client.actor(ACTOR_ID).call(run_input=run_input)
    
    results = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    raw_df = pd.DataFrame(results)
    
    if not raw_df.empty:
        # 1. 숫자형 변환 (에러 방지)
        view_col = next((c for c in ['videoPlayCount', 'playCount', 'viewCount'] if c in raw_df.columns), None)
        like_col = next((c for c in ['likesCount', 'likes'] if c in raw_df.columns), None)
        
        if view_col:
            raw_df[view_col] = pd.to_numeric(raw_df[view_col], errors='coerce').fillna(0)
        if like_col:
            raw_df[like_col] = pd.to_numeric(raw_df[like_col], errors='coerce').fillna(0)

        # 2. 릴스(동영상) 판별 로직 강화
        # - isVideo가 True이거나, 조회수(view_col)가 0보다 큰 경우를 모두 릴스로 간주
        is_video_mask = (raw_df['isVideo'] == True) if 'isVideo' in raw_df.columns else pd.Series([False] * len(raw_df))
        if view_col:
            is_video_mask = is_video_mask | (raw_df[view_col] > 0)
        
        # 3. 데이터 분리 및 정렬
        reels_df = raw_df[is_video_mask].copy()
        feed_df = raw_df[~is_video_mask].copy()

        # 릴스는 조회수 순, 피드는 좋아요 순으로 정렬
        if view_col:
            reels_df = reels_df.sort_values(by=view_col, ascending=False)
        feed_df = feed_df.sort_values(by=like_col, ascending=False)

        # 4. 'type' 컬럼 강제 생성 (대시보드에서 릴스/피드 구분용)
        reels_df['is_reels_custom'] = True
        feed_df['is_reels_custom'] = False

        # 합쳐서 저장
        final_df = pd.concat([reels_df.head(60), feed_df.head(60)])
        
        os.makedirs('data', exist_ok=True)
        final_df.to_csv('data/latest_monitoring.csv', index=False)
        print(f"✅ 필터링 완료: 릴스 {len(reels_df)}개 / 피드 {len(feed_df)}개")
    else:
        print("❌ 수집된 데이터가 없습니다.")

if __name__ == "__main__":
    fetch_data()
