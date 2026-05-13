"""
引力拓扑 - 终极专业仪表盘
使用现代化设计，暗色主题，动画效果
"""

import json
import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
import networkx as nx
import numpy as np
import pandas as pd
from datetime import datetime

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
    dbc.themes.CYBORG,
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css"
])

# ============ 自定义样式 ============
COLORS = {
    'bg_primary': '#0d1117',
    'bg_secondary': '#161b22',
    'bg_card': '#21262d',
    'border': '#30363d',
    'text_primary': '#f0f6fc',
    'text_secondary': '#8b949e',
    'accent_blue': '#58a6ff',
    'accent_purple': '#bc8cff',
    'accent_green': '#3fb950',
    'accent_orange': '#d29922',
    'accent_red': '#f85149',
    'accent_cyan': '#39d2c0',
    'gradient_start': '#667eea',
    'gradient_end': '#764ba2'
}


# ============ 辅助函数 ============
def _create_metric_card(title, value, icon, color, col_class):
    """创建指标卡片"""
    return dbc.Col([
        dbc.Card([
            dbc.CardBody([
                html.Div([
                    html.Div([
                        html.I(className=f"{icon} fa-2x",
                               style={'color': color, 'opacity': '0.8'})
                    ], className="d-flex align-items-center justify-content-center",
                       style={'width': '60px', 'height': '60px', 'borderRadius': '12px',
                              'backgroundColor': f"{color}20"}),
                    html.Div([
                        html.H2(f"{value:,}", className="mb-0 fw-bold",
                                style={'color': COLORS['text_primary'], 'fontSize': '2rem'}),
                        html.P(title, className="mb-0",
                               style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'})
                    ], className="ms-3")
                ], className="d-flex align-items-center")
            ])
        ], style={'backgroundColor': COLORS['bg_card'], 'border': f"1px solid {COLORS['border']}",
                  'borderRadius': '12px'})
    ], className=col_class)


def _create_card(title, icon, content):
    """创建卡片"""
    return dbc.Card([
        dbc.CardHeader([
            html.Div([
                html.I(className=f"{icon} me-2", style={'color': COLORS['accent_blue']}),
                html.Span(title, className="fw-semibold",
                          style={'color': COLORS['text_primary']})
            ])
        ], style={'backgroundColor': COLORS['bg_secondary'], 'borderBottom': f"1px solid {COLORS['border']}"}),
        dbc.CardBody(content, style={'backgroundColor': COLORS['bg_card']})
    ], style={'border': f"1px solid {COLORS['border']}", 'borderRadius': '12px'})


# ============ 布局 ============
app.layout = html.Div([
    # 顶部导航栏
    dbc.Navbar(
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.I(className="fas fa-project-diagram me-2",
                               style={'color': COLORS['accent_cyan']}),
                        html.Span("引力拓扑", className="fw-bold fs-4",
                                  style={'color': COLORS['text_primary']}),
                        html.Span(" Gravity Topology", className="ms-2 fs-6",
                                  style={'color': COLORS['text_secondary']})
                    ])
                ], width="auto"),
            ], align="center", className="g-0"),
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Span("基于空间计量与 A2A 机制的社区暗网发掘系统",
                                  style={'color': COLORS['text_secondary']})
                    ])
                ])
            ], className="ms-4")
        ], fluid=True),
        color=COLORS['bg_secondary'],
        dark=True,
        className="mb-4 border-bottom",
        style={'borderColor': f"{COLORS['border']} !important"}
    ),

    # 主内容区
    dbc.Container([
        # 核心指标卡片
        dbc.Row([
            _create_metric_card("用户数量", len(users), "fas fa-users", COLORS['accent_blue'], "col"),
            _create_metric_card("帖子数量", len(posts), "fas fa-file-alt", COLORS['accent_purple'], "col"),
            _create_metric_card("评论数量", len(comments), "fas fa-comments", COLORS['accent_green'], "col"),
            _create_metric_card("隐藏同好对", len(hidden_pairs), "fas fa-link", COLORS['accent_orange'], "col"),
            _create_metric_card("聚类数", gravity_results.get('clusters', 0), "fas fa-layer-group", COLORS['accent_cyan'], "col"),
        ], className="mb-4 g-3"),

        # 第一行：引力分布 + 用户散点图
        dbc.Row([
            dbc.Col([
                _create_card("引力值分布", "fas fa-chart-bar", dcc.Graph(id='gravity-dist', style={'height': '350px'}))
            ], width=6),
            dbc.Col([
                _create_card("用户活跃度分析", "fas fa-braille", dcc.Graph(id='user-scatter', style={'height': '350px'}))
            ], width=6),
        ], className="mb-4 g-4"),

        # 第二行：社交网络图谱
        dbc.Row([
            dbc.Col([
                _create_card("社交网络图谱", "fas fa-project-diagram",
                            dcc.Graph(id='network-graph', style={'height': '600px'}))
            ], width=12),
        ], className="mb-4 g-4"),

        # 第三行：隐藏同好对表格 + PCA散点图
        dbc.Row([
            dbc.Col([
                _create_card("Top 20 隐藏同好对", "fas fa-trophy",
                            html.Div(id='hidden-pairs-table'))
            ], width=7),
            dbc.Col([
                _create_card("PCA 主成分分析", "fas fa-cube",
                            dcc.Graph(id='pca-scatter', style={'height': '500px'}))
            ], width=5),
        ], className="mb-4 g-4"),

        # 第四行：领域分析
        dbc.Row([
            dbc.Col([
                _create_card("领域专家排行", "fas fa-award",
                            html.Div([
                                dcc.Dropdown(
                                    id='domain-selector',
                                    options=[
                                        {'label': '🤖 AI/技术', 'value': 'ai_tech'},
                                        {'label': '📚 人文/哲学', 'value': 'humanities'},
                                        {'label': '🌍 社会/经济', 'value': 'society'},
                                        {'label': '💡 生活/情感', 'value': 'life'},
                                        {'label': '🎨 创意/艺术', 'value': 'creative'}
                                    ],
                                    value='ai_tech',
                                    style={'backgroundColor': COLORS['bg_card'], 'color': '#000'}
                                ),
                                html.Div(id='domain-experts', className="mt-3")
                            ]))
            ], width=6),
            dbc.Col([
                _create_card("兴趣探索", "fas fa-compass",
                            html.Div([
                                dcc.Dropdown(
                                    id='user-selector',
                                    options=[{'label': user.get('name', token)[:15], 'value': token}
                                            for token, user in users.items()
                                            if len(user.get('contents', [])) >= 5],
                                    placeholder="选择用户探索兴趣变化...",
                                    style={'backgroundColor': COLORS['bg_card'], 'color': '#000'}
                                ),
                                html.Div(id='interest-report', className="mt-3")
                            ]))
            ], width=6),
        ], className="mb-4 g-4"),

        # 底部
        dbc.Row([
            dbc.Col([
                html.Hr(style={'borderColor': COLORS['border']}),
                html.Div([
                    html.P([
                        html.I(className="fas fa-code me-2"),
                        "引力拓扑 (Gravity Topology) | 技术栈: Python + PCA + 空间计量 + DeepSeek AI + Plotly Dash"
                    ], className="text-center mb-0",
                       style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'})
                ])
            ])
        ])

    ], fluid=True, className="px-4")

], style={'backgroundColor': COLORS['bg_primary'], 'minHeight': '100vh', 'fontFamily': "'Segoe UI', sans-serif"})


