import streamlit as st
import pandas as pd
import os
import re

# 1. 페이지 설정
st.set_page_config(page_title="메이투 모니터링", layout="wide")
st.title("🚀 메이투 즉각 모니터링 자동화")

# 2. 파일 불러오기
data_path = './data/latest_monitoring.csv'

if os.path.exists(data_path):
    try:
        # 데이터 읽기
        df = pd.read_csv(data_path)
        
        # [에러 해결 핵심] 숫자 변환 방식을 가장 원시적이고 안전하게 변경
        # 이렇게 하면 'int' object has no attribute 'fillna' 에러가 절대 날 수 없습니다.
        df['view_count'] = pd.to_numeric(df.get('videoPlayCount'), errors='coerce').fillna(0).astype(int)
        df['like_count'] = pd.to_numeric(df.get('likesCount'), errors='coerce').fillna(0).astype(int)
        
        # 캡션이 비어있으면 빈 글자로 채우기 (글자에는 fillna 가능)
        df['caption'] = df['caption'].fillna('')

        # 한국 콘텐츠 필터 (사이드바)
        korean_only = st.sidebar.checkbox("한국 콘텐츠만 보기", value=True)
        if korean_only:
            df = df[df['caption'].str.contains('[가-힣]', regex=True)]

        # ---------------------------------------------------------
        # 요약 수치 표시
        # ---------------------------------------------------------
        m1, m2, m3 = st.columns(3)
        m1.metric("총 수집 콘텐츠", f"{len(df)}개")
        m2.metric("총 조회수 (릴스)", f"{df['view_count'].sum():,}회")
        m3.metric("총 좋아요 (피드)", f"{df['like_count'].sum():,}개")

        st.divider()

        # ---------------------------------------------------------
        # 브랜드 탭 (메이투 / 뷰티캠)
        # ---------------------------------------------------------
        tab1, tab2 = st.tabs(["✨ 메이투 (Meitu)", "📸 뷰티캠 (BeautyCam)"])

        def show_grid(brand_kw):
            # 키워드가 포함된 데이터만 필터링
            target = df[df['caption'].str.contains('|'.join(brand_kw), case=False)]
            
            # 릴스(조회수가 있는 것) vs 피드(조회수가 0인 것)
            reels = target[target['view_count'] > 0].sort_values('view_count', ascending=False).head(12)
            feeds = target[target['view_count'] == 0].sort_values('like_count', ascending=False).head(12)

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🎬 인기 릴스")
                if not reels.empty:
                    for _, row in reels.iterrows():
                        with st.container(border=True):
                            img = row.get('displayUrl')
                            if pd.notna(img): st.image(img, use_container_width=True)
                            st.write(f"**@{row.get('ownerUsername', 'user')}**")
                            st.write(f"🔥 조회수: {row['view_count']:,}회")
                            st.link_button("영상 보기", row.get('url', '#'))
                else:
                    st.info("조건에 맞는 릴스가 없습니다.")

            with col2:
                st.subheader("📸 인기 피드")
                if not feeds.empty:
                    for _, row in feeds.iterrows():
                        with st.container(border=True):
                            img = row.get('displayUrl')
                            if pd.notna(img): st.image(img, use_container_width=True)
                            st.write(f"**@{row.get('ownerUsername', 'user')}**")
                            st.write(f"❤️ 좋아요: {row['like_count']:,}개")
                            st.link_button("게시물 보기", row.get('url', '#'))
                else:
                    st.info("조건에 맞는 피드가 없습니다.")

        with tab1: show_grid(['메이투', 'meitu'])
        with tab2: show_grid(['뷰티캠', 'beautycam'])

    except Exception as e:
        # 어떤 에러인지 더 자세히 보여주도록 수정
        st.error(f"⚠️ 데이터 처리 중 오류가 발생했습니다. (내용: {e})")
else:
    st.error("📂 데이터 파일을 찾을 수 없습니다. GitHub에서 데이터 수집이 완료되었는지 확인해 주세요.")
