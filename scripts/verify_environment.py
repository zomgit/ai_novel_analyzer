#!/usr/bin/env python3
"""
AI Novel Analyzer - 简单验证工具

只需一行命令即可确认您的环境是否准备好运行本项目！
"""

import sys

# Windows 控制台编码兼容处理
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def check_core_deps():
    """检查核心依赖"""
    
    try:
        import requests
        print("✅ requests")
        
        import yaml
        print("✅ pyyaml")
        
        from dotenv import load_dotenv
        print("✅ python-dotenv")
        
        import jsonschema
        print("✅ jsonschema")
        
        from pydantic import BaseModel
        print("✅ pydantic")
        
        import chromadb
        print("✅ chromadb")
        
        from tqdm import tqdm
        print("✅ tqdm")
        
    except ImportError as e:
        missing = str(e).split("'")[1]
        print(f"❌ 缺失：{missing}")
        return False
    
    return True


def check_siliconflow():
    """检查 SiliconFlow API 配置（通过 requests 直接调用，无需额外包）"""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    if os.getenv('SILICONFLOW_API_KEY'):
        print("✅ SILICONFLOW_API_KEY 已配置（云端 Embedding 可用）")
        return True
    else:
        print("⚠️  SILICONFLOW_API_KEY 未配置（向量搜索功能需配置后才能使用）")
        return False


def main():
    print("=" * 60)
    print("🔍 AI Novel Analyzer - 环境验证")
    print("=" * 60)
    print()
    
    # 检查核心依赖
    print("检查核心依赖...")
    if not check_core_deps():
        print("\n💡 请运行：pip install -r requirements.txt")
        return False
    
    print()
    
    # 检查 SiliconFlow
    print("检查可选依赖...")
    has_sf = check_siliconflow()
    
    print()
    print("=" * 60)
    
    if has_sf:
        print("🎉 完美！所有依赖已安装，您可以开始使用了！")
    else:
        print("✅ 核心功能就绪！")
        print("   提示：如需云端向量化服务，请在 .env 中配置 SILICONFLOW_API_KEY")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
