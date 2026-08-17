"""
配置管理模块
提供统一的配置管理系统，包括默认配置、用户配置和环境变量支持
"""

import os
import yaml
from pathlib import Path
from typing import Optional, Any, Dict


class ConfigManager:
    """统一的配置管理器
    
    特性:
    - 支持默认配置 + 用户配置的层级结构
    - 环境变量替换（如 ${VAR_NAME}）
    - 相对路径自动解析（相对于项目根目录）
    - 类型安全的属性访问
    """
    
    # === 配置路径定义 ===
    # 使用 __file__ 的绝对路径来定位配置文件
    _BASE_DIR = Path(__file__).parent.resolve().parents[2]  # 项目根目录
    DEFAULT_CONFIG = _BASE_DIR / "config/defaults.yaml"
    USER_CONFIG = _BASE_DIR / "config/production.yaml"
    
    def __init__(self, config_file: Optional[Path] = None):
        """
        Args:
            config_file: 可选的用户配置文件路径（覆盖默认 USER_CONFIG）
        """
        # 加载默认配置
        if not self.DEFAULT_CONFIG.exists():
            raise FileNotFoundError(f"默认配置文件不存在：{self.DEFAULT_CONFIG}")
        
        self.defaults: Dict[str, Any] = self._load_yaml(self.DEFAULT_CONFIG)
        
        # 加载用户配置
        self.user_config: Dict[str, Any] = {}
        if config_file and config_file.exists():
            self.user_config = self._load_yaml(config_file)
        elif Path(self.USER_CONFIG).exists():
            self.user_config = self._load_yaml(self.USER_CONFIG)
        
        # 合并配置（用户配置覆盖默认配置）
        self.config: Dict[str, Any] = {**self.defaults, **self.user_config}
        
        # 解析环境变量
        self._resolve_environment_variables()
        
        # 确保必需目录存在
        self._ensure_directories()
    
    def _resolve_environment_variables(self) -> None:
        """递归解析配置中的环境变量 ${VAR_NAME}"""
        def resolve_dict(d: dict) -> dict:
            for key, value in d.items():
                if isinstance(value, str):
                    # 匹配 ${VAR_NAME} 格式
                    if value.startswith('${') and value.endswith('}'):
                        var_name = value[2:-1]
                        if var_name in os.environ:
                            d[key] = os.environ[var_name]
                            continue
                elif isinstance(value, dict):
                    resolve_dict(value)
            return d
        
        resolve_dict(self.config)
    
    def _ensure_directories(self) -> None:
        """确保配置中定义的目录存在"""
        dirs_to_create = [
            self.input_dir,
            self.output_dir,
            self.processed_dir,
            self.db_dir,
            self.logs_dir,
            self.chromadb_path
        ]
        
        for dir_path in dirs_to_create:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"警告：无法创建目录 {dir_path}: {e}")
    
    def _load_yaml(self, file_path: Path) -> Dict[str, Any]:
        """安全加载 YAML 文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"YAML 解析错误 [{file_path}]: {e}")
    
    # ========== 标准路径属性 ==========
    
    @property
    def input_dir(self) -> Path:
        """标准输入目录（原始小说文本）"""
        return self._resolve_relative(self.config.get('io', {}).get('input_dir', 'user_data/novel_raw'))
    
    @property
    def output_dir(self) -> Path:
        """标准输出目录（切分+AI 分析结果）"""
        return self._resolve_relative(self.config.get('io', {}).get('output_dir', 'user_data/novel_data'))
    
    @property
    def processed_dir(self) -> Path:
        """处理后的 JSON 文件目录"""
        return self.output_dir / 'processed'
    
    @property
    def raw_dir(self) -> Path:
        """原始文本文件目录"""
        return self.output_dir / 'raw'
    
    @property
    def db_dir(self) -> Path:
        """数据库目录（SQLite + ChromaDB）"""
        return self._resolve_relative(self.config.get('db', {}).get('path', 'user_data/database'))
    
    @property
    def logs_dir(self) -> Path:
        """日志目录"""
        return self._resolve_relative(self.config.get('logging', {}).get('log_dir', 'logs'))
    
    @property
    def chromadb_path(self) -> Path:
        """ChromaDB 存储路径"""
        db_path = self.db_dir / 'chromadb'
        return self._resolve_relative(str(db_path))
    
    @property
    def sqlite_db_path(self) -> Path:
        """SQLite 数据库文件路径"""
        return self.db_dir / 'novel_analyzer.db'
    
    # ========== AI API 配置 ==========
    
    @property
    def api_provider(self) -> str:
        """API 提供者"""
        return self.config.get('ai_api', {}).get('provider', 'siliconflow')
    
    @property
    def api_base_url(self) -> str:
        """API 基础 URL"""
        return self.config.get('ai_api', {}).get('base_url', 'https://api.siliconflow.cn/v1')
    
    @property
    def api_key(self) -> Optional[str]:
        """API Key（从配置或环境变量获取）"""
        ai_config = self.config.get('ai_api', {})
        return ai_config.get('api_key')
    
    @property
    def api_model(self) -> str:
        """AI 模型名称"""
        return self.config.get('ai_api', {}).get('model', 'deepseek-v4')
    
    @property
    def max_tokens(self) -> int:
        """最大 Token 数"""
        return self.config.get('ai_api', {}).get('max_tokens', 8192)
    
    @property
    def temperature(self) -> float:
        """生成温度"""
        return self.config.get('ai_api', {}).get('temperature', 0.7)
    
    # ========== 维度配置 ==========
    
    @property
    def dimension_config_path(self) -> Path:
        """维度配置文件路径"""
        return self._resolve_relative(self.config.get('dimensions', {}).get('config_path', 'config/dimensions/xianxia.yaml'))
    
    @property
    def auto_generate_prompt(self) -> bool:
        """是否自动生成 Prompt"""
        return self.config.get('dimensions', {}).get('auto_generate_prompt', True)
    
    @property
    def batch_size(self) -> int:
        """批量处理大小"""
        return self.config.get('dimensions', {}).get('batch_size', 10)
    
    @property
    def parallel_workers(self) -> int:
        """并行 worker 数量"""
        return self.config.get('dimensions', {}).get('parallel_workers', 4)
    
    # ========== ChromaDB 配置 ==========
    
    @property
    def vector_collection_name(self) -> str:
        """向量集合名称"""
        return self.config.get('vector_store', {}).get('collection_name', 'novel_chunks')
    
    # ========== 日志配置 ==========
    
    @property
    def log_level(self) -> str:
        """日志级别"""
        return self.config.get('logging', {}).get('level', 'INFO')
    
    @property
    def log_max_bytes(self) -> int:
        """日志文件最大字节数"""
        return self.config.get('logging', {}).get('max_bytes', 10485760)  # 10MB
    
    @property
    def log_backup_count(self) -> int:
        """日志备份数量"""
        return self.config.get('logging', {}).get('backup_count', 5)
    
    # ========== 辅助方法 ==========
    
    def _resolve_relative(self, path_str: str) -> Path:
        """
        解析相对路径（相对于项目根目录）
        
        Args:
            path_str: 路径字符串
            
        Returns:
            绝对路径
        """
        p = Path(path_str)
        if p.is_absolute():
            return p
        return Path.cwd() / p
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        通用配置获取方法（支持嵌套键）
        
        Args:
            key: 配置键（支持点号分隔的嵌套键，如 'ai_api.model'）
            default: 默认值
            
        Returns:
            配置值或默认值
        """
        keys = key.split('.')
        value: Any = self.config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
            if value is None:
                return default
        
        return value
    
    def to_dict(self) -> Dict[str, Any]:
        """导出为字典（用于调试和日志）"""
        return self.config
    
    def __repr__(self) -> str:
        """字符串表示"""
        return (
            f"ConfigManager(\n"
            f"  input_dir={self.input_dir}\n"
            f"  output_dir={self.output_dir}\n"
            f"  db_dir={self.db_dir}\n"
            f"  api_provider={self.api_provider}\n"
            f")"
        )


# ========== 快捷函数 ==========

def get_config(config_file: Optional[Path] = None) -> ConfigManager:
    """
    快捷获取 ConfigManager 实例（全局单例模式）
    
    Args:
        config_file: 可选的配置文件路径
        
    Returns:
        ConfigManager 实例
    """
    # 使用模块级变量实现单例
    if not hasattr(get_config, "_instance"):
        get_config._instance = ConfigManager(config_file)
    return get_config._instance


# ========== 测试入口 ==========

if __name__ == "__main__":
    # 测试配置加载
    print("=== 配置管理器测试 ===\n")
    
    config = ConfigManager()
    print(config)
    
    print("\n=== 详细配置 ===")
    for key, value in config.to_dict().items():
        print(f"{key}: {value}")
