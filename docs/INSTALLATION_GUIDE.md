# AI Novel Analyzer - 安装与依赖完整指南

**版本**: 2.0
**最后更新**: 2026-08-16

---

## 📋 目录

1. [核心 Python 包清单](#核心-python-包清单)
2. [SiliconFlow 接入方式说明](#siliconflow-接入方式说明)
3. [安装方法](#安装方法)
4. [验证与检查](#验证与检查)
5. [常见问题 FAQ](#常见问题-faq)

---

## 🎯 核心 Python 包清单

### ✅ 必需的核心依赖（8 个）

| 包名 | 导入名 | 用途 |
|------|--------|------|
| `requests` | `requests` | OpenAI 兼容 API 调用（HTTP 客户端） |
| `pyyaml` | `yaml` | YAML 配置文件解析 |
| `python-dotenv` | `dotenv` | .env 环境变量加载 |
| `jsonschema` | `jsonschema` | AI 输出的 JSON Schema 严格验证 |
| `pydantic` | `pydantic` | 数据模型验证与管理 |
| `chromadb` | `chromadb` | 本地向量数据库存储（无需 GPU） |
| `tqdm` | `tqdm` | 批处理进度条显示 |
| `tiktoken` | `tiktoken` | Token 计数与长文本分片 |

> ⚠️ 注意：导入名与包名不一定一致，例如 `pip install pyyaml` 后在代码中 `import yaml`。

### 🧰 开发依赖（可选）

| 包名 | 用途 |
|------|------|
| `pytest` / `pytest-cov` | 单元测试与覆盖率 |
| `black` / `isort` | 代码格式化 |
| `flake8` / `mypy` | 静态检查 |

安装：`uv sync --group dev`

---

## ☁️ SiliconFlow 接入方式说明

### 关键事实

**SiliconFlow（硅基流动）没有官方 Python SDK！** PyPI 上不存在名为 `siliconflow` 的包。

项目通过标准 `requests` 库直接调用其 **OpenAI 兼容 REST API**：

| 服务 | 端点 |
|------|------|
| Chat 对话 | `https://api.siliconflow.cn/v1/chat/completions` |
| Embedding 向量化 | `https://api.siliconflow.cn/v1/embeddings` |
| 模型列表 | `https://api.siliconflow.cn/v1/models` |

### 调用示例

```python
import requests

response = requests.post(
    "https://api.siliconflow.cn/v1/embeddings",
    headers={"Authorization": f"Bearer {api_key}"},
    json={"model": "BAAI/bge-m3", "input": ["你的文本"]}
)
vector = response.json()["data"][0]["embedding"]
```

**结论**：
- ✅ 无需安装任何额外包
- ✅ 只需在 `.env` 中配置 `SILICONFLOW_API_KEY`
- ✅ 不配置也能使用核心分析功能（仅向量搜索不可用）

---

## 🚀 安装方法

### 方法 A: uv（⭐ 推荐）

```powershell
cd D:\PLAY\AI-Hero_Reborn

# 一键同步（自动创建 .venv 并安装全部依赖）
uv sync

# 含开发依赖
uv sync --group dev

# 运行脚本
uv run python scripts\verify_environment.py
```

**uv 是什么？** 新一代 Python 包管理器（Ruff 团队出品），比 pip 快 10-100 倍，
通过 `pyproject.toml` + `uv.lock` 管理依赖，类似 npm 的锁定机制。

### 方法 B: pip（传统方式）

```powershell
cd D:\PLAY\AI-Hero_Reborn
python -m venv venv
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt

# 国内用户加速：
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## ✅ 验证与检查

### 快速验证

```powershell
uv run python scripts\verify_environment.py
```

输出示例：
```
✅ requests
✅ pyyaml
✅ python-dotenv
✅ jsonschema
✅ pydantic
✅ chromadb
✅ tqdm
✅ SILICONFLOW_API_KEY 已配置（云端 Embedding 可用）

🎉 完美！所有依赖已安装，您可以开始使用了！
```

### 详细检查

```powershell
uv run python scripts\check_dependencies.py
```

---

## ❓ 常见问题 FAQ

### Q1: uv 是什么？和 pip 有什么区别？

A: **uv** 是 Astral 公司开发的现代 Python 包管理器：

| 对比项 | uv | pip |
|--------|-----|-----|
| 速度 | ⚡ 快 10-100 倍 | 普通 |
| 依赖锁定 | ✅ uv.lock | ❌ 需手动 freeze |
| 虚拟环境 | ✅ 自动管理 | ❌ 手动 venv |
| 配置文件 | pyproject.toml | requirements.txt |

两者可以共存，本项目以 uv 为主、pip 兼容。

### Q2: SiliconFlow 真的没有 Python 包吗？

A: **是的**。PyPI 上不存在官方的 `siliconflow` 包。
SiliconFlow 提供的是 OpenAI 兼容的 HTTP API，用 `requests` 直接调用即可。
如果 PyPI 上出现同名包，那是第三方社区包，请谨慎使用。

### Q3: 需要 GPU 吗？

A: **完全不需要！**
- ChromaDB 向量检索：CPU 即可运行
- SiliconFlow 嵌入计算：云端完成
- AI 章节分析：云端 API 调用

### Q4: 下载依赖很慢怎么办？

A: 使用国内镜像源：
```powershell
# uv
$env:UV_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
uv sync

# pip
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q5: `uv` 命令找不到？

A: uv 默认安装在 `%USERPROFILE%\.local\bin\`：
```powershell
# 临时加入 PATH
$env:Path += ";$env:USERPROFILE\.local\bin"

# 或使用完整路径
& "$env:USERPROFILE\.local\bin\uv.exe" sync
```

### Q6: 如何更新依赖？

```powershell
# uv：更新锁文件并同步
uv lock --upgrade
uv sync

# pip：重新安装
pip install -r requirements.txt --upgrade
```

---

## 📂 相关文件位置

| 文件 | 作用 |
|------|------|
| `pyproject.toml` | 项目元数据 + 依赖声明（uv 主配置） |
| `uv.lock` | uv 依赖锁定文件（保证版本一致） |
| `requirements.txt` | pip 兼容的依赖清单 |
| `scripts/check_dependencies.py` | 详细依赖检查工具 |
| `scripts/verify_environment.py` | 快速环境验证 |
| `QUICKSTART.md` | 15 分钟上手教程 |

---

**最后更新**: 2026-08-16
**版本**: 2.0
**状态**: ✅ 生产就绪
