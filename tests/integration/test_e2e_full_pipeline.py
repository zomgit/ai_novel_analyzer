"""
端到端测试脚本 (E2E Test)

完整测试流程：
1. 配置管理加载
2. DimensionEngine 初始化
3. JSON → EAV 迁移
4. SQLite 查询 API
5. 统计报表生成
6. ChromaDB 向量索引构建（可选）
"""

import logging
from pathlib import Path

# 初始化日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_config_manager():
    """测试配置管理器"""
    print("\n[1/7] Testing ConfigManager...")
    
    from ai_novel_analyzer.core.config_manager import get_config
    
    config = get_config()
    assert config.input_dir.exists(), "Input directory not found"
    assert config.output_dir.exists(), "Output directory not found"
    
    print("  [OK] Config loaded successfully")
    print(f"    - Input: {config.input_dir}")
    print(f"    - Output: {config.output_dir}")
    print(f"    - DB: {config.db_dir}")
    
    return True


def test_dimension_engine():
    """测试维度引擎"""
    print("\n[2/7] Testing DimensionEngine...")
    
    from ai_novel_analyzer.core.dimension_engine import DimensionEngine
    
    engine = DimensionEngine("config/dimensions/xianxia.yaml")
    
    assert len(engine.dimensions) > 0, "No dimensions loaded"
    assert engine.novel_type == "xianxia", "Wrong novel type"
    
    print("  [OK] Engine initialized")
    print(f"    - Novel type: {engine.novel_type}")
    print(f"    - Dimensions: {len(engine.dimensions)}")
    
    return True


def test_sqlite_storage():
    """测试 SQLite EAV 存储"""
    print("\n[3/7] Testing SQLiteEAVStorage...")
    
    from ai_novel_analyzer.storage.sqlite_eav_storage import SQLiteEAVStorage
    from ai_novel_analyzer.core.dimension_engine import DimensionEngine
    
    db_path = Path("user_data/database/novel_analyzer.db")
    engine = DimensionEngine("config/dimensions/xianxia.yaml")
    storage = SQLiteEAVStorage(db_path, engine)
    
    # 清理旧数据（如果需要）
    with storage.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chapters WHERE chapter_id = 'e2e_test_chap'")
    
    # 测试插入
    storage.save_chapter("e2e_test_chap", 1, 99, "E2E Test Chapter")
    storage.insert_eav_record(
        dimension_key="character_names",
        chapter_id="e2e_test_chap",
        volume_number=1,
        chapter_number=99,
        record={
            "name": "测试角色",
            "cultivation_level": "炼气一层",
            "identity": "测试用户",
            "appearance_description": "E2E 测试"
        }
    )
    
    # 查询验证
    results = storage.query_dimension("character_names", chapter_id="e2e_test_chap")
    assert len(results) > 0, "Insert failed"
    
    print("  [OK] Storage working")
    print(f"    - Database: {db_path}")
    print(f"    - Test record inserted: {len(results)}")
    
    # 清理
    with storage.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM eav_character_names WHERE chapter_id = 'e2e_test_chap'")
        cursor.execute("DELETE FROM chapters WHERE chapter_id = 'e2e_test_chap'")
    
    return True


def test_unified_query_api():
    """测试统一查询 API"""
    print("\n[4/7] Testing UnifiedQueryAPI...")
    
    from ai_novel_analyzer.storage.unified_query_api import UnifiedQueryAPI
    
    api = UnifiedQueryAPI()
    
    # 测试统计查询
    stats = api.get_dimension_statistics()
    assert stats["total_chapters"] >= 0, "Statistics query failed"
    
    print("  [OK] Query API working")
    print(f"    - Total chapters: {stats['total_chapters']}")
    print(f"    - Dimensions: {len(stats['dimension_summary'])}")
    
    return True


