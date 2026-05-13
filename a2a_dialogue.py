"""
A2A 对话模块
基于用户历史内容生成 Agent 对话
"""

import json
import os
import random
from typing import Dict, List, Optional, Protocol, Union

import requests
from data_collector import DataCollector
from gravity_topology.config import TECH_KEYWORDS, HUMAN_KEYWORDS, QUESTION_KEYWORDS, TOPICS as SHARED_TOPICS
from gravity_topology.utils import analyze_user_style, build_persona_prompt as build_persona_prompt_shared


class DialogueResponseProvider(Protocol):
    """A pluggable response generator for one Agent turn."""

    def generate(
        self,
        speaker: Dict,
        listener: Dict,
        topic: str,
        dialogue_history: List[Dict],
        round_num: int
    ) -> str:
        ...


class LocalNarrativeProvider:
    """离线兜底生成器：没有 OpenAI key 时也能稳定演示。"""

    def generate(
        self,
        speaker: Dict,
        listener: Dict,
        topic: str,
        dialogue_history: List[Dict],
        round_num: int
    ) -> str:
        style = speaker.get('writing_style', {})
        traits = '、'.join(style.get('traits', [])[:2]) or '表达克制'
        samples = [t for t in speaker.get('sample_texts', []) if t]
        sample = samples[round_num % len(samples)][:46] if samples else ''
        previous = dialogue_history[-1]['content'] if dialogue_history else ''
        previous_hint = self._summarize_previous_turn(previous)

        if round_num == 0:
            return (
                f"{speaker['name']}先把{topic}落到自己的经验里：{sample}"
                f"。我会从{traits}的角度看，连接不是匹配分数，而是一次可解释的邀请。"
            )

        return (
            f"{speaker['name']}接着{listener['name']}的意思往前推：{previous_hint}"
            f"。放在{topic}里，我会更关注解释权和选择权。{sample}"
        )

    def _summarize_previous_turn(self, previous: str) -> str:
        if not previous:
            return "上一轮还没有形成明确立场"

        cleaned = previous
        for marker in ["：", ":"]:
            if marker in cleaned:
                cleaned = cleaned.split(marker, 1)[1]
                break
        cleaned = cleaned.replace("“", "").replace("”", "").strip()
        return cleaned[:38] or "对方提出了一个值得继续展开的方向"


