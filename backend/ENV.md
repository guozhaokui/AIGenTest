# 环境变量（示例）

建议在项目根目录创建 `.env`（不入库），其变量示例如下（仅示意）：

```
PORT=3000
MONGO_URL=mongodb://localhost:27017/ai_image_eval
UPLOAD_DIR=imagedb
GOOGLE_API_KEY=你的Google生成式AI密钥
GOOGLE_API_BASE=https://generativelanguage.googleapis.com
```

说明
- 后端启动时会优先加载仓库根目录的 `.env`，其次加载 `backend/.env`（不会覆盖已存在变量）。
- 图片生成接口 `/api/generate` 依赖 `GOOGLE_API_KEY`（也支持 `GENAI_API_KEY` 或 `API_KEY`）。如需通过中转服务，可将 `GOOGLE_API_BASE` 指向你的中转地址（保持与官方 API 路径兼容）。
- 如果需要走代理，请设置：
```
HTTPS_PROXY=http://your-proxy:port
# 或
HTTP_PROXY=http://your-proxy:port
```
后端会自动使用代理进行网络请求。

