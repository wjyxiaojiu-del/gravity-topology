# 引力拓扑 - 部署指南

## 项目定位
知乎灵感引擎与社区引力场 —— 围绕知乎内容生态的 AI 灵感引擎与引力场。

## 快速部署（Render）

### 1. 一键部署
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

或手动步骤：

1. Fork/clone 本仓库到 GitHub
2. 登录 [Render](https://render.com) 并点击 "New Web Service"
3. 选择本仓库，填写配置：
   - **Name**: `gravity-topology`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
4. 点击 Deploy

### 2. 数据文件
以下数据文件已包含在仓库中，部署后会自动在线读取：
- `massive_data.json` —— 主数据集（用户、帖子、评论、互动矩阵）
- `gravity_engine_v2_results.json` —— 隐藏同好与聚类结果
- `a2a_dialogues.json` —— 预生成的 A2A 对话

无需额外配置即可体验核心功能。

### 3. 环境变量（可选）
| 变量 | 说明 | 是否必需 |
|------|------|----------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key，用于 AI 生成灵感、圆桌总结 | 否（无 Key 时自动使用本地模板兜底） |
| `ZHIHU_OAUTH_APP_ID` | 知乎 OAuth App ID | 否 |
| `ZHIHU_OAUTH_APP_KEY` | 知乎 OAuth App Key | 否 |
| `ZHIHU_HOT_API_URL` | 外部知乎热榜接口 | 否（无接口时使用本地热点兜底） |

> **注意**：如果 `ZHIHU_OAUTH_APP_ID` 配置错误（如显示"京东互联网医院"），系统会在前端明确提示"当前 OAuth 凭证疑似未绑定本项目"，且不影响核心功能体验。

### 4. 公网 Demo 链接
部署成功后，Render 会提供一个类似 `https://gravity-topology.onrender.com` 的公网链接。

**当前项目无需 OAuth 登录即可完整体验以下核心功能：**
- 灵感引擎：从热点生成标题、提纲、观点、草稿
- 引力场：输入选题推荐讨论对象并解释原因
- 多 Agent 圆桌：结构化输出共识、分歧、文章角度、传播金句
- 生态仪表盘：数据清洗后的内容生态总览（无 Bot）

### 5. Railway 部署（备选）
1. 登录 [Railway](https://railway.app)
2. New Project → Deploy from GitHub repo
3. 添加变量 `PORT=8050`
4. Railway 会自动识别 `Procfile` 并启动服务

### 6. 本地运行
```bash
pip install -r requirements.txt
python app.py
```
访问 http://localhost:8050

### 7. 验证
```bash
python -m unittest tests.test_hot_api tests.test_dashboard_quality tests.test_a2a_dialogue tests.test_static_assets tests.test_oauth_flow -v
python -m py_compile app.py
```
