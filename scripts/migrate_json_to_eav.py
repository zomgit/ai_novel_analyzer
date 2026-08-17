"""
JSON 到 EAV 数据库迁移工具

将 AI 分析输出的 JSON 文件批量导入 SQLite EAV 数据库
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from ai_novel_analyzer.core.dimension_engine import DimensionEngine
from ai_novel_analyzer.storage.sqlite_eav_storage import SQLiteEAVStorage


class JSONtoEAVMigrator:
    """JSON → EAV 数据库迁移器"""
    
    def __init__(self, config_path: Path, db_path: Path):
        """
        Args:
            config_path: 维度配置文件路径
            db_path: SQLite 数据库路径
        """
        self.logger = logging.getLogger(__name__)
        
        # 初始化引擎和存储
        self.engine = DimensionEngine(config_path)
        self.storage = SQLiteEAVStorage(db_path, self.engine)
        
        self.logger.info(f"初始化完成：{len(self.engine.dimensions)} 个维度")
    
    def migrate_json_file(self, json_path: Path) -> bool:
        """
        迁移单个 JSON 文件
        
        Args:
            json_path: JSON 文件路径
            
        Returns:
            是否成功
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 提取章节信息
            chapter_id = data.get('chapter_id') or json_path.stem
            volume_number = data.get('volume_number', 1)
            chapter_number = data.get('chapter_number', 1)
            title = data.get('title', '')
            
            # 保存章节基本信息
            content_hash = self._calculate_content_hash(data)
            self.storage.save_chapter(chapter_id, volume_number, chapter_number, title, content_hash)
            
            # 迁移各维度数据
            migrated_count = 0
            for dim_key in self.engine.dimension_keys:
                if dim_key in data and data[dim_key]:
                    records = data[dim_key]
                    
                    # 处理单条记录或列表
                    if isinstance(records, dict):
                        records = [records]
                    
                    for record in records:
                        try:
                            self.storage.insert_eav_record(
                                dimension_key=dim_key,
                                chapter_id=chapter_id,
                                volume_number=volume_number,
                                chapter_number=chapter_number,
                                record=record
                            )
                            migrated_count += 1
                        except Exception as e:
                            self.logger.warning(f"插入记录失败 ({dim_key}): {e}")
            
            self.logger.info(f"✓ {json_path.name}: 迁移 {migrated_count} 条记录")
            return True
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON 解析失败 {json_path.name}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"迁移失败 {json_path.name}: {e}")
            return False
    
    def migrate_directory(self, input_dir: Path, pattern: str = "*.json") -> Dict[str, int]:
        """
        批量迁移目录中的所有 JSON 文件
        
        Args:
            input_dir: 输入目录
            pattern: 文件匹配模式
            
        Returns:
            统计结果 {"total": 总数，"success": 成功数，"failed": 失败数}
        """
        json_files = list(input_dir.glob(pattern))
        
        stats = {
            "total": len(json_files),
            "success": 0,
            "failed": 0
        }
        
        if not json_files:
            self.logger.warning(f"目录中没有找到匹配的文件：{input_dir}")
            return stats
        
        self.logger.info(f"开始迁移 {len(json_files)} 个文件...")
        
        for i, json_path in enumerate(json_files, 1):
            if self.migrate_json_file(json_path):
                stats["success"] += 1
            else:
                stats["failed"] += 1
            
            if i % 10 == 0:
                self.logger.info(f"进度：{i}/{len(json_files)}")
        
        self.logger.info(f"迁移完成：成功 {stats['success']}/{stats['total']}, 失败 {stats['failed']}")
        return stats
    
    def _calculate_content_hash(self, data: Dict[str, Any]) -> str:
        """计算内容哈希值（简单实现）"""
        import hashlib
        content_str = json.dumps(data, ensure_ascii=False, sort_keys=True)
        return hashlib.md5(content_str.encode()).hexdigest()
    
    # ==================== 统计和报告 ====================
    
    def generate_report(self) -> Dict[str, Any]:
        """
        生成迁移报告
        
        Returns:
            报告数据字典
        """
        stats = self.storage.get_statistics()
        
        report = {
            "total_chapters": stats['total_chapters'],
            "dimension_summary": {},
            "engine_config": {
                "novel_type": self.engine.novel_type,
                "version": self.engine.schema.version if self.engine.schema else "1.0",
                "dimension_count": len(self.engine.dimensions)
            }
        }
        
        for key, info in stats['dimensions'].items():
            report['dimension_summary'][key] = info
        
        return report


# ========== 快捷函数 =========

def migrate_json_files(config_path: Path, db_path: Path, json_dir: Path, pattern: str = "*.json"):
    """
    快速批量迁移
    
    Args:
        config_path: 维度配置文件路径
        db_path: 数据库路径
        json_dir: JSON 文件目录
        pattern: 文件匹配模式
    """
    migrator = JSONtoEAVMigrator(config_path, db_path)
    return migrator.migrate_directory(json_dir, pattern)


# ========== 测试入口 ==========

if __name__ == "__main__":
    print("=== JSON → EAV Migrator 测试 ===\n")
    
    # 配置路径
    config_path = Path("config/dimensions/xianxia.yaml")
    db_path = Path("user_data/database/novel_analyzer.db")
    
    # 创建测试 JSON 文件
    test_json = {
        "chapter_id": "vol_1_chap_2",
        "volume_number": 1,
        "chapter_number": 2,
        "title": "第二章 家族恩怨",
        "character_names": [
            {
                "name": "林尘",
                "cultivation_level": "炼气四层",
                "identity": "主角",
                "appearance_description": "俊朗少年"
            },
            {
                "name": "王霸",
                "cultivation_level": "炼气五层",
                "identity": "反派",
                "appearance_description": "魁梧大汉"
            }
        ],
        "important_events": [
            {
                "event_name": "家族试炼",
                "participants": ["林尘", "王霸"],
                "location": "林家后院",
                "consequence": "林尘获胜",
                "significance": "展现主角天赋"
            }
        ]
    }
    
    # 保存测试 JSON
    test_dir = Path("user_data/test_migration")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    test_file = test_dir / "vol_1_chap_2.json"
    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(test_json, f, ensure_ascii=False, indent=2)
    
    print(f"创建测试文件：{test_file}\n")
    
    # 执行迁移
    migrator = JSONtoEAVMigrator(config_path, db_path)
    stats = migrator.migrate_directory(test_dir)
    
    print(f"\n迁移统计:")
    print(f"  总文件数：{stats['total']}")
    print(f"  成功：{stats['success']}")
    print(f"  失败：{stats['failed']}")
    
    # 查询验证
    print("\n查询验证:")
    characters = migrator.storage.query_dimension("character_names", chapter_id="vol_1_chap_2")
    print(f"  人物数量：{len(characters)}")
    
    for char in characters:
        print(f"    - {char['name']} ({char['cultivation_level']})")
    
    # 清理测试文件
    test_file.unlink()
    print(f"\n已删除测试文件")
