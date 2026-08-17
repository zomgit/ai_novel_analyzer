#!/usr/bin/env python3
"""
维度库聚合工具 - 独立调用，不嵌入 batch_processor 流程

用法：
    uv run python scripts\\aggregate_dimensions.py \\
        --input-dir output/processed/ \\
        --output-dir output/index/
"""

import argparse
import sys
from pathlib import Path
import logging

# 添加 src 目录到路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ai_novel_analyzer.storage.dimension_aggregator import DimensionAggregator, AggregationConfig


def main():
    parser = argparse.ArgumentParser(description="聚合小说分析维度库")
    parser.add_argument('--input-dir', type=str, default='output/processed/', help='输入目录（单章 JSON 文件）')
    parser.add_argument('--output-dir', type=str, default='output/index/', help='输出目录（维度库索引）')
    parser.add_argument('--no-ai-compression', action='store_true', help='禁用 AI 压缩长摘要')
    parser.add_argument('--workers', type=int, default=4, help='并行工作线程数（默认：4）')
    args = parser.parse_args()
    
    # 设置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    logger.info("🚀 启动维度库聚合...")
    
    config = AggregationConfig(
        processed_dir=Path(args.input_dir).resolve(),
        index_dir=Path(args.output_dir).resolve(),
        use_ai_for_synthesis=not args.no_ai_compression,
        max_workers=args.workers
    )
    
    if not config.processed_dir.exists():
        logger.error(f"❌ 输入目录不存在：{config.processed_dir}")
        return 1
    
    aggregator = DimensionAggregator(config)
    libraries = aggregator.aggregate_all()
    
    # 保存维度库
    from ai_novel_analyzer.storage.dimension_aggregator import save_dimension_libraries
    save_dimension_libraries(libraries, config.index_dir)
    
    logger.info("✅ 聚合完成！")
    return 0


if __name__ == "__main__":
    sys.exit(main())
