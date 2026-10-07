# 水平感知规划式 AI 教练

这是一个读取本地游戏知识库、固定开启 Wiki 关系扩展的单 Agent 应用。项目已不再运行五路检索对比，当前只优化一条主链：

```text
识别问题与相关能力
→ 读取用户在该能力上的等级
→ 规划检索任务
→ 语义检索
→ Wiki 一跳关系扩展
→ 证据合并与审计
→ 按 L1 / L2 / L3 难度生成回答
→ 收集太简单 / 正合适 / 太难
→ 校准能力等级
```

## 当前能力

- 三个独立水平维度：操作与连招、发育与资源、局面决策；
- 三个教学等级：L1 入门执行型、L2 条件判断型、L3 权衡复盘型；
- 用户可以手动校准等级；
- 连续两次相同的“太简单”或“太难”才调整一级；
- “正合适”只提高当前判断的置信度；
- 水平只影响解释深度和文章结构，不改变检索事实与证据标准；
- 每次运行保存路由、计划、工具调用、Wiki 增量、审计、耗时和 Token；
- 页面分别显示生成 API、Embedding 调用、Token 和估算费用。

用户画像保存在 `.rag-data/level_profiles.json`，原始难度反馈追加到 `.rag-data/level_feedback.jsonl`。两者都是本地、可检查的数据文件。

## 启动

首次启动前，打开同目录的 `.env`，只填写：

```text
EMBEDDING_API_KEY=你的百炼API Key
GENERATION_API_KEY=你的DeepSeek API Key
```

模型地址和名称已经预填。`.env` 被 Git 忽略，不会上传到 GitHub；`.env.example` 是可安全提交的模板。保存配置后运行：

```powershell
cd experiments/wiki-vs-rag
.\start.ps1
```

启动脚本会确保本地 Ollama 与 DeepSeek 不被无效的环境代理拦截。

打开 `http://127.0.0.1:8765/`。

首次使用或知识库变化后，在页面底部点击“重建知识索引”。索引没有变化时会直接复用 `.rag-data/manifest.json` 与 `.rag-data/vectors.npy`。

## API

- `GET /api/status`：知识库和索引状态；
- `GET /api/profile?user_id=local-user&hero=镜`：查看水平画像；
- `POST /api/index`：创建或重建向量索引；
- `POST /api/coach/run`：运行固定开启 Wiki 的水平感知 Agent；
- `POST /api/profile`：手动设置某个能力等级；
- `POST /api/feedback`：提交太简单、正合适或太难。

## 测试

```powershell
python -m unittest discover -s tests -v
```

当前版本刻意不包含阅读品味、自动策略发布和模型微调。第一阶段只验证一件事：相同证据下，回答难度能否稳定匹配用户在相关能力上的水平。

## CloudBase 持久化

本地默认使用 `.rag-data`。正式部署可切换到普通 CloudBase PostgreSQL；向量保存在数组列中，由 Python 在内存中检索，不要求安装 `pgvector`：

```env
STORAGE_BACKEND=cloudbase_pg
CLOUDBASE_DATABASE_URL=你的服务端PostgreSQL连接串
EMBEDDING_DIMENSIONS=1024
REQUIRE_CLOUDBASE_IDENTITY=true
```

首次部署前在 CloudBase PG SQL 编辑器执行 `migrations/001_cloudbase_pg.sql`。云端索引按内容哈希增量更新，未变化片段直接复用旧向量；新版本构建失败时旧版本继续提供检索。
