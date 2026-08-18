"""AI API Client Factory - Supports multiple providers with OpenAI compatibility"""

from typing import Optional, Dict, Any, TypeVar, Protocol
import requests
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# HTTP 请求专用日志器
http_logger = None

def get_http_logger():
    """懒加载 HTTP 请求日志器"""
    global http_logger
    if http_logger is None:
        try:
            from ai_novel_analyzer.core.logging_config import setup_http_request_logger
            http_logger = setup_http_request_logger()
        except Exception:
            http_logger = logging.getLogger('http_requests_default')
    return http_logger

# Generic type for response objects
ResponseT = TypeVar('ResponseT')


class ChoiceWrapper:
    """Nested choice wrapper for MockResponse compatibility"""
    def __init__(self, choice_data: dict, full_data: dict):
        # Streaming chunks use 'delta', non-streaming uses 'message'
        # 注意：某些 API 可能直接返回 string content，而非嵌套对象
        # full_data 为完整响应 dict（不能用 self.data，self 指向 ChoiceWrapper 自身）
        default_role = 'assistant'
        try:
            default_role = full_data.get('choices', [{}])[0].get('role') or 'assistant'
        except (IndexError, AttributeError):
            pass
        
        delta = choice_data.get('delta')
        msg_data = None
        
        if isinstance(delta, str):
            # 情况 A: delta 直接是字符串内容
            msg_data = {'role': default_role, 'content': delta}
        elif isinstance(delta, dict):
            # 情况 B: delta 是标准 dict（可能只含 role 无 content）
            msg_data = delta
        elif isinstance(choice_data.get('message'), dict):
            # 情况 C: message 是标准 dict (非流式)
            msg_data = choice_data.get('message')
        else:
            # 情况 D: 扁平化结构或空 chunk（如仅含 finish_reason 的收尾块）
            msg_data = {'role': default_role, 'content': choice_data.get('content') or ''}
        
        self.message = MessageWrapper(msg_data or {})
        # Stream chunks: None until final chunk; avoid masking truncation ('length')
        self.finish_reason = choice_data.get('finish_reason')


class UsageWrapper:
    """Token usage wrapper for MockResponse.usage compatibility"""
    def __init__(self, data: dict):
        self.prompt_tokens = data.get('prompt_tokens', 0)
        self.completion_tokens = data.get('completion_tokens', 0)
        self.total_tokens = data.get('total_tokens', 0)


