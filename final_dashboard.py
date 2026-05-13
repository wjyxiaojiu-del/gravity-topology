"""
引力拓扑 - 最终版仪表盘
知乎蓝色主题，简洁清爽
"""

import json
import dash
from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
import networkx as nx
import numpy as np
import pandas as pd

# ============ 加载数据 ============
with open('massive_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

with open('gravity_engine_v2_results.json', 'r', encoding='utf-8') as f:
    gravity_results = json.load(f)

users = data.get('users', {})
posts = data.get('posts', [])
comments = data.get('comments', [])
hidden_pairs = gravity_results.get('hidden_pairs', [])

# ============ 初始化应用 ============
app = dash.Dash(__name__, external_stylesheets=[
    dbc.themes.FLATLY,
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css"
])

# ============ 知乎蓝色主题 ============
ZHIHU_BLUE = '#0066FF'
ZHIHU_LIGHT = '#E8F0FE'
ZHIHU_DARK = '#0052CC'
GRAY_100 = '#F8F9FA'
GRAY_200 = '#E9ECEF'
GRAY_500 = '#6C757D'
GRAY_700 = '#495057'
GRAY_900 = '#212529'
WHITE = '#FFFFFF'


# ============ 辅助函数 ============
def create_metric_card(icon, value, title, color):
    # 格式化数值
    if isinstance(value, (int, float)):
        formatted_value = f"{value:,}"
    else:
        formatted_value = str(value)

    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.Div([
                    html.I(className=f"fas {icon} fa-lg", style={'color': color})
                ], className="d-flex align-items-center justify-content-center",
                   style={'width': '50px', 'height': '50px', 'borderRadius': '12px',
                          'backgroundColor': f"{color}15"}),
                html.Div([
                    html.H3(formatted_value, className="mb-0 fw-bold", style={'color': GRAY_900}),
                    html.Small(title, style={'color': GRAY_500})
                ], className="ms-3")
            ], className="d-flex align-items-center")
        ])
    ], style={'border': 'none', 'borderRadius': '12px', 'boxShadow': '0 2px 8px rgba(0,0,0,0.06)'})


def create_section_card(title, content, icon="fas fa-chart-bar"):
    return dbc.Card([
        dbc.CardHeader([
            html.I(className=f"{icon} me-2", style={'color': ZHIHU_BLUE}),
            html.Span(title, className="fw-semibold", style={'color': GRAY_900})
        ], style={'backgroundColor': WHITE, 'borderBottom': f"2px solid {ZHIHU_LIGHT}"}),
        dbc.CardBody(content)
    ], style={'border': 'none', 'borderRadius': '12px', 'boxShadow': '0 2px 8px rgba(0,0,0,0.06)'})


