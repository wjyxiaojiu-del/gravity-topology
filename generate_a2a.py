"""
用 DeepSeek 为交换人生生成 A2A 对话
生成多组对话样本，保存到 JSON 供前端使用
"""

import json
import os
import random
import time
from dotenv import load_dotenv
from openai import OpenAI
from gravity_topology.config import DOMAINS, TOPICS as SHARED_TOPICS
from gravity_topology.utils import analyze_user_style, build_persona_prompt as build_persona_prompt_shared

load_dotenv()

# 加载数据
with open('massive_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

with open('gravity_engine_v2_results.json', 'r', encoding='utf-8') as f:
    gravity_results = json.load(f)

users = data.get('users', {})
hidden_pairs = gravity_results.get('hidden_pairs', [])

# DeepSeek 客户端
api_key = os.getenv("DEEPSEEK_API_KEY", "")
if not api_key:
    raise RuntimeError("请设置 DEEPSEEK_API_KEY 环境变量")
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


def get_user_style(token):
    """分析用户风格（委托给共享模块）"""
    user = users.get(token, {})
    contents = user.get('contents', [])
    style = analyze_user_style(contents)
    style['name'] = user.get('name', token)
    style['post_count'] = user.get('post_count', 0)
    style['comment_count'] = user.get('comment_count', 0)
    return style


def build_persona_prompt(token):
    """构建用户人设提示词（委托给共享模块）"""
    user = users.get(token, {})
    style = get_user_style(token)
    return build_persona_prompt_shared(
        user.get('name', token), user, style, user.get('contents', []),
    )


def generate_dialogue(token_a, token_b, topic, rounds=4):
    """生成两人对话"""
    name_a = users.get(token_a, {}).get('name', token_a)
    name_b = users.get(token_b, {}).get('name', token_b)

    persona_a = build_persona_prompt(token_a)
    persona_b = build_persona_prompt(token_b)

    dialogue = []
    history_a = []
    history_b = []

    for r in range(rounds):
        if r % 2 == 0:
            # A 发言
            messages = [{"role": "system", "content": persona_a}]
            if r == 0:
                messages.append({"role": "user", "content": f"话题：{topic}\n\n请发表你的看法，这是开场。"})
            else:
                for h in history_b[-2:]:
                    messages.append({"role": "user", "content": h})
                for h in history_a[-2:]:
                    messages.append({"role": "assistant", "content": h})
                messages.append({"role": "user", "content": f"继续讨论：{topic}\n回应对方并表达你的观点。"})

            try:
                resp = client.chat.completions.create(
                    model="deepseek-chat", messages=messages,
                    max_tokens=250, temperature=0.85
                )
                content = resp.choices[0].message.content
            except Exception as e:
                content = f"[生成失败: {e}]"

            history_a.append(content)
            dialogue.append({'round': r+1, 'speaker': name_a, 'speaker_token': token_a, 'content': content})

        else:
            # B 发言
            messages = [{"role": "system", "content": persona_b}]
            for h in history_a[-2:]:
                messages.append({"role": "user", "content": h})
            for h in history_b[-2:]:
                messages.append({"role": "assistant", "content": h})
            messages.append({"role": "user", "content": f"继续讨论：{topic}\n回应对方并表达你的观点。"})

            try:
                resp = client.chat.completions.create(
                    model="deepseek-chat", messages=messages,
                    max_tokens=250, temperature=0.85
                )
                content = resp.choices[0].message.content
            except Exception as e:
                content = f"[生成失败: {e}]"

            history_b.append(content)
            dialogue.append({'round': r+1, 'speaker': name_b, 'speaker_token': token_b, 'content': content})

        print(f"  [{dialogue[-1]['speaker']}]: {content[:60]}...")
        time.sleep(0.5)

    return dialogue


def generate_interest_analysis(token_a, token_b):
    """用 DeepSeek 分析两人的兴趣碰撞点"""
    style_a = get_user_style(token_a)
    style_b = get_user_style(token_b)
    name_a = style_a['name']
    name_b = style_b['name']

    samples_a = '、'.join(style_a['samples'][:3])
    samples_b = '、'.join(style_b['samples'][:3])

    prompt = f"""分析以下两位知乎用户的兴趣碰撞点：

用户A「{name_a}」（{style_a['traits']}）：
近期内容：{samples_a}

用户B「{name_b}」（{style_b['traits']}）：
近期内容：{samples_b}

请用 JSON 格式返回：
{{
  "overlap": ["共同关注点1", "共同关注点2"],
  "divergence_a": ["A独有但B可能感兴趣的方向1"],
  "divergence_b": ["B独有但A可能感兴趣的方向1"],
  "spark": "一句话描述他们相遇会产生什么火花"
}}"""

    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是兴趣分析专家，擅长发现人与人之间的思想共鸣点。只返回JSON。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300, temperature=0.7
        )
        text = resp.choices[0].message.content
        # 尝试解析 JSON
        if '{' in text:
            json_str = text[text.index('{'):text.rindex('}')+1]
            return json.loads(json_str)
    except Exception as e:
        print(f"  分析失败: {e}")

    return {
        'overlap': ['技术讨论', '社区互动'],
        'divergence_a': ['更多技术细节'],
        'divergence_b': ['更多人文思考'],
        'spark': '技术与人文的碰撞，会产生新的视角'
    }


