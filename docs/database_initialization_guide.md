# 数据库初始化完整指南

## 📊 项目数据库结构总览

本项目使用**混合数据库架构**，包含三种不同类型的存储:

### 1️⃣ **SQLite EAV 数据库** (`workspace/db/eav_novel.db`)
- **用途**: 存储分析后的结构化维度数据
- **特性**: 
  - 动态表结构 (根据维度配置自动生成)
  - Entity-Attribute-Value 模式，支持灵活扩展
  - 索引优化，查询快速
- **表组成**:
  - `chapters`: 章节基本信息表 (固定)
  - `eav_character_names`: 角色维度表 (示例)
  - `eav_locations`: 地点维度表 (示例)
  - ... (其他维度表)

### 2️⃣ **SQLite 任务历史库** (`workspace/db/novel_analyzer.db`)
- **用途**: 记录所有分析任务的执行历史
- **表**: `analysis_tasks`
  - 字段: `task_id`, `scope`, `project`, `book`, `volume_dir`, 
         `start_time`, `end_time`, `total_chapters`, 
         `success_count`, `failed_count`, `status`, `detail_json` 等
- **用途场景**:
  - 查看任务执行历史
  - 监控批量分析进度
  - 故障排查和审计

### 3️⃣ **ChromaDB 向量库** (`workspace/db/chromadb/`)
- **用途**: 存储章节文本的向量嵌入
- **集合**: `novel_chunks`
- **嵌入模型**: `BAAI/bge-m3` (1024 维)
- **用途场景**:
  - 语义搜索
  - 相似章节推荐
  - 智能问答

---

## 🚀 手动初始化脚本

### 使用方法

```bash
# 方式 1: 使用 uv(推荐)
uv run scripts/init_database.py

# 方式 2: 直接运行 python
python scripts/init_database.py
```

### 功能特性

✅ **自动创建工作目录结构**
- `workspace/projects/` - 项目书籍目录
- `workspace/db/` - 数据库目录
- `logs/` - 日志目录
- `output/` - 输出目录

✅ **初始化 ChromaDB 向量存储**
- 创建 `.lock` 文件防止并发问题
- 验证集合可访问性

✅ **创建任务历史数据库**
- 初始化 `analysis_tasks` 表
- 创建性能优化索引
- 启用 WAL 模式提升并发性能

✅ **创建 EAV 维度数据库**
- 读取维度配置文件 (`config/dimensions/xianxia.yaml`)
- 根据配置自动生成维度表
- 为每个表的常用字段创建索引

✅ **显示详细统计信息**
- 各数据库文件大小
- 表结构和字段列表
- 索引信息
- 现有记录数

---

## 📋 表结构详解

### analysis_tasks (任务历史表)

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | TEXT (PK) | 任务唯一标识 |
| scope | TEXT | 分析粒度：book/volume |
| project | TEXT | 项目名称 |
| book | TEXT | 书名 |
| volume_dir | TEXT | 卷目录名 (NULL=整本书) |
| start_time | REAL | 开始时间 (Unix timestamp) |
| end_time | REAL | 结束时间 (NULL=进行中) |
| total_chapters | INTEGER | 总章节数 |
| success_count | INTEGER | 成功章节数 |
| failed_count | INTEGER | 失败章节数 |
| retry_count | INTEGER | 重试次数 |
| status | TEXT | queued/running/success/failed |
| failure_reason | TEXT | 失败原因 |
| detail_json | TEXT | JSON 字符串：卷/章级明细 |

**索引**:
- `idx_task_status` - 按状态查询
- `idx_task_project_book` - 按项目/书查询
- `idx_task_volume` - 按卷查询

### chapters (EAV 基础表)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER (PK) | 自增主键 |
| chapter_id | TEXT (UNIQUE) | 章节唯一标识 |
| volume_number | INTEGER | 卷号 |
| chapter_number | INTEGER | 章号 |
| title | TEXT | 章节标题 |
| content_hash | TEXT | 内容哈希 |
| processed_at | TIMESTAMP | 处理时间 |

**索引**:
- `idx_chapter_id` - 按章节 ID 查询
- `idx_volume_chapter` - 按卷/章组合查询

### eav_{dimension_key} (维度表 - 动态生成)

以角色维度为例 (`eav_character_names`):

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER (PK) | 自增主键 |
| chapter_id | TEXT NOT NULL | 引用章节表 |
| volume_number | INTEGER | 卷号 |
| chapter_number | INTEGER | 章号 |
| name | TEXT | 角色名称 |
| cultivation_level | TEXT | 修为境界 |
| current_location | TEXT | 当前位置 |
| role | TEXT | 角色定位 |
| ... | TEXT | 其他提取字段... |