# ============ 布局 ============
app.layout = html.Div([
    # 导航栏
    dbc.Navbar(
        dbc.Container([
            html.Div([
                html.I(className="fas fa-project-diagram me-2", style={'color': WHITE}),
                html.Span("引力拓扑", className="fw-bold fs-5", style={'color': WHITE}),
                html.Span(" · 社区暗网发掘系统", className="ms-2", style={'color': 'rgba(255,255,255,0.8)'})
            ])
        ], fluid=True),
        color=ZHIHU_BLUE,
        dark=True,
        className="mb-4",
        style={'boxShadow': '0 2px 8px rgba(0,102,255,0.3)'}
    ),

    # 主内容
    dbc.Container([
        # 核心指标
        dbc.Row([
            dbc.Col(create_metric_card("fa-users", len(users), "活跃用户", ZHIHU_BLUE), width=2),
            dbc.Col(create_metric_card("fa-file-alt", len(posts), "帖子数量", "#7C3AED"), width=2),
            dbc.Col(create_metric_card("fa-comments", len(comments), "评论数量", "#059669"), width=2),
            dbc.Col(create_metric_card("fa-link", len(hidden_pairs), "隐藏同好", "#D97706"), width=2),
            dbc.Col(create_metric_card("fa-layer-group", gravity_results.get('clusters', 0), "用户聚类", "#DC2626"), width=2),
            dbc.Col(create_metric_card("fa-chart-line", "5", "特征维度", "#8B5CF6"), width=2),
        ], className="mb-4 g-3"),

        # 第一行：两个图表
        dbc.Row([
            dbc.Col([
                create_section_card(
                    "引力值分布",
                    dcc.Graph(id='gravity-chart', style={'height': '300px'}),
                    "fas fa-chart-bar"
                )
            ], width=6),
            dbc.Col([
                create_section_card(
                    "用户活跃度",
                    dcc.Graph(id='user-chart', style={'height': '300px'}),
                    "fas fa-braille"
                )
            ], width=6),
        ], className="mb-4 g-4"),

        # 第二行：社交网络
        dbc.Row([
            dbc.Col([
                create_section_card(
                    "社交网络图谱",
                    dcc.Graph(id='network-chart', style={'height': '500px'}),
                    "fas fa-project-diagram"
                )
            ], width=12),
        ], className="mb-4 g-4"),

        # 第三行：隐藏同好对 + 领域探索
        dbc.Row([
            dbc.Col([
                create_section_card(
                    "高潜同好匹配",
                    html.Div(id='pairs-table'),
                    "fas fa-trophy"
                )
            ], width=7),
            dbc.Col([
                create_section_card(
                    "兴趣领域探索",
                    html.Div([
                        dcc.Dropdown(
                            id='domain-select',
                            options=[
                                {'label': '🤖 AI/技术', 'value': 'ai_tech'},
                                {'label': '📚 人文/哲学', 'value': 'humanities'},
                                {'label': '🌍 社会/经济', 'value': 'society'},
                                {'label': '💡 生活/情感', 'value': 'life'},
                                {'label': '🎨 创意/艺术', 'value': 'creative'}
                            ],
                            value='ai_tech',
                            style={'marginBottom': '15px'}
                        ),
                        html.Div(id='domain-content')
                    ]),
                    "fas fa-compass"
                )
            ], width=5),
        ], className="mb-4 g-4"),

        # 底部
        html.Div([
            html.Hr(),
            html.P([
                "引力拓扑 (Gravity Topology) · 基于空间计量与 A2A 机制的社区暗网发掘系统"
            ], className="text-center mb-0", style={'color': GRAY_500, 'fontSize': '0.85rem'})
        ], className="mt-4")

    ], fluid=True, className="px-4")

], style={'backgroundColor': GRAY_100, 'minHeight': '100vh'})


# ============ 回调函数 ============

@app.callback(
    Output('gravity-chart', 'figure'),
    Input('gravity-chart', 'id')
)
def update_gravity_chart(_):
    values = [p['gravity'] for p in hidden_pairs]

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=values,
        nbinsx=20,
        marker_color=ZHIHU_BLUE,
        opacity=0.85,
        marker_line=dict(width=0)
    ))

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=40, r=20, t=10, b=40),
        xaxis=dict(gridcolor=GRAY_200, zerolinecolor=GRAY_200, title="引力值"),
        yaxis=dict(gridcolor=GRAY_200, zerolinecolor=GRAY_200, title="数量"),
        bargap=0.1
    )

    return fig


@app.callback(
    Output('user-chart', 'figure'),
    Input('user-chart', 'id')
)
def update_user_chart(_):
    user_data = []
    for token, user in users.items():
        if len(user.get('contents', [])) >= 3:
            user_data.append({
                'name': user.get('name', token)[:8],
                '发帖数': user.get('post_count', 0),
                '评论数': user.get('comment_count', 0),
                '内容数': len(user.get('contents', []))
            })

    df = pd.DataFrame(user_data)

    fig = px.scatter(df, x='发帖数', y='评论数', size='内容数',
                     hover_name='name', color='内容数',
                     color_continuous_scale=[ZHIHU_LIGHT, ZHIHU_BLUE])

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=40, r=20, t=10, b=40),
        xaxis=dict(gridcolor=GRAY_200, zerolinecolor=GRAY_200),
        yaxis=dict(gridcolor=GRAY_200, zerolinecolor=GRAY_200),
        coloraxis_colorbar=dict(title="内容数")
    )

    return fig


