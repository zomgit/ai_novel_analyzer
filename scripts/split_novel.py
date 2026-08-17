"""整卷小说章节分割命令行工具

用法:
    # 基本用法: 分割并输出到 output/chapters/
    python scripts/split_novel.py -i 小说全文.txt

    # 指定输出目录与编码
    python scripts/split_novel.py -i 小说全文.txt -o D:/novel/chapters --encoding gbk

    # 预览模式: 只显示识别结果，不写文件
    python scripts/split_novel.py -i 小说全文.txt --preview

    # 调整兜底切分的段落大小（无章节标题的纯文本）
    python scripts/split_novel.py -i 小说全文.txt --fallback-chars 5000

    # 原小说未分卷时，手动指定卷号（默认 1）
    python scripts/split_novel.py -i 小说全文.txt --volume 3

分卷处理:
    - 原文有 "第X卷 卷名" 标题行时，自动识别并归属章节到对应卷，
      卷标题行本身不作为章节输出
    - 原文无分卷时，所有章节归入 --volume 指定的卷（默认卷1）

输出:
    <输出目录>/vol_<卷号>_chap_<章节号>_<标题>.txt   每章一个文件
    <输出目录>/manifest.json                        章节清单（卷号/序号/标题/字符数）
"""

import argparse
import json
import re
import sys
from pathlib import Path

# 确保可以直接 python 运行（无需安装）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ai_novel_analyzer.utils.chapter_splitter import ChapterSplitter


def sanitize_filename(title: str, max_len: int = 30) -> str:
    """清理文件名中的非法字符"""
    title = re.sub(r'[\\/:*?"<>|\r\n]', '_', title)
    title = title.strip(' ._')
    return title[:max_len] if title else 'untitled'


def main():
    parser = argparse.ArgumentParser(
        description="将整卷小说 txt 自动分割为章节文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('-i', '--input', required=True, help='输入的小说全文 txt 路径')
    parser.add_argument('-o', '--output', default='output/chapters',
                        help='输出目录 (默认: output/chapters)')
    parser.add_argument('--encoding', default=None,
                        help='输入文件编码，如 utf-8 / gbk / gb18030（默认自动探测）')
    parser.add_argument('--fallback-chars', type=int, default=3000,
                        help='无章节标题时，每个分段的目标字符数 (默认: 3000)')
    parser.add_argument('--volume', type=int, default=1,
                        help='原文未分卷时使用的卷号 (默认: 1)；'
                             '原文有"第X卷"标题时自动识别，此参数作为识别前的默认值')
    parser.add_argument('--preview', action='store_true',
                        help='预览模式: 只显示分割结果统计，不写入文件')
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误: 输入文件不存在: {input_path}")
        sys.exit(1)

    splitter = ChapterSplitter(
        fallback_segment_chars=args.fallback_chars,
        default_volume=args.volume,
    )

    print(f"读取文件: {input_path}")
    chapters = splitter.split_file(input_path, args.encoding)

    if not chapters:
        print("错误: 未能从文件中分割出任何章节（文件为空?）")
        sys.exit(1)

    total_chars = sum(ch.char_count for ch in chapters)
    is_fallback = chapters[0].is_fallback
    volumes = sorted({ch.volume_number for ch in chapters})

    print()
    print("=" * 60)
    print(f"分割模式: {'兜底按长度切分（未识别到章节标题）' if is_fallback else '章节标题识别'}")
    print(f"共分割出 {len(chapters)} 章，正文总计 {total_chars:,} 字符")
    if len(volumes) > 1:
        print(f"识别到 {len(volumes)} 个分卷: {volumes}")
    else:
        vol_title = next((c.volume_title for c in chapters if c.volume_title), None)
        suffix = f"（{vol_title}）" if vol_title else "（未识别到分卷标题，使用默认卷号）"
        print(f"所属卷号: 卷{volumes[0]}{suffix}")
    print("=" * 60)
    print(f"{'卷':>3} {'序号':>4}  {'标题':<32} {'字符数':>8}")
    print("-" * 60)
    for ch in chapters:
        print(f"{ch.volume_number:>3} {ch.index:>4}  {ch.title[:30]:<32} {ch.char_count:>8,}")

    if args.preview:
        print("\n(预览模式，未写入文件)")
        return

    # 写入章节文件
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    for ch in chapters:
        safe_title = sanitize_filename(ch.title)
        filename = f"vol_{ch.volume_number}_chap_{ch.index:04d}_{safe_title}.txt"
        file_path = output_dir / filename
        # 标题行 + 正文
        file_path.write_text(f"{ch.title}\n\n{ch.content}\n", encoding='utf-8')
        manifest.append({
            "volume_number": ch.volume_number,
            "volume_title": ch.volume_title,
            "index": ch.index,
            "title": ch.title,
            "file": filename,
            "char_count": ch.char_count,
        })

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    print(f"\n已写入 {len(chapters)} 个章节文件到: {output_dir}")
    print(f"清单文件: {manifest_path}")
    print(f"\n下一步: 用 batch_processor.py 批量处理这些章节文件")


if __name__ == '__main__':
    main()
