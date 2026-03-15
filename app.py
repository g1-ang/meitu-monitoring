import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="메이투 모니터링", layout="wide")
st.title("🚀 메이투 즉각 모니터링 자동화")

data_path = './data/latest_monitoring.csv'

if os.path.exists(data_path):
    try:
        df = pd.read_csv(data_path)
        
        # 파일에 'videoPlayCount'가 없으면 'playCount'를 쓰고, 그것도 없으면 0을 씁니다.
        v_col = 'videoPlayCount' if 'videoPlayCount' in df.columns else ('playCount' if 'playCount' in df.columns else None)
        l_col = 'likesCount' if 'likesCount' in df.columns else ('likes' if 'likes' in df.columns else None)

        df['view_count'] = pd.to_numeric(df[v_col] if v_col else 0, errors='coerce').fillna(0).astype(int)
        df['like_count'] = pd.to_numeric(df[l_col] if l_col else 0, errors='coerce').fillna(0).astype(int)
        df['caption'] = df['caption'].fillna('')

        # 요약 표시
        m1, m2, m3 = st.columns(3)
        m1.metric("총 수집", f"{len(df)}개")
        m2.metric("총 조회수", f"{df['view_count'].sum():,}회")
        m3.metric("총 좋아요", f"{df['like_count'].sum():,}개")

        # 탭 구성 및 출력 (브랜드 키워드 필터)
        tab1, tab2 = st.tabs(["✨ 메이투", "📸 뷰티캠"])
        
        def display(brand_kw):
            target = df[df['caption'].str.contains('|'.join(brand_kw), case=False, na=False)]
            reels = target[target['view_count'] > 0].sort_values('view_count', ascending=False).head(10)
            feeds = target[target['view_count'] == 0].sort_values('like_count', ascending=False).head(10)
            
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🎬 인기 릴스")
                for _, r in reels.iterrows():
                    with st.container(border=True):
                        if pd.notna(r.get('displayUrl')): st.image(r['displayUrl'], use_container_width=True)
                        st.write(f"**@{r.get('ownerUsername', 'user')}** | 🔥 {int(r['view_count']):,}")
                        st.link_button("영상 보기", r.get('url', '#'))
            with c2:
                st.subheader("📸 인기 피드")
                for _, r in feeds.iterrows():
                    with st.container(border=True):
                        if pd.notna(r.get('displayUrl')): st.image(r['displayUrl'], use_container_width=True)
                        st.write(f"**@{r.get('ownerUsername', 'user')}** | ❤️ {int(r['like_count']):,}")
                        st.link_button("게시물 보기", r.get('url', '#'))

        with tab1: display(['메이투', 'meitu'])
        with tab2: display(['뷰티캠', 'beautycam'])

    except Exception as e:
        st.error(f"⚠️ 화면 표시 중 오류 발생: {e}")
else:
    st.error("📂 파일을 찾을 수 없습니다. GitHub에서 'Run workflow'를 먼저 실행해 주세요.")
