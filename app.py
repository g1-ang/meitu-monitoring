import streamlit as st
import pandas as pd
import os
import numpy as np

# 1. 페이지 설정
st.set_page_config(page_title="메이투 모니터링", layout="wide")
st.title("🚀 메이투 즉각 모니터링 자동화")

# 2. 파일 불러오기
data_path = './data/latest_monitoring.csv'

if os.path.exists(data_path):
    try:
        # 데이터 읽기
        df = pd.read_csv(data_path)
        
        # [에러 해결 핵심] 어떤 형식이든 강제로 숫자로 바꾸고 비어있으면 0으로 채움
        def force_numeric(series):
            # 숫자로 변환 (실패하면 NaN)
            nums = pd.to_numeric(series, errors='coerce')
            # NaN을 0으로 바꾸고 정수로 변환
            return nums.replace(np.nan, 0).astype(int)

        # 파일에 있는 컬럼명에 맞춰 안전하게 가져오기
        v_col = 'videoPlayCount' if 'videoPlayCount' in df.columns else ('playCount' if 'playCount' in df.columns else None)
        l_col = 'likesCount' if 'likesCount' in df.columns else ('likes' if 'likes' in df.columns else None)

        df['view_count'] = force_numeric(df[v_col] if v_col else 0)
        df['like_count'] = force_numeric(df[l_col] if l_col else 0)
        df['caption'] = df['caption'].fillna('').astype(str)

        # 요약 표시
        m1, m2, m3 = st.columns(3)
        m1.metric("총 수집", f"{len(df)}개")
        m2.metric("총 조회수", f"{int(df['view_count'].sum()):,}회")
        m3.metric("총 좋아요", f"{int(df['like_count'].sum()):,}개")

        st.divider()

        # 브랜드 탭 구성
        tab1, tab2 = st.tabs(["✨ 메이투", "📸 뷰티캠"])
        
        def display(brand_kw):
            target = df[df['caption'].str.contains('|'.join(brand_kw), case=False, na=False)]
            
            # 릴스 vs 피드 분류
            reels = target[target['view_count'] > 0].sort_values('view_count', ascending=False).head(12)
            feeds = target[target['view_count'] == 0].sort_values('like_count', ascending=False).head(12)
            
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🎬 인기 릴스")
                for _, r in reels.iterrows():
                    with st.container(border=True):
                        img = r.get('displayUrl')
                        if pd.notna(img) and str(img).startswith('http'): 
                            st.image(img, use_container_width=True)
                        st.write(f"**@{r.get('ownerUsername', 'user')}** | 🔥 {int(r['view_count']):,}")
                        st.link_button("영상 보기", r.get('url', '#'))
            with c2:
                st.subheader("📸 인기 피드")
                for _, r in feeds.iterrows():
                    with st.container(border=True):
                        img = r.get('displayUrl')
                        if pd.notna(img) and str(img).startswith('http'): 
                            st.image(img, use_container_width=True)
                        st.write(f"**@{r.get('ownerUsername', 'user')}** | ❤️ {int(r['like_count']):,}")
                        st.link_button("게시물 보기", r.get('url', '#'))

        with tab1: display(['메이투', 'meitu'])
        with tab2: display(['뷰티캠', 'beautycam'])

    except Exception as e:
        st.error(f"⚠️ 데이터 처리 중 오류 발생: {e}")
else:
    st.error("📂 파일을 찾을 수 없습니다. GitHub에서 'Run workflow'를 먼저 실행해 주세요.")
