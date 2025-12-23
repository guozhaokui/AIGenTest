#!/bin/bash
#
# 停止多实例 VLM 服务
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🛑 停止 VLM 服务..."

# 停止负载均衡器
if [ -f logs/load_balancer.pid ]; then
    PID=$(cat logs/load_balancer.pid)
    if kill -0 $PID 2>/dev/null; then
        kill $PID
        echo "  ✅ 负载均衡器已停止 (PID: $PID)"
    fi
    rm -f logs/load_balancer.pid
fi

# 停止所有实例
for pidfile in logs/instance_*.pid; do
    if [ -f "$pidfile" ]; then
        PID=$(cat "$pidfile")
        if kill -0 $PID 2>/dev/null; then
            kill $PID
            echo "  ✅ 实例已停止 (PID: $PID)"
        fi
        rm -f "$pidfile"
    fi
done

# 确保所有 vlm_service 进程都停止
pkill -f "vlm_service.py" 2>/dev/null
pkill -f "load_balancer.py" 2>/dev/null

echo "✅ 所有服务已停止"

