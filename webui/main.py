"""
AI Novel Analyzer Web UI - FastAPI Backend
单文件启动，零配置即用
"""
import sys
import threading
import time
import os
from pathlib import Path
from typing import Optional, List

# 添加项目根目录到 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
from pathlib import Path
import asyncio
import shutil
import uuid
import json
from datetime import datetime

from ai_novel_analyzer.core.config_manager import get_config
from ai_novel_analyzer.core import logging_config as task_logger
from webui.middleware import RequestLoggingMiddleware
# TODO: batch_processor 需要改造以支持异步回调和进度报告
# from scripts.batch_processor import run_chapter_analysis  
# from scripts.check_progress import get_all_task_status  # 需要改造为返回 dict
from webui.api_splitter import process_novel_upload, finalize_split_to_workspace
from scripts.split_book import sanitize_dirname

app = FastAPI(title="AI Novel Analyzer Web UI", version="1.0.0")

# 路径配置
BASE_DIR = Path(__file__).parent.parent
WORKSPACE_DIR = BASE_DIR / "workspace"
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = WORKSPACE_DIR / "temp" / "uploads"
FRONTEND_DIR = Path(__file__).parent / "frontend"

# 确保目录存在
OUTPUT_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# 模板和静态目录
templates = Jinja2Templates(directory=FRONTEND_DIR / "templates")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")
# 挂载 workspace 目录（供前端读取 volume_meta.json 等元数据）
app.mount("/workspace", StaticFiles(directory=WORKSPACE_DIR), name="workspace")

# 全局状态存储（单机本地版无需数据库）
task_status_store = {}


