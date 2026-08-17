"""
声明式维度引擎 (DimensionEngine)

核心思想：配置驱动 - 通过 YAML 配置自动生成所有相关组件
- Prompt 模板
- JSON Schema
- SQLite EAV 表结构
- ChromaDB 元数据过滤字段
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
import yaml


@dataclass
class DimensionConfig:
    """单个维度配置"""
    name: str  # 维度名称（中文）
    key: str   # 技术标识符（英文蛇形命名，如 "character_names"）
    description: str  # 描述
    target_type: str  # 目标类型："entity" | "relation" | "event" | "item"
    extraction_fields: List[str]  # 提取字段列表
    is_required: bool = True  # 是否必填
    
    def to_json_schema(self) -> Dict[str, Any]:
        """转换为 JSON Schema 片段"""
        return {
            "type": "array",
            "description": self.description,
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "action": {"type": "string"},
                    "timestamp": {"type": "string"}
                },
                "required": ["name", "action"]
            }
        }


@dataclass
class DimensionsSchema:
    """完整维度配置 schema"""
    novel_type: str  # 小说类型："xianxia" | "urban" | "scifi" | "fantasy"
    title: str  # 标题
    version: str = "1.0"
    
    dimensions: List[DimensionConfig] = field(default_factory=list)
    
    @property
    def dimension_keys(self) -> List[str]:
        """所有维度的技术关键词"""
        return [d.key for d in self.dimensions]
    
    def add_dimension(self, dim: DimensionConfig):
        """添加维度"""
        self.dimensions.append(dim)
    
    def get_dimension_by_key(self, key: str) -> Optional[DimensionConfig]:
        """根据技术键查找维度"""
        for d in self.dimensions:
            if d.key == key:
                return d
        return None


class DimensionEngine:
    """声明式维度引擎"""
    
    # ==================== 预设配置 ====================
    
    XIANXIA_PRESET = """
title: "仙侠小说分析维度"
novel_type: "xianxia"
version: "1.0"

dimensions:
  # === 人物相关 ===
  - name: "主要人物"
    key: "character_names"
    description: "本章出现的主要人物（包括名字、称谓）"
    target_type: "entity"
    extraction_fields: ["name", "cultivation_level", "identity"]
    is_required: true
  
  - name: "人物关系变化"
    key: "relationship_changes"
    description: "人物之间的关系变化（结拜、敌对、师徒等）"
    target_type: "relation"
    extraction_fields: ["person_a", "person_b", "relation_type", "change_description"]
    is_required: false
  
  - name: "功法修炼"
    key: "cultivation_progress"
    description: "功法/境界突破情况"
    target_type: "event"
    extraction_fields: ["character", "old_level", "new_level", "technique_name"]
    is_required: false
  
  # === 事件相关 ===
  - name: "重要事件"
    key: "important_events"
    description: "推动剧情发展的重要事件"
    target_type: "event"
    extraction_fields: ["event_name", "participants", "location", "consequence"]
    is_required: true
  
  - name: "战斗场景"
    key: "battle_scenes"
    description: "战斗/对决场景记录"
    target_type: "event"
    extraction_fields: ["combatants", "techniques_used", "outcome", "damage_assessment"]
    is_required: false
  
  # === 物品相关 ===
  - name: "灵物丹药"
    key: "spiritual_items"
    description: "出现的法宝、丹药、灵器等"
    target_type: "item"
    extraction_fields: ["item_name", "level", "effect", "owner"]
    is_required: false
  
  # === 世界观 ===
  - name: "地点场景"
    key: "locations"
    description: "新出现或重要的地点场景"
    target_type: "entity"
    extraction_fields: ["location_name", "location_type", "description", "significance"]
    is_required: false
  
  - name: "势力组织"
    key: "factions"
    description: "门派、宗门、家族等势力组织"
    target_type: "entity"
    extraction_fields: ["faction_name", "faction_type", "leader", "stance"]
    is_required: false
