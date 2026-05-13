import unittest
from unittest.mock import patch, MagicMock

import app


class FakeResponse:
    def __init__(self, payload, status_code=200, text=""):
        self.payload = payload
        self.status_code = status_code
        self.text = text or str(payload)

    def json(self):
        return self.payload


class MyZhihuUniverseTests(unittest.TestCase):
    def setUp(self):
        app.app.testing = True
        self.client = app.app.test_client()

    def test_universe_returns_401_when_not_logged_in(self):
        response = self.client.get('/api/my_zhihu_universe')
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertIn('error', data)
        self.assertFalse(data.get('logged_in', True))

    def test_universe_returns_domain_distribution_when_logged_in(self):
        followed_data = [
            {'fullname': '张三', 'headline': 'AI 算法工程师', 'description': '深度学习', 'avatar_path': '', 'url': 'https://zhihu.com/people/zhangsan'},
            {'fullname': '李四', 'headline': '人文博主', 'description': '哲学思考', 'avatar_path': '', 'url': 'https://zhihu.com/people/lisi'},
            {'fullname': '王五', 'headline': '产品经理', 'description': '产品设计', 'avatar_path': '', 'url': 'https://zhihu.com/people/wangwu'},
        ]

        def fake_get(url, **kwargs):
            if 'followed' in url:
                return FakeResponse(followed_data)
            return FakeResponse({})

        with self.client.session_transaction() as sess:
            sess['access_token'] = 'test-token'
            sess['zhihu_user'] = {'name': '测试用户', 'avatar': '', 'headline': ''}

        original = app.http_requests
        app.http_requests = MagicMock()
        app.http_requests.get.side_effect = fake_get

        try:
            response = self.client.get('/api/my_zhihu_universe')
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data['logged_in'])
            self.assertIn('domain_distribution', data)
            self.assertIsInstance(data['domain_distribution'], dict)
            self.assertEqual(data['followed_count'], 3)
        finally:
            app.http_requests = original

    def test_universe_has_required_fields(self):
        followed_data = [
            {'fullname': '技术人', 'headline': 'AI 工程师', 'description': '', 'avatar_path': '', 'url': ''},
            {'fullname': '文青', 'headline': '作家', 'description': '', 'avatar_path': '', 'url': ''},
        ]

        def fake_get(url, **kwargs):
            return FakeResponse(followed_data)

        with self.client.session_transaction() as sess:
            sess['access_token'] = 'test-token'
            sess['zhihu_user'] = {'name': '测试', 'avatar': ''}

        original = app.http_requests
        app.http_requests = MagicMock()
        app.http_requests.get.side_effect = fake_get

        try:
            response = self.client.get('/api/my_zhihu_universe')
            data = response.get_json()

            self.assertIn('same_frequency_users', data)
            self.assertIsInstance(data['same_frequency_users'], list)

            self.assertIn('complementary_users', data)
            self.assertIsInstance(data['complementary_users'], list)

            self.assertIn('breakout_users', data)
            self.assertIsInstance(data['breakout_users'], list)

            self.assertIn('roundtable_candidates', data)
            self.assertIsInstance(data['roundtable_candidates'], list)

            self.assertIn('filter_bubble_score', data)
            self.assertIsInstance(data['filter_bubble_score'], int)
            self.assertGreaterEqual(data['filter_bubble_score'], 0)
            self.assertLessEqual(data['filter_bubble_score'], 100)

            self.assertIn('insights', data)
            self.assertIsInstance(data['insights'], list)
        finally:
            app.http_requests = original

    def test_followed_user_has_avatar_and_url(self):
        followed_data = [
            {'fullname': '用户A', 'headline': '工程师', 'description': '', 'avatar_path': 'https://pic.jpg', 'url': 'https://zhihu.com/people/a'},
        ]

        def fake_get(url, **kwargs):
            return FakeResponse(followed_data)

        with self.client.session_transaction() as sess:
            sess['access_token'] = 'test-token'
            sess['zhihu_user'] = {'name': '测试', 'avatar': ''}

        original = app.http_requests
        app.http_requests = MagicMock()
        app.http_requests.get.side_effect = fake_get

        try:
            response = self.client.get('/api/my_zhihu_universe')
            data = response.get_json()

            for user_list_key in ['same_frequency_users', 'complementary_users', 'breakout_users', 'roundtable_candidates']:
                for u in data.get(user_list_key, []):
                    self.assertIn('avatar', u, f'{user_list_key} user missing avatar')
                    self.assertIn('url', u, f'{user_list_key} user missing url')
                    self.assertIn('name', u, f'{user_list_key} user missing name')
        finally:
            app.http_requests = original

    def test_universe_handles_zhihu_api_error_gracefully(self):
        def fake_get(url, **kwargs):
            return FakeResponse({}, status_code=500, text='Internal Server Error')

        with self.client.session_transaction() as sess:
            sess['access_token'] = 'test-token'
            sess['zhihu_user'] = {'name': '测试', 'avatar': ''}

        original = app.http_requests
        app.http_requests = MagicMock()
        app.http_requests.get.side_effect = fake_get

        try:
            response = self.client.get('/api/my_zhihu_universe')
            self.assertIn(response.status_code, [502, 200])
            data = response.get_json()
            # 应该有错误信息，不应该 500 白屏
            self.assertTrue('error' in data or 'logged_in' in data)
        finally:
            app.http_requests = original

    def test_universe_falls_back_to_demo_when_followed_permission_is_denied(self):
        def fake_get(url, **kwargs):
            return FakeResponse({'code': 403, 'data': 'API Access Deny'})

        with self.client.session_transaction() as sess:
            sess['access_token'] = 'test-token'
            sess['zhihu_user'] = {'name': '测试', 'avatar': ''}

        original = app.http_requests
        app.http_requests = MagicMock()
        app.http_requests.get.side_effect = fake_get

        try:
            response = self.client.get('/api/my_zhihu_universe')
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data['logged_in'])
            self.assertTrue(data['permission_limited'])
            self.assertGreater(data['followed_count'], 0)
            self.assertGreater(len(data.get('roundtable_candidates', [])), 0)
        finally:
            app.http_requests = original

    def test_filter_bubble_score_computation(self):
        # 高集中度
        dist_high = {'ai_tech': 90, 'humanities': 5, 'society': 3, 'life': 1, 'creative': 1, 'unknown': 0}
        score_high = app._compute_filter_bubble_score(dist_high)
        self.assertGreater(score_high, 60)

        # 均匀分布
        dist_low = {'ai_tech': 20, 'humanities': 20, 'society': 20, 'life': 20, 'creative': 20, 'unknown': 0}
        score_low = app._compute_filter_bubble_score(dist_low)
        self.assertLess(score_low, 30)

    def test_analyze_followed_user_extracts_domain(self):
        user = {'fullname': 'AI研究员', 'headline': '大模型算法工程师', 'description': '深度学习和自然语言处理'}
        profile = app._analyze_followed_user(user)
        self.assertEqual(profile['primary_domain'], 'ai_tech')
        self.assertIn('domain_scores', profile)
        self.assertIn('style_type', profile)
        self.assertIn('avatar', profile)
        self.assertIn('url', profile)


if __name__ == '__main__':
    unittest.main()
