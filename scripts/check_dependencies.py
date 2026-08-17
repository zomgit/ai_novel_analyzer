#!/usr/bin/env python3
"""
AI Novel Analyzer - 依赖安装检查工具

运行此脚本快速验证所有必需的核心依赖是否已正确安装。
SiliconFlow 通过标准库 requests 调用 REST API，无需额外安装包。
"""

import sys
from pathlib import Path

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))


def check_package(name: str, package_name: str = None) -> tuple[bool, str | None]:
    """尝试导入一个 Python 包
    
    Args:
        name: 模块在代码中使用的名称（如 'yaml'）
        package_name: pip 安装时的包名（如 'pyyaml'），默认与 name 相同
    
    Returns:
        (成功状态，错误信息)
    """
    pkg_name = package_name or name
    
    try:
        # 特殊处理：chromadb 的导入名称不同
        if name == "chromadb":
            import chromadb
            print(f"✅ {pkg_name} ✓")
            return True, None
        
        # 特殊处理：tqdm
        elif name == "tqdm":
            from tqdm import tqdm
            print(f"✅ {pkg_name} ✓")
            return True, None
        
        else:
            __import__(name)
            print(f"✅ {pkg_name} ✓")
            return True, None
            
    except ImportError as e:
        error_msg = f"缺少 '{pkg_name}' 包，请运行：pip install {pkg_name}"
        print(f"❌ {pkg_name}: {error_msg}")
        return False, pkg_name
    except Exception as e:
        error_msg = f"导入失败：{e}"
        print(f"⚠️  {pkg_name}: {error_msg}")
        return False, None


def main():
    """运行依赖检查"""
    
    print("=" * 70)
    print("🔍 AI Novel Analyzer - 依赖安装检查")
    print("=" * 70)
    print()
    
    missing_packages = []
    warnings = []
    
    # ========== 核心必需依赖 ==========
    print("📦 核心必需依赖:")
    print("-" * 70)
    
    core_deps = [
        ("requests", "requests"),
        ("yaml", "pyyaml"),
        ("dotenv", "python-dotenv"),
        ("jsonschema", "jsonschema"),
        ("pydantic", "pydantic"),
        ("chromadb", "chromadb"),
        ("tqdm", "tqdm"),
    ]
    
    for module_name, pip_name in core_deps:
        success, _ = check_package(module_name, pip_name)
        if not success:
            missing_packages.append(pip_name)
    
    print()
    
    # ========== 可选依赖 ==========
    print("✨ 可选依赖:")
    print("-" * 70)
    
    optional_deps = [
        ("tiktoken", "tiktoken"),  # Token 计数（用于长文本分片）
    ]
    
    has_all_optional = True
    for module_name, pip_name in optional_deps:
        success, _ = check_package(module_name, pip_name)
        if not success:
            warnings.append(f"{pip_name}（可选，但推荐安装）")
            has_all_optional = False
    
    print()
    
    # ========== 检查结果总结 ==========
    print("=" * 70)
    print("📊 检查完成！")
    print("=" * 70)
    print()
    
    if not missing_packages:
        print("✅ 所有核心依赖已安装!")
        
        if not warnings:
            print("✅ 所有可选依赖也已安装 - 完美！")
            sys.exit(0)
        
        else:
            # 显示警告但不阻止运行
            for warning in warnings:
                print(f"⚠️  {warning}")
            
            print()
            print("ℹ️  您的环境基本可用，但建议安装上述可选包以获得完整功能")
            sys.exit(0)
    
    else:
        # 有缺失的依赖
        print("❌ 以下关键依赖缺失，请安装后重试：")
        print("-" * 70)
        for pkg in missing_packages:
            print(f"   ⬅️  {pkg}")
        
        print()
        print("💡 一键修复命令:")
        print("-" * 70)
        print("   uv sync")
        print("   或:")
        print("   pip install -r requirements.txt")
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