"""
    
    URBAN_PRESET = """
title: "都市小说分析维度"
novel_type: "urban"
version: "1.0"

dimensions:
  - name: "主要人物"
    key: "character_names"
    description: "本章出现的主要人物"
    target_type: "entity"
    extraction_fields: ["name", "occupation", "background"]
    is_required: true
  
  - name: "商业活动"
    key: "business_activities"
    description: "商业决策、交易、合作等"
    target_type: "event"
    extraction_fields: ["activity_type", "participants", "outcome", "financial_impact"]
    is_required: false
  
  - name: "情感线发展"
    key: "romantic_developments"
    description: "感情线的推进"
    target_type: "relation"
    extraction_fields: ["person_a", "person_b", "emotion_type", "development_stage"]
    is_required: false
  
  - name: "都市景观"
    key: "urban_locations"
    description: "城市中的地点场景"
    target_type: "entity"
    extraction_fields: ["location_name", "location_type", "description"]
    is_required: false
"""
    
    SCIFI_PRESET = """
title: "科幻小说分析维度"
novel_type: "scifi"
version: "1.0"

dimensions:
  - name: "主要人物"
    key: "character_names"
    description: "主要人物"
    target_type: "entity"
    extraction_fields: ["name", "role", "special_abilities"]
    is_required: true
  
  - name: "科技设定"
    key: "technology_settings"
    description: "出现的科学技术、设备"
    target_type: "item"
    extraction_fields: ["tech_name", "function", "level", "usage"]
    is_required: false
  
  - name: "外星种族"
    key: "alien_races"
    description: "外星智慧种族"
    target_type: "entity"
    extraction_fields: ["race_name", "characteristics", "relationships"]
    is_required: false
  
  - name: "重大发现"
    key: "major_discoveries"
    description: "科学发现、探索成果"
    target_type: "event"
    extraction_fields: ["discovery_type", "location", "implications"]
    is_required: false
