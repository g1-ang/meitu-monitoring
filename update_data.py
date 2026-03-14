import os
import pandas as pd
from apify_client import ApifyClient

# 설정
APIFY_TOKEN = os.getenv('APIFY_API_TOKEN')
ACTOR_ID = "apify/instagram-hashtag-scraper"
KEYWORDS = ["메이투", "뷰티캠", "meitu", "beautycam"]

def fetch_data():
    try:
        client = ApifyClient(APIFY_TOKEN)
        
        run_input = {
            "hashtags": KEYWORDS,
            "resultsLimit": 150, 
        }
        
        print("🚀 Apify 데이터 수집 시작...")
        run = client.actor(ACTOR_ID).call(run_input=run_input)
        
        results = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        raw_df = pd.DataFrame(results)
        
        if not raw_df.empty:
            # 1. 컬럼명 통합
            if 'playCount' in raw_df.columns: raw_df['videoPlayCount'] = raw_df['playCount']
            if 'likesCount' not in raw_df.columns and 'likes' in raw_df.columns: 
                raw_df['likesCount'] = raw_df['likes']
            
            # 2. 숫자형 변환
            raw_df['videoPlayCount'] = pd.to_numeric(raw_df.get('videoPlayCount', 0), errors='coerce').fillna(0)
            raw_df['likesCount'] = pd.to_numeric(raw_df.get('likesCount', 0), errors='coerce').fillna(0)

            # 3. 릴스 판별
            is_video = (raw_df.get('type') == 'Video') | (raw_df.get('isVideo') == True) | (raw_df['videoPlayCount'] > 0)
            raw_df['is_reels_custom'] = is_video

            # 4. 정렬 및 합치기
            reels_df = raw_df[raw_df['is_reels_custom'] == True].sort_values(by='videoPlayCount', ascending=False)
            feed_df = raw_df[raw_df['is_reels_custom'] == False].sort_values(by='likesCount', ascending=False)
            final_df = pd.concat([reels_df, feed_df])
            
            # 저장 폴더 강제 생성
            os.makedirs('data', exist_ok=True)
            save_path = 'data/latest_monitoring.csv'
            final_df.to_csv(save_path, index=False)
            
            print(f"✅ 저장 완료: {save_path} ({len(final_df)} rows)")
        else:
            print("❌ 수집된 데이터가 없습니다.")
    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        # 에러가 나도 워크플로우가 멈추지 않게 하려면 여기서 중단 가능

if __name__ == "__main__":
    fetch_data()
