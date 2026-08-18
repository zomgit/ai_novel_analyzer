"""
Scripts package - CLI tools for novel analysis

This package contains all command-line tools:
- batch_processor: 批量处理引擎
- split_book: 拆书工具（workspace 结构版）
- quick_setup: 新手配置向导
- check_progress: 进度查看工具
- verify_environment: 环境验证工具
"""

from pathlib import Path

# 脚本目录路径
SCRIPTS_DIR = Path(__file__).parent
