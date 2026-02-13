/**
 * 启动 Qwen3 Tiny LLM 服务
 * 这个脚本会检查 Python 环境并启动 LLM 服务
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

// 配置
const QWEN_DIR = path.join(__dirname, '..', 'aiserver', 'qwentinyllm');
const VENV_PYTHON = path.join(QWEN_DIR, 'venv', 'Scripts', 'python.exe');
const SERVICE_PY = path.join(QWEN_DIR, 'service.py');

console.log('╔══════════════════════════════════════════════════════════════╗');
console.log('║           启动 Qwen3 Tiny LLM 服务                          ║');
console.log('╚══════════════════════════════════════════════════════════════╝');
console.log('');

// 检查目录
if (!fs.existsSync(QWEN_DIR)) {
    console.error('❌ 错误: 找不到 qwentinyllm 目录');
    console.error(`   路径: ${QWEN_DIR}`);
    process.exit(1);
}

// 检查虚拟环境
if (!fs.existsSync(VENV_PYTHON)) {
    console.error('❌ 错误: 找不到 Python 虚拟环境');
    console.error(`   期望路径: ${VENV_PYTHON}`);
    console.error('');
    console.error('请先创建虚拟环境:');
    console.error(`   cd ${QWEN_DIR}`);
    console.error('   python -m venv venv');
    console.error('   venv\\Scripts\\activate');
    console.error('   pip install -r requirements.txt');
    process.exit(1);
}

// 检查 service.py
if (!fs.existsSync(SERVICE_PY)) {
    console.error('❌ 错误: 找不到 service.py');
    console.error(`   路径: ${SERVICE_PY}`);
    process.exit(1);
}

console.log('✓ 找到 qwentinyllm 目录');
console.log('✓ 找到 Python 虚拟环境');
console.log('✓ 找到 service.py');
console.log('');
console.log('⏳ 启动 Qwen3 Tiny LLM 服务...');
console.log('   服务地址: http://localhost:6015');
console.log('   测试页面: http://localhost:6015');
console.log('');

// 启动 Python 服务
const pythonProcess = spawn(VENV_PYTHON, [SERVICE_PY], {
    cwd: QWEN_DIR,
    stdio: 'inherit',
    shell: true
});

// 处理进程退出
pythonProcess.on('exit', (code, signal) => {
    if (code !== null) {
        console.log(`\n⚠️  Qwen3 LLM 服务已停止 (退出码: ${code})`);
    } else if (signal !== null) {
        console.log(`\n⚠️  Qwen3 LLM 服务被终止 (信号: ${signal})`);
    }
});

// 处理错误
pythonProcess.on('error', (err) => {
    console.error('\n❌ 启动 Qwen3 LLM 服务失败:');
    console.error(err);
    process.exit(1);
});

// 处理主进程退出
process.on('SIGINT', () => {
    console.log('\n\n👋 关闭 Qwen3 LLM 服务...');
    pythonProcess.kill('SIGINT');
    setTimeout(() => {
        process.exit(0);
    }, 1000);
});

process.on('SIGTERM', () => {
    console.log('\n\n👋 关闭 Qwen3 LLM 服务...');
    pythonProcess.kill('SIGTERM');
    setTimeout(() => {
        process.exit(0);
    }, 1000);
});
