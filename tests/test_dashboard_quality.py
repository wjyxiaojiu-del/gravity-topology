import unittest

import app


class DashboardQualityTests(unittest.TestCase):
    def setUp(self):
        app.app.testing = True
        self.client = app.app.test_client()

    def test_dashboard_returns_cleaning_summary(self):
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        ov = data["overview"]
        self.assertIn("total_users", ov)
        self.assertIn("bot_filtered", ov)
        self.assertIn("real_users", ov)
        self.assertIn("total_posts", ov)
        self.assertIn("total_comments", ov)
        self.assertIn("agent_interactions", ov)

    def test_dashboard_top_users_has_no_bot(self):
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        for user in data["top_users"]:
            name_lower = user.get("name", "").lower()
            self.assertNotIn("bot", name_lower)

    def test_dashboard_domain_heat_has_unknown(self):
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertIn("unknown", data["domain_heat"])
        self.assertEqual(data["domain_heat"]["unknown"]["name"], "未归类")

    def test_dashboard_has_hot_domain_counts(self):
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()

        self.assertIn("hot_domain_counts", data)


if __name__ == "__main__":
    unittest.main()
