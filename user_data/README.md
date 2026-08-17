# user_data/ - 用户数据目录说明

## 目录结构

```
user_data/
├── novel_raw/                    # 原始小说文本输入目录
│   └── [放置待处理的章节 txt/md 文件]
│       ├── vol_1_chap_01.txt
│       ├── vol_1_chap_02.txt
│       └── ...
│
├── novel_data/                   # AI 分析结果输出目录
│   ├── raw/                      # 原始分割的小说章节（自动创建）
│   ├── processed/                # AI 分析后的 JSON 文件（自动创建）
│   │   ├── vol_1/
│   │   │   ├── chap_01.json
│   │   │   └── chap_02.json
│   │   └── vol_2/
│   │       └── chap_01.json
│   └── summaries/                # 章节摘要（上下文使用，自动创建）
│
└── database/                     # 数据库文件目录
    ├── sqlite/                   # SQLite 结构化数据库（Phase 2 功能）
    │   └── novel_analyzer.db
    └── chromadb/                 # ChromaDB 向量存储
        └── novel_analysis/
```

## 使用说明

### 自定义路径

编辑 `config/production.yaml` 文件：

```yaml
io:
  # 方式 1：相对路径（相对于项目根目录）
  input_dir: "user_data/novel_raw"
  output_dir: "user_data/novel_data"
  
  # 方式 2：绝对路径（Windows）
  # input_dir: "D:/Projects/Novels/TangDynasty/raw"
  # output_dir: "D:/Projects/Novels/TangDynasty/data"
  
  # 方式 3：绝对路径（Linux/Mac）
  # input_dir: "/home/user/projects/novels/tangdynasty/raw"
  # output_dir: "/home/user/projects/novels/tangdynasty/data"
```

### 快速开始

1. 将待处理的小说章节放入 `user_data/novel_raw/` 目录
2. 运行批量处理脚本
3. 查看 `user_data/novel_data/processed/` 中的分析结果

## 注意事项

- ✅ 此目录无需提交到 Git（已在 `.gitignore` 中配置）
- ✅ 目录会在首次运行时自动创建
- ✅ 可以清空并重新处理，不会影响其他数据
- ⚠️ 删除此目录会导致所有分析结果丢失
