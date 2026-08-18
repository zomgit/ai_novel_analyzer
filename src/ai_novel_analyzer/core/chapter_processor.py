"""Core Chapter Processing Module - Single Chapter Analysis"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import json
import time
from pathlib import Path
import logging
from datetime import datetime, timezone

from ..models import NovelChapterInput, ProcessingResult
from .prompt_manager import PromptManager
from scripts.split_book import sanitize_dirname

logger = logging.getLogger(__name__)

# Debug dump 目录（懒初始化，仅当 logging.debug_api_dump=true 时生效）
_debug_dump_dir: Optional[Path] = None
_debug_dump_checked: bool = False


@dataclass
class ChapterProcessor:
    """Single chapter analysis processor"""
    
    prompt_manager: PromptManager
    ai_api_client: Optional[Any] = None  # 实际使用时注入 AI API 客户端
    config: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize configuration defaults"""
        # 从 ConfigManager 获取统一的 max_tokens / temperature 等默认值
        # 避免各处硬编码，所有 AI 调用参数统一由 config_manager 管控
        from .config_manager import get_config
        _cfg = get_config()
        
        self.default_config = {
            "temperature": _cfg.temperature,
            "max_tokens": _cfg.max_tokens,
            "timeout": 300,
            "retry_attempts": 5,  # Increased from 3 for unstable APIs
            "strict_validation": True
        }
        # Load chapter-specific retry configuration from processing config
        proc_config = self.config.get("processing", {})
        max_retries = proc_config.get("chapter_retry_attempts", 3)
        # Clamp to range [1, 5]
        self.max_chapter_retries = max(1, min(5, max_retries))
        self.skip_on_max_retries = proc_config.get("skip_chapter_on_max_retries", True)
        # 外部传入的 config 优先，缺项由 ConfigManager 统一值补齐
        merged = {**self.default_config, **self.config}
        self.config = merged
        
        # 初始化 debug dump 目录（懒检查，仅首次调用时生效）
        self._init_debug_dump_dir()
    
    @staticmethod
    def _init_debug_dump_dir():
        """检查配置，若 logging.debug_api_dump=true 则创建 logs/debug/ 目录"""
        global _debug_dump_dir, _debug_dump_checked
        if _debug_dump_checked:
            return
        _debug_dump_checked = True
        try:
            from ai_novel_analyzer.core.config_manager import get_config
            config = get_config()
            if config.get('logging.debug_api_dump', False):
                _debug_dump_dir = config.logs_dir / 'debug'
                _debug_dump_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Debug API dump 已启用，输出目录: {_debug_dump_dir}")
        except Exception:
            pass
    
    @staticmethod
    def _dump_debug_files(chapter_id: str, prompt: str, raw_output: str):
        """将完整的 prompt 和 raw output 写入 logs/debug/ 下的纯文本文件
        
        文件名格式：{chapter_id}_{timestamp}_request.txt / _response.txt
        加入时间戳以避免并发分析时文件名冲突。
        
        Args:
            chapter_id: 章节 ID（如 chap_0012）
            prompt: 发送给 AI 的完整 prompt
            raw_output: AI 返回的原始文本
        """
        if _debug_dump_dir is None:
            return
        try:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            req_path = _debug_dump_dir / f"{chapter_id}_{ts}_request.txt"
            with open(req_path, 'w', encoding='utf-8') as f:
                f.write(prompt)
            
            resp_path = _debug_dump_dir / f"{chapter_id}_{ts}_response.txt"
            with open(resp_path, 'w', encoding='utf-8') as f:
                f.write(raw_output)
            
            logger.debug(f"Debug dump: {chapter_id} request/response → {req_path.parent}")
        except Exception as e:
            logger.warning(f"Failed to write debug dump for {chapter_id}: {e}")
    
    def process_chapter(
        self, 
        chapter_input: NovelChapterInput,
        previous_context_summary: Optional[str] = None,
        show_stream: bool = False  # Default to non-streaming
    ) -> ProcessingResult:
        """Process a single chapter and extract structured information
        
        This is the main entry point for processing one chapter of text.
        
        Args:
            chapter_input: The chapter data to process
            previous_context_summary: Summary of previous N chapters (optional)
            
        Returns:
            ProcessingResult containing the structured analysis
            
        Raises:
            ValueError: If chapter_input is invalid
            RuntimeError: If AI API call fails after all retries
        """
        
        logger.info(f"Processing chapter {chapter_input.chapter_id}")
        start_time = time.time()
        
        try:
            # Step 1: Build the prompt
            prompt = self._build_prompt(chapter_input, previous_context_summary)
            
            # Step 2: Call AI API
            raw_output, token_stats = self._call_ai_api(
                prompt, chapter_input.chapter_id,
                stream_callback=self._stream_print_callback if show_stream else None
            )
            
            # Step 3: Parse and validate JSON (with retry logic)
            structured_data = self._parse_json_response(
                raw_output,
                prompt,
                chapter_input
            )
            
            # Step 4: Create processing result
            brief_summary = None
            if structured_data and 'chapter_summary' in structured_data:
                brief_summary = structured_data['chapter_summary'].get('brief_summary')
            
            # 计算耗时
            elapsed_time = time.time() - start_time
            
            result = ProcessingResult(
                chapter_id=chapter_input.chapter_id,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                success=structured_data is not None,
                error_message=None if structured_data else f"Failed after {self.max_chapter_retries} retries",
                structured_data=structured_data,
                original_text=chapter_input.content,
                next_context_summary=brief_summary,
                processed_at=datetime.now(timezone.utc).isoformat(),
                stats={
                    'elapsed_time': elapsed_time,
                    'tokens': token_stats
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to process chapter {chapter_input.chapter_id}: {str(e)}")
            raise
    
    def _build_prompt(
        self, 
        chapter_input: NovelChapterInput,
        context_summary: Optional[str] = None
    ) -> str:
        """Construct the complete prompt for chapter processing
        
        Args:
            chapter_input: Input chapter data
            context_summary: Previous context summary (optional)
            
        Returns:
            Formatted prompt string ready for AI API
        """
        
        # Load the base template
        base_template = self.prompt_manager.load("chapter_processor")
        
        # ✅ P0-5: 获取前几卷的卷总结（volumes_summary）
        # prev_volumes_summary = self._load_previous_volumes_summary(chapter_input)
        
        # Format the prompt - context_summary will be replaced inside HTML tags in template
        replacements = {
            "{context_summary}": context_summary or "",  # Template provides <summary> tags
            # "{prev_volumes_summary}": prev_volumes_summary or "",  # 新增：前几卷总结
            "{vol_num}": str(chapter_input.volume_number),
            "{chap_num}": str(chapter_input.chapter_number),
            "{text_content}": chapter_input.content,  # Template provides <chapter_text> tag
        }
        formatted_prompt = base_template
        for placeholder, value in replacements.items():
            formatted_prompt = formatted_prompt.replace(placeholder, value)
        
        return formatted_prompt
    
    def _load_previous_volumes_summary(self, chapter_input: NovelChapterInput) -> Optional[str]:
        """加载前几卷的卷总结（volumes_summary）
        
        Args:
            chapter_input: 章节输入数据
            
        Returns:
            前几卷的文本总结，若无则返回 None
        """
        try:
            from pathlib import Path
            import json as json_lib
            
            # 从配置中获取工作区根目录
            config = get_config()
            workspace_root = Path(config.workspace.root if hasattr(config, 'workspace') and isinstance(config.workspace, dict) else 
                                str(PROJECT_ROOT / "workspace") if (PROJECT_ROOT := Path(__file__).parent.parent.resolve().parents[1]).exists() else Path.cwd())
            
            project_name = chapter_input.project_name
            book_name = chapter_input.book_name
            current_vol_num = chapter_input.volume_number
            
            # 查找书籍目录
            projects_dir = config.projects_dir
            book_dir = projects_dir / sanitize_dirname(project_name) / sanitize_dirname(book_name)
            
            if not book_dir.exists():
                return None
            
            prev_summaries = []
            
            # 遍历所有小于当前卷号的卷
            for vol_dir in sorted(book_dir.glob("vol_*")):
                if not vol_dir.is_dir():
                    continue
                
                vol_meta_path = vol_dir / "volume_meta.json"
                if not vol_meta_path.exists():
                    continue
                
                with open(vol_meta_path, "r", encoding="utf-8-sig") as f:
                    vol_meta = json_lib.load(f)
                
                vol_num = vol_meta.get("volume_number", 0)
                if vol_num >= current_vol_num:
                    continue  # 只处理之前的卷
                
                # 检查是否有卷总结
                volumes_summary = vol_meta.get("volumes_summary", {})
                if volumes_summary:
                    summary_text = volumes_summary.get("summary", "")
                    if summary_text:
                        prev_summaries.append(
                            f"【第{vol_num}卷】\n{summary_text}"
                        )
            
            if not prev_summaries:
                return None
            
            return "\n\n".join(prev_summaries)
            
        except Exception as e:
            logger.warning(f"加载前几卷总结失败：{e}")
            return None
        
    def _call_ai_api(
        self, 
        prompt: str,
        chapter_id: str,
        attempt: int = 1,
        stream_callback=None
    ) -> tuple[str, dict]:
        """Call AI API with retry logic
        
        Args:
            prompt: The complete prompt string
            chapter_id: Chapter identifier for logging
            attempt: Current retry attempt number
            
        Returns:
            Tuple of (raw_output: str, token_stats: dict)
            
        Raises:
            RuntimeError: If all retry attempts fail
        """
        
        if self.ai_api_client is None:
            raise RuntimeError("AI API client not configured")
        
        start_time = time.time()  # Track total request time
        
        try:
            if stream_callback:
                # Stream mode: collect chunks
                collected_chunks = []
                first_chunk_time = None  # TTFT tracking
                
                for chunk in self.ai_api_client.generate(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.config["temperature"],
                    max_tokens=self.config["max_tokens"],
                    timeout=self.config["timeout"],
                    stream=True
                ):
                    # Skip empty choices chunks (e.g., final usage-only chunk)
                    if not chunk.choices:
                        continue
                    content = chunk.choices[0].message.content or ''
                    if content:
                        if first_chunk_time is None:
                            first_chunk_time = time.time()
                        collected_chunks.append(content)
                        stream_callback(content)
                    else:
                        logger.debug(f"[stream] Received empty chunk (still processing)")
                
                # Log TTFT and total stream time
                if first_chunk_time is not None:
                    total_time = time.time() - start_time
                    ttft = first_chunk_time - start_time
                    logger.info(f"📊 Stream stats: TTFT={ttft:.3f}s, Total={total_time:.3f}s, Chunks={len(collected_chunks)}")
                
                # Return concatenated result + no token info
                collected_text = ''.join(collected_chunks)
                self._dump_debug_files(chapter_id, prompt, collected_text)
                return collected_text, {}
            else:
                # Non-stream mode (default behavior)
                response = self.ai_api_client.generate(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.config["temperature"],
                    max_tokens=self.config["max_tokens"],
                    timeout=self.config["timeout"],
                    stream=False  # Explicitly disable streaming for non-stream mode
                )
                
                # Extract token usage from response (if available)
                token_stats = {}
                if hasattr(response, 'usage') and response.usage:
                    token_stats = {
                        'prompt_tokens': getattr(response.usage, 'prompt_tokens', 0),
                        'completion_tokens': getattr(response.usage, 'completion_tokens', 0),
                        'total_tokens': getattr(response.usage, 'total_tokens', 0)
                    }
                    logger.debug(
                        f"📊 Token usage: {token_stats['total_tokens']:,} total "
                        f"({token_stats['prompt_tokens']:,} prompt + "
                        f"{token_stats['completion_tokens']:,} completion)"
                    )
                
                raw_content = response.choices[0].message.content
                self._dump_debug_files(chapter_id, prompt, raw_content or '')
                return raw_content, token_stats
            
        except Exception as e:
            if attempt < self.config.get("retry_attempts", 3):
                wait_time = 2 ** (attempt - 1)  # Exponential backoff
                logger.warning(
                    f"Attempt {attempt} failed for {chapter_id}, "
                    f"retrying in {wait_time}s... Error: {str(e)}",
                    exc_info=True
                )
                time.sleep(wait_time)
                return self._call_ai_api(prompt, chapter_id, attempt + 1, stream_callback)
            else:
                raise RuntimeError(
                    f"All {self.config.get('retry_attempts', 3)} "
                    f"attempts failed for chapter {chapter_id}"
                ) from e
    
    def _parse_json_response(
        self, 
        raw_output: str,
        prompt: str,
        chapter_input: NovelChapterInput
    ) -> Dict[str, Any]:
        """Parse and validate JSON response with retry-based recovery on error
        
        Strategy:
        1. Try to parse the JSON (clean markdown blocks first)
        2. If parsing fails, retry AI call up to max_chapter_retries times
        3. On each retry, log attempt number and continue
        4. After max retries, check skip_on_max_retries:
           - If true: log warning and return None (skip this chapter)
           - If false: raise RuntimeError (stop entire batch)
        """
        
        import json
        from ai_novel_analyzer.models import COMPLETE_SCHEMA
        
        # Extract JSON from possible markdown formatting
        cleaned_output = self._clean_json_output(raw_output)
        
        # Try initial parse
        for attempt in range(1, self.max_chapter_retries + 1):
            try:
                schema_path = Path(__file__).parent.parent.parent / \
                    "prompts/templates/output_schema.json"
                
                return self.prompt_manager.validate_json_response(
                    cleaned_output,
                    schema_path,
                    strict=self.config.get("strict_validation", True)
                )
            except (json.JSONDecodeError, ValueError) as e:
                if attempt < self.max_chapter_retries:
                    # JSON failed, trigger retry
                    logger.warning(
                        f"JSON 解析失败 ({str(e)[:80]}), "
                        f"触发重试 ({attempt}/{self.max_chapter_retries})"
                    )
                    # Re-call AI with same prompt
                    raw_output, token_stats = self._call_ai_api(prompt, chapter_input.chapter_id)
                    cleaned_output = self._clean_json_output(raw_output)
                else:
                    # Max retries reached
                    logger.error(
                        f"❌ 重试已达上限 ({self.max_chapter_retries}次), JSON 仍无法解析：{str(e)[:100]}..."
                    )
                    
                    if self.skip_on_max_retries:
                        logger.warning(
                            f"⚠️ 跳过本章处理：{chapter_input.chapter_id}. "
                            f"错误原因：所有 {self.max_chapter_retries} 次尝试均失败"
                        )
                        return None
                    else:
                        raise RuntimeError(
                            f"所有章节重试失败 ({self.max_chapter_retries}次)，停止批量处理。"
                            f"最后错误：{str(e)}"
                        )
    
    @staticmethod
    def _stream_print_callback(content: str):
        """
        Stream callback to print content in real-time.
        Prints without newline, adds newline at end.
        """
        # Simple console streaming - no flushing needed for logger
        import sys
        sys.stdout.write(content)
        sys.stdout.flush()
    
    @staticmethod
    def _clean_json_output(raw_text: str) -> str:
        """Clean raw text output to extract JSON
        
        Removes markdown code blocks and extra whitespace
        
        Args:
            raw_text: Raw output possibly containing markdown formatting
            
        Returns:
            Cleaned JSON string
        """
        import re
        
        # Remove markdown code blocks
        cleaned = re.sub(r'```json\s*|\s*```', '', raw_text)
        
        # Trim whitespace
        cleaned = cleaned.strip()
        
        return cleaned
