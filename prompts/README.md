# AI Novel Analyzer - 项目提示词（Prompt）库

## 📚 目录结构说明

```
prompts/
├── core/                          # 核心处理模块
│   ├── chapter_processor.md       # 单章深度梳理 Prompt（最核心！）
│   ├── context_window_manager.py  # 上下文窗口管理
│   └── batch_processor.md         # 批量处理配置
│
├── tasks/                         # 专项任务模块
│   ├── character_extraction.md    # 人物档案提取
│   ├── event_analysis.md          # 事件分析
│   ├── story_segmenting.md        # 故事片段划分
│   ├── protagonist_growth.md      # 主角成长追踪
│   ├── item_catalog.md            # 物品图鉴维护
│   ├── hidden_info.md             # 隐藏信息识别
│   ├── foreshadowing_tracker.md   # 伏笔标记器
│   ├── thematic_analysis.md       # 主题分析
│   └── continuation_readiness.md  # 续写就绪度生成
│
├── templates/                     # 模板与 Schema
│   ├── output_schema.json         # JSON 输出标准 Schema
│   └── input_template.md          # 输入数据模板
│
└── examples/                      # 示例数据
    ├── sample_output.json         # 完整输出示例
    ├── partial_examples/          # 部分字段示例
    └── common_patterns.md         # 常见模式说明
```

---

## 🎯 核心 Prompt 优先级

### P0: 必须实现（Phase 1 完成）

1. **chapter_processor.md** - 全功能章节处理器
   - 用途：从任意文本片段中提取七维结构化数据
   - 依赖：无（基础 Prompt）
   - 使用场景：逐章处理流程的核心环节

2. **output_schema.json** - 输出格式标准
   - 用途：定义 JSON 输出的数据结构
   - 依赖：无
   - 使用场景：所有 AI 响应的验证基准

### P1: 高度推荐（Phase 1-2 逐步完善）

3. **character_extraction.md** - 人物关系图谱构建
4. **foreshadowing_tracker.md** - 伏笔线索追踪
5. **continuation_readiness.md** - 续写准备包生成

### P2: 扩展功能（Phase 2+ 按需添加）

6. **event_analysis.md** - 重大事件记录
7. **story_segmenting.md** - 场景划分
8. **thematic_analysis.md** - 风格学习

---

## 🔧 Prompt 使用指南

### 方式一：代码集成

```python
from pathlib import Path

class PromptManager:
    """集中管理所有 Prompt 模板"""
    
    PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
    
    @classmethod
    def load(cls, prompt_name: str) -> str:
        """加载 Markdown 格式的 Prompt 模板"""
        path = cls.PROMPTS_DIR / "core" / f"{prompt_name}.md"
        if not path.exists():
            raise FileNotFoundError(f"Prompt not found: {prompt_name}")
        
        content = path.read_text(encoding='utf-8')
        return cls._extract_context_section(content)
    
    @classmethod
    def load_schema(cls, schema_name: str) -> dict:
        """加载 JSON Schema"""
        path = cls.PROMPTS_DIR / "templates" / f"{schema_name}.json"
        import json
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    def _extract_context_section(markdown_content: str) -> str:
        """从 Markdown 文件中提取 Context 部分的正文内容"""
        in_context = False
        context_lines = []
        
        for line in markdown_content.split('\n'):
            if line.startswith('## Context 正文'):
                in_context = True
                continue
            
            if in_context:
                if line.startswith('## ') and line != '## Context 正文':
                    break
                context_lines.append(line)
        
        return '\n'.join(context_lines).strip()
    
    @staticmethod
    def format_prompt(template: str, **kwargs) -> str:
        """格式化 Prompt 模板，替换占位符"""
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing required parameter: {e}")


# 使用示例
def process_chapter(text_content: str, previous_summary: str):
    pm = PromptManager()
    
    # 加载核心 Prompt
    base_prompt = pm.load("chapter_processor")
    
    # 格式化输入
    formatted_prompt = pm.format_prompt(
        base_prompt,
        text_content=text_content,
        context_summary=previous_summary
    )
    
    # 调用 AI API
    response = ai_api.generate(formatted_prompt)
    
    # 验证 JSON 输出
    schema = pm.load_schema("output_schema")
    validate(response, schema)
    
    return response
```

