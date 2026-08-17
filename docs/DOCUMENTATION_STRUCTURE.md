# 📚 文档结构说明

**最后更新**: 2026-08-17  
**版本**: v3.0

---

## 🎯 文档层级架构

本项目采用**分层式文档结构**，从入门到高级逐步深入。

```
docs/
├── README.md                     # ⭐ 总入口（根目录）
│
├── 快速开始/
│   └── QUICKSTART.md             # 15 分钟安装指南
│
├── 核心文档/
│   ├── README.md                 # 项目总览 + 完整功能说明
│   ├── AI_续写项目需求文档.md     # 原始规格书（数据结构 + Prompt）
│   └── docs/配置管理完整指南.md   # 配置管理体系详解
│
├── API 配置/
│   └── AI_API_Configuration_Guide.md  # AI Provider 选型与配置
│
├── Prompt 库/
│   ├── prompts/README.md         # Prompt 使用手册
│   ├── prompts/core/chapter_processor.md  # 核心分析 Prompt
│   └── prompts/tasks/*.md        # 专项任务 Prompts
│
└── 工具使用/
    ├── scripts/README_aggregate.md      # 维度聚合工具
    └── docs/INSTALLATION_GUIDE.md       # 安装依赖详解
```

---

## 📖 各文档详细说明

### 🌟 核心文档（必读）

#### 1. **README.md** - 项目总入口
**位置**: 根目录  
**用途**: 项目的第一印象和快速导航
- ✅ 项目概述与核心功能
- ✅ 快速开始指引
- ✅ 文档导航地图
- ✅ 常见问题速查

**适合人群**: 所有人（第一次使用）

---

#### 2. **QUICKSTART.md** - 15 分钟快速安装
**位置**: 根目录  
**用途**: 从零到可运行的最短路径
- ✅ 两种安装方式对比（uv vs pip）
- ✅ 一键同步依赖
- ✅ 环境验证步骤
- ✅ 常见问题 FAQ

**适合人群**: 新手、想要快速上手的人

**阅读时间**: ~15 分钟

---

#### 3. **AI_续写项目需求文档.md** - 完整规格书
**位置**: 根目录  
**用途**: 完整的技术规格和设计文档
- ✅ 八维数据结构详细定义
- ✅ 完整 Prompt 模板（Role/Objective/Input/Output）
- ✅ 数据流设计与实现思路
- ✅ 扩展规划与路线图

**适合人群**: 开发者、想了解底层设计的人

**阅读时间**: ~60 分钟（可跳读）

---

### 📋 使用指南类

#### 4. **docs/AI_API_Configuration_Guide.md** - AI API 配置指南
**位置**: docs/  
**用途**: 如何选择和配置 AI Provider
- ✅ OpenAI/SiliconFlow/Groq/Ollama 对比表
- ✅ 每种 Provider 的 YAML 配置示例
- ✅ 场景化推荐（性价比/离线/极速）
- ✅ 实际代码示例
- ✅ 故障排查方法

**适合人群**: 需要更换 AI 模型或优化配置的人

**关键内容**:
```markdown
## 🎯 性能 vs 成本对比表
| Provider | 价格 | 速度 | 中文质量 | 离线 |
|---------|------|------|---------|------|
| SiliconFlow 🆓 | 有免费额度 | 快 | ⭐优秀 | 否 |
| Groq ⚡ | 有免费 tier | ⚡极快 | 良 | 否 |
| Ollama | 免费 | 取决于硬件 | 视模型 | ✅ |
```

---

#### 5. **docs/配置管理完整指南.md** - 配置管理体系
**位置**: docs/  
**用途**: 理解四层配置架构和使用方法
- ✅ CLI > YAML > .env > default.yaml 优先级
- ✅ `.env` 敏感信息管理
- ✅ `production.yaml` 运行时配置
- ✅ 多环境切换策略
- ✅ 安全最佳实践

**适合人群**: 需要深度定制配置的人

**核心概念**:
```
┌─────────────────────────┐
│ Layer 1: CLI 命令行参数   │  ← 临时覆盖（最高优先级）
├─────────────────────────┤
│ Layer 2: production.yaml │  ← 运行时配置（引用.env）
├─────────────────────────┤
│ Layer 3: .env 环境变量    │  ← 敏感信息（不存 Git）
├─────────────────────────┤
│ Layer 4: default.yaml    │  ← 全局默认值（Git 版本）
└─────────────────────────┘
```

