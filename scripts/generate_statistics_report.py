"""
统计报表生成工具

从 SQLite EAV 数据库生成各类统计报表：
- 章节总览
- 人物出场统计
- 事件频率分析
- 修炼等级分布
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from ai_novel_analyzer.storage.unified_query_api import UnifiedQueryAPI


class StatisticsReportGenerator:
    """统计报表生成器"""
    
    def __init__(self, api: UnifiedQueryAPI):
        """
        Args:
            api: UnifiedQueryAPI 实例
        """
        self.logger = logging.getLogger(__name__)
        self.api = api
    
    def generate_full_report(self, output_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        生成完整统计报表
        
        Args:
            output_path: 输出文件路径（可选）
            
        Returns:
            报表数据字典
        """
        report = {
            "generated_at": datetime.now().isoformat(),
            "engine_config": {
                "novel_type": self.api.engine.novel_type,
                "dimension_count": len(self.api.engine.dimensions)
            },
            "summary": {},
            "dimension_statistics": {},
            "character_ranking": [],
            "event_frequency": {}
        }
        
        # 基础统计
        stats = self.api.get_dimension_statistics()
        report["summary"] = {
            "total_chapters": stats["total_chapters"],
            "total_records": sum(info["record_count"] for info in stats["dimension_summary"].values())
        }
        
        # 维度统计
        report["dimension_statistics"] = stats["dimension_summary"]
        
        # 角色排名
        report["character_ranking"] = self.api.get_character_statistics(top_n=20)
        
        # 事件频率
        report["event_frequency"] = self._analyze_event_frequency()
        
        # 保存到文件
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"报表已保存：{output_path}")
        
        return report
    
    def _analyze_event_frequency(self) -> Dict[str, int]:
        """
        分析各类型事件的频率
        
        Returns:
            {event_type: count}
        """
        event_types = [
            "important_events",
            "battle_scenes",
            "exploration_events",
            "cultivation_progress"
        ]
        
        frequency = {}
        
        try:
            with self.api.sqlite_storage.get_connection() as conn:
                cursor = conn.cursor()
                
                for event_type in event_types:
                    table_name = f"eav_{event_type}"
                    
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                        count = cursor.fetchone()[0]
                        frequency[event_type] = count
                    except Exception:
                        pass
        
        except Exception as e:
            self.logger.error(f"事件频率分析失败：{e}")
        
        return frequency
    
    def print_report_summary(self, report: Dict[str, Any]):
        """打印报表摘要"""
        print("\n" + "=" * 60)
        print("统计报表摘要")
        print("=" * 60)
        
        print(f"\n生成时间：{report['generated_at']}")
        print(f"小说类型：{report['engine_config']['novel_type']}")
        print(f"维度数量：{report['engine_config']['dimension_count']}")
        
        print("\n--- 总体统计 ---")
        print(f"总章节数：{report['summary']['total_chapters']}")
        print(f"总记录数：{report['summary']['total_records']}")
        
        print("\n--- 维度分布 ---")
        for dim_key, info in report['dimension_statistics'].items():
            required = "[必填]" if info['required'] else "[选填]"
            print(f"  {dim_key:30} {required}: {info['record_count']:4} 条")
        
        print("\n--- 人物出场 TOP 10 ---")
        for i, char in enumerate(report['character_ranking'][:10], 1):
            levels = char.get('levels', 'N/A')
            print(f"  {i}. {char['name']:15} ({char['appearance_count']} 次) - 等级：{levels}")
        
        print("\n--- 事件频率 ---")
        for event_type, count in report['event_frequency'].items():
            print(f"  {event_type:25}: {count} 次")
        
        print("\n" + "=" * 60)


# ========== 快捷函数 =========

def generate_statistics(config_path: Optional[Path] = None, output_path: Optional[Path] = None):
    """
    快速生成统计报表
    
    Args:
        config_path: 维度配置文件路径
        output_path: 输出文件路径
        
    Returns:
        报表数据字典
    """
    api = UnifiedQueryAPI(config_path)
    generator = StatisticsReportGenerator(api)
    
    report = generator.generate_full_report(output_path)
    generator.print_report_summary(report)
    
    return report


# ========== 测试入口 ==========

if __name__ == "__main__":
    print("=== Statistics Report Generator ===\n")
    
    # 配置路径
    config_path = Path("config/dimensions/xianxia.yaml")
    output_path = Path("user_data/reports/statistics_report.json")
    
    # 生成报表
    report = generate_statistics(config_path, output_path)
    
    print(f"\n[OK] Report saved to: {output_path}")
