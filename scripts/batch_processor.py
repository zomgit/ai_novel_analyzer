#!/usr/bin/env python3
"""
Automated Batch Processing Script for Novel Analysis (Workspace 结构版)

对指定卷目录（split_book.py 产出）内未处理的章节执行 AI 分析：
- 血缘信息（项目/书名/卷名）从卷目录的 volume_meta.json 自动读取
- 幂等：已有配对 chap_XXXX.json 且 status=processed 的章节自动跳过
- 失败章节（status=failed）会自动重试
- 严格串行：处理完一章 → JSON 即时落盘 → 再处理下一章（保证上下文链正确）
- 批末统一回写 volume_meta.json 的章节状态

Usage:
    uv run python scripts/batch_processor.py \
        workspace/projects/项目/书名/vol_001_卷名 \
        [--continue-on-failure] [--stream]

Environment Variables:
    SILICONFLOW_API_KEY: API key for embedding service (alternative to --api-key)
    AI_MODEL_API_KEY: API key for AI model generation
"""

import sys
import time
import json
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone
import argparse
import os
import re
import yaml

# Windows GBK 控制台兼容：避免 emoji/特殊字符输出时报错
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# 统一使用 ConfigManager
from ai_novel_analyzer.core.config_manager import get_config
from ai_novel_analyzer.core.logging_config import setup_logging, get_logger
from ai_novel_analyzer.models import (
    NovelChapterInput,
    ProcessingResult,
    BatchProcessingConfig,
    ProcessingStats,
)
from ai_novel_analyzer.core.chapter_processor import ChapterProcessor
from ai_novel_analyzer.core.prompt_manager import PromptManager
from ai_novel_analyzer.storage import StorageManager
from ai_novel_analyzer.utils.ai_api_client import get_ai_client_from_config

# 全局日志记录器
logger = get_logger(__name__)

# 配置管理器和日志初始化
config = get_config()
setup_logging()


