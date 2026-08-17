"""跨章节维度聚合器 - 独立调用模式"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import logging
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


@dataclass
class AggregationConfig:
    """聚合配置"""
    processed_dir: Path       # output/processed/
    index_dir: Path          # output/index/
    use_ai_for_synthesis: bool = True  # 是否用 AI 做语义合成（默认启用）
    embedding_api_key: Optional[str] = None
    max_workers: int = 4


class DimensionAggregator:
    """维度聚合器 - 独立运行，支持增量/全量聚合"""
    
    def __init__(self, config: AggregationConfig):
        self.config = config
        self.processed_files = list(config.processed_dir.glob("*.json"))
        logger.info(f"找到 {len(self.processed_files)} 个待聚合的章节文件")
    
    def aggregate_all(self) -> Dict[str, Any]:
        """执行完整聚合，返回所有维度库"""
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = {
                executor.submit(self._aggregate_characters): "character_library",
                executor.submit(self._aggregate_locations): "location_atlas",
                executor.submit(self._aggregate_items): "item_catalog",
                executor.submit(self._aggregate_world_events): "world_event_timeline",
                executor.submit(self._aggregate_foreshadowing): "foreshadowing_library",
                executor.submit(self._aggregate_plot_secrets): "plot_secrets_library",
            }
            
            result = {}
            for future in futures:
                dim_name = futures[future]
                try:
                    result[dim_name] = future.result()
                except Exception as e:
                    logger.error(f"聚合 {dim_name} 失败：{str(e)}", exc_info=True)
                    result[dim_name] = {"error": str(e)}
            
            return result
    
    # ========== 各维度聚合方法 ==========
    
    def _aggregate_characters(self) -> Dict[str, Any]:
        """人物库聚合
        
        策略：
        1. 从每个 JSON 提取 characters 数组（仅保留 name, attributes, identity, relationships）
        2. 按 name 分组去重
        3. 合并多章更新：首次出场、最新更新、关系网络
        4. ✅ 可选：用 AI 对长描述做语义压缩（当单个人物数据超过 500 字时）
        """
        char_map = {}  # name → CharacterRecord
        
        for file_path in self.processed_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # ✅ 只提取关键字段，不传原始文本
            for char in data.get('characters', []):
                name = char.get('name', '')
                if not name:
                    continue
                
                # 构建精简记录（< 200 字）
                record = {
                    'first_appearance': file_path.stem,  # vol_X_chap_Y
                    'last_update': file_path.stem,
                    'attributes_history': [{  # 属性变化历史
                        'chapter': file_path.stem,
                        'changes': char.get('attributes', {})
                    }] if char.get('attributes') else None,
                    'identity_history': [{  # 身份变化历史
                        'chapter': file_path.stem,
                        'changes': char.get('identity', {})
                    }] if char.get('identity') else None,
                    'relationships_snapshot': char.get('relationships', []),  # 本章最新关系
                    'actions_summary': char.get('actions', ''),  # 本章行动概述
                }
                
                # 合并到 char_map
                if name not in char_map:
                    char_map[name] = record
                else:
                    # 追加历史记录
                    if record['attributes_history']:
                        char_map[name]['attributes_history'].extend(record['attributes_history'])
                    if record['identity_history']:
                        char_map[name]['identity_history'].extend(record['identity_history'])
                    # 更新快照
                    char_map[name]['last_update'] = record['last_update']
                    char_map[name]['relationships_snapshot'] = record['relationships_snapshot']
                    # 累积行动摘要
                    char_map[name]['actions_summary'] += '\n' + record['actions_summary']
        
        # ✅ 可选：AI 压缩超长人物的 actions_summary
        if self.config.use_ai_for_synthesis:
            char_map = self._ai_compress_character_summaries(char_map)
        
        return {
            'version': '1.0',
            'generated_at': str(Path.now()),
            'character_count': len(char_map),
            'characters': list(char_map.values())
        }
    
    def _aggregate_locations(self) -> Dict[str, Any]:
        """地点档案聚合
        
        策略：
        1. 从每个 JSON 提取 locations 数组
        2. 按 name 去重，累积 events 和 characters
        3. ✅ 只传递 location 元数据，不传原文
        """
        loc_map = {}
        
        for file_path in self.processed_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for loc in data.get('locations', []):
                name = loc.get('name', '')
                if not name:
                    continue
                
                if name not in loc_map:
                    loc_map[name] = {
                        'name': name,
                        'type': loc.get('type'),
                        'description': loc.get('description'),
                        'first_appearance': file_path.stem,
                        'events': [],
                        'visits': [],  # 访问记录 [chapter, characters]
                    }
                
                # 累积事件和访问
                loc_map[name]['events'].append(loc.get('events', []))
                loc_map[name]['visits'].append({
                    'chapter': file_path.stem,
                    'characters': loc.get('characters', [])
                })
        
        return {'locations': list(loc_map.values())}
    
    def _aggregate_items(self) -> Dict[str, Any]:
        """物品图鉴聚合
        
        策略：
        1. 按 name 去重
        2. 追踪生命周期：获得→强化→损失
        3. ✅ 只传递物品元数据
        """
        item_map = {}
        
        for file_path in self.processed_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for item in data.get('items', []):
                name = item.get('name', '')
                if not name:
                    continue
                
                if name not in item_map:
                    item_map[name] = {
                        'name': name,
                        'category': item.get('category'),
                        'rarity': item.get('rarity'),
                        'current_owner': item.get('owner'),
                        'life_cycle': []  # [{chapter, change_type, details}]
                    }
                
                item_map[name]['life_cycle'].append({
                    'chapter': file_path.stem,
                    'change_type': item.get('changes', ['获得'])[0] if item.get('changes') else '获得',
                    'details': item.get('properties', '')
                })
        
        return {'items': list(item_map.values())}
    
    def _aggregate_world_events(self) -> List[Dict]:
        """世界事件时间线（不合并，按章节顺序）"""
        events = []
        
        for file_path in sorted(self.processed_files):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for event in data.get('world_events', []):
                event['_source_chapter'] = file_path.stem
                events.append(event)
        
        # 按章节排序
        events.sort(key=lambda x: x['_source_chapter'])
        return events
    
    def _aggregate_foreshadowing(self) -> List[Dict]:
        """伏笔库聚合（从 plot_secrets.clues 提取）"""
        clues = []
        
        for file_path in self.processed_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for clue in data.get('plot_secrets', {}).get('clues', []):
                clue['_source_chapter'] = file_path.stem
                clues.append(clue)
        
        clues.sort(key=lambda x: x['_source_chapter'])
        return clues
    
    def _aggregate_plot_secrets(self) -> Dict[str, List]:
        """剧情秘密库（twists + revelations）"""
        result = {'twists': [], 'revelations': []}
        
        for file_path in self.processed_files:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            ps = data.get('plot_secrets', {})
            for twist in ps.get('twists', []):
                twist['_source_chapter'] = file_path.stem
                result['twists'].append(twist)
            
            for rev in ps.get('revelations', []):
                rev['_source_chapter'] = file_path.stem
                result['revelations'].append(rev)
        
        return result
    
    # ========== 可选：AI 辅助压缩 ==========
    
    def _ai_compress_character_summaries(self, char_map: Dict[str, Any]) -> Dict[str, Any]:
        """用 AI 压缩超长的人物行动摘要（> 500 字时触发）"""
        from ai_novel_analyzer.utils.ai_api_client import get_ai_client_from_config
        from dotenv import load_dotenv
        import os
        
        load_dotenv()
        api_key = os.getenv('AI_MODEL_API_KEY')
        base_url = os.getenv('AI_MODEL_BASE_URL')
        model = os.getenv('AI_MODEL_NAME')
        
        if not api_key:
            logger.warning("未找到 AI_MODEL_API_KEY，跳过 AI 压缩")
            return char_map
        
        client = get_ai_client_from_config({
            'ai_model': {
                'params': {
                    'api_key': api_key,
                    'base_url': base_url or 'https://api.siliconflow.cn/v1',
                    'model': model or 'Qwen/Qwen2.5-72B-Instruct'
                }
            }
        })
        
        compressed_count = 0
        for name, record in char_map.items():
            summary = record.get('actions_summary', '')
            if not summary or len(summary) <= 500:
                continue
            
            # ✅ 只发送 summary 给 AI，不喂原始章节内容
            prompt = f"""请将以下人物行动摘要压缩为 200 字以内的精炼版本，保留关键信息：

{summary}

输出仅包含压缩后的文本（不要任何前缀或说明）："""
            
            try:
                response = client.generate(messages=[{'role': 'user', 'content': prompt}], 
                                          temperature=0.0, max_tokens=256, stream=False)
                compressed = response.choices[0].message.content.strip()
                char_map[name]['actions_summary'] = compressed
                compressed_count += 1
                logger.debug(f"✅ 压缩人物 {name} 的行动摘要")
            except Exception as e:
                logger.warning(f"AI 压缩 {name} 失败：{str(e)[:100]}")
        
        if compressed_count > 0:
            logger.info(f"AI 压缩完成：共处理 {compressed_count} 个人物")
        
        return char_map


def save_dimension_libraries(libraries: Dict[str, Any], index_dir: Path) -> None:
    """保存所有维度库到 output/index/ 目录"""
    index_dir.mkdir(parents=True, exist_ok=True)
    
    for lib_name, lib_data in libraries.items():
        filepath = index_dir / f"{lib_name}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(lib_data, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ 保存维度库：{filepath}")