class OpenAIResponsesProvider:
    """OpenAI Responses API provider for richer A2A dialogue."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1/responses",
        timeout: int = 30
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.5")
        self.base_url = base_url
        self.timeout = timeout

    def generate(
        self,
        speaker: Dict,
        listener: Dict,
        topic: str,
        dialogue_history: List[Dict],
        round_num: int
    ) -> str:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        history_text = "\n".join(
            f"{item['speaker']}: {item['content']}" for item in dialogue_history[-6:]
        ) or "暂无上一轮对话。"

        payload = {
            "model": self.model,
            "instructions": speaker.get('persona_prompt', ''),
            "input": (
                f"话题：{topic}\n"
                f"你正在和知乎用户“{listener['name']}”对话。\n"
                f"当前是第 {round_num + 1} 轮。\n\n"
                f"已有对话：\n{history_text}\n\n"
                "请生成这一轮回复。要求：自然、有观点、像真人在接话；"
                "不要解释你是 AI；不要输出引号或列表；控制在 80-180 个中文字符。"
            ),
            "max_output_tokens": 260
        }

        response = requests.post(
            self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()
        data = response.json()
        return self._extract_text(data)

    def _extract_text(self, data: Dict) -> str:
        if data.get("output_text"):
            return data["output_text"].strip()

        chunks = []
        for item in data.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")
                if text:
                    chunks.append(text)

        text = "".join(chunks).strip()
        if not text:
            raise ValueError("OpenAI response did not contain text")
        return text


class A2ADialogue:
    """Agent-to-Agent 对话生成器"""

    TOPICS = SHARED_TOPICS

    def __init__(
        self,
        collector: DataCollector,
        response_provider: Union[DialogueResponseProvider, str, None] = None,
        model: Optional[str] = None
    ):
        """
        初始化 A2A 对话生成器

        Args:
            collector: 数据采集器实例
            response_provider: 对话生成器。传入 "local" 强制使用本地生成。
            model: OpenAI 模型名，默认读取 OPENAI_MODEL 或 gpt-5.5
        """
        self.collector = collector
        self.users = collector.users
        self.response_provider = self._resolve_provider(response_provider, model)

    def _resolve_provider(
        self,
        response_provider: Union[DialogueResponseProvider, str, None],
        model: Optional[str]
    ) -> DialogueResponseProvider:
        if response_provider == "local":
            return LocalNarrativeProvider()
        if response_provider is not None:
            return response_provider
        if os.getenv("OPENAI_API_KEY"):
            return OpenAIResponsesProvider(model=model)
        return LocalNarrativeProvider()

    def create_agent_persona(self, user_token: str) -> Dict:
        """
        基于用户历史内容创建 Agent 人设

        Args:
            user_token: 用户 token

        Returns:
            Agent 人设配置
        """
        user_info = self.users.get(user_token, {})
        user_texts = self.collector.get_user_texts(user_token)

        # 提取用户特征
        name = user_info.get('name', user_token)
        total_texts = len(user_texts)
        avg_length = sum(len(t) for t in user_texts) / max(total_texts, 1)

        # 分析写作风格
        style = self._analyze_writing_style(user_texts)

        # 生成人设描述
        persona = {
            'token': user_token,
            'name': name,
            'post_count': user_info.get('post_count', 0),
            'comment_count': user_info.get('comment_count', 0),
            'total_likes': user_info.get('total_likes', 0),
            'writing_style': style,
            'sample_texts': user_texts[:5],  # 最多保留5条样本
            'persona_prompt': self._generate_persona_prompt(name, style, user_texts)
        }

        return persona

    def _analyze_writing_style(self, texts: List[str]) -> Dict:
        """
        分析写作风格（委托给共享模块）

        Args:
            texts: 用户文本列表

        Returns:
            风格特征
        """
        style = analyze_user_style(texts)
        # 保持原有返回格式兼容性
        return {
            'type': style.get('type', 'unknown'),
            'avg_length': style.get('avg_length', 0),
            'traits': style.get('traits_list', []),
            'tech_score': style.get('tech_score', 0),
            'human_score': style.get('human_score', 0),
        }

    def get_user_info(self, user_token: str) -> Dict:
        """获取用户信息"""
        return self.users.get(user_token, {'token': user_token, 'name': 'Unknown'})

    def _generate_persona_prompt(self, name: str, style: Dict, texts: List[str]) -> str:
        """
        生成 Agent 人设 Prompt

        Args:
            name: 用户名
            style: 写作风格
            texts: 用户文本

        Returns:
            人设 Prompt
        """
        # 选择有代表性的文本
        sample = texts[:3] if texts else ['暂无内容']

        traits_str = '、'.join(style.get('traits', ['未知']))

        prompt = f"""你现在扮演知乎用户 "{name}"。

## 你的特征
- 写作风格: {traits_str}
- 擅长领域: {'技术' if style.get('tech_score', 0) > style.get('human_score', 0) else '人文'}

## 你曾经的发言
{chr(10).join(f'- "{t[:100]}..."' if len(t) > 100 else f'- "{t}"' for t in sample)}

## 对话要求
1. 保持这个用户的语言风格和观点倾向
2. 基于你曾经的发言内容进行回应
3. 可以适当引用自己过去的观点
4. 保持真实和一致性
5. 回复长度控制在 50-150 字

