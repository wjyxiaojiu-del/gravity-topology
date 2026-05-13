"""
引力拓扑 - Streamlit 仪表盘
实时可视化展示
"""

import json
import streamlit as st
import pandas as pd
import networkx as nx
from collections import defaultdict

# 页面配置
st.set_page_config(
    page_title="引力拓扑 - 社区暗网发掘系统",
    page_icon="🌌",
    layout="wide"
)

# 自定义样式
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
    }
    .metric-label {
        font-size: 0.9rem;
        opacity: 0.8;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_data():
    """加载数据"""
    with open('zhihu_data_massive.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data


@st.cache_data
def load_gravity_results():
    """加载引力计算结果"""
    try:
        with open('gravity_results_optimized.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {'hidden_pairs': []}


def main():
    """主函数"""

    # 标题
    st.markdown('<h1 class="main-header">🌌 引力拓扑 - 社区暗网发掘系统</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #666;">基于空间计量与 A2A 机制，发现隐藏的高潜同好</p>', unsafe_allow_html=True)

    # 加载数据
    data = load_data()
    gravity_results = load_gravity_results()

    users = data.get('users', {})
    posts = data.get('posts', [])
    comments = data.get('comments', [])
    hidden_pairs = gravity_results.get('hidden_pairs', [])

    # ============ 核心指标 ============
    st.markdown("---")
    st.subheader("📊 核心指标")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{len(users)}</div>
            <div class="metric-label">用户数量</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{len(posts)}</div>
            <div class="metric-label">帖子数量</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{len(comments)}</div>
            <div class="metric-label">评论数量</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{len(hidden_pairs)}</div>
            <div class="metric-label">隐藏同好对</div>
        </div>
        """, unsafe_allow_html=True)

    # ============ 隐藏同好对 ============
    st.markdown("---")
    st.subheader("🔗 发现的隐藏同好对")

    if hidden_pairs:
        df_pairs = pd.DataFrame(hidden_pairs[:20])
        df_pairs.columns = ['用户A', '用户A名称', '用户B', '用户B名称', '引力值']

        # 格式化引力值
        df_pairs['引力值'] = df_pairs['引力值'].apply(lambda x: f"{x:.4f}")

        st.dataframe(df_pairs, use_container_width=True, height=400)

        # 引力值分布
        st.subheader("📈 引力值分布")
        gravity_values = [p['gravity'] for p in hidden_pairs]
        st.bar_chart(gravity_values[:20])
    else:
        st.info("暂无引力计算结果，请先运行引力计算")

    # ============ 用户活跃度排名 ============
    st.markdown("---")
    st.subheader("🏆 用户活跃度排名")

    # 计算用户活跃度
    user_activity = []
    for token, user in users.items():
        activity = {
            '用户名': user.get('name', token),
            '发帖数': user.get('post_count', 0),
            '评论数': user.get('comment_count', 0),
            '获赞数': user.get('total_likes', 0),
            '内容数': len(user.get('contents', []))
        }
        user_activity.append(activity)

    df_activity = pd.DataFrame(user_activity)
    df_activity['活跃度'] = df_activity['发帖数'] * 3 + df_activity['评论数'] * 2 + df_activity['获赞数']
    df_activity = df_activity.sort_values('活跃度', ascending=False)

    st.dataframe(df_activity.head(20), use_container_width=True)

    # ============ 圈子分布 ============
    st.markdown("---")
    st.subheader("📍 圈子内容分布")

    ring_names = {
        '2001009660925334090': 'OpenClaw 人类观察员',
        '2015023739549529606': 'A2A for Reconnect',
        '2029619126742656657': '黑客松脑洞补给站'
    }

    ring_dist = defaultdict(int)
    for post in posts:
        ring_id = post.get('ring_id', 'unknown')
        ring_dist[ring_names.get(ring_id, ring_id)] += 1

    df_rings = pd.DataFrame(list(ring_dist.items()), columns=['圈子', '帖子数'])
    st.bar_chart(df_rings.set_index('圈子'))

    # ============ 内容样本 ============
    st.markdown("---")
    st.subheader("📝 用户内容样本")

    # 选择用户
    user_names = {token: user.get('name', token) for token, user in users.items() if user.get('contents')}
    selected_user = st.selectbox("选择用户", list(user_names.values()))

    # 找到对应的 token
    selected_token = None
    for token, name in user_names.items():
        if name == selected_user:
            selected_token = token
            break

    if selected_token:
        user = users[selected_token]
        contents = user.get('contents', [])

        st.write(f"**{selected_user}** 的内容 ({len(contents)} 条):")
        for i, content in enumerate(contents[:5], 1):
            st.markdown(f"**{i}.** {content[:200]}{'...' if len(content) > 200 else ''}")

    # ============ 系统说明 ============
    st.markdown("---")
    st.subheader("ℹ️ 系统说明")

    st.markdown("""
    **引力拓扑 (Gravity Topology)** 是一个基于空间计量与 A2A 机制的社区暗网发掘系统。

    ### 核心功能
    1. **数据采集** - 从知乎圈子采集用户互动数据
    2. **引力计算** - 基于 TF-IDF + Cosine Similarity 计算用户相似度
    3. **隐藏同好发现** - 找出特征相似但无现实交互的用户对
    4. **A2A 对话** - 基于 DeepSeek AI 生成 Agent 对话

    ### 技术栈
    - Python + Streamlit
    - NetworkX 社交网络分析
    - DeepSeek AI 大模型
    - 知乎社区 API
    """)


if __name__ == "__main__":
    main()
