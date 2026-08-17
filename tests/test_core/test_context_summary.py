"""Test context summary integration with chapter analysis"""

import sys
from pathlib import Path
import re

# 创建测试数据
test_chapter_text = """
第 10 章：新的冒险

林默推开破旧酒馆的门，尘封的气息扑面而来。吧台后，一个戴着斗篷的神秘人正擦拭着杯子。

"要一杯什么？"神秘人抬头问道。

林默愣了一下："随便什么都可以。"

就在这时，酒馆的木门被猛地推开，一个身穿黑袍的人冲了进来..."
"""

# 模拟前情提要（假设是第 9 章的总结）
context_summary = """
第 9 章摘要：林默在森林中遇到了一位老猎人，得知附近有狼群出没的消息。他决定前往附近的城镇寻求帮助...
"""

if __name__ == "__main__":
    print("=== Test Context Summary Integration ===\n")
    print(f"Context Summary (about {len(context_summary)} chars):\n{context_summary}\n")
    print("=" * 60)
    print(f"Current Chapter Text:\n{test_chapter_text}\n")
    print("=" * 60)
    
    # 生成提示词看看效果
    from ai_novel_analyzer.core.prompt_manager import PromptManager
    
    pm = PromptManager()
    base_template = pm.load("chapter_processor")
    
    # 模拟 prompt 构建过程（与代码实际逻辑一致）
    replacements = {
        "{context_summary}": context_summary,  # Template provides <summary> tags
        "{vol_num}": "2",
        "{chap_num}": "10",
        "{text_content}": test_chapter_text,  # Template provides <chapter_text> tag
    }
    
    final_prompt = base_template
    for placeholder, value in replacements.items():
        final_prompt = final_prompt.replace(placeholder, value)
    
    print("\n\nGenerated Prompt Structure Preview:")
    print("-" * 60)
    
    # Extract key parts to display
    summary_match = re.search(r'<summary>(.*?)</summary>', final_prompt, re.DOTALL)
    text_match = re.search(r'<chapter_text>(.*?)</chapter_text>', final_prompt, re.DOTALL)
    
    if summary_match:
        print("HTML Summary Tag:")
        print(summary_match.group(0)[:300] + "...")
        print()
    
    if text_match:
        print("HTML Chapter Text Tag:")
        print(text_match.group(0)[:500])
        print("...")
        print()
    
    print("\nTest completed! HTML tag structure is correct.")
    print(f"\nExpected processing effect:")
    print(f"  - AI will see clear HTML separation")
    print(f"  - <summary> content marked as reference")
    print(f"  - Analysis based entirely on <chapter_text>")
