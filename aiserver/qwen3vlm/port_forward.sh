#!/bin/bash
#
# VLM 服务端口转发脚本
# 将远程 zhangqu-8x3090 的 6050 端口转发到本地
#

SSH_HOST="zhangqu-8x3090"
LOCAL_PORT=6050
REMOTE_PORT=6050

# 检查是否已有转发进程
check_existing() {
    pgrep -f "ssh.*-L.*${LOCAL_PORT}:localhost:${REMOTE_PORT}.*${SSH_HOST}" > /dev/null
}

start() {
    if check_existing; then
        echo "✅ 端口转发已在运行"
        return 0
    fi
    
    echo "🔄 启动端口转发: localhost:${LOCAL_PORT} -> ${SSH_HOST}:${REMOTE_PORT}"
    ssh -L ${LOCAL_PORT}:localhost:${REMOTE_PORT} -N -f -o ServerAliveInterval=60 -o ServerAliveCountMax=3 ${SSH_HOST}
    
    if [ $? -eq 0 ]; then
        echo "✅ 端口转发已启动"
    else
        echo "❌ 启动失败"
        return 1
    fi
}

stop() {
    echo "🛑 停止端口转发..."
    pkill -f "ssh.*-L.*${LOCAL_PORT}:localhost:${REMOTE_PORT}.*${SSH_HOST}"
    echo "✅ 已停止"
}

status() {
    if check_existing; then
        echo "✅ 端口转发正在运行"
        echo "   本地端口: ${LOCAL_PORT}"
        echo "   远程主机: ${SSH_HOST}:${REMOTE_PORT}"
        ps aux | grep "ssh.*-L.*${LOCAL_PORT}" | grep -v grep
    else
        echo "❌ 端口转发未运行"
    fi
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 1
        start
        ;;
    status)
        status
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status}"
        echo ""
        echo "示例:"
        echo "  $0 start   # 启动端口转发"
        echo "  $0 stop    # 停止端口转发"
        echo "  $0 status  # 查看状态"
        exit 1
        ;;
esac

