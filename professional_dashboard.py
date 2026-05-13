"""
引力拓扑 - 专业级仪表盘
使用 Plotly Dash 构建
"""

import json
import dash
from dash import dcc, html, Input, Output, callback
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
import networkx as nx
import numpy as np
import pandas as pd

# 加载数据
with open('massive_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

with open('gravity_engine_results.json', 'r', encoding='utf-8') as f:
    gravity_results = json.load(f)

users = data.get('users', {})
posts = data.get('posts', [])
comments = data.get('comments', [])
hidden_pairs = gravity_results.get('hidden_pairs', [])

# 初始化兴趣探索引擎
from interest_explorer import InterestExplorer
explorer = InterestExplorer('massive_data.json')

# 初始化 Dash 应用
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])

# 颜色方案
COLORS = {
    'background': '#0a0a0a',
    'card': '#1a1a2e',
    'accent': '#e94560',
    'text': '#ffffff',
    'muted': '#888888',
    'gradient1': '#667eea',
    'gradient2': '#764ba2'
}

# ============ 布局 ============
app.layout = dbc.Container([
    # 标题
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H1("🌌 引力拓扑", className="display-3 fw-bold",
                         style={'background': f'linear-gradient(90deg, {COLORS["gradient1"]}, {COLORS["gradient2"]})',
                                '-webkit-background-clip': 'text',
                                '-webkit-text-fill-color': 'transparent'}),
                html.P("Gravity Topology: 基于空间计量与 A2A 机制的社区暗网发掘系统",
                        className="lead", style={'color': COLORS['muted']}),
            ], className="text-center py-4")
        ])
    ]),

    # 核心指标卡片
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H2(f"{len(users)}", className="text-center fw-bold",
                             style={'color': COLORS['gradient1'], 'fontSize': '3rem'}),
                    html.P("用户数量", className="text-center", style={'color': COLORS['muted']})
                ])
            ], style={'backgroundColor': COLORS['card'], 'border': 'none', 'borderRadius': '15px'})
        ], width=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H2(f"{len(posts)}", className="text-center fw-bold",
                             style={'color': COLORS['accent'], 'fontSize': '3rem'}),
                    html.P("帖子数量", className="text-center", style={'color': COLORS['muted']})
                ])
            ], style={'backgroundColor': COLORS['card'], 'border': 'none', 'borderRadius': '15px'})
        ], width=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H2(f"{len(comments)}", className="text-center fw-bold",
                             style={'color': '#00d9ff', 'fontSize': '3rem'}),
                    html.P("评论数量", className="text-center", style={'color': COLORS['muted']})
                ])
            ], style={'backgroundColor': COLORS['card'], 'border': 'none', 'borderRadius': '15px'})
        ], width=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H2(f"{len(hidden_pairs)}", className="text-center fw-bold",
                             style={'color': '#ffd700', 'fontSize': '3rem'}),
                    html.P("隐藏同好对", className="text-center", style={'color': COLORS['muted']})
                ])
            ], style={'backgroundColor': COLORS['card'], 'border': 'none', 'borderRadius': '15px'})
        ], width=3),
    ], className="mb-4"),

    # 图表行1
    dbc.Row([
        # 引力值分布
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("📊 引力值分布", style={'color': COLORS['text'], 'backgroundColor': COLORS['card']}),
                dbc.CardBody([
                    dcc.Graph(id='gravity-distribution')
                ])
            ], style={'backgroundColor': COLORS['card'], 'border': 'none', 'borderRadius': '15px'})
        ], width=6),

        # 用户活跃度散点图
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("🎯 用户活跃度 vs 影响力", style={'color': COLORS['text'], 'backgroundColor': COLORS['card']}),
                dbc.CardBody([
                    dcc.Graph(id='user-scatter')
                ])
            ], style={'backgroundColor': COLORS['card'], 'border': 'none', 'borderRadius': '15px'})
        ], width=6),
    ], className="mb-4"),

    # 社交网络图谱
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("🔗 社交网络图谱", style={'color': COLORS['text'], 'backgroundColor': COLORS['card']}),
                dbc.CardBody([
                    dcc.Graph(id='network-graph', style={'height': '600px'})
                ])
            ], style={'backgroundColor': COLORS['card'], 'border': 'none', 'borderRadius': '15px'})
        ], width=12),
    ], className="mb-4"),

    # 隐藏同好对表格
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("🏆 Top 20 隐藏同好对", style={'color': COLORS['text'], 'backgroundColor': COLORS['card']}),
                dbc.CardBody([
                    html.Div(id='hidden-pairs-table')
                ])
            ], style={'backgroundColor': COLORS['card'], 'border': 'none', 'borderRadius': '15px'})
        ], width=12),
    ], className="mb-4"),

    # PCA 分析
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("🔬 PCA 主成分分析", style={'color': COLORS['text'], 'backgroundColor': COLORS['card']}),
                dbc.CardBody([
                    dcc.Graph(id='pca-scatter')
                ])
            ], style={'backgroundColor': COLORS['card'], 'border': 'none', 'borderRadius': '15px'})
        ], width=6),

        # 圈子分布
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("📍 圈子内容分布", style={'color': COLORS['text'], 'backgroundColor': COLORS['card']}),
                dbc.CardBody([
                    dcc.Graph(id='ring-distribution')
                ])
            ], style={'backgroundColor': COLORS['card'], 'border': 'none', 'borderRadius': '15px'})
        ], width=6),
    ], className="mb-4"),

    # 兴趣探索功能
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("🔍 跨领域兴趣探索", style={'color': COLORS['text'], 'backgroundColor': COLORS['card']}),
                dbc.CardBody([
                    html.P("选择用户，探索其兴趣变化和新兴领域",
                           style={'color': COLORS['muted'], 'marginBottom': '15px'}),

                    # 用户选择
                    dbc.Row([
                        dbc.Col([
                            dcc.Dropdown(
                                id='user-selector',
                                options=[{'label': user.get('name', token), 'value': token}
                                        for token, user in users.items()
                                        if len(user.get('contents', [])) >= 5],
                                placeholder="选择用户...",
                                style={'backgroundColor': '#2a2a3e', 'color': '#000'}
                            )
                        ], width=6),
                        dbc.Col([
                            dbc.Button("生成探索报告", id='explore-button', color="primary",
                                       style={'width': '100%'})
                        ], width=6),
                    ], className="mb-3"),

                    # 探索报告
                    html.Div(id='exploration-report')
                ])
            ], style={'backgroundColor': COLORS['card'], 'border': 'none', 'borderRadius': '15px'})
        ], width=12),
    ], className="mb-4"),

    # 领域专家
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("🏆 领域达人排行", style={'color': COLORS['text'], 'backgroundColor': COLORS['card']}),
                dbc.CardBody([
                    # 领域选择
                    dcc.Dropdown(
                        id='domain-selector',
                        options=[
                            {'label': '🤖 AI/技术', 'value': 'ai_tech'},
                            {'label': '📚 人文/哲学', 'value': 'humanities'},
                            {'label': '🌍 社会/经济', 'value': 'society'},
                            {'label': '💡 生活/情感', 'value': 'life'},
                            {'label': '🎨 创意/艺术', 'value': 'creative'}
                        ],
                        placeholder="选择领域...",
                        style={'backgroundColor': '#2a2a3e', 'color': '#000', 'marginBottom': '15px'}
                    ),
                    html.Div(id='domain-experts')
                ])
            ], style={'backgroundColor': COLORS['card'], 'border': 'none', 'borderRadius': '15px'})
        ], width=12),
    ], className="mb-4"),

    # 底部说明
    dbc.Row([
        dbc.Col([
            html.Div([
                html.Hr(style={'borderColor': COLORS['muted']}),
                html.P("引力拓扑 (Gravity Topology) | 基于空间计量与 A2A 机制的社区暗网发掘系统",
                        className="text-center", style={'color': COLORS['muted']}),
                html.P("技术栈: Python + PCA + 空间权重矩阵 + DeepSeek AI + Plotly Dash",
                        className="text-center", style={'color': COLORS['muted'], 'fontSize': '0.8rem'}),
            ])
        ])
    ])

], fluid=True, style={'backgroundColor': COLORS['background'], 'minHeight': '100vh', 'padding': '20px'})