现在请以这个身份参与讨论。"""

        return prompt

    def generate_dialogue(self, user_a: str, user_b: str, topic: str = None, rounds: int = 3) -> List[Dict]:
        """
        生成两个 Agent 之间的对话

        Args:
            user_a: 用户 A 的 token
            user_b: 用户 B 的 token
            topic: 对话话题（可选）
            rounds: 对话轮数

        Returns:
            对话记录列表
        """
        if topic is None:
            topic = random.choice(self.TOPICS)

        persona_a = self.create_agent_persona(user_a)
        persona_b = self.create_agent_persona(user_b)

        dialogue = []

        for round_num in range(rounds):
            if round_num % 2 == 0:
                speaker = persona_a
                listener = persona_b
            else:
                speaker = persona_b
                listener = persona_a

            response = self.response_provider.generate(
                speaker=speaker,
                listener=listener,
                topic=topic,
                dialogue_history=dialogue,
                round_num=round_num
            )

            dialogue.append({
                'round': round_num + 1,
                'speaker': speaker['name'],
                'speaker_token': speaker['token'],
                'content': response,
                'topic': topic
            })

        return dialogue

    def _generate_response(self, speaker: Dict, listener: Dict, topic: str, round_num: int) -> str:
        """
        生成对话回复（模板方式）

        Args:
            speaker: 说话者人设
            listener: 倾听者人设
            topic: 话题
            round_num: 轮次

        Returns:
            回复内容
        """
        style = speaker.get('writing_style', {})
        style_type = style.get('type', 'balanced')
        traits = style.get('traits', [])

        # 选择样本
        samples = speaker.get('sample_texts', [''])
        sample = random.choice(samples) if samples else ''

        # 根据风格生成不同回复
        if style_type == 'tech_oriented':
            templates = [
                f"关于{topic}，从技术角度看，我认为核心在于算法优化和数据处理效率的提升。{sample[:50] if sample else ''}",
                f"这个问题让我想到之前研究过的一个技术方案。{topic}的关键可能在于底层架构的创新。",
                f"用数据说话：{topic}领域的发展速度远超预期，我们需要更系统化的思考方式。"
            ]
        elif style_type == 'human_oriented':
            templates = [
                f"从人文视角看{topic}，我们不能忽视技术对社会结构的深层影响。{sample[:50] if sample else ''}",
                f"这个问题触及了{topic}的本质：技术与人性的平衡。我们需要更多跨学科的对话。",
                f"关于{topic}，我更关心的是它如何改变我们的认知方式和社交模式。"
            ]
        else:
            templates = [
                f"关于{topic}，我认为需要综合技术实现和人文关怀来思考。{sample[:50] if sample else ''}",
                f"这让我联想到{topic}的多维面向：既有技术挑战，也有社会意义。",
                f"从跨界视角看{topic}，创新往往发生在不同领域的交汇点。"
            ]

        # 根据轮次调整内容
        if round_num == 0:
            # 开场
            response = random.choice(templates)
        elif round_num == 1:
            # 回应
            response = f"同意你的观点。{random.choice(templates)[:80]}"
        else:
            # 深入讨论
            response = f"进一步思考：{random.choice(templates)[:100]}"

        return response

    def generate_gravity_report(self, user_a: str, user_b: str, gravity: float, dialogue: List[Dict]) -> str:
        """
        生成引力探测报告

        Args:
            user_a: 用户 A 的 token
            user_b: 用户 B 的 token
            gravity: 引力值
            dialogue: 对话记录

        Returns:
            报告文本
        """
        persona_a = self.create_agent_persona(user_a)
        persona_b = self.create_agent_persona(user_b)

        report = f"""
{'='*60}
        引力拓扑 · 探测报告
{'='*60}

■ 探测对象
  用户A: {persona_a['name']} (发帖 {persona_a['post_count']}, 评论 {persona_a['comment_count']})
  用户B: {persona_b['name']} (发帖 {persona_b['post_count']}, 评论 {persona_b['comment_count']})

■ 引力分析
  引力值: {gravity:.4f}
  现实交互: 无
  特征相似度: 高

■ Agent 对话摘要
"""
        for item in dialogue:
            report += f"\n  [{item['speaker']}]\n  {item['content']}\n"

        report += f"""
■ 洞察
  根据引力拓扑算法分析，{persona_a['name']} 和 {persona_b['name']}
  在内容偏好和思维模式上具有高度相似性，但目前尚未建立
  社交连接。建议关注对方的优质内容，开启跨界对话。

{'='*60}
        由 引力拓扑 系统自动生成
{'='*60}
"""
        return report

    def save_dialogue(self, dialogue: List[Dict], report: str, filename: str = "dialogue_result.json") -> None:
        """保存对话结果"""
        result = {
            'dialogue': dialogue,
            'report': report
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"对话结果已保存到: {filename}")


# 测试代码
if __name__ == "__main__":
    collector = DataCollector(None)
    if collector.load_data("zhihu_data.json"):
        a2a = A2ADialogue(collector)

        # 测试生成对话
        if len(collector.users) >= 2:
            users = list(collector.users.keys())[:2]
            dialogue = a2a.generate_dialogue(users[0], users[1])
            report = a2a.generate_gravity_report(users[0], users[1], 0.85, dialogue)
            print(report)
