# Novel Structure Analyzer - 小说深度梳理与分析工具

**版本**: 3.0 (整洁版)  
**最后更新**: 2026-08-17  
**状态**: ✅ 生产就绪

---

## 📚 文档导航

### 🌟 核心文档
- [README.md](#) - 本文件（项目总览）
- [QUICKSTART.md](./QUICKSTART.md) - **15 分钟快速安装指南** ⭐ 推荐新手先看
- [AI_续写项目需求文档.md](./AI_续写项目需求文档.md) - 完整规格书（数据结构 + Prompt 模板）

### 📖 使用指南
- [docs/配置管理完整指南.md](./docs/配置管理完整指南.md) - 配置管理体系详解
- [docs/CLI_GUIDE.md](./docs/CLI_GUIDE.md) - **CLI 命令速查** ⭐ 推荐新手先看

### 🔧 Prompt 模板
- [prompts/core/chapter_processor.md](./prompts/core/chapter_processor.md) - 核心章节分析 Prompt

---

## 🎯 项目概述

这是一个**生产级的小说分析解决方案**，用于对任意长文/小说进行自动化章节解析、结构化分析和多模态存储。

### 核心功能

✅ **单章深度分析** - 八维结构化提取（事件、地点、人物、场景、成长、物品、秘密、总结）  
✅ **智能上下文管理** - 自动维护前文摘要链，确保剧情连贯性  
✅ **多模态存储** - JSON 文件 + ChromaDB 向量库 + SQLite 结构化数据库  
✅ **云端免费嵌入** - SiliconFlow API 支持（bge-m3 模型完全免费）  
✅ **批量自动化处理** - 并行处理、错误恢复、进度跟踪  
✅ **Prompt 解耦架构** - 所有提示词独立于代码，易于维护和扩展  

### 技术特点

- **无 GPU 依赖**: 全部云端 API 调用，本地只需基础 CPU/RAM
- **零成本可选**: SiliconFlow 免费额度 + 本地 ChromaDB 存储
- **完全离线可选**: Ollama 本地模型 + 本地存储（需 GPU）
- **生产级质量**: 多层验证、容错机制、详细日志
- **高度可扩展**: 插件系统、自定义 Prompt、多 Provider 支持

---

## 🚀 快速开始

### 方式 A: uv 安装（推荐⭐）

```powershell
cd D:\PLAY\AI-Hero_Reborn

# 一键同步依赖（自动创建 .venv）
uv sync

# 验证安装
uv run python scripts\verify_environment.py
```

### 方式 B: pip 安装（传统）

```powershell
cd D:\PLAY\AI-Hero_Reborn

# 创建虚拟环境
python -m venv venv
.\venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt

# 验证安装
python scripts\verify_environment.py
```

📖 **详细说明**: 见 [QUICKSTART.md](./QUICKSTART.md)

---

## 🛠️ CLI 工具箱

本项目提供了丰富的命令行工具，支持小说分析全流程：

### 基础配置与验证

```powershell
# 验证环境安装
uv run python scripts\verify_environment.py

# 交互式配置向导（推荐新手）
uv run python scripts\quick_setup.py
```

### 数据处理工具

#### 小说分割工具

将整卷文本自动分章：

```powershell
# 预览分割效果（不写文件）
uv run python scripts\split_novel.py -i "你的小说.txt" --preview

# 正式分割（输出到 user_data/novel_raw/）
uv run python scripts\split_novel.py -i "你的小说.txt" -o user_data\novel_raw

# 指定分卷号
uv run python scripts\split_novel.py -i "小说.txt" --volume 5

# 并发处理（加速大文件）
uv run python scripts\split_novel.py -i "小说.txt" --workers 8
```

**识别能力**:
- ✅ 标题模式：`第 X 章/节/回 `、`章节 X`、`Chapter X`、`001. 标题`
- ✅ 分卷识别：`第 X 卷 卷名 ` 自动归属卷号
- ✅ 中文数字：`第一百二十三章 `→第 123 章
- ✅ 编码自动探测：utf-8 / gb18030 / gbk / big5
- ✅ 兜底切分：无标题时按 3000 字聚合成段落

#### 批量处理引擎

对已分割的章节进行 AI 分析：

```powershell
# 基础用法（使用 ConfigManager 自动读取配置）
uv run python scripts\batch_processor.py

# 显式指定目录
uv run python scripts\batch_processor.py --input-dir user_data\novel_raw\ --output-dir user_data\novel_data\processed\ --workers 4

# 带向量存储和日志
uv run python scripts\batch_processor.py --vector-db-path user_data\database\chromadb\ --log-file custom.log

# 容错模式（失败跳过继续）
uv run python scripts\batch_processor.py --continue-on-failure
```

💡 **提示**: v2.0+ 使用统一的 ConfigManager，会自动从配置文件读取路径和 API Key

---

### 数据分析工具

#### 维度聚合工具

汇总所有章节的结构化数据：

```powershell
# 启用 AI 压缩（较慢但精炼）
uv run python scripts\aggregate_dimensions.py

# 快速模式（禁用 AI 压缩）
uv run python scripts\aggregate_dimensions.py --no-ai-compression

# 指定目录
uv run python scripts\aggregate_dimensions.py --input-dir user_data\novel_data\processed\ --output-dir user_data\novel_data\index\
```

**生成的维度库**:
- `character_library.json` - 人物库（去重 + 历史合并）
- `location_atlas.json` - 地点档案（访问历史 + 事件）
- `item_catalog.json` - 物品图鉴（全生命周期）
- `world_event_timeline.json` - 世界事件时间线
- `foreshadowing_library.json` - 伏笔库
- `plot_secrets_library.json` - 剧情秘密库

📖 **详细说明**: [scripts/README_aggregate.md](./scripts/README_aggregate.md)

#### 统计报表生成器

从 SQLite EAV 数据库生成统计报告：

```powershell
# 生成完整报表并打印摘要
uv run python scripts\generate_statistics_report.py

# 保存为 JSON 文件
uv run python scripts\generate_statistics_report.py -o user_data\reports\stats.json

# 自定义维度配置
uv run python scripts\generate_statistics_report.py -c config\dimensions\xianxia.yaml
```

**输出内容包括**:
- 📊 总章节数和记录数
- 📈 各维度分布统计
- 👥 角色出场 TOP 排名
- ⚔️ 事件频率分析

#### 维度配置切换器

一键切换不同的维度预设（仙侠/都市/科幻等）：

```powershell
# 列出所有可用预设
uv run python scripts\dimension_switcher.py --list

# 切换到仙侠配置
uv run python scripts\dimension_switcher.py --switch xianxia

# 强制切换（不询问确认）
uv run python scripts\dimension_switcher.py --switch urban --force

# 查看当前配置详情
uv run python scripts\dimension_switcher.py --show
```

**支持的预设类型**:
- `xianxia` - 仙侠小说（修真、门派、法宝）⭐ 默认
- `urban` - 都市小说（商战、情感、职场）
- `scifi` - 科幻小说（科技、外星、探索）
- `fantasy` - 奇幻小说（魔法、种族、大陆）

⚠️ **注意**: 切换维度配置会重新生成数据库表结构，旧数据会自动备份。

#### JSON → EAV 迁移工具

将 AI 分析输出的 JSON 批量导入 SQLite 数据库：

```powershell
# 使用默认配置（config/dimensions/xianxia.yaml）
uv run python scripts\migrate_json_to_eav.py

# 指定 JSON 输入目录
uv run python scripts\migrate_json_to_eav.py -i user_data\novel_data\processed\

# 自定义维度配置
uv run python scripts\migrate_json_to_eav.py -c config\dimensions\urban.yaml

# 覆盖已有数据库（谨慎使用）
uv run python scripts\migrate_json_to_eav.py --force
```

**功能特性**:
- ✅ 批量导入所有章节 JSON
- ✅ 自动生成 EAV 表结构
- ✅ 错误重试和日志记录
- ✅ 迁移报告生成

#### 端到端测试套件

运行完整的系统测试：

```powershell
# 运行 E2E 测试（7 个核心模块）
uv run python tests\integration\test_e2e_full_pipeline.py

# 显示详细日志
uv run python tests\integration\test_e2e_full_pipeline.py -v
```

**测试结果**:
```
[OK] ConfigManager working
[OK] DimensionEngine initialized
[OK] SQLiteEAVStorage functional
[OK] UnifiedQueryAPI operational
[OK] StatisticsReport generated
[OK] ChromaDB Enhancer active
[OK] DimensionSwitcher ready
✅ All 7 tests passed!
```

---

### 常用工作流示例

#### 场景 1: 处理一整本小说（从零开始）

```powershell
# Step 1: 准备配置
uv run python scripts\quick_setup.py

# Step 2: 分割小说（如果文本未分章）
uv run python scripts\split_novel.py -i "我的小说.txt" --volume 1

# Step 3: 批量分析章节
uv run python scripts\batch_processor.py --workers 8

# Step 4: 生成统计报告
uv run python scripts\generate_statistics_report.py

# Step 5: 验证结果
uv run python tests\integration\test_e2e_full_pipeline.py
```

#### 场景 2: 跨不同类型小说切换

```powershell
# 处理仙侠小说
uv run python scripts\dimension_switcher.py --switch xianxia --force
uv run python scripts\batch_processor.py
uv run python scripts\migrate_json_to_eav.py

# 切换到都市小说处理另一本书
uv run python scripts\dimension_switcher.py --switch urban --force
uv run python scripts\batch_processor.py  # 自动适配新维度
```

#### 场景 3: 分析与可视化

```powershell
# 生成结构化数据库
uv run python scripts\migrate_json_to_eav.py

# 导出统计数据
uv run python scripts\generate_statistics_report.py -o reports/stats.json

# 后续可用任何可视化工具读取 SQLite 和 JSON 文件
```



---

## ⚙️ 配置 API Key

### Step 1: 获取 SiliconFlow API Key（推荐🆓）

1. 访问 https://cloud.siliconflow.cn/signup
2. 注册并登录
3. 进入控制台 → Account → API Keys
4. 创建 New API Key（格式：`sf-xxxxx`）

**免费额度**: 
- AI 模型：约 100-1000 次/天免费
- Embedding: 完全免费

### Step 2: 创建 .env 文件

```powershell
# 复制模板
copy .env.example .env

# 编辑 .env 文件
notepad .env
```

填入你的 API Key：
```bash
AI_MODEL_API_KEY="sf-your-siliconflow-key"
SILICONFLOW_API_KEY="sf-your-siliconflow-key"
```

### Step 3: 生成配置文件

```powershell
# 复制 YAML 配置模板
copy config\production.example.yaml config\production.yaml
```

💡 **快捷方式**: 运行交互配置向导
```powershell
uv run python scripts\quick_setup.py
```

📖 **详细说明**: 
- [AI_API_Configuration_Guide.md](./docs/AI_API_Configuration_Guide.md)
- [配置管理完整指南.md](./docs/配置管理完整指南.md)

---

## 📁 准备输入数据

### 整卷小说分割（可选）

如果你有一整卷未分章的 txt 全文，用分割工具自动切分：

```powershell
# 预览分割效果（不写文件）
uv run python scripts\split_novel.py -i 你的小说.txt --preview

# 正式分割（输出到 output/raw/）
uv run python scripts\split_novel.py -i 你的小说.txt -o output/raw
```

**识别能力**:
- 标题模式：`第 X 章/节/回`、`章节 X`、`Chapter X`、`001. 标题`
- 分卷识别：`第 X 卷 卷名` 自动归属卷号
- 中文数字：`第一百二十三章` → 第 123 章
- 编码自动探测：utf-8 / gb18030 / gbk / big5
- 兜底切分：无标题时按 3000 字聚合成段落

### 手动准备章节文件

将原始文本文件放到 `output/raw/` 目录，命名规范：

```
output/raw/
├── vol_1_chap_01.txt
├── vol_1_chap_02.txt
├── vol_1_chap_03.txt
└── ...
```

支持的文件命名格式：
- `vol_X_chap_Y.txt` → 卷 X 第 Y 章
- `chapter_XXXX_标题.txt` → 兼容旧版分割工具
- `01.txt`、`01_标题.txt` → 默认卷 1

---

## 🔄 运行批量处理

```powershell
# 基础用法
uv run python scripts\batch_processor.py --input-dir output/raw/ --output-dir output/processed/ --workers 4

# 带向量存储
uv run python scripts\batch_processor.py --input-dir output/raw/ --output-dir output/processed/ --vector-db-path db/local_vector_store --workers 4

# 容错模式（失败跳过继续）
uv run python scripts\batch_processor.py --input-dir output/raw/ --continue-on-failure
```



📖 **详细说明**: [配置管理完整指南.md](./docs/配置管理完整指南.md)

---

## 📊 聚合维度库（可选）

处理完所有章节后，生成统一的索引库：

```powershell
# 启用 AI 压缩（较慢但精炼）
uv run python scripts\aggregate_dimensions.py

# 快速模式（禁用 AI 压缩）
uv run python scripts\aggregate_dimensions.py --no-ai-compression

# 指定目录
uv run python scripts\aggregate_dimensions.py --input-dir output/processed/ --output-dir output/index/
```

**生成的维度库**:
- `character_library.json` - 人物库（去重 + 历史合并）
- `location_atlas.json` - 地点档案（访问历史 + 事件）
- `item_catalog.json` - 物品图鉴（全生命周期）
- `world_event_timeline.json` - 世界事件时间线
- `foreshadowing_library.json` - 伏笔库
- `plot_secrets_library.json` - 剧情秘密库

📖 **详细说明**: [scripts/README_aggregate.md](./scripts/README_aggregate.md)

---

## 🏗️ 项目结构

```
AI-Hero_Reborn/
├── src/ai_novel_analyzer/        # 核心源码
│   ├── core/                      # 处理器 + Prompt 管理器
│   │   ├── config_manager.py      # ✨ 统一配置管理
│   │   ├── dimension_engine.py    # ✨ 声明式维度引擎
│   │   └── logging_config.py      # ✨ 日志系统
│   ├── models/                    # 数据模型 + Schema
│   ├── storage/                   # 三层存储系统
│   │   ├── sqlite_eav_storage.py  # ✨ EAV 数据库
│   │   ├── unified_query_api.py   # ✨ 统一查询 API
│   │   └── chroma_enhancer.py     # ✨ 向量增强
│   └── utils/                     # API 客户端 + 工具
│
├── prompts/                       # Prompt 模板库
│   ├── core/chapter_processor.md  # 核心 Prompt ⭐
│   ├── tasks/*.md                 # 专项任务 Prompts
│   └── templates/output_schema.json
│
├── config/
│   ├── defaults.yaml              # 默认配置（Git 版本）
│   ├── production.example.yaml    # 配置模板（Git 版本）
│   ├── production.yaml            # 个人配置（忽略）
│   └── dimensions/                # ✨ 维度预设
│       ├── xianxia.yaml          # 仙侠小说（11 维）
│       └── urban.yaml            # 都市小说（7 维）
│
├── scripts/                       # CLI 工具箱
│   ├── verify_environment.py      # 环境验证
│   ├── quick_setup.py             # 交互式配置向导
│   ├── split_novel.py             # 小说分割工具
│   ├── batch_processor.py         # 批量处理引擎
│   ├── aggregate_dimensions.py    # 维度聚合工具
│   ├── migrate_json_to_eav.py     # ✨ JSON→EAV 迁移
│   ├── generate_statistics_report.py # ✨ 统计报表
│   ├── dimension_switcher.py      # ✨ 维度切换
│   └── test_*.py                  # 测试辅助脚本
│
├── tests/                         # ✨ 规范化测试
│   ├── conftest.py                # Pytest fixtures
│   ├── integration/
│   │   └── test_e2e_full_pipeline.py # E2E 测试
│   └── test_*/                    # 单元测试（可选）
│
├── user_data/                     # ✨ 标准数据目录
│   ├── novel_raw/                 # 原始小说文本（输入）
│   ├── novel_data/                # AI 分析结果（输出）
│   │   ├── raw/                   # 分割章节
│   │   ├── processed/             # JSON 文件
│   │   └── summaries/             # 章节摘要
│   └── database/                  # SQLite + ChromaDB
│
├── docs/                          # 文档目录
│   ├── AI_API_Configuration_Guide.md
│   ├── 配置管理完整指南.md
│   ├── INSTALLATION_GUIDE.md
│   └── PHASE_0-4_IMPLEMENTATION_SUMMARY.md
│
├── logs/                          # ✨ 统一日志目录
├── .env                           # 环境变量（忽略）
├── .env.example                   # 环境变量模板
├── QUICKSTART.md                  # 快速开始
└── pyproject.toml                 # uv 配置
```

---

### CLI 命令速查表

| 命令 | 用途 | 状态 |
|------|------|------|
| `split_novel.py` | 小说文本分割 | ✅ 可用 |
| `batch_processor.py` | AI 批量分析 | ✅ 可用 |
| `aggregate_dimensions.py` | 维度数据聚合 | ✅ 可用 |
| `generate_statistics_report.py` | 统计报表生成 | ✅ 新增 |
| `dimension_switcher.py` | 维度配置切换 | ✅ 新增 |
| `migrate_json_to_eav.py` | JSON→EAV 迁移 | ✅ 新增 |
| `test_e2e_full_pipeline.py` | 端到端测试 | ✅ 新增 |
| `quick_setup.py` | 交互式配置 | ✅ 维护 |
| `verify_environment.py` | 环境验证 | ✅ 维护 |

📚 完整文档：[PHASE_0-4_IMPLEMENTATION_SUMMARY.md](./docs/PHASE_0-4_IMPLEMENTATION_SUMMARY.md)

---

## 🤖 支持的 AI Provider

```
AI-Hero_Reborn/
├── src/ai_novel_analyzer/        # 核心源码
│   ├── core/                      # 处理器 + Prompt 管理器
│   ├── models/                    # 数据模型 + Schema
│   ├── storage/                   # 三层存储系统
│   └── utils/                     # API 客户端 + 工具
│
├── prompts/                       # Prompt 模板库
│   ├── core/chapter_processor.md  # 核心 Prompt ⭐
│   ├── tasks/*.md                 # 专项任务 Prompts
│   └── templates/output_schema.json
│
├── config/
│   ├── default.yaml               # 默认配置（Git 版本）
│   ├── production.example.yaml    # 配置模板（Git 版本）
│   └── production.yaml            # 个人配置（忽略）
│
├── scripts/
│   ├── split_novel.py             # 小说分割工具
│   ├── batch_processor.py         # 批量处理引擎
│   ├── aggregate_dimensions.py    # 维度聚合工具
│   └── *.py                       # 测试/辅助脚本
│
├── docs/                          # 文档目录
│   ├── AI_API_Configuration_Guide.md
│   ├── 配置管理完整指南.md
│   └── INSTALLATION_GUIDE.md
│
├── output/                        # 数据存储
│   ├── raw/                       # 原始文本
│   ├── processed/                 # JSON 结果
│   └── db/                        # 数据库文件
│
├── .env                           # 环境变量（忽略）
├── .env.example                   # 环境变量模板
├── README.md                      # 本文件
├── QUICKSTART.md                  # 快速开始
└── pyproject.toml                 # uv 配置
```

---

## 🤖 支持的 AI Provider

| Provider | 价格 | 速度 | 中文质量 | 推荐场景 |
|---------|------|------|---------|---------|
| **SiliconFlow** 🆓 | 有免费额度 | 快 | ⭐优秀 | 性价比最高 |
| **OpenAI** | $0.005/k token | 中 | 良 | 通用性强 |
| **Groq** ⚡ | 有免费 tier | ⚡极快 | 良 | 快速测试 |
| **Ollama** | 免费 | 取决于硬件 | 视模型 | 完全离线 |

📖 **详细配置指南**: [AI_API_Configuration_Guide.md](./docs/AI_API_Configuration_Guide.md)

---

## 💻 Python API 调用

```python
from ai_novel_analyzer.core.chapter_processor import ChapterProcessor
from ai_novel_analyzer.core.prompt_manager import PromptManager
from ai_novel_analyzer.models import NovelChapterInput

# 初始化
pm = PromptManager()
processor = ChapterProcessor(prompt_manager=pm)

# 创建输入
chapter_input = NovelChapterInput(
    chapter_id="vol_1_chap_01",
    chapter_title="第一章",
    content="原文内容...",
    volume_number=1,
    chapter_number=1
)

# 处理单章
result = processor.process_chapter(chapter_input)

# 访问结构化数据
events = result.structured_data.get('world_events', [])
characters = result.structured_data.get('characters', [])
print(f"发现 {len(events)} 个重大事件")
print(f"识别到 {len(characters)} 个人物")
```

---

## 🐛 常见问题

### Q1: "API Key not found"
**解决**: 确认 `.env` 文件存在且已填入正确的 API Key

```powershell
# 检查文件
cat .env

# 验证加载
uv run python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('AI_MODEL_API_KEY'))"
```

### Q2: "Memory error during batch processing"
**解决**: 降低并发数

```yaml
# config/production.yaml
processing.max_workers: 2
```

### Q3: SiliconFlow 需要安装额外包吗？
**回答**: 不需要！通过标准 `requests` 库直接调用 OpenAI 兼容 API

### Q4: 需要 GPU 吗？
**回答**: 完全不需要！ChromaDB 和 SiliconFlow 都是 CPU 友好的方案

📖 **更多问题**: [INSTALLATION_GUIDE.md](./docs/INSTALLATION_GUIDE.md)

---

## 📈 性能指标

### 预期处理速度

| 场景 | 配置 | 预计速度 |
|------|------|---------|
| 单章处理 | 1 worker | ~30-60 秒/章 |
| 批量处理 | 4 workers | ~75-150 章/小时 |
| 批量处理 | 8 workers | ~60-120 章/小时 |

### 资源占用

| 资源 | 最低要求 | 推荐配置 |
|------|---------|---------|
| CPU | Intel i5 / AMD Ryzen 5 | Intel i7 / AMD Ryzen 7 |
| RAM | 8GB | 16GB+ |
| Disk | 10GB SSD | 20GB SSD |
| GPU | ❌ 不需要 | 可选加速 |
| Network | 稳定连接 | ≥10Mbps |

---

## 📚 八维输出结构

每个章节的分析结果包含：

1. **`world_events`** - 世界观事件（重大变更、规则调整、势力变动）
2. **`locations`** - 地点档案（类型、状态变化、关联人物/事件）
3. **`characters`** - 人物档案（属性、身份、关系网络）
4. **`scenes`** - 故事片段（场景化剧情单元）
5. **`growth`** - 主角成长（能力、心智、社交、情感四维）
6. **`items`** - 物品图鉴（获取、强化、损失生命周期）
7. **`plot_secrets`** - 剧情秘密（反转、揭露、伏笔线索）
8. **`chapter_summary`** - 章节总结摘要（用于上下文连贯）

📖 **详细定义**: [AI_续写项目需求文档.md](./AI_续写项目需求文档.md)

---

## 🔄 数据归一化策略

从 v3.1 起，Schema 中所有分类/分级字段（tone、impact、type、category、rarity、urgency、emotion 等）改为**自由文本**，由 AI 使用原文术语输出。

**原因**: 不同小说的设定体系各异，预定义枚举无法覆盖。

**待办方案**: 当某字段 distinct 值超过约 20 个时，开发聚类归一脚本：
1. 读取所有章节 JSON，提取目标字段的 distinct 值及频次
2. 调用 AI 对相近词汇预分组
3. **人工最终确认合并粒度与命名**
4. 生成映射表，统计时通过映射表虚拟归一
5. 不回填原始数据，保留原始术语

---

## 🚧 开发路线

### Phase 0: 基础设施重构 ✅ (已完成)
- [x] ConfigManager 统一配置管理系统
- [x] 声明式维度引擎 (DimensionEngine)
- [x] SQLite EAV 结构化存储
- [x] 统一查询 API (UnifiedQueryAPI)
- [x] 维度配置切换工具
- [x] JSON→EAV 迁移工具
- [x] 统计报表生成器
- [x] E2E 测试套件 (7/7 通过)
- [x] 标准化目录结构和日志系统

### Phase 1-3: 核心功能 ✅ (已完成)
- [x] Prompt 模板库构建
- [x] 单章处理器实现
- [x] 三层存储系统
- [x] 批量处理引擎
- [x] 配置管理系统
- [x] AI API 客户端工厂

### Phase 2: 扩展功能 🔄 (进行中)
- [ ] 可视化前端界面（Plotly + Dash）
- [ ] SQLite 结构化数据库完整实现
- [ ] Web 服务 API（FastAPI）
- [ ] 自动化测试套件
- [ ] Docker 容器化支持

### Phase 3: 高级功能 ⏳ (规划中)
- [ ] 分布式处理（Redis + Celery）
- [ ] 实时流式处理
- [ ] 主动学习反馈循环
- [ ] 跨作品风格迁移
- [ ] 插件生态系统
- [ ] 分布式处理（Redis + Celery）
- [ ] Docker 容器化部署
- [ ] Web 前端界面（React/Vue + FastAPI）
- [ ] GraphQL 数据服务层

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

### 提交规范

1. Fork 项目
2. 创建特性分支：`git checkout -b feature/amazing-feature`
3. 添加测试（如有）
4. 更新文档
5. 提交 PR：`git push origin feature/amazing-feature`

### 代码风格

- 遵循 PEP 8 规范
- 添加类型注解（type hints）
- 编写 docstring
- 保持函数简洁单一职责

---

## 🔐 安全建议

### ✅ 应该做的

1. 使用环境变量存储 API Key
2. 定期轮换密钥（每季度）
3. 监控 API 使用情况
4. 将 `.env` 加入 `.gitignore`
5. 不同环境使用不同密钥

### ❌ 不应该做的

1. 硬编码密钥在代码中
2. 提交 `.env` 到 Git
3. 共享密钥给他人
4. 使用简单密码
5. 在公开场合暴露配置

---

## 📦 技术栈

### 核心 Python 依赖

| 包名 | 用途 |
|------|------|
| `requests` | OpenAI 兼容 API 调用 |
| `pyyaml` | YAML 配置解析 |
| `python-dotenv` | .env 环境变量加载 |
| `jsonschema` | JSON Schema 验证 |
| `pydantic` | 数据模型验证 |
| `chromadb` | 本地向量数据库 |
| `tqdm` | 进度条显示 |
| `tiktoken` | Token 计数 |

📖 **详细说明**: [INSTALLATION_GUIDE.md](./docs/INSTALLATION_GUIDE.md)

---

## 📞 联系方式

- **Issue Tracker**: GitHub Issues
- **文档**: 见 `docs/` 目录

---

## 🎯 立即行动清单

### 今天就能做
- [ ] 注册 SiliconFlow 账号并获取 API Key
- [ ] 复制 `.env.example` 为 `.env`
- [ ] 填入你的 API Keys
- [ ] 准备 1-2 个测试章节

### 本周内
- [ ] 运行小规模批量处理（前 5 章）
- [ ] 验证 JSON 输出质量
- [ ] 调整配置文件（并发数、模型等）
- [ ] 检查向量搜索功能

### 长期规划
- [ ] 全量数据处理
- [ ] 构建前端界面（可选）
- [ ] 持续优化 Prompt 模板
- [ ] 建立自动化测试流程

---

**最后更新**: 2026-08-17  
**版本**: 3.0  
**状态**: ✅ 生产环境就绪  

*Built with ❤️ for novel analysis and continuation support*
