#!/usr/bin/env python3
"""
API Splitter - 为 Web UI 提供的轻量级拆书工具
- process_novel_upload: 只执行分割预览，不写入文件
- finalize_split_to_workspace: 确认后调用 assemble_workspace() 统一写盘
"""

import sys
from pathlib import Path

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ai_novel_analyzer.utils.chapter_splitter import ChapterSplitter
from ai_novel_analyzer.core.config_manager import get_config
from scripts.split_book import (
    DEFAULT_VOLUME_TITLE,
    sanitize_dirname,
    assemble_workspace,
)


class ChapterInfo:
    """章节信息数据结构"""
    def __init__(self, chunk_name: str, preview: str, char_count: int):
        self.chunk_name = chunk_name
        self.preview = preview
        self.char_count = char_count
    
    def model_dump_json(self) -> dict:
        """转换为字典格式（JSON 兼容）"""
        return {
            "chunk_name": self.chunk_name,
            "preview": self.preview,
            "char_count": self.char_count
        }


class SplitResult:
    """拆分结果"""
    def __init__(self, encoding: str, total_chars: int, chapters: list):
        self.encoding = encoding
        self.total_chars = total_chars
        self.chapters_preview = [chap.model_dump_json() for chap in chapters[:50]]  # 仅返回前 50 章
        self.total_chapters = len(chapters)
        self.book_info = {}  # 暂未实现
        self.status = "preview_only"  # 仅预览模式
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "encoding": self.encoding,
            "total_chars": self.total_chars,
            "chapters_preview": self.chapters_preview,
            "total_chapters": self.total_chapters,
            "book_info": self.book_info,
            "status": self.status
        }


def process_novel_upload(file_path: str) -> SplitResult:
    """处理上传的小说文件并预览拆分结果
    
    Args:
        file_path: 小说 txt 文件路径
        
    Returns:
        SplitResult: 包含预览数据和统计信息
    """
    print(f"[Web UI] 正在处理文件：{file_path}")
    
    input_path = Path(file_path)
    if not input_path.exists():
        raise ValueError(f"文件不存在：{file_path}")
    
    # 读取文件内容（自动检测编码）
    try:
        content = input_path.read_text(encoding='utf-8')
        encoding = 'utf-8'
    except UnicodeDecodeError:
        try:
            content = input_path.read_text(encoding='gbk')
            encoding = 'gbk'
        except Exception as e:
            raise ValueError(f"无法解码文件：请检查文件编码")
    
    print(f"[Web UI] 编码识别：{encoding}, 字符数：{len(content)}")
    
    # 分割章节
    config = get_config()
    title_patterns = config.get('chapter_splitting.title_patterns')
    splitter = ChapterSplitter(
        fallback_segment_chars=3000,  # 兜底按长度切分
        default_volume=1,
        title_patterns=title_patterns,
    )
    chapters = splitter.split_file(input_path, encoding)
    
    if not chapters:
        raise ValueError("未能从文件中分割出任何章节")
    
    # 构建结果对象
    chapter_infos = []
    for ch in chapters:
        # 创建简化版章节信息（避免序列化问题）
        # 注意：ch.title 本身已含章节号（如 "第6章 游牧部落"），不再拼接前缀
        info = ChapterInfo(
            chunk_name=ch.title,
            preview=ch.content[:50],  # 仅取前 50 字用于预览
            char_count=ch.char_count
        )
        chapter_infos.append(info)
    
    result = SplitResult(
        encoding=encoding,
        total_chars=len(content),
        chapters=chapter_infos
    )
    
    print(f"[Web UI] 成功分割 {len(chapters)} 章")
    return result


def finalize_split_to_workspace(
    file_path: str,
    project: str,
    book: str,
    author: str,
    overwrite: bool = False,
    dimension_config: str = "xianxia.yaml",
    volumes_data: list = None,
    start_volume_number: int = 1,
) -> dict:
    """确认拆分：调用 assemble_workspace() 统一写盘

    Args:
        volumes_data: [{name, author}, ...] 用户填写的卷信息与作者列表
        start_volume_number: 起始卷号（用于追加卷时避免目录冲突）

    Returns:
        {"book_dir", "volumes": [...], "chapters_count"}
    """
    input_path = Path(file_path)
    config = get_config()
    title_patterns = config.get('chapter_splitting.title_patterns')

    # 分割章节
    splitter = ChapterSplitter(
        fallback_segment_chars=3000,
        default_volume=start_volume_number,
        title_patterns=title_patterns,
    )
    chapters = splitter.split_file(input_path, None)
    if not chapters:
        raise ValueError("未能从文件中分割出任何章节")

    # 统一组装写入
    result = assemble_workspace(
        chapters=chapters,
        input_path=input_path,
        project=project,
        book=book,
        author=author,
        dimension_config=dimension_config,
        volumes_data=volumes_data,
        overwrite=overwrite,
    )

    return {
        "book_dir": str(result['book_dir']),
        "volumes": result['volume_dirnames'],
        "chapters_count": result['chapters_count'],
    }


if __name__ == "__main__":
    # 测试用
    import json
    import sys
    
    if len(sys.argv) < 2:
        print("用法：python api_splitter.py <txt 文件路径>")
        sys.exit(1)
    
    try:
        result = process_novel_upload(sys.argv[1])
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"错误：{e}")
        sys.exit(1)
