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
        # 검색 범위를 넉넉하게 잡습니다.
        run_input = {"hashtags": KEYWORDS, "resultsLimit": 100}
        
        print(f"🚀 Apify 수집 시작: {datetime.now()}")
        run = client.actor(ACTOR_ID).call(run_input=run_input)
        
        results = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        raw_df = pd.DataFrame(results)
        
        if not raw_df.empty:
            print(f"✅ {len(raw_df)}개의 데이터를 성공적으로 가져왔습니다!")
            
            # 컬럼명 통일
            if 'playCount' in raw_df.columns: raw_df['videoPlayCount'] = raw_df['playCount']
            if 'likes' in raw_df.columns: raw_df['likesCount'] = raw_df['likes']
            
            # 숫자 데이터 및 업데이트 시간 강제 삽입 (깃허브 감지용)
            raw_df['videoPlayCount'] = pd.to_numeric(raw_df.get('videoPlayCount', 0), errors='coerce').fillna(0)
            raw_df['likesCount'] = pd.to_numeric(raw_df.get('likesCount', 0), errors='coerce').fillna(0)
            raw_df['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 폴더 생성 및 저장
            os.makedirs('data', exist_ok=True)
            save_path = 'data/latest_monitoring.csv'
            raw_df.to_csv(save_path, index=False)
            print(f"💾 파일 저장 완료: {save_path}")
        else:
            print("⚠️ 수집된 데이터가 없습니다. Apify 설정을 확인해 보세요.")
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    fetch_data()
