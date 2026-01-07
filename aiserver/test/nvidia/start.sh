
# 获取项目根目录路径
ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

# 检查 .env 文件
if [ ! -f "$ENV_FILE" ]; then
    echo "错误: 未找到 .env 文件"
    echo "期望路径: $ENV_FILE"
    echo ""
    echo "请在项目根目录创建 .env 文件，并添加以下内容："
    echo ""
    echo "NVIDIA_API_KEY=nvapi-your-api-key-here"
    echo ""
    echo "将 'nvapi-your-api-key-here' 替换为你的实际 API Key"
    exit 1
fi

# 检查是否配置了 API Key
if ! grep -q "NVIDIA_API_KEY=nvapi-" "$ENV_FILE"; then
    echo "警告: .env 文件中的 NVIDIA_API_KEY 可能未正确配置"
    echo "请确保格式为: NVIDIA_API_KEY=nvapi-xxxxxx"
fi

echo "使用配置文件: $ENV_FILE"

echo "正在启动 NVIDIA NIM Chat 服务器..."
echo "访问地址: http://localhost:5000"
echo ""

python app.py
