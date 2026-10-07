# 原味饼干：GitHub + CloudBase 部署

这套项目分成两部分：

- `experiments/wiki-vs-rag/miniapp` 是微信小程序前端，最终由微信开发者工具上传并发布。
- `experiments/wiki-vs-rag` 是 Python API，使用仓库根目录的 `Dockerfile` 部署到 CloudBase 云托管。

## 1. 创建 CloudBase 环境

1. 在微信开发者工具里打开 `云开发`，创建或关联一个环境。
2. 记录环境 ID，例如 `cloud1-xxxx`。
3. 进入云托管，创建服务，服务名建议使用 `plain-cookie-coach`。

## 2. 从 GitHub 部署 API

在云托管服务中选择 Git 仓库部署，并填写：

| 配置项 | 值 |
| --- | --- |
| 仓库 | `chenbinggang123/plain-cookie-coac` |
| 分支 | `main` |
| 构建目录 | `.` |
| Dockerfile | `Dockerfile` |
| 容器端口 | `8080` |
| 健康检查路径 | `/health` |

不要把模型密钥提交到 GitHub。请在云托管服务的环境变量页面配置：

| 环境变量 | 说明 |
| --- | --- |
| `PROVIDER_CONFIG_MODE` | 固定为 `environment`，禁止客户端覆盖模型配置 |
| `KNOWLEDGE_REPO` | 默认 `chenbinggang123/Cookie-s_Knowledge_Base` |
| `KNOWLEDGE_REF` | 知识仓库分支，默认 `main` |
| `KNOWLEDGE_GITHUB_TOKEN` | 必填；旧知识仓库当前为私有仓库，请使用只读、最小权限 Token |
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

容器启动时只会从知识仓库下载 `game_scope.json` 白名单命中的 Markdown 文件。图片、视频、简历和其他私人笔记不会进入运行目录。不要把 `KNOWLEDGE_GITHUB_TOKEN` 写入代码仓库或小程序。

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

## 4. 上线前必须处理的两个边界

1. 当前索引和服务端段位画像写在容器的 `.rag-data` 目录。云托管实例重建或横向扩容后，这些文件不会形成可靠的共享持久化。当前方案适合单实例 MVP 验证；正式运营前应把索引放到对象存储/向量库，把服务端画像放到 CloudBase 数据库。
2. 界面已支持“全英雄”，但当前 `game_scope.json` 的知识来源仍以已有的镜、马超和通用王者荣耀笔记为主。部署不等于全英雄知识已经齐全；需要逐步扩充各英雄资料并重建索引。

## 5. 发布检查

- `/health` 和 `/api/status` 正常。
- 索引已构建，`/api/status` 显示可用。
- 模型密钥只在 CloudBase 环境变量中。
- 服务日志显示已从知识仓库同步 Markdown，且没有打印 GitHub Token。
- 小程序 `useMock` 已改为 `false`，环境 ID、服务名和 AppID 正确。
- 真机验证提问、历史会话、错误重试和弱网提示。
- 正式发布前关闭不需要的公网访问，并轮换测试阶段使用过的管理令牌。