---

#### 6. **docs/INSTALLATION_GUIDE.md** - 安装依赖详解
**位置**: docs/  
**用途**: 详细的依赖管理和故障排查
- ✅ 核心 Python 包清单（8 个必需）
- ✅ SiliconFlow 接入方式说明
- ✅ uv vs pip 详细对比
- ✅ 国内镜像源加速
- ✅ 常见问题 FAQ

**适合人群**: 遇到安装问题的人

**关键事实**:
> SiliconFlow（硅基流动）**没有官方 Python SDK**，PyPI 上不存在 `siliconflow` 包。项目通过 `requests` 直接调用 OpenAI 兼容 API。

---

### ✍️ Prompt 库类

#### 7. **prompts/README.md** - Prompt 使用手册
**位置**: prompts/  
**用途**: 理解和使用 Prompt 模板库
- ✅ Prompt 目录结构说明
- ✅ P0/P1/P2 优先级分类
- ✅ Prompt 编写规范
- ✅ 质量检查清单
- ✅ 最佳实践示例

**适合人群**: 需要修改或新增 Prompt 的人

**核心规则**:
```markdown
## 编写规范
1. 明确 Input 参数边界
2. 指定 Output 精确格式
3. 包含处理规则和示例
4. 覆盖特殊情况处理
5. 语言简洁无歧义
6. 角色设定清晰合理
```

---

#### 8. **prompts/core/chapter_processor.md** - 核心分析 Prompt
**位置**: prompts/core/  
**用途**: 单章深度分析的核心 Prompt
- ✅ Role 定义（文学分析师 + 知识图谱专家）
- ✅ Objective（八维结构化提取）
- ✅ Input Format（前情提要 + 本章正文）
- ✅ Output Schema（JSON 结构定义）
- ✅ Processing Guidelines（准确性>完整性）

**适合人群**: 想要理解或调整 AI 分析逻辑的人

**重要约束**:
```markdown
### ⚠️ 重要说明
- 【前情提要】仅供参考，用于理解上下文背景
- 分析必须完全基于【本章正文】
- 不得依赖或推断 </summary> 和 <chapter_text> 之间的关联
- 所有输出字段的数据来源应限于 <chapter_text>
```

---

### 🔧 工具使用类

#### 9. **scripts/README_aggregate.md** - 维度聚合工具
**位置**: scripts/  
**用途**: 将章节分析结果聚合为统一索引库
- ✅ 六维度聚合说明（人物/地点/物品/事件/伏笔/秘密）
- ✅ 使用方法（启用/禁用 AI 压缩）
- ✅ 输出结构示例
- ✅ 工作流程图
- ✅ 故障排查

**适合人群**: 处理完所有章节后想要生成汇总报告的人

**关键特性**:
```markdown
## 独立运行
不与 batch_processor 流程绑定，可手动触发执行

## 轻量 AI 调用
仅提取关键字段（人物、地点、物品等元数据）喂给 AI，不传输原始章节文本

## 增量聚合优势
- ✅ 不阻塞批量处理流程
- ✅ 可在处理后任意时间触发
- ✅ 支持多次执行（每次重新聚合最新状态）
```

---

### 🗑️ 已删除的文档（记录原因）

以下文档因**内容过时**或**技术细节冗余**而被删除：

| 原文件名 | 删除原因 |
|---------|---------|
| `docs/CONFIGURATION_MANAGEMENT.md` | 与 `配置管理完整指南.md` 内容高度重合 |
| `docs/Context_Chaining_Implementation.md` | 技术实现细节已在代码中体现，文档价值低 |
| `docs/Context_Summary_Implementation.md` | 同上 |
| `docs/FIX_chapter2_json_error.md` | Bug 修复记录，问题已解决无需保留历史 |
| `docs/RETRY_MECHANISM_REFACTOR.md` | 重构过程记录，当前版本已不同 |
| `AI_续写项目需求文档.md` | 内容已迁移到 README_NEW.md（已删除原始版本） |

---

## 📊 文档使用场景对照表

