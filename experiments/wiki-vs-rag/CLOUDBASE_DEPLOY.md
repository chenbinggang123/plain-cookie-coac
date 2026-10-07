# 原味饼干：GitHub + CloudBase 部署

这套项目分成两部分：

- `experiments/wiki-vs-rag/miniapp` 是微信小程序前端，最终由微信开发者工具上传并发布。
- `experiments/wiki-vs-rag` 是 Python API，使用仓库根目录的 `Dockerfile.cloudbase` 部署到 CloudBase 云托管。

## 1. 创建 CloudBase 环境

1. 在微信开发者工具里打开 `云开发`，创建或关联一个环境。
2. 记录环境 ID，例如 `cloud1-xxxx`。
3. 进入云托管，创建服务，服务名建议使用 `plain-cookie-coach`。

### 创建持久化数据库

正式环境请选择 CloudBase **PG 模式**，打开 SQL 编辑器并执行：

```text
experiments/wiki-vs-rag/migrations/001_cloudbase_pg.sql
```

不要把上面的文件路径当作 SQL 执行。请打开该文件、复制全部 SQL 到编辑器再执行。迁移不依赖 `pgvector`，会创建知识片段、索引版本、用户画像和反馈记录四组表。Embedding 维度由 `EMBEDDING_DIMENSIONS` 校验，当前配置为 1024。

## 2. 从 GitHub 部署 API

在云托管服务中选择 Git 仓库部署，并填写：

| 配置项 | 值 |
| --- | --- |
| 仓库 | 当前 GitHub 仓库 |
| 分支 | 上传代码所在分支 |
| 构建目录 | `.` |
| Dockerfile | `Dockerfile.cloudbase` |
| 容器端口 | `8080` |
| 健康检查路径 | `/health` |

不要把模型密钥提交到 GitHub。请在云托管服务的环境变量页面配置：

| 环境变量 | 说明 |
| --- | --- |
| `PROVIDER_CONFIG_MODE` | 固定为 `environment`，禁止客户端覆盖模型配置 |
| `STORAGE_BACKEND` | 正式环境固定为 `cloudbase_pg` |
| `CLOUDBASE_DATABASE_URL` | CloudBase PG 提供的服务端 PostgreSQL 连接串 |
| `EMBEDDING_DIMENSIONS` | 当前固定为 `1024` |
| `REQUIRE_CLOUDBASE_IDENTITY` | 正式环境固定为 `true`，只接受网关验证的微信身份 |
| `EMBEDDING_KIND` | `openai` 或 `ollama` |
| `EMBEDDING_BASE_URL` | 嵌入模型兼容接口根地址，不含 `/embeddings` |
| `EMBEDDING_MODEL` | 嵌入模型名称 |
| `EMBEDDING_API_KEY` | 嵌入服务密钥 |
| `GENERATION_KIND` | `openai` 或 `ollama` |
| `GENERATION_BASE_URL` | 生成模型兼容接口根地址，不含 `/chat/completions` |
| `GENERATION_MODEL` | 生成模型名称 |
| `GENERATION_API_KEY` | 生成服务密钥 |
| `INDEX_ADMIN_TOKEN` | 随机长字符串，用于保护重建索引接口 |

`PORT` 和 `HOST` 已有容器默认值；CloudBase 注入 `PORT` 时服务会自动读取。

部署完成后先访问 `/health`。返回 `{"ok":true}` 说明容器已启动。随后调用一次索引接口：

```bash
curl -X POST "https://你的临时公网域名/api/index" \
  -H "Content-Type: application/json" \
  -H "X-Index-Admin-Token: 你的索引管理令牌" \
  -d "{}"
```

索引完成后可以关闭公网访问；小程序通过 `wx.cloud.callContainer` 调用云托管，不依赖配置 request 合法域名。

## 3. 连接微信小程序

编辑 `miniapp/config/env.js`：

```js
module.exports = {
  useMock: false,
  mockScenario: 'ready',
  transport: 'cloudbase',
  cloudbaseEnv: '你的 CloudBase 环境 ID',
  serviceName: 'plain-cookie-coach',
  baseURL: 'https://coach-api.example.com',
  timeout: 45000,
  retryCount: 1,
};
```

再把 `miniapp/project.config.json` 中的 `touristappid` 替换成正式小程序 AppID，用微信开发者工具导入 `miniapp` 目录，完成真机调试、上传、提交审核和发布。

## 4. 数据如何保存

设置 `STORAGE_BACKEND=cloudbase_pg` 后：

- 向量以普通 PostgreSQL 数组保存，容器首次检索时加载到内存计算余弦相似度；
- 容器重启只需重新加载已有向量，不会重新调用 Embedding，也不需要重建索引；
- 重建索引会复用内容哈希未变化的向量，只调用新增或修改片段的 Embedding；
- 新索引完整校验后才切换为活动版本，失败时继续使用旧版本；
- 玩家画像和反馈保存在数据库，不依赖容器磁盘；
- CloudBase 网关传入的 `X-WX-OPENID` 会覆盖客户端提交的 `user_id`。

这种模式适合当前的个人知识库和早期使用规模。知识片段达到数万条或并发明显升高后，可以把数组列迁移为 `pgvector`，上层 API 和用户画像表不需要重做。

本地开发保持 `STORAGE_BACKEND=local`，继续使用 `.rag-data`，无需安装或连接数据库。

界面已支持“全英雄”，但当前 `game_scope.json` 的知识来源仍以已有的镜、马超和通用王者荣耀笔记为主。部署不等于全英雄知识已经齐全；需要逐步扩充各英雄资料并重建索引。

## 5. 发布检查

- `/health` 和 `/api/status` 正常。
- 索引已构建，`/api/status` 显示可用。
- `/api/status` 中 `storage_backend` 为 `cloudbase_pg`。
- 重新部署一个版本后索引和画像仍然存在。
- 模型密钥只在 CloudBase 环境变量中。
- 小程序 `useMock` 已改为 `false`，环境 ID、服务名和 AppID 正确。
- 真机验证提问、历史会话、错误重试和弱网提示。
- 正式发布前关闭不需要的公网访问，并轮换测试阶段使用过的管理令牌。
