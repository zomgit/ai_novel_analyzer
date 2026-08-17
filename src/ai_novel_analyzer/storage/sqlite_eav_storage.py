"""
SQLite EAV (Entity-Attribute-Value) 数据库存储模块

用于存储结构化数据，支持：
- 动态表结构（根据维度配置自动生成）
- 快速查询和统计
- 索引优化
"""

import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from contextlib import contextmanager

from ai_novel_analyzer.core.dimension_engine import DimensionEngine


class SQLiteEAVStorage:
    """SQLite EAV 数据存储管理器"""
    
    def __init__(self, db_path: Path, engine: DimensionEngine):
        """
        Args:
            db_path: SQLite 数据库文件路径
            engine: DimensionEngine 实例（提供维度配置）
        """
        self.db_path = Path(db_path)
        self.engine = engine
        self.logger = logging.getLogger(__name__)
        
        # 确保数据库文件存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 初始化数据库表
        self._init_tables()
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接（上下文管理器）"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_tables(self):
        """初始化数据库表结构"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 创建章节信息表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chapters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chapter_id TEXT NOT NULL UNIQUE,
                    volume_number INTEGER,
                    chapter_number INTEGER,
                    title TEXT,
                    content_hash TEXT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chapter_id ON chapters(chapter_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_volume_chapter ON chapters(volume_number, chapter_number)")
            
            # 根据维度配置创建 EAV 表
            for dim in self.engine.dimensions:
                table_name = f"eav_{dim.key}"
                
                # 检查表是否存在
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,)
                )
                if not cursor.fetchone():
                    # 创建新表
                    self._create_eav_table(cursor, table_name, dim)
                    self.logger.info(f"创建 EAV 表：{table_name}")
            
            self.logger.info(f"数据库初始化完成：{self.db_path}")
    
    def _create_eav_table(self, cursor, table_name: str, dim):
        """创建 EAV 表"""
        # 构建 CREATE TABLE 语句
        columns = [
            "id INTEGER PRIMARY KEY AUTOINCREMENT",
            "chapter_id TEXT NOT NULL",
            "volume_number INTEGER",
            "chapter_number INTEGER",
        ]
        
        # 添加提取字段
        for field_name in dim.extraction_fields:
            columns.append(f"{field_name} TEXT")
        
        # 添加外键约束
        columns.append("FOREIGN KEY (chapter_id) REFERENCES chapters(chapter_id) ON DELETE CASCADE")
        
        sql = f"CREATE TABLE {table_name} ({', '.join(columns)})"
        cursor.execute(sql)
        
        # 创建索引
        cursor.execute(f"CREATE INDEX idx_{table_name}_chapter ON {table_name}(chapter_id)")
        
        # 为第一个字段创建索引（如果有）
        if dim.extraction_fields:
            first_field = dim.extraction_fields[0]
            cursor.execute(f"CREATE INDEX idx_{table_name}_{first_field} ON {table_name}({first_field})")
    
    # ==================== 数据操作 API ====================
    
    def save_chapter(self, chapter_id: str, volume_number: int, chapter_number: int, title: str, content_hash: str = ""):
        """保存章节基本信息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO chapters (chapter_id, volume_number, chapter_number, title, content_hash)
                VALUES (?, ?, ?, ?, ?)
            """, (chapter_id, volume_number, chapter_number, title, content_hash))
    
    def insert_eav_record(self, dimension_key: str, chapter_id: str, volume_number: int, chapter_number: int, record: Dict[str, Any]):
        """
        插入 EAV 记录
        
        Args:
            dimension_key: 维度技术键（如 "character_names"）
            chapter_id: 章节 ID
            volume_number: 卷号
            chapter_number: 章号
            record: 数据记录（字段名->值）
        """
        dim = self.engine.schema.get_dimension_by_key(dimension_key)
        if not dim:
            raise ValueError(f"未知维度：{dimension_key}")
        
        table_name = f"eav_{dimension_key}"
        
        # 构建 INSERT 语句
        fields = ["chapter_id", "volume_number", "chapter_number"]
        values = [chapter_id, volume_number, chapter_number]
        
        for field_name in dim.extraction_fields:
            if field_name in record:
                fields.append(field_name)
                values.append(str(record[field_name]) if record[field_name] else None)
        
        placeholders = ", ".join(["?"] * len(fields))
        sql = f"INSERT INTO {table_name} ({', '.join(fields)}) VALUES ({placeholders})"
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, values)
    
    def query_dimension(self, dimension_key: str, chapter_id: Optional[str] = None, **filters) -> List[Dict[str, Any]]:
        """
        查询维度数据
        
        Args:
            dimension_key: 维度技术键
            chapter_id: 章节 ID（可选）
            **filters: 其他过滤条件
            
        Returns:
            查询结果列表
        """
        table_name = f"eav_{dimension_key}"
        
        where_clauses = []
        params = []
        
        if chapter_id:
            where_clauses.append("chapter_id = ?")
            params.append(chapter_id)
        
        # 处理自定义过滤
        for key, value in filters.items():
            where_clauses.append(f"{key} = ?")
            params.append(value)
        
        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        
        sql = f"SELECT * FROM {table_name} {where_clause}"
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计数据字典
        """
        stats = {
            "total_chapters": 0,
            "dimensions": {}
        }
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 章节总数
            cursor.execute("SELECT COUNT(*) FROM chapters")
            stats["total_chapters"] = cursor.fetchone()[0]
            
            # 各维度统计
            for dim in self.engine.dimensions:
                table_name = f"eav_{dim.key}"
                
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cursor.fetchone()[0]
                    stats["dimensions"][dim.key] = {
                        "record_count": count,
                        "required": dim.is_required
                    }
                except sqlite3.Error:
                    pass
        
        return stats


# ========== 快捷函数 =========

def create_database(db_path: Path, config_path: Path) -> SQLiteEAVStorage:
    """
    快速创建数据库
    
    Args:
        db_path: 数据库文件路径
        config_path: 维度配置文件路径
        
    Returns:
        SQLiteEAVStorage 实例
    """
    engine = DimensionEngine(config_path)
    return SQLiteEAVStorage(db_path, engine)


# ========== 测试入口 ==========

if __name__ == "__main__":
    print("=== SQLite EAV Storage 测试 ===\n")
    
    # 使用示例配置
    engine = DimensionEngine()  # 默认 xianxia
    
    db_path = Path("user_data/database/novel_analyzer.db")
    storage = SQLiteEAVStorage(db_path, engine)
    
    # 测试插入数据
    storage.save_chapter("vol_1_chap_1", 1, 1, "第一章 重生归来", "abc123")
    
    # 插入人物数据
    storage.insert_eav_record(
        dimension_key="character_names",
        chapter_id="vol_1_chap_1",
        volume_number=1,
        chapter_number=1,
        record={
            "name": "林尘",
            "cultivation_level": "炼气三层",
            "identity": "主角",
            "appearance_description": "俊朗少年"
        }
    )
    
    # 查询统计
    stats = storage.get_statistics()
    print(f"总章节数：{stats['total_chapters']}")
    print("\n维度记录统计:")
    for key, info in stats['dimensions'].items():
        print(f"  {key}: {info['record_count']} 条记录")
    
    print(f"\n数据库已创建：{db_path}")
