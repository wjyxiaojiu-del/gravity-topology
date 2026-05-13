# 引力拓扑 - 快速启动卡

## 启动命令
```bash
cd C:\Users\wangjunyi\Desktop\gravity-topology
set PYTHONIOENCODING=utf-8
python app.py
```
访问: http://localhost:8050

## 配置状态
- ✅ DeepSeek API Key: 已配置
- ✅ 知乎 OAuth APP_ID: 303
- ✅ 知乎 OAuth APP_KEY: fff438e54654409392d2e7c4a3aff673
- ✅ 知乎社区 API: kao-588

## 已完成功能
- ✅ 数据采集（267 用户，672 帖子）
- ✅ 引力引擎 V2（25 维特征，PCA 降维）
- ✅ 圆桌讨论站内搜索用户
- ✅ OAuth 关注/粉丝扩展圆桌参与者
- ✅ 实时 A2A 对话（交换人生）
- ✅ 数据仪表盘

## 杀进程（如需要）
```bash
netstat -ano | findstr :8050
taskkill /PID <PID> /F
```

## 详细文档
- [PROJECT_STATUS.md](PROJECT_STATUS.md) - 完整项目状态
- [gravity-topology-handoff.md](../gravity-topology-handoff.md) - 工作交接文档
