"""Debug Test: Stream Response Path Tracing"""
import asyncio
import json
import os
from dotenv import load_dotenv

load_dotenv()

from ai_novel_analyzer.utils.ai_api_client import AIApiFactory, MockResponse
from ai_novel_analyzer.core.chapter_processor import ChapterProcessor
from ai_novel_analyzer.core.prompt_manager import PromptManager

# 1. Create minimal chapter input
class MiniInput:
    chapter_id = "vol_1_text_chap_test"
    volume_number = 1
    chapter_number = 1
    
input_obj = MiniInput()

# 2. Create AI client
api_key = os.getenv('AI_MODEL_API_KEY') or os.getenv('AI_API_KEY', '')
base_url = os.getenv('AI_MODEL_BASE_URL') or os.getenv('AI_API_BASE_URL', 'https://api.openai.com/v1')
model = os.getenv('AI_MODEL_NAME') or os.getenv('AI_MODEL', 'gpt-4o')

print(f"API Client Config:")
print(f"  model={model}")
print(f"  base_url={base_url}")
print(f"  api_key exists={bool(api_key)}")
print()

client = AIApiFactory.create_openai_compatible(
    provider="custom", api_key=api_key, base_url=base_url, model=model
)

prompt_mgr = PromptManager()
prompt_content = prompt_mgr.load('chapter_processor')

# Replace placeholders with test data
prompt = prompt_content.replace("{context_summary}", "")
prompt = prompt.replace("{vol_num}", "1")
prompt = prompt.replace("{chap_num}", "test")
prompt = prompt.replace("{text_content}", "简短测试文本。你好")

# 3. Direct API call with trace
print("=" * 80)
print("TEST 1: Direct streaming API call with detailed tracing")
print("=" * 80)

def debug_callback(chunk):
    print(f"[STREAM CALLBACK] Received chunk: '{chunk[:50]}...' len={len(chunk)}")

try:
    for i, chunk in enumerate(client.generate(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=2048,  # Very short to speed up test
        timeout=60,
        stream=True
    )):
        print(f"\n[LOOP ITERATION {i}] Chunk type: {type(chunk).__name__}")
        print(f"  - hasattr choices: {hasattr(chunk, 'choices')}")
        if hasattr(chunk, 'choices'):
            print(f"  - len(choices): {len(chunk.choices)}")
            if len(chunk.choices) > 0:
                choice = chunk.choices[0]
                print(f"  - choice type: {type(choice).__name__}")
                print(f"  - hasattr message: {hasattr(choice, 'message')}")
                if hasattr(choice, 'message'):
                    msg = choice.message
                    print(f"  - msg type: {type(msg).__name__}")
                    print(f"  - msg.role: {msg.role}")
                    print(f"  - msg.content: '{msg.content[:30]}'")
                    print(f"  - len(content): {len(msg.content)}")
        
        # Call callback if has content
        content = chunk.choices[0].message.content
        if content and len(content.strip()) > 0:
            debug_callback(content)
            print(f"[DEBUG] Content length non-zero, calling callback")
        
    print("\n[*] Streaming loop completed")

except Exception as e:
    print("\n[-] ERROR: {type(e).__name__}: {str(e)[:200]}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("TEST 2: Non-streaming call for comparison")
print("=" * 80)

try:
    response = client.generate(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=2048,
        timeout=60,
        stream=False
    )
    
    print(f"Response type: {type(response).__name__}")
    if hasattr(response, 'choices'):
        print(f"  len(choices): {len(response.choices)}")
        if len(response.choices) > 0:
            print(f"  content: {response.choices[0].message.content[:100]}...")
    
    print("\n[*] Non-streaming completed")

except Exception as e:
    print(f"❌ ERROR: {type(e).__name__}: {str(e)[:200]}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("DIAGNOSTIC SUMMARY")
print("=" * 80)
print("Possible issues found:")
print("1. Empty chunks (length 0): might be skipped by stdout.write")
print("2. MessageWrapper missing delta field support")
print("3. MockResponse choices array empty")
print("4. API server not returning proper SSE format")
print("5. requests library not receiving iter_lines correctly")
print()
print("RECOMMENDED FIXES:")
print("A. Ensure MessageWrapper handles both 'message' AND 'delta' fields")
print("B. Add debug logging inside _stream_generate to verify SSE parsing")
print("C. Check raw response from requests.post for SSE format compliance")
print("D. Verify mock responses yield non-empty content before callback")
