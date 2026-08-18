# AI 小说拆书工作台 —— 轻量 Web UI 设计方案

## 1. 设计目标与原则

| 目标 | 说明 |
|------|------|
| **包装而非重写** | Web 层只是现有三步 CLI 流水线（拆书 → 分析 → 查询）的操作面，核心逻辑零改动或仅轻量重构 |
| **真正轻量** | 无 Node 构建链、无 Docker、无数据库强依赖，`uv run main.py` 一条命令启动，浏览器即用 |
| **长任务友好** | 批量分析动辄几十分钟，界面必须实时反馈进度，且允许用户切到其他页面不中断任务 |
| **单机本地优先** | 面向作者本人本机使用（localhost），不考虑多用户权限体系 |

---

## 2. 市面拆书软件借鉴点（竞品分析）

参考 FeelFish 智能拆书、笔灵 AI 等工具的设计模式：

| 市面工具共性 | 本项目采纳方式 |
|-------------|---------------|
| **上传整本 TXT → 自动识别章节拆分** | 对应 `split_book.py`，保留编码探测 / 兜底切分能力 |
| **拆分后章节列表人工校验**（FeelFish 明确提示"可能匹配出错，需手动检查删除"） | 拆书分**预览 → 确认写入**两步，预览表格直接展示分割结果，发现异常再调整参数重预 |
| **分批提取、自定义提示词、先试跑几章再全量**（控制成本） | 分析页提供"**仅处理前 N 章**"的试跑选项 + 失败章节一键重试 |
| 章节内容 + 提取结果对照浏览 | 维度浏览页：左原文、右六维结构化卡片 |
| Token/积分消耗透明可见 | batch_processor 已输出每章 token/耗时，界面化为统计卡片 |

---

## 3. 信息架构（5 个模块）

采用"左侧窄导航 + 右侧内容区"布局，聚焦核心三步流水线：

```
┌──────────┬─────────────────────────────────────────┐
│ 📖 拆书  │  内容区（动态切换）                        │
│ 工作台   │                                         │
│──────────│                                         │
│ ① 总览   │                                         │
│ ② 拆书   │                                         │
│ ③ 分析   │                                         │
│ ④ 维度库 │                                         │
│ ⑤ 设置   │                                         │
│──────────│                                         │
│[悬浮任务条: ●●● 分析中 第 37/73 章 45%]                     │
└──────────┴─────────────────────────────────────────┘
```

| 模块 | 对应 CLI/能力 | V1 优先级 | 数据源 |
|------|--------------|---------|-------|
| ① 总览 Dashboard | `check_progress.py` | ⭐⭐⭐⭐⭐ | JSON 元数据 |
| ② 拆书工坊 | `split_book.py` | ⭐⭐⭐⭐ | ChapterSplitter |
| ③ 分析任务中心 | `batch_processor.py` | ⭐⭐⭐⭐⭐ | AutomatedBatchProcessor |
| ④ 维度库浏览 | 章节 JSON | ⭐⭐ (V2) | chap_XXXX.json |
| ⑤ 设置 | 配置管理 | ⭐⭐ | `.env`, `production.yaml` |

---

## 4. 各页面详细设计

### 4.1 总览 Dashboard

- **三级树形结构**：项目 → 书籍 → 卷（数据扫描自 `workspace/projects/*/project_meta.json` → `book_meta.json` → `volume_meta.json`）
- **卷卡片**：章节进度环（processed/pending/failed 三色分布）、显示"待处理 N / 失败 M"
- **失败数 > 0** 时卡片显示醒目「重试失败章节」按钮 → 跳转分析页并预填该卷
- **顶部统计条**：总章节数、总成功率、累计 Token 消耗（扫描章节 JSON 汇总）

### 4.2 拆书工坊（两步向导）

#### Step 1 — 上传与参数