def _create_metric_card(title, value, icon, color, col_class):
    """创建指标卡片"""
    return dbc.Col([
        dbc.Card([
            dbc.CardBody([
                html.Div([
                    html.Div([
                        html.I(className=f"{icon} fa-2x",
                               style={'color': color, 'opacity': '0.8'})
                    ], className="d-flex align-items-center justify-content-center",
                       style={'width': '60px', 'height': '60px', 'borderRadius': '12px',
                              'backgroundColor': f"{color}20"}),
                    html.Div([
                        html.H2(f"{value:,}", className="mb-0 fw-bold",
                                style={'color': COLORS['text_primary'], 'fontSize': '2rem'}),
                        html.P(title, className="mb-0",
                               style={'color': COLORS['text_secondary'], 'fontSize': '0.85rem'})
                    ], className="ms-3")
                ], className="d-flex align-items-center")
            ])
        ], style={'backgroundColor': COLORS['bg_card'], 'border': f"1px solid {COLORS['border']}",
                  'borderRadius': '12px'})
    ], className=col_class)


def _create_card(title, icon, content):
    """创建卡片"""
    return dbc.Card([
        dbc.CardHeader([
            html.Div([
                html.I(className=f"{icon} me-2", style={'color': COLORS['accent_blue']}),
                html.Span(title, className="fw-semibold",
                          style={'color': COLORS['text_primary']})
            ])
        ], style={'backgroundColor': COLORS['bg_secondary'], 'borderBottom': f"1px solid {COLORS['border']}"}),
        dbc.CardBody(content, style={'backgroundColor': COLORS['bg_card']})
    ], style={'border': f"1px solid {COLORS['border']}", 'borderRadius': '12px'})


