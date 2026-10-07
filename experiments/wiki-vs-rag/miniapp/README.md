# 原味饼干 · 全英雄 AI 教练微信小程序

这是 `wiki-vs-rag` 的微信原生小程序前端，品牌名为“原味饼干”，面向全英雄对局复盘。对话是主界面；历史会话、回答依据、难度选择和能力画像都采用渐进式披露。客户端不包含模型密钥、模型地址、Token 单价或检索底层参数。

## 信息架构

```text
主对话
├─ 顶部：历史 / 原味饼干与服务状态 / 新建对话
├─ 对话流：空态建议 / 用户问题 / 教练回答 / 生成与恢复状态
├─ 回答附属：依据 → 知识来源；难度反馈
└─ 底部：本次难度 / 多行输入 / 发送

渐进层
├─ 左侧抽屉：本地历史会话
├─ 底部抽屉：当前英雄、三维能力画像与手动等级
└─ 底部抽屉：本次回答深度
```

视觉命题是“像聊天一样自然地复盘任意英雄，同时保留专业教练的判断力与可信依据”。交互命题是“用户始终在一次可继续追问的对话里；英雄上下文可随时调整，复杂信息只在主动请求时展开”。

## 本地运行

1. 安装并打开微信开发者工具。
2. 选择“导入项目”，目录指向本文件所在的 `miniapp/`。
3. 未配置 AppID 时可使用测试号；仓库中的 `project.config.json` 使用 `touristappid`。
4. 默认 `config/env.js` 的 `useMock` 为 `true`，可直接体验完整问答、长回答、证据、反馈和画像流程。

可在 `config/env.js` 修改 `mockScenario` 检查关键状态：

- `ready`
- `offline`
- `service_unavailable`
- `index_missing`
- `index_stale`
- `request_error`
- `no_evidence`
- `feedback_error`
- `profile_error`

## 接入真实 API

CloudBase 云托管是默认生产通路。在 `config/env.js` 中把 `useMock` 改为 `false`，保持 `transport: 'cloudbase'`，并填写 CloudBase 环境 ID 与云托管服务名。应用启动时会初始化云开发，请求通过 `wx.cloud.callContainer` 发送。

需要接入普通 HTTPS 后端时，可把 `transport` 改为 `request` 并填写 `baseURL`。该模式要求在微信公众平台配置 request 合法域名；真机不能访问 `127.0.0.1`。

请求层保留以下接口语义：

- `GET /api/status`
- `GET /api/profile?user_id=...&hero=...`
- `POST /api/profile`
- `POST /api/coach/run`
- `POST /api/feedback`

`POST /api/index` 不由普通小程序用户触发；索引创建和模型供应商配置属于服务端运维职责。

### 服务端模型配置

生产小程序不能安全保存模型地址和 API Key，因此前端只发送业务字段：

```json
{
  "question": "...",
  "user_id": "local-user",
  "hero": "李白",
  "declared_level": null
}
```

CloudBase 版本的后端会从服务端环境变量读取 embedding 与 generation 配置，并忽略客户端传入的供应商配置。完整步骤见上级目录的 `CLOUDBASE_DEPLOY.md`。

## 本地数据

历史会话通过 `wx.setStorageSync` 保存在当前设备，数据访问集中在 `services/conversations.js`，后续可替换为后端会话接口。删除会话前会二次确认。

## 状态与可访问性

已实现空对话、长回答、分阶段生成、请求失败、断网、服务不可用、索引缺失/过期、证据不足、反馈提交中/成功/失败、空历史、画像失败、输入接近上限、键盘变化、安全区域和减少动态效果。高频触控目标按约 44px 设计；状态不只依赖颜色，并使用可感知的状态文案。
