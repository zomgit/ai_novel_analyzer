"""
日志配置模块
提供统一的日志管理系统，支持文件轮转和控制台输出
"""

import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional


def setup_logging(
    level: str = "INFO",
    log_dir: Optional[Path] = None,
    log_file: str = "novel_analyzer.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    format_string: Optional[str] = None,
) -> logging.Logger:
    """
    设置日志系统
    
    Args:
        level: 日志级别 (DEBUG|INFO|WARNING|ERROR|CRITICAL)
        log_dir: 日志目录（默认到 logs/）
        log_file: 日志文件名
        max_bytes: 单文件最大大小
        backup_count: 保留备份数量
        format_string: 日志格式字符串
        
    Returns:
        根日志记录器
    """
    
    # 使用 ConfigManager 获取默认值
    try:
        from ai_novel_analyzer.core.config_manager import get_config
        
        config = get_config()
        
        if log_dir is None:
            log_dir = config.logs_dir
            
        if level == "INFO":
            level = config.log_level
        if max_bytes == 10 * 1024 * 1024:
            max_bytes = config.log_max_bytes
        if backup_count == 5:
            backup_count = config.log_backup_count
        if format_string is None:
            format_string = config.logging.get('format', "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            
    except Exception:
        # 如果 ConfigManager 不可用，使用默认值
        if log_dir is None:
            log_dir = Path("logs")
    
    # 确保日志目录存在
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 配置日志文件路径
    log_file_path = log_dir / log_file
    
    # 创建根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # 清除现有的处理器
    root_logger.handlers.clear()
    
    # 创建日志格式器
    formatter = logging.Formatter(format_string)
    
    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 添加文件处理器（带轮转）
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # 创建特定模块的日志记录器
    logger = logging.getLogger(__name__)
    logger.info(f"日志系统已初始化 - 级别={level}, 文件={log_file_path}")
    
    return logger


# 快捷函数
def get_logger(name: str) -> logging.Logger:
    """
    获取特定模块的日志记录器
    
    Args:
        name: 模块名称
        
    Returns:
        日志记录器实例
    """
    return logging.getLogger(name)


# 测试入口
if __name__ == "__main__":
    logger = setup_logging()
    
    # 测试各种日志级别
    logger.debug("这是 DEBUG 消息")
    logger.info("这是 INFO 消息")
    logger.warning("这是 WARNING 消息")
    logger.error("这是 ERROR 消息")
    logger.critical("这是 CRITICAL 消息")
    
    print(f"\n日志已写入：{Path('logs/novel_analyzer.log')}")
