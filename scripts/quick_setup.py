#!/usr/bin/env python3
"""
AI Novel Analyzer - 快速配置向导

此脚本帮助新手用户完成 API Key 和基础配置设置
运行一次即可自动生成所有必要的环境变量和配置文件
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

def print_header():
    """打印标题"""
    print("=" * 70)
    print("🎯 AI Novel Analyzer - 快速配置向导 v2.0")
    print("=" * 70)
    print()

def mask_secret(value):
    """对敏感信息做脱敏展示，保留首尾少量字符"""
    
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * 8}{value[-4:]}"

def load_existing_env(base_dir):
    """解析已有的 .env 文件，返回环境变量字典（不存在则返回空字典）
    
    支持 KEY=VALUE / KEY="VALUE" 格式，自动忽略注释和空行
    """
    
    env_path = base_dir / '.env'
    if not env_path.exists():
        return {}
    
    env_vars = {}
    try:
        for line in env_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            value = value.strip().strip('"').strip("'")
            env_vars[key.strip()] = value
    except Exception:
        return {}
    
    return env_vars

def print_existing_env(env_vars):
    """展示已有环境变量（API Key 脱敏）"""
    
    if not env_vars:
        return
    
    print("\n📋 检测到已有 .env 配置：")
    print("-" * 70)
    
    secret_keys = {'AI_MODEL_API_KEY', 'SILICONFLOW_API_KEY'}
    display_order = ['AI_MODEL_API_KEY', 'SILICONFLOW_API_KEY', 'AI_MODEL_BASE_URL', 'AI_MODEL_NAME']
    
    for key in display_order + [k for k in env_vars if k not in display_order]:
        if key not in env_vars:
            continue
        value = env_vars[key]
        shown = mask_secret(value) if key in secret_keys else value
        print(f"  {key} = {shown or '(空)'}")
    
    print("-" * 70)
    print("💡 后续输入时直接回车（留空）即保留原有值\n")

def get_user_input(prompt, default=None):
    """安全获取用户输入"""
    
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "
    
    try:
        user_input = input(prompt).strip()
        return user_input if user_input else default
    except EOFError:
        return default

def fetch_available_models(base_url, api_key="", timeout=10):
    """从 OpenAI 兼容服务器拉取可用模型列表
    
    调用标准的 GET {base_url}/models 端点（OpenAI 规范）
    
    Args:
        base_url: API 服务器地址（含 /v1 后缀）
        api_key: 认证密钥（本地服务可为空）
        timeout: 请求超时秒数
    
    Returns:
        模型 ID 列表，失败时返回 None
    """
    
    url = base_url.rstrip('/') + "/models"
    
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        
        # OpenAI 规范格式：{"data": [{"id": "model-name", ...}, ...]}
        if isinstance(data, dict) and 'data' in data:
            models = [m.get('id') for m in data['data'] if m.get('id')]
        # 部分服务的简化格式：{"models": [...]} 或直接返回列表
        elif isinstance(data, dict) and 'models' in data:
            models = [m.get('id') if isinstance(m, dict) else str(m) for m in data['models']]
        elif isinstance(data, list):
            models = [m.get('id') if isinstance(m, dict) else str(m) for m in data]
        else:
            return None
        
        return sorted(set(models)) if models else None
        
    except HTTPError as e:
        print(f"⚠️  服务器返回错误：HTTP {e.code}")
        return None
    except URLError as e:
        print(f"⚠️  无法连接服务器：{e.reason}")
        return None
    except Exception as e:
        print(f"⚠️  拉取模型列表失败：{e}")
        return None

def select_model_interactively(base_url, api_key="", default_model="gpt-4o"):
    """交互式选择模型：优先从服务器拉取列表供选择，失败则手动输入
    
    Returns:
        用户选择或输入的模型名称
    """
    
    print("\n🔍 正在从服务器拉取可用模型列表...")
    models = fetch_available_models(base_url, api_key)
    
    if models:
        print(f"✅ 找到 {len(models)} 个可用模型：\n")
        for i, model in enumerate(models, 1):
            print(f"  {i:3d}. {model}")
        
        print(f"\n  0. 手动输入其他模型名称")
        
        while True:
            choice = get_user_input(
                f"请选择模型编号 [1-{len(models)}，0=手动输入]",
                "1"
            )
            
            try:
                idx = int(choice)
                if idx == 0:
                    return get_user_input("请输入模型名称", default_model)
                elif 1 <= idx <= len(models):
                    selected = models[idx - 1]
                    print(f"✅ 已选择：{selected}")
                    return selected
                else:
                    print(f"❌ 请输入 0-{len(models)} 范围内的数字")
            except ValueError:
                # 用户可能直接输入了模型名称，也允许
                if choice:
                    print(f"✅ 已使用自定义模型名：{choice}")
                    return choice
    else:
        print("⚠️  无法获取模型列表（服务器未运行或不支持 /models 端点）")
        return get_user_input("请手动输入模型名称", default_model)

def create_env_file(api_key, siliconflow_key, base_url=None, model=None, base_dir=None):
    """创建 .env 文件
    
    Args:
        api_key: AI 模型 API Key（可为 None，如 Ollama 离线模式）
        siliconflow_key: SiliconFlow Embedding API Key
        base_url: 自定义 OpenAI 兼容服务器地址（可选）
        model: 自定义模型名称（可选）
    """
    
    # 自定义服务器额外配置段
    custom_section = ""
    if base_url:
        custom_section += f"""
