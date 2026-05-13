import unittest

import app


class StaticAssetTests(unittest.TestCase):
    def setUp(self):
        app.app.testing = True
        self.client = app.app.test_client()

    def test_favicon_request_does_not_create_browser_console_404(self):
        response = self.client.get("/favicon.ico")

        self.assertNotEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
