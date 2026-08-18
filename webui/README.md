# AI Novel Analyzer Web UI

基于 FastAPI + Alpine.js 的轻量级小说拆书工作�?

## 🚀 快速启�?

### Windows
```bash
webui/run_webui.bat
```

或使用命令：
```bash
uv run python webui/main.py
```

访问：http://127.0.0.1:18997

## 📦 技术栈

- **后端**: FastAPI (异步原生 + SSE)
- **前端**: Alpine.js (CDN) + Tailwind CSS
- **模板**: Jinja2
- **数据�?*: JSON/SQLite (零数据库依赖)

## �?功能模块

### 1️⃣ 总览仪表�?
- 📊 章节分析进度统计
- 🏗�?项目目录结构�?
- 📈 维度数据可视化图�?
- �?最近任务记�?

### 2️⃣ 拆书工坊
- 📤 上传 TXT 文件
- 🔍 自动识别编码和章节分割点
- 👁�?预览章节内容（前 50 字）
- �?确认拆分并写�?processed 目录

### 3️⃣ 分析任务中心
- ▶️ 一键启动批量分�?
- 📡 SSE 实时日志推�?
- 📊 分卷进度网格视图
- 🔄 失败章节重试机制

### 4️⃣ 维度库浏�?
- 🗃�?6 大维度（角色/地点/物品/事件/技�?世界观）
- 🔎 全文搜索过滤
- 🏷�?二级标签筛选（角色类型、状态等�?
- 📋 详细条目信息展示

### 5️⃣ 系统设置
- 🔑 API Key 管理（OpenAI/Anthropic/Google�?
- 🏥 系统健康诊断
- 📋 操作日志记录

## 🛠�?目录结构

```
webui/
├── main.py                  # FastAPI 主程�?
├── api_splitter.py          # 轻量级拆书工�?
├── frontend/               # 前端静态资�?
�?  ├── templates/         # Jinja2 模板
�?  �?  ├── base.html      # 基础布局
�?  �?  ├── dashboard.html # 总览�?
�?  �?  ├── splitting.html # 拆书工坊
�?  �?  ├── analysis.html  # 分析任务中心
�?  �?  ├── dimensions.html # 维度库浏�?
�?  �?  └── settings.html  # 系统设置
�?  └── static/           # 静态文�?
�?      ├── css/
�?      └── js/
└── run_webui.bat         # Windows 启动脚本
```

## 📝 API 接口概览

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/upload` | POST | 上传 TXT 文件 �?预览拆分结果 |
| `/api/split/{file_id}` | POST | 确认拆分并写�?|
| `/api/analyze` | POST | 启动批量分析任务 |
| `/api/tasks/{task_id}/log` | GET | SSE 日志�?|
| `/api/stats` | GET | 获取统计数据 |
| `/api/dimensions/{type}` | GET | 获取维度库数�?|
| `/api/config/api-keys` | GET/POST | API Key 配置 |

## 🔧 开发建�?

### V1 阶段（当前实现）
�?已完成五核心页面  
�?支持上传 - 预览 - 拆分流程  
⚠️ 批量分析任务需改�?batch_processor 以支持回�? 

### V1.5-V2.0 演进路线
- 引入轻量状态管理（可�?Pinia 替代品）
- 添加虚拟滚动优化大数据列表性能
- 完善 SSE 断线重连机制
- 集成 vis.js 绘制人物关系图谱
- 支持 PostgreSQL �?MongoDB 存储方案

## 🐛 注意事项

1. **本地使用**：默�?`localhost:8000`，不对外暴露
2. **API Key 安全**：Key 仅存储在本地 config.yaml，永不上�?
3. **长任务处�?*：批量分析可能耗时数十分钟，界面可正常使用

## 💡 下一步改�?

- [ ] 添加 WebSocket 替代 SSE 以实现双向通信
- [ ] 引入缓存机制减少重复查询
- [ ] 导出功能（JSON/CSV/PDF�?
- [ ] 支持多本小说同时管理
- [ ] 集成 ChromaDB 进行语义搜索

---

**启动方式**：双�?`run_webui.bat` 或使�?`uv run python webui/main.py`  
**访问地址**：http://127.0.0.1:18997