# Custom OpenAI-compatible server base URL
AI_MODEL_BASE_URL="{base_url}"
"""
    if model:
        custom_section += f"""
# Custom model name
AI_MODEL_NAME="{model}"
"""
    
    env_content = f"""# AI Novel Analyzer - Environment Variables (Personal)
# Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# ⚠️ WARNING: Do NOT commit this file to Git!

# AI Model API Key (for content analysis)
AI_MODEL_API_KEY="{api_key or ''}"

# SiliconFlow Embedding API Key (for vector generation)
SILICONFLOW_API_KEY="{siliconflow_key or ''}"
{custom_section}
# Optional: Database URL (Phase 2 feature)
DATABASE_URL="sqlite:///./db/sqlite/novel.db"
"""
    
    # 固定写入项目根目录（不受运行目录影响）
    target = (base_dir / '.env') if base_dir else Path('.env')
    
    # 检查是否已有.env 文件
    if target.exists():
        backup_name = f".env.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"\n⚠️  检测到现有 .env 文件，已备份为 {backup_name}")
        target.rename(target.parent / backup_name)
    
    # 写入新文件
    with open(target, 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print(f"\n✅ 成功创建 .env 文件: {target.resolve()}")
    return True

def create_production_config(base_dir):
    """基于示例模板创建生产配置"""
    
    config_dir = base_dir / "config"
    config_dir.mkdir(exist_ok=True)
    
    source_file = base_dir / "config" / "production.example.yaml"
    target_file = config_dir / "production.yaml"
    
    if not source_file.exists():
        print(f"\n❌ 未找到配置文件模板：{source_file}")
        return False
    
    # 复制并添加自定义注释
    content = source_file.read_text(encoding='utf-8')
    
    # 添加个性化配置头
    header = f"""# AI Novel Analyzer - 个人配置文件
# 📝 自动说明：请根据实际情况修改以下参数！
# 🔒 敏感信息（API Key）已在 .env 文件中管理
# 📅 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# 
# ⚠️ 重要：
#   • 不要将此文件提交到版本控制系统
#   • 如果共享项目，请分享 production.example.yaml 而非 production.yaml
#
"""
    
    content = header + content
    
    with open(target_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ 成功创建配置文件：{target_file}")
    return True

def guide_for_siliconflow(existing_env=None):
    """引导获取 SiliconFlow API Key"""
    
    print("\n" + "=" * 70)
    print("💰 SiliconFlow API Key 获取指南（推荐免费方案）")
    print("=" * 70)
    print("""
📢 SiliconFlow 提供免费的 AI 模型和 Embedding 服务，非常适合本项目！

步骤 1: 注册账号
├─ 访问：https://cloud.siliconflow.cn/signup
└─ 使用邮箱注册（推荐 Gmail/Outlook）

步骤 2: 创建 API Key
├─ 登录后进入控制台 Dashboard
└─ 点击左侧菜单："Account" → "API Keys"

步骤 3: 生成密钥
├─ 点击 "Create New API Key"
├─ 填写描述（可选，如"AI Novel Analyzer"）
└─ 复制生成的密钥（格式：sf-xxxxxxxxxxxxxxxx）

