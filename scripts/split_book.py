#!/usr/bin/env python3
"""拆书工具（workspace 结构版）

将原始小说 txt 拆分为章节，按新目录结构落位：

    workspace/projects/{项目名}/{书名}/
    ├── book_meta.json
    ├── source/{原始文件名}            # 原始文件副本（仅溯源）
    └── vol_{NNN}_{卷名}/
        ├── volume_meta.json
        ├── chap_0001.txt              # 章节源文本
        └── ...

同时创建/更新三级 JSON 元数据（project / book / volume）。
书名、作者、项目名全部为必填入参——绝不从原始文件名猜测。

用法:
    uv run python scripts/split_book.py \
        -i 某小说.txt --project 我的项目 --book 书名 --author 作者名

    # 预览模式：只显示分割结果，不写入任何文件
    uv run python scripts/split_book.py -i 某小说.txt \
        --project 我的项目 --book 书名 --author 佚名 --preview

    # 手动指定卷名 / 卷号（原文未识别到"第X卷"时使用）
    uv run python scripts/split_book.py -i 某小说.txt \
        --project 我的项目 --book 书名 --author 佚名 \
        --volume-title 第一册 --volume-number 1
"""

import argparse
import json
import re
import shutil
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

# Windows GBK 控制台兼容：避免 emoji/特殊字符输出时报错
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# 确保可以直接 python 运行（无需安装）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ai_novel_analyzer.core.config_manager import get_config
from ai_novel_analyzer.utils.chapter_splitter import ChapterSplitter

# 单册书的默认卷名（原文未识别到分卷标题且未手动指定时）
DEFAULT_VOLUME_TITLE = "单册"


def sanitize_dirname(name: str, max_len: int = 30) -> str:
    """清理目录名中的非法字符
    
    Args:
        name: 待清理的名称（可以为 None）
        max_len: 最大长度
        
    Returns:
        清理后的名称，如果输入为 None 或空则返回 'untitled'
    """
    if name is None:
        return 'untitled'
    name = str(name)
    name = re.sub(r'[\\/:*?"<>|\r\n]', '_', name)
    name = name.strip(' ._')
    return name[:max_len] if name else 'untitled'


def now_iso() -> str:
    """当前 UTC 时间（ISO 8601）"""
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict:
    """读取 JSON 元数据文件（utf-8-sig 兼容带 BOM 的文件）"""
    with open(path, 'r', encoding='utf-8-sig') as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    """写入 JSON 元数据文件（覆盖）"""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def group_chapters_by_volume(chapters):
    """按卷号分组，卷内章节从 1 重新编号

    Returns:
        OrderedDict: {volume_number: [(新章节号, Chapter), ...]}
    """
    groups = OrderedDict()
    counters = {}
    for ch in sorted(chapters, key=lambda c: (c.volume_number, c.index)):
        groups.setdefault(ch.volume_number, [])
        counters[ch.volume_number] = counters.get(ch.volume_number, 0) + 1
        groups[ch.volume_number].append((counters[ch.volume_number], ch))
    return groups


def build_volume_dirname(volume_number: int, volume_title: str) -> str:
    """卷目录名：vol_{NNN}_{卷名}"""
    return f"vol_{volume_number:03d}_{sanitize_dirname(volume_title)}"