# ============ 回调函数 ============

@app.callback(
    Output('gravity-dist', 'figure'),
    Input('gravity-dist', 'id')
)
def update_gravity_dist(_):
    """引力分布图"""
    gravity_values = [p['gravity'] for p in hidden_pairs]

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=gravity_values,
        nbinsx=25,
        marker=dict(
            color=gravity_values,
            colorscale='Viridis',
            line=dict(width=0)
        ),
        opacity=0.9
    ))

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color=COLORS['text_secondary'],
        margin=dict(l=40, r=20, t=20, b=40),
        xaxis=dict(gridcolor=COLORS['border'], zerolinecolor=COLORS['border']),
        yaxis=dict(gridcolor=COLORS['border'], zerolinecolor=COLORS['border']),
        bargap=0.05
    )

    return fig


@app.callback(
    Output('user-scatter', 'figure'),
    Input('user-scatter', 'id')
)
def update_user_scatter(_):
    """用户散点图"""
    user_data = []
    for token, user in users.items():
        if len(user.get('contents', [])) >= 3:
            user_data.append({
                'name': user.get('name', token)[:10],
                '发帖数': user.get('post_count', 0),
                '评论数': user.get('comment_count', 0),
                '内容数': len(user.get('contents', []))
            })

    df = pd.DataFrame(user_data)

    fig = px.scatter(df, x='发帖数', y='评论数', size='内容数',
                     hover_name='name', color='内容数',
                     color_continuous_scale='Plasma',
                     size_max=20)

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color=COLORS['text_secondary'],
        margin=dict(l=40, r=20, t=20, b=40),
        xaxis=dict(gridcolor=COLORS['border'], zerolinecolor=COLORS['border']),
        yaxis=dict(gridcolor=COLORS['border'], zerolinecolor=COLORS['border']),
        coloraxis_colorbar=dict(title="内容数")
    )

    return fig


@app.callback(
    Output('network-graph', 'figure'),
    Input('network-graph', 'id')
)
def update_network_graph(_):
    """社交网络图谱"""
    G = nx.Graph()

    # 添加节点
    active_users = {token: user for token, user in users.items()
                    if len(user.get('contents', [])) >= 3}

    for token, user in active_users.items():
        G.add_node(token, name=user.get('name', token)[:8],
                   size=len(user.get('contents', [])))

    # 添加边
    for pair in hidden_pairs[:40]:
        if pair['user_a'] in G and pair['user_b'] in G:
            G.add_edge(pair['user_a'], pair['user_b'], weight=pair['gravity'])

    # 布局
    pos = nx.spring_layout(G, k=2.5, iterations=80, seed=42)

    # 边
    edge_x, edge_y, edge_colors = [], [], []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])
        # 边颜色基于引力值
        weight = G.edges[edge].get('weight', 0.5)
        edge_colors.extend([weight, weight, None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=1.5, color=edge_colors, colorscale='Viridis'),
        hoverinfo='none', mode='lines',
        opacity=0.6
    )

    # 节点
    node_x, node_y, node_text, node_size, node_color = [], [], [], [], []
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_text.append(G.nodes[node]['name'])
        node_size.append(max(15, G.nodes[node]['size'] * 3))
        # 节点颜色基于度数
        node_color.append(G.degree(node))

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        text=node_text,
        textposition="top center",
        textfont=dict(size=9, color=COLORS['text_primary']),
        hoverinfo='text',
        marker=dict(
            size=node_size,
            color=node_color,
            colorscale='Plasma',
            line=dict(width=2, color='white'),
            opacity=0.9
        )
    )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color=COLORS['text_primary'],
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=20, r=20, t=20, b=20),
        hovermode='closest'
    )

    return fig


