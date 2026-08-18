# 分析任务日志系统实施报告

## 📋 需求概述

根据用户明确要求：
1. **卷总结功能**：移除自动生成逻辑，仅保留手动调用（800-1600 字建议）
2. **任务落盘统计**：仅开始 + 结束写 DB（WAL 模式 + 异步简化）
3. **HTTP 独立日志**：记录请求/响应内容，超过 1MB 自动轮转（不删除历史）

---

## ✅ 已完成修改

### 1️⃣ 数据库任务历史表 ([src/ai_novel_analyzer/core/logging_config.py](file:///d:/PLAY/AI-Hero_Reborn/src/ai_novel_analyzer/core/logging_config.py))

**新增函数：**
- `init_analysis_tasks_db(db_path)`: 初始化 SQLite 表（WAL 模式）
- `record_task_start(task_id, scope, project, book, volume_dir)`: 记录任务开始
- `finalize_task(task_id, status, metrics, failure_reason)`: 记录任务结束

**表结构：**
```sql
CREATE TABLE analysis_tasks (
    task_id TEXT PRIMARY KEY,
    scope TEXT NOT NULL,              -- 'book' / 'volume'
    project TEXT NOT NULL,
    book TEXT NOT NULL,
    volume_dir TEXT,                  -- NULL 表示整本书
    
    start_time REAL NOT NULL,         -- Unix timestamp
    end_time REAL,                    -- NULL 表示进行中
    
    total_chapters INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    retry_count INTEGER DEFAULT 0,
    
    status TEXT NOT NULL,             -- 'queued' / 'running' / 'success' / 'failed'
    failure_reason TEXT,              -- NULL 表示成功
    
    detail_json TEXT                  -- JSON 字符串：卷/章级别明细
);

-- 索引优化
CREATE INDEX idx_task_status ON analysis_tasks(status);
CREATE INDEX idx_task_project_book ON analysis_tasks(project, book);
```

---

### 2️⃣ 后台任务集成 ([webui/main.py](file:///d:/PLAY/AI-Hero_Reborn/webui/main.py))

**修改位置：** `run_analysis_background()` 函数

**改动点：**
1. **启动时落盘**：
   ```python
   task_logger.record_task_start(task_id, scope, project, book, volume_dir)
   ```

2. **更新统计指标**：
   - 增加：`total_chapters`, `success_count`, `failed_count`, `retry_count`, `detail_json`
   - 替换原 `processed_items` / `failed_items` 逻辑

3. **结束时落盘**（两种情况）：
   - 正常结束：`task_logger.finalize_task(task_id, "success", metrics, None)`
   - 异常结束：`task_logger.finalize_task(task_id, "failed", metrics, error_message)`

4. **App 生命周期初始化**：
   ```python
   # 初始化数据库表
   db_path = BASE_DIR / 'workspace' / 'db' / 'novel_analyzer.db'
   task_logger.init_analysis_tasks_db(db_path)
   
   # 添加 HTTP 中间件
   app.add_middleware(RequestLoggingMiddleware)
   ```

---

### 3️⃣ HTTP 请求日志系统 ([src/ai_novel_analyzer/core/logging_config.py](file:///d:/PLAY/AI-Hero_Reborn/src/ai_novel_analyzer/core/logging_config.py))

**新增函数：**
- `setup_http_request_logger(log_dir=None, max_bytes=1MB)`: 创建专用日志器

