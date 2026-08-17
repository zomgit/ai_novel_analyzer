"""Prompt Manager - 从 prompts/ 目录加载 Prompt 模板

Project Structure Overview
===========================
- Core Processing Pipeline (chapter_processor.py)
- Storage Layer Abstraction (storage/)
- Utility Functions (utils/)
- Data Models (models/)
- Command Line Interface (cli/)

Key Features:
- Modular architecture for easy testing
- Progress tracking and logging
- Error handling with retry mechanisms
- Support for both local and cloud embeddings
- Batch processing with parallel execution
- JSON validation before storage
- Automatic context management between chapters

Usage Examples:
==============

1. Process a single chapter:
   python -m ai_novel_analyzer.cli process --chapter vol_1_chap_01.txt

2. Batch process multiple chapters:
   python -m ai_novel_analyzer.cli batch-process \
       --input-dir data/raw/ \
       --output-dir data/processed/ \
       --workers 4 \
       --continue-on-failure

3. Verify all processed files:
   python -m ai_novel_analyzer.cli verify --data-dir data/processed/

"""

from pathlib import Path
from typing import Optional, Dict, Any, List
import json
from dataclasses import dataclass, field

@dataclass
class PromptManager:
    """Centralized Prompt Template Manager"""
    
    # prompts/ 位于项目根目录: src/ai_novel_analyzer/core/ -> 上溯 3 层
    PROMPTS_DIR: Path = field(default_factory=lambda: Path(__file__).resolve().parents[3] / "prompts")
    
    def load(self, prompt_name: str) -> str:
        """Load a Markdown prompt template from file
        
        Args:
            prompt_name: Name of the prompt file (without extension)
            
        Returns:
            String content of the prompt
            
        Raises:
            FileNotFoundError: If the prompt file doesn't exist
        """
        path = self.PROMPTS_DIR / "core" / f"{prompt_name}.md"
        
        if not path.exists():
            raise FileNotFoundError(f"Prompt template not found: {prompt_name}")
        
        content = path.read_text(encoding='utf-8')
        return self._extract_context_section(content)
    
    @staticmethod
    def _extract_context_section(markdown_content: str) -> str:
        """Extract the prompt body starting from the '## Context 正文' marker
        
        模板结构: 头部元信息（用途/参数说明） + '## Context 正文' 标记 + Prompt 主体。
        Prompt 主体内部包含自己的 ## 标题（如 ## Profile），因此提取到文件末尾，
        而非下一个二级标题。
        """
        marker = '## Context 正文'
        
        idx = markdown_content.find(marker)
        if idx == -1:
            # 无标记时整个文件作为 Prompt 主体
            return markdown_content.strip()
        
        body = markdown_content[idx + len(marker):].strip()
        
        # 移除末尾的文档性附录（如有以 '---' 分隔的维护信息）
        return body
    
    @classmethod
    def format_prompt(cls, template: str, **kwargs) -> str:
        """Format a prompt template with provided values
        
        Args:
            template: The prompt template string
            **kwargs: Values to substitute into the template
            
        Returns:
            Formatted prompt string
            
        Raises:
            ValueError: If a required parameter is missing
        """
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing required parameter: {e}") from e
    
    @classmethod
    def validate_json_response(
        cls, 
        response: str, 
        schema_path: Optional[Path] = None,
        strict: bool = True
    ) -> Dict[str, Any]:
        """Validate a JSON response against a schema
        
        Args:
            response: Raw JSON string from AI
            schema_path: Optional path to JSON Schema file
            strict: Whether to enforce strict validation
            
        Returns:
            Parsed and validated JSON object
            
        Raises:
            json.JSONDecodeError: If response is not valid JSON
            ValidationError: If response doesn't match schema (when provided)
        """
        import json
        import jsonschema
        
        try:
            data = json.loads(response)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Invalid JSON response: {response[:200]}...",
                e.doc,
                e.pos
            )
        
        if schema_path and schema_path.exists():
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema = json.load(f)
            
            try:
                jsonschema.validate(instance=data, schema=schema)
            except jsonschema.exceptions.ValidationError as e:
                if strict:
                    raise ValueError(
                        f"JSON validation failed: {e.message}"
                    ) from e
                else:
                    # Log warning but continue
                    pass
        
        return data
    
    @classmethod
    def try_parse_and_fix_json(
        cls, 
        raw_output: str, 
        schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """尝试解析并自动修复常见的 JSON 错误
        
        支持的修复策略（按优先级）：
        1. 直接解析原始输出
        2. 删除 JSON 代码块外的文本
        3. 从第一个 '{' 开始截断到最后一个 '}'
        4. 补充缺失的结尾符号
        5. 提取首个完整合法的 JSON 对象
        6. 逐层补全括号后缀
        
        Args:
            raw_output: AI 返回的原始文本
            schema: 可选的 JSON Schema 用于验证修复结果
            
        Returns:
            解析成功的字典对象
            
        Raises:
            ValueError: 所有修复策略都失败时抛出
        """
        strategies = [
            ("直接解析", lambda: json.loads(raw_output.strip())),
            ("截取代码块", cls._strip_code_block),
            ("截断非 JSON 部分", cls._strip_non_json),
            ("提取完整 JSON", cls._extract_valid_json),
            ("补充结尾符号", cls._fix_missing_end),
            ("增量补全括号", cls._incremental_filling),
        ]
        
        last_error = None
        
        for name, extractor in strategies:
            try:
                candidate = extractor(raw_output)
                data = json.loads(candidate)
                
                # 如果提供了 schema，额外验证
                if schema:
                    import jsonschema
                    jsonschema.validate(data, schema)
                
                logger.debug(f"JSON 修复成功 ({name})")
                return data
                
            except Exception as e:
                last_error = e
                continue
        
        raise ValueError(
            f"JSON 修复失败：已尝试 {len(strategies)} 种策略\n"
            f"最后错误：{str(last_error)[:200]}\n"
            f"原始输出前 500 字符：{raw_output[:500]}..."
        )
    
    @staticmethod
    def _strip_code_block(text: str) -> str:
        """移除 Markdown 代码块标记并提取内容"""
        start = text.find("```json")
        if start == -1:
            start = text.find("```")
        else:
            start += 7  # 跳过 ```json
        
        end = text.rfind("```")
        if end != -1 and end > start:
            return text[start:end].strip()
        
        return text[start:].strip() if start > 0 else text
    
    @staticmethod
    def _strip_non_json(text: str) -> str:
        """删除 JSON 代码块前的描述性文本"""
        start = text.find("{")
        if start == -1:
            raise ValueError("No JSON found")
        
        end = text.rfind("}")
        if end == -1 or end <= start:
            raise ValueError("Unmatched braces")
        
        return text[start:end+1]
    
    @staticmethod
    def _extract_valid_json(text: str) -> str:
        """从文本中提取首个完整的 JSON 对象（处理嵌套结构）"""
        depth = 0
        start = None
        in_string = False
        escape_next = False
        
        for i, c in enumerate(text):
            # 处理字符串内的字符
            if c == '"' and not escape_next:
                in_string = not in_string
            elif c == '\\' and in_string:
                escape_next = True
            else:
                escape_next = False
            
            # 不在字符串内时才计数括号
            if not in_string:
                if c == "{":
                    if start is None:
                        start = i
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0 and start is not None:
                        return text[start:i+1]
        
        raise ValueError(f"未找到完整的 JSON 对象 (深度={depth}, start={start})")
    
    @staticmethod
    def _fix_missing_end(text: str) -> str:
        """检测并补充缺失的大括号/方括号"""
        text = text.strip()
        
        # 统计括号匹配情况
        brace_depth = 0
        bracket_depth = 0
        in_string = False
        escape_next = False
        
        for i, c in enumerate(text):
            if c == '"' and not escape_next:
                in_string = not in_string
            elif c == '\\' and in_string:
                escape_next = True
            elif not in_string:
                escape_next = False
                if c == "{":
                    brace_depth += 1
                elif c == "}":
                    brace_depth -= 1
                elif c == "[":
                    bracket_depth += 1
                elif c == "]":
                    bracket_depth -= 1
        
        # 构建需要补充的后缀
        suffix = "}" * max(0, brace_depth) + "]" * max(0, bracket_depth)
        
        if suffix:
            return text + suffix
        
        return text
    
    @staticmethod
    def _incremental_filling(text: str) -> str:
        """逐步添加可能的结尾组合直到形成合法 JSON"""
        from itertools import product
        
        # 尝试各种组合
        patterns = ["}", "]", "}}", "]} ", "}]", "}}]", "}]}", "]]}"]
        
        for pattern in patterns:
            try:
                candidate = text + pattern
                json.loads(candidate)
                return candidate
            except:
                continue
        
        raise ValueError("无法通过增量补全修复 JSON")