class OpenAICompatibleClient:
    """
    OpenAI-compatible API client for any provider that follows OpenAI's standard
    
    Supports:
    - OpenAI (official)
    - SiliconFlow
    - Ollama (with wrapper)
    - LocalLLaMA
    - Any compatible provider (TogetherAI, Groq, etc.)
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "gpt-4o",
        temperature: float = 0.0,
        max_tokens: int = 32768,
        timeout: int = 120,
        system_prompt: Optional[str] = None
    ):
        """Initialize OpenAI-compatible client
        
        Args:
            api_key: API key for authentication
            base_url: Base URL of the API (e.g., https://api.openai.com/v1)
            model: Model name to use
            temperature: Generation temperature
            max_tokens: Maximum tokens in output
            timeout: Request timeout in seconds
            system_prompt: Optional system prompt prefix
        """
        
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.system_prompt = system_prompt
        
        logger.info(
            f"OpenAICompatibleClient initialized: "
            f"model={model}, url={self.base_url}"
        )
    
    def generate(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
        stream: bool = True  # Default to streaming
    ) -> 'MockResponse':
        """Generate completion using OpenAI-compatible API
        
        Args:
            messages: List of message dicts with role/content keys
            temperature: Override temperature for this request
            max_tokens: Override max_tokens for this request
            timeout: Override timeout for this request
            stream: If True, return streaming response generator
            
        Returns:
            MockResponse object with choices array (non-streaming)
            or generator that yields MockResponse chunks (streaming)
            
        Raises:
            requests.RequestException: On network error
            ValueError: On invalid response format
        """
        
        # Use provided values or fall back to defaults
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        req_timeout = timeout if timeout is not None else self.timeout
        
        # Build the request payload
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": tokens,
            "stream": stream
        }
        
        # Add system prompt if configured
        if self.system_prompt:
            if len(messages) == 0 or messages[0].get('role') != 'system':
                messages = [{'role': 'system', 'content': self.system_prompt}] + messages
        
        # Send request
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            # Determine endpoint: avoid duplicating /v1 when base_url already ends with it
            base = self.base_url.rstrip('/')
            if base.endswith('/chat/completions'):
                full_url = base
            elif base.endswith('/v1'):
                full_url = f"{base}/chat/completions"
            else:
                full_url = f"{base}/v1/chat/completions"
            
            logger.debug(f"Sending request to {full_url}")
            
            if stream:
                # Stream mode: return generator
                return self._stream_generate(
                    full_url, headers, payload, req_timeout
                )
            
            # Non-stream mode: wait for complete response
            start_time = datetime.now()
            
            http_log = {
                "timestamp": start_time.isoformat(),
                "type": "llm_call",
                "method": "POST",
                "url": full_url,
                "request_headers": {"Content-Type": "application/json"},
                "request_body_size": len(json.dumps(payload)),
                "response_status": None,
                "response_time_ms": None,
                "error_message": None
            }
            
            # Send request (non-stream mode)
            response = requests.post(
                full_url,
                headers=headers,
                json=payload,
                timeout=req_timeout
            )
            
            end_time = datetime.now()
            elapsed_ms = int((end_time - start_time).total_seconds() * 1000)
            
            http_log["response_status"] = response.status_code
            http_log["response_time_ms"] = elapsed_ms
            
            # Raise exception for bad status codes
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            
            # Log to HTTP logger
            usage_data = data.get('usage', {})
            http_log['response_body_size'] = len(response.content)
            http_log['prompt_tokens'] = usage_data.get('prompt_tokens', 0)
            http_log['completion_tokens'] = usage_data.get('completion_tokens', 0)
            http_log['total_tokens'] = usage_data.get('total_tokens', 0)
            http_log['response_content_preview'] = str(data)[:500] + '...' if str(data) else ''
            
            get_http_logger().debug(json.dumps(http_log, ensure_ascii=False))
            
            # Validate response structure
            if 'choices' not in data or len(data['choices']) == 0:
                raise ValueError("Invalid response: no choices in response")
            
            # Detect truncation: finish_reason == 'length' means output hit max_tokens limit
            finish_reason = data['choices'][0].get('finish_reason', '')
            if finish_reason == 'length':
                raise ValueError(
                    "Response truncated by max_tokens limit (finish_reason=length). "
                    "Output is incomplete, triggering retry."
                )
            
            # Detect empty content
            content = data['choices'][0].get('message', {}).get('content', '') or ''
            if not content.strip():
                raise ValueError(
                    "API returned empty content (possible content filter or output limit). "
                    f"finish_reason={finish_reason}"
                )
            
            # Return mock response object (compatible with existing code)
            return MockResponse(data)
        
            http_log['error_message'] = f"Request timed out after {req_timeout}s"
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 'unknown'
            error_msg = e.response.text[:500] if e.response is not None else str(e)
            http_log['response_status'] = status
            http_log['error_message'] = f"HTTP error: {status} - {error_msg}"
            get_http_logger().debug(json.dumps(http_log, ensure_ascii=False))
            raise RuntimeError(f"HTTP error: {status} - {error_msg}")
    
    def _stream_generate(
        self,
        full_url: str,
        headers: dict,
        payload: dict,
        timeout: int
    ):
        """
        Streaming generator for chunk-by-chunk response processing.
            
        Yields MockResponse objects for each SSE (Server-Sent Event) line.
        """

            
        logger.info(f"[_stream_generate] Starting stream to {full_url}")
            
        try:
            response = requests.post(
                full_url,
                headers=headers,
                json=payload,
                stream=True,
                timeout=timeout
            )
                
            logger.info(f"[_stream_generate] Request status code: {response.status_code}")
            if response.status_code != 200:
                logger.error(f"[_stream_generate] Response content: {response.text[:200]}")
                raise RuntimeError(f"HTTP {response.status_code}: {response.text[:200]}")
                
            # Process SSE lines
            line_count = 0
            yield_count = 0
            for line in response.iter_lines():
                if line:
                    line_count += 1
                    decoded_line = line.decode('utf-8')
                        
                    # Skip empty lines or event markers
                    if decoded_line == 'data: [DONE]':
                        logger.info(f"[_stream_generate] Received [DONE] after {line_count} lines, yielded {yield_count} chunks")
                        break
                        
                    if decoded_line.startswith('data:'):
                        data_str = decoded_line[5:].strip()
                        if not data_str:
                            continue
                            
                        try:
                            data = json.loads(data_str)
                            choices = data.get('choices', [])
                                
                            # Detect truncation on the final stream chunk
                            if choices and choices[0].get('finish_reason') == 'length':
                                raise ValueError(
                                    "Response truncated by max_tokens limit (finish_reason=length). "
                                    "Output is incomplete, triggering retry."
                                )
                                
                            # Yield partial response as MockResponse
                            mock_resp = MockResponse(data)
                            yield_count += 1
                            logger.debug(f"[_stream_generate] Chunk {yield_count} yielded")
                            yield mock_resp  # 关键：缺少此行函数会退化为普通函数并返回 None
                                
                        except json.JSONDecodeError as e:
                            logger.debug(f"[_stream_generate] Skipping unparseable line {line_count}: {e}")
                            continue
                
        except requests.exceptions.Timeout:
            raise RuntimeError(f"Streaming request timed out after {timeout}s")
        except Exception as e:
            logger.error(f"[_stream_generate] Failed with error: {str(e)}", exc_info=True)
            raise


class OllamaClient:
    """
    Direct Ollama client for local LLM inference
    
    Note: Ollama uses a different API format than OpenAI, so this provides native support.
    """
    
    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "llama3.2",
        temperature: float = 0.0,
        num_predict: int = -1,  # -1 means use model default
        context_window: int = 4096
    ):
        """Initialize Ollama client
        
        Args:
            host: Ollama server URL
            model: Model name to pull and use
            temperature: Generation temperature
            num_predict: Maximum tokens to generate (-1 = unlimited)
            context_window: Context window size
        """
        
        self.host = host.rstrip('/')
        self.model = model
        self.temperature = temperature
        self.num_predict = num_predict
        self.context_window = context_window
        
        # Pull model if not present
        self._ensure_model_exists()
        
        logger.info(f"OllamaClient initialized: model={model}")
    
    def _ensure_model_exists(self):
        """Pull model if not already installed locally"""
        
        try:
            response = requests.get(f"{self.host}/api/tags")
            response.raise_for_status()
            
            data = response.json()
            existing_models = [m['name'] for m in data.get('models', [])]
            
            if self.model not in existing_models:
                logger.warning(f"Model {self.model} not found, pulling...")
                
                pull_response = requests.post(
                    f"{self.host}/api/pull",
                    json={"name": self.model},
                    stream=True
                )
                
                pull_response.raise_for_status()
                
                # Stream progress
                for line in pull_response.iter_lines():
                    if line:
                        progress = json.loads(line)
                        if progress.get('status') == 'success':
                            logger.info(f"Successfully pulled model {self.model}")
                            
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                "Cannot connect to Ollama server. "
                "Make sure Ollama is running and accessible at localhost:11434"
            )
    
    def generate(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        num_predict: Optional[int] = None
    ) -> 'MockResponse':
        """Generate completion from Ollama
        
        Args:
            messages: Chat messages
            temperature: Override temperature
            num_predict: Override max tokens
            
        Returns:
            MockResponse with generated text
        """
        
        temp = temperature if temperature is not None else self.temperature
        predict = num_predict if num_predict is not None else self.num_predict
        
        # Convert OpenAI-style messages to Ollama format
        payload = {
            "model": self.model,
            "messages": [{"role": msg['role'], "content": msg['content']} for msg in messages],
            "stream": False,
            "options": {
                "temperature": temp,
                "num_predict": predict
            }
        }
        
        try:
            response = requests.post(
                f"{self.host}/api/chat",
                json=payload,
                timeout=self.context_window * 2
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Wrap in mock response object
            mock_data = {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": data['message']['content']
                    }
                }]
            }
            
            return MockResponse(mock_data)
            
        except Exception as e:
            raise RuntimeError(f"Ollama generation failed: {str(e)}")


class MockResponse:
    """
    Mock response object to maintain backward compatibility
    
    This wraps raw API responses into an object structure
    that matches OpenAI's SDK response format.
    """
    
    def __init__(self, data: dict):
        """Initialize mock response
        
        Args:
            data: Raw response dictionary
        """
        
        self.data = data
        
        # Extract choices
        choices_data = data.get('choices', [])
        
        if len(choices_data) > 0:
            first_choice = choices_data[0]
            
            class ChoiceWrapper:
                def __init__(self, choice_data, full_data):
                    # Streaming chunks use 'delta', non-streaming uses 'message'
                    # 注意：某些 API 可能直接返回 string content，而非嵌套对象
                    # full_data 为完整响应 dict（不能用 self.data，self 指向 ChoiceWrapper 自身）
                    default_role = 'assistant'
                    try:
                        default_role = full_data.get('choices', [{}])[0].get('role') or 'assistant'
                    except (IndexError, AttributeError):
                        pass
                    
                    delta = choice_data.get('delta')
                    msg_data = None
                    
                    if isinstance(delta, str):
                        # 情况 A: delta 直接是字符串内容
                        msg_data = {'role': default_role, 'content': delta}
                    elif isinstance(delta, dict):
                        # 情况 B: delta 是标准 dict（可能只含 role 无 content）
                        msg_data = delta
                    elif isinstance(choice_data.get('message'), dict):
                        # 情况 C: message 是标准 dict (非流式)
                        msg_data = choice_data.get('message')
                    else:
                        # 情况 D: 扁平化结构或空 chunk（如仅含 finish_reason 的收尾块）
                        msg_data = {'role': default_role, 'content': choice_data.get('content') or ''}
                    
                    self.message = MessageWrapper(msg_data or {})
                    # Stream chunks: None until final chunk; avoid masking truncation ('length')
                    self.finish_reason = choice_data.get('finish_reason')
                    
            self.choices = [ChoiceWrapper(first_choice, data)]
        else:
            self.choices = []
    
    @property
    def usage(self):
        """Return token usage stats if available"""
        
        usage_data = self.data.get('usage', {})
        
        if usage_data:
            class UsageWrapper:
                def __init__(self, data):
                    self.prompt_tokens = data.get('prompt_tokens', 0)
                    self.completion_tokens = data.get('completion_tokens', 0)
                    self.total_tokens = data.get('total_tokens', 0)
            
            return UsageWrapper(usage_data)
        
        return None


class MessageWrapper:
    """Wrapper for message object, supporting both 'message' and 'delta' formats"""
    
    def __init__(self, data: dict):
        self.role = data.get('role', 'assistant')
        
        # 尝试多种可能的内容位置（优先级：delta -> message -> nested in choice -> direct）
        content = None
        if isinstance(data, dict):
            content = data.get('content') or data.get('delta') or data.get('message')
            if isinstance(content, dict):
                content = content.get('content', '')
        
        self.content = content or ''


class AIApiFactory:
    """Factory for creating appropriate API clients based on configuration"""
    
    @staticmethod
    def create_openai_compatible(
        provider: str,
        api_key: str,
        base_url: str,
        model: str = "gpt-4o",
        **kwargs
    ) -> OpenAICompatibleClient:
        """Create OpenAI-compatible client for various providers
        
        Common configurations:
        
        # OpenAI official
        AIApiFactory.create_openai_compatible(
            provider="openai",
            api_key="sk-...",
            base_url="https://api.openai.com/v1",
            model="gpt-4o"
        )
        
        # SiliconFlow (free tier available)
        AIApiFactory.create_openai_compatible(
            provider="siliconflow",
            api_key="sf-...",
            base_url="https://api.siliconflow.cn/v1",
            model="Qwen/Qwen2.5-72B-Instruct"
        )
        
        # TogetherAI
        AIApiFactory.create_openai_compatible(
            provider="together",
            api_key="tog-...",
            base_url="https://api.together.xyz/v1",
            model="mistralai/Mixtral-8x7B-Instruct-v0.1"
        )
        
        # Groq (very fast inference)
        AIApiFactory.create_openai_compatible(
            provider="groq",
            api_key="gpk-...",
            base_url="https://api.groq.com/openai/v1",
            model="llama3-70b-8192"
        )
        
        # Local LM Studio
        AIApiFactory.create_openai_compatible(
            provider="lmstudio",
            api_key="not-needed",
            base_url="http://localhost:1234/v1",
            model="any-local-model"
        )
        
        # Any other OpenAI-compatible server
        AIApiFactory.create_openai_compatible(
            provider="custom",
            api_key="your-key",
            base_url="https://your-server.com/v1",
            model="your-model-name"
        )
        
        Args:
            provider: Provider identifier (for logging only)
            api_key: API key
            base_url: Base URL
            model: Model name
            **kwargs: Additional parameters passed to constructor
            
        Returns:
            OpenAICompatibleClient instance
        """
        
        logger.info(f"Creating OpenAI-compatible client for {provider}")
        
        return OpenAICompatibleClient(
            api_key=api_key,
            base_url=base_url,
            model=model,
            **kwargs
        )
    
    @staticmethod
    def create_ollama(
        model: str = "llama3.2",
        host: str = "http://localhost:11434",
        **kwargs
    ) -> OllamaClient:
        """Create Ollama client for local inference
        
        Args:
            model: Model name (will be pulled if not exists)
            host: Ollama server URL
            **kwargs: Additional parameters
            
        Returns:
            OllamaClient instance
        """
        
        logger.info(f"Creating Ollama client: {model}@{host}")
        
        return OllamaClient(
            host=host,
            model=model,
            **kwargs
        )


def get_ai_client_from_config(config_dict: Dict[str, Any]) -> object:
    """
    Factory function to create AI client from config dictionary
    
    Example config:
    
    ```yaml
    ai_model:
      provider: "openai_compatible"  # or "ollama"
      params:
        type: "openai_compatible"
        api_key: "your-api-key"
        base_url: "https://api.siliconflow.cn/v1"
        model: "Qwen/Qwen2.5-72B-Instruct"
        temperature: 0.0
        max_tokens: 32768
    ```
    
    Args:
        config_dict: Configuration dictionary
        
    Returns:
        Configured AI client instance
    """
    
    ai_config = config_dict.get('ai_model', {})
    provider_type = ai_config.get('type', ai_config.get('provider', 'openai_compatible'))
    params = ai_config.get('params', ai_config)
    
    if provider_type == 'ollama':
        return AIApiFactory.create_ollama(**params)
    elif provider_type in ['openai', 'openai_compatible', 'together', 'groq']:
        return AIApiFactory.create_openai_compatible(
            provider=provider_type,
            **params
        )
    else:
        # Default to openai_compatible with fallback URL
        logger.warning(f"Unknown provider type: {provider_type}, using default")
        return AIApiFactory.create_openai_compatible(
            provider="custom",
            **params
        )
