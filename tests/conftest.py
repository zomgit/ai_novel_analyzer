"""
Pytest configuration and shared fixtures for all tests.
"""

import pytest
from pathlib import Path


@pytest.fixture(scope="session")
def base_dir() -> Path:
    """返回项目根目录"""
    return Path(__file__).parent.parent.parent


@pytest.fixture(scope="session")
def config_dir(base_dir: Path) -> Path:
    """返回 config 目录"""
    return base_dir / "config"


@pytest.fixture
def sample_chapter_file(config_dir: Path, tmp_path: Path):
    """创建一个测试用的章节文件"""
    content = """# Chapter 1

Some chapter content here...
"""
    file = tmp_path / "vol_1_chap_1.txt"
    file.write_text(content, encoding="utf-8")
    return file
