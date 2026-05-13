# 引力拓扑 (Gravity Topology) - 项目状态文档

**更新时间**: 2026-05-13
**项目路径**: `C:\Users\wangjunyi\Desktop\gravity-topology\`

---

## 一、项目概述

引力拓扑是一个基于知乎社区数据的社交分析工具，通过空间计量算法计算用户之间的"引力值"，发现隐藏的同好关系，并提供 A2A 对话、圆桌讨论等功能。

---

## 二、环境配置

### 2.1 启动命令

```bash
cd C:\Users\wangjunyi\Desktop\gravity-topology
set PYTHONIOENCODING=utf-8
python app.py
```

访问地址: http://localhost:8050

### 2.2 环境变量 (.env)

```env
# DeepSeek API Key (A2A 对话必需)
DEEPSEEK_API_KEY=sk-4f335606c6a9425a97f018e556840aa8

# 知乎 OAuth (用户登录、关注/粉丝功能)
ZHIHU_OAUTH_APP_ID=303
ZHIHU_OAUTH_APP_KEY=fff438e54654409392d2e7c4a3aff673
ZHIHU_OAUTH_REDIRECT_URI=http://localhost:8050/callback

# 知乎社区 API (数据采集、发帖、评论)
ZHIHU_COMMUNITY_APP_KEY=kao-588
ZHIHU_COMMUNITY_APP_SECRET=Wyz3iQ6VQNNjzpPXC0Q1VfgJwb5dONLO
```

---

## 三、数据规模

| 数据项 | 数量 |
|--------|------|
| 采集用户 | 267 个 |
| 去重后真实用户 | 230 个（过滤 15 个 bot，25 对重名）|
| 帖子 | 672 条 |
| 评论 | 1480 条 |
| 活跃用户（内容>=3条）| 35 个 |
| 隐藏同好对（引力>0.3）| 415 对 |

---

## 四、已完成功能

### 4.1 核心功能

| 功能 | 状态 | 说明 |
|------|------|------|
| 数据采集 | ✅ 完成 | 3 个圈子：OpenClaw 人类观察员、A2A for Reconnect、黑客松脑洞补给站 |
| 引力引擎 V2 | ✅ 完成 | 25 维特征矩阵，PCA 降维到 5 个主成分（79.11% 方差）|
| 用户聚类 | ✅ 完成 | 5 个用户聚类 |
| Bot/去重过滤 | ✅ 完成 | `_real_user_tokens` 集合全局过滤 |

### 4.2 页面功能

| 页面 | 功能 | 状态 |
|------|------|------|
| 首页 | 4 个功能卡片入口 | ✅ |
| 引力场 | 交换人生体验 | ✅ |
| 多 Agent 圆桌 | 圆桌讨论/辩论 | ✅ |
| 生态仪表盘 | 数据可视化 | ✅ |
| 为你推荐 | 兴趣标签推荐 | ✅ |
| 灵感引擎 | 创作素材生成 | ✅ |

### 4.3 高优先级功能（已全部完成）

| 功能 | 状态 | 说明 |
|------|------|------|
| A. 圆桌讨论站内搜索用户 | ✅ 完成 | `/api/search_users` 接口，前端实时搜索过滤 |
| B. OAuth 关注列表扩展 | ✅ 完成 | 登录后可将关注/粉丝加入圆桌讨论 |
| C. 实时 A2A 对话 | ✅ 完成 | 交换人生页面实时调用 DeepSeek 生成对话 |

---

## 五、API 端点

### 5.1 核心 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/search_users?q=关键词` | GET | 搜索已采集用户 |
| `/api/a2a_chat` | POST | 实时 A2A 对话 |
| `/api/roundtable` | POST | 圆桌讨论 |
| `/api/dashboard` | GET | 数据仪表盘 |
| `/api/exchange/{token}` | GET | 交换人生数据 |
| `/api/exchange_preview/{a}/{b}` | GET | 交换预览 |

### 5.2 OAuth API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/login` | GET | 知乎 OAuth 登录跳转 |
| `/callback` | GET | OAuth 回调处理 |
| `/api/me` | GET | 获取当前登录用户信息 |
| `/api/oauth_status` | GET | OAuth 配置状态 |
| `/logout` | GET | 退出登录 |
| `/api/my_followers` | GET | 获取粉丝列表 |
| `/api/my_followed` | GET | 获取关注列表 |

### 5.3 知乎社区 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/publish_pin` | POST | 发布想法到圈子 |
| `/api/comment` | POST | 创建评论 |
| `/api/like` | POST | 点赞/取消点赞 |

---

## 六、前端页面结构

### 6.1 导航栏

