"""
引力拓扑 - 产品体验版 V2
核心功能：每日探索 + 交换人生 + 实时 A2A 对话 + 圆桌讨论 + 数据仪表盘
"""

import json
import random
import hashlib
import os
import time
import secrets
import re
import math
from urllib.parse import urlencode
from collections import Counter, defaultdict
from dotenv import load_dotenv
from flask import Flask, render_template, jsonify, request, Response, redirect, session, url_for
from flask_session import Session
from openai import OpenAI
import requests as http_requests

load_dotenv(override=False)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET") or secrets.token_hex(32)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = './flask_session'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24小时
Session(app)
OAUTH_LAST_EVENT = None

# ============ 加载数据 ============
with open('massive_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

with open('gravity_engine_v2_results.json', 'r', encoding='utf-8') as f:
    gravity_results = json.load(f)

# 加载 A2A 对话
try:
    with open('a2a_dialogues.json', 'r', encoding='utf-8') as f:
        a2a_dialogues = json.load(f)
except FileNotFoundError:
    a2a_dialogues = []

users = data.get('users', {})
posts = data.get('posts', [])
comments = data.get('comments', [])
hidden_pairs = gravity_results.get('hidden_pairs', [])
interaction_matrix = data.get('interaction_matrix', {})

# 构建 A2A 对话索引
a2a_index = {}
for d in a2a_dialogues:
    pair = d['pair']
    key1 = (pair['user_a'], pair['user_b'])
    key2 = (pair['user_b'], pair['user_a'])
    a2a_index[key1] = d
    a2a_index[key2] = d

# ============ DeepSeek 客户端 ============
class _LazyDeepseekClient:
    """懒加载代理：首次访问时创建客户端，之后缓存复用"""
    def __init__(self):
        self._client = None
        self._initialized = False

    def _get(self):
        if not self._initialized:
            key = _getenv_nonempty("DEEPSEEK_API_KEY")
            if key:
                self._client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
            self._initialized = True
        return self._client

    def __bool__(self):
        return self._get() is not None

    def __getattr__(self, name):
        client = self._get()
        if client is None:
            raise AttributeError("DeepSeek API 未配置。如需启用 AI 生成，请设置 DEEPSEEK_API_KEY 环境变量并重启服务器")
        return getattr(client, name)

deepseek_client = _LazyDeepseekClient()

# ============ 从共享模块导入配置和工具 ============
from gravity_topology.config import (
    DOMAINS, TOPICS, TECH_KEYWORDS, HUMAN_KEYWORDS, QUESTION_KEYWORDS,
    ZHIHU_OAUTH_APP_ID, ZHIHU_OAUTH_APP_KEY, ZHIHU_OAUTH_REDIRECT_URI,
    ZHIHU_COMMUNITY_APP_KEY, ZHIHU_COMMUNITY_APP_SECRET, ZHIHU_HOT_API_URL,
    getenv_nonempty as _getenv_nonempty,
)
from gravity_topology.utils import (
    clean_html, clean_hot_text, split_hot_title, time_ago as _time_ago,
    is_bot_user, calculate_entropy, infer_domain_from_text,
    analyze_user_style as _analyze_user_style_shared,
    build_persona_prompt as _build_persona_prompt_shared,
    get_user_profile as _get_user_profile_shared,
)



# ============ 工具函数（委托给共享模块） ============

def get_user_profile(token):
    """获取用户完整画像"""
    return _get_user_profile_shared(token, users, posts, comments)


def get_user_style(token):
    """分析用户风格"""
    user = users.get(token, {})
    contents = user.get('contents', [])
    style = _analyze_user_style_shared(contents)
    style['name'] = user.get('name', token)
    return style


def build_persona_prompt(token):
    """为用户构建 Agent 人设 prompt"""
    user = users.get(token, {})
    if not user:
        return "你是一个知乎用户。"
    contents = user.get('contents', [])
    style = get_user_style(token)
    return _build_persona_prompt_shared(
        user.get('name', token), user, style, contents,
    )


# 构建去重用户表
from gravity_topology.utils import build_dedup_users as _build_dedup
_real_user_tokens = _build_dedup(users)



def get_user_daily_feed(token, limit=8, seen_prefixes=None):
    if seen_prefixes is None:
        seen_prefixes = set()

    user = users.get(token, {})
    contents = user.get('contents', [])
    user_posts = [p for p in posts if p.get('author_token') == token]
    posts_by_content = {p.get('content', '')[:60]: p for p in user_posts}

    feed = []
    for content in contents:
        if len(feed) >= limit:
            break
        prefix = content[:60].strip()
        if prefix in seen_prefixes or len(prefix) < 10:
            continue
        seen_prefixes.add(prefix)

        matched_post = posts_by_content.get(prefix)
        pin_id = matched_post.get('pin_id', '') if matched_post else ''
        pin_url = f'https://www.zhihu.com/pin/{pin_id}' if pin_id else ''

        feed.append({
            'content': content[:150] + ('...' if len(content) > 150 else ''),
            'full_content': content,
            'type': 'post',
            'pin_url': pin_url,
            'like_num': matched_post.get('like_num', 0) if matched_post else 0,
            'comment_num': matched_post.get('comment_num', 0) if matched_post else 0,
        })

    return feed



def _build_immersive_feed(token, limit=15):
    """构建沉浸式视角信息流 - 以指定用户的视角刷知乎"""
    user = users.get(token, {})
    profile = get_user_profile(token)
    style = get_user_style(token)

    if not profile:
        return {'persona': None, 'feed': [], 'insight': {}}

    primary_domain = profile.get('primary_domain', 'unknown')
    domain_info = DOMAINS.get(primary_domain, {})
    domain_keywords = domain_info.get('keywords', [])

    seen_prefixes = set()
    feed = []

    # 1. own: 该用户自己的 posts
    own_posts = [p for p in posts if p.get('author_token') == token]
    for p in own_posts[:max(2, limit // 5)]:
        content = p.get('content', '')
        prefix = content[:60].strip()
        if prefix in seen_prefixes or len(prefix) < 10:
            continue
        seen_prefixes.add(prefix)
        feed.append({
            'id': f'own_{p.get("pin_id", "")}',
            'type': 'own',
            'type_label': '你的创作',
            'type_color': '#7C3AED',
            'title': split_hot_title(content),
            'excerpt': clean_hot_text(content, 200),
            'author': profile['name'],
            'author_token': token,
            'author_avatar': profile['name'][0] if profile['name'] else '?',
            'likes': int(p.get('like_num', 0)),
            'comments': int(p.get('comment_num', 0)),
            'why_recommended': '这是你自己的历史创作',
            'time_ago': _time_ago(p.get('publish_time', 0)),
        })

    # 2. domain_peer: 同领域其他用户的高赞 posts
    domain_posts = []
    for p in posts:
        if p.get('author_token') == token:
            continue
        p_content = p.get('content', '')
        if any(kw in p_content for kw in domain_keywords[:8]):
            domain_posts.append(p)
    domain_posts.sort(key=lambda x: int(x.get('like_num', 0)), reverse=True)

    for p in domain_posts[:max(3, limit // 3)]:
        content = p.get('content', '')
        prefix = content[:60].strip()
        if prefix in seen_prefixes or len(prefix) < 10:
            continue
        seen_prefixes.add(prefix)
        author_name = p.get('author_name', '未知用户')
        feed.append({
            'id': f'domain_{p.get("pin_id", "")}',
            'type': 'domain_peer',
            'type_label': '领域推荐',
            'type_color': '#1565C0',
            'title': split_hot_title(content),
            'excerpt': clean_hot_text(content, 200),
            'author': author_name,
            'author_token': p.get('author_token', ''),
            'author_avatar': author_name[0] if author_name else '?',
            'likes': int(p.get('like_num', 0)),
            'comments': int(p.get('comment_num', 0)),
            'why_recommended': f'与你关注的「{domain_info.get("name", "该领域")}」领域相关',
            'time_ago': _time_ago(p.get('publish_time', 0)),
        })

    # 3. style_match: 风格相似用户的内容
    style_type = style.get('type', 'unknown')
    style_posts = []
    for other_token in _real_user_tokens:
        if other_token == token:
            continue
        other_style = get_user_style(other_token)
        if other_style.get('type') == style_type:
            other_posts = [p for p in posts if p.get('author_token') == other_token]
            style_posts.extend(other_posts)
    style_posts.sort(key=lambda x: int(x.get('like_num', 0)), reverse=True)

    for p in style_posts[:max(2, limit // 5)]:
        content = p.get('content', '')
        prefix = content[:60].strip()
        if prefix in seen_prefixes or len(prefix) < 10:
            continue
        seen_prefixes.add(prefix)
        author_name = p.get('author_name', '未知用户')
        feed.append({
            'id': f'style_{p.get("pin_id", "")}',
            'type': 'style_match',
            'type_label': '风格匹配',
            'type_color': '#E65100',
            'title': split_hot_title(content),
            'excerpt': clean_hot_text(content, 200),
            'author': author_name,
            'author_token': p.get('author_token', ''),
            'author_avatar': author_name[0] if author_name else '?',
            'likes': int(p.get('like_num', 0)),
            'comments': int(p.get('comment_num', 0)),
            'why_recommended': f'写作风格与你相似（{style["traits"][:20]}...）',
            'time_ago': _time_ago(p.get('publish_time', 0)),
        })

    # 4. hot_interest: 高赞内容中匹配用户兴趣的
    hot_posts = [p for p in posts if int(p.get('like_num', 0)) >= 3]
    user_contents = ' '.join(user.get('contents', [])[:20])
    interest_posts = []
    for p in hot_posts:
        if p.get('author_token') == token:
            continue
        p_content = p.get('content', '')
        prefix = p_content[:60].strip()
        if prefix in seen_prefixes:
            continue
        overlap = sum(1 for word in re.findall(r'[\w\u4e00-\u9fff]{2,}', user_contents)[:50]
                     if word in p_content)
        if overlap > 0:
            interest_posts.append((p, overlap))
    interest_posts.sort(key=lambda x: x[1] * 10 + int(x[0].get('like_num', 0)), reverse=True)

    for p, _ in interest_posts[:max(2, limit // 5)]:
        content = p.get('content', '')
        prefix = content[:60].strip()
        if prefix in seen_prefixes or len(prefix) < 10:
            continue
        seen_prefixes.add(prefix)
        author_name = p.get('author_name', '未知用户')
        feed.append({
            'id': f'hot_{p.get("pin_id", "")}',
            'type': 'hot_interest',
            'type_label': '热点精选',
            'type_color': '#1B5E20',
            'title': split_hot_title(content),
            'excerpt': clean_hot_text(content, 200),
            'author': author_name,
            'author_token': p.get('author_token', ''),
            'author_avatar': author_name[0] if author_name else '?',
            'likes': int(p.get('like_num', 0)),
            'comments': int(p.get('comment_num', 0)),
            'why_recommended': '根据你的阅读兴趣推荐',
            'time_ago': _time_ago(p.get('publish_time', 0)),
        })

    random.shuffle(feed)

    # 生成 insight
    similar_users = []
    for other_token in list(_real_user_tokens)[:50]:
        if other_token == token:
            continue
        other_profile = get_user_profile(other_token)
        if other_profile and other_profile.get('primary_domain') == primary_domain:
            similar_users.append({
                'token': other_token,
                'name': other_profile['name'],
                'domain': other_profile['primary_domain_name'],
                'emoji': other_profile['primary_domain_emoji'],
            })
    random.shuffle(similar_users)

    persona_summary = f'你是「{profile["name"]}」，一个关注{domain_info.get("name", "多领域")}的知乎用户。'
    if style.get('type') == 'tech':
        persona_summary += '你倾向于用数据和逻辑分析问题，喜欢深入技术细节。'
    elif style.get('type') == 'humanist':
        persona_summary += '你善于从人文角度思考，关注技术对社会的影响。'
    else:
        persona_summary += '你兼具理性与感性，能在不同视角间切换。'

    return {
        'persona': {
            'token': token,
            'name': profile['name'],
            'domain': domain_info.get('name', '未归类'),
            'domain_emoji': domain_info.get('emoji', ''),
            'style_traits': style.get('traits', '风格未知'),
            'style_type': style.get('type', 'unknown'),
            'content_count': profile['total_content'],
            'post_count': profile['post_count'],
            'comment_count': profile['comment_count'],
        },
        'feed': feed[:limit],
        'insight': {
            'persona_summary': persona_summary,
            'reading_pattern': f'偏好阅读{domain_info.get("name", "多领域")}相关内容，对{style.get("traits", "多元")}风格的内容感兴趣',
            'engagement_style': '倾向于深度阅读后给出有见地的评论' if profile['comment_count'] > profile['post_count'] else '喜欢创作原创内容并引发讨论',
            'similar_users': similar_users[:5],
        }
    }


# clean_hot_text, split_hot_title, infer_domain_from_text 已从 gravity_topology.utils 导入


def get_related_users_for_hot(text, domain_id, limit=3):
    domain_keywords = DOMAINS.get(domain_id, {}).get('keywords', [])
    scored = []
    text_lower = text.lower()
    for token in _real_user_tokens:
        user = users.get(token, {})
        contents = user.get('contents', [])
        if not contents:
            continue
        joined = ' '.join(contents[:12])
        kw_score = sum(2 for kw in domain_keywords if kw.lower() in joined.lower())
        text_score = sum(1 for word in re.findall(r'[\w\u4e00-\u9fff]{2,}', text_lower)[:30] if word in joined.lower())
        content_count = len(contents)
        score = kw_score + text_score + min(content_count, 20) * 0.05
        if score > 0:
            scored.append((score, token, user))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            'token': token,
            'name': user.get('name', token),
            'content_count': len(user.get('contents', [])),
        }
        for _, token, user in scored[:limit]
    ]


def normalize_external_hot_items(payload, domain_filter=None):
    raw_items = []
    if isinstance(payload, list):
        raw_items = payload
    elif isinstance(payload, dict):
        for key in ['items', 'data', 'list', 'hot_list']:
            value = payload.get(key)
            if isinstance(value, list):
                raw_items = value
                break
        if not raw_items and isinstance(payload.get('data'), dict):
            for key in ['items', 'list', 'hot_list']:
                value = payload['data'].get(key)
                if isinstance(value, list):
                    raw_items = value
                    break

    items = []
    for idx, raw in enumerate(raw_items[:50], start=1):
        if not isinstance(raw, dict):
            continue
        target = raw.get('target') if isinstance(raw.get('target'), dict) else raw
        title = target.get('title') or raw.get('title') or raw.get('name') or split_hot_title(target.get('excerpt') or raw.get('excerpt') or '')
        excerpt = target.get('excerpt') or raw.get('excerpt') or raw.get('summary') or raw.get('description') or title
        url = target.get('url') or raw.get('url') or raw.get('link') or ''
        if url and url.startswith('/'):
            url = f'https://www.zhihu.com{url}'
        if not url:
            question_id = target.get('id') or raw.get('id')
            url = f'https://www.zhihu.com/question/{question_id}' if question_id else 'https://www.zhihu.com/hot'
        text = f'{title} {excerpt}'
        domain_id = infer_domain_from_text(text)
        if domain_filter and domain_id != domain_filter:
            continue
        domain_info = DOMAINS.get(domain_id, {'name': '未归类', 'emoji': '❓'})
        items.append({
            'id': str(raw.get('id') or target.get('id') or idx),
            'rank': len(items) + 1,
            'title': clean_hot_text(title, 60),
            'excerpt': clean_hot_text(excerpt, 180),
            'url': url,
            'heat': int(raw.get('heat') or raw.get('score') or raw.get('hot') or max(1, 1000 - idx * 12)),
            'domain': domain_id,
            'domain_name': domain_info['name'],
            'domain_emoji': domain_info['emoji'],
            'author': target.get('author', {}).get('name') if isinstance(target.get('author'), dict) else raw.get('author_name', ''),
            'source_label': '知乎热榜',
            'creative_potential': '高' if idx <= 5 else '中',
            'controversy': '待分析',
            'creation_direction': ['综合视角', '热点跟进'],
            'related_users': get_related_users_for_hot(text, domain_id),
        })
    return items


def select_hot_posts(scored_posts, domain_filter=None, limit=30):
    if domain_filter:
        return sorted(scored_posts, key=lambda x: x[0], reverse=True)[:limit]

    grouped = defaultdict(list)
    for item in sorted(scored_posts, key=lambda x: x[0], reverse=True):
        grouped[item[3]].append(item)

    selected = []
    domain_order = sorted(
        grouped.keys(),
        key=lambda did: grouped[did][0][0] if grouped[did] else 0,
        reverse=True
    )
    while len(selected) < limit and any(grouped.values()):
        for domain_id in domain_order:
            if grouped[domain_id]:
                selected.append(grouped[domain_id].pop(0))
                if len(selected) >= limit:
                    break
    return selected


def build_local_hot_items(domain_filter=None, limit=30):
    scored_posts = []
    seen_titles = set()
    now = int(time.time())
    for post in posts:
        author_name = post.get('author_name', '')
        author_token = post.get('author_token', '')
        if is_bot_user(author_name) or is_bot_user(author_token):
            continue
        content = post.get('content', '')
        if len(clean_hot_text(content, 80)) < 8:
            continue
        title = split_hot_title(content)
        if title in seen_titles:
            continue
        seen_titles.add(title)
        text = f"{title} {content}"
        domain_id = infer_domain_from_text(text)
        if domain_filter and domain_id != domain_filter:
            continue
        like_num = int(post.get('like_num') or 0)
        comment_num = int(post.get('comment_num') or 0)
        publish_time = int(post.get('publish_time') or 0)
        recency = max(0, 1 - abs(now - publish_time) / (86400 * 30))
        content_bonus = min(len(content) / 600, 2)
        heat = round(math.log1p(comment_num) * 90 + math.log1p(like_num) * 70 + content_bonus * 20 + recency * 15, 1)
        scored_posts.append((heat, post, title, domain_id))

    selected_posts = select_hot_posts(scored_posts, domain_filter, limit)
    items = []
    creation_directions = {
        'ai_tech': ['技术解读', '行业影响', '产品测评'],
        'humanities': ['哲学思考', '文化评论', '伦理探讨'],
        'society': ['社会观察', '数据分析', '政策解读'],
        'life': ['经验分享', '情感共鸣', '实用指南'],
        'creative': ['创作教程', '审美分析', '灵感启发'],
        'unknown': ['综合视角', '现象观察'],
    }
    for rank, (heat, post, title, domain_id) in enumerate(selected_posts, start=1):
        content = post.get('content', '')
        pin_id = post.get('pin_id') or ''
        text = f'{title} {content}'
        like_num = int(post.get('like_num') or 0)
        comment_num = int(post.get('comment_num') or 0)

        if heat > 80:
            creative_potential = '高'
        elif heat > 40:
            creative_potential = '中'
        else:
            creative_potential = '低'

        controversy_ratio = comment_num / max(like_num, 1)
        if controversy_ratio > 0.8:
            controversy = '高'
        elif controversy_ratio > 0.3:
            controversy = '中'
        else:
            controversy = '低'

        domain_info = DOMAINS.get(domain_id, {'name': '未归类', 'emoji': '❓'})
        items.append({
            'id': str(pin_id or f'local-{rank}'),
            'rank': rank,
            'title': clean_hot_text(title, 60),
            'excerpt': clean_hot_text(content, 180),
            'url': f'https://www.zhihu.com/pin/{pin_id}' if pin_id else 'https://www.zhihu.com/hot',
            'heat': heat,
            'domain': domain_id,
            'domain_name': domain_info['name'],
            'domain_emoji': domain_info['emoji'],
            'author': post.get('author_name', ''),
            'source_label': '社区热点',
            'like_num': like_num,
            'comment_num': comment_num,
            'creative_potential': creative_potential,
            'controversy': controversy,
            'creation_direction': creation_directions.get(domain_id, ['综合视角']),
            'related_users': get_related_users_for_hot(text, domain_id),
        })
    return items


def find_domain_experts(domain_id, top_n=6):
    if domain_id not in DOMAINS:
        return []

    domain = DOMAINS[domain_id]
    keywords = domain['keywords']
    experts = []

    for token in _real_user_tokens:
        user = users.get(token, {})
        contents = user.get('contents', [])
        name = user.get('name', token)
        if len(contents) < 5:
            continue

        hits = 0
        for content in contents:
            for kw in keywords:
                if kw in content:
                    hits += 1
                    break
        domain_score = hits / len(contents)

        is_bot = is_bot_user(name)
        unique_prefixes = set(c[:40] for c in contents if len(c) >= 40)
        uniqueness = len(unique_prefixes) / max(len(contents), 1)
        avg_len = sum(len(c) for c in contents) / max(len(contents), 1)
        length_score = min(avg_len / 200, 1.0)
        quality = uniqueness * 0.5 + length_score * 0.3 + (0.3 if not is_bot else -0.2)

        final_score = domain_score * 0.6 + max(quality, 0) * 0.4

        if final_score > 0.03:
            experts.append({
                'token': token,
                'name': name,
                'score': round(final_score, 3),
                'domain_score': round(domain_score, 3),
                'quality': round(max(quality, 0), 3),
                'is_bot': is_bot,
                'post_count': user.get('post_count', 0),
                'comment_count': user.get('comment_count', 0),
                'content_count': len(contents),
            })

    experts.sort(key=lambda x: x['score'], reverse=True)
    return experts[:top_n]


def find_exchange_partner(token):
    candidates = []
    seen_tokens = set()

    for pair in hidden_pairs:
        for target_token, target_name in [(pair['user_b'], pair['user_b_name']), (pair['user_a'], pair['user_a_name'])]:
            if (pair['user_a'] == token or pair['user_b'] == token) and target_token != token:
                if target_token in _real_user_tokens and target_token not in seen_tokens:
                    seen_tokens.add(target_token)
                    candidates.append({
                        'token': target_token,
                        'name': target_name,
                        'gravity': pair['gravity'],
                        'reasons': pair.get('match_reasons', []),
                        'source': 'hidden_pair',
                    })

    for (ua, ub), dialogue in a2a_index.items():
        if ua == token and ub not in seen_tokens and ub in _real_user_tokens:
            seen_tokens.add(ub)
            candidates.append({
                'token': ub,
                'name': dialogue['pair']['user_b_name'] if ua == dialogue['pair']['user_a'] else dialogue['pair']['user_a_name'],
                'gravity': dialogue['pair']['gravity'],
                'reasons': [f"已有A2A对话：{dialogue['topic'][:20]}..."],
                'source': 'a2a',
            })

    if len(candidates) < 3:
        profile = get_user_profile(token)
        if profile:
            primary = profile['primary_domain']
            for t in _real_user_tokens:
                if t == token or t in seen_tokens:
                    continue
                u = users.get(t, {})
                if len(u.get('contents', [])) < 5:
                    continue
                p = get_user_profile(t)
                if p and p['primary_domain'] == primary:
                    common_kw = 0
                    for kw in DOMAINS[primary]['keywords']:
                        for c in u.get('contents', [])[:10]:
                            if kw in c:
                                common_kw += 1
                                break
                    sim = min(common_kw / max(len(u.get('contents', [])[:10]), 1), 1.0)
                    seen_tokens.add(t)
                    candidates.append({
                        'token': t,
                        'name': u.get('name', t),
                        'gravity': round(0.4 + sim * 0.5, 3),
                        'reasons': ['同领域不同视角'],
                        'source': 'domain_match',
                    })

    candidates.sort(key=lambda x: x['gravity'], reverse=True)
    return candidates[:8]


def get_a2a_dialogue(token_a, token_b):
    key = (token_a, token_b)
    if key in a2a_index:
        return a2a_index[key]
    return None


def build_local_a2a_fallback(token_a, token_b, topic):
    """在实时模型不可用时生成可展示的本地兜底对话。"""
    static_dialogue = get_a2a_dialogue(token_a, token_b)
    if static_dialogue and static_dialogue.get('dialogue'):
        return static_dialogue.get('topic', topic), static_dialogue['dialogue']

    profile_a = get_user_profile(token_a)
    profile_b = get_user_profile(token_b)
    name_a = profile_a['name'] if profile_a else token_a
    name_b = profile_b['name'] if profile_b else token_b
    sample_a = (profile_a.get('contents') or ['我更关注真实内容背后的兴趣连接。'])[0] if profile_a else ''
    sample_b = (profile_b.get('contents') or ['我更在意社区讨论能不能产生新的连接。'])[0] if profile_b else ''

    return topic, [
        {
            'round': 1,
            'speaker': name_a,
            'speaker_token': token_a,
            'content': f"如果围绕「{topic}」聊，我会先从自己常看的内容出发。比如「{sample_a[:80]}」，这里面最打动我的是真实经验能不能被重新连接起来。"
        },
        {
            'round': 2,
            'speaker': name_b,
            'speaker_token': token_b,
            'content': f"我会补一个视角：从我的内容看，「{sample_b[:80]}」更像是在寻找同频的人。这个话题的价值不只在观点相同，而在能不能让不同路径的人相遇。"
        }
    ]


def oauth_failure_redirect(error_code, detail=None):
    record_oauth_event(False, error_code, detail)
    params = {'error': error_code}
    if detail:
        params['oauth_detail'] = clean_hot_text(detail, 120)
    return redirect('/?' + urlencode(params))


def record_oauth_event(ok, stage, detail=None, extra=None):
    global OAUTH_LAST_EVENT
    event = {
        'ok': bool(ok),
        'stage': stage,
        'detail': clean_hot_text(str(detail or ''), 200),
        'time': int(time.time()),
        'redirect_uri': ZHIHU_OAUTH_REDIRECT_URI,
        'app_id_prefix': ZHIHU_OAUTH_APP_ID[:4] + '...' if ZHIHU_OAUTH_APP_ID and len(ZHIHU_OAUTH_APP_ID) > 4 else ZHIHU_OAUTH_APP_ID,
    }
    if extra:
        event.update(extra)
    OAUTH_LAST_EVENT = event
    try:
        session['oauth_last'] = event
    except RuntimeError:
        pass

    try:
        with open('oauth_debug.log', 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    except Exception:
        pass


def extract_oauth_error_detail(payload):
    if isinstance(payload, dict):
        return payload.get('data') or payload.get('error_description') or payload.get('error') or payload.get('message')
    return payload


def default_zhihu_user():
    return {
        'uid': None,
        'name': '已连接知乎',
        'avatar': '',
        'headline': '授权成功，关注网络可用于本次演示分析',
    }


def normalize_zhihu_user(user_info):
    if not isinstance(user_info, dict):
        return default_zhihu_user()
    if user_info.get('code') in (401, 403) or user_info.get('data') == 'Access token is not valid':
        return default_zhihu_user()
    if isinstance(user_info.get('data'), dict):
        user_info = user_info['data']

    return {
        'uid': user_info.get('uid'),
        'name': user_info.get('fullname') or user_info.get('name') or '知乎用户',
        'avatar': user_info.get('avatar_path') or user_info.get('avatar') or '',
        'headline': user_info.get('headline') or user_info.get('description') or '',
    }


def extract_access_token(token_payload):
    if not isinstance(token_payload, dict):
        return None
    if token_payload.get('access_token'):
        return token_payload.get('access_token')
    data = token_payload.get('data')
    if isinstance(data, dict):
        return data.get('access_token') or data.get('token')
    return None


def request_zhihu_access_token(code):
    payload = {
        'app_id': ZHIHU_OAUTH_APP_ID,
        'app_key': ZHIHU_OAUTH_APP_KEY,
        'grant_type': 'authorization_code',
        'redirect_uri': ZHIHU_OAUTH_REDIRECT_URI,
        'code': code,
    }

    # 知乎API要求使用 application/x-www-form-urlencoded 格式
    response = http_requests.post(
        'https://openapi.zhihu.com/access_token',
        timeout=10,
        data=payload,
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )
    response_preview = clean_hot_text(getattr(response, 'text', ''), 160)
    record_oauth_event(response.status_code == 200, 'token_response', response_preview, {
        'http_status': getattr(response, 'status_code', None),
    })
    return response


def compute_interest_collision(token_a, token_b):
    profile_a = get_user_profile(token_a)
    profile_b = get_user_profile(token_b)

    if not profile_a or not profile_b:
        return None

    scores_a = profile_a['domain_scores']
    scores_b = profile_b['domain_scores']

    overlap_domains = []
    for domain_id in DOMAINS:
        if scores_a.get(domain_id, 0) > 0.1 and scores_b.get(domain_id, 0) > 0.1:
            overlap_domains.append({
                'domain': DOMAINS[domain_id]['name'],
                'emoji': DOMAINS[domain_id]['emoji'],
                'score_a': round(scores_a[domain_id], 2),
                'score_b': round(scores_b[domain_id], 2),
            })

    diverge_a = []
    diverge_b = []
    for domain_id in DOMAINS:
        if scores_a.get(domain_id, 0) > 0.2 and scores_b.get(domain_id, 0) < 0.1:
            diverge_a.append(DOMAINS[domain_id]['name'])
        if scores_b.get(domain_id, 0) > 0.2 and scores_a.get(domain_id, 0) < 0.1:
            diverge_b.append(DOMAINS[domain_id]['name'])

    contents_a = set()
    contents_b = set()
    for c in profile_a.get('contents', [])[:30]:
        for kw_list in DOMAINS.values():
            for kw in kw_list['keywords']:
                if kw in c:
                    contents_a.add(kw)
    for c in profile_b.get('contents', [])[:30]:
        for kw_list in DOMAINS.values():
            for kw in kw_list['keywords']:
                if kw in c:
                    contents_b.add(kw)

    common_keywords = list(contents_a & contents_b)[:8]
    only_a = list(contents_a - contents_b)[:5]
    only_b = list(contents_b - contents_a)[:5]

    return {
        'overlap_domains': overlap_domains,
        'diverge_a': diverge_a,
        'diverge_b': diverge_b,
        'common_keywords': common_keywords,
        'only_a': only_a,
        'only_b': only_b,
    }


# ============ 路由 ============


@app.route('/favicon.ico')
def favicon():
    return Response(status=204)


@app.route('/')
def index():
    # OAuth 回调处理（兼容直接跳转回 / 的情况）
    code = request.args.get('code') or request.args.get('authorization_code')
    if code:
        return _handle_oauth_callback(code, request.args.get('state'))
    return _render_index()


@app.route('/callback')
def oauth_callback():
    """知乎 OAuth 回调路由（redirect_uri = http://localhost:8050/callback）"""
    code = request.args.get('code') or request.args.get('authorization_code')
    if not code:
        return redirect('/')
    return _handle_oauth_callback(code, request.args.get('state'))


def _handle_oauth_callback(code, state):
    """处理知乎 OAuth 回调"""
    record_oauth_event(False, 'code_received', '已收到知乎授权码，准备换取 access_token', {
        'has_state': bool(state),
        'code_length': len(code or ''),
    })
    expected_state = session.get('oauth_state')
    if state and expected_state and state != expected_state:
        return oauth_failure_redirect('invalid_state')

    try:
        token_resp = request_zhihu_access_token(code)
    except Exception as e:
        app.logger.error(f"OAuth token request failed: {e}")
        return oauth_failure_redirect('token_failed', str(e))

    if token_resp.status_code != 200:
        app.logger.error(f"OAuth token request returned {token_resp.status_code}: {token_resp.text[:200]}")
        return oauth_failure_redirect('token_failed', token_resp.text[:200])

    token_data = token_resp.json()
    access_token = extract_access_token(token_data)

    if not access_token:
        app.logger.error(f"OAuth token response missing access_token: {token_data}")
        return oauth_failure_redirect('no_token', extract_oauth_error_detail(token_data))

    session['access_token'] = access_token
    session['zhihu_user'] = default_zhihu_user()
    session.pop('oauth_state', None)
    session.permanent = True  # 保持session持久化

    try:
        user_resp = http_requests.get(
            'https://openapi.zhihu.com/user',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10
        )
        if user_resp.status_code == 200:
            user_info = user_resp.json()
            session['zhihu_user'] = normalize_zhihu_user(user_info)
    except Exception as e:
        app.logger.warning(f"Failed to fetch user info after OAuth: {e}")

    record_oauth_event(True, 'token_ok', 'OAuth token stored')
    return redirect('/?login=success')


def _render_index():
    quality_users = []
    for token in _real_user_tokens:
        user = users.get(token, {})
        content_count = len(user.get('contents', []))
        if content_count >= 5:
            quality_users.append({
                'token': token,
                'name': user.get('name', token),
                'content_count': content_count,
                'post_count': user.get('post_count', 0),
                'comment_count': user.get('comment_count', 0),
            })
    quality_users.sort(key=lambda x: x['content_count'], reverse=True)
    quality_users = quality_users[:30]

    pairs = []
    for pair in hidden_pairs:
        pairs.append({
            'user_a': pair['user_a'],
            'user_a_name': pair['user_a_name'],
            'user_b': pair['user_b'],
            'user_b_name': pair['user_b_name'],
            'gravity': round(pair['gravity'], 4),
            'reasons': pair.get('match_reasons', []),
        })

    return render_template('index.html',
                         domains=DOMAINS,
                         quality_users=quality_users,
                         pairs=pairs,
                         total_users=len(users),
                         total_posts=len(posts),
                         total_comments=len(comments))


@app.route('/api/explore/<domain_id>')
def api_explore(domain_id):
    if domain_id not in DOMAINS:
        return jsonify({'error': '未知领域'}), 400

    domain = DOMAINS[domain_id]
    experts = find_domain_experts(domain_id, top_n=6)

    seen_prefixes = set()
    for expert in experts:
        expert['feed'] = get_user_daily_feed(expert['token'], limit=5, seen_prefixes=seen_prefixes)
        profile = get_user_profile(expert['token'])
        if profile:
            expert['primary_domain'] = profile['primary_domain_name']
            expert['primary_domain_emoji'] = profile['primary_domain_emoji']

    return jsonify({'domain': domain, 'experts': experts})


@app.route('/api/zhihu_hot')
def api_zhihu_hot():
    """知乎热点流：优先外部热榜接口，失败时使用本地社区热点兜底。"""
    domain_filter = request.args.get('domain', '').strip()
    if domain_filter and domain_filter not in DOMAINS:
        return jsonify({'error': '未知领域'}), 400

    items = []
    source = 'local_community'
    source_note = '使用本地采集的知乎圈子内容生成社区热点'

    if ZHIHU_HOT_API_URL:
        try:
            resp = http_requests.get(ZHIHU_HOT_API_URL, timeout=8)
            if resp.status_code == 200:
                items = normalize_external_hot_items(resp.json(), domain_filter or None)
                if items:
                    source = 'configured_api'
                    source_note = '使用配置的知乎热榜接口'
        except Exception as e:
            app.logger.warning(f"Configured hot API failed, falling back to local community data: {e}")

    if not items:
        items = build_local_hot_items(domain_filter or None)

    return jsonify({
        'source': source,
        'source_note': source_note,
        'domain': domain_filter or 'all',
        'domains': {
            did: {'name': d['name'], 'emoji': d['emoji']}
            for did, d in DOMAINS.items()
        },
        'updated_at': int(time.time()),
        'items': items,
    })


@app.route('/api/trending')
def api_trending():
    """实时热点 - 聚合多源时事热点，用于灵感引擎"""
    domain_filter = request.args.get('domain', '').strip()
    if domain_filter and domain_filter not in DOMAINS:
        return jsonify({'error': '未知领域'}), 400

    all_items = []
    sources_used = []

    # 1. 尝试从配置的外部热榜 API 获取
    if ZHIHU_HOT_API_URL:
        try:
            resp = http_requests.get(ZHIHU_HOT_API_URL, timeout=8)
            if resp.status_code == 200:
                items = normalize_external_hot_items(resp.json(), domain_filter or None)
                if items:
                    all_items.extend(items)
                    sources_used.append('知乎热榜')
        except Exception:
            pass

    # 2. 尝试从公共热点聚合 API 获取（今日热榜）
    public_apis = [
        ('https://tophub.today/api/nodes/2', '今日热榜-综合'),
        ('https://tophub.today/api/nodes/3', '今日热榜-科技'),
    ]
    for api_url, api_name in public_apis:
        try:
            resp = http_requests.get(api_url, timeout=5, headers={'User-Agent': 'GravityTopology/1.0'})
            if resp.status_code == 200:
                data = resp.json()
                raw_items = data.get('data', {}).get('items', []) if isinstance(data, dict) else []
                for idx, item in enumerate(raw_items[:20]):
                    if not isinstance(item, dict):
                        continue
                    title = item.get('Title') or item.get('title') or item.get('name') or ''
                    if not title:
                        continue
                    text = title
                    domain_id = infer_domain_from_text(text)
                    if domain_filter and domain_id != domain_filter:
                        continue
                    domain_info = DOMAINS.get(domain_id, {'name': '未归类', 'emoji': '❓'})
                    all_items.append({
                        'id': f'{api_name}-{idx}',
                        'rank': len(all_items) + 1,
                        'title': clean_hot_text(title, 60),
                        'excerpt': clean_hot_text(item.get('Description') or item.get('description') or title, 180),
                        'url': item.get('Url') or item.get('url') or f'https://www.zhihu.com/search?q={title}',
                        'heat': int(item.get('Hot') or item.get('hot') or max(1, 1000 - idx * 12)),
                        'domain': domain_id,
                        'domain_name': domain_info['name'],
                        'domain_emoji': domain_info['emoji'],
                        'source_label': api_name,
                        'creative_potential': '高' if idx <= 5 else '中',
                        'controversy': '待分析',
                        'creation_direction': ['综合视角', '热点跟进'],
                        'related_users': get_related_users_for_hot(text, domain_id),
                    })
                sources_used.append(api_name)
        except Exception:
            pass

    # 3. AI 生成当前时事热点话题（如果 DeepSeek 可用）
    if deepseek_client and len(all_items) < 10:
        try:
            prompt = """请生成 8 个当前（2025-2026年）最热门的中文互联网讨论话题，覆盖科技、社会、生活、人文、创意等领域。

要求：
1. 每个话题用一句话表达，带问号或对比
2. 话题要有时效性，是最近真实在讨论的
3. 覆盖不同领域，不要重复
4. 直接输出 JSON 数组，每个元素包含 title 和 domain 字段
5. domain 取值：ai_tech / humanities / society / life / creative

输出格式示例：[{"title": "...", "domain": "ai_tech"}]"""
            response = deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.9
            )
            text = response.choices[0].message.content.strip()
            if text.startswith('```'):
                text = text.split('```')[1].replace('json', '').strip()
            ai_topics = json.loads(text)
            for idx, t in enumerate(ai_topics):
                title = t.get('title', '')
                domain_id = t.get('domain', 'unknown')
                if domain_filter and domain_id != domain_filter:
                    continue
                if domain_id not in DOMAINS:
                    domain_id = infer_domain_from_text(title)
                domain_info = DOMAINS.get(domain_id, {'name': '未归类', 'emoji': '❓'})
                all_items.append({
                    'id': f'ai-trend-{idx}',
                    'rank': len(all_items) + 1,
                    'title': clean_hot_text(title, 60),
                    'excerpt': f'AI 基于当前趋势生成的热点话题，涵盖{domain_info["name"]}领域',
                    'url': f'https://www.zhihu.com/search?q={title}',
                    'heat': max(1, 800 - idx * 50),
                    'domain': domain_id,
                    'domain_name': domain_info['name'],
                    'domain_emoji': domain_info['emoji'],
                    'source_label': 'AI 趋势预测',
                    'creative_potential': '高',
                    'controversy': '中',
                    'creation_direction': ['深度分析', '观点碰撞'],
                    'related_users': get_related_users_for_hot(title, domain_id),
                })
            sources_used.append('AI 趋势预测')
        except Exception:
            pass

    # 4. 本地社区热点兜底
    if len(all_items) < 5:
        local_items = build_local_hot_items(domain_filter or None, limit=15)
        all_items.extend(local_items)
        sources_used.append('社区热点')

    # 去重
    seen_titles = set()
    unique_items = []
    for item in all_items:
        t = item.get('title', '')
        if t not in seen_titles:
            seen_titles.add(t)
            unique_items.append(item)

    # 重新编号
    for idx, item in enumerate(unique_items):
        item['rank'] = idx + 1

    return jsonify({
        'source': 'trending_aggregate',
        'source_note': f'热点来源：{" + ".join(sources_used)}',
        'domain': domain_filter or 'all',
        'domains': {
            did: {'name': d['name'], 'emoji': d['emoji']}
            for did, d in DOMAINS.items()
        },
        'updated_at': int(time.time()),
        'items': unique_items[:30],
    })


@app.route('/api/exchange/<token>')
def api_exchange(token):
    profile = get_user_profile(token)
    if not profile:
        return jsonify({'error': '用户不存在'}), 404

    partners = find_exchange_partner(token)
    my_feed = get_user_daily_feed(token, limit=6)

    return jsonify({
        'user': {
            'token': token,
            'name': profile['name'],
            'primary_domain': profile['primary_domain_name'],
            'primary_domain_emoji': profile['primary_domain_emoji'],
            'post_count': profile['post_count'],
            'comment_count': profile['comment_count'],
        },
        'my_feed': my_feed,
        'partners': partners
    })


@app.route('/api/exchange_preview/<token_a>/<token_b>')
def api_exchange_preview(token_a, token_b):
    profile_a = get_user_profile(token_a)
    profile_b = get_user_profile(token_b)

    if not profile_a or not profile_b:
        return jsonify({'error': '用户不存在'}), 404

    feed_a = get_user_daily_feed(token_a, limit=5)
    feed_b = get_user_daily_feed(token_b, limit=5)

    gravity = 0
    reasons = []
    for pair in hidden_pairs:
        if (pair['user_a'] == token_a and pair['user_b'] == token_b) or \
           (pair['user_a'] == token_b and pair['user_b'] == token_a):
            gravity = pair['gravity']
            reasons = pair.get('match_reasons', [])
            break

    a2a = get_a2a_dialogue(token_a, token_b)
    collision = compute_interest_collision(token_a, token_b)

    return jsonify({
        'user_a': {
            'token': token_a,
            'name': profile_a['name'],
            'domain': profile_a['primary_domain_name'],
            'domain_emoji': profile_a['primary_domain_emoji'],
            'post_count': profile_a['post_count'],
            'comment_count': profile_a['comment_count'],
        },
        'user_b': {
            'token': token_b,
            'name': profile_b['name'],
            'domain': profile_b['primary_domain_name'],
            'domain_emoji': profile_b['primary_domain_emoji'],
            'post_count': profile_b['post_count'],
            'comment_count': profile_b['comment_count'],
        },
        'feed_a': feed_a,
        'feed_b': feed_b,
        'gravity': gravity,
        'reasons': reasons,
        'a2a': a2a,
        'collision': collision,
    })


@app.route('/api/hidden_pairs')
def api_hidden_pairs():
    result = []
    for pair in hidden_pairs:
        result.append({
            'user_a': pair['user_a'],
            'user_a_name': pair['user_a_name'],
            'user_b': pair['user_b'],
            'user_b_name': pair['user_b_name'],
            'gravity': round(pair['gravity'], 4),
            'reasons': pair.get('match_reasons', []),
        })
    return jsonify(result)


# ============ 为你推荐 ============

def _build_for_you_feed(interests, limit=15):
    """基于用户兴趣构建个性化信息流"""
    if not interests:
        interests = list(DOMAINS.keys())

    # 收集用户选择领域的所有关键词
    all_keywords = []
    for domain_id in interests:
        domain_info = DOMAINS.get(domain_id, {})
        all_keywords.extend(domain_info.get('keywords', [])[:8])

    seen_prefixes = set()
    feed = []
    matched_users = set()

    # 1. 高赞内容中匹配兴趣的
    scored_posts = []
    for p in posts:
        content = p.get('content', '')
        prefix = content[:60].strip()
        if prefix in seen_prefixes or len(prefix) < 10:
            continue
        score = sum(2 for kw in all_keywords if kw in content)
        score += int(p.get('like_num', 0)) * 0.05
        if score > 0:
            scored_posts.append((score, p, prefix))

    scored_posts.sort(key=lambda x: x[0], reverse=True)

    for score, p, prefix in scored_posts[:limit]:
        if prefix in seen_prefixes:
            continue
        seen_prefixes.add(prefix)
        author_name = p.get('author_name', '未知用户')
        matched_users.add(p.get('author_token', ''))

        # 判断属于哪个领域
        best_domain = 'unknown'
        best_dscore = 0
        for domain_id in interests:
            domain_info = DOMAINS.get(domain_id, {})
            dscore = sum(1 for kw in domain_info.get('keywords', []) if kw in p.get('content', ''))
            if dscore > best_dscore:
                best_dscore = dscore
                best_domain = domain_id

        domain_info = DOMAINS.get(best_domain, {'name': '未归类', 'emoji': '', 'keywords': []})

        feed.append({
            'id': f'fy_{p.get("pin_id", "")}',
            'title': split_hot_title(p.get('content', '')),
            'excerpt': clean_hot_text(p.get('content', ''), 220),
            'author': author_name,
            'author_token': p.get('author_token', ''),
            'likes': int(p.get('like_num', 0)),
            'comments': int(p.get('comment_num', 0)),
            'domain': domain_info.get('name', ''),
            'domain_emoji': domain_info.get('emoji', ''),
            'time_ago': _time_ago(p.get('publish_time', 0)),
            'why_recommended': f'基于你对「{domain_info.get("name", "")}」的兴趣',
        })

    # 2. 匹配兴趣领域的用户推荐
    user_recommendations = []
    for token in _real_user_tokens:
        if token in matched_users:
            continue
        profile = get_user_profile(token)
        if not profile:
            continue
        if profile.get('primary_domain') in interests:
            user_recommendations.append({
                'token': token,
                'name': profile['name'],
                'domain': profile['primary_domain_name'],
                'emoji': profile['primary_domain_emoji'],
                'content_count': profile['total_content'],
            })

    random.shuffle(user_recommendations)

    return {
        'feed': feed[:limit],
        'users': user_recommendations[:6],
        'interests': interests,
    }


@app.route('/api/for_you', methods=['POST'])
def api_for_you():
    """为你推荐 - 基于用户兴趣的个性化内容"""
    body = request.get_json()
    interests = body.get('interests', [])
    if not interests or not isinstance(interests, list):
        return jsonify({'error': '请提供兴趣标签'}), 400

    # 过滤无效领域
    valid_interests = [d for d in interests if d in DOMAINS]
    if not valid_interests:
        valid_interests = list(DOMAINS.keys())

    result = _build_for_you_feed(valid_interests)
    return jsonify(result)


# ============ AI 生成热点话题 ============

def _generate_hot_topic():
    """基于社区数据和知乎风格，AI 生成一个热点讨论话题"""
    # 随机选几个热点关键词作为灵感
    hot_keywords = [
        'AI Agent', '大模型', '信息茧房', '算法推荐', '数字游民',
        '远程办公', '知识付费', '元宇宙', '脑机接口', '自动驾驶',
        '基因编辑', '量子计算', 'Web3', 'NFT', '碳中和',
        '内卷', '躺平', ' FIRE运动', '副业', '自媒体',
        ' ChatGPT', '提示工程', 'RAG', '多模态', '具身智能',
        '社交焦虑', '亲密关系', '原生家庭', '职业倦怠', '意义感',
    ]
    seed_keywords = random.sample(hot_keywords, 3)

    # 从 posts 中随机抽取几条真实内容作为背景
    sample_posts = random.sample(posts, min(5, len(posts))) if posts else []
    sample_contents = [p.get('content', '')[:80] + '...' for p in sample_posts]
    sample_text = '\n'.join([f'- {c}' for c in sample_contents])

    if not deepseek_client:
        # 本地兜底：组合关键词生成话题
        templates = [
            f"{seed_keywords[0]}时代，{seed_keywords[1]}会是下一个风口吗？",
            f"当{seed_keywords[0]}遇到{seed_keywords[1]}，{seed_keywords[2]}还有多远？",
            f"从{seed_keywords[0]}到{seed_keywords[1]}：我们忽略了什么？",
            f"{seed_keywords[0]}正在改变{seed_keywords[1]}，但这真的是好事吗？",
            f"深度思考：{seed_keywords[0]}、{seed_keywords[1]}与{seed_keywords[2]}的三角关系",
            f"如果{seed_keywords[0]}全面普及，{seed_keywords[1]}会变成什么样？",
            f"{seed_keywords[0]} vs {seed_keywords[1]}：普通人该如何选择？",
        ]
        topic = random.choice(templates)
        return {'topic': topic, 'source': 'local', 'seed': seed_keywords}

    prompt = f"""你是一位资深知乎内容策划。基于以下社区真实讨论片段，生成一个适合圆桌讨论的热点话题。

参考内容：
{sample_text}

灵感关键词：{', '.join(seed_keywords)}

要求：
1. 话题要有知乎感（带问号、对比、争议性）
2. 话题要新颖，不是老生常谈
3. 话题要能引发不同观点的碰撞
4. 只输出话题标题本身，不要有任何解释

热点话题："""

    try:
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=80,
            temperature=0.9
        )
        topic = response.choices[0].message.content.strip().strip('"').strip('"')
        if not topic or len(topic) < 10:
            raise ValueError("生成的 topic 太短")
        return {'topic': topic, 'source': 'llm'}
    except Exception as e:
        templates = [
            f"{seed_keywords[0]}时代，{seed_keywords[1]}会是下一个风口吗？",
            f"当{seed_keywords[0]}遇到{seed_keywords[1]}，{seed_keywords[2]}还有多远？",
            f"从{seed_keywords[0]}到{seed_keywords[1]}：我们忽略了什么？",
            f"{seed_keywords[0]}正在改变{seed_keywords[1]}，但这真的是好事吗？",
        ]
        topic = random.choice(templates)
        return {'topic': topic, 'source': 'local', 'fallback_reason': str(e)}


@app.route('/api/generate_topic', methods=['POST'])
def api_generate_topic():
    """AI 生成一个基于热点的讨论话题"""
    result = _generate_hot_topic()
    return jsonify(result)


# ============ 沉浸式视角 ============

@app.route('/api/immersive_feed', methods=['POST'])
def api_immersive_feed():
    """沉浸式视角 - 以指定用户的视角刷知乎"""
    body = request.get_json()
    token = body.get('token', '')
    if not token or token not in users:
        return jsonify({'error': '请提供有效的用户 token'}), 400

    result = _build_immersive_feed(token)
    return jsonify(result)


# ============ 新功能：实时 A2A 对话 ============

@app.route('/api/a2a_chat', methods=['POST'])
def api_a2a_chat():
    """实时 A2A 对话 - 调用 DeepSeek API 生成"""
    body = request.get_json()
    token_a = body.get('user_a')
    token_b = body.get('user_b')
    topic = body.get('topic', random.choice(TOPICS))
    rounds = min(body.get('rounds', 4), 6)

    if not token_a or not token_b:
        return jsonify({'error': '请提供 user_a 和 user_b'}), 400

    profile_a = get_user_profile(token_a)
    profile_b = get_user_profile(token_b)
    if not profile_a or not profile_b:
        return jsonify({'error': '用户不存在'}), 404

    if not deepseek_client:
        fallback_topic, fallback_dialogue = build_local_a2a_fallback(token_a, token_b, topic)
        return jsonify({
            'topic': fallback_topic,
            'dialogue': fallback_dialogue,
            'user_a': {'token': token_a, 'name': profile_a['name']},
            'user_b': {'token': token_b, 'name': profile_b['name']},
            'fallback_available': True,
            'fallback_reason': 'DeepSeek API Key 未配置，已切换为演示兜底对话',
        })

    persona_a = build_persona_prompt(token_a)
    persona_b = build_persona_prompt(token_b)

    dialogue = []
    messages_a = []
    messages_b = []

    for round_num in range(rounds):
        if round_num % 2 == 0:
            response = _call_deepseek(persona_a, topic, messages_a, messages_b, round_num == 0)
            messages_a.append({"role": "assistant", "content": response})
            messages_b.append({"role": "user", "content": response})
            dialogue.append({
                'round': round_num + 1,
                'speaker': profile_a['name'],
                'speaker_token': token_a,
                'content': response
            })
        else:
            response = _call_deepseek(persona_b, topic, messages_b, messages_a, False)
            messages_b.append({"role": "assistant", "content": response})
            messages_a.append({"role": "user", "content": response})
            dialogue.append({
                'round': round_num + 1,
                'speaker': profile_b['name'],
                'speaker_token': token_b,
                'content': response
            })

    return jsonify({
        'topic': topic,
        'dialogue': dialogue,
        'user_a': {'token': token_a, 'name': profile_a['name']},
        'user_b': {'token': token_b, 'name': profile_b['name']},
    })


def _call_deepseek(system_prompt, topic, speaker_history, listener_history, is_first):
    """调用 DeepSeek API"""
    if not deepseek_client:
        raise RuntimeError("DeepSeek API Key 未配置，请设置 DEEPSEEK_API_KEY 环境变量")

    messages = [{"role": "system", "content": system_prompt}]

    if is_first:
        messages.append({
            "role": "user",
            "content": f"话题讨论：{topic}\n\n请以你的身份，针对这个话题发表看法。这是开场发言。"
        })
    else:
        # 按轮次交替排列历史对话：自己说的=assistant，对方说的=user
        recent_speaker = speaker_history[-2:]
        recent_listener = listener_history[-2:]
        for i in range(max(len(recent_speaker), len(recent_listener))):
            if i < len(recent_speaker):
                messages.append({"role": "assistant", "content": recent_speaker[i]['content']})
            if i < len(recent_listener):
                messages.append({"role": "user", "content": recent_listener[i]['content']})
        messages.append({
            "role": "user",
            "content": f"继续讨论话题：{topic}\n\n请回应对方的观点，并表达你的看法。"
        })

    try:
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            max_tokens=300,
            temperature=0.8
        )
        return _strip_md(response.choices[0].message.content)
    except Exception as e:
        return f"[API 调用失败: {str(e)}]"


def _strip_md(text):
    """去除 markdown 格式标记"""
    if not text:
        return ''
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    text = re.sub(r'~~(.*?)~~', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    return text.strip()


def _generate_roundtable_summary(topic, discussion):
    if not discussion:
        return _local_roundtable_summary(topic, discussion)
    if deepseek_client:
        try:
            contents = '\n'.join([f"{d['speaker']}: {d['content']}" for d in discussion[:20]])
            prompt = f"""基于以下圆桌讨论，生成结构化总结：

话题：{topic}

讨论记录：
{contents}

请以 JSON 格式返回（不要 markdown 代码块），包含以下字段：
- consensus: 主要共识（1-2句话）
- disagreements: 关键分歧（数组，每条1句话）
- article_angles: 可写成文章的角度（数组，3个）
- engagement_questions: 适合评论区互动的问题（数组，3个）
- viral_quote: 最有传播力的一句话

注意：所有文本内容不要使用 markdown 格式（不要用 **加粗**、*斜体* 等），直接用纯文本。
"""
            response = deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=600,
                temperature=0.7
            )
            text = response.choices[0].message.content.strip()
            if text.startswith('```'):
                text = text.split('```')[1].replace('json', '').strip()
            parsed = json.loads(text)
            return {
                'consensus': _strip_md(parsed.get('consensus', '')),
                'disagreements': [_strip_md(d) for d in parsed.get('disagreements', [])],
                'article_angles': [_strip_md(a) for a in parsed.get('article_angles', [])],
                'engagement_questions': [_strip_md(q) for q in parsed.get('engagement_questions', [])],
                'viral_quote': _strip_md(parsed.get('viral_quote', '')),
                'source': 'llm',
            }
        except Exception:
            pass
    return _local_roundtable_summary(topic, discussion)


def _local_roundtable_summary(topic, discussion):
    speakers = list(set(d['speaker'] for d in discussion))
    if discussion:
        viral = max(discussion, key=lambda x: len(x['content']))['content'][:80] + '...'
    else:
        viral = f"关于「{topic}」，最值得关注的是它还没有标准答案。"
    return {
        'consensus': f"参与讨论的 {len(speakers)} 位 Agent 围绕「{topic}」交换了观点，认为这是一个值得持续关注的议题。",
        'disagreements': [
            f"不同参与者对「{topic}」的紧迫性判断存在差异。",
            "技术实现路径与伦理考量之间仍需更多对话。"
        ] if len(discussion) >= 4 else ["讨论尚在进行中，更多分歧有待呈现。"],
        'article_angles': [
            f"从实践者视角看「{topic}」的真实影响",
            f"「{topic}」背后的深层逻辑与长期趋势",
            "如果让不同立场的人各说一段话，会得到什么"
        ],
        'engagement_questions': [
            f"你对「{topic}」的第一反应是什么？",
            "如果你必须选一个立场，你会站在哪边？",
            "这个话题在你的实际工作/生活中有对应场景吗？"
        ],
        'viral_quote': viral,
        'source': 'local',
    }


def _build_local_inspire(topic, heat_data=None):
    base = {
        'topic': topic,
        'titles': [
            f"如何看待「{topic}」？这可能是目前最完整的分析",
            f"「{topic}」背后，有哪些没人敢说的事实？",
            f"亲身经历：我是怎么理解「{topic}」的",
            f"深度拆解「{topic}」：3 个角度，5 个结论",
            f"关于「{topic}」，我和一位从业者聊了一下午",
        ],
        'outline': [
            "一、现象回顾：这个话题为什么现在火了",
            "二、核心争议：支持方与质疑方各自的理由",
            "三、深层原因：为什么这个问题难以达成共识",
            "四、我的判断：基于现有信息的理性推演",
            "五、开放讨论：还有几个值得追问的问题",
        ],
        'pro_viewpoints': [
            "这一趋势代表了效率和体验的双重升级，早期采用者已经验证了价值。",
            "从长期来看，技术成熟后成本会大幅下降，惠及更多普通用户。",
            "相关基础设施正在快速完善，生态门槛比想象中更低。",
        ],
        'con_viewpoints': [
            "目前宣传的效果与真实落地之间仍有明显差距，需要警惕过度包装。",
            "隐私、安全和伦理问题尚未得到充分讨论，可能带来隐性成本。",
            "对既有利益格局的冲击可能被低估，推进速度需要与社会承受力匹配。",
        ],
        'quotes': [
            "每一个看似简单的选择，背后都是复杂利益的博弈。",
            "技术本身没有立场，但使用技术的人总有偏好。",
            f"关于「{topic}」，最大的风险不是做错，而是从未认真思考过。",
        ],
        'draft': f"""最近「{topic}」在知乎上讨论很多，我也来说几句。

先说结论：这不是一个非黑即白的问题，而是一个「取决于你怎么看」的问题。

从积极的一面看，这个话题确实切中了当下很多人的痛点。无论是效率焦虑还是信息过载，大家都希望有一个更优解。而目前的方案至少在部分场景下已经证明了它的价值。

但从审慎的角度，我也想提醒几点。第一，任何新技术都有蜜月期和幻灭期，现在可能还在前者。第二，真实世界的复杂度远超实验室，规模化落地的挑战才刚刚开始。第三，也是最常被忽略的——技术变革的速度和社会接受的速度往往不匹配。

我的建议是：保持关注，但不必焦虑。如果你是从业者，深耕一个细分场景比追逐概念更有价值；如果你是普通用户，让子弹再飞一会儿，等第一批坑被踩完再入场也不迟。

最后抛一个问题：如果是你，你会选择现在入场，还是再等一年？欢迎在评论区聊聊你的真实想法。""",
        'source': 'local',
        'heat_analysis': heat_data or {
            'total_discussions': '本地数据检索中...',
            'avg_engagement': '基于社区互动估算',
            'trend': '近期讨论热度呈上升趋势',
            'peak_time': '工作日晚间 20:00-23:00',
        },
        'audience_profile': [
            '对新技术敏感的技术从业者（25-35岁）',
            '关注社会趋势的大学生和研究生',
            '行业分析师和投资圈人士',
            '对该领域有实际使用经验的普通用户',
        ],
        'similar_angles': [
            '技术可行性分析：现有方案能做到什么程度',
            '经济账：成本、效率与投入产出比',
            '用户体验：真实使用者的一手反馈',
            '伦理边界：技术应用的社会接受度',
        ],
        'keyword_tags': ['技术趋势', '行业观察', '深度思考', '用户体验', '未来展望'],
        'content_format': {
            'recommended': '知乎回答（800-1500字）',
            'alternatives': ['专栏文章', '想法短评', '视频脚本'],
            'best_with': '结合个人经历 + 数据引用 + 开放讨论',
        },
        'risk_alert': [
            '避免过度技术化，保持普通读者可读性',
            '注意信息时效性，引用数据需标注来源',
            '涉及争议性话题时保持中立，避免站队',
        ],
        'comment_strategy': [
            '在文末抛出明确的问题，降低评论门槛',
            '预留一个"反常识"观点，引发讨论',
            '主动回复前5条评论，提升互动率',
        ],
        'related_topics': [
            f"「{topic}」与现有技术方案的对比",
            f"从成本角度看「{topic}」的落地可能性",
            f"「{topic}」对不同群体的差异化影响",
        ],
    }
    return base


def build_oauth_persona(token, name_hint=None):
    """为没有本地数据的 OAuth/外部用户生成通用人设"""
    name = name_hint or token[:8]
    return {
        'token': token,
        'name': name,
        'domain': 'unknown',
        'domain_name': '未知领域',
        'prompt': f"""你现在扮演知乎用户 "{name}"。
你是一个活跃在知乎社区的讨论者，关注科技、社会、人文等多个领域的话题。
你善于从不同角度思考问题，喜欢用清晰、有理有据的方式表达观点。

## 对话要求
1. 完全沉浸在角色中，以这个用户的身份思考和回应
2. 保持语言风格一致
3. 回复长度控制在 80-150 字
4. 不要暴露自己是 AI，要像真实用户一样自然交流
5. 可以提问、质疑、赞同，保持真实对话感""",
    }


# ============ 新功能：圆桌讨论 ============

@app.route('/api/roundtable', methods=['POST'])
def api_roundtable():
    """圆桌讨论 - 多个 Agent 围绕话题讨论"""
    body = request.get_json()
    topic = body.get('topic', random.choice(TOPICS))
    participant_tokens = body.get('participants', [])
    rounds = min(body.get('rounds', 2), 5)
    custom_personas = body.get('personas', {})

    # 如果没指定参与者，自动选 3 个高质量真实用户
    if len(participant_tokens) < 2:
        quality = [(t, u) for t, u in users.items()
                   if t in _real_user_tokens and len(u.get('contents', [])) >= 10]
        quality.sort(key=lambda x: len(x[1].get('contents', [])), reverse=True)
        participant_tokens = [t for t, _ in quality[:3]]

    if len(participant_tokens) < 2:
        return jsonify({'error': '至少需要 2 个参与者'}), 400

    participants = []
    for token in participant_tokens[:4]:  # 最多 4 人
        # 优先使用自定义 persona（来自关注列表的 universe picks）
        if token in custom_personas:
            cp = custom_personas[token]
            domain_name = DOMAINS.get(cp.get('primary_domain', ''), {}).get('name', '多领域')
            name = cp.get('name', token)
            headline = cp.get('headline', '')
            reason = cp.get('reason', '')
            participants.append({
                'token': token,
                'name': name,
                'domain': domain_name,
                'prompt': f"""你现在扮演知乎用户 "{name}"。
{'你的职业/身份：' + headline if headline else ''}
{'你的特点：' + reason if reason else ''}
你善于从不同角度思考问题，喜欢用清晰、有理有据的方式表达观点。

## 对话要求
1. 完全沉浸在角色中，以这个用户的身份思考和回应
2. 保持语言风格一致
3. 回复长度控制在 80-150 字
4. 不要暴露自己是 AI，要像真实用户一样自然交流
5. 可以提问、质疑、赞同，保持真实对话感""",
            })
        else:
            profile = get_user_profile(token)
            if profile:
                participants.append({
                    'token': token,
                    'name': profile['name'],
                    'domain': profile['primary_domain_name'],
                    'prompt': build_persona_prompt(token),
                })
            else:
                # OAuth 用户或没有本地数据的用户，使用通用人设
                participants.append(build_oauth_persona(token))

    if len(participants) < 2:
        return jsonify({'error': '有效参与者不足'}), 400

    # 生成圆桌讨论
    discussion = []
    all_history = []  # 公共对话历史

    for round_num in range(rounds):
        for p in participants:
            # 构建上下文：包含所有人之前的发言
            context_msgs = []
            for hist in all_history[-6:]:  # 最近 6 条
                context_msgs.append(f"[{hist['speaker']}]: {hist['content']}")

            context_str = '\n'.join(context_msgs) if context_msgs else '（讨论刚刚开始）'

            prompt = f"""你正在参加一个圆桌讨论。

话题：{topic}

讨论历史：
{context_str}

请以你的身份发表看法。要求：
1. 回应之前发言者的观点（如果有的话）
2. 提出你自己的独特见解
3. 回复 80-150 字
4. 保持自然对话感"""

            messages = [
                {"role": "system", "content": p['prompt']},
                {"role": "user", "content": prompt}
            ]

            if not deepseek_client:
                content = "[DeepSeek API 未配置。如需启用 AI 生成，请设置 DEEPSEEK_API_KEY 环境变量并重启服务器]"
            else:
                try:
                    response = deepseek_client.chat.completions.create(
                        model="deepseek-chat",
                        messages=messages,
                        max_tokens=250,
                        temperature=0.85
                    )
                    content = _strip_md(response.choices[0].message.content)
                except Exception as e:
                    content = f"[API 调用失败: {str(e)[:100]}]"

            entry = {
                'round': round_num + 1,
                'speaker': p['name'],
                'speaker_token': p['token'],
                'content': content
            }
            discussion.append(entry)
            all_history.append(entry)

    # 检查是否有 API 错误
    has_api_error = any('[API 调用失败' in d['content'] or '未配置' in d['content'] for d in discussion)

    summary = _generate_roundtable_summary(topic, discussion)
    resp = jsonify({
        'topic': topic,
        'participants': [{'token': p['token'], 'name': p['name'], 'domain': p['domain']} for p in participants],
        'discussion': discussion,
        'summary': summary,
    })
    if has_api_error:
        resp.status_code = 207  # Multi-Status: 部分成功
    return resp


# ============ 用户搜索 ============

@app.route('/api/search_users')
def api_search_users():
    """搜索已采集的用户"""
    q = request.args.get('q', '').strip()
    if not q or len(q) < 1:
        return jsonify({'users': []})

    q_lower = q.lower()
    results = []
    for token in _real_user_tokens:
        user = users.get(token, {})
        name = user.get('name', token)
        if q_lower in name.lower() or q_lower in token.lower():
            results.append({
                'token': token,
                'name': name,
                'content_count': len(user.get('contents', [])),
                'post_count': user.get('post_count', 0),
                'comment_count': user.get('comment_count', 0),
            })

    results.sort(key=lambda x: x['content_count'], reverse=True)
    return jsonify({'users': results[:20]})


# ============ 灵感引擎 ============

@app.route('/api/inspire', methods=['POST'])
def api_inspire():
    """灵感引擎 - 基于热点生成创作素材"""
    body = request.get_json()
    topic = body.get('topic', '')
    if not topic:
        return jsonify({'error': '请提供话题'}), 400

    # 基于本地数据的热度分析
    topic_lower = topic.lower()
    related_posts = []
    for post in posts:
        content = post.get('content', '')
        if any(word in content.lower() for word in re.findall(r'[\w\u4e00-\u9fff]{2,}', topic_lower)[:5]):
            related_posts.append(post)

    heat_data = {
        'total_discussions': len(related_posts),
        'avg_likes': round(sum(int(p.get('like_num', 0)) for p in related_posts) / max(len(related_posts), 1), 1),
        'avg_comments': round(sum(int(p.get('comment_num', 0)) for p in related_posts) / max(len(related_posts), 1), 1),
        'trend': '近期讨论热度呈上升趋势' if len(related_posts) > 5 else '话题较为冷门，适合抢先占位',
        'peak_time': '工作日晚间 20:00-23:00',
    }

    if deepseek_client:
        try:
            prompt = f"""你是一位资深知乎内容策划。针对以下热点，为创作者提供完整的内容灵感包。

热点：{topic}

本地数据参考：该话题在社区中已有 {heat_data['total_discussions']} 条相关讨论，平均获赞 {heat_data['avg_likes']}，平均评论 {heat_data['avg_comments']}。

请返回 JSON 格式（不要 markdown 代码块），包含：
- titles: 5 个知乎风格标题（数组）
- outline: 文章提纲（数组，每个元素是一个要点字符串）
- pro_viewpoints: 正方观点（数组，3条）
- con_viewpoints: 反方观点（数组，3条）
- quotes: 3 条金句（数组）
- draft: 800 字知乎回答草稿（字符串）
- heat_analysis: 热度分析对象，包含 total_discussions, avg_engagement, trend, peak_time
- audience_profile: 受众画像数组（4-5条）
- similar_angles: 已有高赞回答角度数组（4条）
- keyword_tags: SEO关键词数组（5个）
- content_format: 内容形式建议对象，包含 recommended, alternatives, best_with
- risk_alert: 风险提醒数组（3条）
- comment_strategy: 评论区互动策略数组（3条）
- related_topics: 相关延伸话题数组（3条）

要求：
1. 标题要有知乎感（带问号、对比、数字、悬念）
2. 提纲清晰，适合展开成长文
3. 正方反方要有真实论据感
4. 金句适合单独截图传播
5. 草稿用第一人称，有经历感，结尾引导互动
6. 热度分析要基于提供的本地数据
"""
            if not deepseek_client:
                return jsonify(_build_local_inspire(topic, heat_data))
            response = deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.8
            )
            text = response.choices[0].message.content.strip()
            if text.startswith('```'):
                text = text.split('```')[1].replace('json', '').strip()
            parsed = json.loads(text)
            return jsonify({
                'topic': topic,
                'titles': parsed.get('titles', []),
                'outline': parsed.get('outline', []),
                'pro_viewpoints': parsed.get('pro_viewpoints', []),
                'con_viewpoints': parsed.get('con_viewpoints', []),
                'quotes': parsed.get('quotes', []),
                'draft': parsed.get('draft', ''),
                'heat_analysis': parsed.get('heat_analysis', heat_data),
                'audience_profile': parsed.get('audience_profile', []),
                'similar_angles': parsed.get('similar_angles', []),
                'keyword_tags': parsed.get('keyword_tags', []),
                'content_format': parsed.get('content_format', {}),
                'risk_alert': parsed.get('risk_alert', []),
                'comment_strategy': parsed.get('comment_strategy', []),
                'related_topics': parsed.get('related_topics', []),
                'source': 'llm',
            })
        except Exception:
            pass

    return jsonify(_build_local_inspire(topic, heat_data))


# ============ 引力场 ============

@app.route('/api/gravity_field', methods=['POST'])
def api_gravity_field():
    """引力场 - 输入热点/选题，推荐最适合讨论的用户"""
    body = request.get_json()
    topic = body.get('topic', '')
    if not topic:
        return jsonify({'error': '请提供话题'}), 400

    topic_lower = topic.lower()
    topic_domain = infer_domain_from_text(topic)
    scored = []

    for token in _real_user_tokens:
        user = users.get(token, {})
        contents = user.get('contents', [])
        if not contents:
            continue

        joined = ' '.join(contents[:20]).lower()
        text_overlap = sum(1 for word in re.findall(r'[\w\u4e00-\u9fff]{2,}', topic_lower)[:20] if word in joined)

        profile = get_user_profile(token)
        user_domain = profile['primary_domain'] if profile else 'unknown'
        domain_match = 1.0 if topic_domain == user_domain else 0.3

        avg_len = sum(len(c) for c in contents) / max(len(contents), 1)
        quality_score = min(avg_len / 200, 1.0) * 0.5 + min(len(contents), 50) / 50 * 0.5

        style = get_user_style(token)
        total_score = text_overlap * 2 + domain_match * 10 + quality_score * 5

        reasons = []
        if text_overlap > 0:
            reasons.append('内容相似')
        if topic_domain == user_domain:
            reasons.append('领域相关')
        if avg_len > 150:
            reasons.append('历史发言质量高')
        if style['type'] == 'humanist':
            reasons.append('观点互补')
        elif style['type'] == 'tech':
            reasons.append('技术视角')

        if total_score > 5:
            scored.append({
                'token': token,
                'name': user.get('name', token),
                'score': round(total_score, 2),
                'reasons': reasons[:3],
                'content_count': len(contents),
            })

    scored.sort(key=lambda x: x['score'], reverse=True)

    invite = []
    collide = []
    for i, s in enumerate(scored[:20]):
        token = s['token']
        user = users.get(token, {})
        contents = user.get('contents', [])
        # 找与话题最相关的 2 条历史发言
        related_contents = []
        for c in contents:
            overlap = sum(1 for word in re.findall(r'[\w\u4e00-\u9fff]{2,}', topic_lower)[:10] if word in c.lower())
            if overlap > 0:
                related_contents.append((overlap, c))
        related_contents.sort(key=lambda x: x[0], reverse=True)
        top_contents = [c[:120] + '...' if len(c) > 120 else c for _, c in related_contents[:2]]

        # 计算详细分数
        profile = get_user_profile(token)
        user_domain = profile['primary_domain'] if profile else 'unknown'
        style = get_user_style(token)

        enriched = {
            **s,
            'top_contents': top_contents,
            'primary_domain': DOMAINS.get(user_domain, {}).get('name', '未归类'),
            'domain_emoji': DOMAINS.get(user_domain, {}).get('emoji', '❓'),
            'style_type': style.get('type', 'unknown'),
            'style_traits': style.get('traits', ''),
            'avg_content_len': round(sum(len(c) for c in contents) / max(len(contents), 1)),
        }
        if i < 8:
            invite.append(enriched)
        else:
            collide.append(enriched)

    return jsonify({
        'topic': topic,
        'topic_domain': DOMAINS.get(topic_domain, {}).get('name', '未归类'),
        'topic_domain_emoji': DOMAINS.get(topic_domain, {}).get('emoji', '❓'),
        'invite': invite,
        'collision': collide,
    })


# ============ 圆桌讨论追加轮次 ============

@app.route('/api/roundtable_extend', methods=['POST'])
def api_roundtable_extend():
    """追加一轮圆桌讨论"""
    body = request.get_json()
    topic = body.get('topic', '')
    participant_tokens = body.get('participants', [])
    existing_discussion = body.get('discussion', [])

    if not topic or len(participant_tokens) < 2:
        return jsonify({'error': '参数不足'}), 400

    participants = []
    for token in participant_tokens[:4]:
        profile = get_user_profile(token)
        if profile:
            participants.append({
                'token': token,
                'name': profile['name'],
                'domain': profile['primary_domain_name'],
                'prompt': build_persona_prompt(token),
            })
        else:
            participants.append(build_oauth_persona(token))

    if len(participants) < 2:
        return jsonify({'error': '有效参与者不足'}), 400

    current_round = max((d.get('round', 0) for d in existing_discussion), default=0) + 1
    all_history = existing_discussion[:]
    discussion = []

    for p in participants:
        context_msgs = []
        for hist in all_history[-6:]:
            context_msgs.append(f"[{hist['speaker']}]: {hist['content']}")
        context_str = '\n'.join(context_msgs) if context_msgs else '（讨论刚刚开始）'

        prompt = f"""你正在参加一个圆桌讨论。

话题：{topic}

讨论历史：
{context_str}

请以你的身份发表看法。要求：
1. 回应之前发言者的观点（如果有的话）
2. 提出你自己的独特见解
3. 回复 80-150 字
4. 保持自然对话感"""

        messages = [
            {"role": "system", "content": p['prompt']},
            {"role": "user", "content": prompt}
        ]

        if not deepseek_client:
            content = "[DeepSeek API 未配置。如需启用 AI 生成，请设置 DEEPSEEK_API_KEY 环境变量并重启服务器]"
        else:
            try:
                response = deepseek_client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                    max_tokens=250,
                    temperature=0.85
                )
                content = _strip_md(response.choices[0].message.content)
            except Exception as e:
                content = f"[API 调用失败: {str(e)[:100]}]"

        entry = {
            'round': current_round,
            'speaker': p['name'],
            'speaker_token': p['token'],
            'content': content
        }
        discussion.append(entry)
        all_history.append(entry)

    has_api_error = any('[API 调用失败' in d['content'] or '未配置' in d['content'] for d in discussion)

    summary = _generate_roundtable_summary(topic, discussion)
    resp = jsonify({
        'topic': topic,
        'participants': [{'token': p['token'], 'name': p['name'], 'domain': p['domain']} for p in participants],
        'discussion': discussion,
        'round': current_round,
        'summary': summary,
    })
    if has_api_error:
        resp.status_code = 207
    return resp


# ============ 辩论模式 ============

@app.route('/api/debate', methods=['POST'])
def api_debate():
    """辩论模式 - 两个 Agent 持对立观点辩论"""
    body = request.get_json()
    topic = body.get('topic', '')
    token_a = body.get('user_a')
    token_b = body.get('user_b')
    rounds = min(body.get('rounds', 3), 5)

    if not topic:
        return jsonify({'error': '请提供辩论话题'}), 400
    if not token_a or not token_b:
        return jsonify({'error': '请提供双方参与者'}), 400
    if token_a == token_b:
        return jsonify({'error': '辩论需要两个不同的参与者'}), 400

    profile_a = get_user_profile(token_a)
    profile_b = get_user_profile(token_b)
    if not profile_a or not profile_b:
        return jsonify({'error': '用户不存在'}), 404

    participants = []
    for token, profile in [(token_a, profile_a), (token_b, profile_b)]:
        user = users.get(token, {})
        if user:
            participants.append({
                'token': token,
                'name': profile['name'],
                'domain': profile['primary_domain_name'],
                'prompt': build_persona_prompt(token),
            })
        else:
            participants.append(build_oauth_persona(token, profile['name']))

    discussion = []
    all_history = []

    for round_num in range(rounds):
        for idx, p in enumerate(participants):
            stance = '正方（支持）' if idx == 0 else '反方（反对）'
            context_msgs = []
            for hist in all_history[-6:]:
                side = '正方' if hist['speaker_token'] == token_a else '反方'
                context_msgs.append(f"[{side} {hist['speaker']}]: {hist['content']}")
            context_str = '\n'.join(context_msgs) if context_msgs else '（辩论即将开始）'

            prompt = f"""你正在参加一场辩论。

辩题：{topic}

你的立场：{stance}

辩论记录：
{context_str}

请以你的身份发表辩论观点。要求：
1. 明确表达你的立场（支持或反对）
2. 回应对方的论点并进行反驳
3. 提出有力的论据和例证
4. 回复 100-200 字
5. 保持理性辩论的风度"""

            messages = [
                {"role": "system", "content": p['prompt']},
                {"role": "user", "content": prompt}
            ]

            if not deepseek_client:
                content = f"[DeepSeek API 未配置，无法生成辩论内容]"
            else:
                try:
                    response = deepseek_client.chat.completions.create(
                        model="deepseek-chat",
                        messages=messages,
                        max_tokens=350,
                        temperature=0.9
                    )
                    content = _strip_md(response.choices[0].message.content)
                except Exception as e:
                    content = f"[API 调用失败: {str(e)[:100]}]"

            entry = {
                'round': round_num + 1,
                'speaker': p['name'],
                'speaker_token': p['token'],
                'stance': stance,
                'content': content
            }
            discussion.append(entry)
            all_history.append(entry)

    has_api_error = any('[API 调用失败' in d['content'] or '未配置' in d['content'] for d in discussion)

    # 生成辩论总结
    summary = _generate_debate_summary(topic, discussion)

    resp = jsonify({
        'topic': topic,
        'participants': [
            {'token': token_a, 'name': profile_a['name'], 'stance': '正方（支持）'},
            {'token': token_b, 'name': profile_b['name'], 'stance': '反方（反对）'},
        ],
        'discussion': discussion,
        'summary': summary,
    })
    if has_api_error:
        resp.status_code = 207
    return resp


def _generate_debate_summary(topic, discussion):
    """生成辩论总结"""
    if not discussion:
        return {'source': 'local'}

    if deepseek_client:
        try:
            contents = '\n'.join([f"[{d['stance']}] {d['speaker']}: {d['content']}" for d in discussion[:20]])
            prompt = f"""基于以下辩论，生成结构化总结：

辩题：{topic}

辩论记录：
{contents}

请以 JSON 格式返回（不要 markdown 代码块），包含以下字段：
- result: 辩论结果概述（1-2句话）
- pro_strengths: 正方论点优势（数组，2-3条）
- con_strengths: 反方论点优势（数组，2-3条）
- key_clash: 核心争议焦点（数组，2-3条）
- judge_comment: 评委点评（1-2句话）
- viral_quote: 最有传播力的一句话

注意：所有文本内容不要使用 markdown 格式（不要用 **加粗**、*斜体* 等），直接用纯文本。
"""
            response = deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.7
            )
            text = response.choices[0].message.content.strip()
            if text.startswith('```'):
                text = text.split('```')[1].replace('json', '').strip()
            parsed = json.loads(text)
            return {
                'result': _strip_md(parsed.get('result', '')),
                'pro_strengths': [_strip_md(s) for s in parsed.get('pro_strengths', [])],
                'con_strengths': [_strip_md(s) for s in parsed.get('con_strengths', [])],
                'key_clash': [_strip_md(c) for c in parsed.get('key_clash', [])],
                'judge_comment': _strip_md(parsed.get('judge_comment', '')),
                'viral_quote': _strip_md(parsed.get('viral_quote', '')),
                'source': 'llm',
            }
        except Exception:
            pass

    # 本地兜底
    pro_msgs = [d for d in discussion if d.get('stance', '').startswith('正方')]
    con_msgs = [d for d in discussion if d.get('stance', '').startswith('反方')]
    return {
        'result': f'围绕「{topic}」，正反双方进行了 {len(discussion)} 轮辩论，各有精彩论点。',
        'pro_strengths': [m['content'][:60] + '...' for m in pro_msgs[:2]],
        'con_strengths': [m['content'][:60] + '...' for m in con_msgs[:2]],
        'key_clash': [f'对「{topic}」的核心分歧在于价值判断和事实认知的差异'],
        'judge_comment': '双方都展现了扎实的论证能力，辩论富有建设性。',
        'viral_quote': max(discussion, key=lambda x: len(x['content']))['content'][:80] + '...',
        'source': 'local',
    }


# ============ OAuth 状态检测 ============

@app.route('/api/oauth_status')
def api_oauth_status():
    """检查 OAuth 配置状态"""
    app_id = ZHIHU_OAUTH_APP_ID
    return jsonify({
        'oauth_configured': bool(app_id and ZHIHU_OAUTH_APP_KEY),
        'suspicious_credentials': False,
        'logged_in': bool(session.get('access_token')),
        'user': session.get('zhihu_user') if session.get('access_token') else None,
        'last_oauth': session.get('oauth_last') or OAUTH_LAST_EVENT,
        'redirect_uri': ZHIHU_OAUTH_REDIRECT_URI,
        'app_id_prefix': app_id[:4] + '...' if app_id and len(app_id) > 4 else app_id,
    })


@app.route('/api/oauth_debug')
def api_oauth_debug():
    return jsonify({
        'logged_in': bool(session.get('access_token')),
        'session_oauth': session.get('oauth_last'),
        'global_oauth': OAUTH_LAST_EVENT,
        'redirect_uri': ZHIHU_OAUTH_REDIRECT_URI,
        'app_id_prefix': ZHIHU_OAUTH_APP_ID[:4] + '...' if ZHIHU_OAUTH_APP_ID and len(ZHIHU_OAUTH_APP_ID) > 4 else ZHIHU_OAUTH_APP_ID,
    })


# ============ 新功能：数据分析仪表盘 ============

@app.route('/api/dashboard')
def api_dashboard():
    """数据分析仪表盘数据 - 清洗后真实用户视角"""

    # 数据清洗摘要
    raw_user_count = len(users)
    bot_count = sum(1 for u in users.values() if is_bot_user(u.get('name', '')))
    real_user_count = len(_real_user_tokens)

    # 1. 用户活跃度分布（仅真实用户）
    user_activity = []
    for token in _real_user_tokens:
        user = users.get(token, {})
        content_count = len(user.get('contents', []))
        if content_count > 0:
            user_activity.append(content_count)

    # 2. 领域热度（每条内容只归一个主领域，unknown 单独统计）
    domain_heat = {'unknown': {'name': '未归类', 'emoji': '❓', 'count': 0}}
    for domain_id, domain_info in DOMAINS.items():
        domain_heat[domain_id] = {
            'name': domain_info['name'],
            'emoji': domain_info['emoji'],
            'count': 0
        }

    for token in _real_user_tokens:
        user = users.get(token, {})
        seen_contents = set()
        for c in user.get('contents', []):
            prefix = c[:60].strip()
            if prefix in seen_contents or len(prefix) < 5:
                continue
            seen_contents.add(prefix)
            domain_id = infer_domain_from_text(c)
            domain_heat[domain_id]['count'] += 1

    # 3. 隐藏同好引力分布
    gravity_dist = {'high': 0, 'medium': 0, 'low': 0}
    for pair in hidden_pairs:
        g = pair['gravity']
        if g > 0.7:
            gravity_dist['high'] += 1
        elif g > 0.5:
            gravity_dist['medium'] += 1
        else:
            gravity_dist['low'] += 1

    # 4. 聚类统计
    clusters = gravity_results.get('clusters', 0)

    # 5. 互动网络统计（仅真实用户之间）
    total_interactions = 0
    for source, targets in interaction_matrix.items():
        if source not in _real_user_tokens:
            continue
        for target in targets:
            if isinstance(target, dict):
                target_token = target.get('token', target.get('user_token', ''))
            elif isinstance(target, str):
                target_token = target
            else:
                continue
            if target_token in _real_user_tokens:
                total_interactions += 1
    avg_interactions = total_interactions / max(real_user_count, 1)

    # 6. 内容长度分布（仅真实用户）
    content_lengths = []
    for token in _real_user_tokens:
        user = users.get(token, {})
        for c in user.get('contents', []):
            content_lengths.append(len(c))

    # 7. Top 活跃用户（仅真实用户，已去重）
    top_users = []
    for token in _real_user_tokens:
        user = users.get(token, {})
        top_users.append({
            'name': user.get('name', token),
            'content_count': len(user.get('contents', [])),
            'post_count': user.get('post_count', 0),
            'comment_count': user.get('comment_count', 0),
        })
    top_users.sort(key=lambda x: x['content_count'], reverse=True)

    # 8. 引力网络图数据（top pairs）
    network_nodes = set()
    network_edges = []
    for pair in hidden_pairs[:20]:
        network_nodes.add(pair['user_a_name'])
        network_nodes.add(pair['user_b_name'])
        network_edges.append({
            'source': pair['user_a_name'],
            'target': pair['user_b_name'],
            'gravity': round(pair['gravity'], 3)
        })

    # 9. Agent 互动次数
    agent_interactions = len(a2a_dialogues)

    # 10. 热点选题分布（基于当前本地热点）
    hot_items = build_local_hot_items(limit=50)
    hot_domain_counts = {}
    for item in hot_items:
        d = item.get('domain', 'unknown')
        hot_domain_counts[d] = hot_domain_counts.get(d, 0) + 1

    return jsonify({
        'overview': {
            'total_users': raw_user_count,
            'bot_filtered': bot_count,
            'real_users': real_user_count,
            'total_posts': len(posts),
            'total_comments': len(comments),
            'total_interactions': total_interactions,
            'avg_interactions': round(avg_interactions, 1),
            'hidden_pairs_count': len(hidden_pairs),
            'quality_users': len([t for t in _real_user_tokens if len(users.get(t, {}).get('contents', [])) >= 10]),
            'agent_interactions': agent_interactions,
        },
        'user_activity': user_activity,
        'domain_heat': domain_heat,
        'gravity_distribution': gravity_dist,
        'cluster_count': clusters,
        'content_length_stats': {
            'avg': round(sum(content_lengths) / max(len(content_lengths), 1)),
            'max': max(content_lengths) if content_lengths else 0,
            'min': min(content_lengths) if content_lengths else 0,
        },
        'top_users': top_users[:15],
        'hot_domain_counts': hot_domain_counts,
        'network': {
            'nodes': list(network_nodes),
            'edges': network_edges,
        }
    })


# ============ 知乎 OAuth 登录 ============

@app.route('/login')
def login():
    """跳转到知乎授权页面"""
    if not ZHIHU_OAUTH_APP_ID or not ZHIHU_OAUTH_APP_KEY:
        return redirect('/?login_error=oauth_not_configured')

    state = secrets.token_hex(16)
    session['oauth_state'] = state

    auth_url = "https://openapi.zhihu.com/authorize?" + urlencode({
        'redirect_uri': ZHIHU_OAUTH_REDIRECT_URI,
        'app_id': ZHIHU_OAUTH_APP_ID,
        'response_type': 'code',
        'state': state,
    })
    return redirect(auth_url)


@app.route('/logout')
def logout():
    """退出登录"""
    session.pop('access_token', None)
    session.pop('zhihu_user', None)
    return redirect('/')


@app.route('/api/me')
def api_me():
    """获取当前登录用户信息"""
    user = session.get('zhihu_user')
    if user:
        return jsonify({'logged_in': True, 'user': user})
    if session.get('access_token'):
        user = default_zhihu_user()
        session['zhihu_user'] = user
        return jsonify({'logged_in': True, 'user': user})
    return jsonify({'logged_in': False})


@app.route('/api/my_followers')
def api_my_followers():
    """获取我的粉丝列表"""
    access_token = session.get('access_token')
    if not access_token:
        return jsonify({'error': '未登录', 'users': []}), 401

    page = request.args.get('page', 0, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    try:
        resp = http_requests.get(
            f'https://openapi.zhihu.com/user/followers?page={page}&per_page={per_page}',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            users = data if isinstance(data, list) else data.get('data', data) if isinstance(data, dict) else []
            return jsonify({'users': users})
    except Exception:
        pass
    return jsonify({'error': '获取失败', 'users': []}), 500


@app.route('/api/my_followed')
def api_my_followed():
    """获取我的关注列表"""
    access_token = session.get('access_token')
    if not access_token:
        return jsonify({'error': '未登录', 'users': []}), 401

    page = request.args.get('page', 0, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    try:
        resp = http_requests.get(
            f'https://openapi.zhihu.com/user/followed?page={page}&per_page={per_page}',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            users = data if isinstance(data, list) else data.get('data', data) if isinstance(data, dict) else []
            return jsonify({'users': users})
    except Exception:
        pass
    return jsonify({'error': '获取失败', 'users': []}), 500


# ============ 我的知乎宇宙 ============

def _analyze_followed_user(u):
    """为一个关注者生成轻量画像"""
    text = ' '.join(filter(None, [
        u.get('fullname', ''),
        u.get('headline', ''),
        u.get('description', ''),
    ]))
    primary_domain = infer_domain_from_text(text)

    # 头像 URL 规范化：兼容多种字段名，相对路径补全域名
    raw_avatar = u.get('avatar_url') or u.get('avatar_path') or u.get('avatar') or ''
    if isinstance(raw_avatar, dict):
        raw_avatar = raw_avatar.get('url') or raw_avatar.get('path') or ''
    avatar = raw_avatar
    if avatar and avatar.startswith('//'):
        avatar = 'https:' + avatar
    elif avatar and not avatar.startswith('http'):
        avatar = 'https://pic1.zhimg.com' + avatar

    domain_scores = {}
    for domain_id, domain_info in DOMAINS.items():
        score = sum(1 for kw in domain_info['keywords'] if kw.lower() in text.lower())
        domain_scores[domain_id] = score

    total_kw = sum(domain_scores.values()) or 1
    normalized = {k: round(v / total_kw, 3) for k, v in domain_scores.items()}

    style_map = {
        'ai_tech': 'tech',
        'humanities': 'humanist',
        'creative': 'creator',
        'life': 'life',
        'society': 'observer',
    }
    style_type = style_map.get(primary_domain, 'unknown')

    domain_names = {k: v['name'] for k, v in DOMAINS.items()}
    why = f"关注领域为{domain_names.get(primary_domain, '未归类')}"

    return {
        'name': u.get('fullname', ''),
        'avatar': avatar,
        'headline': u.get('headline', ''),
        'url': u.get('url', ''),
        'uid': u.get('uid', ''),
        'hash_id': u.get('hash_id', ''),
        'primary_domain': primary_domain,
        'domain_scores': normalized,
        'style_type': style_type,
        'why_matched': why,
    }


def _extract_zhihu_user_list(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []

    if payload.get('code') in (401, 403):
        raise PermissionError(str(payload.get('data') or 'API Access Deny'))

    data_value = payload.get('data', payload.get('users', []))
    if isinstance(data_value, list):
        return data_value
    if isinstance(data_value, dict):
        for key in ('users', 'items', 'list', 'data'):
            value = data_value.get(key)
            if isinstance(value, list):
                return value
    if isinstance(data_value, str) and data_value:
        raise PermissionError(data_value)
    return []


def _demo_followed_users(limit=36):
    ranked_tokens = sorted(
        _real_user_tokens,
        key=lambda token: len(users.get(token, {}).get('contents', [])),
        reverse=True
    )
    demo_users = []
    for token in ranked_tokens[:limit]:
        user = users.get(token, {})
        contents = user.get('contents', [])[:4]
        demo_users.append({
            'uid': token,
            'hash_id': token,
            'fullname': user.get('name') or token,
            'headline': clean_hot_text(contents[0], 60) if contents else '知乎社区高质量创作者',
            'description': ' '.join(clean_hot_text(c, 80) for c in contents),
            'avatar_path': '',
            'url': '',
        })
    return demo_users


def _compute_filter_bubble_score(domain_distribution):
    """计算信息茧房指数 0-100，越高越集中"""
    total = sum(domain_distribution.values())
    if total == 0:
        return 0
    max_ratio = max(domain_distribution.values()) / total
    # 线性映射：max_ratio 0.2 -> 0分, 1.0 -> 100分
    score = int(max(0, min(100, (max_ratio - 0.2) / 0.8 * 100)))
    return score


def _generate_universe_insights(domain_distribution, bubble_score, followed_count):
    """生成洞察文案"""
    insights = []
    total = sum(domain_distribution.values()) or 1
    sorted_domains = sorted(domain_distribution.items(), key=lambda x: x[1], reverse=True)

    top_domain_id, top_count = sorted_domains[0]
    top_name = DOMAINS.get(top_domain_id, {}).get('name', '未归类')
    top_ratio = round(top_count / total * 100)

    if bubble_score < 30:
        insights.append('你的关注结构比较均衡，信息茧房风险较低。')
    elif bubble_score < 60:
        insights.append(f'你有明显兴趣中心（{top_name}占{top_ratio}%），但仍保留了跨域输入。')
    else:
        insights.append(f'你的关注高度集中在{top_name}（{top_ratio}%），建议加入破圈视角。')

    if followed_count > 0:
        insights.append(f'你关注了{followed_count}人，正在构建你的知乎宇宙。')

    zero_domains = [DOMAINS[did]['name'] for did, cnt in domain_distribution.items() if cnt == 0 and did != 'unknown']
    if zero_domains:
        insights.append(f'你的关注中缺少{"、".join(zero_domains[:2])}领域的视角。')

    return insights


def _pick_same_frequency(profiles, my_domain_dist, limit=5):
    """选出与当前用户兴趣最接近的关注者"""
    total = sum(my_domain_dist.values()) or 1
    my_top = max(my_domain_dist, key=my_domain_dist.get)

    scored = []
    for p in profiles:
        p_domain = p['primary_domain']
        # 同领域加分
        match_score = 0
        if p_domain == my_top:
            match_score += 50
        # 领域分布相似度
        for did in DOMAINS:
            my_ratio = my_domain_dist.get(did, 0) / total
            p_score = p['domain_scores'].get(did, 0)
            match_score += (1 - abs(my_ratio - p_score)) * 10
        scored.append((match_score, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, p in scored[:limit]:
        results.append({
            'name': p['name'],
            'avatar': p['avatar'],
            'headline': p['headline'],
            'primary_domain': p['primary_domain'],
            'match_score': round(score, 1),
            'reason': f"与你同属{DOMAINS.get(p['primary_domain'], {}).get('name', '该领域')}领域",
            'url': p['url'],
        })
    return results


def _pick_complementary(profiles, my_domain_dist, limit=5):
    """选出与主兴趣不同但能提供新视角的关注者"""
    total = sum(my_domain_dist.values()) or 1
    my_top = max(my_domain_dist, key=my_domain_dist.get)
    my_top_ratio = my_domain_dist.get(my_top, 0) / total

    scored = []
    for p in profiles:
        p_domain = p['primary_domain']
        # 不同领域加分
        complement_score = 0
        if p_domain != my_top and p_domain != 'unknown':
            complement_score += 40
            # 我的弱势领域是TA的强项，加分更多
            my_weak_ratio = my_domain_dist.get(p_domain, 0) / total
            complement_score += (1 - my_weak_ratio) * 30
        # 跨域能力
        non_zero = sum(1 for v in p['domain_scores'].values() if v > 0.1)
        complement_score += non_zero * 5
        scored.append((complement_score, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, p in scored[:limit]:
        results.append({
            'name': p['name'],
            'avatar': p['avatar'],
            'headline': p['headline'],
            'primary_domain': p['primary_domain'],
            'complement_score': round(score, 1),
            'reason': f"TA的{DOMAINS.get(p['primary_domain'], {}).get('name', '独特')}视角能补充你的认知盲区",
            'url': p['url'],
        })
    return results


def _pick_breakout(profiles, domain_distribution, limit=3):
    """选出低占比领域的人，用于打破信息茧房"""
    total = sum(domain_distribution.values()) or 1
    sorted_domains = sorted(domain_distribution.items(), key=lambda x: x[1])

    results = []
    for domain_id, count in sorted_domains:
        if domain_id == 'unknown':
            continue
        ratio = count / total
        if ratio > 0.2:
            continue
        # 找这个领域的关注者
        for p in profiles:
            if p['primary_domain'] == domain_id and len(results) < limit:
                domain_name = DOMAINS.get(domain_id, {}).get('name', '该领域')
                reason_templates = [
                    f'你的关注中{domain_name}类较少，TA能补充真实经验视角',
                    f'你的关注集中在{DOMAINS.get(sorted_domains[-1][0], {}).get("name", "主流")}领域，TA的{domain_name}表达能提供反向启发',
                ]
                results.append({
                    'name': p['name'],
                    'avatar': p['avatar'],
                    'headline': p['headline'],
                    'primary_domain': p['primary_domain'],
                    'reason': random.choice(reason_templates),
                    'url': p['url'],
                })
                break

    return results


def _pick_roundtable_candidates(profiles, limit=4):
    """选出适合发起圆桌的人"""
    # 按内容多样性排序
    scored = []
    for p in profiles:
        non_zero = sum(1 for v in p['domain_scores'].values() if v > 0.1)
        scored.append((non_zero, p))
    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for _, p in scored[:limit]:
        results.append({
            'name': p['name'],
            'avatar': p['avatar'],
            'headline': p['headline'],
            'primary_domain': p['primary_domain'],
            'reason': f"擅长{DOMAINS.get(p['primary_domain'], {}).get('name', '多领域')}，适合深度讨论",
            'url': p['url'],
        })
    return results


@app.route('/api/my_zhihu_universe')
def api_my_zhihu_universe():
    """我的知乎宇宙 - 基于关注列表的个人化分析"""
    access_token = session.get('access_token')
    if not access_token:
        return jsonify({'error': '未登录，请先登录知乎连接你的关注网络', 'logged_in': False}), 401

    zhihu_user = session.get('zhihu_user', {})

    # 获取关注列表（分页拉取所有）
    all_followed = []
    permission_limited = False
    source_note = '已读取你的知乎关注列表'
    page = 0
    per_page = 30
    max_pages = 10  # 安全上限

    while page < max_pages:
        try:
            resp = http_requests.get(
                f'https://openapi.zhihu.com/user/followed?page={page}&per_page={per_page}',
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=10
            )
            if resp.status_code != 200:
                if page == 0:
                    return jsonify({
                        'error': '知乎接口返回异常，请稍后重试',
                        'logged_in': True,
                        'user': zhihu_user,
                    }), 502
                break

            data = resp.json()
            try:
                batch = _extract_zhihu_user_list(data)
            except PermissionError as e:
                permission_limited = True
                source_note = f'知乎关注列表接口暂不可用，已切换为演示关注宇宙：{clean_hot_text(str(e), 80)}'
                all_followed = _demo_followed_users()
                break
            if not batch:
                break
            all_followed.extend(batch)
            if len(batch) < per_page:
                break
            page += 1
        except Exception as e:
            app.logger.warning(f"Failed to fetch followed list page {page}: {e}")
            if page == 0:
                return jsonify({
                    'error': '网络异常，无法获取关注列表',
                    'logged_in': True,
                    'user': zhihu_user,
                }), 502
            break

    # 分析每个关注者
    profiles = [_analyze_followed_user(u) for u in all_followed]
    profiles = [p for p in profiles if p['name']]  # 过滤空名

    # 领域分布统计
    domain_distribution = {did: 0 for did in DOMAINS}
    domain_distribution['unknown'] = 0
    for p in profiles:
        did = p['primary_domain']
        if did in domain_distribution:
            domain_distribution[did] += 1
        else:
            domain_distribution['unknown'] += 1

    # 信息茧房指数
    bubble_score = _compute_filter_bubble_score(domain_distribution)

    # 同频、互补、破圈、圆桌候选人
    same_freq = _pick_same_frequency(profiles, domain_distribution)
    complementary = _pick_complementary(profiles, domain_distribution)
    breakout = _pick_breakout(profiles, domain_distribution)
    roundtable_cands = _pick_roundtable_candidates(profiles)

    # 洞察
    insights = _generate_universe_insights(domain_distribution, bubble_score, len(profiles))

    return jsonify({
        'logged_in': True,
        'user': zhihu_user,
        'followed_count': len(profiles),
        'domain_distribution': domain_distribution,
        'same_frequency_users': same_freq,
        'complementary_users': complementary,
        'breakout_users': breakout,
        'roundtable_candidates': roundtable_cands,
        'filter_bubble_score': bubble_score,
        'insights': insights,
        'permission_limited': permission_limited,
        'source_note': source_note,
    })


@app.route('/api/my_zhihu_universe/gravity', methods=['POST'])
def api_my_universe_gravity():
    """基于我的关注列表的引力场推荐"""
    access_token = session.get('access_token')
    if not access_token:
        return jsonify({'error': '未登录'}), 401

    body = request.get_json()
    topic = body.get('topic', '')
    if not topic:
        return jsonify({'error': '请提供话题'}), 400

    # 复用 /api/my_zhihu_universe 的逻辑获取关注列表分析
    # 为避免重复请求知乎API，这里做一个简化版
    zhihu_user = session.get('zhihu_user', {})
    all_followed = []
    page = 0
    while page < 5:
        try:
            resp = http_requests.get(
                f'https://openapi.zhihu.com/user/followed?page={page}&per_page=30',
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=10
            )
            if resp.status_code != 200:
                break
            data = resp.json()
            try:
                batch = _extract_zhihu_user_list(data)
            except PermissionError:
                all_followed = _demo_followed_users()
                break
            if not batch:
                break
            all_followed.extend(batch)
            if len(batch) < 30:
                break
            page += 1
        except Exception:
            break

    if not all_followed:
        all_followed = _demo_followed_users()

    profiles = [_analyze_followed_user(u) for u in all_followed if isinstance(u, dict) and u.get('fullname')]

    # 基于话题匹配
    topic_domain = infer_domain_from_text(topic)
    topic_keywords = re.findall(r'[\w一-鿿]{2,}', topic.lower())

    scored = []
    for p in profiles:
        text = f"{p['name']} {p['headline']}".lower()
        score = 0
        if p['primary_domain'] == topic_domain:
            score += 10
        score += sum(1 for kw in topic_keywords if kw in text)
        scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)

    same_freq = []
    complementary = []
    breakout_list = []

    total = sum(1 for _, _ in scored) or 1
    for score, p in scored[:20]:
        entry = {
            'name': p['name'],
            'avatar': p['avatar'],
            'headline': p['headline'],
            'primary_domain': p['primary_domain'],
            'domain_name': DOMAINS.get(p['primary_domain'], {}).get('name', '未归类'),
            'domain_emoji': DOMAINS.get(p['primary_domain'], {}).get('emoji', ''),
            'url': p['url'],
            'score': score,
            'reason': p['why_matched'],
        }
        if p['primary_domain'] == topic_domain:
            same_freq.append(entry)
        elif p['primary_domain'] != 'unknown':
            complementary.append(entry)
        else:
            breakout_list.append(entry)

    return jsonify({
        'topic': topic,
        'topic_domain': DOMAINS.get(topic_domain, {}).get('name', '未归类'),
        'same_frequency': same_freq[:5],
        'complementary': complementary[:5],
        'breakout': breakout_list[:3],
    })


# ============ 运行 ============
if __name__ == '__main__':
    app.run(debug=False, port=8050, host='0.0.0.0')