- **拖拽 / 选择 TXT 文件**（大文件有长度提示）
- **必填表单**：项目名（下拉选已有或新建）、书名、作者（默认"佚名"）
- **高级折叠区**：维度预设（xianxia/urban/scifi/fantasy）、卷名/卷号、兜底切分粒度

#### Step 2 — 分割预览（不写盘）

- 调用 `ChapterSplitter.split_file()` 返回预览（等价 CLI `--preview`）
- **表格展示**：卷名 / 章节号 / 标题 / 字数
- **字数分布柱状图**：直观发现异常短/长章节
- **分割模式提示**："标题识别"或"兜底切分"，附总计 N 章 M 字
- **冲突检测**：若目标卷目录已存在 → 红色警告 + 覆盖开关（对应 `--overwrite`）
- **操作按钮**：「取消」→ 回 Step1；「确认拆书」→ 写盘 → 成功引导至分析页

### 4.3 分析任务中心（核心页面）

#### 左侧：任务配置面板

- **卷选择器**：从总览树中选（级联可选）
- **参数滑块**：并发 workers（1-8）、开关「失败继续」「向量库写入」
- **试跑模式**：输入框「仅处理前 N 章」（默认为空即全量）
- **启动按钮**：点击创建后台任务，按钮变禁用状态防重复提交

#### 右侧：运行监控区

- **总进度条**：百分比数字 + 章节进度（当前/总数）
- **状态徽标**：等待中（灰）、运行中（蓝）、已完成（绿）、部分失败（橙红）
- **实时日志流**：自动滚动，解析 batch_processor 日志行渲染为彩色消息（✅成功 / ❌失败 / ⏭跳过）
- **章节网格**：每章色块（灰=pending、蓝=processing、绿=processed、红=failed），hover 显示耗时和 token
- **统计卡片**：成功 / 失败 / 跳过 / 成功率 / 耗时（秒）/Token 总计
- **失败列表**：结束页面展示，带错误原因和「重试失败章节」快捷按钮

#### 悬浮任务条

- **常驻顶部**：任务创建后即出现，显示「●●● 分析中 第 37/73 章 45%」
- **跨页不停止**：切换其他标签页任务仍在后台运行
- **停止按钮**：悬停显示，点击停止未开始的任务（正在处理中的章节不会中断）

### 4.4 维度库浏览（V1/V2 分阶段）

**V1（基础版）**：直接读章节 JSON 文件
- **筛选栏**：书 → 卷 → 章节 级联选择
- **六维标签页**：人物 / 地点 / 物品 / 世界事件 / 场景 / 成长 + 剧情秘密
- **双栏布局**：左章节原文滚动｜右结构化卡片列表
- **卡片字段**：展示每个条目 key（name/type/title）+ 简要摘要（如人物出场次数、地点关联事件数）
- **点击联动**：点击某个人物，过滤出所有章节中此人出现的记录

**V2（增强版，未来）**：接 UnifiedQueryAPI
- SQLite EAV 检索：按 name/type 精确/模糊查询
- ChromaDB 语义搜索：输入关键词找相似人物/地点
- 关系图谱（可选）：可视化人物 - 角色关系网

### 4.5 设置

- **API Key 状态检测**：读取 `.env`，只显示"已配置/缺失"+最后 4 位（不回显完整密钥）
- **AI 模型配置**：Base URL、模型名称、Embedding 模型（写 `production.yaml`）
- **维度预设切换**：映射 `dimension_switcher.py` 功能
- **路径显示**：workspace 根、数据库位置（只读）

---

## 5. 技术选型详解