"""

    # ==================== 初始化 ====================
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Args:
            config_path: 维度配置文件路径（可选）
                        - 如果提供：从文件加载
                        - 如果不提供：使用默认预设（xianxia）
        """
        self.logger = logging.getLogger(__name__)
        self.schema: Optional[DimensionsSchema] = None
        
        # 支持 str 或 Path
        if isinstance(config_path, str):
            config_path = Path(config_path)
        
        if config_path and config_path.exists():
            self._load_from_file(config_path)
            self.logger.info(f"从文件加载维度配置：{config_path}")
        else:
            # 默认使用 xianxia 预设
            self._load_preset("xianxia")
            self.logger.info("使用默认 xianxia 预设配置")
    
    def _load_from_file(self, file_path: Path):
        """从 YAML 文件加载配置"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        self.schema = DimensionsSchema(
            novel_type=data['novel_type'],
            title=data['title'],
            version=data.get('version', '1.0')
        )
        
        # 解析每个维度
        for dim_data in data['dimensions']:
            dim = DimensionConfig(
                name=dim_data['name'],
                key=dim_data['key'],
                description=dim_data['description'],
                target_type=dim_data['target_type'],
                extraction_fields=dim_data.get('extraction_fields', []),
                is_required=dim_data.get('is_required', True)
            )
            self.schema.add_dimension(dim)
        
        self.logger.info(f"成功加载 {len(self.schema.dimensions)} 个维度")
    
    def _load_preset(self, preset_type: str):
        """加载预设配置"""
        preset_map = {
            "xianxia": self.XIANXIA_PRESET,
            "urban": self.URBAN_PRESET,
            "scifi": self.SCIFI_PRESET,
            "fantasy": self.XIANXIA_PRESET  # 暂时复用 xianxia
        }
        
        if preset_type not in preset_map:
            raise ValueError(f"未知的预设类型：{preset_type}")
        
        data = yaml.safe_load(preset_map[preset_type])
        self._parse_config(data)
    
    def _parse_config(self, data: Dict[str, Any]):
        """解析配置数据"""
        self.schema = DimensionsSchema(
            novel_type=data['novel_type'],
            title=data['title'],
            version=data.get('version', '1.0')
        )
        
        for dim_data in data['dimensions']:
            dim = DimensionConfig(
                name=dim_data['name'],
                key=dim_data['key'],
                description=dim_data['description'],
                target_type=dim_data['target_type'],
                extraction_fields=dim_data.get('extraction_fields', []),
                is_required=dim_data.get('is_required', True)
            )
            self.schema.add_dimension(dim)
    
    # ==================== 生成组件 ====================
    
    def generate_prompt(self, context: str = "") -> str:
        """
        根据维度配置生成 Prompt
        
        Args:
            context: 上下文信息（可选）
            
        Returns:
            完整的 Prompt 模板字符串
        """
        if not self.schema:
            raise RuntimeError("维度配置未初始化")
        
        prompt_lines = [
            "# Role Definition",
            "你是一个专业的小说分析专家，擅长从章节中提取结构化信息。",
            "",
            "# 任务说明",
            f"小说类型：{self.schema.title}",
            f"版本号：{self.schema.version}",
            ""
        ]
        
        if context:
            prompt_lines.extend([
                "# 上下文信息",
                context,
                ""
            ])
        
        # 维度定义
        prompt_lines.append("# 分析维度")
        prompt_lines.append("请按照以下维度提取本章信息，并以 JSON 格式输出：")
        prompt_lines.append("")
        
        for i, dim in enumerate(self.schema.dimensions, 1):
            required_str = "【必填】" if dim.is_required else "【选填】"
            prompt_lines.extend([
                f"{i}. {dim.name} ({required_str})",
                f"   描述：{dim.description}",
                f"   类型：{dim.target_type}",
                f"   提取字段：{', '.join(dim.extraction_fields)}",
                ""
            ])
        
        # JSON Schema 要求
        prompt_lines.extend([
            "# JSON Schema 要求",
            "请严格遵循以下 JSON 结构：",
            "",
            "```json",
            "{",
        ])
        
        # 构建 JSON 对象
        for dim in self.schema.dimensions:
            if dim.is_required:
                prompt_lines.append(f'    "{dim.key}": [...],')
            else:
                prompt_lines.append(f'    // "{dim.key}": [...] (可选)',)
        
        prompt_lines.extend([
            "}"
        ])
        
        if self.schema.novel_type == "xianxia":
            prompt_lines.extend([
                "",
                "# 特殊说明",
                "• 人物名称可能是：本名、道号、尊称等多种形式",
                "• 修炼等级包括但不限于：炼气、筑基、金丹、元婴、化神等",
                "• 功法名称可能包含：真、经、典、录、诀等后缀",
                "• 法宝/丹药需标注品阶：下品、中品、上品、极品",
            ])
        
        prompt_lines.extend([
            "",
            "```",
            ""
        ])
        
        return "\n".join(prompt_lines)
    
    def generate_json_schema(self) -> Dict[str, Any]:
        """
        生成 JSON Schema
        
        Returns:
            完整的 JSON Schema 字典
        """
        if not self.schema:
            raise RuntimeError("维度配置未初始化")
        
        schema_dict = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": f"{self.schema.title} Analysis Output",
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False
        }
        
        for dim in self.schema.dimensions:
            schema_dict["properties"][dim.key] = dim.to_json_schema()
            
            if dim.is_required:
                schema_dict["required"].append(dim.key)
        
        return schema_dict
    
    def generate_eav_schema(self) -> Dict[str, Dict[str, Any]]:
        """
        生成 EAV (Entity-Attribute-Value) 数据库表结构
        
        返回：{dimension_key: {columns, description}}
        """
        if not self.schema:
            raise RuntimeError("维度配置未初始化")
        
        eav_tables = {}
        
        for dim in self.schema.dimensions:
            table_name = f"eav_{dim.key}"
            
            # 根据 target_type 决定主字段
            if dim.target_type == "entity":
                primary_field = "name"
            elif dim.target_type == "event":
                primary_field = "event_name"
            elif dim.target_type == "item":
                primary_field = "item_name"
            else:  # relation
                primary_field = "relation_type"
            
            eav_tables[dim.key] = {
                "table_name": table_name,
                "description": dim.description,
                "primary_field": primary_field,
                "fields": {
                    "id": {"type": "INTEGER PRIMARY KEY AUTOINCREMENT"},
                    "chapter_id": {"type": "TEXT NOT NULL"},
                    "volume_number": {"type": "INTEGER"},
                    "chapter_number": {"type": "INTEGER"},
                }
            }
            
            # 添加提取字段
            for field_name in dim.extraction_fields:
                eav_tables[dim.key]["fields"][field_name] = {"type": "TEXT"}
        
        return eav_tables
    
    # ==================== API 方法 ====================
    
    def get_dimension_keys(self) -> List[str]:
        """获取所有维度的技术关键词"""
        if not self.schema:
            return []
        return self.dimension_keys
    
    def get_dimension_names(self) -> List[str]:
        """获取所有维度的中文名"""
        if not self.schema:
            return []
        return [d.name for d in self.dimensions]
    
    def get_chroma_db_metadata(self) -> Dict[str, str]:
        """
        获取 ChromaDB 元数据过滤字段
        
        Returns:
            {collection_name: [filter_fields]}
        """
        if not self.schema:
            return {}
        
        metadata = {}
        for dim in self.schema.dimensions:
            collection_name = f"novel_{dim.key}"
            # 元数据过滤字段通常是：chapter_id, volume, 以及主要实体的名称
            filter_fields = ["chapter_id", "volume_number", "chapter_number"]
            metadata[collection_name] = filter_fields
        
        return metadata
    
    # ==================== 工具方法 ====================
    
    @property
    def dimensions(self) -> List[DimensionConfig]:
        """访问维度列表"""
        if not self.schema:
            return []
        return self.schema.dimensions
    
    @property
    def dimension_keys(self) -> List[str]:
        """获取维度技术关键词"""
        if not self.schema:
            return []
        return self.schema.dimension_keys
    
    @property
    def novel_type(self) -> str:
        """获取小说类型"""
        if not self.schema:
            return "unknown"
        return self.schema.novel_type


# ========== 快捷函数 =========

def load_dimension_engine(config_path: Optional[Path] = None) -> DimensionEngine:
    """
    快速加载 DimensionEngine
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        DimensionEngine 实例
    """
    return DimensionEngine(config_path)


# ========== 测试入口 ==========

if __name__ == "__main__":
    print("=== DimensionEngine 测试 ===\n")
    
    # 使用默认预设
    engine = DimensionEngine()
    
    print(f"小说类型：{engine.novel_type}")
    print(f"维度数量：{len(engine.dimensions)}\n")
    
    print("维度列表:")
    for i, dim in enumerate(engine.dimensions, 1):
        print(f"{i}. {dim.name} ({dim.key}) - {dim.target_type}")
    
    print("\n生成的 Prompt 示例:")
    print("-" * 50)
    prompt = engine.generate_prompt("这是背景介绍...")
    print(prompt[:1000])  # 只显示前 1000 字符
    
    print("\n\nJSON Schema 示例:")
    print("-" * 50)
    schema = engine.generate_json_schema()
    print(json.dumps(schema, indent=2, ensure_ascii=False)[:500])
    
    print("\n\nEAV 表结构:")
    print("-" * 50)
    eav = engine.generate_eav_schema()
    for key, info in eav.items():
        print(f"\n表名：{info['table_name']}")
        print(f"主字段：{info['primary_field']}")
        print(f"描述：{info['description']}")
        print(f"字段数：{len(info['fields'])}")
