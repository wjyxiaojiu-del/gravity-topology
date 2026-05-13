"""
数据采集模块
从知乎圈子采集用户互动数据
"""

import json
import os
import time
from typing import Dict, List, Set, Tuple
from collections import defaultdict
from zhihu_api import ZhihuAPI
from gravity_topology.utils import clean_html
from gravity_topology.config import RINGS


class DataCollector:
    """知乎圈子数据采集器"""

    RINGS = RINGS

    def __init__(self, api: ZhihuAPI):
        """
        初始化数据采集器

        Args:
            api: 知乎 API 客户端
        """
        self.api = api

        # 用户数据存储
        self.users: Dict[str, Dict] = {}  # token -> 用户信息
        self.posts: List[Dict] = []  # 所有帖子
        self.comments: List[Dict] = []  # 所有评论

        # 互动关系
        self.user_posts: Dict[str, List[str]] = defaultdict(list)  # 用户 -> 帖子列表
        self.user_comments: Dict[str, List[Dict]] = defaultdict(list)  # 用户 -> 评论列表
        self.post_comments: Dict[str, List[Dict]] = defaultdict(list)  # 帖子 -> 评论列表

        # 用户互动矩阵 (用户A 在 用户B 的帖子下评论过)
        self.interaction_matrix: Dict[str, Set[str]] = defaultdict(set)

    def collect_ring_data(self, ring_id: str, max_pages: int = 5) -> None:
        """
        采集指定圈子的数据

        Args:
            ring_id: 圈子 ID
            max_pages: 最大采集页数
        """
        print(f"\n开始采集圈子数据: {self.RINGS.get(ring_id, ring_id)}")

        for page in range(1, max_pages + 1):
            print(f"  采集第 {page} 页...")

            result = self.api.get_ring_detail(ring_id, page_num=page, page_size=50)

            if result.get('status') != 0:
                print(f"  错误: {result.get('msg')}")
                break

            contents = result.get('data', {}).get('contents', [])
            if not contents:
                print("  没有更多内容")
                break

            for post in contents:
                self._process_post(post, ring_id)

            # 限流保护
            time.sleep(0.5)

    def _process_post(self, post: Dict, ring_id: str) -> None:
        """处理单个帖子"""
        pin_id = str(post.get('pin_id'))
        author_name = post.get('author_name', 'unknown')
        author_token = post.get('author_token', author_name)

        # 清理内容
        content = clean_html(post.get('content', ''))

        # 存储帖子信息
        post_data = {
            'pin_id': pin_id,
            'content': content,
            'author_name': author_name,
            'author_token': author_token,
            'like_num': post.get('like_num', 0),
            'comment_num': post.get('comment_num', 0),
            'publish_time': post.get('publish_time', 0),
            'ring_id': ring_id
        }
        self.posts.append(post_data)
        self.user_posts[author_token].append(pin_id)

        # 记录用户信息
        if author_token not in self.users:
            self.users[author_token] = {
                'token': author_token,
                'name': author_name,
                'post_count': 0,
                'comment_count': 0,
                'total_likes': 0,
                'contents': []  # 用户发布的内容文本
            }
        self.users[author_token]['post_count'] += 1
        self.users[author_token]['total_likes'] += post.get('like_num', 0)
        if content:
            self.users[author_token]['contents'].append(content)

        # 处理评论
        comments = post.get('comments', [])
        for comment in comments:
            self._process_comment(comment, pin_id, author_token)

    def _process_comment(self, comment: Dict, pin_id: str, post_author: str) -> None:
        """处理单条评论"""
        comment_id = str(comment.get('comment_id'))
        commenter_name = comment.get('author_name', 'unknown')
        commenter_token = comment.get('author_token', commenter_name)

        # 清理内容
        content = clean_html(comment.get('content', ''))

        # 存储评论信息
        comment_data = {
            'comment_id': comment_id,
            'content': content,
            'author_name': commenter_name,
            'author_token': commenter_token,
            'like_count': comment.get('like_count', 0),
            'pin_id': pin_id,
            'post_author': post_author
        }
        self.comments.append(comment_data)
        self.user_comments[commenter_token].append(comment_data)
        self.post_comments[pin_id].append(comment_data)

        # 记录用户信息
        if commenter_token not in self.users:
            self.users[commenter_token] = {
                'token': commenter_token,
                'name': commenter_name,
                'post_count': 0,
                'comment_count': 0,
                'total_likes': 0,
                'contents': []
            }
        self.users[commenter_token]['comment_count'] += 1
        if content:
            self.users[commenter_token]['contents'].append(content)

        # 记录互动关系（评论者 -> 帖子作者）
        if commenter_token != post_author:
            self.interaction_matrix[commenter_token].add(post_author)
            self.interaction_matrix[post_author].add(commenter_token)

    def collect_all_rings(self, max_pages: int = 3) -> None:
        """
        采集所有圈子的数据

        Args:
            max_pages: 每个圈子最大采集页数
        """
        print("=" * 50)
        print("开始采集知乎圈子数据")
        print("=" * 50)

        for ring_id in self.RINGS:
            self.collect_ring_data(ring_id, max_pages)
            time.sleep(1)  # 圈子间休息

        print("\n" + "=" * 50)
        print("数据采集完成!")
        print(f"用户数量: {len(self.users)}")
        print(f"帖子数量: {len(self.posts)}")
        print(f"评论数量: {len(self.comments)}")
        print("=" * 50)

    def save_data(self, filename: str = "collected_data.json") -> None:
        """
        保存采集的数据

        Args:
            filename: 输出文件名
        """
        data = {
            'users': self.users,
            'posts': self.posts,
            'comments': self.comments,
            'interaction_matrix': {k: list(v) for k, v in self.interaction_matrix.items()},
            'user_posts': dict(self.user_posts),
            'collect_time': time.strftime('%Y-%m-%d %H:%M:%S')
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"\n数据已保存到: {filename}")

    def load_data(self, filename: str = "collected_data.json") -> bool:
        """
        加载已采集的数据

        Args:
            filename: 数据文件名

        Returns:
            是否加载成功
        """
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.users = data.get('users', {})
            self.posts = data.get('posts', [])
            self.comments = data.get('comments', [])
            self.user_posts = data.get('user_posts', {})
            self.interaction_matrix = {
                k: set(v) for k, v in data.get('interaction_matrix', {}).items()
            }

            print(f"数据加载成功!")
            print(f"用户数量: {len(self.users)}")
            print(f"帖子数量: {len(self.posts)}")
            print(f"评论数量: {len(self.comments)}")
            return True
        except FileNotFoundError:
            print(f"文件不存在: {filename}")
            return False

    def get_user_texts(self, user_token: str) -> List[str]:
        """
        获取用户的所有文本内容

        Args:
            user_token: 用户 token

        Returns:
            用户发布的内容列表
        """
        texts = []

        # 用户发布的帖子
        if user_token in self.users:
            texts.extend(self.users[user_token].get('contents', []))

        # 用户的评论
        for comment in self.user_comments.get(user_token, []):
            texts.append(comment.get('content', ''))

        return texts


# 测试代码
if __name__ == "__main__":
    APP_KEY = os.getenv("ZHIHU_COMMUNITY_APP_KEY") or os.getenv("ZHIHU_APP_KEY")
    APP_SECRET = os.getenv("ZHIHU_COMMUNITY_APP_SECRET") or os.getenv("ZHIHU_APP_SECRET")

    if not APP_KEY or not APP_SECRET:
        raise SystemExit("请先设置 ZHIHU_COMMUNITY_APP_KEY 和 ZHIHU_COMMUNITY_APP_SECRET 环境变量")

    api = ZhihuAPI(APP_KEY, APP_SECRET)
    collector = DataCollector(api)

    # 采集数据
    collector.collect_all_rings(max_pages=2)

    # 保存数据
    collector.save_data("zhihu_data.json")