# ============ 回调函数 ============

@app.callback(
    Output('gravity-distribution', 'figure'),
    Input('gravity-distribution', 'id')
)
def update_gravity_distribution(_):
    """引力值分布图"""
    gravity_values = [p['gravity'] for p in hidden_pairs]

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=gravity_values,
        nbinsx=30,
        marker_color=COLORS['gradient1'],
        opacity=0.8
    ))

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color=COLORS['text'],
        xaxis_title="引力值",
        yaxis_title="数量",
        margin=dict(l=40, r=20, t=20, b=40)
    )

    return fig


@app.callback(
    Output('user-scatter', 'figure'),
    Input('user-scatter', 'id')
)
def update_user_scatter(_):
    """用户活跃度散点图"""
    user_data = []
    for token, user in users.items():
        if len(user.get('contents', [])) >= 3:
            user_data.append({
                'name': user.get('name', token)[:10],
                '发帖数': user.get('post_count', 0),
                '获赞数': user.get('total_likes', 0),
                '内容数': len(user.get('contents', []))
            })

    df = pd.DataFrame(user_data)

    fig = px.scatter(df, x='发帖数', y='获赞数', size='内容数',
                     hover_name='name', color='内容数',
                     color_continuous_scale='Viridis')

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color=COLORS['text'],
        margin=dict(l=40, r=20, t=20, b=40)
    )

    return fig


