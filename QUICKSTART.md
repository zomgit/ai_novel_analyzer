# 15 分钟快速安装指南

**AI Novel Analyzer v2.0** - 从安装到首次运行

---

## 📋 前置条件

- ✅ Python >= 3.12（推荐最新 3.13）
- ✅ uv 包管理器（推荐）或 pip
- ✅ 网络连接（用于下载依赖和调用 API）

---

## 🚀 方法一：使用 uv 包管理器（推荐⭐）

**uv 的优势**:
- ⚡ 比 pip 快 **10-100 倍**
- 🔒 自动锁定依赖版本（`uv.lock`）
- 🎯 自动管理虚拟环境（`.venv`）

### 安装步骤

```powershell
# Step 1: 安装 uv（如果还没有）
# 方式 A: pip 安装
pip install uv

# 方式 B: 官方安装脚本（Windows PowerShell）
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Step 2: 进入项目目录
cd D:\PLAY\AI-Hero_Reborn

# Step 3: 一键同步所有依赖（自动创建 .venv + 安装依赖）
uv sync

# Step 4: 验证安装
uv run python scripts\verify_environment.py
```

**完成！** 您现在有完整的运行环境了。

---

## 🐍 方法二：使用 pip（传统方式）

```powershell
# Step 1: 创建并激活虚拟环境
python -m venv venv
.\venv\Scripts\Activate.ps1

# Step 2: 安装依赖
pip install -r requirements.txt

# Step 3: 验证安装
python scripts\verify_environment.py
```

---

## 📦 项目依赖清单

| 包名 | 用途 | 必需性 |
|------|------|--------|
| `requests` | OpenAI 兼容 API 调用 | ✅ 必需 |
| `pyyaml` | YAML 配置解析 | ✅ 必需 |
| `python-dotenv` | .env 环境变量加载 | ✅ 必需 |
| `jsonschema` | JSON Schema 验证 | ✅ 必需 |
| `pydantic` | 数据模型验证 | ✅ 必需 |
| `chromadb` | 本地向量数据库 | ✅ 必需 |
| `tqdm` | 进度条显示 | ✅ 必需 |
| `tiktoken` | Token 计数 | 🔶 可选 |

> ℹ️ **SiliconFlow 说明**：硅基流动没有官方 Python SDK，项目通过 `requests` 直接调用其 OpenAI 兼容 REST API，只需在 `.env` 中配置 API Key 即可。

---

## ⚙️ 后续配置

安装完成后，还需要：

1. **获取 SiliconFlow API Key**（免费额度）
   - 访问 https://cloud.siliconflow.cn/
   - 注册并创建 API Key

2. **配置环境变量**
   ```powershell
   # 复制模板
   Copy-Item .env.example .env

   # 编辑 .env 文件填入密钥
   # SILICONFLOW_API_KEY="sf-your-key"
   # AI_MODEL_API_KEY="your-key"
   ```

3. **运行配置向导**
   ```powershell
   cd scripts
   uv run python .\quick_setup.py
   # 或激活虚拟环境后：python .\quick_setup.py
   ```

---

## 🛠️ 常见问题

### Q1: uv 命令找不到？
A: uv 默认安装在 `%USERPROFILE%\.local\bin\`，请将其加入 PATH：
```powershell
$env:Path += ";$env:USERPROFILE\.local\bin"
```

### Q2: 下载速度慢？
A: 使用清华镜像源：
```powershell
# uv
$env:UV_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
uv sync

# pip
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q3: 需要 GPU 吗？
A: **不需要！** ChromaDB 和 SiliconFlow 都是 CPU 友好的方案。

### Q4: 如何检查依赖是否完整？
```powershell
uv run python scripts\check_dependencies.py
```

---

## 📚 下一步

- [ ] 阅读 `README.md` 了解完整功能
- [ ] 复制 `config/production.example.yaml` 为 `config/production.yaml` 并按需修改
- [ ] 开始批量处理小说章节！

---

**最后更新**: 2026-08-16
**版本**: 2.0
