"""
知乎社区 API 封装模块
提供签名生成和所有 API 调用功能
"""

import hashlib
import hmac
import base64
import os
import time
import uuid
import requests
from typing import Optional, Dict, Any


class ZhihuAPI:
    """知乎社区 API 客户端"""

    BASE_URL = "https://openapi.zhihu.com"

    def __init__(self, app_key: str, app_secret: str):
        """
        初始化 API 客户端

        Args:
            app_key: 用户 token (知乎个人主页 people/ 后面的内容)
            app_secret: 应用密钥
        """
        self.app_key = app_key
        self.app_secret = app_secret

    def _generate_sign(self, timestamp: str, log_id: str, extra_info: str = "") -> str:
        """
        生成 HMAC-SHA256 签名

        Args:
            timestamp: 时间戳（秒级）
            log_id: 请求日志 ID
            extra_info: 额外信息

        Returns:
            Base64 编码的签名
        """
        sign_str = f"app_key:{self.app_key}|ts:{timestamp}|logid:{log_id}|extra_info:{extra_info}"
        h = hmac.new(
            self.app_secret.encode('utf-8'),
            sign_str.encode('utf-8'),
            hashlib.sha256
        )
        return base64.b64encode(h.digest()).decode('utf-8')

    def _get_headers(self, extra_info: str = "") -> Dict[str, str]:
        """
        生成请求头

        Args:
            extra_info: 额外信息

        Returns:
            包含鉴权信息的请求头
        """
        timestamp = str(int(time.time()))
        log_id = f"log_{uuid.uuid4().hex[:16]}"
        sign = self._generate_sign(timestamp, log_id, extra_info)

        return {
            "X-App-Key": self.app_key,
            "X-Timestamp": timestamp,
            "X-Log-Id": log_id,
            "X-Sign": sign,
            "X-Extra-Info": extra_info
        }

    def get_ring_detail(self, ring_id: str, page_num: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """
        获取圈子详情和内容列表

        Args:
            ring_id: 圈子 ID
            page_num: 页码，默认 1
            page_size: 每页条数，最多 50

        Returns:
            API 响应数据
        """
        url = f"{self.BASE_URL}/openapi/ring/detail"
        params = {
            "ring_id": ring_id,
            "page_num": page_num,
            "page_size": min(page_size, 50)
        }

        response = requests.get(url, headers=self._get_headers(), params=params)
        return response.json()

    def publish_pin(self, ring_id: str, content: str, title: str = None, image_urls: list = None) -> Dict[str, Any]:
        """
        在圈子中发布想法

        Args:
            ring_id: 圈子 ID
            content: 内容正文
            title: 标题（可选）
            image_urls: 图片 URL 列表（可选）

        Returns:
            API 响应数据
        """
        url = f"{self.BASE_URL}/openapi/publish/pin"
        headers = self._get_headers()
        headers["Content-Type"] = "application/json"

        data = {
            "content": content,
            "ring_id": ring_id
        }
        if title:
            data["title"] = title
        if image_urls:
            data["image_urls"] = image_urls

        response = requests.post(url, headers=headers, json=data)
        return response.json()

    def get_comment_list(self, content_token: str, content_type: str = "pin",
                         page_num: int = 0, page_size: int = 10) -> Dict[str, Any]:
        """
        获取评论列表

        Args:
            content_token: 想法 ID 或评论 ID
            content_type: 内容类型，"pin"（想法）或 "comment"（评论）
            page_num: 页码，默认 0
            page_size: 每页条数，默认 10，最多 50

        Returns:
            API 响应数据
        """
        url = f"{self.BASE_URL}/openapi/comment/list"
        params = {
            "content_token": content_token,
            "content_type": content_type,
            "page_num": page_num,
            "page_size": min(page_size, 50)
        }

        response = requests.get(url, headers=self._get_headers(), params=params)
        return response.json()

    def create_comment(self, content_token: str, content_type: str, content: str) -> Dict[str, Any]:
        """
        创建评论

        Args:
            content_token: 内容 ID（想法 ID 或评论 ID）
            content_type: 内容类型，"pin"（想法）或 "comment"（评论）
            content: 评论内容

        Returns:
            API 响应数据
        """
        url = f"{self.BASE_URL}/openapi/comment/create"
        headers = self._get_headers()
        headers["Content-Type"] = "application/json"

        data = {
            "content_token": content_token,
            "content_type": content_type,
            "content": content
        }

        response = requests.post(url, headers=headers, json=data)
        return response.json()

    def delete_comment(self, comment_id: str) -> Dict[str, Any]:
        """
        删除评论

        Args:
            comment_id: 评论 ID

        Returns:
            API 响应数据
        """
        url = f"{self.BASE_URL}/openapi/comment/delete"
        headers = self._get_headers()
        headers["Content-Type"] = "application/json"

        data = {"comment_id": comment_id}

        response = requests.post(url, headers=headers, json=data)
        return response.json()

    def reaction(self, content_token: str, content_type: str,
                 action_type: str = "like", action_value: int = 1) -> Dict[str, Any]:
        """
        点赞/取消点赞

        Args:
            content_token: 内容 ID（想法 ID 或评论 ID）
            content_type: 内容类型，"pin"（想法）或 "comment"（评论）
            action_type: 操作类型，目前支持 "like"
            action_value: 操作值，1 表示点赞，0 表示取消点赞

        Returns:
            API 响应数据
        """
        url = f"{self.BASE_URL}/openapi/reaction"
        headers = self._get_headers()
        headers["Content-Type"] = "application/json"

        data = {
            "content_token": content_token,
            "content_type": content_type,
            "action_type": action_type,
            "action_value": action_value
        }

        response = requests.post(url, headers=headers, json=data)
        return response.json()

    def get_story_list(self) -> Dict[str, Any]:
        """
        获取故事概要列表

        Returns:
            API 响应数据
        """
        url = f"{self.BASE_URL}/openapi/hackathon_story/list"
        response = requests.get(url, headers=self._get_headers())
        return response.json()

    def get_story_detail(self, work_id: str) -> Dict[str, Any]:
        """
        获取故事章节详情

        Args:
            work_id: 作品 ID

        Returns:
            API 响应数据
        """
        url = f"{self.BASE_URL}/openapi/hackathon_story/detail"
        params = {"work_id": work_id}

        response = requests.get(url, headers=self._get_headers(), params=params)
        return response.json()


# 测试代码
if __name__ == "__main__":
    # 配置：从环境变量读取社区 API 密钥，避免泄露。
    APP_KEY = os.getenv("ZHIHU_COMMUNITY_APP_KEY") or os.getenv("ZHIHU_APP_KEY")
    APP_SECRET = os.getenv("ZHIHU_COMMUNITY_APP_SECRET") or os.getenv("ZHIHU_APP_SECRET")

    if not APP_KEY or not APP_SECRET:
        raise SystemExit("请先设置 ZHIHU_COMMUNITY_APP_KEY 和 ZHIHU_COMMUNITY_APP_SECRET 环境变量")

    # 创建客户端
    api = ZhihuAPI(APP_KEY, APP_SECRET)

    # 测试获取圈子详情
    print("=== 测试获取圈子详情 ===")
    result = api.get_ring_detail("2001009660925334090")
    print(f"状态: {result.get('status')}")
    print(f"消息: {result.get('msg')}")

    if result.get('status') == 0:
        data = result.get('data', {})
        ring_info = data.get('ring_info', {})
        print(f"圈子名称: {ring_info.get('ring_name')}")
        print(f"成员数量: {ring_info.get('membership_num')}")
        print(f"讨论数量: {ring_info.get('discussion_num')}")

        contents = data.get('contents', [])
        print(f"\n最新内容 ({len(contents)} 条):")
        for i, item in enumerate(contents[:3], 1):
            print(f"  {i}. {item.get('author_name')}: {item.get('content', '')[:50]}...")
