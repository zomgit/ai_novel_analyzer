"""
日志配置模块
提供统一的日志管理系统，支持文件轮转和控制台输出
"""

import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional
import sqlite3
import json
from datetime import datetime


def init_analysis_tasks_db(db_path: Path) -> None:
    """
    初始化分析任务历史数据库表（WAL 模式）
    
    Args:
        db_path: SQLite 数据库路径
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute('PRAGMA journal_mode = WAL')
    
    # 创建任务历史表
    conn.execute('''
        CREATE TABLE IF NOT EXISTS analysis_tasks (
            task_id TEXT PRIMARY KEY,
            scope TEXT NOT NULL,              -- 'book' / 'volume'
            project TEXT NOT NULL,
            book TEXT NOT NULL,
            volume_dir TEXT,                  -- NULL 表示整本书
            
            start_time REAL NOT NULL,         -- Unix timestamp
            end_time REAL,                    -- NULL 表示进行中
            
            total_chapters INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            retry_count INTEGER DEFAULT 0,
            
            status TEXT NOT NULL,             -- 'queued' / 'running' / 'success' / 'failed'
            failure_reason TEXT,              -- NULL 表示成功
            
            detail_json TEXT                  -- JSON 字符串：卷/章级别明细
        )
    ''')
    
    # 创建索引以提升查询性能
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_task_status ON analysis_tasks(status)
    ''')
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_task_project_book ON analysis_tasks(project, book)
    ''')
    
    conn.commit()
    conn.close()


def record_task_start(
    task_id: str,
    scope: str,
    project: str,
    book: str,
    volume_dir: Optional[str] = None,
    db_path: Optional[Path] = None
) -> None:
    """
    记录任务开始（仅写一次）
    
    Args:
        task_id: 任务唯一标识
        scope: 'book' or 'volume'
        project: 项目名称
        book: 书名
        volume_dir: 卷目录名（单卷分析时）
        db_path: 数据库路径（默认从 ConfigManager 读取）
    """
    if db_path is None:
        try:
            from ai_novel_analyzer.core.config_manager import get_config
            config = get_config()
            db_path = config.chromadb_path.parent / 'novel_analyzer.db'
        except Exception:
            db_path = Path('workspace/db/novel_analyzer.db')
    
    # 确保数据库已初始化
    if not db_path.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_analysis_tasks_db(db_path)
    
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute('''
            INSERT INTO analysis_tasks 
                (task_id, scope, project, book, volume_dir, start_time, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            task_id, scope, project, book, volume_dir,
            datetime.now().timestamp(), 'running'
        ))
        conn.commit()
    except Exception as e:
        print(f"⚠️  写入任务开始失败：{e}")
    finally:
        conn.close()


def finalize_task(
    task_id: str,
    status: str,
    metrics: dict,
    failure_reason: Optional[str] = None,
    db_path: Optional[Path] = None
) -> None:
    """
    任务结束时更新最终状态（仅写一次）
    
    Args:
        task_id: 任务唯一标识
        status: 'success' or 'failed'
        metrics: {total_chapters, success_count, failed_count, retry_count, detail_json?}
        failure_reason: 失败原因描述
        db_path: 数据库路径
    """
    if db_path is None:
        try:
            from ai_novel_analyzer.core.config_manager import get_config
            config = get_config()
            db_path = config.chromadb_path.parent / 'novel_analyzer.db'
        except Exception:
            db_path = Path('workspace/db/novel_analyzer.db')
    
    conn = sqlite3.connect(str(db_path))
    try:
        detail_json = json.dumps(metrics.get('detail_json', {}), ensure_ascii=False)
        
        conn.execute('''
            UPDATE analysis_tasks SET
                status = ?,
                end_time = ?,
                total_chapters = ?,
                success_count = ?,
                failed_count = ?,
                retry_count = ?,
                failure_reason = ?,
                detail_json = ?
            WHERE task_id = ?
        ''', (
            status,
            datetime.now().timestamp() if status == 'success' else None,
            metrics.get('total_chapters', 0),
            metrics.get('success_count', 0),
            metrics.get('failed_count', 0),
            metrics.get('retry_count', 0),
            failure_reason,
            detail_json,
            task_id
        ))
        conn.commit()
    except Exception as e:
        print(f"⚠️  写入任务结束失败：{e}")
    finally:
        conn.close()


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


def setup_http_request_logger(
    log_dir: Optional[Path] = None,
    max_bytes: int = 1024 * 1024,  # 1MB
    format_string: str = '%(message)s'  # JSON 行格式
) -> logging.Logger:
    """
    创建 HTTP 请求专用日志记录器（独立文件 + 自动轮转）
    
    Args:
        log_dir: 日志目录（默认到 logs/）
        max_bytes: 单文件最大大小（默认 1MB）
        format_string: 日志格式字符串（JSON 行）
        
    Returns:
        HTTP 请求日志记录器
    """
    try:
        from ai_novel_analyzer.core.config_manager import get_config
        config = get_config()
        if log_dir is None:
            log_dir = config.logs_dir
    except Exception:
        log_dir = Path("logs")
    
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建基础 HTTP 请求记录器
    logger = logging.getLogger('http_requests')
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()  # 清除所有现有 handler
    
    # 创建 RotatingFileHandler（不设置 backupCount，保留所有历史文件）
    http_log_file = log_dir / "api_http_requests.log"
    file_handler = RotatingFileHandler(
        http_log_file,
        maxBytes=max_bytes,
        backupCount=0,  # 0 表示无限制，不会自动删除
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(format_string))
    logger.addHandler(file_handler)
    
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
