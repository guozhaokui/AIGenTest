# Gemini 视频理解 - 功能说明

## ✨ 新增功能

### 1. 自动价格计算
- ✅ 自动提取视频时长（支持 ffprobe、opencv、文件大小估算）
- ✅ 根据 FPS 和模型计算预估 Token 消耗
- ✅ 显示详细成本（美元和人民币）
- ✅ 支持多种模型价格对比

### 2. Dry-run 模式
- ✅ 使用 `--dry-run` 参数只估算成本，不调用 API
- ✅ 适合测试和成本规划
- ✅ 不消耗 API 配额

### 3. 多模型支持
- gemini-2.0-flash-exp（实验版，可能免费）
- gemini-2.0-flash-lite（性价比最高）
- gemini-2.5-flash-lite
- gemini-2.5-pro（高质量）
- gemini-3-pro-preview（最新最强）

## 📊 使用示例

### 示例 1: 只估算成本，不调用 API
```bash
python aiserver/test/gemini_video_understanding.py \
  --mode file \
  --video_path "/path/to/video.mp4" \
  --fps 8 \
  --model gemini-3-pro-preview \
  --dry-run
```

输出：
```
============================================================
📊 成本估算
============================================================
视频时长: 30.0 秒
采样率: 8 FPS
模型: Gemini 3 Pro Preview (gemini-3-pro-preview)

📈 Token 消耗:
  输入 tokens: 61,920
  预计输出 tokens: 500
  总计: 62,420 tokens

💰 预估成本:
  输入成本: $0.123840 (¥0.8917)
  输出成本: $0.006000 (¥0.0432)
  总成本: $0.129840 (¥0.9349)
============================================================

🔍 Dry-run 模式: 只进行成本估算，不实际调用 API
```

### 示例 2: 实际分析视频（带成本估算）
```bash
python aiserver/test/gemini_video_understanding.py \
  --mode file \
  --video_path "/path/to/game.mp4" \
  --fps 5 \
  --model gemini-2.0-flash-lite \
  --prompt "详细分析游戏玩法和操作"
```

会先显示成本估算，然后执行分析。

### 示例 3: 对比不同模型价格
```bash
# Flash-Lite (最便宜)
python aiserver/test/gemini_video_understanding.py \
  --mode file --video_path video.mp4 --fps 8 \
  --model gemini-2.0-flash-lite --dry-run

# Gemini 3 Pro (最强)
python aiserver/test/gemini_video_understanding.py \
  --mode file --video_path video.mp4 --fps 8 \
  --model gemini-3-pro-preview --dry-run
```

## 💰 价格对比（基于 30 秒视频）

| 模型 | FPS | 输入 Tokens | 总成本(USD) | 总成本(CNY) | 适用场景 |
|------|-----|------------|------------|------------|---------|
| Flash-Lite | 1 | 7,740 | $0.00075 | ¥0.005 | 预览/测试 |
| Flash-Lite | 8 | 61,920 | $0.006 | ¥0.043 | **游戏视频推荐** |
| Gemini 3 Pro | 1 | 7,740 | $0.022 | ¥0.16 | 高质量分析 |
| Gemini 3 Pro | 8 | 61,920 | $0.130 | ¥0.94 | 最强方案 |

## 🎯 使用建议

### 游戏视频分析
```bash
# 推荐配置：Flash-Lite + FPS=5-8
python aiserver/test/gemini_video_understanding.py \
  --mode file \
  --video_path game_video.mp4 \
  --fps 8 \
  --model gemini-2.0-flash-lite \
  --prompt "分析游戏操作、规则和玩法"
```

**为什么选择 FPS=8？**
- FPS=1：只能看到静态画面，丢失动作细节
- FPS=5-8：捕捉快速操作和连续动作
- FPS=10：最高质量，但成本增加 25%

