"""
Test Run CLI: Chapter Processor Single/Batch Testing
Usage (PowerShell):
  uv run scripts/test_run.py --input "output/_test_in" --output "output/_test_out" --pattern "vol_*_chap*.txt" [--dry-run] [--show-debug]

Features:
  - Fixed input/output directories: _test_in → _test_out
  - chapter_id format: vol_<vol_num>_text_chap_<chap_num> (auto-extracted from filename)
  - Output: processed JSON in {output}/processed/
  - Debug JSON (full internal trace) optionally in {output}/debug/
"""

import argparse
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Try to load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Adjust imports to match project layout if needed
from ai_novel_analyzer.utils.ai_api_client import AIApiFactory, OpenAICompatibleClient
from ai_novel_analyzer.core.prompt_manager import PromptManager
from ai_novel_analyzer.core.chapter_processor import ChapterProcessor
from ai_novel_analyzer.models import NovelChapterInput

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_INPUT = "output/_test_in"
DEFAULT_OUTPUT = "output/_test_out"

@dataclass
class Config:
    input_dir: Path
    output_dir: Path
    pattern: str
    dry_run: bool
    show_debug: bool

def parse_args() -> Config:
    parser = argparse.ArgumentParser(description="Chapter Processor Test Runner")
    parser.add_argument("--input", type=str, default=DEFAULT_INPUT, help="Input directory path")
    parser.add_argument("--output", type=str, default=DEFAULT_OUTPUT, help="Output directory path")
    parser.add_argument("--pattern", type=str, default="vol_*_chap*.txt", help="Glob pattern for input files")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without making changes")
    parser.add_argument("--show-debug", action="store_true", help="Generate debug JSON outputs")
    args = parser.parse_args()
    return Config(
        input_dir=Path(args.input),
        output_dir=Path(args.output),
        pattern=args.pattern,
        dry_run=args.dry_run,
        show_debug=args.show_debug
    )

def extract_chapter_key(filename: str) -> tuple[int,int]:
    """
    Extract volume & chapter numbers from filenames like:
      vol_1_chap_0001_第1章 建立人物.txt
    Returns (vol_num, chap_num) as integers.
    Fallbacks: vol=1, chap=1 on failure and logs a warning.
    """
    # Expecting patterns: vol_<N>_chap_<M>_... or <N>_chap_<M>_...
    m_vol = re.search(r"vol[_\s]?(\d+)", filename.lower())
    m_chap = re.search(r"chap[_\s]?(\d+)", filename.lower())
    vol = int(m_vol.group(1)) if m_vol else 1
    chap = int(m_chap.group(1)) if m_chap else 1
    return vol, chap

def build_chapter_id(vol: int, chap: int) -> str:
    return f"vol_{vol}_text_chap_{chap}"

def load_prompt_files(prompt_mgr: PromptManager) -> dict[str,str]:
    """Load core prompt templates."""
    # Use prompt_mgr.load() method for markdown files
    chapter_proc = prompt_mgr.load('chapter_processor')
    # For schema, read the JSON file directly
    import os
    schema_path = Path(__file__).parent.parent / 'prompts' / 'templates' / 'output_schema.json'
    schema_content = schema_path.read_text(encoding='utf-8')
    return {
        'chapter_processor': chapter_proc,
        'output_schema': schema_content
    }

def run_single_chapter(
    text: str,
    processor: ChapterProcessor,
    chapter_id: str,
    vol_num: int,
    chap_num: int,
    title: str,
    show_stream: bool = True  # Default to streaming
) -> dict:
    """Process one chapter using the existing ChapterProcessor entrypoint."""
    # Build input object
    chapter_input = NovelChapterInput(
        chapter_id=chapter_id,
        chapter_title=title,
        content=text,
        volume_number=vol_num,
        chapter_number=chap_num
    )
    
    # Process and extract structured data
    result = processor.process_chapter(chapter_input, show_stream=show_stream)
    return result.structured_data or {}

def ensure_dirs(cfg: Config):
    cfg.input_dir.mkdir(parents=True, exist_ok=True)
    Path(f"{cfg.output_dir}/processed").mkdir(parents=True, exist_ok=True)
    if cfg.show_debug:
        Path(f"{cfg.output_dir}/debug").mkdir(parents=True, exist_ok=True)

def run_test(cfg: Config) -> None:
    ensure_dirs(cfg)
    prompt_mgr = PromptManager()
    prompts = load_prompt_files(prompt_mgr)
    
    # Create AI client from environment variables
    import os
    api_key = os.getenv('AI_MODEL_API_KEY') or os.getenv('AI_API_KEY', '')
    base_url = os.getenv('AI_MODEL_BASE_URL') or os.getenv('AI_API_BASE_URL', 'https://api.openai.com/v1')
    model = os.getenv('AI_MODEL_NAME') or os.getenv('AI_MODEL', 'gpt-4o')
    
    if not api_key:
        logger.error("API key not found. Please set AI_MODEL_API_KEY or AI_API_KEY in environment variables")
        return
    
    client = AIApiFactory.create_openai_compatible(
        provider="custom",
        api_key=api_key,
        base_url=base_url,
        model=model
    )
    processor = ChapterProcessor(prompt_manager=prompt_mgr, ai_api_client=client)

    files = sorted([f for f in cfg.input_dir.iterdir() if f.is_file() and f.match(cfg.pattern)])
    if not files:
        logger.warning(f"No files found in {cfg.input_dir} matching pattern '{cfg.pattern}'")
        return

    for filepath in files:
        chap_title = filepath.stem  # e.g., vol_1_chap_0001_第1章 建立人物
        vol_num, chap_num = extract_chapter_key(chap_title)
        chapter_id = build_chapter_id(vol_num, chap_num)

        logger.info(f"Processing: {filepath.name} => {chapter_id}")
        text = filepath.read_text(encoding="utf-8")

        if cfg.dry_run:
            logger.info("[DRY-RUN] Skipping write operations.")
            continue

        out_json_name = f"{chapter_id}.json"
        result = run_single_chapter(
            text, processor, chapter_id, vol_num, chap_num, chap_title,
            show_stream=True  # Always enable streaming in test mode
        )
        out_path = cfg.output_dir / "processed" / out_json_name
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Wrote: {out_path}")

        if cfg.show_debug and isinstance(result, dict):
            debug_path = cfg.output_dir / "debug" / (out_json_name.replace(".json", "_debug.json"))
            debug_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info(f"Wrote debug: {debug_path}")

if __name__ == "__main__":
    cfg = parse_args()
    run_test(cfg)
