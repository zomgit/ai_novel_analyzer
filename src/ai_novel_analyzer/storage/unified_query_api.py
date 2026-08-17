"""
统一数据查询 API

提供对 SQLite 和 ChromaDB 的统一访问接口，支持：
- 结构化查询（SQLite）
- 向量相似度搜索（ChromaDB）
- 混合查询（SQL+Vector）
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from ai_novel_analyzer.core.config_manager import get_config
from ai_novel_analyzer.core.dimension_engine import DimensionEngine
from ai_novel_analyzer.storage.sqlite_eav_storage import SQLiteEAVStorage
from ai_novel_analyzer.storage import StorageManager


class UnifiedQueryAPI:
    """统一数据查询 API"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Args:
            config_path: 维度配置文件路径（可选）
        """
        self.logger = logging.getLogger(__name__)
        self.config = get_config()
        
        # 初始化引擎和存储
        if config_path is None:
            config_path = self.config.dimension_config_path
        
        self.engine = DimensionEngine(config_path)
        
        # SQLite 存储
        db_path = self.config.sqlite_db_path
        self.sqlite_storage = SQLiteEAVStorage(db_path, self.engine)
        
        # ChromaDB 向量存储（可选）
        try:
            import chromadb
            self.chroma_client = chromadb.PersistentClient(path=str(self.config.chromadb_path))
            self.vector_store_available = True
        except Exception as e:
            self.logger.warning(f"ChromaDB 不可用：{e}")
            self.chroma_client = None
            self.vector_store_available = False
    
    # ==================== 基础查询 ====================
    
    def query_by_chapter(self, chapter_id: str) -> Dict[str, Any]:
        """
        查询某章节的所有维度数据
        
        Args:
            chapter_id: 章节 ID
            
        Returns:
            {dimension_key: [records]}
        """
        result = {}
        
        for dim in self.engine.dimensions:
            records = self.sqlite_storage.query_dimension(
                dim.key,
                chapter_id=chapter_id
            )
            result[dim.key] = records
        
        return result
    
    def query_character_appearances(self, character_name: str, volume_number: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        查询某角色的出场记录
        
        Args:
            character_name: 角色名字
            volume_number: 卷号（可选）
            
        Returns:
            出场记录列表
        """
        query_params = {"chapter_id": None}
        
        # 构建过滤条件
        where_clauses = ["name = ?"]
        params = [character_name]
        
        if volume_number:
            where_clauses.append("volume_number = ?")
            params.append(volume_number)
        
        # 执行查询
        sql = f"SELECT * FROM eav_character_names WHERE {' AND '.join(where_clauses)}"
        
        try:
            with self.sqlite_storage.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"查询失败：{e}")
            return []
    
    def query_events_by_type(self, event_type: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        按事件类型查询
        
        Args:
            event_type: 事件类型（important_events|battle_scenes 等）
            limit: 返回数量限制
            
        Returns:
            事件记录列表
        """
        table_name = f"eav_{event_type}"
        
        try:
            with self.sqlite_storage.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"SELECT * FROM {table_name} LIMIT ?", (limit,))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"查询失败：{e}")
            return []
    
    # ==================== 统计查询 ====================
    
    def get_dimension_statistics(self) -> Dict[str, Any]:
        """
        获取所有维度的统计数据
        
        Returns:
            统计数据字典
        """
        stats = {
            "total_chapters": 0,
            "dimension_summary": {}
        }
        
        try:
            with self.sqlite_storage.get_connection() as conn:
                cursor = conn.cursor()
                
                # 总章节数
                cursor.execute("SELECT COUNT(*) FROM chapters")
                stats["total_chapters"] = cursor.fetchone()[0]
                
                # 各维度统计
                for dim in self.engine.dimensions:
                    table_name = f"eav_{dim.key}"
                    
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                        count = cursor.fetchone()[0]
                        
                        stats["dimension_summary"][dim.key] = {
                            "record_count": count,
                            "required": dim.is_required,
                            "description": dim.description
                        }
                    except Exception:
                        pass
            
        except Exception as e:
            self.logger.error(f"统计查询失败：{e}")
        
        return stats
    
    def get_character_statistics(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        获取角色出场次数统计
        
        Args:
            top_n: 返回前 N 名
            
        Returns:
            [{name: ..., count: ..., avg_cultivation_level: ...}]
        """
        try:
            with self.sqlite_storage.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        name,
                        COUNT(*) as appearance_count,
                        GROUP_CONCAT(cultivation_level) as levels
                    FROM eav_character_names
                    GROUP BY name
                    ORDER BY appearance_count DESC
                    LIMIT ?
                """, (top_n,))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"角色统计失败：{e}")
            return []
    
    # ==================== 向量搜索（ChromaDB）====================
    
    def vector_search(self, query: str, collection_name: str = "novel_analysis", top_k: int = 5) -> List[Dict[str, Any]]:
        """
        向量相似度搜索
        
        Args:
            query: 查询文本
            collection_name: 集合名称
            top_k: 返回结果数量
            
        Returns:
            搜索结果列表
        """
        if not self.vector_store_available:
            self.logger.warning("向量存储不可用")
            return []
        
        try:
            # 获取嵌入模型（这里简化为直接调用）
            from ai_novel_analyzer.utils.ai_api_client import AIApiFactory
            
            client = AIApiFactory.create_siliconflow_embedding(
                api_key=self.config.api_key or "dummy_key"
            )
            
            # 生成查询向量
            query_embedding = client.embed_documents([query])
            
            # 执行向量搜索
            collection = self.chroma_client.get_collection(collection_name)
            results = collection.query(
                query_embeddings=[query_embedding[0]],
                n_results=top_k,
                include=['documents', 'metadatas', 'distances']
            )
            
            # 格式化结果
            formatted_results = []
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    "id": results['ids'][0][i],
                    "content": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i]
                })
            
            return formatted_results
            
        except Exception as e:
            self.logger.error(f"向量搜索失败：{e}")
            return []
    
    # ==================== 混合查询 ====================
    
    def hybrid_search(self, query: str, dimension_key: str = "character_names", limit: int = 10) -> Dict[str, Any]:
        """
        混合搜索（SQL + Vector）
        
        Args:
            query: 查询文本
            dimension_key: 维度键
            limit: 结果数量限制
            
        Returns:
            {sql_results: [...], vector_results: [...]}
        """
        result = {
            "sql_results": [],
            "vector_results": []
        }
        
        # 执行 SQL 查询
        if dimension_key == "character_names":
            result["sql_results"] = self.query_character_appearances(query)
        else:
            result["sql_results"] = self.query_events_by_type(dimension_key, limit)
        
        # 执行向量搜索
        result["vector_results"] = self.vector_search(query, top_k=limit)
        
        return result


# ========== 快捷函数 =========

def create_query_api(config_path: Optional[Path] = None) -> UnifiedQueryAPI:
    """
    快速创建查询 API
    
    Args:
        config_path: 维度配置文件路径
        
    Returns:
        UnifiedQueryAPI 实例
    """
    return UnifiedQueryAPI(config_path)


# ========== 测试入口 ==========

if __name__ == "__main__":
    print("=== Unified Query API 测试 ===\n")
    
    api = UnifiedQueryAPI()
    
    print("1. 获取统计信息:")
    stats = api.get_dimension_statistics()
    print(f"   总章节数：{stats['total_chapters']}")
    
    print("\n2. 维度统计:")
    for key, info in stats['dimension_summary'].items():
        print(f"   {key}: {info['record_count']} records")
    
    print("\n3. 角色统计:")
    characters = api.get_character_statistics()
    for char in characters:
        print(f"   {char['name']}: {char['appearance_count']} appearances")
    
    print("\n[OK] Test completed")
