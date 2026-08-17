"""Core Chapter Processing Module - Single Chapter Analysis"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import json
import time
from pathlib import Path
import logging

from ..models import NovelChapterInput, ProcessingResult
from .prompt_manager import PromptManager

logger = logging.getLogger(__name__)


@dataclass
class ChapterProcessor:
    """Single chapter analysis processor"""
    
    prompt_manager: PromptManager
    ai_api_client: Optional[Any] = None  # 实际使用时注入 AI API 客户端
    config: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize configuration defaults"""
        self.default_config = {
            "temperature": 0.0,  # Deterministic output
            "max_tokens": 24576,  # Increased from 16384 for large models like DeepSeek-V4
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
        self.config.update(self.default_config)
    
    def process_chapter(
        self, 
        chapter_input: NovelChapterInput,
        previous_context_summary: Optional[str] = None,
        show_stream: bool = True  # Default to streaming
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
            raw_output = self._call_ai_api(
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
            
            result = ProcessingResult(
                chapter_id=chapter_input.chapter_id,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                success=structured_data is not None,
                error_message=None if structured_data else f"Failed after {self.max_chapter_retries} retries",
                structured_data=structured_data,
                original_text=chapter_input.content,
                next_context_summary=brief_summary
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
        
        # Format the prompt - context_summary will be replaced inside HTML tags in template
        replacements = {
            "{context_summary}": context_summary or "",  # Template provides <summary> tags
            "{vol_num}": str(chapter_input.volume_number),
            "{chap_num}": str(chapter_input.chapter_number),
            "{text_content}": chapter_input.content,  # Template provides <chapter_text> tag
        }
        formatted_prompt = base_template
        for placeholder, value in replacements.items():
            formatted_prompt = formatted_prompt.replace(placeholder, value)
        
        return formatted_prompt
        
    def _call_ai_api(
        self, 
        prompt: str,
        chapter_id: str,
        attempt: int = 1,
        stream_callback=None
    ) -> str:
        """Call AI API with retry logic
        
        Args:
            prompt: The complete prompt string
            chapter_id: Chapter identifier for logging
            attempt: Current retry attempt number
            
        Returns:
            Raw string response from AI API
            
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
                    temperature=self.config.get("temperature", 0.0),
                    max_tokens=self.config.get("max_tokens", 8192),
                    timeout=self.config.get("timeout", 120),
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
                
                # Return concatenated result
                return ''.join(collected_chunks)
            else:
                # Non-stream mode (default behavior)
                response = self.ai_api_client.generate(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.config.get("temperature", 0.0),
                    max_tokens=self.config.get("max_tokens", 8192),
                    timeout=self.config.get("timeout", 120),
                    stream=False  # Explicitly disable streaming for non-stream mode
                )
                return response.choices[0].message.content
            
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
                    raw_output = self._call_ai_api(prompt, chapter_input.chapter_id)
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
