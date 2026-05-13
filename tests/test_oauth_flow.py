import unittest

import app


class FakeResponse:
    def __init__(self, payload, status_code=200, text=""):
        self.payload = payload
        self.status_code = status_code
        self.text = text or str(payload)

    def json(self):
        return self.payload


class FakeRequests:
    def post(self, *args, **kwargs):
        return FakeResponse({"access_token": "test-token", "token_type": "Bearer", "expires_in": 3600})

    def get(self, *args, **kwargs):
        return FakeResponse({"uid": 1, "fullname": "测试用户", "avatar_path": "", "headline": "知乎用户"})


class TokenErrorRequests:
    def post(self, *args, **kwargs):
        return FakeResponse({"code": 20001, "data": "Access denied: not exists"})

    def get(self, *args, **kwargs):
        raise AssertionError("user info should not be requested without an access token")


class NestedTokenRequests:
    def post(self, *args, **kwargs):
        return FakeResponse({"code": 0, "data": {"access_token": "nested-token"}})

    def get(self, *args, **kwargs):
        return FakeResponse({"code": 401, "data": "API Access Deny"})


class OAuthFlowTests(unittest.TestCase):
    def setUp(self):
        app.app.testing = True
        self.client = app.app.test_client()
        self.original_requests = app.http_requests
        app.http_requests = FakeRequests()
        self._orig_app_id = app.ZHIHU_OAUTH_APP_ID
        self._orig_app_key = app.ZHIHU_OAUTH_APP_KEY
        self._orig_redirect_uri = app.ZHIHU_OAUTH_REDIRECT_URI
        app.ZHIHU_OAUTH_APP_ID = "test-app-id"
        app.ZHIHU_OAUTH_APP_KEY = "test-app-key"
        app.ZHIHU_OAUTH_REDIRECT_URI = "http://localhost:8050/callback"

    def tearDown(self):
        app.http_requests = self.original_requests
        app.ZHIHU_OAUTH_APP_ID = self._orig_app_id
        app.ZHIHU_OAUTH_APP_KEY = self._orig_app_key
        app.ZHIHU_OAUTH_REDIRECT_URI = self._orig_redirect_uri

    def test_callback_accepts_authorization_code_when_zhihu_omits_state(self):
        self.client.get("/login", follow_redirects=False)

        response = self.client.get("/callback?code=test-code", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/?login=success")
        with self.client.session_transaction() as session:
            self.assertEqual(session.get("access_token"), "test-token")
            self.assertEqual(session.get("zhihu_user", {}).get("name"), "测试用户")

    def test_api_me_reports_logged_in_when_token_exists_without_user_profile(self):
        with self.client.session_transaction() as session:
            session["access_token"] = "test-token"

        response = self.client.get("/api/me")
        payload = response.get_json()

        self.assertTrue(payload["logged_in"])
        self.assertEqual(payload["user"]["name"], "已连接知乎")

    def test_login_redirect_url_encodes_redirect_uri_parameter(self):
        response = self.client.get("/login", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertIn("redirect_uri=http%3A%2F%2Flocalhost%3A8050%2Fcallback", response.headers["Location"])

    def test_callback_redirects_with_provider_detail_when_token_response_has_no_access_token(self):
        app.http_requests = TokenErrorRequests()

        response = self.client.get("/callback?code=test-code", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertIn("error=no_token", response.headers["Location"])
        self.assertIn("oauth_detail=Access+denied%3A+not+exists", response.headers["Location"])

    def test_callback_accepts_nested_access_token_payload(self):
        app.http_requests = NestedTokenRequests()

        response = self.client.get("/callback?code=test-code", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/?login=success")
        with self.client.session_transaction() as session:
            self.assertEqual(session.get("access_token"), "nested-token")
            self.assertEqual(session.get("zhihu_user", {}).get("name"), "已连接知乎")


if __name__ == "__main__":
    unittest.main()