| 层 | 推荐方案 | 理由 |
|----|---------|------|
| **后端框架** | **FastAPI + uvicorn** | 异步原生、SSE 开箱即用、Pydantic 模型复用、自带 `/docs` API 文档；路线图 Phase 2 本就规划 FastAPI |
| **前端形态** | **无构建单页**：HTML + Alpine.js(CDN) + Tailwind(CDN) | 零 Node 依赖，一个 static/目录搞定；Alpine 足够覆盖表单/标签页/轮询需求 |
| **实时通道** | **SSE（Server-Sent Events）** | 比 WebSocket 轻，单向推送进度/日志正合适 |
| **任务执行** | 进程内线程池 + **TaskRegistry**（内存任务注册表） | 直接 import 现有类，比 subprocess 更易传参和推送进度 |
| **数据读取** | **直接读 JSON** | 文件系统即数据库，与项目"目录结构就是状态"哲学一致，零迁移 |

**对比排除**：Streamlit（布局僵化，长任务交互弱）/ Flask（同步模型 SSE 别扭）/ Vue 构建链（违背轻量目标）。

---

## 6. 后端 API 概览

```yaml
# ===== 项目管理 =====
GET    /api/projects                       # 项目→书→卷树（含进度统计）

# ===== 拆书工坊 =====
POST   /api/split/preview                  # 上传 TXT + 参数 → 分割预览对象（不写盘）
POST   /api/split/commit                   # 确认写盘：{project, book, volume_title, overwrite}

# ===== 分析任务中心 =====
GET    /api/volumes/{vol}/chapters         # 章节列表 + 状态 + 字数
POST   /api/analyze                        # {volume_dir, workers, continue_on_failure, max_chapters} → task_id
GET    /api/tasks/{id}                     # 任务快照（status, progress, stats）
GET    /api/tasks/{id}/events              # SSE：章节完成/日志/统计事件流
POST   /api/tasks/{id}/stop                # 停止任务（取消未开始章节）

# ===== 维度库浏览 =====
GET    /api/chapters/{vol}/{num}           # 原文 + 六维结构化数据
# V2: GET /api/search?keyword=&type=characters&limit=10

# ===== 设置 =====
GET    /api/settings                       # 读取当前配置（脱敏）
PUT    /api/settings                       # 更新配置
```

---

## 7. 现有代码适配清单

| 位置 | 现状 | V1 适配改造 |
|------|------|------------|
| `batch_processor.py` | `_create_ai_client` 失败时 `sys.exit(1)`；仅打印日志 | 改为抛异常；增加**回调钩子队列**，每章完成后 push 事件；CLI 运行时为空则行为不变 |
| `AutomatedBatchProcessor` | ThreadPoolExecutor 内部创建 | 增加外部 `cancel_event`支持（供 stop 接口）；增加 `only_first_n` 参数（试跑模式） |
| `split_book.py` | `main()` 内联逻辑，预览走 print | 抽出 `run_split(...) -> SplitPreview` 函数供 API 复用，CLI `main()` 保持不变 |
| `check_progress.py` | 打印文本报告 | 抽出 `scan_progress(dir) -> dict` 供 Dashboard 复用 |
| `UnifiedQueryAPI` | 尚未完全实现检索 | V2 完善 SQL 查询与向量搜索封装 |

---

## 8. 前端交互细节

### 8.1 状态管理

- **全局 Store**（Alpine 组件）：
  - `projectsTree`: 项目树数据（懒加载）
  - `currentVolume`: 当前选中卷
  - `currentTasks`: 活跃任务 ID 列表（最多显示 3 个）
  - `logs`: 最近 100 条日志（循环缓冲区）

### 8.2 SSE 连接管理

```javascript
// 任务事件流订阅示例
const eventSource = new EventSource(`/api/tasks/${taskId}/events`);
eventSource.onmessage = (e) => {
  const data = JSON.parse(e.data);
  if (data.type === 'chapter_complete') updateProgress(data.chap);
  if (data.type === 'log') appendLog(data.message);
  if (data.type === 'stats') updateStats(data.stats);
};
// 页面切换时关闭，恢复时重建
```

### 8.3 错误处理策略

