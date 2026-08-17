"""Data Models for Chapter Processing"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum


class ProcessingStatus(Enum):
    """Processing result status"""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"


@dataclass
class NovelChapterInput:
    """Input data for a single chapter"""
    
    chapter_id: str  # Format: vol_X_chap_Y
    chapter_title: str
    content: str
    volume_number: int
    chapter_number: int
    estimated_tokens: Optional[int] = None
    
    def __post_init__(self):
        """Validate input data"""
        if not self.chapter_id.startswith("vol_") or "_chap_" not in self.chapter_id:
            raise ValueError(f"Invalid chapter_id format: {self.chapter_id}")
        
        # Estimate tokens (rough approximation for Chinese text)
        if self.estimated_tokens is None:
            self.estimated_tokens = len(self.content) // 3 * 1.5  # Rough multiplier


@dataclass 
class ProcessingResult:
    """Complete result of processing a chapter"""
    
    chapter_id: str
    timestamp: str
    success: bool
    error_message: Optional[str] = None
    structured_data: Optional[Dict[str, Any]] = None
    original_text: Optional[str] = None
    next_context_summary: Optional[str] = None
    
    @property
    def has_data(self) -> bool:
        """Check if processing was successful with data"""
        return self.success and self.structured_data is not None


@dataclass
class BatchProcessingConfig:
    """Configuration for batch processing"""
    
    max_workers: int = 4
    retry_on_failure: bool = True
    continue_on_error: bool = True
    save_intermediate: bool = True
    progress_callback: Optional[callable] = None
    
    # Storage configuration
    output_dir: Optional[str] = None
    vector_db_path: Optional[str] = None
    
    # Configuration file (优先级高于环境变量)
    config_file: Optional[str] = None
    
    # Embedding configuration
    use_cloud_embeddings: bool = True
    embedding_api_key: Optional[str] = None


@dataclass
class ProcessingStats:
    """Statistics for batch processing"""
    
    total_chapters: int = 0
    processed_successfully: int = 0
    failed: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)
    
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage"""
        if self.total_chapters == 0:
            return 0.0
        return (self.processed_successfully / self.total_chapters) * 100
    
    @property
    def elapsed_time(self) -> Optional[float]:
        """Get elapsed time in seconds"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None


# Schema definitions for JSON validation (v3.0 精简字段命名，与 output_schema.json 保持一致)
# v3.1 取消全部 enum 约束，分类字段改为自由文本：不同小说设定体系各异（装备等级、地点类型等），
# 预定义枚举无法覆盖；由 AI 使用原文术语输出，需统计分析时再通过聚类脚本建立映射表归一

SCHEMA_METADATA = {
    "type": "object",
    "required": ["chapter_id", "chapter_title", "volume_number"],
    "properties": {
        "chapter_id": {"type": "string", "pattern": "^\\d+_text_chap_\\d+$"},
        "chapter_title": {"type": "string"},
        "volume_number": {"type": "integer", "minimum": 1},
        "confidence_score": {"type": "number", "minimum": 0.0, "maximum": 1.0}
    }
}

SCHEMA_WORLD_LINE_EVENTS = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "type": {"type": "string", "maxLength": 20},
            "name": {"type": "string"},
            "time": {"type": "string"},
            "description": {"type": "string", "maxLength": 100},
            "impact": {"type": "string", "maxLength": 20},
            "locations": {"type": "array", "items": {"type": "string"}},
            "consequences": {"type": "string"}
        }
    }
}

SCHEMA_LOCATION_ATLAS = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["name"],
        "properties": {
            "name": {"type": "string"},
            "type": {"type": "string", "maxLength": 20},
            "description": {"type": "string", "maxLength": 100},
            "change": {"type": ["string", "null"]},
            "characters": {"type": "array", "items": {"type": "string"}},
            "events": {"type": "array", "items": {"type": "string"}}
        }
    }
}

SCHEMA_CHARACTER_UPDATES = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["name", "protagonist", "actions"],
        "properties": {
            "name": {"type": "string"},
            "protagonist": {"type": "boolean"},
            "attributes": {"type": "object"},
            "identity": {"type": "object"},
            "personality": {
                "type": "object",
                "properties": {
                    "before": {"type": "array", "items": {"type": "string"}},
                    "after": {"type": "array", "items": {"type": "string"}},
                    "trigger": {"type": "string"}
                }
            },
            "objective": {
                "type": "object",
                "properties": {
                    "now": {"type": "string"},
                    "plan": {"type": "string"}
                }
            },
            "relationships": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "relation": {"type": "string"},
                        "trust": {"type": "integer", "minimum": 0, "maximum": 100},
                        "highlights": {"type": "array", "items": {"type": "string"}},
                        "pending": {"type": "array", "items": {"type": "string"}}
                    }
                }
            },
            "actions": {"type": "string"}
        }
    }
}

SCHEMA_STORY_SEGMENTS = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["id", "location", "characters", "events"],
        "properties": {
            "id": {"type": "integer"},
            "location": {"type": "string"},
            "characters": {"type": "array", "items": {"type": "string"}},
            "description": {"type": "string"},
            "events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "event": {"type": "string"},
                        "significance": {"type": "string"},
                        "tone": {"type": "string", "maxLength": 20}
                    }
                }
            },
            "dialogues": {"type": "array", "items": {"type": "string"}},
            "advancement": {"type": "string"}
        }
    }
}

SCHEMA_PROTAGONIST_GROWTH = {
    "type": "object",
    "properties": {
        "capability": {"type": "object"},
        "mental": {"type": "object"},
        "social": {"type": ["string", "null"]},
        "emotional": {"type": "object"},
        "summary": {"type": ["string", "null"]}
    }
}

SCHEMA_ITEM_CATALOG = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "category": {"type": "string", "maxLength": 20},
            "rarity": {"type": ["string", "null"]},
            "owner": {"type": "string"},
            "changes": {"type": "array", "items": {"type": "string"}},
            "role": {"type": "string"},
            "properties": {"type": "string"}
        }
    }
}

SCHEMA_HIDDEN_INFORMATION = {
    "type": "object",
    "properties": {
        "twists": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "truth": {"type": "string"},
                    "misdirection": {"type": "string"}
                }
            }
        },
        "revelations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "knowers": {"type": "array", "items": {"type": "string"}}
                }
            }
        }
    }
}

SCHEMA_FORESHADOWING_TRACKER = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "description": {"type": "string"},
            "resolution": {"type": "string"},
            "urgency": {"type": "string", "maxLength": 20},
            "characters": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0}
        }
    }
}

SCHEMA_CONTINUATION_READINESS = {
    "type": "object",
    "required": ["brief_summary"],
    "properties": {
        "brief_summary": {"type": "string", "maxLength": 200},
        "key_points": {"type": "array", "items": {"type": "string"}},
        "style_notes": {"type": ["object", "null"]}
    }
}

COMPLETE_SCHEMA = {
    "type": "object",
    "required": [
        "metadata", 
        "world_events", 
        "locations",
        "characters", 
        "scenes", 
        "growth", 
        "chapter_summary"
    ],
    "properties": {
        "metadata": SCHEMA_METADATA,
        "world_events": SCHEMA_WORLD_LINE_EVENTS,
        "locations": SCHEMA_LOCATION_ATLAS,
        "characters": SCHEMA_CHARACTER_UPDATES,
        "scenes": SCHEMA_STORY_SEGMENTS,
        "growth": SCHEMA_PROTAGONIST_GROWTH,
        "items": SCHEMA_ITEM_CATALOG,
        "plot_secrets": {
            "type": "object",
            "properties": {
                "twists": SCHEMA_HIDDEN_INFORMATION["properties"]["twists"],
                "revelations": SCHEMA_HIDDEN_INFORMATION["properties"]["revelations"],
                "clues": SCHEMA_FORESHADOWING_TRACKER
            }
        },
        "chapter_summary": SCHEMA_CONTINUATION_READINESS
    }
}