**外键约束**: `chapter_id` → `chapters(chapter_id)` ON DELETE CASCADE

**索引**:
- `idx_eav_{dim}_chapter` - 按章节查询
- `idx_eav_{dim}_{第一字段}` - 按第一个提取字段查询

---

## 🔧 常见问题

### Q1: 何时需要手动初始化？

✅ **首次部署时** - 提前准备好所有数据库  
✅ **数据库损坏时** - 清空后重新初始化  
✅ **新增维度配置时** - 需要创建新维度表  
✅ **生产环境标准化** - 确保所有服务器环境一致  

### Q2: 如果数据库已存在怎么办？

脚本会智能检测:
- ⏭️ **跳过已有表** - 不会重复创建
- ✅ **只初始化缺失部分** - 增量更新
- 💡 **提示已有记录数** - 方便确认数据完整性

### Q3: 如何验证初始化成功？

运行脚本后检查:
```
✅ 工作空间目录结构 - 所有必需目录已创建
✅ ChromaDB 向量存储 - 集合可访问
✅ 任务历史日志数据库 - analysis_tasks 表存在
✅ EAV 维度数据库 - 所有章节表和维度表已创建
```

### Q4: 数据库路径在哪里？

默认位置 (可在 `config/production.yaml` 中修改):
```
workspace/
├── db/
│   ├── novel_analyzer.db          # 任务历史库
│   ├── eav_novel.db               # EAV 维度库
│   └── chromadb/                   # ChromaDB 向量库
│       └── ... (内部文件)
```

### Q5: 可以重置数据库吗？

可以，但会**永久删除所有数据**!

```bash
# 删除数据库文件
rm workspace/db/*.db
rm -rf workspace/db/chromadb/*

# 重新初始化
uv run scripts/init_database.py
```

⚠️ **警告**: 此操作不可逆，请谨慎执行!

---

## 📝 典型工作流程

### 场景 1: 全新部署
```bash
# 1. 安装依赖
uv sync

# 2. 初始化数据库
uv run scripts/init_database.py

# 3. 启动 Web UI
cd webui
uv run python main.py
```

### 场景 2: 清理重置
```bash
# 1. 停止 Web UI

# 2. 删除旧数据库
rm workspace/db/*.db
rm -rf workspace/db/chromadb/*

# 3. 重新初始化
uv run scripts/init_database.py

# 4. 重启 Web UI
```

### 场景 3: 新增维度配置

假设您想在 `xianxia.yaml` 中添加新的维度:

1. 编辑 `config/dimensions/xianxia.yaml`
2. 运行初始化脚本:
   ```bash
   uv run scripts/init_database.py
   ```
3. 脚本会自动检测到新增的维度并创建对应的 EAV 表

---

## 🎯 高级用法

### 单独初始化某个数据库

如果您只想初始化特定数据库，可以修改脚本或手动执行:

```python
# Python交互式调试
from pathlib import Path
import sqlite3
from ai_novel_analyzer.core.config_manager import get_config

config = get_config()
db_path = config.db.path / "novel_analyzer.db"

conn = sqlite3.connect(str(db_path))
conn.execute('PRAGMA journal_mode = WAL')
# ... 手动执行建表语句 ...
conn.close()
```

### 导出数据库 schema

```bash
# SQLite 数据库导出 schema
sqlite3 workspace/db/novel_analyzer.db ".schema" > analysis_tasks_schema.sql
sqlite3 workspace/db/eav_novel.db ".schema" > eav_schema.sql

# ChromaDB 无 schema 概念 (动态创建)
```

### 数据库备份建议

```bash
# 定时备份脚本
#!/bin/bash
BACKUP_DIR="backups/db_$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

cp workspace/db/*.db "$BACKUP_DIR/"
cp -r workspace/db/chromadb "$BACKUP_DIR/"

echo "备份完成：$BACKUP_DIR"
```

---

## 📖 相关文档

- [SQL Lite EAV Storage](src/ai_novel_analyzer/storage/sqlite_eav_storage.py) - EAV 存储实现
- [Task Logging Implementation](docs/task_logging_implementation.md) - 任务日志系统详解
- [Config Management Guide](docs/配置管理完整指南.md) - 配置管理完整指南

---

## 🆘 技术支持

如遇问题，请提供以下信息:
1. 完整的错误日志
2. 数据库文件路径
3. 维度配置文件内容
4. Python 版本和依赖列表

---

**最后更新**: 2026-08-18  
**脚本版本**: v1.0