@app.callback(
    Output('network-graph', 'figure'),
    Input('network-graph', 'id')
)
def update_network_graph(_):
    """社交网络图谱"""
    G = nx.Graph()

    # 添加节点（只添加有内容的用户）
    active_users = {token: user for token, user in users.items()
                    if len(user.get('contents', [])) >= 3}

    for token, user in active_users.items():
        G.add_node(token, name=user.get('name', token)[:8],
                   size=len(user.get('contents', [])))

    # 添加边（基于引力）
    for pair in hidden_pairs[:50]:  # 只显示前50对
        if pair['user_a'] in G and pair['user_b'] in G:
            G.add_edge(pair['user_a'], pair['user_b'], weight=pair['gravity'])

    # 布局
    pos = nx.spring_layout(G, k=2, iterations=50, seed=42)

    # 边
    edge_x, edge_y = [], []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(x=edge_x, y=edge_y, line=dict(width=0.5, color='#888'),
                            hoverinfo='none', mode='lines')

    # 节点
    node_x, node_y, node_text, node_size = [], [], [], []
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_text.append(G.nodes[node]['name'])
        node_size.append(max(10, G.nodes[node]['size'] * 2))

    node_trace = go.Scatter(x=node_x, y=node_y, mode='markers+text',
                            text=node_text, textposition="top center",
                            textfont=dict(size=8, color=COLORS['text']),
                            hoverinfo='text', marker=dict(size=node_size, color=COLORS['accent']))

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color=COLORS['text'],
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=20, r=20, t=20, b=20)
    )

    return fig


@app.callback(
    Output('hidden-pairs-table', 'figure'),
    Input('hidden-pairs-table', 'id')
)
def update_hidden_pairs_table(_):
    """隐藏同好对表格"""
    table_data = []
    for i, pair in enumerate(hidden_pairs[:20], 1):
        table_data.append([
            i,
            pair['user_a_name'],
            pair['user_b_name'],
            f"{pair['gravity']:.4f}",
            f"{pair['feature_sim']:.4f}",
            "无"
        ])

    fig = go.Figure(data=[go.Table(
        header=dict(values=['排名', '用户A', '用户B', '引力值', '特征相似度', '现实交互'],
                    fill_color=COLORS['gradient1'],
                    font=dict(color='white', size=12),
                    align='center'),
        cells=dict(values=list(zip(*table_data)),
                   fill_color=COLORS['card'],
                   font=dict(color=COLORS['text'], size=11),
                   align='center')
    )])

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=20, b=20)
    )

    return fig


@app.callback(
    Output('pca-scatter', 'figure'),
    Input('pca-scatter', 'id')
)
def update_pca_scatter(_):
    """PCA 散点图"""
    # 这里需要实际的 PCA 数据，暂时用模拟
    fig = go.Figure()
    fig.add_annotation(text="PCA 3D 散点图<br>需要运行 gravity_engine.py 生成数据",
                       xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                       font=dict(size=16, color=COLORS['muted']))

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color=COLORS['text'],
        margin=dict(l=40, r=20, t=20, b=40)
    )

    return fig


