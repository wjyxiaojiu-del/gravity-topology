"""
大规模数据采集模块
采集所有圈子的全部数据
"""

import json
import time
from typing import Dict, List, Set
from collections import defaultdict
from zhihu_api import ZhihuAPI
from gravity_topology.utils import clean_html
from gravity_topology.config import RINGS


class MassiveCollector:
    """大规模数据采集器"""

    RINGS = RINGS

    def __init__(self, api: ZhihuAPI):
        self.api = api
        self.users: Dict[str, Dict] = {}
        self.posts: List[Dict] = []
        self.comments: List[Dict] = []
        self.interaction_matrix: Dict[str, Set[str]] = defaultdict(set)

    def collect_all(self) -> None:
        """采集所有圈子的全部数据"""
        print("=" * 60)
        print("开始大规模数据采集")
        print("=" * 60)

        for ring_id, ring_name in self.RINGS.items():
            self._collect_ring(ring_id, ring_name)

        self._print_stats()

    def _collect_ring(self, ring_id: str, ring_name: str) -> None:
        """采集单个圈子"""
        print(f"\n采集圈子: {ring_name}")
        print("-" * 40)

        total_posts = 0
        total_comments = 0

        for page in range(1, 21):  # 最多20页，每页50条 = 1000条
            result = self.api.get_ring_detail(ring_id, page_num=page, page_size=50)

            if result.get('status') != 0:
                print(f"  第 {page} 页错误: {result.get('msg')}")
                break

            contents = result.get('data', {}).get('contents', [])
            if not contents:
                print(f"  第 {page} 页无内容，停止")
                break

            for post in contents:
                self._process_post(post, ring_id)

            page_comments = sum(len(p.get('comments', [])) for p in contents)
            total_posts += len(contents)
            total_comments += page_comments

            print(f"  第 {page:2d} 页: {len(contents)} 帖子, {page_comments} 评论")

            time.sleep(0.3)

        print(f"  小计: {total_posts} 帖子, {total_comments} 评论")

    def _process_post(self, post: Dict, ring_id: str) -> None:
        """处理帖子"""
        pin_id = str(post.get('pin_id'))
        author_name = post.get('author_name', 'unknown')
        author_token = post.get('author_token', author_name)
        content = clean_html(post.get('content', ''))

        # 存储帖子
        self.posts.append({
            'pin_id': pin_id,
            'content': content,
            'author_name': author_name,
            'author_token': author_token,
            'like_num': post.get('like_num', 0),
            'comment_num': post.get('comment_num', 0),
            'share_num': post.get('share_num', 0),
            'fav_num': post.get('fav_num', 0),
            'publish_time': post.get('publish_time', 0),
            'ring_id': ring_id
        })

        # 更新用户
        if author_token not in self.users:
            self.users[author_token] = {
                'token': author_token,
                'name': author_name,
                'post_count': 0,
                'comment_count': 0,
                'total_likes': 0,
                'total_shares': 0,
                'total_favs': 0,
                'contents': [],
                'post_times': [],
                'ring_activity': defaultdict(int)
            }

        user = self.users[author_token]
        user['post_count'] += 1
        user['total_likes'] += post.get('like_num', 0)
        user['total_shares'] += post.get('share_num', 0)
        user['total_favs'] += post.get('fav_num', 0)
        user['post_times'].append(post.get('publish_time', 0))
        user['ring_activity'][ring_id] += 1

        if content:
            user['contents'].append(content)

        # 处理评论
        for comment in post.get('comments', []):
            self._process_comment(comment, pin_id, author_token)

    def _process_comment(self, comment: Dict, pin_id: str, post_author: str) -> None:
        """处理评论"""
        comment_id = str(comment.get('comment_id'))
        commenter_name = comment.get('author_name', 'unknown')
        commenter_token = comment.get('author_token', commenter_name)
        content = clean_html(comment.get('content', ''))

        self.comments.append({
            'comment_id': comment_id,
            'content': content,
            'author_name': commenter_name,
            'author_token': commenter_token,
            'like_count': comment.get('like_count', 0),
            'pin_id': pin_id,
            'post_author': post_author,
            'publish_time': comment.get('publish_time', 0)
        })

        if commenter_token not in self.users:
            self.users[commenter_token] = {
                'token': commenter_token,
                'name': commenter_name,
                'post_count': 0,
                'comment_count': 0,
                'total_likes': 0,
                'total_shares': 0,
                'total_favs': 0,
                'contents': [],
                'post_times': [],
                'ring_activity': defaultdict(int)
            }

        self.users[commenter_token]['comment_count'] += 1
        if content:
            self.users[commenter_token]['contents'].append(content)

        # 互动关系
        if commenter_token != post_author:
            self.interaction_matrix[commenter_token].add(post_author)
            self.interaction_matrix[post_author].add(commenter_token)

    def _print_stats(self) -> None:
        """打印统计信息"""
        print("\n" + "=" * 60)
        print("数据采集完成!")
        print("=" * 60)
        print(f"用户数量: {len(self.users)}")
        print(f"帖子数量: {len(self.posts)}")
        print(f"评论数量: {len(self.comments)}")

        # 有内容的用户统计
        users_with_content = sum(1 for u in self.users.values() if len(u['contents']) >= 3)
        print(f"有内容用户(>=3条): {users_with_content}")

    def save(self, filename: str = "massive_data.json") -> None:
        """保存数据"""
        # 转换 defaultdict
        interaction = {k: list(v) for k, v in self.interaction_matrix.items()}

        # 转换用户的 ring_activity
        users_save = {}
        for token, user in self.users.items():
            user_copy = user.copy()
            user_copy['ring_activity'] = dict(user_copy['ring_activity'])
            users_save[token] = user_copy

        data = {
            'users': users_save,
            'posts': self.posts,
            'comments': self.comments,
            'interaction_matrix': interaction,
            'collect_time': time.strftime('%Y-%m-%d %H:%M:%S')
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"\n数据已保存到: {filename}")


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()

    APP_KEY = os.getenv("ZHIHU_COMMUNITY_APP_KEY", "") or os.getenv("ZHIHU_APP_KEY", "")
    APP_SECRET = os.getenv("ZHIHU_COMMUNITY_APP_SECRET", "") or os.getenv("ZHIHU_APP_SECRET", "")
    if not APP_KEY or not APP_SECRET:
        raise RuntimeError("请设置 ZHIHU_COMMUNITY_APP_KEY 和 ZHIHU_COMMUNITY_APP_SECRET 环境变量")

    api = ZhihuAPI(APP_KEY, APP_SECRET)
    collector = MassiveCollector(api)
    collector.collect_all()
    collector.save("massive_data.json")
