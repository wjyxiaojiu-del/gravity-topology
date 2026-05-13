"""
引力拓扑 - 共享工具函数
消除各模块间的重复代码
"""

import re
import time
import json
from typing import Dict, List, Optional
from collections import defaultdict, Counter

from .config import (
    DOMAINS, TECH_KEYWORDS, HUMAN_KEYWORDS, QUESTION_KEYWORDS,
    CREATIVE_KEYWORDS, EMOTION_KEYWORDS, BOT_SIGNALS,
)


# ============ 文本处理 ============

def clean_html(text: str) -> str:
    """清理 HTML 标签和多余空白"""
    text = re.sub(r'<[^>]+>', '', str(text or ''))
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def clean_hot_text(text, limit=180):
    """清理文本并截断到指定长度"""
    text = clean_html(text)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + '...'


def split_hot_title(content, max_len=48):
    """从内容中提取标题"""
    content = clean_hot_text(content, 260)
    if not content:
        return '知乎社区热点'
    for sep in ['｜', '|', '。', '！', '？', '\n']:
        if sep in content:
            head = content.split(sep, 1)[0].strip()
            if 6 <= len(head) <= max_len:
                return head
    return content[:36].rstrip() + ('...' if len(content) > 36 else '')


# ============ 时间工具 ============

def time_ago(timestamp) -> str:
    """时间戳转为相对时间描述"""
    if not timestamp:
        return '很久以前'
    try:
        ts = int(timestamp)
        now = int(time.time())
        delta = now - ts
        if delta < 0:
            return '刚刚'
        if delta < 3600:
            return f'{max(1, delta // 60)}分钟前'
        elif delta < 86400:
            return f'{delta // 3600}小时前'
        elif delta < 2592000:
            return f'{delta // 86400}天前'
        elif delta < 31536000:
            return f'{delta // 2592000}个月前'
        else:
            return f'{delta // 31536000}年前'
    except Exception:
        return '很久以前'


# ============ 数学工具 ============

def calculate_entropy(values: list) -> float:
    """计算信息熵"""
    if not values:
        return 0
    counts = defaultdict(int)
    for v in values:
        counts[v] += 1
    total = len(values)
    probs = [c / total for c in counts.values()]
    return -sum(p * __import__('math').log2(p) for p in probs if p > 0)


# ============ 用户分析 ============

def is_bot_user(name: str) -> bool:
    """检测是否为 bot 用户"""
    name_lower = str(name or '').lower()
    return any(s in name_lower for s in BOT_SIGNALS)


def count_keywords(texts: List[str], keywords: List[str]) -> int:
    """统计关键词在文本列表中的出现次数"""
    return sum(1 for c in texts for k in keywords if k in c)


def analyze_user_style(contents: List[str]) -> Dict:
    """
    分析用户写作风格（统一实现）
    替代 a2a_dialogue._analyze_writing_style / deepseek_a2a._analyze_style
    / generate_a2a.get_user_style / app.get_user_style 中的重复逻辑
    """
    if not contents:
        return {'type': 'unknown', 'traits': '风格未知', 'samples': [], 'avg_length': 0}

    tech_score = count_keywords(contents, TECH_KEYWORDS)
    human_score = count_keywords(contents, HUMAN_KEYWORDS)
    question_count = count_keywords(contents, QUESTION_KEYWORDS)
    avg_len = sum(len(t) for t in contents) / len(contents)

    # 判断风格类型
    if tech_score > human_score * 2:
        style_type = 'tech'
        traits_list = ['技术导向', '逻辑严密', '喜欢用数据说话']
        traits_str = '技术导向、逻辑严密、喜欢用数据说话'
    elif human_score > tech_score * 2:
        style_type = 'humanist'
        traits_list = ['人文关怀', '善于思辨', '关注社会影响']
        traits_str = '人文关怀、善于思辨、关注社会影响'
    else:
        style_type = 'balanced'
        traits_list = ['理性与感性并重', '跨界思维', '善于综合分析']
        traits_str = '跨界思维、理性与感性并重'

    # 长度特征
    if avg_len > 200:
        traits_list.append('表达详细')
    elif avg_len < 50:
        traits_list.append('言简意赅')

    # 提问倾向
    if question_count > len(contents) * 0.3:
        traits_list.append('善于提问')

    return {
        'type': style_type,
        'traits': traits_str,
        'traits_list': traits_list,
        'avg_length': avg_len,
        'tech_score': tech_score,
        'human_score': human_score,
        'samples': [c[:80] for c in contents[:5]],
    }


