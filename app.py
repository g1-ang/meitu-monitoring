import streamlit as st
import pandas as pd
import os
import re
from collections import Counter

# 1. 페이지 설정
st.set_page_config(page_title="메이투 마케팅 대시보드", layout="wide")
st.title("🚀 메이투 즉각 모니터링 자동화 시스템")

# 2. 파일 불러오기 로직 수정
data_dir = './data'
# 자동 수집된 최신 파일 경로
auto_data_path = os.path.join(data_dir, 'latest_monitoring.csv')

if os.path.exists(auto_data_path):
    file_path = auto_data_path
    st.sidebar.success("✅ 자동 업데이트된 최신 데이터를 표시 중입니다.")
else:
    # 자동 수집 파일이 없을 경우 기존의 CSV 파일들 찾기
    csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')] if os.path.exists(data_dir) else []
    if csv_files:
        file_path = os.path.join(data_dir, csv_files[0])
        st.sidebar.info("ℹ️ 기존 업로드된 데이터를 표시 중입니다.")
    else:
        file_path = None

if file_path:
    df = pd.read_csv(file_path)
    
    # 데이터 전처리 (에러 방지용)
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        df = df.dropna(subset=['timestamp'])
        df['date_only'] = df['timestamp'].dt.date
    else:
        # 날짜 컬럼이 없을 경우를 대비한 기본값
        df['date_only'] = pd.Timestamp.now().date()

    df['videoPlayCount'] = pd.to_numeric(df.get('videoPlayCount', 0), errors='coerce').fillna(0)

    # 사이드바 필터
    st.sidebar.header("🔍 필터링 설정")
    korean_only = st.sidebar.checkbox("한국 콘텐츠만 보기 (한글 포함)", value=True)
    
    # 날짜 범위 설정
    min_date, max_date = df['date_only'].min(), df['date_only'].max()
    date_range = st.sidebar.date_input("조회 기간", value=(min_date, max_date))

    # 데이터 필터링 실행
    def filter_data(data):
        # 캡션이 없는 경우 빈 문자열로 처리
        data['caption'] = data['caption'].fillna('')
        # 광고 제거
        data = data[~data['caption'].str.contains('광고|협찬|ad|sponsored|체험단', case=False)]
        if korean_only:
            data = data[data['caption'].str.contains('[가-힣]', regex=True)]
        if isinstance(date_range, tuple) and len(date_range) == 2:
            data = data[(data['date_only'] >= date_range[0]) & (data['date_only'] <= date_range[1])]
        return data

    filtered_df = filter_data(df)

    # ---------------------------------------------------------
    # 📊 상단 요약 통계
    # ---------------------------------------------------------
    st.subheader("📊 핵심 성과 요약 (Weekly Summary)")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("총 수집 콘텐츠", f"{len(filtered_df)}개")
    with col2:
        total_views = filtered_df['videoPlayCount'].sum()
        st.metric("총 누적 조회수", f"{int(total_views):,}회")
    with col3:
        avg_views = filtered_df['videoPlayCount'].mean() if len(filtered_df) > 0 else 0
        st.metric("평균 조회수", f"{int(avg_views):,}회")
    with col4:
        if len(filtered_df) > 0:
            best_account = filtered_df.sort_values(by='videoPlayCount', ascending=False).iloc[0].get('ownerUsername', 'N/A')
        else:
            best_account = "N/A"
        st.info(f"🏆 베스트 계정: @{best_account}")

    st.divider()

    # 5. 탭 구성
    tab1, tab2 = st.tabs(["✨ 메이투 (Meitu)", "📸 뷰티캠 (BeautyCam)"])

    def display_posts_with_keywords(target_df, keywords, brand_name):
        target = target_df[target_df['caption'].str.contains('|'.join(keywords), case=False)]
        
        if not target.empty:
            st.write(f"### 🔠 {brand_name} 주간 핫 키워드 TOP 10")
            all_text = " ".join(target['caption'].tolist())
            words = re.findall(r'[가-힣]{2,}', all_text)
            stop_words = ['있는', '진짜', '너무', '추천', '어플', '사진', '영상', '만들기', '어떻게', '좋아요'] + keywords
            words = [w for w in words if w not in stop_words]
            
            most_common = Counter(words).most_common(10)
            kw_cols = st.columns(10)
            for idx, (word, count) in enumerate(most_common):
                kw_cols[idx].markdown(f"**{word}**\n({count}회)")
            
            st.divider()

            top_posts = target.sort_values(by='videoPlayCount', ascending=False).head(20)
            cols = st.columns(2)
            for i, (idx, row) in enumerate(top_posts.iterrows()):
                with cols[i % 2]:
                    with st.container(border=True):
                        img = row.get('displayUrl', '')
                        if pd.notna(img): st.image(img, use_container_width=True)
                        st.write(f"**아이디:** @{row.get('ownerUsername', 'unknown')} | 📅 {row['date_only']}")
                        st.write(f"🔥 **조회수:** {int(row['videoPlayCount']):,}회")
                        st.link_button("🚀 영상 보기", row.get('url', '#'))
        else:
            st.warning(f"{brand_name} 관련 콘텐츠가 없습니다.")

    with tab1:
        display_posts_with_keywords(filtered_df, ['메이투', 'meitu'], "메이투")
    with tab2:
        display_posts_with_keywords(filtered_df, ['뷰티캠', 'beautycam'], "뷰티캠")

else:
    st.error("데이터 파일(CSV)을 찾을 수 없습니다. Apify 수집을 기다리거나 파일을 업로드해주세요!")
