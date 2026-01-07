#!/bin/bash
# 视频分析成本对比脚本

VIDEO_PATH="/mnt/c/Users/DELL/Desktop/参考图片/videoplayback.mp4"

echo "======================================================================"
echo "Gemini 视频分析价格对比 (基于同一视频)"
echo "======================================================================"
echo ""

echo "1️⃣  Gemini 2.0 Flash-Lite - FPS=1 (低成本方案)"
echo "----------------------------------------------------------------------"
python aiserver/test/gemini_video_understanding.py --mode file --video_path "$VIDEO_PATH" --fps 1 --model gemini-2.0-flash-lite --dry-run 2>/dev/null | grep -A 15 "成本估算"
echo ""

echo "2️⃣  Gemini 2.0 Flash-Lite - FPS=8 (游戏视频推荐)"
echo "----------------------------------------------------------------------"
python aiserver/test/gemini_video_understanding.py --mode file --video_path "$VIDEO_PATH" --fps 8 --model gemini-2.0-flash-lite --dry-run 2>/dev/null | grep -A 15 "成本估算"
echo ""

echo "3️⃣  Gemini 2.5 Pro - FPS=1 (高质量方案)"
echo "----------------------------------------------------------------------"
python aiserver/test/gemini_video_understanding.py --mode file --video_path "$VIDEO_PATH" --fps 1 --model gemini-2.5-pro --dry-run 2>/dev/null | grep -A 15 "成本估算"
echo ""

echo "4️⃣  Gemini 3 Pro Preview - FPS=8 (最强方案)"
echo "----------------------------------------------------------------------"
python aiserver/test/gemini_video_understanding.py --mode file --video_path "$VIDEO_PATH" --fps 8 --model gemini-3-pro-preview --dry-run 2>/dev/null | grep -A 15 "成本估算"
echo ""

echo "======================================================================"
echo "💡 使用建议："
echo "  - 预览/测试: Flash-Lite + FPS=1"
echo "  - 游戏视频: Flash-Lite + FPS=5-8"
echo "  - 高精度分析: Gemini 3 Pro + FPS=8-10"
echo "======================================================================"