@app.callback(
    Output('ring-distribution', 'figure'),
    Input('ring-distribution', 'id')
)
def update_ring_distribution(_):
    """圈子分布图"""
    ring_names = {
        '2001009660925334090': 'OpenClaw 人类观察员',
        '2015023739549529606': 'A2A for Reconnect',
        '2029619126742656657': '黑客松脑洞补给站'
    }

    from collections import defaultdict
    ring_dist = defaultdict(int)
    for post in posts:
        ring_id = post.get('ring_id', 'unknown')
        ring_dist[ring_names.get(ring_id, ring_id)] += 1

    fig = go.Figure(data=[go.Pie(
        labels=list(ring_dist.keys()),
        values=list(ring_dist.values()),
        hole=0.4,
        marker=dict(colors=[COLORS['gradient1'], COLORS['accent'], '#00d9ff'])
    )])

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        font_color=COLORS['text'],
        margin=dict(l=40, r=20, t=20, b=40)
    )

    return fig


# ============ 兴趣探索回调 ============

@app.callback(
    Output('exploration-report', 'children'),
    Input('explore-button', 'n_clicks'),
    Input('user-selector', 'value'),
    prevent_initial_call=True
)
def update_exploration_report(n_clicks, user_token):
    """生成兴趣探索报告"""
    if not user_token:
        return html.P("请选择用户", style={'color': COLORS['muted']})

    # 生成报告
    report = explorer.generate_exploration_report(user_token)

    # 解析报告并格式化
    lines = report.split('\n')
    formatted_lines = []
    for line in lines:
        if line.startswith('■'):
            formatted_lines.append(html.H5(line, style={'color': COLORS['accent'], 'marginTop': '15px'}))
        elif line.startswith('  •'):
            formatted_lines.append(html.Li(line[4:], style={'color': COLORS['text']}))
        elif line.startswith('  '):
            formatted_lines.append(html.P(line, style={'color': COLORS['muted'], 'marginBottom': '5px'}))
        else:
            formatted_lines.append(html.P(line, style={'color': COLORS['text']}))

    return html.Div(formatted_lines)


@app.callback(
    Output('domain-experts', 'children'),
    Input('domain-selector', 'value'),
    prevent_initial_call=True
)
def update_domain_experts(domain_id):
    """更新领域专家列表"""
    if not domain_id:
        return html.P("请选择领域", style={'color': COLORS['muted']})

    experts = explorer.find_domain_experts(domain_id, top_n=10)

    if not experts:
        return html.P("该领域暂无专家", style={'color': COLORS['muted']})

    domain_info = explorer.DOMAINS.get(domain_id, {})
    domain_name = domain_info.get('name', domain_id)

    # 生成专家列表
    expert_list = []
    for i, expert in enumerate(experts, 1):
        # 获取专家近期内容
        contents = explorer.get_expert_daily_content(expert['token'])
        recent_content = contents[0]['content'][:60] + '...' if contents else '暂无内容'

        expert_list.append(
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.H5(f"#{i} {expert['name']}", style={'color': COLORS['text']}),
                            html.P(f"专业度: {expert['domain_score']:.2%}",
                                   style={'color': COLORS['accent']}),
                        ], width=3),
                        dbc.Col([
                            html.P(f"发帖: {expert['post_count']} | 评论: {expert['comment_count']}",
                                   style={'color': COLORS['muted']}),
                        ], width=3),
                        dbc.Col([
                            html.P(f"近期关注: {recent_content}",
                                   style={'color': COLORS['text'], 'fontSize': '0.9rem'}),
                        ], width=6),
                    ])
                ])
            ], style={'backgroundColor': '#2a2a3e', 'marginBottom': '10px', 'borderRadius': '10px'})
        )

    return html.Div([
        html.H5(f"{domain_info.get('emoji', '')} {domain_name} 领域达人",
                style={'color': COLORS['text'], 'marginBottom': '15px'}),
        html.Div(expert_list)
    ])


# ============ 运行 ============
if __name__ == '__main__':
    app.run(debug=True, port=8050)
