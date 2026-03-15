import streamlit as st
import pandas as pd
import os
import re

# 1. 페이지 설정
st.set_page_config(page_title="메이투 마케팅 모니터링", layout="wide")
st.title("🚀 메이투 즉각 모니터링 자동화 시스템")

# 2. 파일 불러오기
data_path = './data/latest_monitoring.csv'

if os.path.exists(data_path):
    try:
        df = pd.read_csv(data_path)
        
        # --- [복구 1] 날짜 데이터 처리 ---
        # timestamp나 last_updated 중 있는 것을 사용합니다.
        time_col = 'timestamp' if 'timestamp' in df.columns else ('last_updated' if 'last_updated' in df.columns else None)
        if time_col:
            df['date_only'] = pd.to_datetime(df[time_col], errors='coerce').dt.date
        else:
            df['date_only'] = pd.Timestamp.now().date()

        # --- 숫자 데이터 안전 변환 ---
        def clean_num(df, col_names):
            found_col = next((c for c in col_names if c in df.columns), None)
            return pd.to_numeric(df[found_col], errors='coerce').fillna(0).astype(int) if found_col else pd.Series([0]*len(df))

        df['view_count'] = clean_num(df, ['videoPlayCount', 'playCount'])
        df['like_count'] = clean_num(df, ['likesCount', 'likes'])
        df['caption'] = df['caption'].fillna('').astype(str)

        # --- [복구 2] 릴스 판별 로직 강화 ---
        # 조회수가 0보다 크거나, 유형이 Video인 경우 릴스로 판단
        df['is_reels'] = (df['view_count'] > 0) | (df.get('type') == 'Video')

        # --- [복구 3] 필터링 기능 (사이드바) ---
        st.sidebar.header("🔍 필터링 설정")
        korean_only = st.sidebar.checkbox("한국 콘텐츠만 보기 (한글 포함)", value=True)
        
        # 날짜 필터
        min_date = df['date_only'].min() if not df.empty else pd.Timestamp.now().date()
        max_date = df['date_only'].max() if not df.empty else pd.Timestamp.now().date()
        date_range = st.sidebar.date_input("조회 기간", value=(min_date, max_date))

        # 필터 적용
        display_df = df.copy()
        if korean_only:
            display_df = display_df[display_df['caption'].str.contains('[가-힣]', regex=True)]
        if isinstance(date_range, tuple) and len(date_range) == 2:
            display_df = display_df[(display_df['date_only'] >= date_range[0]) & (display_df['date_only'] <= date_range[1])]

        # 성과 요약
        m1, m2, m3 = st.columns(3)
        m1.metric("수집 콘텐츠", f"{len(display_df)}개")
        m2.metric("총 조회수", f"{int(display_df['view_count'].sum()):,}회")
        m3.metric("총 좋아요", f"{int(display_df['like_count'].sum()):,}개")

        st.divider()

        # --- 브랜드 탭 구성 ---
        tab1, tab2 = st.tabs(["✨ 메이투 (Meitu)", "📸 뷰티캠 (BeautyCam)"])

        def show_grid(brand_kw):
            target = display_df[display_df['caption'].str.contains('|'.join(brand_kw), case=False, na=False)]
            
            # 릴스(동영상)와 피드를 구분하여 정렬
            reels = target[target['is_reels'] == True].sort_values('view_count', ascending=False).head(12)
            feeds = target[target['is_reels'] == False].sort_values('like_count', ascending=False).head(12)

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🎬 인기 릴스 (동영상)")
                for _, r in reels.iterrows():
                    with st.container(border=True):
                        if pd.notna(r.get('displayUrl')): st.image(r['displayUrl'], use_container_width=True)
                        st.caption(f"📅 날짜: {r['date_only']}")
                        st.write(f"**@{r.get('ownerUsername', 'user')}** | 🔥 {int(r['view_count']):,}")
                        st.link_button("영상 보기", r.get('url', '#'))
            with col2:
                st.subheader("📸 인기 피드 (게시글)")
                for _, r in feeds.iterrows():
                    with st.container(border=True):
                        if pd.notna(r.get('displayUrl')): st.image(r['displayUrl'], use_container_width=True)
                        st.caption(f"📅 날짜: {r['date_only']}")
                        st.write(f"**@{r.get('ownerUsername', 'user')}** | ❤️ {int(r['like_count']):,}")
                        st.link_button("게시물 보기", r.get('url', '#'))

        with tab1: show_grid(['메이투', 'meitu'])
        with tab2: show_grid(['뷰티캠', 'beautycam'])

    except Exception as e:
        st.error(f"⚠️ 기능 복구 중 오류 발생: {e}")
else:
    st.error("📂 파일을 찾을 수 없습니다.")
