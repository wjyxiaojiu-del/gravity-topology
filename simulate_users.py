"""
模拟100个用户使用引力拓扑系统
收集使用数据，发现问题，生成改进建议
"""

import json
import random
import time
from collections import defaultdict, Counter

# 加载数据
with open('massive_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

with open('gravity_engine_v2_results.json', 'r', encoding='utf-8') as f:
    gravity_results = json.load(f)

users = data.get('users', {})
posts = data.get('posts', [])
comments = data.get('comments', [])
hidden_pairs = gravity_results.get('hidden_pairs', [])

# 领域定义
DOMAINS = {
    'ai_tech': {
        'name': 'AI/技术',
        'keywords': ['AI', 'Agent', '算法', '模型', '技术', 'LLM', '代码', '开发', 'API', 'Python']
    },
    'humanities': {
        'name': '人文/哲学',
        'keywords': ['思考', '哲学', '人文', '意义', '价值', '伦理', '意识', '认知']
    },
    'society': {
        'name': '社会/经济',
        'keywords': ['社会', '经济', '市场', '金融', '教育', '发展', '改革']
    },
    'life': {
        'name': '生活/情感',
        'keywords': ['生活', '情感', '成长', '工作', '职场', '心理', '幸福']
    },
    'creative': {
        'name': '创意/艺术',
        'keywords': ['创意', '艺术', '设计', '美学', '写作', '摄影', '创作']
    }
}

def get_user_domains(token):
    """分析用户领域分布"""
    user = users.get(token, {})
    contents = user.get('contents', [])
    if not contents:
        return {}

    scores = {}
    for did, dinfo in DOMAINS.items():
        hits = sum(1 for c in contents for kw in dinfo['keywords'] if kw in c)
        scores[did] = min(hits / len(contents), 1.0)
    return scores

def get_quality_users(min_contents=10):
    """获取优质用户列表"""
    result = []
    for token, user in users.items():
        contents = user.get('contents', [])
        if len(contents) >= min_contents:
            result.append({
                'token': token,
                'name': user.get('name', token),
                'content_count': len(contents),
                'post_count': user.get('post_count', 0),
                'comment_count': user.get('comment_count', 0),
            })
    result.sort(key=lambda x: x['content_count'], reverse=True)
    return result


def simulate():
    """运行100个用户的模拟"""
    quality = get_quality_users(10)
    print(f"=" * 60)
    print(f"  引力拓扑 · 用户模拟系统")
    print(f"=" * 60)
    print(f"优质用户池: {len(quality)} 人")
    print(f"隐藏同好对: {len(hidden_pairs)} 对")
    print()

    # 随机选100个模拟用户
    sim_users = random.sample(quality, min(100, len(quality)))

    # 统计数据
    stats = {
        'explore_actions': [],      # 探索行为
        'exchange_actions': [],     # 交换行为
        'feedback': [],             # 模拟反馈
        'domain_interests': defaultdict(int),  # 领域兴趣分布
        'exchange_satisfaction': [],  # 交换满意度
        'pain_points': Counter(),   # 痛点统计
    }

    print(f"开始模拟 {len(sim_users)} 个用户...")
    print()

    for i, user in enumerate(sim_users):
        token = user['token']
        name = user['name']
        domains = get_user_domains(token)
        primary = max(domains, key=domains.get) if domains else 'ai_tech'

        # 模拟探索行为
        explore_domain = random.choice(list(DOMAINS.keys()))
        stats['explore_actions'].append({
            'user': name,
            'domain': explore_domain,
            'primary_domain': primary,
            'cross_domain': explore_domain != primary,
        })
        stats['domain_interests'][explore_domain] += 1

        # 模拟交换人生行为
        # 找到该用户的隐藏同好
        partners = []
        for pair in hidden_pairs:
            if pair['user_a'] == token:
                partners.append(pair['user_b_name'])
            elif pair['user_b'] == token:
                partners.append(pair['user_a_name'])

        if partners:
            stats['exchange_actions'].append({
                'user': name,
                'has_partners': True,
                'partner_count': len(partners),
                'partner': random.choice(partners),
            })
        else:
            stats['exchange_actions'].append({
                'user': name,
                'has_partners': False,
                'partner_count': 0,
                'partner': None,
            })

        # 模拟满意度（基于内容匹配度）
        if partners:
            # 有隐藏同好的用户满意度更高
            satisfaction = random.uniform(0.6, 1.0)
        else:
            satisfaction = random.uniform(0.3, 0.7)
        stats['exchange_satisfaction'].append(satisfaction)

        # 模拟痛点
        if not partners:
            stats['pain_points']['没有找到合适的交换对象'] += 1
        if user['content_count'] < 20:
            stats['pain_points']['用户内容太少，画像不完整'] += 1
        if domains.get(primary, 0) < 0.3:
            stats['pain_points']['领域匹配度不够精准'] += 1

        # 进度
        if (i + 1) % 20 == 0:
            print(f"  已模拟 {i+1}/{len(sim_users)} 个用户")

    print()
    print(f"=" * 60)
    print(f"  模拟结果分析")
    print(f"=" * 60)

    # 探索行为分析
    cross_domain = sum(1 for e in stats['explore_actions'] if e['cross_domain'])
    print(f"\n[探索行为]")
    print(f"  总探索次数: {len(stats['explore_actions'])}")
    print(f"  跨领域探索: {cross_domain} ({cross_domain/len(stats['explore_actions'])*100:.0f}%)")
    print(f"  领域兴趣分布:")
    for domain, count in sorted(stats['domain_interests'].items(), key=lambda x: -x[1]):
        print(f"    {DOMAINS[domain]['name']}: {count} 人")

    # 交换行为分析
    has_partners = sum(1 for e in stats['exchange_actions'] if e['has_partners'])
    no_partners = len(stats['exchange_actions']) - has_partners
    print(f"\n[交换人生]")
    print(f"  有匹配对象: {has_partners} 人 ({has_partners/len(sim_users)*100:.0f}%)")
    print(f"  无匹配对象: {no_partners} 人 ({no_partners/len(sim_users)*100:.0f}%)")
    avg_satisfaction = sum(stats['exchange_satisfaction']) / len(stats['exchange_satisfaction'])
    print(f"  平均满意度: {avg_satisfaction:.2f}")

    # 痛点分析
    print(f"\n[用户痛点]")
    for pain, count in stats['pain_points'].most_common():
        print(f"  {pain}: {count} 人 ({count/len(sim_users)*100:.0f}%)")

    # 核心问题
    print(f"\n" + "=" * 60)
    print(f"  核心问题诊断")
    print(f"=" * 60)

    issues = []
    if no_partners > len(sim_users) * 0.3:
        issues.append(f"[严重] {no_partners/len(sim_users)*100:.0f}% 用户找不到交换对象 -> 需要扩大匹配池")
    if avg_satisfaction < 0.7:
        issues.append(f"[中等] 平均满意度仅 {avg_satisfaction:.2f} -> 交换体验需要增强")
    if cross_domain < len(sim_users) * 0.3:
        issues.append(f"[中等] 跨领域探索比例低 -> 需要更好的领域推荐引导")

    # 内容太少的用户
    low_content = sum(1 for u in sim_users if u['content_count'] < 20)
    if low_content > len(sim_users) * 0.3:
        issues.append(f"[严重] {low_content/len(sim_users)*100:.0f}% 用户内容不足20条 -> 画像不完整")

    for issue in issues:
        print(f"  {issue}")

    # 改进建议
    print(f"\n" + "=" * 60)
    print(f"  改进建议")
    print(f"=" * 60)

    suggestions = [
        "1. [交换人生] 增加 A2A 对话 - 用 DeepSeek 生成两人的模拟对话，让交换更有趣",
        "2. [交换人生] 增加「兴趣碰撞点」分析 - 展示两人观点的交集和分歧",
        "3. [交换人生] 增加「假如你是TA」模式 - 用 AI 生成从对方视角看世界的体验",
        "4. [每日探索] 增加「今日精选」- 自动推荐跨领域的高价值内容",
        "5. [匹配算法] 放宽匹配条件 - 不仅看引力值，还看领域互补性",
        "6. [用户画像] 内容不足时用评论补充 - 评论也是兴趣的体现",
    ]
    for s in suggestions:
        print(f"  {s}")

    # 保存模拟结果
    result = {
        'simulated_users': len(sim_users),
        'explore_cross_domain_rate': cross_domain / len(sim_users),
        'exchange_partner_rate': has_partners / len(sim_users),
        'avg_satisfaction': avg_satisfaction,
        'domain_distribution': dict(stats['domain_interests']),
        'top_pains': stats['pain_points'].most_common(5),
        'issues': issues,
    }

    with open('simulation_results.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n模拟结果已保存到 simulation_results.json")
    return result


if __name__ == '__main__':
    simulate()
