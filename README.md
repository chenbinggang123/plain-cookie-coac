# 原味饼干 AI 教练

微信小程序前端与 CloudBase 云托管后端。程序代码存放在本仓库，游戏知识从独立的 GitHub 知识仓库按白名单同步，模型密钥和私有仓库令牌只保存在 CloudBase 环境变量中。

- 微信小程序：`experiments/wiki-vs-rag/miniapp`
- Python 后端：`experiments/wiki-vs-rag`
- CloudBase 镜像：`Dockerfile`
- 部署说明：`experiments/wiki-vs-rag/CLOUDBASE_DEPLOY.md`

## 本地验证

```bash
cd experiments/wiki-vs-rag
python -m unittest discover -s tests -v
cd miniapp
node tests/smoke.js
```
