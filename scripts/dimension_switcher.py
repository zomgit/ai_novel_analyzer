"""
维度配置切换工具

支持：
- 列出所有可用预设
- 切换维度配置（仙侠/都市/科幻）
- 自动重新生成数据库结构
- 备份旧数据
"""

import logging
import shutil
from pathlib import Path
from typing import List, Optional

from ai_novel_analyzer.core.config_manager import get_config
from ai_novel_analyzer.core.dimension_engine import DimensionEngine
from ai_novel_analyzer.storage.sqlite_eav_storage import SQLiteEAVStorage


class DimensionSwitcher:
    """维度配置切换器"""
    
    # 内置预设
    PRESETS = {
        "xianxia": "仙侠小说（修真、门派、法宝）",
        "urban": "都市小说（商战、情感、职场）",
        "scifi": "科幻小说（科技、外星、探索）",
        "fantasy": "奇幻小说（魔法、种族、大陆）",
    }
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = get_config()
        
        self.dimensions_dir = Path("config/dimensions")
        self.dimensions_dir.mkdir(parents=True, exist_ok=True)
    
    def list_presets(self) -> List[str]:
        """
        列出所有可用预设
        
        Returns:
            预设类型列表
        """
        available = []
        
        # 从代码中的预设
        for preset_type, description in self.PRESETS.items():
            config_file = self.dimensions_dir / f"{preset_type}.yaml"
            exists_marker = "[YES]" if config_file.exists() else "[NO ]"
            print(f"  {exists_marker} {preset_type:12} - {description}")
            available.append(preset_type)
        
        return available
    
    def switch_to(self, novel_type: str, force: bool = False) -> bool:
        """
        切换到指定的维度配置
        
        Args:
            novel_type: 小说类型（xianxia|urban|scifi|fantasy）
            force: 是否强制覆盖现有数据库
            
        Returns:
            是否成功
        """
        config_file = self.dimensions_dir / f"{novel_type}.yaml"
        
        if not config_file.exists():
            # 尝试从预设加载
            if novel_type in DimensionEngine.XIANXIA_PRESET:
                self.logger.info(f"创建预设配置：{novel_type}")
                self._create_preset(novel_type, config_file)
            else:
                self.logger.error(f"未知预设类型：{novel_type}")
                return False
        
        # 备份现有数据库
        db_path = Path("user_data/database/novel_analyzer.db")
        if db_path.exists() and not force:
            backup_path = db_path.with_suffix(".bak")
            shutil.copy2(db_path, backup_path)
            self.logger.info(f"已备份数据库：{backup_path}")
            
            print("\nWarning: Existing database detected. Switching configuration will cause:")
            print("   - New table structure incompatible with old data")
            print("   - Old data has been backed up to novel_analyzer.db.bak")
            print("\nContinue? (y/N): ", end="")
            
            response = input().strip().lower()
            if response != 'y':
                self.logger.info("用户取消操作")
                return False
        
        # 重新创建数据库
        try:
            engine = DimensionEngine(config_file)
            storage = SQLiteEAVStorage(db_path, engine)
            
            print(f"[OK] Successfully switched to {novel_type} dimension config")
            print(f"  - Dimension count: {len(engine.dimensions)}")
            print(f"  - Database location: {db_path}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"切换失败：{e}")
            return False
    
    def _create_preset(self, novel_type: str, output_path: Path):
        """从代码预设创建配置文件"""
        preset_map = {
            "xianxia": DimensionEngine.XIANXIA_PRESET,
            "urban": DimensionEngine.URBAN_PRESET,
            "scifi": DimensionEngine.SCIFI_PRESET,
            "fantasy": DimensionEngine.XIANXIA_PRESET,  # 暂时复用
        }
        
        if novel_type not in preset_map:
            raise ValueError(f"未知预设类型：{novel_type}")
        
        content = preset_map[novel_type]
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        self.logger.info(f"已创建配置文件：{output_path}")
    
    def show_current(self):
        """显示当前使用的维度配置"""
        config_path = self.config.dimension_config_path
        
        if not config_path.exists():
            print("✗ 未找到维度配置文件")
            return
        
        try:
            engine = DimensionEngine(config_path)
            
            print(f"当前维度配置:")
            print(f"  - 类型：{engine.novel_type}")
            print(f"  - 版本：{engine.schema.version if engine.schema else 'N/A'}")
            print(f"  - 维度数量：{len(engine.dimensions)}")
            print("\n维度列表:")
            
            for i, dim in enumerate(engine.dimensions, 1):
                required = "必填" if dim.is_required else "选填"
                print(f"  {i}. {dim.name} ({dim.key}) [{required}]")
                
        except Exception as e:
            self.logger.error(f"读取配置失败：{e}")


# ========== CLI 入口 ==========

def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="维度配置切换工具")
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有可用预设"
    )
    parser.add_argument(
        "--switch",
        type=str,
        choices=["xianxia", "urban", "scifi", "fantasy"],
        help="切换到指定维度配置"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制覆盖（不询问确认）"
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="显示当前配置"
    )
    
    args = parser.parse_args()
    
    switcher = DimensionSwitcher()
    
    if args.list:
        print("\n可用预设:")
        switcher.list_presets()
    
    elif args.show:
        print()
        switcher.show_current()
    
    elif args.switch:
        print(f"\n切换到 {args.switch}...")
        success = switcher.switch_to(args.switch, force=args.force)
        
        if success:
            print("\n提示：可以使用 --show 查看当前配置详情")
        else:
            print("\n切换失败，请检查日志")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