- 首页 | 为你推荐 | 灵感引擎 | 引力场 | 多 Agent 圆桌 | 生态仪表盘
- 右侧：知乎登录按钮 + 用户头像/退出

### 6.2 圆桌讨论页面

- 话题选择（预设 + 自定义输入）
- 参与者选择（2-4人）：
  - 搜索框：实时搜索已采集的 267 个用户
  - OAuth tabs：登录后显示「我的关注」「我的粉丝」
  - 默认列表：活跃用户（内容>=10条）
- 圆桌动画覆盖层：圆形桌面 + 环形轨道 + 参与者落座
- 讨论结果展示（聊天气泡样式）

### 6.3 数据仪表盘

- 概览卡片（用户数、帖子数、评论数、隐藏同好对数）
- 领域内容热度柱状图
- 隐藏同好引力分布图
- Top 10 活跃用户排行榜
- 隐藏同好引力网络图（SVG 圆形布局）

---

## 七、核心文件说明

| 文件 | 说明 | 状态 |
|------|------|------|
| `app.py` | Flask 主应用，所有 API 端点 | ✅ 完整 |
| `templates/index.html` | 前端单页应用（含 CSS + JS）| ✅ 完整 |
| `zhihu_api.py` | 知乎 API 封装（HMAC-SHA256 签名）| ✅ 无需修改 |
| `data_collector.py` | 数据采集模块 | ✅ 无需修改 |
| `gravity_engine_v2.py` | 引力引擎 V2 | ✅ 无需修改 |
| `deepseek_a2a.py` | DeepSeek A2A 对话模块 | ✅ 无需修改 |
| `massive_data.json` | 采集数据（267 用户，672 帖子）| ✅ 已有 |
| `gravity_engine_v2_results.json` | 引力计算结果（30 对隐藏同好）| ✅ 已有 |
| `.env` | 环境变量配置 | ✅ 已配置 |

---

## 八、已知问题

1. **端口 8050 缓存**: Windows 上重启时可能需要手动杀进程
   ```bash
   netstat -ano | findstr :8050
   taskkill /PID <PID> /F
   ```

2. **中文编码**: Windows 终端输出中文会乱码，需要 `set PYTHONIOENCODING=utf-8`

3. **A2A 对话较慢**: DeepSeek API 每轮对话约 3-5 秒，圆桌讨论（3人×3轮）约 30-50 秒

4. **OAuth 需要登录**: 未登录时点击登录会跳转到知乎授权页面

---

## 九、待优化功能（低优先级）

| 功能 | 说明 | 工程量 |
|------|------|--------|
| 圆桌辩论模式 | 两个 Agent 持对立观点辩论 | 1-2 小时 |
| 数据仪表盘交互增强 | 网络图节点点击查看详情 | 2-3 小时 |
| 发布想法到圈子 | Agent 自动发布引力探测报告 | 1 小时 |
| 前端打包优化 | 拆分 CSS/JS，用 vite 打包 | 2-3 小时 |
| 部署到服务器 | 阿里云 ECS 47.114.72.251 | 2-4 小时 |

---

## 十、测试清单

### 10.1 基本功能测试

- [ ] 访问 http://localhost:8050 能正常加载首页
- [ ] 点击「知乎登录」能跳转到授权页面
- [ ] OAuth 登录后能获取用户信息
- [ ] 搜索框能搜索用户（输入中文名测试）
- [ ] 圆桌讨论能正常进行
- [ ] 交换人生能正常体验
- [ ] 数据仪表盘能正常加载

### 10.2 OAuth 功能测试

- [ ] 登录后显示「我的关注」「我的粉丝」tabs
- [ ] 能将关注/粉丝加入圆桌讨论
- [ ] 退出登录后 tabs 隐藏

---

## 十一、答辩重点展示

1. **空间计量算法**: 25 维特征矩阵 + PCA 降维 + 用户聚类
2. **交换人生**: 以他人视角浏览知乎 + 实时 A2A 对话
3. **圆桌讨论**: 多 Agent 多轮讨论 + 搜索用户 + OAuth 扩展
4. **数据仪表盘**: 领域热度 + 引力分布 + 网络图可视化

---

## 十二、快速启动 Checklist

1. ✅ 确认 `.env` 文件存在且配置正确
2. ✅ 运行 `set PYTHONIOENCODING=utf-8`
3. ✅ 运行 `python app.py`
4. ✅ 访问 http://localhost:8050
5. ✅ 测试搜索功能
6. ✅ 测试 OAuth 登录
7. ✅ 测试圆桌讨论
8. ✅ 测试交换人生

---

**文档维护**: 如有更新，请同步修改此文档
