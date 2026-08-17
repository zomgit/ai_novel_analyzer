#!/usr/bin/env python3
"""
Automated Batch Processing Script for Novel Analysis

This script provides a complete automated workflow for processing all chapters
of a novel from raw text files through structured analysis to vector storage.

Usage:
    python -m ai_novel_analyzer.batch_processor \\
        --input-dir data/raw/ \\
        --output-dir data/processed/ \\
        --vector-db-path db/local_vector_store/ \\
        --workers 4 \\
        [--continue-on-failure] \\
        [--api-key YOUR_API_KEY]

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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import argparse
import os
import re

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
from ai_novel_analyzer.core.chapter_processor import ChapterProcessor
from ai_novel_analyzer.core.prompt_manager import PromptManager
from ai_novel_analyzer.storage import StorageManager
from ai_novel_analyzer.utils.ai_api_client import get_ai_client_from_config


class AutomatedBatchProcessor:
    """Complete automated batch processor for novel chapters"""
    
    def __init__(self, config: BatchProcessingConfig):
        """Initialize the batch processor
        
        Args:
            config: Processing configuration
        """
        self.config = config
        self.stats = ProcessingStats()
        
        # Setup logging first (其他组件初始化依赖 self.logger)
        self._setup_logging()
        
        # Initialize components
        self.prompt_manager = PromptManager()
        self.ai_api_client = self._create_ai_client()
        self.storage_manager = StorageManager(
            data_dir=Path(config.output_dir),
            vector_db_path=Path(config.vector_db_path) if config.vector_db_path else None,
            use_cloud_embeddings=config.use_cloud_embeddings,
            embedding_api_key=config.embedding_api_key
        )
        
        self.logger.info("AutomatedBatchProcessor initialized")
    
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
    
    def run_batch(
        self, 
        input_dir: Path,
        chapter_files: Optional[List[Path]] = None
    ) -> bool:
        """Run batch processing on all chapters
        
        Args:
            input_dir: Directory containing raw chapter files
            chapter_files: Specific files to process (None for all)
            
        Returns:
            True if all processing completed successfully
        """
        
        self.logger.info(f"Starting batch processing from {input_dir}")
        self.stats.start_time = time.time()
        
        # Discover chapter files
        if chapter_files is None:
            chapter_files = list(input_dir.glob("*.txt")) + \
                          list(input_dir.glob("*.md"))
        
        if not chapter_files:
            self.logger.error(f"No text files found in {input_dir}")
            return False
        
        # 按解析出的章节号排序，保证处理顺序与章节顺序一致（解析失败的排最后）
        def _sort_key(p: Path):
            vol, chap = self._parse_chapter_numbers(p)
            return (vol, chap if chap is not None else float('inf'))
        
        chapter_files.sort(key=_sort_key)
        
        self.stats.total_chapters = len(chapter_files)
        self.logger.info(f"Found {len(chapter_files)} chapters to process")
        
        # Process chapters with parallelization
        processed_count = 0
        failed_count = 0
        
        # Store results in order for context chaining
        self.results = []
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = {}
            
            for file_path in chapter_files:
                try:
                    chapter_input = self._load_chapter_from_file(file_path)
                    
                    if chapter_input is None:
                        self.logger.warning(f"Skipping invalid file: {file_path}")
                        continue
                    
                    future = executor.submit(
                        self._process_single_chapter,
                        chapter_input,
                        processed_count  # Pass previous summary index
                    )
                    futures[future] = file_path
                    
                except Exception as e:
                    self.logger.error(f"Failed to load {file_path}: {str(e)}")
                    failed_count += 1
            
            # Track progress
            for future in as_completed(futures):
                file_path = futures[future]
                
                try:
                    result = future.result()
                    
                    if result.success and result.has_data:
                        processed_count += 1
                        
                        # Save results
                        self._save_result(result)
                        
                        # Add to results list for context chaining (maintain order)
                        self.results.append(result)
                        
                        self.logger.info(
                            f"Chapter {result.chapter_id}: Processed successfully "
                            f"({len(result.structured_data.get('chapter_summary', {}).get('brief_summary', ''))} chars summary)"
                        )
                        
                    else:
                        failed_count += 1
                        if result.error_message:
                            self.logger.error(
                                f"Processing failed for {file_path}: "
                                f"{result.error_message}"
                            )
                        
                        # Add failed result to maintain order
                        self.results.append(result)
                
                except Exception as e:
                    self.logger.error(f"Exception processing {file_path}: {str(e)}")
                    if self.config.continue_on_error:
                        failed_count += 1
                    else:
                        raise
        
        self.stats.end_time = time.time()
        self.stats.processed_successfully = processed_count
        self.stats.failed = failed_count
        
        self._log_final_stats()
        
        return failed_count == 0
    
    def _load_chapter_from_file(self, file_path: Path) -> Optional[NovelChapterInput]:
        """Load chapter data from file
        
        Args:
            file_path: Path to chapter file
            
        Returns:
            NovelChapterInput object or None if loading fails
        """
        
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Extract metadata from filename
            volume_num, chap_num = self._parse_chapter_numbers(file_path)
            
            if chap_num is None:
                self.logger.warning(
                    f"无法从文件名解析章节编号，跳过: {file_path.name}\n"
                    f"    支持的命名: vol_1_chap_01.txt 或 chapter_0001_标题.txt"
                )
                return None
            
            # Use title line from content
            title = content.split('\n')[0] if content else "Untitled"
            
            return NovelChapterInput(
                chapter_id=f"vol_{volume_num}_chap_{chap_num}",
                chapter_title=title,
                content=content,
                volume_number=volume_num,
                chapter_number=chap_num
            )
            
        except Exception as e:
            self.logger.error(f"Failed to load {file_path}: {str(e)}")
            return None
    
    @staticmethod
    def _parse_chapter_numbers(file_path: Path):
        """从文件名解析卷号与章节号，兼容两种命名格式
        
        支持:
            vol_1_chap_01.txt            -> (1, 1)
            chapter_0001_标题.txt         -> (1, 1)   # split_novel.py 输出
            01.txt / 01_标题.txt          -> (1, 1)   # 纯数字前缀
            
        Returns:
            (volume_num, chap_num)，解析失败时 chap_num 为 None
        """
        filename = file_path.stem
        
        # 格式 1: vol_X_chap_Y
        m = re.match(r'^vol_(\d+)_chap_(\d+)', filename)
        if m:
            return int(m.group(1)), int(m.group(2))
        
        # 格式 2: chapter_XXXX[_标题]（split_novel.py 输出）
        m = re.match(r'^chapter_(\d+)', filename)
        if m:
            return 1, int(m.group(1))
        
        # 格式 3: 纯数字开头，如 01.txt / 01_标题.txt
        m = re.match(r'^(\d+)', filename)
        if m:
            return 1, int(m.group(1))
        
        return 1, None
    
    def _process_single_chapter(
        self, 
        chapter_input: NovelChapterInput,
        prev_summary_index: int
    ) -> ProcessingResult:
        """Process a single chapter with context chaining
        
        Args:
            chapter_input: Input chapter data
            prev_summary_index: Index of previous summary (for context chaining)
            
        Returns:
            ProcessingResult with analysis output
        """
        
        # Retrieve previous chapter's brief summary for context
        previous_summary = None
        if prev_summary_index >= 0 and prev_summary_index < len(self.results):
            prev_result = self.results[prev_summary_index]
            if prev_result.success and prev_result.structured_data:
                # Extract brief_summary from previous chapter's structured data
                previous_summary = prev_result.structured_data.get('chapter_summary', {}).get('brief_summary')
                
                if previous_summary:
                    self.logger.debug(
                        f"Chapter {chapter_input.chapter_id}: Using previous summary "
                        f"({len(previous_summary)} chars)"
                    )
                else:
                    self.logger.warning(
                        f"Chapter {chapter_input.chapter_id}: Previous chapter exists "
                        f"but has no brief_summary - processing independently"
                    )
            else:
                self.logger.warning(
                    f"Chapter {chapter_input.chapter_id}: Cannot retrieve context from "
                    f"previous chapter (index={prev_summary_index})"
                )
        
        # Create chapter processor
        processor = ChapterProcessor(
            prompt_manager=self.prompt_manager,
            ai_api_client=self.ai_api_client
        )
        
        # Process chapter with context summary
        result = processor.process_chapter(
            chapter_input,
            previous_context_summary=previous_summary
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
        storage_data = {
            'metadata': result.structured_data.get('metadata', {}),
            'world_events': result.structured_data.get('world_events', []),
            'locations': result.structured_data.get('locations', []),
            'characters': result.structured_data.get('characters', []),
            'scenes': result.structured_data.get('scenes', []),
            'growth': result.structured_data.get('growth', {}),
            'items': result.structured_data.get('items', []),
            'plot_secrets': result.structured_data.get('plot_secrets', {}),
            'chapter_summary': result.structured_data.get('chapter_summary', {}),
            'original_text': result.original_text
        }
        
        # Save using storage manager
        self.storage_manager.save_chapter_result(
            chapter_id=result.chapter_id,
            result_data=storage_data
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
        description="Automated batch processor for novel analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m ai_novel_analyzer.batch_processor \\
      --input-dir data/raw/ \\
      --output-dir data/processed/ \\
      --vector-db-path db/local_vector_store/
  
  python -m ai_novel_analyzer.batch_processor \\
      --input-dir novels/test/ \\
      --output-dir output/test/ \\
      --workers 2 \\
      --continue-on-failure
        """
    )
    
    parser.add_argument(
        '--input-dir',
        type=str,
        required=True,
        help='Directory containing raw chapter text files'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='output/processed',
        help='Output directory for processed JSON files (default: output/processed)'
    )
    
    parser.add_argument(
        '--vector-db-path',
        type=str,
        default=None,
        help='Path to ChromaDB storage directory (optional)'
    )
    
    parser.add_argument(
        '--workers',
        type=int,
        default=4,
        help='Number of parallel worker threads (default: 4)'
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
    
    # Load config from file if provided
    config_dict = {}
    if args.config_file and Path(args.config_file).exists():
        with open(args.config_file, 'r', encoding='utf-8') as f:
            config_dict = yaml.safe_load(f)
    
    # Override with command line args
    config_dict.update({
        'max_workers': args.workers,
        'continue_on_error': args.continue_on_failure,
        'output_dir': args.output_dir,
        'vector_db_path': args.vector_db_path,
        'embedding_api_key': args.api_key or os.getenv('SILICONFLOW_API_KEY') or config_dict.get('embedding_api_key'),
        'config_file': args.config_file
    })
    
    # Set defaults
    config_dict.setdefault('use_cloud_embeddings', True)
    config_dict.setdefault('retry_on_failure', True)
    config_dict.setdefault('save_intermediate', True)
    
    # Create config object
    config = BatchProcessingConfig(**config_dict)
    
    # Run batch processing
    processor = AutomatedBatchProcessor(config)
    
    input_dir = Path(args.input_dir)
    
    if not input_dir.exists():
        print(f"Error: Input directory {input_dir} does not exist")
        sys.exit(1)
    
    success = processor.run_batch(input_dir)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