@app.post("/api/shutdown")
async def shutdown_server():
    """优雅关闭服务器（供启动脚本重启前调用）

    延迟 0.5 秒后退出进程，确保响应先返回给客户端。
    """
    def _delayed_shutdown():
        time.sleep(0.5)
        print("🛑 收到关闭请求，服务器正在退出...")
        os._exit(0)

    threading.Thread(target=_delayed_shutdown, daemon=True).start()
    return {"success": True, "message": "服务器正在关闭"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    print("=== AI Novel Analyzer Web UI 已启动 ===")
    print(f"工作目录：{BASE_DIR}")
    print(f"前端目录：{FRONTEND_DIR}")
    
    # 初始化数据库（WAL 模式）- 确保在任务记录前完成
    db_path = BASE_DIR / 'workspace' / 'db' / 'novel_analyzer.db'
    db_path.parent.mkdir(parents=True, exist_ok=True)
    from ai_novel_analyzer.core import logging_config as task_logger
    try:
        task_logger.init_analysis_tasks_db(db_path)
        print(f"✅ 任务历史数据库已初始化：{db_path}")
    except Exception as e:
        print(f"⚠️  数据库初始化失败：{e}")
    
    # 添加 HTTP 请求记录中间件
    app.add_middleware(RequestLoggingMiddleware)
    print("✅ HTTP 请求日志中间件已加载")
    
    yield
    
    # 关闭时清理
    print("Web UI 正在关闭...")


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """总览页面"""
    return templates.TemplateResponse(request=request, name="dashboard.html")


@app.get("/splitting")
async def splitting_page(request: Request):
    """拆书工坊页面"""
    return templates.TemplateResponse(request=request, name="splitting.html")


@app.get("/analysis")
async def analysis_page(request: Request):
    """分析任务中心页面"""
    return templates.TemplateResponse(request=request, name="analysis.html")


@app.get("/dimensions")
async def dimensions_page(request: Request):
    """维度库浏览页面"""
    return templates.TemplateResponse(request=request, name="dimensions.html")


@app.get("/settings")
async def settings_page(request: Request):
    """设置页面"""
    return templates.TemplateResponse(request=request, name="settings.html")


# ========== API 接口层 ==========

# ========== 项目和书籍管理 API ==========

@app.post("/api/upload")
async def upload_novel(file: UploadFile = File(...)):
    """上传小说文件并预处理
    
    功能：
    1. 检测编码
    2. 识别章节分割点
    3. 返回预览结果供用户确认
    """
    if not file.filename.endswith('.txt'):
        raise HTTPException(status_code=400, detail="仅支持 TXT 格式文件")
    
    try:
        # 保存临时文件
        file_id = str(uuid.uuid4())
        temp_file = TEMP_DIR / f"{file_id}_{file.filename}"
        
        with open(temp_file, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # 调用拆书脚本（API 版）
        result = await asyncio.to_thread(process_novel_upload, str(temp_file))
        
        return {
            "success": True,
            "file_id": file_id,
            "filename": file.filename,
            "encoding": result.encoding,
            "total_chars": result.total_chars,
            "chapters_preview": result.chapters_preview,
            "total_chapters": result.total_chapters
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/split/{file_id}")
async def finalize_split(file_id: str, request: Request):
    """确认拆分：按 workspace/projects/{项目}/{书}/ 结构真实写盘

    与 CLI（scripts/split_book.py）行为一致：
    - 项目名/书名/作者 必填（与 CLI 的 --project/--book/--author 对齐）
    - 卷目录已存在且未指定 overwrite 时返回 409
    """
    body = await request.json()
    project = (body.get("project") or "").strip()
    book = (body.get("book") or "").strip()
    author = (body.get("author") or "").strip()
    overwrite = bool(body.get("overwrite", False))
    # volumes_data: [{name, author}, ...]
    volumes_data = body.get("volumes_data") or []

    # 提取卷名列表（向后兼容原有逻辑）
    volume_titles = [vol.get("name", "") for vol in volumes_data if isinstance(vol, dict)]

    # 必填校验（与 CLI 一致：绝不从文件名猜测）
    missing = [name for name, val in [("project", project), ("book", book), ("author", author)] if not val]
    if missing:
        raise HTTPException(status_code=400, detail=f"缺少必填参数：{', '.join(missing)}")
    if len(project) > 30 or len(book) > 30 or len(author) > 30:
        raise HTTPException(status_code=400, detail="项目名/书名/作者长度不能超过 30 字符")

    try:
        # 定位源文件：优先临时上传目录，其次 book_meta 记录的源文件（重新分割场景）
        files = list(TEMP_DIR.glob(f"{file_id}_*.txt"))
        source_file = files[0] if files else None
        if source_file is None:
            config = get_config()
            book_dir = config.projects_dir / sanitize_dirname(project) / sanitize_dirname(book)
            book_meta_path = book_dir / "book_meta.json"
            if book_meta_path.exists():
                try:
                    import json as json_lib
                    book_meta = json_lib.loads(book_meta_path.read_text(encoding="utf-8-sig"))
                    pending_path = book_meta.get("pending_source_path")
                    if pending_path:
                        candidate = book_dir / pending_path
                        if candidate.exists():
                            source_file = candidate
                except Exception:
                    pass
        if source_file is None:
            raise HTTPException(status_code=404, detail="未找到源文件（可能已过期，请重新上传或重新分割）")

        # 写盘前预检：卷目录已存在且未指定覆盖时提前返回 409
        from scripts.split_book import build_volume_dirname, group_chapters_by_volume
        from ai_novel_analyzer.utils.chapter_splitter import ChapterSplitter
        from scripts.split_book import DEFAULT_VOLUME_TITLE
        
        config = get_config()
        title_patterns = config.get('chapter_splitting.title_patterns')
        book_dir = config.projects_dir / sanitize_dirname(project) / sanitize_dirname(book)
        
        # 自动递增卷号：查询已有最大卷号
        existing_volumes = []
        if book_dir.exists():
            import re
            for d in book_dir.iterdir():
                if d.is_dir() and d.name.startswith('vol_'):
                    match = re.match(r'vol_(\d+)_', d.name)
                    if match:
                        existing_volumes.append(int(match.group(1)))
        max_existing_volume = max(existing_volumes) if existing_volumes else 0
        
        if not overwrite:
            splitter = ChapterSplitter(fallback_segment_chars=3000, default_volume=max_existing_volume + 1, title_patterns=title_patterns)
            chapters = splitter.split_file(source_file, None)
            groups = group_chapters_by_volume(chapters)
            existing = []
            for vol_num, vol_chapters in groups.items():
                recognized_title = next(
                    (ch.volume_title for _, ch in vol_chapters if ch.volume_title), None
                )
                vol_dirname = build_volume_dirname(
                    vol_num, recognized_title or DEFAULT_VOLUME_TITLE)
                if (book_dir / vol_dirname / "volume_meta.json").exists():
                    existing.append(vol_dirname)
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=f"卷目录已存在：{', '.join(existing)}。确认覆盖请重新提交（overwrite=true）",
                )

        # 真实写盘（复用 scripts/split_book.py 的写入函数，传入用户卷名）
        result = await asyncio.to_thread(
            finalize_split_to_workspace,
            str(source_file), project, book, author, overwrite,
            "xianxia.yaml", volumes_data, max_existing_volume + 1,
        )

        # 清理临时文件（仅清理上传的临时文件，不删除 source 存档）
        if source_file.parent == TEMP_DIR:
            source_file.unlink()

        # 写盘成功：更新书籍元数据（split_status → done，清除待分割信息）
        import json as json_lib
        from datetime import datetime, timezone
        book_meta_path = book_dir / "book_meta.json"
        if book_meta_path.exists():
            try:
                book_meta = json_lib.loads(book_meta_path.read_text(encoding="utf-8-sig"))
                book_meta["split_status"] = "done"
                book_meta.pop("pending_file_id", None)
                book_meta.pop("pending_source_path", None)
                book_meta.pop("pending_preview", None)
                book_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
                with open(book_meta_path, "w", encoding="utf-8") as f:
                    json_lib.dump(book_meta, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        return {
            "success": True,
            "message": f"已写入 {result['chapters_count']} 章 → {result['volumes']} 卷",
            "book_dir": result["book_dir"],
            "volumes": result["volumes"],
            "chapters_count": result["chapters_count"],
            "split_status": "done"
        }

    except HTTPException:
        raise
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze")
async def start_analysis(request: Request):
    """启动分析任务（book/volume 双模式，支持勾选卷 + 并发）"""
    import asyncio
    import uuid
    
    body = await request.json()
    scope = body.get("scope")  # "book" or "volume"
    project = (body.get("project") or "").strip()
    book = (body.get("book") or "").strip()
    volume = (body.get("volume") or "").strip() if scope == 'volume' else None
    
    # 新增：勾选卷列表 + 并发模式
    selected_volumes = body.get("selected_volumes")  # List[str] 卷目录名列表
    concurrency_mode = body.get("concurrency_mode", "sequential")  # "sequential" | "concurrent"
    max_concurrent = min(int(body.get("max_concurrent", 3)), 5)  # 上限 5
    
    # 参数校验
    if not project:
        raise HTTPException(status_code=400, detail="缺少必填参数：project")
    if not book:
        raise HTTPException(status_code=400, detail="缺少必填参数：book")
    if scope == "volume" and not volume:
        raise HTTPException(status_code=400, detail="卷分析模式必须指定 volume 参数")
    if scope == "book" and selected_volumes is not None and len(selected_volumes) == 0:
        raise HTTPException(status_code=400, detail="至少选择一个卷")
    
    task_id = str(uuid.uuid4())
    task_status_store[task_id] = {
        "status": "queued", 
        "progress": 0,
        "scope": scope,
        "details": {
            "project": project,
            "book": book,
            "volume": volume,
            "selected_volumes": selected_volumes,
            "concurrency_mode": concurrency_mode
        }
    }
    
    asyncio.create_task(run_analysis_background(
        task_id, scope, project, book, volume,
        selected_volumes=selected_volumes,
        concurrency_mode=concurrency_mode,
        max_concurrent=max_concurrent
    ))
    
    return {"task_id": task_id, "status": "started"}


async def run_analysis_background(
    task_id: str,
    scope: str,
    project: str,
    book: str,
    volume: Optional[str] = None,
    selected_volumes: Optional[list] = None,
    concurrency_mode: str = "sequential",
    max_concurrent: int = 3
):
    """后台运行分析任务（book/volume 双模式，支持勾选卷 + 并发）"""
    from scripts.batch_processor import AutomatedBatchProcessor, BatchProcessingConfig
    import json as json_lib
    
    # Step 1: 落盘记录任务开始
    volume_dir = volume if scope == 'volume' else None
    task_logger.record_task_start(task_id, scope, project, book, volume_dir)
    
    try:
        task_status_store[task_id]["status"] = "running"
        
        # 使用已有的全局日志系统（不再调用 basicConfig 避免覆盖已有配置）
        import logging
        logger = logging.getLogger(__name__)
        
        config = get_config()
        projects_dir = config.projects_dir
        
        # 初始化统计指标
        total_chapters = 0
        success_count = 0
        failed_count = 0
        retry_count = 0
        detail_json = {}
        
        # 辅助函数：创建并执行单卷分析
        def create_processor(vol_dir: Path):
            processor_config = BatchProcessingConfig(
                volume_dir=str(vol_dir),
                max_workers=1,
                continue_on_error=True,
                vector_db_path=str(config.chromadb_path),
                embedding_api_key=os.getenv('SILICONFLOW_API_KEY'),
                use_cloud_embeddings=True,
                retry_on_failure=True,
                save_intermediate=True
            )
            return AutomatedBatchProcessor(processor_config)
        
        if scope == "book":
            # === 按书籍分析：遍历选中的卷 ===
            book_dir = projects_dir / sanitize_dirname(project) / sanitize_dirname(book)
            
            # 获取所有卷（按 book_meta 顺序）
            all_volumes = get_ordered_volumes(book_dir)
            
            # 按勾选过滤（selected_volumes=None 表示全选）
            if selected_volumes is not None:
                selected_set = set(selected_volumes)
                volumes = [v for v in all_volumes if v.name in selected_set]
            else:
                volumes = all_volumes
            
            # 预检：统计各卷待处理章数，过滤空卷
            vol_pending = []  # [(vol_dir, pending_count)]
            for vol_dir in volumes:
                vol_meta_path = vol_dir / "volume_meta.json"
                if not vol_meta_path.exists():
                    continue
                with open(vol_meta_path, 'r', encoding='utf-8-sig') as f:
                    vol_meta = json_lib.load(f)
                chapters = vol_meta.get('chapters', [])
                pending = sum(1 for c in chapters if c.get('status') in ('pending', 'failed'))
                if pending > 0:
                    vol_pending.append((vol_dir, pending))
            
            total_items = len(vol_pending)
            total_chapters = sum(p for _, p in vol_pending)
            completed_chapters = 0  # 按章加权进度
            processed_items = 0
            
            if concurrency_mode == "concurrent" and total_items > 1:
                # === 并发模式 ===
                semaphore = asyncio.Semaphore(max_concurrent)
                # 线程安全的计数器
                import threading
                progress_lock = threading.Lock()
                
                async def process_vol_concurrent(vol_dir: Path, pending: int):
                    nonlocal success_count, failed_count, completed_chapters, processed_items
                    async with semaphore:
                        update_progress(task_id, f"正在分析：{vol_dir.name} ({pending}章待处理)")
                        processor = create_processor(vol_dir)
                        vol_success = await asyncio.to_thread(processor.run_batch, enable_stream=False)
                        
                        with progress_lock:
                            if vol_success:
                                success_count += 1
                                vol_summary = {"chapters": pending, "success": pending, "failed": 0}
                            else:
                                failed_count += 1
                                vol_summary = {"chapters": pending, "success": 0, "failed": pending}
                            detail_json[vol_dir.name] = vol_summary
                            completed_chapters += pending
                            processed_items += 1
                            progress_pct = int((completed_chapters / total_chapters) * 100) if total_chapters > 0 else 0
                            task_status_store[task_id].update({
                                "progress": progress_pct,
                                "message": f"进度：{processed_items}/{total_items} 卷完成（{completed_chapters}/{total_chapters}章）"
                            })
                
                # 并发启动所有卷
                tasks = [process_vol_concurrent(vd, p) for vd, p in vol_pending]
                await asyncio.gather(*tasks)
                
            else:
                # === 顺序模式（默认） ===
                for vol_dir, pending in vol_pending:
                    update_progress(task_id, f"正在分析：{vol_dir.name} ({pending}章待处理)")
                    
                    processor = create_processor(vol_dir)
                    vol_success = await asyncio.to_thread(processor.run_batch, enable_stream=False)
                    
                    if vol_success:
                        success_count += 1
                        vol_summary = {"chapters": pending, "success": pending, "failed": 0}
                    else:
                        failed_count += 1
                        vol_summary = {"chapters": pending, "success": 0, "failed": pending}
                    
                    detail_json[vol_dir.name] = vol_summary
                    completed_chapters += pending
                    processed_items += 1
                    
                    progress_pct = int((completed_chapters / total_chapters) * 100) if total_chapters > 0 else 0
                    task_status_store[task_id].update({
                        "progress": progress_pct,
                        "message": f"进度：{processed_items}/{total_items} 卷完成（{completed_chapters}/{total_chapters}章）"
                    })
                
        elif scope == "volume":
            # === 按卷分析：只处理单个卷 ===
            if not volume:
                raise ValueError("卷分析模式必须指定 volume 参数")
            
            vol_dir = projects_dir / sanitize_dirname(project) / sanitize_dirname(book) / sanitize_dirname(volume)
            
            # 检查是否有待处理章节
            vol_meta_path = vol_dir / "volume_meta.json"
            if not vol_meta_path.exists():
                raise ValueError(f"卷目录不存在：{vol_dir}")
            
            with open(vol_meta_path, 'r', encoding='utf-8-sig') as f:
                vol_meta = json_lib.load(f)
            
            chapters = vol_meta.get('chapters', [])
            pending = sum(1 for c in chapters if c.get('status') in ('pending', 'failed'))
            
            if pending == 0:
                task_status_store[task_id].update({
                    "status": "completed",
                    "progress": 100,
                    "message": "本卷所有章节已完成分析"
                })
                return
            
            update_progress(task_id, f"正在分析：{vol_dir.name} ({pending}章待处理)")
            
            # 执行分析
            processor = create_processor(vol_dir)
            success = await asyncio.to_thread(processor.run_batch, enable_stream=False)
            
            # 统计结果
            total_chapters = pending
            if success:
                success_count = 1
                detail_json[volume] = {"chapters": pending, "success": pending, "failed": 0}
                retry_count += 0
            else:
                failed_count = 1
                detail_json[volume] = {"chapters": pending, "success": 0, "failed": pending}
            
            task_status_store[task_id].update({
                "status": "completed" if success else "failed",
                "progress": 100,
                "message": f"{'✅ 分析完成' if success else '❌ 分析失败'}"
            })
        
        # 任务结束落盘
        final_status = "success" if failed_count == 0 else "failed"
        failure_reason = None if final_status == "success" else "部分章节分析失败"
        
        metrics = {
            "total_chapters": total_chapters,
            "success_count": success_count,
            "failed_count": failed_count,
            "retry_count": retry_count,
            "detail_json": detail_json
        }
        
        task_logger.finalize_task(task_id, final_status, metrics, failure_reason)
        
    except Exception as e:
        logger.error(f"分析任务失败：{e}", exc_info=True)
        task_status_store[task_id].update({
            "status": "failed",
            "error": str(e)
        })
        
        # 异常时也要落盘
        metrics = {
            "total_chapters": total_chapters,
            "success_count": success_count,
            "failed_count": failed_count + 1,
            "retry_count": retry_count,
            "detail_json": detail_json
        }
        task_logger.finalize_task(task_id, "failed", metrics, str(e))


@app.get("/api/tasks/{task_id}/log")
async def get_task_log(task_id: str):
    """SSE 推送任务日志流"""
    from starlette.responses import StreamingResponse
    
    async def generate():
        while task_id in task_status_store:
            status = task_status_store[task_id]
            log_entry = f"[{status['status'].upper()}] 进度：{status.get('progress', 0)}%\n"
            yield f"data: {log_entry}\n\n"
            await asyncio.sleep(1)
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/stats")
async def get_statistics():
    """获取总览统计数据"""
    config = get_config()
    projects_dir = config.projects_dir

    # 统计 workspace/projects 下已拆分的章节源文件数（chap_XXXX.txt）
    chapters_total = sum(
        1 for p in projects_dir.rglob("chap_*.txt")
    ) if projects_dir.exists() else 0

    stats = {
        "chapters_total": chapters_total,
        "characters": 0,
        "locations": 0,
        "items": 0,
        "events": 0,
        "skills": 0,
        "world_building": 0
    }

    # TODO: 从数据库中读取真实维度数据
    return stats


@app.get("/api/projects")
async def get_projects():
    """列出已有项目（完整嵌套结构，包含 book_meta、volume_meta 所有字段）"""
    import json as json_lib

    config = get_config()
    projects_dir = config.projects_dir
    if not projects_dir.exists():
        return []

    projects = []
    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        
        meta_path = project_dir / "project_meta.json"
        books = []
        if meta_path.exists():
            try:
                # ✅ P0-6: 直接展开项目元数据，透传所有原始字段
                project_meta = json_lib.loads(meta_path.read_text(encoding="utf-8-sig"))
                
                # 读取各书的 book_meta.json，也全部透传
                for book_name in project_meta.get("books", []):
                    book_meta_path = project_dir / book_name / "book_meta.json"
                    if book_meta_path.exists():
                        book_meta = json_lib.loads(book_meta_path.read_text(encoding="utf-8-sig"))
                        # 归一化 volumes：旧数据（字符串数组）升级为对象数组，保证前端树可渲染
                        raw_vols = book_meta.get("volumes", [])
                        if raw_vols and isinstance(raw_vols[0], str):
                            book_meta["volumes"] = [
                                {"name": "", "dir": d, "chapter_count": 0} for d in raw_vols
                            ]
                        books.append({
                            **book_meta,  # 直接展开所有字段
                            "_path": f"{project_dir.name}/{book_name}/book_meta.json"
                        })
            except Exception:
                pass
        
        projects.append({
            **project_meta,  # 直接展开所有字段
            "books": books,  # ✅ 用展开后的 book_meta 对象数组覆盖原始字符串数组
            "_path": f"{project_dir.name}/project_meta.json"
        })
    
    return projects


@app.post("/api/projects")
async def create_project(request: Request):
    """创建新项目"""
    body = await request.json()
    name = (body.get("name") or "").strip()
    
    if not name:
        raise HTTPException(status_code=400, detail="项目名称不能为空")
    
    import json as json_lib
    from pathlib import Path
    from datetime import datetime, timezone
    
    config = get_config()
    projects_dir = config.projects_dir
    project_dir = projects_dir / sanitize_dirname(name)
    
    if project_dir.exists():
        raise HTTPException(status_code=409, detail=f"项目已存在：{name}")
    
    # 创建目录和元数据文件
    project_dir.mkdir(parents=True, exist_ok=True)
    project_meta = {
        "name": name,
        "books": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "dimension_config": "xianxia.yaml"
    }
    
    with open(project_dir / "project_meta.json", "w", encoding="utf-8") as f:
        json_lib.dump(project_meta, f, ensure_ascii=False, indent=2)
    
    return {"success": True, "message": f"项目已创建：{name}"}


def get_ordered_volumes(book_dir: Path) -> List[Path]:
    """按 book_meta 顺序返回卷目录列表"""
    import json as json_lib
    
    volumes = []
    book_meta_path = book_dir / "book_meta.json"
    book_meta_volumes = []
    
    if book_meta_path.exists():
        try:
            book_meta = json_lib.loads(book_meta_path.read_text(encoding='utf-8-sig'))
            raw_vols = book_meta.get('volumes', [])
            book_meta_volumes = [
                (v['dir'] if isinstance(v, dict) else v) for v in raw_vols
            ]
        except Exception:
            pass
    
    all_vol_dirs = {p.name: p for p in book_dir.glob('vol_*') if p.is_dir()}
    ordered_vol_dirs = []
    
    for vol_name in book_meta_volumes:
        if vol_name in all_vol_dirs:
            ordered_vol_dirs.append(all_vol_dirs.pop(vol_name))
    
    ordered_vol_dirs.extend(sorted(all_vol_dirs.values()))
    
    return ordered_vol_dirs


def update_progress(task_id: str, message: str):
    """更新任务进度"""
    if task_id in task_status_store:
        task_status_store[task_id].update({
            "status": "running",
            "message": message
        })


@app.get("/api/chapters/{chapter_id}/details")
async def get_chapter_details(chapter_id: str):
    """获取章节详情（从卷目录 JSON 读取）"""
    # TODO: 改为从 workspace 卷目录直接读取 JSON 文件
    raise HTTPException(status_code=501, detail="章节详情接口待重构")


@app.get("/api/dimensions/characters")
async def get_characters(volume_id: str = "vol_1"):
    """获取角色维度库"""
    # TODO: 改为从 workspace 卷目录 JSON 聚合角色数据
    raise HTTPException(status_code=501, detail="角色维度库接口待重构")


@app.get("/api/config/api-keys")
async def get_api_keys_config():
    """获取当前 API Key 配置状态"""
    from src.ai_novel_analyzer.core.config_manager import ConfigManager
    
    config = ConfigManager()
    return {
        "openai_key_set": bool(config.get("OPENAI_API_KEY")),
        "anthropic_key_set": bool(config.get("ANTHROPIC_API_KEY")),
        "google_key_set": bool(config.get("GOOGLE_API_KEY"))
    }


@app.post("/api/config/api-keys")
async def save_api_keys(config: dict):
    """保存 API Key 配置"""
    from src.ai_novel_analyzer.core.config_manager import ConfigManager
    
    config_manager = ConfigManager()
    
    for key, value in config.items():
        if value:  # 非空才更新
            config_manager.set(key.upper(), value)
    
    return {"success": True, "message": "配置已保存"}


@app.get("/api/book/status")
async def get_book_status(project: str, book: str):
    """获取书籍的拆分状态和分析进度"""
    import json as json_lib
    from scripts.split_book import build_volume_dirname
    
    config = get_config()
    project_dir = config.projects_dir / sanitize_dirname(project)
    book_dir = project_dir / sanitize_dirname(book)
    
    result = {
        "split_progress": 0,
        "analysis_progress": 0,
        "dimension_sync": False,
        "vector_sync": False,
        "volumes": [],
        "error": None
    }
    
    if not book_dir.exists():
        result["error"] = "书籍目录不存在"
        return result
    
    # 读取书籍元数据：分割状态、待确认分割信息、卷顺序
    book_meta_path = book_dir / "book_meta.json"
    split_status = "unknown"
    pending_file_id = None
    preview = None
    book_meta_volumes = []  # book_meta 中声明的卷顺序（dir 列表）
    if book_meta_path.exists():
        try:
            book_meta = json_lib.loads(book_meta_path.read_text(encoding="utf-8-sig"))
            pending_file_id = book_meta.get("pending_file_id")
            preview = book_meta.get("pending_preview")
            result["author"] = book_meta.get("author", "")
            result["book_name"] = book_meta.get("book_name", book)
            result["source_files"] = book_meta.get("source_files", [])
            raw_vols = book_meta.get("volumes", [])
            # 兼容旧数据（字符串数组）
            book_meta_volumes = [
                (v["dir"] if isinstance(v, dict) else v) for v in raw_vols
            ]
            split_status = book_meta.get("split_status")
        except Exception:
            pass
    
    # 查找卷目录（按 book_meta 声明的顺序，保证与拖拽排序一致）
    volumes = []
    split_count = 0
    total_chapters = 0
    
    all_vol_dirs = {p.name: p for p in book_dir.glob("vol_*") if p.is_dir()}
    ordered_vol_dirs = []
    for vol_name in book_meta_volumes:
        if vol_name in all_vol_dirs:
            ordered_vol_dirs.append(all_vol_dirs.pop(vol_name))
    # book_meta 未声明的卷目录（如 CLI 直接拆入）追加在后
    ordered_vol_dirs.extend(sorted(all_vol_dirs.values()))
    
    for vol_dir in ordered_vol_dirs:
        if not vol_dir.is_dir():
            continue
        
        vol_meta_path = vol_dir / "volume_meta.json"
        if not vol_meta_path.exists():
            continue
        
        try:
            vol_meta = json_lib.loads(vol_meta_path.read_text(encoding="utf-8-sig"))
            chapters = vol_meta.get("chapters", [])
            total_chapters = len(chapters)  # volume_meta.json 无 total_chapters 字段，用数组长度
            completed = sum(1 for c in chapters if c.get("status") == "processed")
            failed = sum(1 for c in chapters if c.get("status") == "failed")
            vol_chars = sum(c.get("char_count", 0) for c in chapters)
            
            split_percent = 100 if total_chapters > 0 else 0
            analysis_percent = int((completed / total_chapters * 100)) if total_chapters > 0 else 0
            
            volumes.append({
                "id": vol_meta.get("volume_number", 1),
                "title": vol_meta.get("volume_title", ""),
                "volume_author": vol_meta.get("volume_author", ""),
                "dir": vol_dir.name,  # 卷目录名，用于后续 API 调用
                "total_chapters": total_chapters,
                "completed_chapters": completed,
                "failed_chapters": failed,
                "total_chars": vol_chars,
                "split_progress": split_percent,
                "analysis_progress": analysis_percent
            })
            
            split_count += total_chapters
            
        except Exception:
            continue
    
    result["volumes"] = volumes
    
    # 计算整体进度
    result["split_progress"] = 100 if split_count > 0 else 0
    
    if volumes:
        avg_analysis = sum(v["analysis_progress"] for v in volumes) / len(volumes)
        result["analysis_progress"] = int(avg_analysis)
    
    # 分割状态兑底：旧数据无 split_status 字段时按卷目录推断
    if not split_status:
        split_status = "done" if volumes else "unknown"
    result["split_status"] = split_status
    result["pending_file_id"] = pending_file_id
    result["preview"] = preview
    
    # 检查维度库和向量库同步状态（待实现）
    result["dimension_sync"] = result["analysis_progress"] >= 80
    result["vector_sync"] = False  # TODO: 实现向量库同步状态检查
    
    return result


@app.get("/api/chapters")
async def get_chapter_list(project: str, book: str, volume: str = None):
    """获取选定书籍的所有章节及其分析状态（可选按卷过滤）"""
    import json as json_lib
    
    config = get_config()
    project_dir = config.projects_dir / sanitize_dirname(project)
    book_dir = project_dir / sanitize_dirname(book)
    
    chapters = []
    chapter_id_counter = 0
    
    if not book_dir.exists():
        return chapters
    
    # 如果指定了卷，只返回该卷的章节
    if volume:
        vol_dir = book_dir / sanitize_dirname(volume)
        if not vol_dir.exists():
            return chapters
        ordered_vol_dirs = [vol_dir]
    else:
        # 按 book_meta 声明的卷顺序遍历（与拖拽排序一致）
        book_meta_path = book_dir / "book_meta.json"
        book_meta_volumes = []
        if book_meta_path.exists():
            try:
                book_meta = json_lib.loads(book_meta_path.read_text(encoding="utf-8-sig"))
                book_meta_volumes = [
                    (v["dir"] if isinstance(v, dict) else v) for v in book_meta.get("volumes", [])
                ]
            except Exception:
                pass
        
        all_vol_dirs = {p.name: p for p in book_dir.glob("vol_*") if p.is_dir()}
        ordered_vol_dirs = []
        for vol_name in book_meta_volumes:
            if vol_name in all_vol_dirs:
                ordered_vol_dirs.append(all_vol_dirs.pop(vol_name))
        ordered_vol_dirs.extend(sorted(all_vol_dirs.values()))
    
    vol_order = {v.name: i for i, v in enumerate(ordered_vol_dirs)}
    
    for vol_dir in ordered_vol_dirs:
        if not vol_dir.is_dir():
            continue
        
        vol_meta_path = vol_dir / "volume_meta.json"
        if not vol_meta_path.exists():
            continue
        
        try:
            vol_meta = json_lib.loads(vol_meta_path.read_text(encoding="utf-8-sig"))
            chapters_data = vol_meta.get("chapters", [])
            
            for chap_record in chapters_data:
                chapter_id_counter += 1
                chap_number = chap_record.get("number", chapter_id_counter)
                chap_title = chap_record.get("title", f"第{chap_number}章")
                chap_status = chap_record.get("status", "pending")
                
                # 读取 JSON 结果文件获取字数统计
                txt_file = vol_dir / f"chap_{chap_number:04d}.txt"
                json_file = vol_dir / f"chap_{chap_number:04d}.json"
                
                char_count = 0
                content_preview = ""
                if txt_file.exists():
                    content = txt_file.read_text(encoding="utf-8")
                    char_count = len(content)
                    # 章节原文前 50 字（tooltip 预览用）
                    content_preview = content[:50]
                
                result_length = 0
                if json_file.exists():
                    try:
                        json_data = json_lib.loads(json_file.read_text(encoding="utf-8-sig"))
                        # 获取结构化数据中的字段名（兼容新旧 schema）
                        structured_data = json_data.get("structured_data", json_data)
                        chapter_summary = structured_data.get("chapter_summary", {})
                        result_content = chapter_summary.get("result_content", chapter_summary.get("content", ""))
                        result_length = len(result_content)
                    except Exception:
                        pass
                
                chapters.append({
                    "id": f"chap_{chapter_id_counter:04d}",
                    "number": chap_number,
                    "title": chap_title,
                    "content_preview": content_preview,
                    "char_count": char_count,
                    "status": chap_status,
                    "result_length": result_length,
                    "volume_dir": vol_dir.name,
                    "volume_index": vol_order.get(vol_dir.name, 0)
                })
        
        except Exception:
            continue
    
    # 保持卷顺序，卷内按章节号排序
    chapters.sort(key=lambda c: (c.get("volume_index", 999), c["number"]))
    
    return chapters


@app.post("/api/volumes/{volume_path}/summarize")
async def summarize_volume(volume_path: str, request: Request):
    """生成当前卷的完整总结
    
    功能：
    1. 收集本卷所有章节的 brief_summary
    2. 可选：提取 character_status_snapshot 和 plot_threads
    3. 生成卷级摘要并写入 volume_meta.json
    
    Args:
        volume_path: 卷路径（如 workspace/projects/项目/书名/vol_001_卷名）
    """
    import json as json_lib
    from datetime import datetime, timezone
    
    config = get_config()
    vol_dir = Path(config.workspace_dir) / volume_path
    
    if not vol_dir.exists() or not (vol_dir / "volume_meta.json").exists():
        raise HTTPException(status_code=404, detail=f"卷目录不存在：{volume_path}")
    
    # 检查所有章节是否都已处理
    vol_meta_path = vol_dir / "volume_meta.json"
    with open(vol_meta_path, "r", encoding="utf-8-sig") as f:
        vol_meta = json_lib.load(f)
    
    chapters = vol_meta.get("chapters", [])
    all_processed = all(c.get("status") == "processed" for c in chapters)
    
    if not all_processed:
        failed_count = sum(1 for c in chapters if c.get("status") == "failed")
        pending_count = sum(1 for c in chapters if c.get("status") == "pending")
        raise HTTPException(
            status_code=400,
            detail=f"未完成的章节：{pending_count}待处理，{failed_count}失败，请先完成所有章节分析"
        )
    
    # 已有卷总结的情况
    if vol_meta.get("volumes_summary"):
        # TODO: 询问用户是否重新生成
        raise HTTPException(
            status_code=409,
            detail=f"本卷已有总结（共{len(chapters)}章），如需重新生成请删除现有 summary 后重试"
        )
    
    # 收集所有章节的 brief_summary
    chapter_summaries = []
    characters_map = {}
    plot_threads_map = {}
    
    for chap in sorted(chapters, key=lambda c: c["number"]):
        chap_num = chap["number"]
        json_file = vol_dir / f"chap_{chap_num:04d}.json"
        
        if not json_file.exists():
            continue
        
        try:
            with open(json_file, "r", encoding="utf-8-sig") as f:
                chap_data = json_lib.load(f)
            
            structured_data = chap_data.get("structured_data", chap_data)
            chap_summary = structured_data.get("chapter_summary", {})
            
            # 章节总结
            brief_summary = chap_summary.get("brief_summary", "")
            if brief_summary:
                chapter_summaries.append(brief_summary)
            
            # Layer 2: 提取角色信息（仅记录首次出现或状态变化）
            chars = structured_data.get("characters", [])
            for char in chars:
                name = char.get("name", "")
                if name and name not in characters_map:
                    characters_map[name] = {
                        "name": name,
                        "level": char.get("cultivation_level", "未知"),
                        "location": char.get("current_location", "未知"),
                        "first_appearance": f"第{chap_num}章",
                        "role": char.get("role", "配角")
                    }
            
            # Layer 2: 提取剧情伏笔
            secrets = structured_data.get("plot_secrets", {})
            if isinstance(secrets, dict):
                for thread_key, thread_data in secrets.items():
                    if isinstance(thread_data, dict):
                        thread_name = thread_data.get("thread_name", thread_key)
                        status = thread_data.get("status", "")
                        if thread_name and status and thread_name not in plot_threads_map:
                            plot_threads_map[thread_name] = {
                                "thread_name": thread_name,
                                "status": status,
                                "appeared_at": f"第{chap_num}章",
                                "description": thread_data.get("description", "")
                            }
        
        except Exception as e:
            logger.error(f"读取章节 {chap_num} 时出错：{e}")
    
    # 使用 AI 生成完整卷总结（拼接所有章节总结）
    full_summary_text = "\n\n".join(chapter_summaries)
    
    # 构建 prompt 供 AI 生成卷总结
    summary_prompt = f"""
请基于以下本章简要总结，为该卷生成一个完整的概要文档。
要求：
1. 概述本卷的主要情节发展（不超过 500 字）
2. 列出主要角色的状态变化
3. 标记重要的伏笔或悬念

=== 本卷各章简要总结 ===
{full_summary_text}

=== 输出格式 (JSON) ===
{{
  "volumes_summary": {{
    "summary": "完整卷总结文本",
    "character_status_snapshot": [
      {{"name": "角色 A", "level": "LV3", "location": "某地", "role": "主角"}}
    ],
    "plot_threads": [
      {{"thread_name": "伏笔名称", "status": "进行中", "description": "..."}}
    ]
  }}
}}
"""
    
    # 调用 AI API 生成总结
    try:
        from ai_novel_analyzer.utils.ai_api_client import AIApiFactory
        
        # 从 ConfigManager 统一读取 API 参数，避免硬编码
        cfg = get_config()
        
        client = AIApiFactory.create_openai_compatible(
            api_key=os.getenv('AI_MODEL_API_KEY', ''),
            base_url=os.getenv('AI_MODEL_BASE_URL', 'https://api.siliconflow.cn/v1'),
            model=os.getenv('AI_MODEL_NAME', 'Qwen/Qwen2.5-72B-Instruct')
        )
        
        response = client.generate(
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=cfg.temperature,
            max_tokens=cfg.aux_max_tokens,
            stream=False
        )
        
        # 解析 AI 返回的 JSON
        import re
        raw_output = response.choices[0].message.content
        cleaned = re.sub(r'```json\s*|\s*```', '', raw_output).strip()
        
        summary_result = json_lib.loads(cleaned)
        volumes_summary = summary_result.get("volumes_summary", {})
        
        # 更新卷元数据
        vol_meta["volumes_summary"] = volumes_summary
        vol_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        with open(vol_meta_path, "w", encoding="utf-8") as f:
            json_lib.dump(vol_meta, f, ensure_ascii=False, indent=2)
        
        return {
            "success": True,
            "message": f"成功生成本卷总结（共{len(chapters)}章）",
            "summary": volumes_summary
        }
    
    except Exception as e:
        logger.error(f"生成卷总结失败：{e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成总结失败：{str(e)}")


@app.post("/api/books/{project}/{book}/volumes/reorder")
async def reorder_volumes(project: str, book: str, request: Request):
    """卷排序：按前端传入的 dir 顺序重写 book_meta.json 的 volumes 数组

    仅修改元数据顺序，不移动文件系统目录。
    """
    import json as json_lib
    from datetime import datetime, timezone

    body = await request.json()
    ordered_dirs = body.get("dirs") or []
    if not isinstance(ordered_dirs, list) or not ordered_dirs:
        raise HTTPException(status_code=400, detail="dirs 必须为非空数组")

    config = get_config()
    book_dir = config.projects_dir / sanitize_dirname(project) / sanitize_dirname(book)
    book_meta_path = book_dir / "book_meta.json"
    if not book_meta_path.exists():
        raise HTTPException(status_code=404, detail=f"书籍不存在：{book}")

    book_meta = json_lib.loads(book_meta_path.read_text(encoding="utf-8-sig"))
    volumes = book_meta.get("volumes", [])

    # 兼容旧数据（字符串数组）
    if volumes and isinstance(volumes[0], str):
        volumes = [{"name": "", "dir": d, "chapter_count": 0} for d in volumes]

    dir_map = {v["dir"]: v for v in volumes if isinstance(v, dict)}
    unknown = [d for d in ordered_dirs if d not in dir_map]
    if unknown:
        raise HTTPException(status_code=400, detail=f"未知卷目录：{', '.join(unknown)}")
    if len(ordered_dirs) != len(dir_map):
        raise HTTPException(status_code=400, detail="dirs 数量与现有卷数量不一致")

    book_meta["volumes"] = [dir_map[d] for d in ordered_dirs]
    book_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(book_meta_path, "w", encoding="utf-8") as f:
        json_lib.dump(book_meta, f, ensure_ascii=False, indent=2)

    return {"success": True, "message": "卷顺序已更新", "volumes": book_meta["volumes"]}


@app.post("/api/books/{project}/{book}/volumes/rename")
async def rename_volume(project: str, book: str, request: Request):
    """编辑卷名：同步更新 book_meta.json、volume_meta.json 并重命名卷目录

    修改卷名时，同步更新：
    1. 卷目录名称（vol_XXX_旧名 → vol_XXX_新名）
    2. book_meta.json 中对应卷的 dir 和 name 字段
    3. volume_meta.json 中的 volume_title 字段
    """
    import json as json_lib
    import shutil
    from datetime import datetime, timezone

    body = await request.json()
    vol_dir = (body.get("dir") or "").strip()
    new_name = (body.get("name") or "").strip()

    if not vol_dir:
        raise HTTPException(status_code=400, detail="缺少必填参数：dir")
    if not new_name:
        raise HTTPException(status_code=400, detail="卷名不能为空")
    if len(new_name) > 30:
        raise HTTPException(status_code=400, detail="卷名长度不能超过 30 字符")

    config = get_config()
    book_dir = config.projects_dir / sanitize_dirname(project) / sanitize_dirname(book)
    old_vol_path = book_dir / vol_dir
    new_vol_dir = new_name[:30]  # 限制目录名长度
    new_vol_path = book_dir / f"vol_{vol_dir.split("_")[1]}_{new_vol_dir}"  # 保留卷号，更新新卷名
    
    if not old_vol_path.exists():
        raise HTTPException(status_code=404, detail=f"卷不存在：{vol_dir}")

    now = datetime.now(timezone.utc).isoformat()

    # 1. 重命名卷目录
    if old_vol_path != new_vol_path:
        if new_vol_path.exists():
            raise HTTPException(status_code=400, detail=f"卷目录已存在：{new_vol_path.name}")
        shutil.move(str(old_vol_path), str(new_vol_path))

    # 2. 更新 volume_meta.json
    vol_meta_path = new_vol_path / "volume_meta.json"
    vol_meta = json_lib.loads(vol_meta_path.read_text(encoding="utf-8-sig"))
    vol_meta["volume_title"] = new_name
    vol_meta["updated_at"] = now
    with open(vol_meta_path, "w", encoding="utf-8") as f:
        json_lib.dump(vol_meta, f, ensure_ascii=False, indent=2)

    # 3. 同步更新 book_meta.json 中对应卷的 dir 和 name
    book_meta_path = book_dir / "book_meta.json"
    if book_meta_path.exists():
        book_meta = json_lib.loads(book_meta_path.read_text(encoding="utf-8-sig"))
        volumes = book_meta.get("volumes", [])
        if volumes and isinstance(volumes[0], str):
            # 兼容旧数据：升级为对象数组
            volumes = [{"name": "", "dir": d, "chapter_count": 0} for d in volumes]
        for v in volumes:
            if isinstance(v, dict) and v.get("dir") == vol_dir:
                v["dir"] = new_vol_path.name
                v["name"] = new_name
                break
        book_meta["volumes"] = volumes
        book_meta["updated_at"] = now
        with open(book_meta_path, "w", encoding="utf-8") as f:
            json_lib.dump(book_meta, f, ensure_ascii=False, indent=2)

    return {"success": True, "message": f"卷名已更新：{new_name}"}


@app.post("/api/books/{project}/{book}/edit")
async def edit_book(project: str, book: str, request: Request):
    """编辑书籍元数据（作者等）"""
    import json as json_lib
    from datetime import datetime, timezone

    body = await request.json()
    new_author = (body.get("author") or "").strip()

    config = get_config()
    book_dir = config.projects_dir / sanitize_dirname(project) / sanitize_dirname(book)
    book_meta_path = book_dir / "book_meta.json"
    if not book_meta_path.exists():
        raise HTTPException(status_code=404, detail=f"书籍不存在：{book}")

    if new_author and len(new_author) > 30:
        raise HTTPException(status_code=400, detail="作者长度不能超过 30 字符")

    book_meta = json_lib.loads(book_meta_path.read_text(encoding="utf-8-sig"))
    if new_author:
        book_meta["author"] = new_author
    book_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(book_meta_path, "w", encoding="utf-8") as f:
        json_lib.dump(book_meta, f, ensure_ascii=False, indent=2)

    return {"success": True, "message": "书籍信息已更新"}


@app.post("/api/books")
async def create_book(request: Request):
    """新建空书籍（仅登记元数据，不上传文件）

    流程：创建书籍目录 → 登记元数据（split_status=pending，volumes 为空）
    后续在拆书界面上传 TXT 并预览分卷、填写卷名后确认分割
    """
    import json as json_lib
    from datetime import datetime, timezone
    from scripts.split_book import upsert_project_meta

    body = await request.json()
    project = (body.get("project") or "").strip()
    book_name = (body.get("book") or "").strip()
    author = (body.get("author") or "").strip()

    # 必填校验
    missing = [name for name, val in [("project", project), ("book", book_name), ("author", author)] if not val]
    if missing:
        raise HTTPException(status_code=400, detail=f"缺少必填参数：{', '.join(missing)}")

    # 长度限制
    if len(project) > 30 or len(book_name) > 30 or len(author) > 30:
        raise HTTPException(status_code=400, detail="项目名/书名/作者长度不能超过 30 字符")

    config = get_config()
    project_dir = config.projects_dir / sanitize_dirname(project)
    book_dir = project_dir / sanitize_dirname(book_name)

    # 重复书籍校验
    if (book_dir / "book_meta.json").exists():
        raise HTTPException(status_code=409, detail=f"书籍已存在：{book_name}")

    # 登记书籍元数据（空书：无卷、待上传）
    project_dir.mkdir(parents=True, exist_ok=True)
    book_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    book_meta = {
        "book_name": book_name,
        "author": author,
        "source_files": [],
        "volumes": [],
        "split_status": "pending",
        "created_at": now,
        "updated_at": now,
    }
    with open(book_dir / "book_meta.json", "w", encoding="utf-8") as f:
        json_lib.dump(book_meta, f, ensure_ascii=False, indent=2)

    # 登记项目元数据
    upsert_project_meta(project_dir, project, book_name, "xianxia.yaml")

    return {
        "success": True,
        "message": f"书籍已创建：{book_name}（请上传 TXT 并确认分割）",
        "split_status": "pending",
    }


@app.post("/api/books/upload-preview")
async def upload_split_preview(
    project: str = Form(...),
    book: str = Form(...),
    file: UploadFile = File(...),
):
    """上传 TXT 并预览分卷结果（不写盘）

    返回章节预览 + 分卷预览（供用户填写卷名）
    """
    import json as json_lib
    from scripts.split_book import group_chapters_by_volume
    from ai_novel_analyzer.utils.chapter_splitter import ChapterSplitter

    project = (project or "").strip()
    book_name = (book or "").strip()

    if not project or not book_name:
        raise HTTPException(status_code=400, detail="缺少必填参数：project / book")

    if not file.filename.endswith('.txt'):
        raise HTTPException(status_code=400, detail="仅支持 TXT 格式文件")

    config = get_config()
    book_dir = config.projects_dir / sanitize_dirname(project) / sanitize_dirname(book_name)
    if not (book_dir / "book_meta.json").exists():
        raise HTTPException(status_code=404, detail=f"书籍不存在：{book_name}，请先新建书籍")

    # 保存临时文件（确认分割后清理）
    file_id = str(uuid.uuid4())
    source_file = TEMP_DIR / f"{file_id}_{file.filename}"

    try:
        with open(source_file, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # 分割预览（只解析，不写盘）
        result = await asyncio.to_thread(process_novel_upload, str(source_file))

        # 自动递增卷号：查询已有最大卷号（与确认分割逻辑保持一致）
        existing_volumes = []
        if book_dir.exists():
            import re
            for d in book_dir.iterdir():
                if d.is_dir() and d.name.startswith('vol_'):
                    match = re.match(r'vol_(\d+)_', d.name)
                    if match:
                        existing_volumes.append(int(match.group(1)))
        start_volume_number = (max(existing_volumes) if existing_volumes else 0) + 1

        # 分卷预览：按卷分组，返回每卷章节数和识别到的卷名建议
        def build_volume_preview():
            input_path = Path(str(source_file))
            _cfg = get_config()
            _tp = _cfg.get('chapter_splitting.title_patterns')
            splitter = ChapterSplitter(fallback_segment_chars=3000, default_volume=start_volume_number, title_patterns=_tp)
            chapters = splitter.split_file(input_path, None)
            groups = group_chapters_by_volume(chapters)
            volumes_preview = []
            for volume_number, volume_chapters in groups.items():
                recognized_title = next(
                    (ch.volume_title for _, ch in volume_chapters if ch.volume_title), None
                )
                volumes_preview.append({
                    "volume_number": volume_number,
                    "suggested_title": recognized_title or "",
                    "chapter_count": len(volume_chapters),
                    "char_count": sum(ch.char_count for _, ch in volume_chapters),
                })
            return volumes_preview

        volumes_preview = await asyncio.to_thread(build_volume_preview)

        # 将预览信息暂存到 book_meta（确认分割时使用）
        book_meta_path = book_dir / "book_meta.json"
        book_meta = json_lib.loads(book_meta_path.read_text(encoding="utf-8-sig"))
        book_meta["pending_file_id"] = file_id
        book_meta["pending_preview"] = {
            "encoding": result.encoding,
            "total_chars": result.total_chars,
            "total_chapters": result.total_chapters,
            "chapters_preview": result.chapters_preview,
            "volumes_preview": volumes_preview,
        }
        with open(book_meta_path, "w", encoding="utf-8") as f:
            json_lib.dump(book_meta, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "message": f"预览完成：共 {result.total_chapters} 章 → {len(volumes_preview)} 卷",
            "file_id": file_id,
            "total_chapters": result.total_chapters,
            "preview": book_meta["pending_preview"],
        }

    except HTTPException:
        raise
    except Exception as e:
        if source_file.exists():
            source_file.unlink()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/books/{project}/{book}/resplit-preview")
async def resplit_preview(project: str, book: str, request: Request):
    """重新分割预览：使用 book_meta 存档的 source_files 重新分割（无需重新上传）

    与 upload_split_preview 行为一致，但源文件来自书籍存档目录 book_dir/source/，
    确认分割（POST /api/split/{file_id}）时通过 pending_source_path 定位源文件。
    """
    import json as json_lib
    from scripts.split_book import group_chapters_by_volume
    from ai_novel_analyzer.utils.chapter_splitter import ChapterSplitter

    project = (project or "").strip()
    book_name = (book or "").strip()

    body = await request.json()
    source_rel = (body.get("source_file") or "").strip()

    config = get_config()
    book_dir = config.projects_dir / sanitize_dirname(project) / sanitize_dirname(book_name)
    book_meta_path = book_dir / "book_meta.json"
    if not book_meta_path.exists():
        raise HTTPException(status_code=404, detail=f"书籍不存在：{book_name}")

    book_meta = json_lib.loads(book_meta_path.read_text(encoding="utf-8-sig"))
    source_files = book_meta.get("source_files") or []
    if not source_files:
        raise HTTPException(status_code=400, detail="book_meta 未记录 source_files，请先通过「上传 TXT」分割一次")

    # 确定源文件：显式指定 > 第一个存档文件
    if source_rel:
        if source_rel not in source_files:
            raise HTTPException(status_code=400, detail=f"源文件不在 book_meta 记录中：{source_rel}")
    else:
        source_rel = source_files[0]

    source_file = book_dir / source_rel
    if not source_file.exists():
        raise HTTPException(status_code=404, detail=f"存档源文件不存在：{source_rel}")

    try:
        # 分割预览（只解析，不写盘）
        result = await asyncio.to_thread(process_novel_upload, str(source_file))

        # 自动递增卷号：查询已有最大卷号（与确认分割逻辑保持一致）
        existing_volumes = []
        if book_dir.exists():
            import re
            for d in book_dir.iterdir():
                if d.is_dir() and d.name.startswith('vol_'):
                    match = re.match(r'vol_(\d+)_', d.name)
                    if match:
                        existing_volumes.append(int(match.group(1)))
        start_volume_number = (max(existing_volumes) if existing_volumes else 0) + 1

        # 分卷预览：按卷分组，返回每卷章节数和识别到的卷名建议
        def build_volume_preview():
            _cfg = get_config()
            _tp = _cfg.get('chapter_splitting.title_patterns')
            splitter = ChapterSplitter(fallback_segment_chars=3000, default_volume=start_volume_number, title_patterns=_tp)
            chapters = splitter.split_file(source_file, None)
            groups = group_chapters_by_volume(chapters)
            volumes_preview = []
            for volume_number, volume_chapters in groups.items():
                recognized_title = next(
                    (ch.volume_title for _, ch in volume_chapters if ch.volume_title), None
                )
                volumes_preview.append({
                    "volume_number": volume_number,
                    "suggested_title": recognized_title or "",
                    "chapter_count": len(volume_chapters),
                    "char_count": sum(ch.char_count for _, ch in volume_chapters),
                })
            return volumes_preview

        volumes_preview = await asyncio.to_thread(build_volume_preview)

        # 将预览信息暂存到 book_meta（确认分割时使用；源文件来自存档，不复制临时文件）
        file_id = str(uuid.uuid4())
        book_meta["pending_file_id"] = file_id
        book_meta["pending_source_path"] = source_rel
        book_meta["pending_preview"] = {
            "encoding": result.encoding,
            "total_chars": result.total_chars,
            "total_chapters": result.total_chapters,
            "chapters_preview": result.chapters_preview,
            "volumes_preview": volumes_preview,
        }
        with open(book_meta_path, "w", encoding="utf-8") as f:
            json_lib.dump(book_meta, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "message": f"重新分割预览完成：共 {result.total_chapters} 章 → {len(volumes_preview)} 卷",
            "file_id": file_id,
            "total_chapters": result.total_chapters,
            "preview": book_meta["pending_preview"],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=18997, reload=False)