@app.callback(
    Output('hidden-pairs-table', 'children'),
    Input('hidden-pairs-table', 'id')
)
def update_hidden_pairs_table(_):
    """隐藏同好对表格"""
    rows = []
    for i, pair in enumerate(hidden_pairs[:20], 1):
        # 匹配理由标签
        reason_badges = []
        for reason in pair.get('match_reasons', [])[:2]:
            reason_badges.append(
                dbc.Badge(reason, color="info", className="me-1",
                         style={'fontSize': '0.7rem'})
            )

        rows.append(
            html.Tr([
                html.Td(f"#{i}", style={'color': COLORS['text_secondary'], 'fontWeight': 'bold'}),
                html.Td(pair['user_a_name'], style={'color': COLORS['text_primary']}),
                html.Td(pair['user_b_name'], style={'color': COLORS['text_primary']}),
                html.Td(f"{pair['gravity']:.3f}",
                        style={'color': COLORS['accent_green'], 'fontWeight': 'bold'}),
                html.Td(
                    dbc.Badge("是" if pair.get('same_cluster') else "否",
                             color="success" if pair.get('same_cluster') else "secondary",
                             style={'fontSize': '0.75rem'})
                ),
                html.Td(reason_badges)
            ], style={'borderBottom': f"1px solid {COLORS['border']}"})
        )

    table = dbc.Table([
        html.Thead(html.Tr([
            html.Th("#", style={'color': COLORS['text_secondary']}),
            html.Th("用户A", style={'color': COLORS['text_secondary']}),
            html.Th("用户B", style={'color': COLORS['text_secondary']}),
            html.Th("引力值", style={'color': COLORS['text_secondary']}),
            html.Th("同簇", style={'color': COLORS['text_secondary']}),
            html.Th("匹配理由", style={'color': COLORS['text_secondary']}),
        ], style={'backgroundColor': COLORS['bg_secondary']})),
        html.Tbody(rows)
    ], bordered=False, hover=True, responsive=True,
       style={'color': COLORS['text_primary'], 'marginBottom': '0'})

    return table


@app.callback(
    Output('pca-scatter', 'figure'),
    Input('pca-scatter', 'id')
)
def update_pca_scatter(_):
    """PCA 散点图"""
    # 模拟 PCA 数据（实际应该从引擎获取）
    np.random.seed(42)
    n_users = len(hidden_pairs) + 10
    pca_data = np.random.randn(n_users, 3)

    fig = go.Figure(data=[go.Scatter3d(
        x=pca_data[:, 0],
        y=pca_data[:, 1],
        z=pca_data[:, 2],
        mode='markers',
        marker=dict(
            size=8,
            color=pca_data[:, 2],
            colorscale='Plasma',
            opacity=0.8,
            line=dict(width=1, color='white')
        ),
        text=[f"User {i}" for i in range(n_users)],
        hoverinfo='text'
    )])

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        font_color=COLORS['text_secondary'],
        margin=dict(l=0, r=0, t=0, b=0),
        scene=dict(
            xaxis=dict(gridcolor=COLORS['border'], zerolinecolor=COLORS['border']),
            yaxis=dict(gridcolor=COLORS['border'], zerolinecolor=COLORS['border']),
            zaxis=dict(gridcolor=COLORS['border'], zerolinecolor=COLORS['border']),
            bgcolor=COLORS['bg_card']
        )
    )

    return fig


