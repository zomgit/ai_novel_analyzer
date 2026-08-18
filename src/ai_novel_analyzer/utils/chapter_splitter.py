"""Chapter Splitter Utility

将整卷小说文本自动分割为独立章节。

支持策略:
1. 标题模式匹配: 第X章 / 第X节 / 第X回 / 第X卷 / 章节X / Chapter X 等
2. 中文数字 + 阿拉伯数字 混合支持
3. 兜底策略: 无章节标题时按段落长度均匀切分

用法参见 scripts/split_book.py
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class Chapter:
    """分割后的单个章节"""
    index: int            # 章节序号（从 1 开始）
    title: str            # 章节标题
    content: str          # 正文内容（不含标题行）
    char_count: int = 0   # 正文字符数
    is_fallback: bool = False  # 是否为兜底切分（非标题识别）
    volume_number: int = 1     # 所属卷号
    volume_title: Optional[str] = None  # 所属卷名（如有）
    # 血缘信息（由拆书入口写入，透传到卷/章节元数据）
    project_name: Optional[str] = None
    book_name: Optional[str] = None

    def __post_init__(self):
        if self.char_count == 0:
            self.char_count = len(self.content)


# 中文数字映射（支持到千万级）
_CN_DIGITS = {'零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4,
              '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
_CN_UNITS = {'十': 10, '百': 100, '千': 1000}
_CN_BIG_UNITS = {'万': 10000, '亿': 100000000}


def chinese_numeral_to_int(text: str) -> Optional[int]:
    """将中文数字转换为阿拉伯数字，失败返回 None

    支持: 一 ~ 九千九百九十九万九千九百九十九
    """
    if not text:
        return None

    total = 0      # 累计总值（万/亿以上部分）
    section = 0    # 当前小节（万以内）
    digit = 0      # 当前数字
    matched = False

    for ch in text:
        if ch in _CN_DIGITS:
            digit = _CN_DIGITS[ch]
            matched = True
        elif ch in _CN_UNITS:
            # "十" 开头表示 10（如 "十二"）
            digit = digit if digit > 0 else 1
            section += digit * _CN_UNITS[ch]
            digit = 0
            matched = True
        elif ch in _CN_BIG_UNITS:
            section = (section + digit) * _CN_BIG_UNITS[ch]
            total += section
            section = 0
            digit = 0
            matched = True
        else:
            return None

    return total + section + digit if matched else None


# 分卷标题正则: 第X卷 卷名（单独处理，不作为章节）
VOLUME_PATTERN = re.compile(
    r'^\s*第\s*([0-9０-９]+|[零一二两三四五六七八九十百千万亿]+)\s*卷'
    r'\s*[::\s]?\s*(.{0,60})\s*$'
)

# 默认章节标题正则列表（中文模式，不含英文 Chapter）
# 每条正则必须包含两个捕获组: group(1)=章节编号, group(2)=标题后缀
# 注意: 纯数字编号分隔符不含冒号，避免 "14:00" 等时间表达式被误识别
_DEFAULT_TITLE_PATTERNS: List[str] = [
    r'^\s*第\s*([0-9０-９]+|[零一二两三四五六七八九十百千万亿]+)\s*[章节回部集篇]\s*[::\s]?\s*(.{0,60})\s*$',
    r'^\s*[章节回]\s*([0-9０-９]+|[零一二两三四五六七八九十百千万亿]+)\s*[::\s]?\s*(.{0,60})\s*$',
    r'^\s*(\d{1,4})\s*[.、．,，]\s*(.{1,60})\s*$',
    r'^\s*(序章|楔子|引子|终章|尾声|番外|后记|前言)\s+[::\s]?\s*(.{1,60})\s*$',
]


def compile_title_patterns(patterns: List[str] = None) -> list:
    """将正则字符串列表编译为正则对象列表

    Args:
        patterns: 正则字符串列表，为 None 时使用默认中文模式
    """
    src = patterns if patterns is not None else _DEFAULT_TITLE_PATTERNS
    return [re.compile(p) for p in src]

# 单行最长字符数限制：超过此长度的行不太可能是章节标题
MAX_TITLE_LINE_LENGTH = 80


class ChapterSplitter:
    """小说章节分割器"""

    def __init__(
        self,
        min_chapters: int = 2,
        fallback_segment_chars: int = 3000,
        default_volume: int = 1,
        title_patterns: List[str] = None,
    ):
        """
        Args:
            min_chapters: 标题模式至少需匹配到这么多章节才认为有效，
                          否则回退到兜底切分
            fallback_segment_chars: 兜底切分时每个分段的目标字符数
            default_volume: 未识别到分卷标题时使用的卷号
            title_patterns: 章节标题正则字符串列表，为 None 时使用默认中文模式
        """
        self.min_chapters = min_chapters
        self.fallback_segment_chars = fallback_segment_chars
        self.default_volume = default_volume
        self.title_patterns = compile_title_patterns(title_patterns)

    # ---------- 公开接口 ----------

    def split_text(self, text: str) -> List[Chapter]:
        """将整卷文本分割为章节列表

        优先使用标题模式识别；识别失败则按长度兜底切分。
        """
        text = self._normalize(text)
        chapters = self._split_by_title_patterns(text)

        if len(chapters) >= self.min_chapters:
            return self._finalize(chapters)

        return self._fallback_split(text)

    def split_file(self, file_path: Path, encoding: Optional[str] = None) -> List[Chapter]:
        """从文件读取并分割，自动探测编码（utf-8 / gb18030 / gbk）"""
        text = self.read_text_file(file_path, encoding)
        return self.split_text(text)

    # ---------- 文件读取 ----------

    @staticmethod
    def read_text_file(file_path: Path, encoding: Optional[str] = None) -> str:
        """读取文本文件，支持编码自动探测"""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        if encoding:
            return file_path.read_text(encoding=encoding, errors='replace')

        for enc in ('utf-8', 'gb18030', 'gbk', 'big5'):
            try:
                return file_path.read_text(encoding=enc)
            except UnicodeDecodeError:
                continue

        # 全部失败则用 utf-8 强制替换
        return file_path.read_text(encoding='utf-8', errors='replace')

    # ---------- 内部实现 ----------

    @staticmethod
    def _normalize(text: str) -> str:
        """统一换行符、去除 BOM"""
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        if text.startswith('\ufeff'):
            text = text[1:]
        return text

    def _split_by_title_patterns(self, text: str) -> List[Chapter]:
        """基于标题正则切分，同时跟踪分卷结构"""
        lines = text.split('\n')
        marks = []  # [(line_index, chapter_title, volume_number, volume_title)]

        current_volume = self.default_volume
        current_volume_title: Optional[str] = None

        for i, line in enumerate(lines):
            if len(line) > MAX_TITLE_LINE_LENGTH:
                continue

            # 分卷标题行: 更新当前卷，不作为章节输出
            vm = VOLUME_PATTERN.match(line)
            if vm:
                number_str = vm.group(1).translate(
                    str.maketrans('０１２３４５６７８９', '0123456789'))
                if number_str.isdigit():
                    current_volume = int(number_str)
                else:
                    converted = chinese_numeral_to_int(number_str)
                    current_volume = converted if converted else current_volume + 1
                current_volume_title = (vm.group(2) or '').strip() or None
                continue

            for pattern in self.title_patterns:
                m = pattern.match(line)
                if m:
                    number_str, suffix = m.group(1), (m.group(2) or '').strip()
                    title = self._build_title(line, number_str, suffix)
                    marks.append((i, title, current_volume, current_volume_title))
                    break

        if len(marks) < self.min_chapters:
            return []

        chapters = []
        for idx, (line_no, title, vol_num, vol_title) in enumerate(marks):
            end = marks[idx + 1][0] if idx + 1 < len(marks) else len(lines)
            content = '\n'.join(lines[line_no + 1:end]).strip()
            chapters.append(Chapter(
                index=idx + 1,
                title=title,
                content=content,
                volume_number=vol_num,
                volume_title=vol_title,
            ))

        return chapters

    @staticmethod
    def _build_title(raw_line: str, number_str: str, suffix: str) -> str:
        """构建规范化标题，中文数字统一转换为阿拉伯数字"""
        # 全角数字转半角
        number_str = number_str.translate(str.maketrans('０１２３４５６７８９', '0123456789'))

        if number_str.isdigit():
            number = int(number_str)
        else:
            converted = chinese_numeral_to_int(number_str)
            number = converted if converted is not None else 0

        title_body = raw_line.strip()
        if number > 0 and suffix:
            return f"第{number}章 {suffix}"
        if number > 0:
            return title_body
        return title_body

    # 句子边界切分正则（用于超长段落内部切分）
    _sentence_split_re = re.compile(r'(?<=[。！？!?…])')

    def _fallback_split(self, text: str) -> List[Chapter]:
        """兜底切分: 按段落聚合到目标字符数，避免切断段落/句子"""
        paragraphs = self._extract_paragraphs(text)
        if not paragraphs:
            return []

        chapters = []
        buffer: List[str] = []
        buffer_len = 0

        for para in paragraphs:
            buffer.append(para)
            buffer_len += len(para)
            if buffer_len >= self.fallback_segment_chars:
                chapters.append(Chapter(
                    index=len(chapters) + 1,
                    title=f"分段 {len(chapters) + 1}",
                    content='\n\n'.join(buffer),
                    is_fallback=True,
                    volume_number=self.default_volume,
                ))
                buffer, buffer_len = [], 0

        if buffer:
            chapters.append(Chapter(
                index=len(chapters) + 1,
                title=f"分段 {len(chapters) + 1}",
                content='\n\n'.join(buffer),
                is_fallback=True,
                volume_number=self.default_volume,
            ))

        return chapters

    def _extract_paragraphs(self, text: str) -> List[str]:
        """提取段落；对超长段落按句子边界进一步切分，避免无法拆分"""
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]

        # 单个段落超过目标长度 2 倍时，按句号/叹号等句子边界拆分
        threshold = self.fallback_segment_chars * 2
        expanded: List[str] = []
        for para in paragraphs:
            if len(para) <= threshold:
                expanded.append(para)
                continue
            sentences = [s for s in self._sentence_split_re.split(para) if s]
            buffer = ''
            for sentence in sentences:
                buffer += sentence
                if len(buffer) >= self.fallback_segment_chars:
                    expanded.append(buffer)
                    buffer = ''
            if buffer:
                expanded.append(buffer)

        return expanded

    @staticmethod
    def _finalize(chapters: List[Chapter]) -> List[Chapter]:
        """清理空章节、重排序号"""
        result = []
        for ch in chapters:
            if ch.content.strip():
                ch.index = len(result) + 1
                ch.char_count = len(ch.content)
                result.append(ch)
        return result


def split_novel_file(
    input_path: Path,
    encoding: Optional[str] = None,
    min_chapters: int = 2,
    fallback_segment_chars: int = 3000,
    default_volume: int = 1,
    title_patterns: List[str] = None,
) -> List[Chapter]:
    """便捷函数: 分割整卷小说文件"""
    splitter = ChapterSplitter(
        min_chapters=min_chapters,
        fallback_segment_chars=fallback_segment_chars,
        default_volume=default_volume,
        title_patterns=title_patterns,
    )
    return splitter.split_file(Path(input_path), encoding)
