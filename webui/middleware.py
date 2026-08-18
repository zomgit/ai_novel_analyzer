"""FastAPI 中间件：HTTP 请求日志记录"""

import json
import logging
from datetime import datetime

logger = logging.getLogger('http_requests')


class RequestLoggingMiddleware:
    """
    拦截所有 /api/* 请求并记录到独立日志文件（带轮转）
    
    记录内容：
    - 时间戳、方法、URL
    - 请求头、Body 大小
    - 响应状态码、耗时
    - 错误信息
    """
    
    async def dispatch(self, request, call_next):
        # 开始计时
        start_time = datetime.now()
        
        # 提取基本信息
        method = request.method
        url = str(request.url)
        
        # 读取请求体（仅用于 POST/PUT/PATCH）
        body_size = 0
        if method in ['POST', 'PUT', 'PATCH']:
            try:
                body = await request.body()
                body_size = len(body)
                # 重新包装 body
                request._body = body
            except Exception:
                body_size = 0
        
        try:
            # 处理请求
            response = await call_next(request)
            
            # 计算耗时
            end_time = datetime.now()
            elapsed_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # 构建日志条目（JSON 行格式）
            log_entry = {
                "timestamp": start_time.isoformat(),
                "type": "http_request",
                "method": method,
                "url": url,
                "request_headers": dict(request.headers),
                "request_body_size": body_size,
                "response_status": response.status_code,
                "response_time_ms": elapsed_ms,
                "error_message": None
            }
            
            logger.debug(json.dumps(log_entry, ensure_ascii=False))
            
            return response
            
        except Exception as e:
            # 异常时也记录
            end_time = datetime.now()
            elapsed_ms = int((end_time - start_time).total_seconds() * 1000)
            
            log_entry = {
                "timestamp": start_time.isoformat(),
                "type": "http_error",
                "method": method,
                "url": url,
                "request_body_size": body_size,
                "response_status": None,
                "response_time_ms": elapsed_ms,
                "error_message": str(e)
            }
            
            logger.error(json.dumps(log_entry, ensure_ascii=False))
            raise
