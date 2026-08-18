#!/usr/bin/env python3
"""进度查看工具

递归扫描 workspace/projects/（或指定项目目录），
读取三级 JSON 元数据统计各卷的处理进度。只读，不修改任何文件。

用法:
    # 查看全部项目的进度
    uv run python scripts/check_progress.py

    # 只看某个项目
    uv run python scripts/check_progress.py workspace/projects/我的项目
"""

import argparse
import json
import sys
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

STATUS_ICONS = {
    'processed': '✅',
    'pending': '⏳',
    'failed': '❌',
    'processing': '🔄',
}


def load_json(path: Path):
    """读取 JSON，失败返回 None（utf-8-sig 兼容带 BOM 的文件）"""
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception:
        return None


def scan_volume(volume_dir: Path) -> dict:
    """统计单个卷的进度（元数据状态与磁盘配对情况互相印证）"""
    meta = load_json(volume_dir / "volume_meta.json")

    txt_files = set(p.stem for p in volume_dir.glob("chap_*.txt"))
    json_files = set(p.stem for p in volume_dir.glob("chap_*.json"))

    stats = {'processed': 0, 'pending': 0, 'failed': 0, 'other': 0, 'orphan_json': 0}

    # 有 txt 的章节：按配对 json 的 status 归类
    for stem in txt_files:
        if stem not in json_files:
            stats['pending'] += 1
            continue
        data = load_json(volume_dir / f"{stem}.json") or {}
        status = data.get('status', 'processed')
        if status in stats:
            stats[status] += 1
        else:
            stats['other'] += 1

    # 只有 json 没有 txt 的异常文件
    stats['orphan_json'] = len(json_files - txt_files)

    if meta:
        stats['volume_title'] = meta.get('volume_title', '')
        stats['book_name'] = meta.get('book_name', '')
        stats['project_name'] = meta.get('project_name', '')
    return stats


def scan_book(book_dir: Path) -> dict:
    """扫描一本书的所有卷"""
    meta = load_json(book_dir / "book_meta.json") or {}
    volumes = []
    for vol_dir in sorted(book_dir.glob("vol_*")):
        if vol_dir.is_dir():
            volumes.append((vol_dir.name, scan_volume(vol_dir)))
    return {'author': meta.get('author', '?'), 'volumes': volumes}


def scan_project(project_dir: Path) -> dict:
    """扫描一个项目的所有书"""
    meta = load_json(project_dir / "project_meta.json") or {}
    books = []
    for book_dir in sorted(p for p in project_dir.iterdir() if p.is_dir()):
        # 跳过 source 等非书籍目录（书籍目录下应有 book_meta.json 或 vol_* 子目录）
        if (book_dir / "book_meta.json").exists() or any(book_dir.glob("vol_*")):
            books.append((book_dir.name, scan_book(book_dir)))
    return {'meta': meta, 'books': books}


def main():
    parser = argparse.ArgumentParser(description="查看 workspace 项目处理进度")
    parser.add_argument(
        'target', nargs='?', default=None,
        help='项目目录路径（缺省扫描整个 projects 目录）'
    )
    args = parser.parse_args()

    config = get_config()

    if args.target:
        target = Path(args.target)
        if not target.exists():
            print(f"错误：目录不存在：{target}")
            sys.exit(1)
        project_dirs = [target]
    else:
        projects_dir = config.projects_dir
        if not projects_dir.exists() or not any(projects_dir.iterdir()):
            print(f"projects 目录为空：{projects_dir}")
            print("请先运行 scripts/split_book.py 拆书创建项目")
            return
        project_dirs = sorted(p for p in projects_dir.iterdir() if p.is_dir())

    grand_total = {'processed': 0, 'pending': 0, 'failed': 0, 'total': 0}

    for project_dir in project_dirs:
        project = scan_project(project_dir)
        meta = project['meta']
        print()
        print("=" * 64)
        print(f"📁 项目：{project_dir.name}"
              f"    维度配置：{meta.get('dimension_config', '?')}")
        print("=" * 64)

        if not project['books']:
            print("  （暂无书籍，请先运行 scripts/split_book.py 拆书）")
            continue

        for book_name, book in project['books']:
            print(f"\n  📖 {book_name}（作者：{book['author']}）")

            if not book['volumes']:
                print("     （暂无卷目录）")
                continue

            for vol_dirname, stats in book['volumes']:
                total = stats['processed'] + stats['pending'] + \
                    stats['failed'] + stats['other']
                grand_total['processed'] += stats['processed']
                grand_total['pending'] += stats['pending']
                grand_total['failed'] += stats['failed']
                grand_total['total'] += total

                percent = (stats['processed'] / total * 100) if total else 0.0
                bar = f"{stats['processed']}/{total}".rjust(9)
                print(f"     📚 {vol_dirname:<28} {bar} ({percent:5.1f}%)")

                details = []
                if stats['pending']:
                    details.append(f"⏳ 待处理 {stats['pending']}")
                if stats['failed']:
                    details.append(f"❌ 失败 {stats['failed']}")
                if stats['orphan_json']:
                    details.append(f"⚠️ 孤立 JSON（无配对 txt）{stats['orphan_json']}")
                if details:
                    print(f"        {'  '.join(details)}")

    # 总进度
    if grand_total['total']:
        print()
        print("=" * 64)
        percent = grand_total['processed'] / grand_total['total'] * 100
        print(f"总计：{grand_total['processed']}/{grand_total['total']} 章已处理 "
              f"({percent:.1f}%)")
        if grand_total['pending']:
            print(f"  ⏳ 待处理：{grand_total['pending']}")
        if grand_total['failed']:
            print(f"  ❌ 失败（重跑 batch_processor.py 即可重试）：{grand_total['failed']}")
        print("=" * 64)


if __name__ == "__main__":
    main()
