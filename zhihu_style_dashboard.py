"""
引力拓扑 - 知乎风格仪表盘
明亮、欢快、清爽
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
    dbc.themes.BOOTSTRAP,
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css"
])

# 自定义蓝色主题 CSS
app.index_string = '''
<!DOCTYPE html>
<html>
<head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <style>
        .Select-control { border-color: #E8F0FE !important; }
        .Select.is-focused .Select-control { border-color: #0066FF !important; box-shadow: 0 0 0 1px #0066FF !important; }
        .Select-menu-outer { border-color: #E8F0FE !important; }
        .Select-option.is-focused { background-color: #E8F0FE !important; }
        .Select-value-label { color: #1A1A1A !important; }
        .Select-placeholder { color: #999999 !important; }
        .dash-dropdown .Select-control { border-radius: 8px !important; }
        .card { transition: box-shadow 0.2s ease; }
        .card:hover { box-shadow: 0 4px 12px rgba(0,102,255,0.12) !important; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-thumb { background: #E8F0FE; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #0066FF; }
    </style>
</head>
<body>
    {%app_entry%}
    <footer>
        {%config%}
        {%scripts%}
        {%renderer%}
    </footer>
</body>
</html>
'''

# ============ 知乎明亮风格配色 ============
# 主色调
ZHIHU_BLUE = '#0066FF'
ZHIHU_BLUE_LIGHT = '#E8F0FE'
ZHIHU_BLUE_DARK = '#0052CC'

# 背景色
BG_WHITE = '#FFFFFF'
BG_GRAY = '#F6F6F6'
BG_LIGHT = '#FAFAFA'

# 文字色
TEXT_PRIMARY = '#1A1A1A'
TEXT_SECONDARY = '#666666'
TEXT_MUTED = '#999999'

# 强调色
SUCCESS = '#00C853'
WARNING = '#FF9800'
DANGER = '#FF5252'
INFO = '#2196F3'
PURPLE = '#9C27B0'
CYAN = '#00BCD4'

# 卡片样式
CARD_STYLE = {
    'backgroundColor': BG_WHITE,
    'border': 'none',
    'borderRadius': '12px',
    'boxShadow': '0 1px 3px rgba(0,0,0,0.08)',
    'overflow': 'hidden'
}

CARD_HEADER_STYLE = {
    'backgroundColor': BG_WHITE,
    'borderBottom': f'2px solid {ZHIHU_BLUE_LIGHT}',
    'padding': '16px 20px'
}

CARD_BODY_STYLE = {
    'padding': '20px'
}


# ============ 辅助函数 ============
def create_metric_card(icon, value, title, color, bg_color):
    """创建指标卡片"""
    if isinstance(value, (int, float)):
        formatted = f"{value:,}"
    else:
        formatted = str(value)

    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.Div([
                    html.I(className=f"fas {icon}",
                           style={'color': color, 'fontSize': '24px'})
                ], style={
                    'width': '56px', 'height': '56px',
                    'borderRadius': '16px',
                    'backgroundColor': bg_color,
                    'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center'
                }),
                html.Div([
                    html.H3(formatted, className="mb-0",
                            style={'color': TEXT_PRIMARY, 'fontWeight': '700', 'fontSize': '28px'}),
                    html.Span(title, style={'color': TEXT_SECONDARY, 'fontSize': '14px'})
                ], className="ms-3")
            ], className="d-flex align-items-center")
        ], style={'padding': '20px'})
    ], style=CARD_STYLE)


def create_section(title, content, icon="fas fa-chart-bar", extra=None):
    """创建区块"""
    header_content = [
        html.Div([
            html.I(className=f"{icon} me-2", style={'color': ZHIHU_BLUE}),
            html.Span(title, style={'color': TEXT_PRIMARY, 'fontWeight': '600', 'fontSize': '16px'})
        ])
    ]

    if extra:
        header_content.append(extra)

    return dbc.Card([
        dbc.CardHeader(header_content, style={
            **CARD_HEADER_STYLE,
            'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center'
        }),
        dbc.CardBody(content, style=CARD_BODY_STYLE)
    ], style=CARD_STYLE)


# ============ 布局 ============
app.layout = html.Div([
    # 顶部导航
    html.Nav([
        html.Div([
            html.Div([
                html.I(className="fas fa-project-diagram me-2", style={'color': ZHIHU_BLUE, 'fontSize': '20px'}),
                html.Span("引力拓扑", style={
                    'color': TEXT_PRIMARY, 'fontWeight': '700', 'fontSize': '20px'
                }),
                html.Span(" · Gravity Topology", style={
                    'color': ZHIHU_BLUE, 'fontSize': '14px', 'marginLeft': '8px'
                })
            ], className="d-flex align-items-center"),
            html.Div([
                html.Span("基于空间计量与 A2A 机制的社区暗网发掘系统",
                          style={'color': TEXT_SECONDARY, 'fontSize': '14px'})
            ])
        ], className="d-flex justify-content-between align-items-center",
           style={'maxWidth': '1400px', 'margin': '0 auto', 'padding': '16px 24px'})
    ], style={
        'backgroundColor': BG_WHITE,
        'borderBottom': f'3px solid {ZHIHU_BLUE}',
        'boxShadow': '0 1px 3px rgba(0,0,0,0.05)'
    }),

    # 主内容
    html.Div([
        # 指标卡片行
        html.Div([
            dbc.Row([
                dbc.Col(create_metric_card("fa-users", len(users), "活跃用户", ZHIHU_BLUE, ZHIHU_BLUE_LIGHT), width=True),
                dbc.Col(create_metric_card("fa-file-alt", len(posts), "帖子数量", ZHIHU_BLUE, ZHIHU_BLUE_LIGHT), width=True),
                dbc.Col(create_metric_card("fa-comments", len(comments), "评论数量", ZHIHU_BLUE, ZHIHU_BLUE_LIGHT), width=True),
                dbc.Col(create_metric_card("fa-link", len(hidden_pairs), "隐藏同好", ZHIHU_BLUE, ZHIHU_BLUE_LIGHT), width=True),
                dbc.Col(create_metric_card("fa-layer-group", gravity_results.get('clusters', 0), "用户聚类", ZHIHU_BLUE, ZHIHU_BLUE_LIGHT), width=True),
            ], className="g-4")
        ], className="mb-4"),

        # 图表行
        dbc.Row([
            dbc.Col([
                create_section(
                    "引力值分布",
                    dcc.Graph(id='gravity-chart', style={'height': '320px'}),
                    "fas fa-chart-bar"
                )
            ], width=6),
            dbc.Col([
                create_section(
                    "用户活跃度",
                    dcc.Graph(id='user-chart', style={'height': '320px'}),
                    "fas fa-braille"
                )
            ], width=6),
        ], className="mb-4 g-4"),

        # 网络图谱
        dbc.Row([
            dbc.Col([
                create_section(
                    "社交网络图谱",
                    dcc.Graph(id='network-chart', style={'height': '520px'}),
                    "fas fa-project-diagram"
                )
            ], width=12),
        ], className="mb-4 g-4"),

        # 同好对 + 领域探索
        dbc.Row([
            dbc.Col([
                create_section(
                    "高潜同好匹配",
                    html.Div(id='pairs-table'),
                    "fas fa-trophy",
                    extra=html.Span(f"共 {len(hidden_pairs)} 对", style={'color': TEXT_MUTED, 'fontSize': '13px'})
                )
            ], width=7),
            dbc.Col([
                create_section(
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
                            style={'marginBottom': '16px'}
                        ),
                        html.Div(id='domain-content')
                    ]),
                    "fas fa-compass"
                )
            ], width=5),
        ], className="mb-4 g-4"),

        # 页脚
        html.Footer([
            html.Hr(style={'borderColor': BG_GRAY, 'margin': '0 0 16px 0'}),
            html.P([
                html.I(className="fas fa-code me-2", style={'color': TEXT_MUTED}),
                "引力拓扑 (Gravity Topology) · 基于空间计量与 A2A 机制的社区暗网发掘系统"
            ], className="text-center mb-0",
               style={'color': TEXT_MUTED, 'fontSize': '13px', 'padding': '0 0 24px 0'})
        ])

    ], style={'maxWidth': '1400px', 'margin': '0 auto', 'padding': '24px'})

], style={'backgroundColor': BG_GRAY, 'minHeight': '100vh', 'fontFamily': "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"})


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
        marker=dict(
            color=ZHIHU_BLUE,
            line=dict(width=0)
        ),
        opacity=0.9
    ))

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=40, r=20, t=10, b=40),
        xaxis=dict(
            gridcolor='#F0F0F0',
            zerolinecolor='#F0F0F0',
            title="引力值",
            titlefont=dict(size=12, color=TEXT_SECONDARY)
        ),
        yaxis=dict(
            gridcolor='#F0F0F0',
            zerolinecolor='#F0F0F0',
            title="数量",
            titlefont=dict(size=12, color=TEXT_SECONDARY)
        ),
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

    fig = px.scatter(
        df, x='发帖数', y='评论数', size='内容数',
        hover_name='name', color='内容数',
        color_continuous_scale=[[0, ZHIHU_BLUE_LIGHT], [1, ZHIHU_BLUE]],
        size_max=20
    )

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=40, r=20, t=10, b=40),
        xaxis=dict(gridcolor='#F0F0F0', zerolinecolor='#F0F0F0'),
        yaxis=dict(gridcolor='#F0F0F0', zerolinecolor='#F0F0F0'),
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
        node_size.append(max(15, G.nodes[node]['size'] * 2.5))
        node_color.append(G.degree(node))

    fig = go.Figure()

    # 边
    fig.add_trace(go.Scatter(
        x=edge_x, y=edge_y,
        mode='lines',
        line=dict(width=1.5, color=ZHIHU_BLUE_LIGHT),
        hoverinfo='none'
    ))

    # 节点
    fig.add_trace(go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        text=node_text,
        textposition="top center",
        textfont=dict(size=10, color=ZHIHU_BLUE_DARK),
        marker=dict(
            size=node_size,
            color=node_color,
            colorscale=[[0, ZHIHU_BLUE_LIGHT], [1, ZHIHU_BLUE]],
            line=dict(width=2, color=BG_WHITE)
        ),
        hoverinfo='text'
    ))

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
        reasons = pair.get('match_reasons', [])[:2]
        reason_text = ", ".join(reasons) if reasons else "综合相似"

        rows.append(
            html.Tr([
                html.Td(i, style={
                    'color': TEXT_MUTED, 'fontWeight': '600',
                    'width': '40px', 'border': 'none', 'padding': '12px 16px'
                }),
                html.Td([
                    html.Span(pair['user_a_name'], style={'color': TEXT_PRIMARY, 'fontWeight': '500'}),
                    html.Span(" ↔ ", style={'color': ZHIHU_BLUE}),
                    html.Span(pair['user_b_name'], style={'color': TEXT_PRIMARY, 'fontWeight': '500'})
                ], style={'border': 'none', 'padding': '12px 16px'}),
                html.Td(
                    html.Span(f"{pair['gravity']:.2f}", style={
                        'color': ZHIHU_BLUE, 'fontWeight': '600', 'fontSize': '15px'
                    }),
                    style={'border': 'none', 'padding': '12px 16px', 'textAlign': 'right'}
                ),
                html.Td(
                    html.Small(reason_text, style={'color': TEXT_MUTED}),
                    style={'border': 'none', 'padding': '12px 16px', 'textAlign': 'right'}
                )
            ], style={'borderBottom': f"1px solid {BG_GRAY}"})
        )

    return dbc.Table([
        html.Thead(html.Tr([
            html.Th("#", style={'color': ZHIHU_BLUE, 'fontWeight': '600', 'border': 'none', 'padding': '12px 16px', 'backgroundColor': ZHIHU_BLUE_LIGHT}),
            html.Th("用户对", style={'color': ZHIHU_BLUE, 'fontWeight': '600', 'border': 'none', 'padding': '12px 16px', 'backgroundColor': ZHIHU_BLUE_LIGHT}),
            html.Th("引力值", style={'color': ZHIHU_BLUE, 'fontWeight': '600', 'border': 'none', 'padding': '12px 16px', 'textAlign': 'right', 'backgroundColor': ZHIHU_BLUE_LIGHT}),
            html.Th("匹配理由", style={'color': ZHIHU_BLUE, 'fontWeight': '600', 'border': 'none', 'padding': '12px 16px', 'textAlign': 'right', 'backgroundColor': ZHIHU_BLUE_LIGHT}),
        ])),
        html.Tbody(rows)
    ], bordered=False, hover=True, responsive=True, style={'marginBottom': '0'})


@app.callback(
    Output('domain-content', 'children'),
    Input('domain-select', 'value')
)
def update_domain_content(domain_id):
    if not domain_id:
        return html.P("请选择领域", style={'color': TEXT_MUTED})

    from interest_explorer import InterestExplorer
    explorer = InterestExplorer('massive_data.json')
    experts = explorer.find_domain_experts(domain_id, top_n=5)

    if not experts:
        return html.P("暂无数据", style={'color': TEXT_MUTED})

    domain_info = explorer.DOMAINS.get(domain_id, {})
    domain_name = domain_info.get('name', domain_id)

    items = []
    for i, expert in enumerate(experts, 1):
        contents = explorer.get_expert_daily_content(expert['token'])
        recent = contents[0]['content'][:45] + '...' if contents else ''

        items.append(
            html.Div([
                html.Div([
                    html.Span(i, style={
                        'color': ZHIHU_BLUE, 'fontWeight': '700', 'fontSize': '16px',
                        'width': '24px', 'display': 'inline-block'
                    }),
                    html.Span(expert['name'], style={
                        'color': TEXT_PRIMARY, 'fontWeight': '600', 'fontSize': '15px'
                    }),
                    html.Span(f" · {expert['domain_score']:.0%}", style={
                        'color': ZHIHU_BLUE, 'fontSize': '13px', 'marginLeft': '8px'
                    })
                ]),
                html.Div(recent, style={'color': TEXT_SECONDARY, 'fontSize': '13px', 'marginTop': '4px'}) if recent else None
            ], style={
                'padding': '12px 0',
                'borderBottom': f"1px solid {BG_GRAY}"
            })
        )

    return html.Div([
        html.Div([
            html.Span(domain_info.get('emoji', ''), style={'fontSize': '18px'}),
            html.Span(f" {domain_name} 领域达人", style={
                'color': ZHIHU_BLUE_DARK, 'fontWeight': '600', 'fontSize': '15px', 'marginLeft': '8px'
            })
        ], style={'marginBottom': '12px'}),
        html.Div(items)
    ])


# ============ 运行 ============
if __name__ == '__main__':
    app.run(debug=False, port=8050, host='0.0.0.0')
