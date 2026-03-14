import os
import pandas as pd
from apify_client import ApifyClient
from datetime import datetime

APIFY_TOKEN = os.getenv('APIFY_API_TOKEN')
ACTOR_ID = "apify/instagram-hashtag-scraper"
KEYWORDS = ["메이투", "뷰티캠", "meitu", "beautycam"]

def fetch_data():
    try:
        client = ApifyClient(APIFY_TOKEN)
        run_input = {"hashtags": KEYWORDS, "resultsLimit": 150}
        
        print(f"🚀 수집 시작: {datetime.now()}")
        run = client.actor(ACTOR_ID).call(run_input=run_input)
        
        results = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        raw_df = pd.DataFrame(results)
        
        if not raw_df.empty:
            if 'playCount' in raw_df.columns: raw_df['videoPlayCount'] = raw_df['playCount']
            if 'likesCount' not in raw_df.columns and 'likes' in raw_df.columns: raw_df['likesCount'] = raw_df['likes']
            
            raw_df['videoPlayCount'] = pd.to_numeric(raw_df.get('videoPlayCount', 0), errors='coerce').fillna(0)
            raw_df['likesCount'] = pd.to_numeric(raw_df.get('likesCount', 0), errors='coerce').fillna(0)
            raw_df['is_reels_custom'] = (raw_df.get('type') == 'Video') | (raw_df.get('isVideo') == True) | (raw_df['videoPlayCount'] > 0)
            
            # 깃허브가 변화를 감지하도록 시간 컬럼 추가
            raw_df['last_updated_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            os.makedirs('data', exist_ok=True)
            save_path = 'data/latest_monitoring.csv'
            raw_df.to_csv(save_path, index=False)
            
            print(f"✅ 파일 생성 성공: {save_path}")
        else:
            print("❌ 수집된 데이터 없음")
    except Exception as e:
        print(f"❌ 오류: {e}")

if __name__ == "__main__":
    fetch_data()