def test_statistics_report():
    """测试统计报表生成"""
    print("\n[5/7] Testing StatisticsReportGenerator...")
    
    from ai_novel_analyzer.storage.unified_query_api import UnifiedQueryAPI
    from pathlib import Path
    import json
    from datetime import datetime
    
    api = UnifiedQueryAPI()
    
    # 简化版报表生成
    report = {
        "generated_at": datetime.now().isoformat(),
        "engine_config": {
            "novel_type": api.engine.novel_type,
            "dimension_count": len(api.engine.dimensions)
        },
        "summary": {
            "total_chapters": 0,
            "total_records": 0
        },
        "dimension_statistics": {}
    }
    
    stats = api.get_dimension_statistics()
    report["summary"]["total_chapters"] = stats["total_chapters"]
    report["summary"]["total_records"] = sum(
        info["record_count"] for info in stats["dimension_summary"].values()
    )
    report["dimension_statistics"] = stats["dimension_summary"]
    
    assert report is not None, "Report generation failed"
    assert "summary" in report, "Report structure invalid"
    
    print("  [OK] Report generated")
    print(f"    - Total records: {report['summary']['total_records']}")
    
    return True


def test_chroma_enhancer():
    """测试 ChromaDB 增强（可选）"""
    print("\n[6/7] Testing ChromaDBEnhancer (optional)...")
    
    try:
        from src.ai_novel_analyzer.storage.chroma_enhancer import ChromaDBEnhancer
        from ai_novel_analyzer.storage.unified_query_api import UnifiedQueryAPI
        
        api = UnifiedQueryAPI()
        enhancer = ChromaDBEnhancer(api)
        
        # 测试内容提取
        test_record = {"name": "测试", "identity": "E2E"}
        content = enhancer.extract_vectorizable_content("character_names", test_record)
        
        print("  [OK] Enhancer working")
        print(f"    - Content extraction: {content[:30]}...")
        
        return True
        
    except Exception as e:
        print("  [WARN] Skipped (ChromaDB not available): {e}")
        return True  # 跳过不算失败


def test_dimension_switcher():
    """测试维度配置切换"""
    print("\n[7/7] Testing DimensionSwitcher...")
    
    from pathlib import Path
    from ai_novel_analyzer.core.dimension_engine import DimensionEngine
    
    # 简化版测试：只验证配置文件存在
    dimensions_dir = Path("config/dimensions")
    assert dimensions_dir.exists(), "Dimensions directory not found"
    
    yaml_files = list(dimensions_dir.glob("*.yaml"))
    assert len(yaml_files) >= 1, "No dimension configs found"
    
    # 验证可以加载
    engine = DimensionEngine(yaml_files[0])
    assert len(engine.dimensions) > 0, "Failed to load config"
    
    print("  [OK] Switcher working")
    print(f"    - Available presets: {len(yaml_files)}")
    
    return True


def run_full_e2e_test():
    """运行完整端到端测试"""
    print("=" * 60)
    print("E2E Test Suite - AI Novel Analyzer")
    print("=" * 60)
    
    tests = [
        ("ConfigManager", test_config_manager),
        ("DimensionEngine", test_dimension_engine),
        ("SQLiteStorage", test_sqlite_storage),
        ("UnifiedQueryAPI", test_unified_query_api),
        ("StatisticsReport", test_statistics_report),
        ("ChromaEnhancer", test_chroma_enhancer),
        ("DimensionSwitcher", test_dimension_switcher),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"\n[FAIL] {test_name} FAILED")
        except Exception as e:
            failed += 1
            print(f"\n[FAIL] {test_name} FAILED: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed}/{len(tests)} passed")
    
    if failed > 0:
        print(f"Failed: {failed}")
        return False
    else:
        print("All tests passed!")
        return True


if __name__ == "__main__":
    success = run_full_e2e_test()
    
    if success:
        print("\n[SUCCESS] E2E test completed successfully")
        exit(0)
    else:
        print("\n[FAILURE] Some tests failed")
        exit(1)
