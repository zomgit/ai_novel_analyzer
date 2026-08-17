"""
ChromaDB 向量存储增强模块

提供：
- 自动从 SQLite EAV 数据提取向量化内容
- 批量嵌入生成
- 混合搜索路由（SQL + Vector）
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from ai_novel_analyzer.core.config_manager import get_config
from ai_novel_analyzer.core.dimension_engine import DimensionEngine
from ai_novel_analyzer.storage.unified_query_api import UnifiedQueryAPI


class ChromaDBEnhancer:
    """ChromaDB 向量存储增强器"""
    
    def __init__(self, api: UnifiedQueryAPI):
        """
        Args:
            api: UnifiedQueryAPI 实例
        """
        self.logger = logging.getLogger(__name__)
        self.api = api
        
        # 检查向量存储是否可用
        if not self.api.vector_store_available:
            self.logger.warning("向量存储不可用，混合搜索功能受限")
    
    def extract_vectorizable_content(self, dimension_key: str, record: Dict[str, Any]) -> str:
        """
        从 EAV 记录中提取可向量化内容
        
        Args:
            dimension_key: 维度键
            record: EAV 记录
            
        Returns:
            可嵌入的文本内容
        """
        # 根据维度类型提取关键字段
        if dimension_key == "character_names":
            return f"{record.get('name', '')} - {record.get('identity', '')}"
        
        elif dimension_key == "important_events":
            return f"{record.get('event_name', '')}: {record.get('consequence', '')}"
        
        elif dimension_key == "battle_scenes":
            combatants = record.get('combatants', '')
            outcome = record.get('outcome', '')
            return f"战斗：{combatants} - {outcome}"
        
        elif dimension_key == "locations":
            return f"{record.get('location_name', '')}: {record.get('description', '')}"
        
        else:
            # 默认：拼接所有文本字段
            text_parts = []
            for key, value in record.items():
                if isinstance(value, str) and value:
                    text_parts.append(value)
            
            return " ".join(text_parts)
    
    def build_vector_index(self, dimension_keys: Optional[List[str]] = None, batch_size: int = 50):
        """
        构建向量索引
        
        Args:
            dimension_keys: 要索引的维度键列表（None=全部）
            batch_size: 批量大小
        """
        if not self.api.vector_store_available:
            self.logger.error("无法构建向量索引：ChromaDB 不可用")
            return
        
        if dimension_keys is None:
            dimension_keys = self.api.engine.dimension_keys
        
        collection_name = self.api.config.vector_collection_name
        
        try:
            # 获取或创建集合
            collection = self.api.chroma_client.get_or_create_collection(
                name=collection_name,
                metadata={"description": "Novel analysis vector index"}
            )
            
            # 遍历各维度数据
            total_count = 0
            for dim_key in dimension_keys:
                dim = self.api.engine.schema.get_dimension_by_key(dim_key)
                if not dim:
                    continue
                
                # 查询该维度的所有记录
                records = self.api.sqlite_storage.query_dimension(dim_key)
                
                # 提取可嵌入内容
                embeddings_data = []
                metadatas = []
                ids = []
                
                for record in records:
                    content = self.extract_vectorizable_content(dim_key, record)
                    
                    embeddings_data.append(content)
                    metadatas.append({
                        "dimension": dim_key,
                        "chapter_id": record.get("chapter_id", ""),
                        "primary_field": list(record.keys())[0] if record else ""
                    })
                    ids.append(f"{dim_key}_{len(ids)}")
                
                # 批量添加
                if embeddings_data:
                    collection.add(
                        documents=embeddings_data,
                        metadatas=metadatas,
                        ids=ids
                    )
                    total_count += len(embeddings_data)
                    
                    self.logger.info(f"维度 {dim_key}: 索引 {len(embeddings_data)} 条记录")
            
            self.logger.info(f"向量索引构建完成：共 {total_count} 条记录")
            
        except Exception as e:
            self.logger.error(f"向量索引构建失败：{e}")
            raise
    
    def hybrid_search(self, query: str, limit: int = 10) -> Dict[str, List[Dict[str, Any]]]:
        """
        混合搜索（SQL + Vector）
        
        Args:
            query: 查询文本
            limit: 结果数量限制
            
        Returns:
            {
                "sql_results": [...],
                "vector_results": [...],
                "combined_score": [...]
            }
        """
        result = {
            "sql_results": [],
            "vector_results": [],
            "combined": []
        }
        
        # SQL 查询
        for dim in self.api.engine.dimensions:
            if dim.key == "character_names":
                result["sql_results"] = self.api.query_character_appearances(query)
            else:
                events = self.api.query_events_by_type(dim.key, limit=limit)
                result["sql_results"].extend(events)
        
        # Vector 搜索
        if self.api.vector_store_available:
            result["vector_results"] = self.api.vector_search(query, top_k=limit)
        
        # 合并结果（简单策略：去重 + 排序）
        combined = self._combine_results(result["sql_results"], result["vector_results"])
        result["combined"] = combined[:limit]
        
        return result
    
    def _combine_results(self, sql_results: List[Dict], vector_results: List[Dict]) -> List[Dict]:
        """
        合并 SQL 和 Vector 搜索结果
        
        简化策略：
        - SQL 结果权重 1.0
        - Vector 结果权重 0.8
        - 去重（基于 primary field）
        """
        combined = []
        seen_keys = set()
        
        # 先加 SQL 结果
        for r in sql_results:
            key = self._get_result_key(r)
            if key not in seen_keys:
                combined.append({**r, "score": 1.0})
                seen_keys.add(key)
        
        # 再加 Vector 结果
        for r in vector_results:
            content = r.get("content", "")
            key = content[:50]  # 简化键
            
            if key not in seen_keys:
                combined.append({
                    "content": content,
                    "metadata": r.get("metadata", {}),
                    "distance": r.get("distance", 0),
                    "score": 0.8
                })
                seen_keys.add(key)
        
        # 按分数排序
        combined.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        return combined
    
    def _get_result_key(self, record: Dict) -> str:
        """获取记录的唯一键"""
        # 优先使用第一个非 id 字段
        for key, value in record.items():
            if key not in ["id", "chapter_id"] and value:
                return str(value)
        return str(record.get("id", ""))


# ========== 快捷函数 =========

def build_hybrid_index(config_path: Optional[Path] = None):
    """
    快速构建混合索引
    
    Args:
        config_path: 维度配置文件路径
    """
    api = UnifiedQueryAPI(config_path)
    enhancer = ChromaDBEnhancer(api)
    
    enhancer.build_vector_index()


# ========== 测试入口 ==========

if __name__ == "__main__":
    print("=== ChromaDB Enhancer Test ===\n")
    
    api = UnifiedQueryAPI()
    enhancer = ChromaDBEnhancer(api)
    
    # 测试内容提取
    test_record = {
        "name": "林尘",
        "cultivation_level": "炼气四层",
        "identity": "主角"
    }
    
    content = enhancer.extract_vectorizable_content("character_names", test_record)
    print(f"Extracted content: {content}")
    
    print("\n[OK] Test completed")