def write_volume(
    book_dir: Path,
    volume_number: int,
    volume_title: str,
    volume_chapters,
    project_name: str,
    book_name: str,
    overwrite: bool = False,
    volume_author: str = ""
) -> str:
    """写入单个卷的章节文件与卷元数据

    Args:
        volume_chapters: [(卷内新章节号，Chapter), ...]
        volume_author: 卷作者（可为空，为空时使用书籍作者）

    Returns:
        卷目录名
    """
    vol_dirname = build_volume_dirname(volume_number, volume_title)
    vol_dir = book_dir / vol_dirname

    meta_path = vol_dir / "volume_meta.json"
    if meta_path.exists() and not overwrite:
        raise FileExistsError(
            f"卷目录已存在：{vol_dir}\n"
            f"    若确认重新拆书，请加 --overwrite 覆盖"
        )

    vol_dir.mkdir(parents=True, exist_ok=True)

    # 写入章节源文本
    chapter_records = []
    for chap_num, ch in volume_chapters:
        chap_file = vol_dir / f"chap_{chap_num:04d}.txt"
        chap_file.write_text(f"{ch.title}\n\n{ch.content}\n", encoding='utf-8')
        chapter_records.append({
            "number": chap_num,
            "title": ch.title,
            "status": "pending",
            "char_count": getattr(ch, "char_count", 0) or len(ch.content)
        })

    # 卷元数据（含上级名称血缘快照 + 卷作者）
    volume_meta = {
        "project_name": project_name,
        "book_name": book_name,
        "volume_number": volume_number,
        "volume_title": volume_title,
        "volume_author": volume_author,
        "chapters": chapter_records,
        "created_at": now_iso(),
        "updated_at": now_iso()
    }
    save_json(meta_path, volume_meta)

    return vol_dirname


def upsert_book_meta(book_dir: Path, book_name: str, author: str,
                     source_filename: str, volume_dirnames: list,
                     volume_titles: dict = None) -> None:
    """创建或更新书籍元数据

    volumes 字段为对象数组（JSON 顺序即卷顺序）：
        [{"name": 卷名, "dir": 卷目录名, "chapter_count": 章节数}, ...]
    兼容旧数据（字符串数组）：读取时自动升级为对象数组。

    Args:
        volume_dirnames: 本次写入的卷目录名列表
        volume_titles: {卷目录名: 卷名}（用于升级旧数据时回填名称）
    """
    volume_titles = volume_titles or {}
    meta_path = book_dir / "book_meta.json"
    if meta_path.exists():
        meta = load_json(meta_path)
        # 兼容旧数据：字符串数组升级为对象数组
        if meta.get("volumes") and isinstance(meta["volumes"][0], str):
            upgraded = []
            for item in meta["volumes"]:
                vol_meta_path = book_dir / item / "volume_meta.json"
                if vol_meta_path.exists():
                    try:
                        vol_meta = load_json(vol_meta_path)
                        upgraded.append({
                            "name": vol_meta.get("volume_title", ""),
                            "dir": item,
                            "chapter_count": len(vol_meta.get("chapters", []))
                        })
                    except Exception:
                        upgraded.append({"name": "", "dir": item, "chapter_count": 0})
                else:
                    upgraded.append({"name": "", "dir": item, "chapter_count": 0})
            meta["volumes"] = upgraded
    else:
        meta = {
            "book_name": book_name,
            "author": author,
            "source_files": [],
            "volumes": [],
            "created_at": now_iso()
        }

    meta.setdefault("volumes", [])
    existing_dirs = {v["dir"] for v in meta["volumes"] if isinstance(v, dict)}

    # 合并源文件与卷列表（保持顺序、去重）
    source_rel = f"source/{source_filename}"
    if source_rel not in meta.get("source_files", []):
        meta.setdefault("source_files", []).append(source_rel)
    for vol_dirname in volume_dirnames:
        if vol_dirname in existing_dirs:
            continue
        vol_meta_path = book_dir / vol_dirname / "volume_meta.json"
        name = volume_titles.get(vol_dirname, "")
        chapter_count = 0
        if vol_meta_path.exists():
            try:
                vol_meta = load_json(vol_meta_path)
                name = name or vol_meta.get("volume_title", "")
                chapter_count = len(vol_meta.get("chapters", []))
            except Exception:
                pass
        meta["volumes"].append({
            "name": name,
            "dir": vol_dirname,
            "chapter_count": chapter_count
        })
        existing_dirs.add(vol_dirname)

    meta["author"] = author
    meta["updated_at"] = now_iso()
    save_json(meta_path, meta)


