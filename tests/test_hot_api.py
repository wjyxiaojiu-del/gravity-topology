import unittest
from collections import Counter

import app


class ZhihuHotApiTests(unittest.TestCase):
    def setUp(self):
        app.app.testing = True
        self.client = app.app.test_client()

    def test_hot_api_returns_local_fallback_items_with_links_and_related_users(self):
        response = self.client.get("/api/zhihu_hot")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn(data["source"], {"local_community", "configured_api"})
        self.assertGreater(len(data["items"]), 0)

        first = data["items"][0]
        for key in ["id", "rank", "title", "excerpt", "url", "heat", "domain", "related_users"]:
            self.assertIn(key, first)
        self.assertTrue(first["title"].strip())
        self.assertTrue(first["url"].startswith("http"))
        self.assertIsInstance(first["related_users"], list)

    def test_inspire_api_returns_full_local_fallback_fields(self):
        response = self.client.post("/api/inspire", json={"topic": "人工智能"})
        self.assertEqual(response.status_code, 200)
        d = response.get_json()
        for key in ["topic", "titles", "outline", "pro_viewpoints", "con_viewpoints", "quotes", "draft", "source",
                    "heat_analysis", "audience_profile", "similar_angles", "keyword_tags",
                    "content_format", "risk_alert", "comment_strategy", "related_topics"]:
            self.assertIn(key, d, f"missing key: {key}")
        self.assertIn(d["source"], {"local", "llm"})
        self.assertGreater(len(d["titles"]), 0)
        self.assertGreater(len(d["outline"]), 0)
        self.assertIsInstance(d["heat_analysis"], dict)
        self.assertIsInstance(d["audience_profile"], list)
        self.assertIsInstance(d["similar_angles"], list)

    def test_hot_api_filters_items_by_domain(self):
        response = self.client.get("/api/zhihu_hot?domain=ai_tech")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["domain"], "ai_tech")
        self.assertGreater(len(data["items"]), 0)
        self.assertTrue(all(item["domain"] == "ai_tech" for item in data["items"]))

    def test_hot_api_excludes_obvious_bot_authors_from_local_fallback(self):
        response = self.client.get("/api/zhihu_hot")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        author_names = [item.get("author", "").lower() for item in data["items"]]
        self.assertFalse(any("bot" in name for name in author_names))

    def test_all_hot_api_interleaves_available_domains_instead_of_ai_only(self):
        response = self.client.get("/api/zhihu_hot")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        counts = Counter(item["domain"] for item in data["items"])
        self.assertGreaterEqual(len(counts), 4)
        self.assertLessEqual(counts["ai_tech"], len(data["items"]) * 0.6)


if __name__ == "__main__":
    unittest.main()