@app.callback(
    Output('network-chart', 'figure'),
    Input('network-chart', 'id')
)
def update_network_chart(_):
    G = nx.Graph()

    active_users = {t: u for t, u in users.items() if len(u.get('contents', [])) >= 3}
    for token, user in active_users.items():
        G.add_node(token, name=user.get('name', token)[:8], size=len(user.get('contents', [])))

    for pair in hidden_pairs[:35]:
        if pair['user_a'] in G and pair['user_b'] in G:
            G.add_edge(pair['user_a'], pair['user_b'], weight=pair['gravity'])

    pos = nx.spring_layout(G, k=2, iterations=60, seed=42)

    # 边
    edge_x, edge_y = [], []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    # 节点
    node_x, node_y, node_text, node_size, node_color = [], [], [], [], []
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_text.append(G.nodes[node]['name'])
        node_size.append(max(12, G.nodes[node]['size'] * 2.5))
        node_color.append(G.degree(node))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode='lines',
                            line=dict(width=1, color=GRAY_200), hoverinfo='none'))
    fig.add_trace(go.Scatter(x=node_x, y=node_y, mode='markers+text',
                            text=node_text, textposition="top center",
                            textfont=dict(size=9, color=GRAY_700),
                            marker=dict(size=node_size, color=node_color,
                                       colorscale=[[0, ZHIHU_LIGHT], [1, ZHIHU_BLUE]],
                                       line=dict(width=2, color=WHITE))))

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=20, r=20, t=20, b=20)
    )

    return fig


@app.callback(
    Output('pairs-table', 'children'),
    Input('pairs-table', 'id')
)
def update_pairs_table(_):
    rows = []
    for i, pair in enumerate(hidden_pairs[:15], 1):
        # 匹配理由
        reasons = pair.get('match_reasons', [])[:2]
        reason_text = ", ".join(reasons) if reasons else "综合相似"

        rows.append(
            html.Tr([
                html.Td(i, style={'color': GRAY_500, 'fontWeight': '600', 'width': '40px'}),
                html.Td([
                    html.Span(pair['user_a_name'], style={'color': GRAY_900, 'fontWeight': '500'}),
                    html.Span(" ↔ ", style={'color': GRAY_500}),
                    html.Span(pair['user_b_name'], style={'color': GRAY_900, 'fontWeight': '500'})
                ]),
                html.Td(
                    html.Span(f"{pair['gravity']:.2f}",
                             style={'color': ZHIHU_BLUE, 'fontWeight': '600'}),
                    style={'textAlign': 'right'}
                ),
                html.Td(
                    html.Small(reason_text, style={'color': GRAY_500}),
                    style={'textAlign': 'right'}
                )
            ], style={'borderBottom': f"1px solid {GRAY_200}"})
        )

    return dbc.Table([
        html.Thead(html.Tr([
            html.Th("#", style={'color': GRAY_500, 'fontWeight': '600', 'border': 'none'}),
            html.Th("用户对", style={'color': GRAY_500, 'fontWeight': '600', 'border': 'none'}),
            html.Th("引力", style={'color': GRAY_500, 'fontWeight': '600', 'border': 'none', 'textAlign': 'right'}),
            html.Th("理由", style={'color': GRAY_500, 'fontWeight': '600', 'border': 'none', 'textAlign': 'right'}),
        ], style={'backgroundColor': GRAY_100})),
        html.Tbody(rows)
    ], bordered=False, hover=True, responsive=True, style={'marginBottom': '0'})


@app.callback(
    Output('domain-content', 'children'),
    Input('domain-select', 'value')
)
def update_domain_content(domain_id):
    if not domain_id:
        return html.P("请选择领域", style={'color': GRAY_500})

    from interest_explorer import InterestExplorer
    explorer = InterestExplorer('massive_data.json')
    experts = explorer.find_domain_experts(domain_id, top_n=5)

    if not experts:
        return html.P("暂无数据", style={'color': GRAY_500})

    domain_info = explorer.DOMAINS.get(domain_id, {})
    domain_name = domain_info.get('name', domain_id)

    items = []
    for i, expert in enumerate(experts, 1):
        # 获取专家近期内容
        contents = explorer.get_expert_daily_content(expert['token'])
        recent = contents[0]['content'][:40] + '...' if contents else ''

        items.append(
            html.Div([
                html.Div([
                    html.Span(i, className="fw-bold me-2", style={'color': ZHIHU_BLUE}),
                    html.Span(expert['name'], className="fw-semibold", style={'color': GRAY_900}),
                    html.Span(f" · {expert['domain_score']:.0%}", style={'color': ZHIHU_BLUE, 'fontSize': '0.85rem'})
                ]),
                html.Small(recent, style={'color': GRAY_500}) if recent else None
            ], className="py-2", style={'borderBottom': f"1px solid {GRAY_200}"})
        )

    return html.Div([
        html.H6(f"{domain_info.get('emoji', '')} {domain_name} 领域达人",
                style={'color': GRAY_900, 'marginBottom': '10px'}),
        html.Div(items)
    ])


# ============ 运行 ============
if __name__ == '__main__':
    app.run(debug=False, port=8050, host='0.0.0.0')