@app.callback(
    Output('domain-experts', 'children'),
    Input('domain-selector', 'value')
)
def update_domain_experts(domain_id):
    """领域专家"""
    if not domain_id:
        return html.P("请选择领域", style={'color': COLORS['text_secondary']})

    # 模拟数据
    domain_names = {
        'ai_tech': 'AI/技术',
        'humanities': '人文/哲学',
        'society': '社会/经济',
        'life': '生活/情感',
        'creative': '创意/艺术'
    }

    # 找到该领域的内容最多的用户
    from interest_explorer import InterestExplorer
    explorer = InterestExplorer('massive_data.json')
    experts = explorer.find_domain_experts(domain_id, top_n=5)

    if not experts:
        return html.P("暂无数据", style={'color': COLORS['text_secondary']})

    expert_cards = []
    for i, expert in enumerate(experts, 1):
        expert_cards.append(
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.Div([
                            html.Span(f"#{i}", className="fw-bold fs-5",
                                      style={'color': COLORS['accent_blue']})
                        ], style={'width': '40px'}),
                        html.Div([
                            html.H6(expert['name'], className="mb-1",
                                    style={'color': COLORS['text_primary']}),
                            html.Small(f"专业度: {expert['domain_score']:.1%}",
                                      style={'color': COLORS['accent_green']})
                        ], className="ms-2 flex-grow-1")
                    ], className="d-flex align-items-center")
                ], className="py-2")
            ], style={'backgroundColor': COLORS['bg_secondary'], 'border': f"1px solid {COLORS['border']}",
                     'marginBottom': '8px', 'borderRadius': '8px'})
        )

    return html.Div(expert_cards)


@app.callback(
    Output('interest-report', 'children'),
    Input('user-selector', 'value')
)
def update_interest_report(user_token):
    """兴趣探索报告"""
    if not user_token:
        return html.Div([
            html.I(className="fas fa-search fa-3x mb-3",
                   style={'color': COLORS['text_secondary'], 'opacity': '0.5'}),
            html.P("选择用户探索兴趣变化",
                   style={'color': COLORS['text_secondary']})
        ], className="text-center py-5")

    from interest_explorer import InterestExplorer
    explorer = InterestExplorer('massive_data.json')

    # 检测兴趣变化
    change = explorer.detect_interest_change(user_token)
    if 'error' in change:
        return html.P(change['error'], style={'color': COLORS['accent_red']})

    # 生成报告内容
    domain_changes = change.get('domain_changes', {})
    sorted_domains = sorted(domain_changes.items(),
                           key=lambda x: x[1]['change'], reverse=True)

    report_items = []
    for domain_id, info in sorted_domains[:3]:
        domain_info = explorer.DOMAINS.get(domain_id, {})
        emoji = domain_info.get('emoji', '🔍')
        name = domain_info.get('name', domain_id)
        change_val = info['change']

        color = COLORS['accent_green'] if change_val > 0 else COLORS['accent_red'] if change_val < 0 else COLORS['text_secondary']
        icon = "fa-arrow-up" if change_val > 0 else "fa-arrow-down" if change_val < 0 else "fa-minus"

        report_items.append(
            html.Div([
                html.Div([
                    html.Span(emoji, className="me-2"),
                    html.Span(name, style={'color': COLORS['text_primary']})
                ], className="d-flex align-items-center"),
                html.Div([
                    html.I(className=f"fas {icon} me-1", style={'color': color}),
                    html.Span(f"{change_val:+.2%}", style={'color': color, 'fontWeight': 'bold'})
                ])
            ], className="d-flex justify-content-between align-items-center py-2",
               style={'borderBottom': f"1px solid {COLORS['border']}"})
        )

    # 新兴兴趣
    emerging = change.get('emerging_interests', [])
    if emerging:
        report_items.append(
            html.Div([
                html.H6("新兴兴趣", className="mt-3 mb-2",
                        style={'color': COLORS['accent_cyan']}),
                html.Div([
                    dbc.Badge(
                        f"{explorer.DOMAINS.get(d, {}).get('emoji', '')} {explorer.DOMAINS.get(d, {}).get('name', d)}",
                        color="info", className="me-1"
                    ) for d in emerging[:3]
                ])
            ])
        )

    return html.Div(report_items)


# ============ 运行 ============
if __name__ == '__main__':
    app.run(debug=False, port=8050, host='0.0.0.0')
