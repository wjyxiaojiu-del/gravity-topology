"""
DeepSeek A2A 对话模块
接入 DeepSeek API 生成真实的 Agent 对话
"""

import json
import os
from typing import Dict, List, Optional
from dotenv import load_dotenv
from openai import OpenAI
from gravity_topology.config import TECH_KEYWORDS, HUMAN_KEYWORDS, TOPICS as SHARED_TOPICS
from gravity_topology.utils import analyze_user_style, build_persona_prompt as build_persona_prompt_shared

load_dotenv()


class DeepSeekA2A:
    """基于 DeepSeek 的 A2A 对话生成器"""

    TOPICS = SHARED_TOPICS

    def __init__(self, api_key: str, data_file: str = "zhihu_data_massive.json"):
        """
        初始化

        Args:
            api_key: DeepSeek API Key
            data_file: 数据文件路径
        """
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )

        with open(data_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

        self.users = self.data.get('users', {})

    def create_persona(self, user_token: str) -> Dict:
        """
        基于用户历史创建人设

        Args:
            user_token: 用户 token

        Returns:
            人设配置
        """
        user = self.users.get(user_token, {})
        contents = user.get('contents', [])

        # 取最有代表性的内容
        sample_contents = contents[:10] if contents else ['暂无内容']

        # 分析风格
        style = self._analyze_style(contents)

        return {
            'token': user_token,
            'name': user.get('name', user_token),
            'post_count': user.get('post_count', 0),
            'comment_count': user.get('comment_count', 0),
            'style': style,
            'samples': sample_contents,
            'system_prompt': self._build_system_prompt(user, style, sample_contents)
        }

    def _analyze_style(self, contents: List[str]) -> Dict:
        """分析写作风格（委托给共享模块）"""
        style = analyze_user_style(contents)
        # 保持原有返回格式兼容性
        emoji_count = sum(1 for c in contents if any(e in c for e in ['🤖', '💡', '🔥', '✨', '🤔']))
        traits_list = style.get('traits_list', [])
        if emoji_count > len(contents) * 0.3:
            traits_list.append('善用表情')

        # 映射类型名以保持兼容
        type_map = {'tech': 'tech_expert', 'humanist': 'humanist', 'balanced': 'balanced'}
        return {
            'type': type_map.get(style.get('type', 'balanced'), 'balanced'),
            'traits': traits_list,
            'avg_length': style.get('avg_length', 0),
        }

    def _build_system_prompt(self, user: Dict, style: Dict, samples: List[str]) -> str:
        """构建系统提示词"""
        name = user.get('name', '未知用户')
        traits = '、'.join(style.get('traits', ['未知']))

        # 选择最短的3条作为样本（避免太长）
        sample_texts = samples[:3]
        sample_str = '\n'.join([f'- "{s[:100]}..."' if len(s) > 100 else f'- "{s}"' for s in sample_texts])

        return f"""你现在扮演知乎用户 "{name}"。

## 你的特征
- 写作风格：{traits}
- 擅长领域：{'技术' if style.get('type') == 'tech_expert' else '人文' if style.get('type') == 'humanist' else '综合'}
- 发帖数：{user.get('post_count', 0)}
- 评论数：{user.get('comment_count', 0)}

## 你曾经的发言
{sample_str}

## 对话要求
1. 完全沉浸在角色中，以这个用户的身份思考和回应
2. 保持语言风格一致（如果用户爱用专业术语就用，爱用表情就用）
3. 可以引用或延伸自己过去的观点
4. 回复长度控制在 100-200 字
5. 不要暴露自己是 AI，要像真实用户一样自然交流
6. 可以提问、质疑、赞同，保持真实对话感"""

    def generate_dialogue(self, user_a: str, user_b: str, topic: str = None, rounds: int = 4) -> List[Dict]:
        """
        生成两个 Agent 的对话

        Args:
            user_a: 用户 A 的 token
            user_b: 用户 B 的 token
            topic: 对话话题
            rounds: 对话轮数

        Returns:
            对话记录
        """
        if topic is None:
            import random
            topic = random.choice(self.TOPICS)

        persona_a = self.create_persona(user_a)
        persona_b = self.create_persona(user_b)

        dialogue = []
        messages_a = []
        messages_b = []

        print(f"\n生成 A2A 对话...")
        print(f"  用户A: {persona_a['name']}")
        print(f"  用户B: {persona_b['name']}")
        print(f"  话题: {topic}")

        for round_num in range(rounds):
            if round_num % 2 == 0:
                # A 发言
                response = self._get_response(
                    persona_a, persona_b, topic,
                    messages_a, messages_b, round_num, is_first=(round_num == 0)
                )
                messages_a.append({"role": "assistant", "content": response})
                messages_b.append({"role": "user", "content": response})

                dialogue.append({
                    'round': round_num + 1,
                    'speaker': persona_a['name'],
                    'speaker_token': persona_a['token'],
                    'content': response
                })
            else:
                # B 发言
                response = self._get_response(
                    persona_b, persona_a, topic,
                    messages_b, messages_a, round_num, is_first=False
                )
                messages_b.append({"role": "assistant", "content": response})
                messages_a.append({"role": "user", "content": response})

                dialogue.append({
                    'round': round_num + 1,
                    'speaker': persona_b['name'],
                    'speaker_token': persona_b['token'],
                    'content': response
                })

            print(f"  [{dialogue[-1]['speaker']}]: {response[:50]}...")

        return dialogue

    def _get_response(self, speaker: Dict, listener: Dict, topic: str,
                      speaker_history: List, listener_history: List,
                      round_num: int, is_first: bool) -> str:
        """获取 AI 回复"""

        # 构建对话历史
        messages = [{"role": "system", "content": speaker['system_prompt']}]

        # 添加话题上下文
        if is_first:
            messages.append({
                "role": "user",
                "content": f"话题讨论：{topic}\n\n请以你的身份，针对这个话题发表看法。这是开场发言。"
            })
        else:
            # 添加历史对话：speaker_history 里自己说的=assistant，listener_history 里对方说的=user
            # 按轮次交替排列，保留最近几轮
            recent_speaker = speaker_history[-2:]
            recent_listener = listener_history[-2:]
            for i in range(max(len(recent_speaker), len(recent_listener))):
                if i < len(recent_speaker):
                    messages.append({"role": "assistant", "content": recent_speaker[i]['content']})
                if i < len(recent_listener):
                    messages.append({"role": "user", "content": recent_listener[i]['content']})

            messages.append({
                "role": "user",
                "content": f"继续讨论话题：{topic}\n\n请回应对方的观点，并表达你的看法。"
            })

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                max_tokens=300,
                temperature=0.8
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"  API 调用失败: {e}")
            return f"[API 错误: {str(e)}]"

    def generate_report(self, user_a: str, user_b: str, gravity: float, dialogue: List[Dict]) -> str:
        """生成引力探测报告"""
        persona_a = self.create_persona(user_a)
        persona_b = self.create_persona(user_b)

        report = f"""
{'='*60}
        引力拓扑 · 探测报告
{'='*60}

■ 探测对象
  用户A: {persona_a['name']}
    - 发帖 {persona_a['post_count']} 篇
    - 评论 {persona_a['comment_count']} 条
    - 风格: {', '.join(persona_a['style']['traits'])}

  用户B: {persona_b['name']}
    - 发帖 {persona_b['post_count']} 篇
    - 评论 {persona_b['comment_count']} 条
    - 风格: {', '.join(persona_b['style']['traits'])}

■ 引力分析
  引力值: {gravity:.4f}
  现实交互: 无
  特征相似度: {'极高' if gravity > 0.8 else '高' if gravity > 0.6 else '中等'}

■ Agent 对话摘要
"""
        for item in dialogue:
            report += f"\n  [{item['speaker']}]\n  {item['content']}\n"

        report += f"""
■ 洞察
  根据引力拓扑算法分析，{persona_a['name']} 和 {persona_b['name']}
  在内容偏好和思维模式上具有高度相似性。

  他们可能在以下方面有共同话题：
  - AI 技术发展
  - 社区生态建设
  - 知识分享与交流

  建议：关注对方的优质内容，开启跨界对话。

{'='*60}
        由 引力拓扑 系统自动生成
        Powered by DeepSeek AI
{'='*60}
"""
        return report

    def save_dialogue(self, dialogue: List[Dict], report: str, filename: str = "a2a_result.json") -> None:
        """保存对话结果"""
        result = {
            'dialogue': dialogue,
            'report': report
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"对话结果已保存到: {filename}")


# 测试
if __name__ == "__main__":
    API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    if not API_KEY:
        print("请设置 DEEPSEEK_API_KEY 环境变量")
        exit(1)

    a2a = DeepSeekA2A(API_KEY, "zhihu_data_massive.json")

    # 找一个有内容的用户对测试
    with open("gravity_results_optimized.json", 'r', encoding='utf-8') as f:
        results = json.load(f)

    pairs = results.get('hidden_pairs', [])
    if pairs:
        best = pairs[0]
        dialogue = a2a.generate_dialogue(best['user_a'], best['user_b'], rounds=4)
        report = a2a.generate_report(best['user_a'], best['user_b'], best['gravity'], dialogue)
        print(report)
        a2a.save_dialogue(dialogue, report)
