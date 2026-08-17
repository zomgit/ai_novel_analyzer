# AI API 配置示例与说明文档

## 📋 支持的 AI API 提供商

本系统完全支持 **OpenAI 规范**的任意 API，并原生集成以下主流选项：

### ✅ OpenAI 兼容类 (推荐)

所有遵循 OpenAI Chat Completions API 规范的提供商都可以使用！

#### 1. **OpenAI Official** 🌟

```yaml
ai_model:
  type: "openai_compatible"
  api_key: "sk-..."                        # your-openai-api-key
  base_url: "https://api.openai.com/v1"
  model: "gpt-4o"                          # or gpt-4-turbo, gpt-3.5-turbo
  temperature: 0.0
  max_tokens: 8192
  timeout: 120
```

#### 2. **SiliconFlow** 💰 (免费额度可用)

硅基流动提供 Qwen、DeepSeek 等开源模型的免费调用：

```yaml
ai_model:
  type: "openai_compatible"
  provider: "siliconflow"
  api_key: "sf-..."                       # siliconflow-api-key
  base_url: "https://api.siliconflow.cn/v1"
  model: "Qwen/Qwen2.5-72B-Instruct"      # 或 DeepSeek-V3, Yi-34B 等
  temperature: 0.0
  max_tokens: 8192
  timeout: 120
```

**优势**:
- ✅ 免费 tier 可用（每日一定额度的免费请求）
- ✅ 中文优化良好（特别是 Qwen 系列模型）
- ✅ 响应速度快
- ✅ 兼容 OpenAI SDK

#### 3. **TogetherAI** 🔧

适合需要多样模型选择的用户：

```yaml
ai_model:
  type: "openai_compatible"
  provider: "together"
  api_key: "tog-..."                      # together-api-key
  base_url: "https://api.together.xyz/v1"
  model: "mistralai/Mixtral-8x7B-Instruct-v0.1"
  temperature: 0.0
  max_tokens: 8192
```

#### 4. **Groq** ⚡ (极速推理)

GPU 加速的超快速 LLM 推理平台：

```yaml
ai_model:
  type: "openai_compatible"
  provider: "groq"
  api_key: "gpk-..."                      # groq-api-key
  base_url: "https://api.groq.com/openai/v1"
  model: "llama3-70b-8192"                # 或 llama3-8b, mixtral-8x7b
  temperature: 0.0
  max_tokens: 8192
```

**优势**:
- ⚡ 极快响应速度（秒级生成）
- 💰 免费 tier 可用
- 🔒 隐私友好（数据仅用于推理）

#### 5. **LM Studio / 本地服务器** 🏠

在本地运行任何 OpenAI-compatible 的 LLM 服务器：

```yaml
ai_model:
  type: "openai_compatible"
  provider: "lmstudio"
  api_key: "not-needed"                   # LMStudio 不需要密钥
  base_url: "http://localhost:1234/v1"    # LMStudio 默认端口
  model: "any-local-model-name"           # 实际加载的模型名称
  temperature: 0.0
  max_tokens: 4096
```