步骤 4: 验证额度
├─ 查看账户余额和免费额度
├─ AI 模型：通常有每日免费调用次数
└─ Embedding: 完全免费，每天大量可用


🎯 建议操作：
• 创建两个不同的 Key（一个用于 AI 模型，一个用于 Embedding）
• 定期轮换密钥（每季度更换一次）
• 监控使用情况避免超额


""")
    
    # 询问用户是否要手动获取
    choice = get_user_input("你已完成上述步骤吗？", "yes/no")
    
    if choice.lower() == 'no':
        print("\n💡 提示：打开浏览器访问 SiliconFlow 官网注册即可")
        input("\n按 Enter 键返回...")
        return None, None
    
    print("\n请输入你的 API Key:")
    
    existing_env = existing_env or {}
    
    # 获取 AI Model API Key（留空则沿用已有值）
    ai_key = get_user_input(
        "AI Model API Key",
        existing_env.get('AI_MODEL_API_KEY') or None
    )
    
    # 询问是否使用同一个 Key
    use_same = get_user_input("Embedding 也使用同一个 Key?", "yes")
    
    if use_same.lower() == 'yes':
        emb_key = ai_key
        print("\n✅ 已配置为使用同一密钥")
    else:
        emb_key = get_user_input(
            "SiliconFlow Embedding API Key",
            existing_env.get('SILICONFLOW_API_KEY') or None
        )
    
    return ai_key, emb_key

def guide_for_custom_provider(provider_name, provider_info):
    """引导配置其他 Provider"""
    
    print(f"\n{'=' * 70}")
    print(f"🔧 配置 {provider_name}")
    print('=' * 70)
    print(f"\n{provider_info['description']}\n")
    
    if 'steps' in provider_info:
        for i, step in enumerate(provider_info['steps'], 1):
            print(f"{i}. {step}")
    
    api_key = get_user_input(f"{provider_name} API Key")
    base_url = get_user_input("Base URL", "https://api.example.com/v1")
    model = get_user_input("Model Name", "gpt-4o")
    
    return api_key, base_url, model

def run_interactive_setup():
    """交互式设置流程"""
    
    print_header()
    
    # Step 0: 加载并展示已有配置
    base_dir = Path(__file__).parent.parent
    existing_env = load_existing_env(base_dir)
    print_existing_env(existing_env)
    
    # Step 1: 选择 Provider
    print("\n请选择 AI Provider:")
    print("1. SiliconFlow (推荐 🆓 免费)")
    print("2. OpenAI Official")
    print("3. Groq (极速 ⚡)")
    print("4. TogetherAI")
    print("5. LM Studio (本地)")
    print("6. Ollama (离线)")
    print("7. 自定义兼容服务器\n")
    
    choice = get_user_input("选项编号 [1]", "1")
    
    providers = {
        '1': ('siliconflow', {'name': 'SiliconFlow', 'desc': '硅基流动，完全免费额度'}),
        '2': ('openai', {'name': 'OpenAI', 'desc': '官方 API，质量稳定'}),
        '3': ('groq', {'name': 'Groq', 'desc': 'GPU 加速，响应超快'}),
        '4': ('together', {'name': 'TogetherAI', 'desc': '多样模型选择'}),
        '5': ('lmstudio', {'name': 'LM Studio', 'desc': '本地服务器，需自行部署'}),
        '6': ('ollama', {'name': 'Ollama', 'desc': '完全离线运行'}),
        '7': ('custom', {'name': '自定义', 'desc': '任意 OpenAI 兼容服务器'}),
    }
    
    selected = providers.get(choice, providers['1'])
    provider_type, provider_info = selected[0], selected[1]
    
    api_keys = {}
    
    if provider_type == 'siliconflow':
        api_keys['AI_MODEL'], api_keys['EMBEDDING_KEY'] = guide_for_siliconflow(existing_env)
        
        if api_keys['AI_MODEL'] is None:
            return  # 用户取消
    
    elif provider_type in ['openai', 'groq', 'together']:
        provider_display = provider_info['name']
        print(f"\n请在 https://{provider_type}.com 上申请 API Key")
        api_keys['AI_MODEL'] = get_user_input(
            f"{provider_display} API Key",
            existing_env.get('AI_MODEL_API_KEY') or None
        )
        api_keys['EMBEDDING'] = get_user_input("Embedding 供应商 [SiliconFlow 默认]") or "siliconflow"
        
        if api_keys['EMBEDDING'] == 'siliconflow':
            api_keys['EMBEDDING_KEY'] = get_user_input(
                "SiliconFlow Embedding API Key",
                existing_env.get('SILICONFLOW_API_KEY') or None
            )
    
    elif provider_type == 'ollama':
        print("\n✅ Ollama 无需 API Key，确保已安装并运行 ollama serve")
        api_keys['AI_MODEL'] = None
        api_keys['EMBEDDING'] = 'local'  # 需要本地 GPU
        print("\n⚠️  注意：本地 Embedding 需要独立 GPU，建议使用 SiliconFlow 云端")
    
    elif provider_type == 'lmstudio':
        print("\n✅ LM Studio 本地服务器无需 API Key")
        print("   请确保 LM Studio 已启动并加载了模型（默认端口 1234）")
        api_keys['AI_MODEL'] = "not-needed"
        api_keys['BASE_URL'] = get_user_input(
            "Base URL",
            existing_env.get('AI_MODEL_BASE_URL') or "http://localhost:1234/v1"
        )
        api_keys['MODEL'] = select_model_interactively(
            api_keys['BASE_URL'],
            api_key="",
            default_model=existing_env.get('AI_MODEL_NAME') or "local-model"
        )
    
    elif provider_type == 'custom':
        print("\n🔧 自定义 OpenAI 兼容服务器配置")
        print("   适用于：vLLM、FastChat、One API、自建网关等")
        api_keys['BASE_URL'] = get_user_input(
            "Base URL (含 /v1 后缀)",
            existing_env.get('AI_MODEL_BASE_URL') or "http://localhost:8000/v1"
        )
        api_keys['AI_MODEL'] = get_user_input(
            "API Key (无需可留空)",
            existing_env.get('AI_MODEL_API_KEY') or ""
        )
        
        # 自动拉取模型列表供用户选择
        api_keys['MODEL'] = select_model_interactively(
            api_keys['BASE_URL'],
            api_key=api_keys['AI_MODEL'],
            default_model=existing_env.get('AI_MODEL_NAME') or "gpt-4o"
        )
        
        # 询问 Embedding 方案
        emb_choice = get_user_input("Embedding 是否也用该服务器? [yes/no]", "no")
        if emb_choice.lower() == 'yes':
            api_keys['EMBEDDING'] = 'custom'
            api_keys['EMBEDDING_KEY'] = api_keys['AI_MODEL']
        else:
            api_keys['EMBEDDING'] = 'siliconflow'
            api_keys['EMBEDDING_KEY'] = get_user_input(
                "SiliconFlow Embedding API Key",
                existing_env.get('SILICONFLOW_API_KEY') or None
            )
    
    else:
        api_keys['AI_MODEL'] = get_user_input(
            "Custom API Key",
            existing_env.get('AI_MODEL_API_KEY') or None
        )
        api_keys['BASE_URL'] = get_user_input(
            "Base URL",
            existing_env.get('AI_MODEL_BASE_URL') or None
        )
    
    # Step 2: 创建配置文件
    print("\n" + "=" * 70)
    print("📝 正在创建配置文件...")
    print("=" * 70)
    
    if create_env_file(
        api_keys.get('AI_MODEL'),
        api_keys.get('EMBEDDING_KEY'),
        base_url=api_keys.get('BASE_URL'),
        model=api_keys.get('MODEL'),
        base_dir=base_dir
    ):
        create_production_config(base_dir)
        
        print("\n" + "=" * 70)
        print("🎉 配置完成！")
        print("=" * 70)
        
        print("""
📂 创建的文件:
  ✅ .env              - API Key 和环境变量
  ✅ config/production.yaml - 完整配置文件

🚀 下一步:
  1. 检查配置文件内容是否正确
  2. 根据你的需求调整参数（如并发数、模型选择等）
  3. 开始运行批量处理！

💡 提示：
  • 详细使用说明见 README.md
  • 遇到问题可查看 docs/AI_API_Configuration_Guide.md
  • 记得不要将 .env 文件提交到 Git！

祝您使用愉快！🎊

""")
        
        return True
    else:
        print("\n❌ 配置失败，请检查错误信息")
        return False

def main():
    """主函数"""
    try:
        success = run_interactive_setup()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  用户取消配置")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误：{str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