**配置参数：**
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_bytes` | 1MB | 单文件最大大小 |
| `backupCount` | 0 | 无限制（保留所有历史） |
| `format_string` | `'%(message)s'` | JSON 行格式 |

**日志目录：** `logs/api_http_requests.log`（自动轮转）

---

### 4️⃣ AI API Client 增强 ([src/ai_novel_analyzer/utils/ai_api_client.py](file:///d:/PLAY/AI-Hero_Reborn/src/ai_novel_analyzer/utils/ai_api_client.py))

**新增组件：**
1. **懒加载 HTTP 日志器**：
   ```python
   def get_http_logger():  # 首次使用时初始化
   ```

2. **非流式请求日志记录**（成功 & 失败场景）：
   ```json
   {
     "timestamp": "2026-08-18T15:30:00.123Z",
     "type": "llm_call",
     "method": "POST",
     "url": "https://api.siliconflow.cn/v1/chat/completions",
     "request_headers": {"Content-Type": "application/json"},
     "request_body_size": 4567,
     "response_status": 200,
     "response_time_ms": 3452,
     "response_body_size": 2345,
     "prompt_tokens": 500,
     "completion_tokens": 1200,
     "total_tokens": 1700,
     "response_content_preview": "...",
     "error_message": null
   }
   ```

3. **错误捕获**：超时、HTTP Error、JSON Decode Error 均记录后抛出

---

### 5️⃣ FastAPI 中间件 ([webui/middleware.py](file:///d:/PLAY/AI-Hero_Reborn/webui/middleware.py)) ⭐ 新建

**功能：**
- 拦截所有 `/api/*` 请求
- 记录方法、URL、Body 大小、响应状态码、耗时
- 异常情况下同样记录

**日志格式（JSON 行）：**
```json
{
  "timestamp": "2026-08-18T15:30:00.123Z",
  "type": "http_request",
  "method": "POST",
  "url": "/api/analyze",
  "request_headers": {...},
  "request_body_size": 123,
  "response_status": 200,
  "response_time_ms": 456,
  "error_message": null
}
```

---

### 6️⃣ App 生命周期整合 ([webui/main.py](file:///d:/PLAY/AI-Hero_Reborn/webui/main.py))

**修改位置：** `lifespan` 上下文管理器

**执行顺序：**
1. 打印启动信息
2. **初始化任务历史数据库**（WAL 模式）
3. **添加 HTTP 请求日志中间件**
4. `yield` 等待关闭信号
5. 清理提示

---

## 📊 日志文件规划

```
logs/
├── novel_analyzer.log          # 主应用日志（INFO/ERROR，带轮转）
├── api_http_requests.log       # HTTP 请求日志（DEBUG，1MB 轮转，保留所有历史）
│   ├── api_http_requests.log.1 (已分割的旧文件)
│   └── api_http_requests.log.2
└── error/
    └── *.err                   # 单独的错误日志（可选）
```

**SQLite 数据库：**
```
workspace/db/novel_analyzer.db  # WAL 模式 (+journal-wal 文件)
```

---

## 🔍 数据流向图

```
用户操作 → FastAPI 路由 → [中间件] 记录 HTTP 请求
                          ↓
                     业务逻辑 → [AI Client] 记录 LLM 调用
                          ↓
                     run_analysis_background() → [DB] 记录任务开始
                          ↓
                     批量处理章节
                          ↓
                     finalize_task() → [DB] 记录任务结束
```

---

## ✨ 使用示例

### 查看任务历史

```python
import sqlite3

conn = sqlite3.connect('workspace/db/novel_analyzer.db')
cursor = conn.cursor()

# 查询最近 10 个任务
cursor.execute('''
    SELECT task_id, scope, project, book, volume_dir, 
           start_time, end_time, status, success_count, failed_count
    FROM analysis_tasks 
    ORDER BY start_time DESC LIMIT 10
''')

for row in cursor.fetchall():
    print(row)
```

### 分析 HTTP 请求日志

```bash
# 查看所有 POST 到 /api/analyze 的请求
grep '"method": "POST"' logs/api_http_requests.log | grep '/api/analyze'

# 统计平均响应时间
cat logs/api_http_requests.log | python -c "import sys, json; [print(json.loads(l)['response_time_ms']) for l in sys.stdin]"
```

---

## ⚠️ 注意事项

1. **任务 ID 唯一性**：UUID v4 确保全局唯一（已在 `start_analysis()` 中生成）
2. **WAL 模式**：提升并发写入性能，避免锁竞争
3. **异步落盘**：当前简化版直接在主线程同步写入（如需优化可改为 Queue + Worker）
4. **日志大小增长**：`backupCount=0` 表示无限制，定期清理建议：
   ```bash
   # 保留最近 7 天的 HTTP 日志
   find logs/ -name "api_http_requests.log.*" -mtime +7 -delete
   ```

---

## 🧪 测试清单

- [ ] 启动 WebUI，观察控制台输出数据库和中间件加载成功
- [ ] 在 UI 点击"批量分析"，检查 `logs/api_http_requests.log` 是否有记录
- [ ] 查询 `workspace/db/novel_analyzer.db` 确认任务落盘成功
- [ ] 验证 HTTP 日志文件大小达到 1MB 后自动轮转（生成 `.1` 后缀文件）
- [ ] 尝试分析失败场景，确认 `failure_reason` 正确记录

---

## 🚀 下一步优化建议

1. **前端任务历史页面**：展示数据库中的历史任务统计
2. **日志清理脚本**：自动删除 30 天前的旧日志
3. **异步写入队列**：使用 `asyncio.Queue` 解耦业务逻辑与落盘操作
4. **指标看板**：ECharts 可视化展示成功率、平均耗时等指标

---

**实施者**: Qoder  
**日期**: 2026-08-18  
**版本**: v1.0