### 🎯 我想快速运行起来
→ [QUICKSTART.md](../QUICKSTART.md)

### 🎯 我想了解项目能做什么
→ [README.md](../README.md)

### 🎯 我想配置 AI API
→ [AI_API_Configuration_Guide.md](../docs/AI_API_Configuration_Guide.md)

### 🎯 我想深度定制配置
→ [配置管理完整指南.md](../docs/配置管理完整指南.md)

### 🎯 我想理解 Prompt 设计
→ [prompts/README.md](../prompts/README.md) + [chapter_processor.md](../prompts/core/chapter_processor.md)

### 🎯 我想生成维度汇总报告
→ [scripts/README_aggregate.md](../scripts/README_aggregate.md)

### 🎯 我想安装依赖时遇到问题
→ [INSTALLATION_GUIDE.md](../docs/INSTALLATION_GUIDE.md)

### 🎯 我想看底层数据结构
→ [AI_续写项目需求文档.md](../AI_续写项目需求文档.md)

---

## 🔄 文档维护建议

### ✅ 应该做的
1. **及时更新**: 代码变更后同步更新相关文档
2. **保持一致**: 避免同一主题有多份不同版本的文档
3. **添加示例**: 每个概念都配以实际可运行的代码示例
4. **定期审查**: 每季度检查一次文档准确性
5. **版本控制**: 在文档头部注明最后更新日期和版本号

### ❌ 不应该做的
1. **创建重复文档**: 同一主题只在最合适的地方维护一份
2. **保留过期文档**: 已解决的问题无需保留历史记录
3. **忽略文档**: 代码和文档脱节会导致用户困惑
4. **过度设计**: 不要为了完美而延迟发布

---

## 📈 文档演进历史

| 版本 | 日期 | 主要变更 |
|------|------|---------|
| v3.0 | 2026-08-17 | 大规模整合，删除过时技术细节，建立分层结构 |
| v2.0 | 2026-08-16 | 重构为通用版，去除《再生勇士》专有名词 |
| v1.x | <2026-08-16 | 原始项目文档（已归档） |

---

## 🎓 学习路径推荐

### 🌱 新手入门（~30 分钟）
1. 阅读 [README.md](../README.md) 了解项目 (~5 分钟)
2. 跟随 [QUICKSTART.md](../QUICKSTART.md) 完成安装 (~15 分钟)
3. 运行第一个批量处理任务 (~10 分钟)

### 🌿 进阶使用（~60 分钟）
1. 学习 [AI_API_Configuration_Guide.md](../docs/AI_API_Configuration_Guide.md) 选择最优 Provider (~20 分钟)
2. 理解 [配置管理完整指南.md](../docs/配置管理完整指南.md) 的四层架构 (~20 分钟)
3. 尝试修改配置文件并观察效果 (~20 分钟)

### 🌳 深度定制（~2 小时）
1. 研读 [AI_续写项目需求文档.md](../AI_续写项目需求文档.md) 的数据结构定义 (~40 分钟)
2. 分析 [prompts/core/chapter_processor.md](../prompts/core/chapter_processor.md) 的 Prompt 设计 (~40 分钟)
3. 尝试修改 Prompt 并验证输出质量 (~40 分钟)

---

## 🔗 快速链接索引

| 类别 | 文件 | 用途 |
|------|------|------|
| **核心** | README.md | 项目总入口 |
| **入门** | QUICKSTART.md | 15 分钟快速安装 |
| **规格** | AI_续写项目需求文档.md | 完整数据结构定义 |
| **配置** | docs/AI_API_Configuration_Guide.md | AI Provider 选型 |
| **配置** | docs/配置管理完整指南.md | 四层配置体系 |
| **依赖** | docs/INSTALLATION_GUIDE.md | 依赖管理详解 |
| **Prompt** | prompts/README.md | Prompt 使用手册 |
| **Prompt** | prompts/core/chapter_processor.md | 核心分析 Prompt |
| **工具** | scripts/README_aggregate.md | 维度聚合工具 |

---

**维护者**: AI Novel Analyzer Team  
**反馈渠道**: GitHub Issues  
**许可协议**: MIT

---

*此文档由 Qoder 自动生成，用于指导项目的文档组织结构。*
