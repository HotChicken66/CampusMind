# CampusMind 部署指南

本文档提供 CampusMind 在不同环境下的部署建议，重点关注如何稳定连接并应对 QQ 平台的封控。

## 环境要求

- **操作系统**: Windows (推荐使用 start.bat) 或 Linux (需要手动配置 Shell)。
- **Python**: 3.10+。
- **内存**: 建议 4GB 以上（向量数据库检索及模型预加载需要一定资源）。

## 步骤 1：连接协议栈的选择 (核心)

由于 QQ 现有的风控政策，直接登录极易导致封号或无法扫码。CampusMind 采用分离式架构，通过适配器连接已有的协议栈：

### 协议栈推荐：NapCat
NapCat 是一个现代化的 OneBot V11 实现，稳定性极佳。
1. 下载并在项目根目录的 `NapCat` 文件夹中部署 NapCat。
2. 配置 NapCat 的 HTTP/WebSocket 上报地址为 `http://127.0.0.1:8080`（对应项目配置文件中的端口）。
3. 使用扫码登录。

## 步骤 2：知识库初始化

在首次启动前，建议将相关的原始文档放入 `data/` 目录。
- 文本资料放入 `data/knowledge/`。
- 图片资料放入 `data/images/`。

## 步骤 3：配置环境变量

参考项目根目录下的 `config.example.env`。关键项说明：
- `ENVIRONMENT`: 设置为 `prod`。
- `LOG_LEVEL`: 推荐在调试阶段设为 `DEBUG`，稳定后改为 `INFO`。
- `OPENROUTER_API_KEY`: 必填项，否则 Agent 将无法思考。

## 步骤 4：启动

### Windows 环境
直接运行项目根目录下的 `start.bat`。它将依次启动：
1. 协议栈服务。
2. Web 管理后台 (8080 端口)。
3. 评估系统后台 (8081 端口)。
4. NoneBot 机器人核心。

### Linux 环境
分别运行以下脚本：
```bash
python bot.py
python scripts/weekly_admin_service.py
python eval/ui_server.py
```

## ⚠️ 防封控小贴士 (Antic-Ban Tips)

1. **响应频率控制**：框架内置了模拟真人打字的延迟机制（见 `rag_worker.py`），请勿私自缩短延迟。
2. **账号权重**：尽量使用等级较高、且已在目标群聊中活跃一段时间的账号作为 Bot 账号。
3. **敏感词过滤**：在 `interceptor.py` 插件中可以自定义过滤逻辑。

---
遇到问题？请检查 `logs/` 目录下的日志输出。