def build_persona_prompt(
    name: str,
    user_info: Dict,
    style: Dict,
    contents: List[str],
) -> str:
    """
    构建 Agent 人设 prompt（统一实现）
    替代 a2a_dialogue._generate_persona_prompt / generate_a2a.build_persona_prompt
    / app.build_persona_prompt 中的重复逻辑
    """
    samples = contents[:5] if contents else ['暂无内容']
    sample_str = '\n'.join(
        f'- "{s[:120]}"' if len(s) > 120 else f'- "{s}"'
        for s in samples
    )

    domain = '技术' if style.get('type') == 'tech' else \
             '人文' if style.get('type') == 'humanist' else '综合'

    return f"""你现在扮演知乎用户 "{name}"。

## 你的特征
- 写作风格：{style.get('traits', '未知')}
- 擅长领域：{domain}
- 发帖数：{user_info.get('post_count', 0)}
- 评论数：{user_info.get('comment_count', 0)}

## 你曾经的发言
{sample_str}

## 对话要求
1. 完全沉浸在角色中，以这个用户的身份思考和回应
2. 保持语言风格一致
3. 可以引用或延伸自己过去的观点
4. 回复长度控制在 80-150 字
5. 不要暴露自己是 AI，要像真实用户一样自然交流
6. 可以提问、质疑、赞同，保持真实对话感"""


def get_user_profile(token: str, users: Dict, posts: List, comments: List) -> Optional[Dict]:
    """获取用户完整画像"""
    user = users.get(token, {})
    if not user:
        return None

    user_posts = [p for p in posts if p.get('author_token') == token]
    user_comments = [c for c in comments if c.get('author_token') == token]
    all_contents = user.get('contents', [])

    domain_scores = {}
    for domain_id, domain_info in DOMAINS.items():
        kw_hits = 0
        for content in all_contents[:50]:
            for kw in domain_info['keywords']:
                if kw in content:
                    kw_hits += 1
                    break
        domain_scores[domain_id] = min(kw_hits / max(len(all_contents[:50]), 1), 1.0)

    primary_domain = max(domain_scores, key=domain_scores.get) if domain_scores else 'ai_tech'

    return {
        'token': token,
        'name': user.get('name', token),
        'post_count': user.get('post_count', 0),
        'comment_count': user.get('comment_count', 0),
        'total_content': len(all_contents),
        'contents': all_contents,
        'posts': user_posts[:10],
        'comments': user_comments[:10],
        'domain_scores': domain_scores,
        'primary_domain': primary_domain,
        'primary_domain_name': DOMAINS.get(primary_domain, {}).get('name', ''),
        'primary_domain_emoji': DOMAINS.get(primary_domain, {}).get('emoji', ''),
    }


def infer_domain_from_text(text: str) -> str:
    """从文本推断所属领域"""
    best_domain = 'unknown'
    best_score = 0
    text_lower = text.lower()
    for domain_id, domain_info in DOMAINS.items():
        score = sum(1 for kw in domain_info['keywords'] if kw.lower() in text_lower)
        if score > best_score:
            best_domain = domain_id
            best_score = score
    return best_domain


# ============ 数据构建工具 ============

def build_dedup_users(users: Dict) -> set:
    """构建去重用户表：同名用户只保留内容最多的那个，排除 bot"""
    seen_names = {}
    for token, user in users.items():
        name = user.get('name', token)
        if is_bot_user(name):
            continue
        content_count = len(user.get('contents', []))
        if name not in seen_names or content_count > seen_names[name][1]:
            seen_names[name] = (token, content_count)
    return {v[0] for v in seen_names.values()}


def load_json_file(filepath: str, default=None):
    """安全加载 JSON 文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default if default is not None else {}