def upsert_project_meta(project_dir: Path, project_name: str,
                        book_name: str, dimension_config: str) -> None:
    """创建或更新项目元数据"""
    meta_path = project_dir / "project_meta.json"
    if meta_path.exists():
        meta = load_json(meta_path)
        if meta.get("dimension_config") != dimension_config:
            print(
                f"[警告] 项目已配置维度 {meta.get('dimension_config')}，"
                f"忽略本次 --dimension-config={dimension_config}"
            )
    else:
        meta = {
            "project_name": project_name,
            "description": "",
            "dimension_config": dimension_config,
            "books": [],
            "created_at": now_iso()
        }

    if book_name not in meta["books"]:
        meta["books"].append(book_name)
    meta["updated_at"] = now_iso()
    save_json(meta_path, meta)


def assemble_workspace(
    chapters,
    input_path: Path,
    project: str,
    book: str,
    author: str,
    dimension_config: str = 'xianxia.yaml',
    volumes_data: list = None,
    volume_title_fallback: str = None,
    overwrite: bool = False,
) -> dict:
    """将已分割的章节写入 workspace 项目结构 + 三级元数据

    统一的组装入口：CLI (split_book) 与 WebUI (api_splitter) 均调用此函数，
    保证目录结构和元数据格式完全一致。

    Args:
        chapters: Chapter 对象列表（由 ChapterSplitter 产出）
        input_path: 原始小说 txt 路径（用于复制源文件）
        project: 项目名
        book: 书名
        author: 作者名
        dimension_config: 维度配置文件名
        volumes_data: 每卷用户指定信息 [{name, author}, ...]（可选）
        volume_title_fallback: 未识别卷名时的默认卷名（默认 DEFAULT_VOLUME_TITLE）
        overwrite: 是否覆盖已有卷目录

    Returns:
        {book_dir, volume_dirnames, chapters_count, groups}
    """
    volumes_data = volumes_data or []
    volume_title_fallback = volume_title_fallback or DEFAULT_VOLUME_TITLE

    config = get_config()
    projects_dir = config.projects_dir

    groups = group_chapters_by_volume(chapters)

    project_dir = projects_dir / sanitize_dirname(project)
    book_dir = project_dir / sanitize_dirname(book)
    book_dir.mkdir(parents=True, exist_ok=True)

    # 1. 原始文件副本（仅溯源）
    source_dir = book_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(input_path, source_dir / input_path.name)

    # 2. 各卷章节文件 + 卷元数据
    volume_dirnames = []
    title_map = {}
    for idx, (volume_number, volume_chapters) in enumerate(groups.items()):
        recognized_title = next(
            (ch.volume_title for _, ch in volume_chapters if ch.volume_title), None
        )
        # 用户指定卷名 > 识别卷名 > 兜底默认
        user_title = ''
        volume_author = ''
        if idx < len(volumes_data) and isinstance(volumes_data[idx], dict):
            user_title = volumes_data[idx].get('name', '') or ''
            volume_author = volumes_data[idx].get('author', '') or ''
        volume_title = user_title or recognized_title or volume_title_fallback

        vol_dirname = write_volume(
            book_dir=book_dir,
            volume_number=volume_number,
            volume_title=volume_title,
            volume_chapters=volume_chapters,
            project_name=project,
            book_name=book,
            overwrite=overwrite,
            volume_author=volume_author,
        )
        volume_dirnames.append(vol_dirname)
        title_map[vol_dirname] = volume_title

    # 3. 书籍元数据
    upsert_book_meta(book_dir, book, author, input_path.name, volume_dirnames, title_map)

    # 4. 项目元数据
    upsert_project_meta(project_dir, project, book, dimension_config)

    return {
        'book_dir': book_dir,
        'volume_dirnames': volume_dirnames,
        'chapters_count': len(chapters),
        'groups': groups,
    }


