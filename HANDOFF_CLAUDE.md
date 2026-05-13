# 引力拓扑 (Gravity Topology) - 项目交接文档 V2

## 1. 当前项目结构

```
gravity-topology/
├── zhihu_api.py              # 知乎 API 封装（HMAC-SHA256 签名）
├── data_collector.py         # 数据采集模块
├── similarity.py             # 基础相似度计算
├── gravity_engine.py         # 引力引擎 V1（PCA + 空间权重）
├── gravity_engine_v2.py      # 引力引擎 V2（25维特征 + 聚类 + 增强引力）
├── deepseek_a2a.py           # DeepSeek A2A 对话模块
├── a2a_dialogue.py           # 基础 A2A 对话（模板 + OpenAI）
├── app.py                    # Flask 主应用（产品体验版 V2）
├── main.py                   # 命令行入口
├── massive_data.json         # 最新采集数据（267用户，672帖子，1480评论）
├── gravity_engine_v2_results.json  # 引力计算结果（30对隐藏同好）
├── templates/index.html      # 前端 UI（完整单页应用）
├── requirements.txt          # Python 依赖
└── HANDOFF_CLAUDE.md         # 本文件
```

## 2. 核心功能

### 2.1 已完成功能

| 功能 | 状态 | 说明 |
|------|------|------|
| 知乎 API 鉴权 | 完成 | HMAC-SHA256 签名，支持所有圈子 API |
| 数据采集 | 完成 | 采集 3 个圈子数据，自动去重、HTML 清理 |
| 引力计算引擎 V2 | 完成 | 25维特征、PCA降维、空间权重矩阵、K-Means聚类 |
| 隐藏同好发现 | 完成 | 找到 415 对隐藏同好，返回 Top 30 |
| 交换人生 | 完成 | 选择用户 → 匹配对象 → 视角交换动画 → A2A对话 |
| 实时 A2A 对话 | 完成 | 调用 DeepSeek API 实时生成 Agent 对话 |
| 圆桌讨论 | 完成 | 2-4 个 Agent 围绕话题进行多轮讨论 |
| 数据仪表盘 | 完成 | 领域热度、引力分布、用户排名、网络图可视化 |
| 每日探索 | 完成 | 3D 旋转轮播选择领域，展示高质量达人 |
| 前端 UI | 完成 | 知乎风格设计，流畅动画，响应式布局 |

### 2.2 API 端点列表

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 首页（Jinja2 渲染） |
| `/api/explore/<domain_id>` | GET | 领域探索 |
| `/api/exchange/<token>` | GET | 交换人生匹配 |
| `/api/exchange_preview/<a>/<b>` | GET | 交换预览（含A2A对话） |
| `/api/hidden_pairs` | GET | 隐藏同好列表 |
| `/api/a2a_chat` | POST | 实时 A2A 对话（DeepSeek） |
| `/api/roundtable` | POST | 圆桌讨论 |
| `/api/dashboard` | GET | 数据仪表盘 |

## 3. 运行方式

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量（复制 .env.example 为 .env 并填入真实值）
cp .env.example .env
# 编辑 .env 文件，填入 DEEPSEEK_API_KEY 等

# 启动服务
python app.py
# 访问 http://localhost:8050
```

## 4. 技术栈

- **后端**: Python 3.8+, Flask, scikit-learn, numpy, pandas
- **AI**: DeepSeek API (deepseek-chat 模型)
- **前端**: HTML/CSS/JS 单页应用, Font Awesome 图标
- **数据**: 知乎社区 API (圈子详情、评论、点赞)

## 5. 数据说明

### 5.1 采集数据 (massive_data.json)

- 用户数量：267
- 帖子数量：672
- 评论数量：1480
- 活跃用户（内容>=3条）：35
- 采集时间：2026-05-13

### 5.2 引力计算结果

- 隐藏同好对：415 对（引力 > 0.3）
- Top 30 对已保存
- 用户聚类：5 个簇
- PCA 主成分：5 个（累计解释方差 79.11%）

## 6. 黑客松亮点

1. **空间计量算法**: 借鉴空间计量经济学，构建 25 维用户特征 + PCA 降维 + 空间权重矩阵
2. **交换人生**: 独特的视角交换体验，AI 模拟用户人设进行对话预演
3. **圆桌讨论**: 多 Agent 围绕话题深度碰撞，展示 AI 驱动的新型讨论形态
4. **数据可视化**: 完整的仪表盘，展示引力分布、用户聚类、领域热度
5. **端到端系统**: 从数据采集到分析到展示，完整闭环