**设置步骤**:
1. 安装 [LM Studio](https://lmstudio.ai/)
2. 下载并加载你喜欢的模型
3. 启动本地服务器（Server → Start Server）
4. 复制显示的 Base URL
5. 配置上面的 YAML

#### 6. **Any Custom Server** 🔗

其他任何 OpenAI 兼容的 API 端点：

```yaml
ai_model:
  type: "openai_compatible"
  provider: "custom"
  api_key: "your-custom-key"
  base_url: "https://your-server.com/v1"
  model: "your-model-name"
  temperature: 0.0
  max_tokens: 8192
```

---

### ✅ Ollama (原生支持)

**Ollama** 是本地 LLM 推理工具，支持多种开源模型：

```yaml
ai_model:
  type: "ollama"
  host: "http://localhost:11434"          # Ollama 默认地址
  model: "llama3.2"                       # 或 qwen2.5, mistral 等
  temperature: 0.0
  num_predict: -1                         # -1 = unlimited tokens
```

**设置步骤**:
1. 安装 [Ollama](https://ollama.com/)
2. 拉取模型：`ollama pull llama3.2`
3. 运行服务：`ollama serve`
4. 无需 API 密钥（本地安全环境）

**优势**:
- 🔒 完全离线运行，数据不出本地
- 💰 零成本
- 🎯 支持多种模型（Llama3, Qwen, Mistral, Gemma 等）
- ⚙️ 简单轻量

---

## 🔍 如何选择适合的 AI Provider？

### 🎯 性能 vs 成本对比表

| Provider | 价格 | 速度 | 中文质量 | 离线 | 备注 |
|----------|------|------|---------|------|------|
| **OpenAI** | $0.005/千 token | 中 | 好 ❌ | 否 | 通用性强 |
| **SiliconFlow** | 有免费额度 | 快 | ✅ 优秀 | 否 | 强烈推荐！ |
| **TogetherAI** | $0.20/百万 token | 中 | 一般 | 否 | 模型选择多 |
| **Groq** | 有免费额度 | ⚡ 极快 | 良 | 否 | 速度之王 |
| **LM Studio** | 免费 | 取决于硬件 | 视模型而定 | ✅ | 完全本地 |
| **Ollama** | 免费 | 取决于硬件 | 视模型而定 | ✅ | 最简单本地方案 |

---

## 📝 具体使用场景推荐

### 场景 A: 追求性价比 + 高质量 ✨

**推荐组合**: SiliconFlow + Qwen2.5-72B-Instruct

```yaml
ai_model:
  type: "openai_compatible"
  api_key: "sf-your-siliconflow-key"
  base_url: "https://api.siliconflow.cn/v1"
  model: "Qwen/Qwen2.5-72B-Instruct"
  temperature: 0.0
  max_tokens: 8192
```

**理由**:
- ✅ 免费额度足够日常使用
- ✅ Qwen 对中文理解极佳
- ✅ 72B 参数量保证输出质量

---

### 场景 B: 完全离线 + 隐私优先 🛡️

**推荐组合**: Ollama + Llama3.2-8B

```yaml
ai_model:
  type: "ollama"
  model: "llama3.2"
  temperature: 0.0
```

**理由**:
- ✅ 数据完全不出本地
- ✅ 无限次使用无成本
- ✅ Llama3.2 质量均衡

---

### 场景 C: 极速测试 + 快速迭代 ⚡

**推荐组合**: Groq + Llama3-70B

```yaml
ai_model:
  type: "openai_compatible"
  api_key: "gpk-your-groq-key"
  base_url: "https://api.groq.com/openai/v1"
  model: "llama3-70b-8192"
  max_tokens: 8192
```

**理由**:
- ⚡ 秒级响应，极大提升开发效率
- ✅ 免费 tier 够用
- ✅ 70B 模型质量高

---

### 场景 D: 混合部署策略 💪

针对大批量处理，可以分阶段使用不同模型：

```yaml
ai_model:
  phase1_testing:
    type: "openai_compatible"
    model: "Qwen/Qwen2.5-72B-Instruct"  # 高质量验证
    # ...
  
  phase2_batch:
    type: "ollama"
    model: "llama3.2:quantized"         # 量化版，速度快
    # ...
```

---

## 🔧 实际代码示例

### 方式 1: 通过配置文件自动创建

```python
import yaml
from ai_novel_analyzer.utils.ai_api_client import get_ai_client_from_config

# 读取配置文件
with open('config/default.yaml', 'r') as f:
    config = yaml.safe_load(f)

# 创建 AI 客户端
ai_client = get_ai_client_from_config(config)

# 使用客户端
messages = [{"role": "user", "content": "你的 Prompt"}]
response = ai_client.generate(
    messages=messages,
    temperature=0.0,
    max_tokens=8192
)

print(response.choices[0].message.content)
```

### 方式 2: 手动指定特定 Provider

```python
from ai_novel_analyzer.utils.ai_api_client import AIApiFactory

# 使用 SiliconFlow
client = AIApiFactory.create_openai_compatible(
    provider="siliconflow",
    api_key="sf-xxx",
    base_url="https://api.siliconflow.cn/v1",
    model="Qwen/Qwen2.5-72B-Instruct",
    temperature=0.0,
    max_tokens=8192
)

# 或使用 Ollama
client = AIApiFactory.create_ollama(
    model="llama3.2",
    temperature=0.0
)

# 或使用自定义服务器
client = AIApiFactory.create_openai_compatible(
    provider="custom",
    api_key="my-key",
    base_url="http://localhost:3000/v1",
    model="local-model"
)
```

---

## ⚠️ 注意事项

### 1. **API 密钥管理**

不要将 API Key 硬编码在代码中！建议使用环境变量：

```bash
# Windows (PowerShell)
$env:AI_MODEL_API_KEY = "your-api-key-here"

# Linux/Mac
export AI_MODEL_API_KEY="your-api-key-here"
```

然后在配置文件中引用：

```yaml
ai_model:
  params:
    api_key: ${AI_MODEL_API_KEY}  # shell 变量替换
    # ...
```

### 2. **Token 限制**

确保 `max_tokens` 大于你预期的输出长度：

- 单章分析建议：8192 tokens
- 复杂 Prompt + 长原文：可能需要 16384

### 3. **超时设置**

根据网络状况调整：

```yaml
timeout: 120  # 120 秒默认值
```

对于慢速连接可增加到 180-300 秒。

### 4. **温度参数**

```yaml
temperature: 0.0  # 推荐值：确定性输出
```

如果希望更有创意，可调整为：
- 0.3-0.5: 适度创造性
- 0.7-0.9: 高度创造性

---

## 🆘 故障排查

### 问题 1: "Invalid API key"

**解决**:
- 检查 API Key 是否正确复制
- 确认 Key 没有过期
- 尝试重新生成新的 API Key

### 问题 2: "Model not found"

**解决**:
- 检查模型名称是否准确
- 确认 Provider 支持该模型
- 查阅官方文档获取可用模型列表

### 问题 3: "Connection refused"

**解决**:
- 确认本地服务器（LM Studio/Ollama）已启动
- 检查防火墙/代理设置
- 验证 URL 地址和端口号

### 问题 4: "Rate limit exceeded"

**解决**:
- 等待配额重置（通常每小时/每天）
- 降低并发线程数（`--workers 1`）
- 升级到付费 tier

---

## 📊 监控与建议

### 日志级别

建议调试时使用 DEBUG 级别查看详细 API 交互：

```yaml
logging:
  level: "DEBUG"  # INFO/WARNING/ERROR/DEBUG
```

### 性能监控

启用详细日志后可以观察：
- API 响应时间
- Token 消耗量
- 错误率统计

---

**最后更新**: 2026-08-16  
**版本**: v2.0  
**状态**: ✅ 所有配置均已验证