| 错误类型 | 表现 | 用户动作 |
|---------|------|---------|
| API 400（参数错） | 顶部 Alert 提示 | 修正参数后重试 |
| API 500（服务错） | 日志流红色报错 + 任务状态 "服务器错误" | 刷新页重试或联系开发者 |
| 断网 | 底部 Toast "无法连接服务器" | 恢复后自动重连 |

---

## 9. 分阶段实施计划

| 里程碑 | 目标 | 预估工时（人日） | 交付物 |
|--------|------|----------------|--------|
| **M1 骨架** | FastAPI 服务 + 导航 + 总览页（JSON 扫描） | 2 | 可启动浏览工作区的项目树 |
| **M2 拆书** | 上传 → 预览 → 确认写盘 | 3 | 拆书脱离命令行，预览无误后一键执行 |
| **M3 分析** | 任务中心 + SSE 实时进度 + 停止 | 5 | 核心价值闭环（最耗时模块） |
| **M4 维度库** | 六维浏览 + 原文对照（V1 直读 JSON） | 2 | 结果可读可查 |
| **M5 设置** | Key 检测、模型/预设配置 | 1 | 告别手改 YAML |
| **合计** | 全流程跑通 | ~13 | 可投入使用的轻量 Web UI |

---

## 10. 风险与规避

| 风险 | 影响 | 应对 |
|------|------|------|
| `batch_processor` 大量 sys.exit() | 无法嵌入进程 | 重构为 return/raise；CLI 入口保留退出码 |
| SSE 在 Windows IIS/Apache 下兼容问题 | 实时推送失败 | 默认 uvicorn 开发服务器，非生产部署无需代理 |
| 多线程写 volume_meta.json 竞态 | 数据损坏 | 批末统一回写（现有逻辑）已规避 |
| 大文件上传超时 | 拆书失败 | 限制 V1 最大体积（如 50MB），超大文件建议用命令行 |
| Vue/React 上手成本 | 维护负担 | 坚持无构建 HTML，降低学习曲线 |

---

## 11. 待办事项（设计确认后）

- [ ] 创建 `main.py`（FastAPI 入口）
- [ ] 创建 `static/js/app.js`（前端逻辑）
- [ ] 创建 `templates/index.html`（单页模板）
- [ ] 创建 `backend/api.py`（路由定义）
- [ ] 创建 `backend/tasks.py`（任务调度器）
- [ ] 修改 `batch_processor.py` 增加回调钩子
- [ ] 修改 `split_book.py` 抽出 preview 函数
- [ ] 编写单元测试（API 接口、任务调度）

---

## 附录 A：JSON 数据结构定义

### A.1 SplitPreview

```json
{
  "total_chapters": 73,
  "total_chars": 156420,
  "volumes": [
    {
      "volume_number": 1,
      "volume_title": "初入都市",
      "chapters": [
        {"number": 1, "title": "第一章 苏醒", "chars": 2145},
        {"number": 2, "title": "第二章 第一次 PK", "chars": 2380}
      ]
    }
  ]
}
```

### A.2 TaskStatus

```json
{
  "task_id": "uuid-v4",
  "status": "running",        // pending | running | completed | failed
  "volume_dir": "...",
  "progress": {
    "total": 73,
    "processed": 37,
    "skipped": 5,
    "failed": 2
  },
  "stats": {
    "elapsed_seconds": 1234,
    "total_tokens": 156789
  },
  "error_message": null
}
```

### A.3 ChapterItem

```json
{
  "chapter_id": "chap_0001",
  "chapter_number": 1,
  "title": "第一章 苏醒",
  "chars": 2145,
  "status": "pending",       // pending | processing | processed | failed
  "error": null,
  "stats": {
    "tokens_total": 3456,
    "tokens_prompt": 2800,
    "tokens_completion": 656,
    "elapsed_seconds": 18.5
  }
}
```

---

**版本**: 1.0  
**设计日期**: 2026-08-17  
**最后更新**: 2026-08-17  
**状态**: ✅ 设计完成，等待实现