class AutomatedBatchProcessor:
    """Complete automated batch processor for novel chapters"""
    
    def __init__(self, config: BatchProcessingConfig):
        """Initialize the batch processor
        
        Args:
            config: Processing configuration（必须含 volume_dir）
        """
        self.config = config
        self.stats = ProcessingStats()
        
        # Setup logging first (其他组件初始化依赖 self.logger)
        self._setup_logging()
        
        if not config.volume_dir:
            raise ValueError(
                "缺少必需参数 volume_dir：请传入卷目录路径（split_book.py 产出）"
            )
        self.volume_dir = Path(config.volume_dir)
        self.volume_meta = None          # run_batch 时从 volume_meta.json 读取
        self._identities = {}            # chapter_id → 血缘信息
        self._meta_chapters = {}         # 章节号 → volume_meta 章节记录
        
        # Initialize components
        self.prompt_manager = PromptManager()
        self.ai_api_client = self._create_ai_client()
        self.storage_manager = StorageManager(
            data_dir=self.volume_dir,
            vector_db_path=Path(config.vector_db_path) if config.vector_db_path else None,
            use_cloud_embeddings=config.use_cloud_embeddings,
            embedding_api_key=config.embedding_api_key
        )
        
        self.logger.info(f"AutomatedBatchProcessor initialized for {self.volume_dir}")
    
    def _setup_logging(self):
        """Setup logging configuration"""
        
        log_file = "batch_processing.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
    
    def _create_ai_client(self):
        """创建 AI API 客户端
        
        配置优先级: --config-file 指定的 YAML > 环境变量(.env)
        """
        # 优先使用配置文件（--config-file）
        if getattr(self.config, 'config_file', None) and Path(self.config.config_file).exists():
            with open(self.config.config_file, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f) or {}
            yaml_config = self._expand_env_vars(yaml_config)
            client = get_ai_client_from_config(yaml_config)
            self.logger.info(f"AI 客户端已从配置文件创建: {self.config.config_file}")
            return client
        
        # 回退: 从环境变量构建（quick_setup.py 生成的 .env）
        api_key = os.getenv('AI_MODEL_API_KEY', '').strip()
        if not api_key:
            self.logger.error(
                "未配置 AI_MODEL_API_KEY。请先运行配置向导: "
                "uv run python scripts\\quick_setup.py，或在 .env 中填入 API Key"
            )
            sys.exit(1)
        
        base_url = os.getenv('AI_MODEL_BASE_URL', 'https://api.siliconflow.cn/v1').strip()
        model = os.getenv('AI_MODEL_NAME', 'Qwen/Qwen2.5-72B-Instruct').strip()
        
        client = get_ai_client_from_config({
            'ai_model': {
                'type': 'openai_compatible',
                'params': {
                    'api_key': api_key,
                    'base_url': base_url,
                    'model': model,
                },
            }
        })
        self.logger.info(f"AI 客户端已从环境变量创建: {base_url} / {model}")
        return client
    
    @staticmethod
    def _expand_env_vars(obj):
        """递归展开配置中的 ${VAR} 环境变量占位符"""
        if isinstance(obj, str):
            return re.sub(
                r'\$\{(\w+)\}',
                lambda m: os.getenv(m.group(1), ''),
                obj
            )
        if isinstance(obj, dict):
            return {k: AutomatedBatchProcessor._expand_env_vars(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [AutomatedBatchProcessor._expand_env_vars(v) for v in obj]
        return obj
    
    def run_batch(self, enable_stream: bool = False) -> bool:
        """Run batch processing on all pending chapters in the volume dir
        
        幂等：已有配对 chap_XXXX.json 且 status=processed 的章节自动跳过；
        status=failed 的章节会自动重试。
            
        Returns:
            True if all processing completed successfully
        """
        
        self.logger.info(f"Starting batch processing for volume dir {self.volume_dir}")
        self.stats.start_time = time.time()
        
        # 读取卷元数据（血缘信息来自元数据，而非命令行参数）
        self.volume_meta = self._load_volume_meta()
        
        # Discover chapter files（仅 chap_XXXX.txt，按章节号排序）
        chapter_files = []
        for p in self.volume_dir.glob("chap_*.txt"):
            m = re.match(r'^chap_(\d{4})$', p.stem)
            if m:
                chapter_files.append(p)
            else:
                self.logger.warning(f"文件名不符合 chap_XXXX.txt 规范，跳过: {p.name}")
        
        if not chapter_files:
            self.logger.error(f"No chap_*.txt files found in {self.volume_dir}")
            return False
        
        chapter_files.sort(key=lambda p: int(p.stem.split('_')[1]))
        
        # 幂等跳过：配对 json 存在且 status=processed → 已处理
        pending_files = []
        skipped = 0
        for txt_path in chapter_files:
            json_path = txt_path.with_suffix('.json')
            if json_path.exists():
                try:
                    with open(json_path, 'r', encoding='utf-8-sig') as f:
                        existing = json.load(f)
                    if existing.get('status') == 'processed':
                        skipped += 1
                        continue
                except Exception:
                    pass  # 损坏的 json 视为未处理，重新分析
            pending_files.append(txt_path)
        
        self.stats.skipped = skipped
        if skipped:
            self.logger.info(f"Skipped {skipped} already-processed chapters")
        
        if not pending_files:
            self.logger.info("All chapters already processed, nothing to do")
            return True
        
        self.stats.total_chapters = len(chapter_files)
        self.logger.info(f"Found {len(pending_files)} pending chapters to process")
        
        # 建立章节号 → volume_meta 章节记录的映射（用于状态回写）
        self._meta_chapters = {
            c['number']: c for c in self.volume_meta.get('chapters', [])
        }
        
        # Process chapters serially（严格串行：处理完一章 → 即时落盘 → 再处理下一章）
        processed_count = 0
        failed_count = 0
                
        # 串行上下文链：只保留上一章的 brief_summary（避免累积全部结果导致内存泄漏）
        # 若前面有已处理章节，从最后已处理章节的 JSON 中恢复上下文摘要，避免上下文链断裂
        prev_summary = self._load_last_processed_summary(chapter_files, pending_files)
                
        for file_path in pending_files:
            try:
                chapter_input = self._load_chapter_from_file(file_path)
                        
                if chapter_input is None:
                    self.logger.warning(f"Skipping invalid file: {file_path}")
                    continue
                        
                # 串行处理：传入上一章的 brief_summary 作为上下文
                result = self._process_single_chapter(
                    chapter_input,
                    prev_summary,
                    enable_stream
                )
                        
                if result.success and result.has_data:
                    processed_count += 1
                            
                    # 即时落盘（处理完一章立即写 JSON，再处理下一章）
                    self._save_result(result)
                    self._update_chapter_status(result.chapter_id, 'processed')
                            
                    # ✅ 输出 token 与耗时统计
                    token_info = ""
                    elapsed_info = ""
                    if hasattr(result, 'stats') and result.stats:
                        tokens = result.stats.get('tokens', {})
                        total_tokens = tokens.get('total_tokens', 0)
                        prompt_tokens = tokens.get('prompt_tokens', 0)
                        completion_tokens = tokens.get('completion_tokens', 0)
                        token_info = f"{total_tokens:,} tokens ({prompt_tokens} p + {completion_tokens} c)"
                                
                        elapsed = result.stats.get('elapsed_time', 0)
                        elapsed_info = f"{elapsed:.2f}s"
                            
                    self.logger.info(
                        f"✅ [{chapter_input.book_name}] {chapter_input.volume_title} | "
                        f"{chapter_input.chapter_title} ({result.chapter_id}): Success"
                        + (f" | {token_info}" if token_info else "")
                        + (f" | {elapsed_info}" if elapsed_info else "")
                    )
                            
                else:
                    failed_count += 1
                    self._update_chapter_status(
                        result.chapter_id, 'failed', result.error_message
                    )
                    if result.error_message:
                        self.logger.error(
                            f"Processing failed for {file_path}: "
                            f"{result.error_message}"
                        )
                        
                # 更新上下文链：提取本章 brief_summary 供下一章使用
                if result.success and result.structured_data:
                    prev_summary = result.structured_data.get(
                        'chapter_summary', {}
                    ).get('brief_summary')
                else:
                    prev_summary = None
                        
                # 释放原文引用，避免内存累积（JSON 已落盘，原文不再需要）
                result.original_text = None
                        
            except Exception as e:
                self.logger.error(f"Exception processing {file_path}: {str(e)}")
                if self.config.continue_on_error:
                    failed_count += 1
                    prev_summary = None  # 本章异常，下一章无上下文
                else:
                    raise
        
        # 批末统一回写卷元数据（章节状态）
        self._save_volume_meta()
        
        self.stats.end_time = time.time()
        self.stats.processed_successfully = processed_count
        self.stats.failed = failed_count
        
        self._log_final_stats()
        
        return failed_count == 0
    
    def _load_volume_meta(self) -> dict:
        """读取卷元数据（血缘信息的唯一来源）"""
        meta_path = self.volume_dir / "volume_meta.json"
        if not meta_path.exists():
            self.logger.error(
                f"不是 split_book.py 产出的卷目录（缺少 volume_meta.json）：{self.volume_dir}\n"
                f"    请先运行 scripts/split_book.py 拆书"
            )
            sys.exit(1)
        with open(meta_path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    
    def _load_last_processed_summary(
        self,
        chapter_files: List[Path],
        pending_files: List[Path]
    ) -> Optional[str]:
        """从最后一个已处理章节的 JSON 中加载 brief_summary，恢复上下文链。
        
        在断点续跑场景下，前 n 章已处理、第 n+1 章开始进入 pending_files，
        此时需要读取第 n 章的 chapter_summary.brief_summary 作为 prev_summary，
        确保上下文链不断裂。
        
        Args:
            chapter_files: 所有章节文件（已排序）
            pending_files: 待处理章节文件（已排序）
            
        Returns:
            brief_summary 字符串，或 None（无法获取时静默降级）
        """
        # 边界：没有待处理章节，或第一个待处理章节就是第一章 → 无前置摘要
        if not pending_files or pending_files[0] == chapter_files[0]:
            return None
        
        # 找到 pending_files[0] 在 chapter_files 中的位置，取前一章
        try:
            idx = chapter_files.index(pending_files[0])
        except ValueError:
            return None
        
        if idx == 0:
            return None
        
        prev_txt = chapter_files[idx - 1]
        prev_json = prev_txt.with_suffix('.json')
        
        if not prev_json.exists():
            self.logger.debug(
                f"前一章节 JSON 不存在，无法恢复上下文摘要: {prev_json.name}"
            )
            return None
        
        try:
            with open(prev_json, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            summary = (
                data.get('chapter_summary', {})
                .get('brief_summary')
            )
            if summary:
                self.logger.info(
                    f"已从 {prev_json.name} 恢复上下文摘要 "
                    f"({len(summary)} chars)"
                )
            else:
                self.logger.debug(
                    f"{prev_json.name} 中无 brief_summary 字段"
                )
            return summary
        except Exception as e:
            # 读取失败不应中断批量流程，静默降级
            self.logger.warning(
                f"读取 {prev_json.name} 的摘要失败，上下文链将从 None 开始: {e}"
            )
            return None
    
    def _save_volume_meta(self) -> None:
        """回写卷元数据（章节状态）"""
        self.volume_meta['updated_at'] = datetime.now(timezone.utc).isoformat()
        meta_path = self.volume_dir / "volume_meta.json"
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(self.volume_meta, f, ensure_ascii=False, indent=2)
    
    def _update_chapter_status(
        self,
        chapter_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """更新 volume_meta 中对应章节的状态（内存中，批末统一写盘）"""
        m = re.match(r'^chap_(\d{4})$', chapter_id)
        if not m:
            return
        record = self._meta_chapters.get(int(m.group(1)))
        if record is None:
            return
        record['status'] = status
        if status == 'failed' and error_message:
            record['error'] = error_message
        elif 'error' in record:
            del record['error']
    
    def _load_chapter_from_file(self, file_path: Path) -> Optional[NovelChapterInput]:
        """Load chapter data from file（血缘信息取自卷元数据）
        
        Args:
            file_path: Path to chapter file (chap_XXXX.txt)
            
        Returns:
            NovelChapterInput object or None if loading fails
        """
        
        try:
            content = file_path.read_text(encoding='utf-8')
            
            m = re.match(r'^chap_(\d{4})$', file_path.stem)
            if not m:
                self.logger.warning(f"文件名不符合 chap_XXXX.txt 规范，跳过: {file_path.name}")
                return None
            chapter_number = int(m.group(1))
            
            # Use title line from content
            title = content.split('\n')[0] if content else "Untitled"
            
            # 记录血缘信息（保存时注入章节 JSON）
            self._identities[file_path.stem] = {
                'project_name': self.volume_meta.get('project_name'),
                'book_name': self.volume_meta.get('book_name'),
                'volume_number': self.volume_meta.get('volume_number'),
                'volume_title': self.volume_meta.get('volume_title'),
                'chapter_number': chapter_number,
                'chapter_title': title,
                'source_file': file_path.name,
            }
            
            return NovelChapterInput(
                chapter_id=file_path.stem,
                chapter_title=title,
                content=content,
                volume_number=self.volume_meta.get('volume_number', 1),
                chapter_number=chapter_number,
                project_name=self.volume_meta.get('project_name'),
                book_name=self.volume_meta.get('book_name'),
                volume_title=self.volume_meta.get('volume_title')
            )
            
        except Exception as e:
            self.logger.error(f"Failed to load {file_path}: {str(e)}")
            return None
    
    def _process_single_chapter(
        self, 
        chapter_input: NovelChapterInput,
        prev_summary: Optional[str] = None,
        enable_stream: bool = False  # Enable streaming output
    ) -> ProcessingResult:
        """Process a single chapter with context chaining
        
        Args:
            chapter_input: Input chapter data
            prev_summary: Previous chapter's brief_summary (直接传字符串)
            
        Returns:
            ProcessingResult with analysis output
        """
        
        if prev_summary:
            self.logger.debug(
                f"Chapter {chapter_input.chapter_id}: Using previous summary "
                f"({len(prev_summary)} chars)"
            )
        
        # Create chapter processor
        processor = ChapterProcessor(
            prompt_manager=self.prompt_manager,
            ai_api_client=self.ai_api_client
        )
        
        # Process chapter with context summary
        result = processor.process_chapter(
            chapter_input,
            previous_context_summary=prev_summary,
            show_stream=enable_stream
        )
        
        return result
    
    def _save_result(self, result: ProcessingResult) -> None:
        """Save processing result to storage
        
        Args:
            result: Processing result to save
        """
        
        if not result.success:
            return
        
        # ✅ 使用当前 AI 输出的 v3.0 schema 字段名
        # 注意：不存储 original_text 到 JSON，减少文件体积（原文已在 novel_raw/ 中）
        storage_data = {
            'metadata': result.structured_data.get('metadata', {}),
            'world_events': result.structured_data.get('world_events', []),
            'locations': result.structured_data.get('locations', []),
            'characters': result.structured_data.get('characters', []),
            'scenes': result.structured_data.get('scenes', []),
            'growth': result.structured_data.get('growth', {}),
            'items': result.structured_data.get('items', []),
            'plot_secrets': result.structured_data.get('plot_secrets', {}),
            'chapter_summary': result.structured_data.get('chapter_summary', {})
        }
        
        # Save using storage manager（附带血缘信息）
        self.storage_manager.save_chapter_result(
            chapter_id=result.chapter_id,
            result_data=storage_data,
            identity=self._identities.get(result.chapter_id)
        )
        
        self.logger.debug(f"Saved result for {result.chapter_id}")
    
    def _log_final_stats(self):
        """Log final processing statistics"""
        
        elapsed = self.stats.elapsed_time
        success_rate = self.stats.success_rate
        
        self.logger.info("=" * 50)
        self.logger.info("BATCH PROCESSING COMPLETED")
        self.logger.info("=" * 50)
        self.logger.info(f"Total chapters:     {self.stats.total_chapters}")
        self.logger.info(f"Successful:         {self.stats.processed_successfully}")
        self.logger.info(f"Failed:             {self.stats.failed}")
        self.logger.info(f"Success rate:       {success_rate:.2f}%")
        self.logger.info(f"Elapsed time:       {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")
        self.logger.info("=" * 50)


def parse_arguments():
    """Parse command line arguments"""
    
    parser = argparse.ArgumentParser(
        description="批量分析器：处理指定卷目录内未处理的章节（幂等，可断点续跑）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python scripts/batch_processor.py \\
      workspace/projects/我的项目/书名/vol_001_第一册

  uv run python scripts/batch_processor.py \\
      workspace/projects/我的项目/书名/vol_001_第一册 \\
      --workers 2 --continue-on-failure

  # 默认行为：实时显示每章的 token 消耗与耗时（不可关闭）
        """
    )
    
    parser.add_argument(
        'volume_dir',
        type=str,
        help='卷目录路径（split_book.py 产出，含 volume_meta.json）'
    )
    
    parser.add_argument(
        '--vector-db-path',
        type=str,
        default=None,
        help='Path to ChromaDB storage directory（缺省使用 workspace/db/chromadb）'
    )
    
    parser.add_argument(
        '--no-vector-db',
        action='store_true',
        help='禁用向量库写入'
    )
    
    parser.add_argument(
        '--workers',
        type=int,
        default=1,
        help='[已废弃] 批处理已改为严格串行，此参数不再生效（保留仅为向后兼容）'
    )
    
    parser.add_argument(
        '--continue-on-failure',
        action='store_true',
        help='Continue processing even if some chapters fail'
    )
    
    parser.add_argument(
        '--api-key',
        type=str,
        default=None,
        help='API key for cloud embedding service'
    )
    
    parser.add_argument(
        '--config-file',
        type=str,
        default=None,
        help='Path to YAML configuration file (e.g., config/production.yaml). '
             '优先级高于 .env 环境变量'
    )
    
    return parser.parse_args()


def main():
    """Main entry point"""
    
    args = parse_arguments()
    
    volume_dir = Path(args.volume_dir)
    if not volume_dir.exists():
        print(f"Error: 卷目录不存在：{volume_dir}")
        sys.exit(1)
    if not (volume_dir / "volume_meta.json").exists():
        print(
            f"Error: 不是 split_book.py 产出的卷目录（缺少 volume_meta.json）：{volume_dir}\n"
            f"       请先运行 scripts/split_book.py 拆书"
        )
        sys.exit(1)
    
    # 向量库路径：缺省使用 workspace/db/chromadb（可 --no-vector-db 禁用）
    if args.no_vector_db:
        vector_db_path = None
    elif args.vector_db_path:
        vector_db_path = args.vector_db_path
    else:
        vector_db_path = str(get_config().chromadb_path)
    
    # Load config from file if provided
    config_dict = {}
    if args.config_file and Path(args.config_file).exists():
        with open(args.config_file, 'r', encoding='utf-8') as f:
            config_dict = yaml.safe_load(f)
    
    # Override with command line args
    config_dict.update({
        'max_workers': args.workers,
        'continue_on_error': args.continue_on_failure,
        'volume_dir': str(volume_dir),
        'vector_db_path': vector_db_path,
        'embedding_api_key': args.api_key or os.getenv('SILICONFLOW_API_KEY') or config_dict.get('embedding_api_key'),
        'config_file': args.config_file
    })
    
    # Set defaults
    config_dict.setdefault('use_cloud_embeddings', True)
    config_dict.setdefault('retry_on_failure', True)
    config_dict.setdefault('save_intermediate', True)
    
    # Create config object
    config = BatchProcessingConfig(**config_dict)
    
    # Run batch processing（始终显示统计信息，不使用流式输出）
    processor = AutomatedBatchProcessor(config)
    success = processor.run_batch(enable_stream=False)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()