def generate_walking_shoes(token_a, token_b):
    """生成「假如你是TA」体验内容"""
    style_a = get_user_style(token_a)
    style_b = get_user_style(token_b)
    name_a = style_a['name']
    name_b = style_b['name']

    prompt = f"""你是一个创意写作专家。请为以下场景生成一段体验描述：

用户「{name_a}」想体验「{name_b}」的视角。

{name_a}的特征：{style_a['traits']}，发帖{style_a['post_count']}条
{name_b}的特征：{style_b['traits']}，发帖{style_b['post_count']}条

请生成一段 100-150 字的「假如你是TA」体验描述，用第二人称（你），让{name_a}感受到{name_b}看世界的方式。要有画面感和情感共鸣。"""

    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是创意写作专家，善于用文字创造沉浸式体验。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=250, temperature=0.9
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"生成失败: {e}"


def main():
    """为前10对生成完整的A2A体验"""
    print("=" * 60)
    print("  引力拓扑 · A2A 对话生成系统")
    print("=" * 60)

    topics = SHARED_TOPICS

    results = []
    pairs_to_process = hidden_pairs[:10]

    for i, pair in enumerate(pairs_to_process):
        token_a = pair['user_a']
        token_b = pair['user_b']
        name_a = pair['user_a_name']
        name_b = pair['user_b_name']
        gravity = pair['gravity']

        print(f"\n[{i+1}/{len(pairs_to_process)}] {name_a} <-> {name_b} (引力: {gravity:.2f})")

        topic = random.choice(topics)
        print(f"  话题: {topic}")

        # 1. 生成对话
        print(f"  生成 A2A 对话...")
        dialogue = generate_dialogue(token_a, token_b, topic, rounds=4)

        # 2. 分析兴趣碰撞
        print(f"  分析兴趣碰撞...")
        collision = generate_interest_analysis(token_a, token_b)

        # 3. 生成「假如你是TA」
        print(f"  生成假如你是TA...")
        walking_a = generate_walking_shoes(token_a, token_b)
        walking_b = generate_walking_shoes(token_b, token_a)

        result = {
            'pair': {
                'user_a': token_a,
                'user_a_name': name_a,
                'user_b': token_b,
                'user_b_name': name_b,
                'gravity': gravity,
                'reasons': pair.get('match_reasons', []),
            },
            'topic': topic,
            'dialogue': dialogue,
            'collision': collision,
            'walking_shoes': {
                'a_sees_b': walking_a,
                'b_sees_a': walking_b,
            }
        }
        results.append(result)

        print(f"  完成！")

    # 保存
    with open('a2a_dialogues.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n已生成 {len(results)} 组 A2A 体验，保存到 a2a_dialogues.json")


if __name__ == '__main__':
    main()
