"""
跨领域兴趣探索引擎
当用户对新领域产生兴趣时，推荐该领域达人关注的内容
"""

import json
import re
from typing import Dict, List, Tuple, Set, Optional
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from gravity_topology.config import DOMAINS as SHARED_DOMAINS


class InterestExplorer:
    """兴趣探索引擎"""

    # 使用共享领域定义（仅保留兴趣探索需要的子集）
    DOMAINS = {k: v for k, v in SHARED_DOMAINS.items() if k in ('ai_tech', 'humanities', 'society', 'life', 'creative')}

    def __init__(self, data_file: str = "massive_data.json"):
        """初始化"""
        with open(data_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

        self.users = self.data.get('users', {})
        self.posts = self.data.get('posts', [])
        self.comments = self.data.get('comments', [])

        # 预处理：为每个用户计算领域分布
        self.user_domain_scores: Dict[str, Dict[str, float]] = {}
        self._precompute_domain_scores()

    def _precompute_domain_scores(self) -> None:
        """预计算每个用户的领域得分"""
        for token, user in self.users.items():
            contents = user.get('contents', [])
            if not contents:
                continue

            domain_scores = {}
            for domain_id, domain_info in self.DOMAINS.items():
                score = 0
                for content in contents:
                    for keyword in domain_info['keywords']:
                        if keyword in content:
                            score += 1
                domain_scores[domain_id] = score / max(len(contents), 1)

            # 归一化
            total = sum(domain_scores.values())
            if total > 0:
                domain_scores = {k: v/total for k, v in domain_scores.items()}

            self.user_domain_scores[token] = domain_scores

    def detect_interest_change(self, user_token: str, recent_window: int = 10) -> Dict:
        """
        检测用户兴趣变化

        Args:
            user_token: 用户 token
            recent_window: 最近内容窗口大小

        Returns:
            兴趣变化分析结果
        """
        user = self.users.get(user_token)
        if not user:
            return {'error': '用户不存在'}

        contents = user.get('contents', [])
        if len(contents) < 5:
            return {'error': '内容太少，无法分析'}

        # 分析历史内容（早期）
        early_contents = contents[:len(contents)//2]
        # 分析近期内容
        recent_contents = contents[-recent_window:]

        # 计算早期和近期的领域分布
        early_domains = self._analyze_content_domains(early_contents)
        recent_domains = self._analyze_content_domains(recent_contents)

        # 找出变化最大的领域
        changes = {}
        for domain_id in self.DOMAINS:
            early_score = early_domains.get(domain_id, 0)
            recent_score = recent_domains.get(domain_id, 0)
            change = recent_score - early_score
            changes[domain_id] = {
                'early': early_score,
                'recent': recent_score,
                'change': change,
                'direction': 'rising' if change > 0.1 else 'declining' if change < -0.1 else 'stable'
            }

        # 找出新兴兴趣（近期明显上升的领域）
        emerging_interests = [
            domain_id for domain_id, info in changes.items()
            if info['direction'] == 'rising'
        ]

        # 按变化幅度排序
        sorted_changes = sorted(changes.items(), key=lambda x: x[1]['change'], reverse=True)

        return {
            'user_token': user_token,
            'user_name': user.get('name', user_token),
            'total_content': len(contents),
            'early_count': len(early_contents),
            'recent_count': len(recent_contents),
            'domain_changes': changes,
            'emerging_interests': emerging_interests,
            'top_rising': sorted_changes[0] if sorted_changes else None,
            'top_declining': sorted_changes[-1] if sorted_changes else None
        }

    def _analyze_content_domains(self, contents: List[str]) -> Dict[str, float]:
        """分析内容的领域分布"""
        domain_scores = {domain_id: 0 for domain_id in self.DOMAINS}

        for content in contents:
            for domain_id, domain_info in self.DOMAINS.items():
                for keyword in domain_info['keywords']:
                    if keyword in content:
                        domain_scores[domain_id] += 1

        # 归一化
        total = sum(domain_scores.values())
        if total > 0:
            domain_scores = {k: v/total for k, v in domain_scores.items()}

        return domain_scores

    def find_domain_experts(self, domain_id: str, top_n: int = 10) -> List[Dict]:
        """
        找到指定领域的专家用户

        Args:
            domain_id: 领域 ID
            top_n: 返回前 N 个专家

        Returns:
            专家用户列表
        """
        if domain_id not in self.DOMAINS:
            return []

        experts = []
        for token, scores in self.user_domain_scores.items():
            domain_score = scores.get(domain_id, 0)
            if domain_score > 0.2:  # 阈值
                user = self.users.get(token, {})
                experts.append({
                    'token': token,
                    'name': user.get('name', token),
                    'domain_score': domain_score,
                    'post_count': user.get('post_count', 0),
                    'comment_count': user.get('comment_count', 0),
                    'total_likes': user.get('total_likes', 0),
                    'content_count': len(user.get('contents', []))
                })

        # 按领域得分排序
        experts.sort(key=lambda x: x['domain_score'], reverse=True)
        return experts[:top_n]

    def get_expert_daily_content(self, expert_token: str, days: int = 7) -> List[Dict]:
        """
        获取专家近期发布的内容

        Args:
            expert_token: 专家用户 token
            days: 最近几天

        Returns:
            内容列表
        """
        user = self.users.get(expert_token, {})
        contents = user.get('contents', [])

        # 这里简化处理，返回最近的内容
        # 实际应该根据时间戳过滤
        recent_count = min(len(contents), 10)
        recent_contents = contents[-recent_count:]

        return [
            {
                'content': content[:200] + '...' if len(content) > 200 else content,
                'full_content': content,
                'domain': self._detect_content_domain(content)
            }
            for content in recent_contents
        ]

    def _detect_content_domain(self, content: str) -> str:
        """检测内容所属领域"""
        max_score = 0
        max_domain = 'unknown'

        for domain_id, domain_info in self.DOMAINS.items():
            score = 0
            for keyword in domain_info['keywords']:
                if keyword in content:
                    score += 1
            if score > max_score:
                max_score = score
                max_domain = domain_id

        return max_domain

    def explore_new_domain(self, user_token: str, target_domain: str) -> Dict:
        """
        探索新领域

        Args:
            user_token: 用户 token
            target_domain: 目标领域 ID

        Returns:
            探索报告
        """
        user = self.users.get(user_token, {})
        if not user:
            return {'error': '用户不存在'}

        # 找到目标领域的专家
        experts = self.find_domain_experts(target_domain, top_n=5)

        if not experts:
            return {'error': f'没有找到{self.DOMAINS.get(target_domain, {}).get("name", target_domain)}领域的专家'}

        # 获取专家的内容
        expert_contents = []
        for expert in experts:
            contents = self.get_expert_daily_content(expert['token'])
            expert_contents.append({
                'expert': expert,
                'contents': contents
            })

        # 生成探索报告
        domain_info = self.DOMAINS.get(target_domain, {})

        report = {
            'user': {
                'token': user_token,
                'name': user.get('name', user_token)
            },
            'target_domain': {
                'id': target_domain,
                'name': domain_info.get('name', target_domain),
                'emoji': domain_info.get('emoji', '🔍')
            },
            'experts': experts,
            'expert_contents': expert_contents,
            'recommendation_count': sum(len(ec['contents']) for ec in expert_contents)
        }

        return report

    def generate_exploration_report(self, user_token: str) -> str:
        """
        生成兴趣探索报告

        Args:
            user_token: 用户 token

        Returns:
            报告文本
        """
        # 检测兴趣变化
        interest_change = self.detect_interest_change(user_token)

        if 'error' in interest_change:
            return f"无法生成报告: {interest_change['error']}"

        # 获取用户信息
        user = self.users.get(user_token, {})
        user_name = user.get('name', user_token)

        # 生成报告
        report = f"""
{'='*60}
        兴趣探索报告 · {user_name}
{'='*60}

■ 用户画像
  用户名: {user_name}
  总内容数: {interest_change['total_content']}
  分析窗口: 早期 {interest_change['early_count']} 条 / 近期 {interest_change['recent_count']} 条

■ 兴趣领域分布变化
"""

        # 按变化幅度排序
        domain_changes = interest_change['domain_changes']
        sorted_domains = sorted(domain_changes.items(),
                               key=lambda x: x[1]['change'], reverse=True)

        for domain_id, change_info in sorted_domains:
            domain_info = self.DOMAINS.get(domain_id, {})
            emoji = domain_info.get('emoji', '🔍')
            name = domain_info.get('name', domain_id)
            direction = change_info['direction']
            change = change_info['change']

            if direction == 'rising':
                indicator = '📈'
            elif direction == 'declining':
                indicator = '📉'
            else:
                indicator = '➡️'

            report += f"  {emoji} {name}: {indicator} {change:+.2f}\n"
            report += f"      早期: {change_info['early']:.2%} → 近期: {change_info['recent']:.2%}\n"

        # 新兴兴趣
        emerging = interest_change['emerging_interests']
        if emerging:
            report += f"\n■ 新兴兴趣领域\n"
            for domain_id in emerging:
                domain_info = self.DOMAINS.get(domain_id, {})
                report += f"  {domain_info.get('emoji', '🔍')} {domain_info.get('name', domain_id)}\n"

            # 推荐探索
            report += f"\n■ 探索推荐\n"
            for domain_id in emerging[:2]:  # 推荐前两个新兴领域
                domain_info = self.DOMAINS.get(domain_id, {})
                experts = self.find_domain_experts(domain_id, top_n=3)

                if experts:
                    report += f"\n  {domain_info.get('emoji', '🔍')} {domain_info.get('name', domain_id)} 领域达人:\n"
                    for expert in experts:
                        report += f"    • {expert['name']} (专业度: {expert['domain_score']:.2%})\n"

                        # 获取专家内容
                        contents = self.get_expert_daily_content(expert['token'])
                        if contents:
                            report += f"      近期关注: {contents[0]['content'][:50]}...\n"

        report += f"""
{'='*60}
        由 引力拓扑 兴趣探索引擎 生成
{'='*60}
"""
        return report

    def get_domain_trending_content(self, domain_id: str, top_n: int = 10) -> List[Dict]:
        """
        获取指定领域的热门内容

        Args:
            domain_id: 领域 ID
            top_n: 返回前 N 条内容

        Returns:
            热门内容列表
        """
        if domain_id not in self.DOMAINS:
            return []

        # 找到该领域的内容
        domain_contents = []

        for post in self.posts:
            content = post.get('content', '')
            domain = self._detect_content_domain(content)

            if domain == domain_id:
                domain_contents.append({
                    'content': content[:200],
                    'author': post.get('author_name', 'unknown'),
                    'likes': post.get('like_num', 0),
                    'comments': post.get('comment_num', 0),
                    'domain': domain
                })

        # 按点赞数排序
        domain_contents.sort(key=lambda x: x['likes'], reverse=True)

        return domain_contents[:top_n]

    def save_exploration_data(self, user_token: str, filename: str = "exploration_result.json") -> None:
        """保存探索结果"""
        report_data = {
            'interest_change': self.detect_interest_change(user_token),
            'exploration_report': self.generate_exploration_report(user_token)
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        print(f"探索结果已保存到: {filename}")


# 测试
if __name__ == "__main__":
    explorer = InterestExplorer("massive_data.json")

    # 测试用户
    test_users = ['pjl', '冬子', '零一知制诰', '奶瓶']

    for user_token in test_users:
        if user_token in explorer.users:
            print(f"\n测试用户: {user_token}")
            report = explorer.generate_exploration_report(user_token)
            print(report[:500])
            print("...")