def main():
    parser = argparse.ArgumentParser(
        description="拆书：原始 txt → workspace 项目结构（章节文件 + 三级元数据）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('-i', '--input', required=True, help='原始小说 txt 文件路径')
    parser.add_argument('--project', required=True, help='所属项目名（不存在则新建）')
    parser.add_argument('--book', required=True, help='书名（必填，不从文件名猜测）')
    parser.add_argument('--author', required=True, help='作者名（必填，未知可填"佚名"）')
    parser.add_argument('--volume-title', default=None,
                        help='原文未识别到"第X卷"时使用的卷名（默认: 单册）')
    parser.add_argument('--volume-number', type=int, default=1,
                        help='原文未分卷时使用的卷号（默认: 1）')
    parser.add_argument('--dimension-config', default='xianxia.yaml',
                        help='项目维度配置文件名（默认: xianxia.yaml）')
    parser.add_argument('--encoding', default=None,
                        help='输入文件编码（默认自动探测）')
    parser.add_argument('--fallback-chars', type=int, default=3000,
                        help='无章节标题时，每个分段的目标字符数（默认: 3000）')
    parser.add_argument('--overwrite', action='store_true',
                        help='允许覆盖已存在的卷目录')
    parser.add_argument('--preview', action='store_true',
                        help='预览模式：只显示分割结果，不写入文件')
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误：输入文件不存在：{input_path}")
        sys.exit(1)

    # 加载配置
    config = get_config()
    splitting_config = config.get('chapter_splitting.title_patterns')

    # 分割章节
    print(f"读取文件：{input_path}")
    splitter = ChapterSplitter(
        fallback_segment_chars=args.fallback_chars,
        default_volume=args.volume_number,
        title_patterns=splitting_config,
    )
    chapters = splitter.split_file(input_path, args.encoding)

    if not chapters:
        print("错误：未能从文件中分割出任何章节（文件为空?）")
        sys.exit(1)

    # 卷标题：用户指定 > splitter 识别 > 默认“单册”
    default_title = args.volume_title or DEFAULT_VOLUME_TITLE
    
    groups = group_chapters_by_volume(chapters)
    total_chars = sum(ch.char_count for ch in chapters)
    
    print()
    print("=" * 60)
    print(f"分割模式：{'兜底按长度切分（未识别到章节标题）' if chapters[0].is_fallback else '章节标题识别'}")
    print(f"共分割出 {len(chapters)} 章，正文总计 {total_chars:,} 字符")
    print(f"项目：{args.project}    书名：{args.book}    作者：{args.author}")
    print("=" * 60)
    
    for volume_number, volume_chapters in groups.items():
        recognized_title = next(
            (ch.volume_title for _, ch in volume_chapters if ch.volume_title), None
        )
        volume_title = recognized_title or default_title
        vol_dirname = build_volume_dirname(volume_number, volume_title)
    
        print(f"\n[{vol_dirname}] {len(volume_chapters)} 章")
        print(f"{'章':>4}  {'标题':<32} {'字符数':>8}")
        print("-" * 52)
        for chap_num, ch in volume_chapters:
            print(f"{chap_num:>4}  {ch.title[:30]:<32} {ch.char_count:>8,}")
    
    if args.preview:
        print("\n（预览模式，未写入文件）")
        return
    
    # ===== 写入阶段（统一入口） =====
    result = assemble_workspace(
        chapters=chapters,
        input_path=input_path,
        project=args.project,
        book=args.book,
        author=args.author,
        dimension_config=args.dimension_config,
        volume_title_fallback=default_title,
        overwrite=args.overwrite,
    )
    
    print()
    print("=" * 60)
    print("[完成] 拆书成功：{} 章 → {} 卷".format(result['chapters_count'], len(result['volume_dirnames'])))
    print(f"   书籍目录：{result['book_dir']}")
    for dirname in result['volume_dirnames']:
        print(f"   卷目录：{result['book_dir'] / dirname}")
    print(f"\n下一步：对每个卷目录执行批量分析（batch_processor.py）")


if __name__ == "__main__":
    main()