**为什么选择 Flash-Lite？**
- 性价比极高（8 FPS 只要 ¥0.04）
- 速度快
- 对于大多数游戏视频已经足够

### 教学/讲解视频
```bash
# 中等配置：Flash-Lite + FPS=3
python aiserver/test/gemini_video_understanding.py \
  --mode file \
  --video_path tutorial.mp4 \
  --fps 3 \
  --model gemini-2.0-flash-lite
```

### 高精度分析
```bash
# 高配置：Gemini 3 Pro + FPS=8-10
python aiserver/test/gemini_video_understanding.py \
  --mode file \
  --video_path critical_video.mp4 \
  --fps 10 \
  --model gemini-3-pro-preview
```

## 🔧 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--mode` | 运行模式 (file/youtube/embedded/demo) | demo |
| `--video_path` | 视频文件路径 | - |
| `--fps` | 采样率 (1-10) | 1 |
| `--model` | 模型选择 | gemini-2.0-flash-exp |
| `--dry-run` | 只估算不调用 API | false |
| `--output-tokens` | 预计输出 tokens | 500 |
| `--prompt` | 分析提示词 | "请详细描述这个视频的内容" |

## 📝 完整使用示例

### 1. 测试成本
```bash
# 先用 dry-run 看看需要多少钱
python aiserver/test/gemini_video_understanding.py \
  --mode file \
  --video_path my_video.mp4 \
  --fps 8 \
  --model gemini-2.0-flash-lite \
  --dry-run
```

### 2. 确认后执行
```bash
# 确认成本可接受后，去掉 --dry-run 执行
python aiserver/test/gemini_video_understanding.py \
  --mode file \
  --video_path my_video.mp4 \
  --fps 8 \
  --model gemini-2.0-flash-lite \
  --prompt "分析这个视频中的关键信息"
```

## 🚀 性能优化建议

1. **批量处理用 Flash-Lite**
   - 成本低，速度快
   - 适合处理大量视频

2. **重要视频用 Gemini 3 Pro**
   - 质量最高
   - 理解能力最强

3. **先低 FPS 预览，再高 FPS 精析**
   - 第一遍用 FPS=1 快速浏览
   - 关键部分用 FPS=8-10 深入分析

4. **合理设置输出 tokens**
   - 简单摘要：200-300 tokens
   - 详细分析：500-1000 tokens
   - 影响成本计算准确性

## ⚠️ 注意事项

1. **视频时长估算**
   - 优先使用 ffmpeg (最准确)
   - 备选 opencv-python
   - 最后用文件大小估算（误差较大）

2. **Token 消耗公式**
   - 输入 Tokens = 视频时长(秒) × 258 × FPS
   - 每秒视频 ≈ 258 tokens (1 FPS 基准)

3. **上下文限制**
   - Gemini 2.5/3 Pro: 超过 200K tokens 价格翻倍
   - 1 小时视频 @ 1 FPS ≈ 93K tokens
   - 1 小时视频 @ 10 FPS ≈ 930K tokens（超限！）

## 🎮 实际测试结果

**测试视频**: 游戏演示 (30秒, 793KB)

| 配置 | Token 消耗 | 成本 | 效果评价 |
|------|-----------|------|----------|
| FPS=1, Flash-Lite | 7,740 | ¥0.005 | 只能看出游戏类型，动作模糊 |
| FPS=8, Flash-Lite | 61,920 | ¥0.043 | **推荐！** 捕捉所有关键操作 |
| FPS=8, Gemini 3 | 61,920 | ¥0.94 | 最详细，理解最深入 |

**结论**: 对于游戏视频，Flash-Lite + FPS=8 是最佳性价比选择！

## 📚 更多资源

- [Gemini API 文档](https://ai.google.dev/gemini-api/docs/video-understanding)
- [价格详情](https://ai.google.dev/gemini-api/docs/pricing)
- 本地测试脚本：`aiserver/test/gemini_video_understanding.py`
