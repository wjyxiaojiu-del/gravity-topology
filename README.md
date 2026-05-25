> **中文** | [English](README_en.md)

# 引力拓扑 (Gravity Topology)

> 知乎黑客松参赛项目 — 基于空间计量与 A2A 机制的社交关系发现系统

## 项目背景

在知乎这样的社区中，大量用户在内容偏好和思维模式上高度相似，却因算法推荐的信息茧房从未相遇。**引力拓扑**通过空间计量经济学方法量化用户间的"引力"，再借助 A2A (Agent-to-Agent) 对话机制，为潜在的"隐藏同好"生成个性化的连接建议。

**核心问题：** 如何发现那些在特征空间上高度相似、但现实中没有交互的用户对？

## 技术方案

### 整体架构

```
┌──────────────────────────────────────────────────────────┐
│                   引力拓扑系统架构                          │
├──────────────────────────────────────────────────────────┤
│  数据层                                                    │
│    ├─ 知乎圈子数据采集（用户互动、发帖、评论）                 │
│    └─ 构建面板数据 (Panel Data)                             │
├──────────────────────────────────────────────────────────┤
│  计算层                                                    │
│    ├─ TF-IDF 文本向量化                                    │
│    ├─ Cosine Similarity 相似度计算                          │
│    ├─ 行为互动得分叠加                                      │
│    └─ 输出：高潜同好对列表                                   │
├──────────────────────────────────────────────────────────┤
│  交互层                                                    │
│    ├─ 用户人设实例化（基于历史内容生成 Agent Persona）        │
│    ├─ Agent-to-Agent 对话生成                              │
│    └─ 引力探测报告 → 个性化连接建议                          │
└──────────────────────────────────────────────────────────┘
```

### 核心算法：引力模型

借鉴空间计量经济学中的**引力模型**（Gravity Model），将用户间的社交吸引力量化为：

```
Gravity(A, B) = α · ContentSimilarity(A, B) + β · InteractionScore(A, B)
```

- **ContentSimilarity**: 基于 TF-IDF + Cosine Similarity 的内容相似度
- **InteractionScore**: 基于评论、点赞等行为的互动得分
- 通过加权融合，输出综合引力值

### A2A 对话机制

不同于传统的"推荐列表"，本系统通过 A2A 对话生成个性化的连接建议：

1. **人设生成**: 基于用户历史内容，用 LLM 生成 Agent Persona
2. **观点碰撞**: 两个 Agent 围绕共同兴趣话题展开对话
3. **报告输出**: 生成"引力探测报告"，呈现两个用户的共鸣点

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 演示模式（使用模拟数据）
python main.py demo

# 测试 API 连接
python main.py test

# 采集数据并分析
python main.py collect

# 使用已有数据分析
python main.py analyze
```

## 项目亮点

| 维度 | 说明 |
|------|------|
| **算法创新** | 将空间计量经济学的引力模型应用于社交网络分析 |
| **交互创新** | A2A 对话生成替代传统推荐列表，提供个性化连接建议 |
| **工程实现** | 完整的数据采集 → 计算 → 生成管线，支持增量更新 |
| **应用价值** | 帮助用户发现"隐藏同好"，打破信息茧房 |

## 技术栈

| 层级 | 技术 |
|------|------|
| 数据采集 | Python requests, 知乎 API |
| 文本向量化 | scikit-learn (TF-IDF) |
| 相似度计算 | Cosine Similarity, NumPy |
| 对话生成 | DeepSeek / OpenAI API |
| 可视化 | Pyecharts, NetworkX |

## 文件结构

```
gravity-topology/
├── zhihu_api.py          # 知乎 API 封装
├── data_collector.py     # 数据采集模块
├── similarity.py         # 相似度计算
├── a2a_dialogue.py       # A2A 对话生成
├── gravity_engine.py     # 引力计算引擎
├── deepseek_a2a.py       # DeepSeek A2A 实现
├── social_graph.py       # 社交图谱可视化
├── main.py               # 主程序入口
└── templates/            # 可视化模板
```

## 配置

```powershell
$env:ZHIHU_APP_KEY="your_app_key"
$env:ZHIHU_APP_SECRET="your_app_secret"
$env:OPENAI_API_KEY="your_api_key"
$env:OPENAI_MODEL="gpt-5.5"
```

## License

MIT
