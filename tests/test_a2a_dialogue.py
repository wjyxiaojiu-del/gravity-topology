import unittest

from a2a_dialogue import A2ADialogue


class FakeCollector:
    def __init__(self):
        self.users = {
            "alice": {
                "token": "alice",
                "name": "算法猫",
                "post_count": 2,
                "comment_count": 1,
                "total_likes": 12,
                "contents": [
                    "我更关心模型评估和数据闭环，A/B 实验不能只看点击率。",
                    "推荐系统应该解释为什么把两个人连接起来。",
                ],
            },
            "bob": {
                "token": "bob",
                "name": "社群观察员",
                "post_count": 1,
                "comment_count": 3,
                "total_likes": 20,
                "contents": [
                    "社区连接不只是相似度，还要看人愿不愿意开始一段对话。",
                    "技术需要给用户留下解释和拒绝的空间。",
                ],
            },
        }

    def get_user_texts(self, user_token):
        return self.users[user_token]["contents"]


class RecordingProvider:
    def __init__(self):
        self.calls = []

    def generate(self, speaker, listener, topic, dialogue_history, round_num):
        self.calls.append(
            {
                "speaker": speaker,
                "listener": listener,
                "topic": topic,
                "dialogue_history": list(dialogue_history),
                "round_num": round_num,
            }
        )
        return f"{speaker['name']} 对 {listener['name']} 说：第 {round_num + 1} 轮讨论 {topic}"


class A2ADialogueProviderTests(unittest.TestCase):
    def test_generate_dialogue_uses_injected_provider_for_each_round(self):
        provider = RecordingProvider()
        a2a = A2ADialogue(FakeCollector(), response_provider=provider)

        dialogue = a2a.generate_dialogue("alice", "bob", topic="社区引力", rounds=2)

        self.assertEqual(len(dialogue), 2)
        self.assertEqual(len(provider.calls), 2)
        self.assertEqual(dialogue[0]["content"], "算法猫 对 社群观察员 说：第 1 轮讨论 社区引力")
        self.assertEqual(dialogue[1]["content"], "社群观察员 对 算法猫 说：第 2 轮讨论 社区引力")
        self.assertEqual(provider.calls[1]["dialogue_history"][0]["content"], dialogue[0]["content"])

    def test_local_provider_creates_contextual_nonempty_dialogue_without_api_key(self):
        a2a = A2ADialogue(FakeCollector(), response_provider="local")

        dialogue = a2a.generate_dialogue("alice", "bob", topic="社区引力", rounds=3)

        self.assertEqual(len(dialogue), 3)
        self.assertTrue(all(item["content"].strip() for item in dialogue))
        self.assertTrue(any("算法猫" in item["content"] or "社群观察员" in item["content"] for item in dialogue))
        self.assertTrue(any("社区引力" in item["content"] for item in dialogue))


if __name__ == "__main__":
    unittest.main()
