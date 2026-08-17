# 维度库聚合工具使用指南

## 概述

本工具用于将批量处理后的单章分析结果（JSON 文件）聚合为各维度的统一索引库。

**独立运行**：不与 batch_processor 流程绑定，可手动触发执行。

**轻量 AI 调用**：仅提取关键字段（人物、地点、物品等元数据）喂给 AI，不传输原始章节文本。

---

## 功能特性

### 1. 六维度聚合

| 维度库 | 文件名 | 聚合策略 |
|--------|-------|---------|
| **人物库** | `character_library.json` | 按 name 去重，合并属性/身份变化历史，累积关系网络 |
| **地点档案** | `location_atlas.json` | 按 name 去重，累积访问记录和事件列表 |
| **物品图鉴** | `item_catalog.json` | 按 name 去重，追踪生命周期（获得→强化→损失） |
| **世界事件时间线** | `world_event_timeline.json` | 按章节顺序串联所有世界事件 |
| **伏笔库** | `foreshadowing_library.json` | 汇总所有章节的 clues，按优先级排序 |
| **剧情秘密库** | `plot_secrets_library.json` | 汇总 twists 和 revelations |

### 2. AI 辅助压缩（可选）

当单个人物的行动摘要超过 500 字时，自动调用 AI 压缩为 200 字以内的精炼版本。

**关闭方式**：`--no-ai-compression` 参数

---

## 使用方法

### 前置条件

确保已运行批量处理，生成 `output/processed/*.json` 文件。

### 基本用法

```bash
# 默认配置（启用 AI 压缩）
uv run python scripts\aggregate_dimensions.py

# 指定输入输出目录
uv run python scripts\aggregate_dimensions.py ^
    --input-dir output/processed/ ^
    --output-dir output/index/

# 禁用 AI 压缩（快速模式）
uv run python scripts\aggregate_dimensions.py ^
    --no-ai-compression

# 调整并行线程数
uv run python scripts\aggregate_dimensions.py ^
    --workers 8
```

### PowerShell 用户注意

PowerShell 中换行需使用 `^`，或使用单行命令：

```powershell
uv run python scripts\aggregate_dimensions.py --input-dir output/processed/ --output-dir output/index/ --no-ai-compression
```

---

## 输出结构

### 维度库示例

**character_library.json**
```json
{
  "version": "1.0",
  "generated_at": "2026-08-16 12:00:00",
  "character_count": 5,
  "characters": [
    {
      "name": "与天争锋",
      "first_appearance": "vol_1_chap_1",
      "last_update": "vol_1_chap_10",
      "attributes_history": [...],
      "identity_history": [...],
      "relationships_snapshot": [...],
      "actions_summary": "..."
    }
  ]
}
```

**location_atlas.json**
```json
{
  "locations": [
    {
      "name": "圣殿",
      "type": "其他",
      "description": "...",
      "first_appearance": "vol_1_chap_1",
      "events": [...],
      "visits": [
        {"chapter": "vol_1_chap_1", "characters": ["与天争锋"]},
        {"chapter": "vol_1_chap_5", "characters": ["与天争锋", "白衣天使"]}
      ]
    }
  ]
}
```

---

## 工作流程

### 典型场景

```bash
# Step 1: 批量处理所有章节
uv run python scripts\batch_processor.py \
    --input-dir data/raw/ \
    --output-dir output/processed/ \
    --workers 8

# Step 2: 等待处理完成（手动或自动脚本触发）
# ... 可能需要数十分钟至数小时，取决于章节数量 ...

# Step 3: 单独调用聚合（可选，按需执行）
uv run python scripts\aggregate_dimensions.py
```

### 增量聚合优势

- ✅ 不阻塞批量处理流程
- ✅ 可在处理后任意时间触发
- ✅ 支持多次执行（每次重新聚合最新状态）
- ✅ 便于调试（检查中间状态）

---

## 故障排查

### 问题 1：找不到输入目录

**错误信息**：`❌ 输入目录不存在：xxx`

**解决方案**：
- 确认批量处理已生成 JSON 文件
- 检查路径是否正确（区分大小写）

### 问题 2：AI 压缩失败

**错误信息**：`AI 压缩 xx 失败：未找到 API_KEY`

**解决方案**：
- 确保 `.env` 文件中设置了 `AI_MODEL_API_KEY`
- 或使用 `--no-ai-compression` 跳过 AI 步骤

### 问题 3：维度库文件为空

**可能原因**：
- 输入 JSON 中没有对应维度数据
- Schema 字段名不匹配（请检查是否运行了最新代码）

---

## 扩展开发

如需增加新维度，在 `DimensionAggregator` 类中添加 `_aggregate_xxx()` 方法，并在 `aggregate_all()` 中注册即可。

**示例**：添加"成长轨迹库"

```python
def _aggregate_growth(self) -> Dict[str, Any]:
    growth_data = []
    for file_path in self.processed_files:
        with open(file_path, 'r') as f:
            data = json.load(f)
        growth = data.get('growth', {})
        if growth:
            growth['_source_chapter'] = file_path.stem
            growth_data.append(growth)
    return {'growth_records': growth_data}
```

---

## 注意事项

1. **不要删除** `output/processed/*.json`，聚合依赖这些源文件。
2. 聚合后的维度库建议定期备份到 Git 或版本控制系统。
3. AI 压缩会额外消耗 token，大量人物时可能较慢（通常 < 5 分钟）。
4. 首次运行聚合前，建议先检查 `output/processed/` 中是否有足够多的章节 JSON。