### 方式二：命令行工具

```bash
#!/bin/bash
# scripts/load_prompt.sh

PROMPT_NAME=$1
if [ -z "$PROMPT_NAME" ]; then
    echo "Usage: ./load_prompt.sh <prompt_name>"
    exit 1
fi

python << EOF
from prompts import PromptManager
pm = PromptManager()
content = pm.load("$PROMPT_NAME")
print(content)
EOF
```

```bash
# 测试命令
./scripts/load_prompt.sh chapter_processor
```

### 方式三：直接引用文档

在开发或调试时，可以直接查看 `prompts/core/chapter_processor.md` 文件的原始内容。

---

## ✍️ Prompt 编写规范

每个 Prompt 文件应遵循以下结构：

```markdown
# {Prompt 名称} (英文缩写)

## 用途说明
{一句话描述此 Prompt 的作用和适用场景}

## Input 参数
- `{param1}`: 参数描述 + 预期格式
- `{param2}`: ...

## Output Format
{期望的输出格式说明，如 JSON 数组/对象}

## Context 正文
{这才是实际传递给 AI 的完整 Prompt，包括 Role/Profile/Objective 等}

## Processing Rules
{具体的处理逻辑和约束条件}
- 分类体系
- 判断准则
- 优先级规则

## Special Cases
{特殊情况的处理方法}
- 边缘情况 A 的处理
- 冲突检测策略
- 不确定信息的标注方式
```

---

## 🔍 Prompt 质量检查清单

在将新 Prompt 投入使用前，请确保：

- ✅ 明确定义了 Input 参数的边界
- ✅ 指定了 Output 的精确格式
- ✅ 包含足够的处理规则和示例
- ✅ 覆盖了常见特殊情况的处理
- ✅ 语言简洁无歧义
- ✅ 角色设定清晰且合理

---

## 📝 版本控制

所有 Prompt 文件都应包含版本信息：

```markdown
# Version: 2.0.0
# Created: 2026-08-16
# Last Modified: YYYY-MM-DD
# Author: AI Novels Analyzer Team
```

修改历史记录：

| 版本 | 日期 | 修改内容 | 原因 |
|------|------|---------|------|
| 2.0.0 | 2026-08-16 | 重构为通用版 | 去除《再生勇士》专有名词 |
| 1.3.0 | 2026-08-XX | 优化续写就绪度字段 | 提升续写质量 |

---

## 🤝 协作贡献

### 如何提交新的 Prompt？

1. 新建文件至对应目录（`tasks/` 或 `core/`）
2. 按照上述结构填写内容
3. 添加单元测试示例
4. 更新 `common_patterns.md` 文档
5. 提交 Pull Request

### 如何反馈问题？

如果某个 Prompt 效果不佳：
1. 收集失败案例（Input + 不良 Output）
2. 分析 Prompt 的模糊之处
3. 提出改进建议并附示例
4. 在项目中创建 Issue 讨论

---

## 🌟 最佳实践示例

### 成功的 Prompt 特征

```json
// 好：具体明确
{
  "urgency": "高 | 中 | 低",
  "estimated_timeline": "预计回收时间范围"
}

// 差：模糊不清
{
  "priority": "important",
  "timeline": "soon"
}
```

### Prompt 组合策略

对于复杂任务，可以级联多个 Prompt：

```
[chapter_processor] → 提取七维数据
    ↓
[continuation_readiness] → 生成续写摘要
    ↓
[style_notes] → 提取写作风格特征
    ↓
最终组装成续写准备包
```

---

## 📞 技术支持

如有问题，请参考：
- 主文档：`AI_Novel_Analyzer_Project_Specification_v2.0.md`
- 重构指南：`重构指南.txt`
- 项目 Wiki: [链接待添加]

---

**当前版本**: v2.0  
**最后更新**: 2026-08-16  
**状态**: Phase 1 进行中