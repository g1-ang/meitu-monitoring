import os
import pandas as pd
from apify_client import ApifyClient
from datetime import datetime

# 설정
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
            # 1. 컬럼 정리
            if 'playCount' in raw_df.columns: raw_df['videoPlayCount'] = raw_df['playCount']
            if 'likesCount' not in raw_df.columns and 'likes' in raw_df.columns: raw_df['likesCount'] = raw_df['likes']
            
            raw_df['videoPlayCount'] = pd.to_numeric(raw_df.get('videoPlayCount', 0), errors='coerce').fillna(0)
            raw_df['likesCount'] = pd.to_numeric(raw_df.get('likesCount', 0), errors='coerce').fillna(0)
            raw_df['is_reels_custom'] = (raw_df.get('type') == 'Video') | (raw_df.get('isVideo') == True) | (raw_df['videoPlayCount'] > 0)

            # [핵심] 강제로 파일 내용을 다르게 만드는 마법의 한 줄
            # 실행할 때마다 현재 시간이 기록되어 깃허브가 '변경됨'으로 인식합니다.
            raw_df['last_updated_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 2. 폴더 생성 및 저장
            os.makedirs('data', exist_ok=True)
            save_path = 'data/latest_monitoring.csv'
            raw_df.to_csv(save_path, index=False)
            
            print(f"✅ 파일 생성 성공: {save_path}")
            print(f"📊 총 {len(raw_df)}행의 데이터를 저장했습니다.")
        else:
            print("❌ 수집된 데이터 없음")
    except Exception as e:
        print(f"❌ 오류: {e}")

if __name__ == "__main__":
    fetch_data()
