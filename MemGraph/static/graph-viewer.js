// MemGraph 知识图谱可视化
const API_BASE = 'http://localhost:8800';

// Canvas 和上下文
const canvas = document.getElementById('graphCanvas');
const ctx = canvas.getContext('2d');

// 图谱数据
let nodes = new Map(); // doc_id -> node
let edges = [];        // [{from, to, similarity}]
let selectedNode = null;
let selectedEdge = null;  // 选中的边
let hoveredEdge = null;  // 悬停的边

// 视图控制
let offsetX = 0;
let offsetY = 0;
let scale = 1;
let isDraggingCanvas = false;
let isDraggingNode = false;
let draggedNode = null;
let dragStartX = 0;
let dragStartY = 0;

// 物理引擎参数
const REPULSION = 20000;        // 增大排斥力，让节点更分散
const ATTRACTION = 0.005;       // 减小吸引力，让连接更松散
const DAMPING = 0.85;           // 增加阻尼，减少抖动
const MIN_DISTANCE = 200;       // 增加最小距离，避免重叠
const CENTER_FORCE = 0.0005;    // 减小中心吸引力

// 颜色配置
const LAYER_COLORS = {
    0: '#667eea',  // 主节点 - 紫色
    1: '#48bb78',  // 一级关联 - 绿色
    2: '#ed8936',  // 二级关联 - 橙色
};

// 节点类
class Node {
    constructor(data) {
        this.id = data.doc_id;
        this.label = this.truncate(data.problem || data.path || `Node ${data.doc_id}`, 30);
        this.layer = data.layer || 0;
        this.data = data;

        // 物理属性
        this.x = Math.random() * canvas.width;
        this.y = Math.random() * canvas.height;
        this.vx = 0;
        this.vy = 0;
        this.radius = 35;        // 增大节点半径
        this.fixed = false;      // 是否固定（用户拖动后）
    }

    truncate(str, maxLen) {
        if (str.length <= maxLen) return str;
        return str.substring(0, maxLen) + '...';
    }

    getColor() {
        if (selectedNode && selectedNode.id === this.id) {
            return '#ffd700'; // 金色表示选中
        }
        return LAYER_COLORS[this.layer] || '#999';
    }

    draw() {
        // 绘制连线（到其他节点）
        ctx.strokeStyle = '#e0e0e0';
        ctx.lineWidth = 1 / scale;

        // 绘制节点圆圈
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
        ctx.fillStyle = this.getColor();
        ctx.fill();

        // 选中节点有特殊边框
        if (selectedNode && selectedNode.id === this.id) {
            ctx.strokeStyle = '#ff6b6b';
            ctx.lineWidth = 4 / scale;
        } else {
            ctx.strokeStyle = 'rgba(255,255,255,0.8)';
            ctx.lineWidth = 3 / scale;
        }
        ctx.stroke();

        // 绘制文字（深色文字，白色描边）
        const fontSize = 13 / scale;
        ctx.font = `bold ${fontSize}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        // 白色描边（增强可读性）
        ctx.strokeStyle = 'rgba(255,255,255,0.9)';
        ctx.lineWidth = 3 / scale;
        ctx.strokeText(this.label, this.x, this.y);

        // 深色文字
        ctx.fillStyle = '#1a202c';
        ctx.fillText(this.label, this.x, this.y);

        // 绘制 Layer 标签（带背景）
        const layerText = `L${this.layer}`;
        const layerY = this.y + this.radius + 15 / scale;

        ctx.font = `${10 / scale}px sans-serif`;
        ctx.fillStyle = 'rgba(255,255,255,0.95)';
        const textWidth = ctx.measureText(layerText).width;
        ctx.fillRect(
            this.x - textWidth / 2 - 4 / scale,
            layerY - 8 / scale,
            textWidth + 8 / scale,
            16 / scale
        );

        ctx.fillStyle = '#666';
        ctx.fillText(layerText, this.x, layerY);
    }

    contains(x, y) {
        const dx = x - this.x;
        const dy = y - this.y;
        return Math.sqrt(dx * dx + dy * dy) <= this.radius;
    }

    applyForce(fx, fy) {
        this.vx += fx;
        this.vy += fy;
    }

    update() {
        // 如果节点被固定（用户拖动过），不更新位置
        if (this.fixed) {
            this.vx = 0;
            this.vy = 0;
            return;
        }

        // 更新位置
        this.x += this.vx;
        this.y += this.vy;

        // 应用阻尼
        this.vx *= DAMPING;
        this.vy *= DAMPING;

        // 速度很小时停止（减少抖动）
        if (Math.abs(this.vx) < 0.01) this.vx = 0;
        if (Math.abs(this.vy) < 0.01) this.vy = 0;

        // 边界约束
        const padding = 100;
        this.x = Math.max(padding, Math.min(canvas.width - padding, this.x));
        this.y = Math.max(padding, Math.min(canvas.height - padding, this.y));
    }
}

// 初始化 Canvas
function resizeCanvas() {
    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;
}

window.addEventListener('resize', resizeCanvas);
resizeCanvas();

// 力导向布局算法
function applyForces() {
    const nodeArray = Array.from(nodes.values());

    // 1. 排斥力（节点之间互相排斥）- 更强的排斥力
    for (let i = 0; i < nodeArray.length; i++) {
        for (let j = i + 1; j < nodeArray.length; j++) {
            const n1 = nodeArray[i];
            const n2 = nodeArray[j];

            const dx = n2.x - n1.x;
            const dy = n2.y - n1.y;
            const distance = Math.sqrt(dx * dx + dy * dy) + 0.1; // 避免除零

            // 总是应用排斥力，距离越近力越大
            const force = REPULSION / (distance * distance);
            const fx = (dx / distance) * force;
            const fy = (dy / distance) * force;

            if (!n1.fixed) n1.applyForce(-fx, -fy);
            if (!n2.fixed) n2.applyForce(fx, fy);
        }
    }

    // 2. 吸引力（连接的节点互相吸引）- 只对连接的节点
    edges.forEach(edge => {
        const n1 = nodes.get(edge.from);
        const n2 = nodes.get(edge.to);

        if (n1 && n2) {
            const dx = n2.x - n1.x;
            const dy = n2.y - n1.y;
            const distance = Math.sqrt(dx * dx + dy * dy) + 0.1;

            // 理想距离：300像素
            const idealDistance = 300;
            const force = ATTRACTION * (distance - idealDistance);
            const fx = (dx / distance) * force;
            const fy = (dy / distance) * force;

            if (!n1.fixed) n1.applyForce(fx, fy);
            if (!n2.fixed) n2.applyForce(-fx, -fy);
        }
    });

    // 3. 中心吸引力（温和）
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    nodeArray.forEach(node => {
        if (node.fixed) return;

        const dx = centerX - node.x;
        const dy = centerY - node.y;
        const distance = Math.sqrt(dx * dx + dy * dy);

        if (distance > 0) {
            const force = CENTER_FORCE * distance;
            node.applyForce(dx / distance * force, dy / distance * force);
        }
    });

    // 更新节点位置
    nodeArray.forEach(node => node.update());
}

// 渲染循环
function render() {
    // 清空画布
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 应用变换
    ctx.save();
    ctx.translate(offsetX, offsetY);
    ctx.scale(scale, scale);

    // 绘制边
    edges.forEach(edge => {
        const n1 = nodes.get(edge.from);
        const n2 = nodes.get(edge.to);

        if (n1 && n2) {
            // 检查是否是选中或悬停的边
            const isSelected = selectedEdge &&
                              selectedEdge.from === edge.from &&
                              selectedEdge.to === edge.to;

            const isHovered = hoveredEdge &&
                              hoveredEdge.from === edge.from &&
                              hoveredEdge.to === edge.to;

            if (isSelected) {
                // 选中边：绿色加粗
                ctx.strokeStyle = '#48bb78';
                ctx.lineWidth = 5 / scale;
            } else if (isHovered) {
                // 悬停边：蓝色加粗
                ctx.strokeStyle = '#667eea';
                ctx.lineWidth = 4 / scale;
            } else {
                // 普通边
                ctx.strokeStyle = '#d0d0d0';
                ctx.lineWidth = 2 / scale;
            }

            ctx.beginPath();
            ctx.moveTo(n1.x, n1.y);
            ctx.lineTo(n2.x, n2.y);
            ctx.stroke();

            // 如果悬停或选中，显示提示
            if ((isHovered || isSelected) && edge.similarity !== undefined) {
                const midX = (n1.x + n2.x) / 2;
                const midY = (n1.y + n2.y) / 2;

                const text = isSelected ? '已选中 - 查看详情' : '点击查看详情';
                ctx.font = `bold ${11 / scale}px sans-serif`;
                const textWidth = ctx.measureText(text).width;

                ctx.fillStyle = 'rgba(255,255,255,0.95)';
                ctx.fillRect(
                    midX - textWidth / 2 - 6 / scale,
                    midY - 10 / scale,
                    textWidth + 12 / scale,
                    20 / scale
                );

                // 绘制文字
                ctx.fillStyle = isSelected ? '#48bb78' : '#667eea';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(text, midX, midY);
            }
        }
    });

    // 绘制节点
    nodes.forEach(node => node.draw());

    ctx.restore();

    // 应用物理引擎
    applyForces();

    requestAnimationFrame(render);
}

// 启动渲染
render();

// 坐标转换
function screenToCanvas(screenX, screenY) {
    const rect = canvas.getBoundingClientRect();
    const canvasX = (screenX - rect.left - offsetX) / scale;
    const canvasY = (screenY - rect.top - offsetY) / scale;
    return { x: canvasX, y: canvasY };
}

// 计算点到线段的距离
function distanceToLineSegment(px, py, x1, y1, x2, y2) {
    const dx = x2 - x1;
    const dy = y2 - y1;
    const lengthSquared = dx * dx + dy * dy;

    if (lengthSquared === 0) {
        // 线段退化为点
        return Math.sqrt((px - x1) ** 2 + (py - y1) ** 2);
    }

    // 计算投影参数 t
    let t = ((px - x1) * dx + (py - y1) * dy) / lengthSquared;
    t = Math.max(0, Math.min(1, t));  // 限制在 [0, 1] 范围内

    // 计算投影点
    const projX = x1 + t * dx;
    const projY = y1 + t * dy;

    // 返回距离
    return Math.sqrt((px - projX) ** 2 + (py - projY) ** 2);
}

// 鼠标事件
canvas.addEventListener('mousedown', (e) => {
    const { x, y } = screenToCanvas(e.clientX, e.clientY);

    // 检查是否点击了节点
    let clickedNode = null;
    nodes.forEach(node => {
        if (node.contains(x, y)) {
            clickedNode = node;
        }
    });

    if (clickedNode) {
        // 按住 Shift 键拖动节点，否则选中节点
        if (e.shiftKey) {
            isDraggingNode = true;
            draggedNode = clickedNode;
            dragStartX = x;
            dragStartY = y;
            canvas.style.cursor = 'move';
        } else {
            selectNode(clickedNode);
        }
    } else {
        // 检查是否点击了边
        let clickedEdge = null;
        edges.forEach(edge => {
            const n1 = nodes.get(edge.from);
            const n2 = nodes.get(edge.to);
            if (n1 && n2) {
                const dist = distanceToLineSegment(x, y, n1.x, n1.y, n2.x, n2.y);
                if (dist < 10 / scale) {
                    clickedEdge = edge;
                }
            }
        });

        if (clickedEdge) {
            // 点击了边，显示边的详细信息
            selectEdge(clickedEdge);
        } else {
            // 开始拖拽画布
            isDraggingCanvas = true;
            dragStartX = e.clientX - offsetX;
            dragStartY = e.clientY - offsetY;
            canvas.style.cursor = 'grabbing';
        }
    }
});

canvas.addEventListener('mousemove', (e) => {
    const { x, y } = screenToCanvas(e.clientX, e.clientY);

    if (isDraggingNode && draggedNode) {
        // 拖动节点
        const dx = x - dragStartX;
        const dy = y - dragStartY;

        draggedNode.x += dx;
        draggedNode.y += dy;
        draggedNode.fixed = true;  // 标记为固定

        dragStartX = x;
        dragStartY = y;
    } else if (isDraggingCanvas) {
        // 拖动画布
        offsetX = e.clientX - dragStartX;
        offsetY = e.clientY - dragStartY;
    } else {
        // 检查鼠标悬停节点
        let hoveringNode = false;
        nodes.forEach(node => {
            if (node.contains(x, y)) {
                hoveringNode = true;
            }
        });

        // 检查鼠标悬停边
        let foundEdge = null;
        if (!hoveringNode) {
            edges.forEach(edge => {
                const n1 = nodes.get(edge.from);
                const n2 = nodes.get(edge.to);
                if (n1 && n2) {
                    const dist = distanceToLineSegment(x, y, n1.x, n1.y, n2.x, n2.y);
                    if (dist < 10 / scale) {  // 10px tolerance
                        foundEdge = edge;
                    }
                }
            });
        }
        hoveredEdge = foundEdge;

        // 显示合适的光标
        if (hoveringNode && e.shiftKey) {
            canvas.style.cursor = 'move';
        } else if (hoveringNode) {
            canvas.style.cursor = 'pointer';
        } else if (foundEdge) {
            canvas.style.cursor = 'help';  // 悬停边时显示帮助光标
        } else {
            canvas.style.cursor = 'default';
        }
    }
});

canvas.addEventListener('mouseup', () => {
    isDraggingCanvas = false;
    isDraggingNode = false;
    draggedNode = null;
    canvas.style.cursor = 'default';
});

// Shift 键状态改变时更新光标
canvas.addEventListener('mousemove', (e) => {
    if (!isDraggingCanvas && !isDraggingNode) {
        const { x, y } = screenToCanvas(e.clientX, e.clientY);
        let hovering = false;

        nodes.forEach(node => {
            if (node.contains(x, y)) {
                hovering = true;
            }
        });

        if (hovering && e.shiftKey) {
            canvas.style.cursor = 'move';
        } else if (hovering) {
            canvas.style.cursor = 'pointer';
        } else {
            canvas.style.cursor = 'default';
        }
    }
});

canvas.addEventListener('wheel', (e) => {
    e.preventDefault();

    const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
    const newScale = Math.max(0.1, Math.min(3, scale * zoomFactor));

    // 以鼠标位置为中心缩放
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    offsetX = mouseX - (mouseX - offsetX) * (newScale / scale);
    offsetY = mouseY - (mouseY - offsetY) * (newScale / scale);
    scale = newScale;
});

// 控制按钮
document.getElementById('resetZoomBtn').addEventListener('click', () => {
    scale = 1;
    offsetX = 0;
    offsetY = 0;

    // 重新居中节点
    if (nodes.size > 0) {
        centerNodes();
    }
});

document.getElementById('zoomInBtn').addEventListener('click', () => {
    scale = Math.min(3, scale * 1.2);
});

document.getElementById('zoomOutBtn').addEventListener('click', () => {
    scale = Math.max(0.1, scale / 1.2);
});

// 居中节点
function centerNodes() {
    const nodeArray = Array.from(nodes.values());
    if (nodeArray.length === 0) return;

    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;

    // 计算节点中心
    let sumX = 0, sumY = 0;
    nodeArray.forEach(n => {
        sumX += n.x;
        sumY += n.y;
    });

    const avgX = sumX / nodeArray.length;
    const avgY = sumY / nodeArray.length;

    // 移动所有节点到中心
    nodeArray.forEach(n => {
        n.x += (centerX - avgX);
        n.y += (centerY - avgY);
    });
}

// 显示状态消息
function showStatus(message, type = 'loading') {
    const statusEl = document.getElementById('statusMessage');
    statusEl.textContent = message;
    statusEl.className = `status-message show ${type}`;

    if (type !== 'loading') {
        setTimeout(() => {
            statusEl.classList.remove('show');
        }, 3000);
    }
}

// 搜索节点
document.getElementById('searchBtn').addEventListener('click', async () => {
    const query = document.getElementById('searchInput').value.trim();
    if (!query) {
        showStatus('请输入搜索关键词', 'error');
        return;
    }

    const initialNodes = parseInt(document.getElementById('initialNodes').value) || 5;
    const expandLayers = parseInt(document.getElementById('expandLayers').value) || 0;
    const nodesPerLayer = parseInt(document.getElementById('nodesPerLayer').value) || 3;

    document.getElementById('searchBtn').disabled = true;
    showStatus('🔍 搜索中...', 'loading');

    try {
        const response = await fetch(`${API_BASE}/graph/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query,
                initial_k: initialNodes,
                expand_layers: expandLayers,
                nodes_per_layer: nodesPerLayer
            })
        });

        const data = await response.json();

        if (data.success) {
            buildGraph(data.layers);
            showStatus(`✓ 找到 ${countNodes(data.layers)} 个节点`, 'success');
        } else {
            showStatus('搜索失败: ' + data.error, 'error');
        }
    } catch (error) {
        showStatus('网络错误: ' + error.message, 'error');
    } finally {
        document.getElementById('searchBtn').disabled = false;
    }
});

// 回车搜索
document.getElementById('searchInput').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        document.getElementById('searchBtn').click();
    }
});

// 统计节点数量
function countNodes(layers) {
    let count = 0;
    Object.values(layers).forEach(layer => {
        count += layer.length;
    });
    return count;
}

// 构建图谱
function buildGraph(layers) {
    // 清空现有数据
    nodes.clear();
    edges = [];
    selectedNode = null;

    // 添加节点
    Object.keys(layers).forEach(layerKey => {
        const layerNodes = layers[layerKey];
        layerNodes.forEach(nodeData => {
            const node = new Node(nodeData);
            nodes.set(node.id, node);
        });
    });

    // 创建边：layer0 -> layer1, layer1 -> layer2
    const layer0 = layers.layer0 || [];
    const layer1 = layers.layer1 || [];
    const layer2 = layers.layer2 || [];

    // layer0 到 layer1 的连接
    layer0.forEach(n0 => {
        layer1.forEach(n1 => {
            edges.push({
                from: n0.doc_id,
                to: n1.doc_id,
                similarity: n1.similarity_score || n1.vector_score || 0.5
            });
        });
    });

    // layer1 到 layer2 的连接
    layer1.forEach(n1 => {
        layer2.forEach(n2 => {
            edges.push({
                from: n1.doc_id,
                to: n2.doc_id,
                similarity: n2.similarity_score || n2.vector_score || 0.5
            });
        });
    });

    // 初始化节点位置（按层圆形分布）
    layoutNodes(layers);
    centerNodes();
}

// 按层圆形布局（更宽松）
function layoutNodes(layers) {
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;

    Object.keys(layers).forEach((layerKey, layerIndex) => {
        const layerNodes = layers[layerKey];
        const radius = 250 + layerIndex * 350;  // 更大的间距
        const angleStep = (Math.PI * 2) / layerNodes.length;

        layerNodes.forEach((nodeData, i) => {
            const node = nodes.get(nodeData.doc_id);
            if (node) {
                const angle = i * angleStep;
                node.x = centerX + radius * Math.cos(angle);
                node.y = centerY + radius * Math.sin(angle);
                node.vx = 0;
                node.vy = 0;
                node.fixed = false;  // 重置固定状态
            }
        });
    });
}

// 选择节点
function selectNode(node) {
    selectedNode = node;
    selectedEdge = null;
    displayNodeInfo(node);
}

// 选择边
async function selectEdge(edge) {
    selectedEdge = edge;
    selectedNode = null;

    const infoEl = document.getElementById('nodeInfo');
    infoEl.innerHTML = '<div class="info-empty">⏳ 正在加载边的详细信息...</div>';

    console.log('选择边:', edge.from, '->', edge.to);

    try {
        const response = await fetch(`${API_BASE}/graph/edge-details`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                doc_id1: edge.from,
                doc_id2: edge.to,
                top_k: 20  // 最多显示20对匹配
            })
        });

        const data = await response.json();
        console.log('API返回:', data);

        if (data.success) {
            console.log('找到匹配数:', data.matches.length);
            displayEdgeInfo(edge, data.matches);
        } else {
            infoEl.innerHTML = '<div class="info-empty">❌ 加载失败</div>';
        }
    } catch (error) {
        console.error('错误:', error);
        infoEl.innerHTML = `<div class="info-empty">❌ 错误: ${error.message}</div>`;
    }
}

// 显示节点信息
function displayNodeInfo(node) {
    const infoEl = document.getElementById('nodeInfo');
    const data = node.data;

    const tags = (data.tags && data.tags.length > 0)
        ? data.tags.split(',').map(t => `<span class="tag">${t.trim()}</span>`).join('')
        : '<span class="tag">无标签</span>';

    infoEl.innerHTML = `
        <h3>节点信息</h3>

        <div class="info-section">
            <div class="info-section-title">问题/标题</div>
            <div class="info-section-content">${data.problem || data.path || '-'}</div>
        </div>

        <div class="info-section">
            <div class="info-section-title">解决方案（预览）</div>
            <div class="info-section-content">${data.solution || '-'}</div>
        </div>

        <div class="info-section">
            <div class="info-section-title">标签</div>
            <div class="info-tags">${tags}</div>
        </div>

        <div class="info-section">
            <div class="info-section-title">元数据</div>
            <div class="info-section-content">
                <div>文档ID: ${data.doc_id}</div>
                <div>层级: Layer ${data.layer}</div>
                ${data.timestamp ? `<div>时间: ${data.timestamp}</div>` : ''}
                ${data.similarity_score ? `<div>相似度: ${(data.similarity_score * 100).toFixed(1)}%</div>` : ''}
            </div>
        </div>

        <div class="info-section">
            <div class="info-section-title">展开设置</div>
            <div class="info-section-content">
                <label style="display: flex; align-items: center; gap: 10px; font-size: 13px;">
                    <span>最小相似度:</span>
                    <input type="range" id="expandSimilarity_${data.doc_id}"
                           min="0" max="100" value="70" step="5"
                           style="flex: 1;"
                           oninput="document.getElementById('expandSimilarityValue_${data.doc_id}').textContent = this.value + '%'">
                    <span id="expandSimilarityValue_${data.doc_id}" style="min-width: 40px; font-weight: 600; color: #667eea;">70%</span>
                </label>
            </div>
        </div>

        <button class="expand-btn" onclick="expandNodeWithSimilarity(${data.doc_id})">
            🔗 展开关联节点
        </button>

        <button class="expand-btn" onclick="showNodeRelations(${data.doc_id})" style="background: #48bb78; margin-top: 10px;">
            🔍 查看所有关联详情
        </button>

        <button class="expand-btn" onclick="deleteNode(${data.doc_id})" style="background: #f44336; margin-top: 10px;">
            🗑️ 删除此节点
        </button>
    `;
}

// 显示边的详细信息
function displayEdgeInfo(edge, matches) {
    const infoEl = document.getElementById('nodeInfo');

    const node1 = nodes.get(edge.from);
    const node2 = nodes.get(edge.to);

    const node1Label = node1 ? node1.label : `节点 ${edge.from}`;
    const node2Label = node2 ? node2.label : `节点 ${edge.to}`;

    // 粒度映射
    const granularityNames = {
        'ngram': 'N-gram',
        'sentence': '句子',
        'n_sentences': 'N句子',
        'paragraph': '段落',
        'full': '全文'
    };

    // 构建匹配项HTML
    let matchesHtml = '';
    if (matches.length === 0) {
        matchesHtml = '<div style="color: #999; padding: 20px; text-align: center;">未找到匹配的向量对</div>';
    } else {
        matchesHtml = matches.map((match, index) => `
            <div class="match-item" style="margin-bottom: 15px; padding: 12px; background: #f8f9fa; border-radius: 6px; border-left: 3px solid #667eea;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span style="font-weight: 600; color: #667eea;">匹配 #${index + 1}</span>
                    <span style="background: #667eea; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px;">
                        相似度: ${(match.similarity * 100).toFixed(1)}%
                    </span>
                </div>

                <div style="margin-bottom: 10px;">
                    <div style="font-size: 11px; color: #667eea; font-weight: 600; margin-bottom: 4px;">
                        📄 ${node1Label} [${granularityNames[match.vec1_granularity] || match.vec1_granularity}]
                    </div>
                    <div style="font-size: 13px; color: #333; line-height: 1.5; padding: 6px; background: white; border-radius: 4px;">
                        ${match.vec1_content || '(无内容)'}
                    </div>
                </div>

                <div style="text-align: center; margin: 8px 0; color: #999;">⬍</div>

                <div>
                    <div style="font-size: 11px; color: #48bb78; font-weight: 600; margin-bottom: 4px;">
                        📄 ${node2Label} [${granularityNames[match.vec2_granularity] || match.vec2_granularity}]
                    </div>
                    <div style="font-size: 13px; color: #333; line-height: 1.5; padding: 6px; background: white; border-radius: 4px;">
                        ${match.vec2_content || '(无内容)'}
                    </div>
                </div>
            </div>
        `).join('');
    }

    infoEl.innerHTML = `
        <h3>🔗 边关系详情</h3>

        <div class="info-section">
            <div class="info-section-title">连接节点</div>
            <div class="info-section-content">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                    <span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: #667eea;"></span>
                    <strong>${node1Label}</strong> (ID: ${edge.from})
                </div>
                <div style="text-align: center; color: #999; margin: 4px 0;">⬍</div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: #48bb78;"></span>
                    <strong>${node2Label}</strong> (ID: ${edge.to})
                </div>
            </div>
        </div>

        <div class="info-section">
            <div class="info-section-title">向量匹配详情 (共 ${matches.length} 对)</div>
            <div style="max-height: 450px; overflow-y: auto;">
                ${matchesHtml}
            </div>
        </div>

        <button class="expand-btn" onclick="selectedEdge = null; selectedNode = null; document.getElementById('nodeInfo').innerHTML = '<div class=\\'info-empty\\'>点击节点或边查看详细信息</div>';">
            ← 返回
        </button>
    `;
}

// 展开节点（带相似度参数）
async function expandNodeWithSimilarity(docId) {
    // 获取用户设置的相似度阈值
    const similarityInput = document.getElementById(`expandSimilarity_${docId}`);
    const minSimilarity = similarityInput ? parseInt(similarityInput.value) / 100 : 0.7;

    showStatus(`🔍 正在展开节点（相似度 ≥ ${(minSimilarity * 100).toFixed(0)}%）...`, 'loading');

    try {
        const response = await fetch(`${API_BASE}/graph/expand`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                doc_id: docId,
                top_k: 5,
                min_similarity: minSimilarity
            })
        });

        const data = await response.json();

        if (data.success && data.related_nodes.length > 0) {
            addRelatedNodes(docId, data.related_nodes);
            showStatus(`✓ 展开了 ${data.related_nodes.length} 个关联节点（≥${(minSimilarity * 100).toFixed(0)}%）`, 'success');
        } else {
            showStatus(`没有找到相似度 ≥ ${(minSimilarity * 100).toFixed(0)}% 的关联节点`, 'error');
        }
    } catch (error) {
        showStatus('展开失败: ' + error.message, 'error');
    }
}

// 展开节点（旧接口，保持兼容）
async function expandNode(docId) {
    expandNodeWithSimilarity(docId);
}

// 添加关联节点
function addRelatedNodes(fromId, relatedNodes) {
    const fromNode = nodes.get(fromId);
    if (!fromNode) return;

    // 确定新节点的层级（比源节点高1层）
    const newLayer = fromNode.layer + 1;

    // 计算新节点的布局位置（圆形分布）
    const radius = 350;  // 距离源节点的半径
    const angleStep = (Math.PI * 2) / relatedNodes.length;

    relatedNodes.forEach((nodeData, index) => {
        // 如果节点已存在，只添加边
        if (nodes.has(nodeData.doc_id)) {
            // 检查边是否已存在
            const edgeExists = edges.some(e =>
                (e.from === fromId && e.to === nodeData.doc_id) ||
                (e.from === nodeData.doc_id && e.to === fromId)
            );
            if (!edgeExists) {
                edges.push({
                    from: fromId,
                    to: nodeData.doc_id,
                    similarity: nodeData.similarity_score || 0.5
                });
            }
            return;
        }

        // 创建新节点
        nodeData.layer = newLayer;
        const node = new Node(nodeData);

        // 在源节点周围均匀分布
        const angle = index * angleStep;
        node.x = fromNode.x + radius * Math.cos(angle);
        node.y = fromNode.y + radius * Math.sin(angle);
        node.vx = 0;
        node.vy = 0;
        node.fixed = false;  // 新节点不固定，允许物理引擎调整

        nodes.set(node.id, node);

        // 添加边（包含相似度信息）
        edges.push({
            from: fromId,
            to: nodeData.doc_id,
            similarity: nodeData.similarity_score || 0.5
        });
    });
}

// 显示节点的所有关联详情（新方法）
async function showNodeRelations(docId) {
    const infoEl = document.getElementById('nodeInfo');
    infoEl.innerHTML = '<div class="info-empty">⏳ 正在分析节点关联...</div>';

    try {
        const response = await fetch(`${API_BASE}/graph/node-relations`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                doc_id: docId,
                top_k_per_vector: 5,      // 每个向量返回5个相似向量
                min_similarity: 0.2        // 降低阈值以包含更多弱关联
            })
        });

        const data = await response.json();

        if (data.success) {
            displayNodeRelations(docId, data.relations, data.related_nodes);
        } else {
            infoEl.innerHTML = '<div class="info-empty">❌ 加载失败</div>';
        }
    } catch (error) {
        infoEl.innerHTML = `<div class="info-empty">❌ 错误: ${error.message}</div>`;
    }
}

// 显示节点关联的详细视图
function displayNodeRelations(sourceDocId, relations, relatedNodes) {
    const infoEl = document.getElementById('nodeInfo');

    const sourceNode = nodes.get(sourceDocId);
    const sourceLabel = sourceNode ? sourceNode.label : `节点 ${sourceDocId}`;

    // 粒度映射
    const granularityNames = {
        'ngram': 'N-gram',
        'sentence': '句子',
        'n_sentences': 'N句子',
        'paragraph': '段落',
        'full': '全文'
    };

    // 统计信息
    const relatedCount = Object.keys(relations).length;
    let totalMatches = 0;
    for (const matches of Object.values(relations)) {
        totalMatches += matches.length;
    }

    // 构建关联节点列表
    let relationsHtml = '';
    if (relatedCount === 0) {
        relationsHtml = '<div style="color: #999; padding: 20px; text-align: center;">未找到关联节点</div>';
    } else {
        // 按匹配数量排序
        const sortedRelations = Object.entries(relations).sort((a, b) => b[1].length - a[1].length);

        relationsHtml = sortedRelations.map(([targetDocId, matches]) => {
            const targetNode = relatedNodes[targetDocId];
            const targetLabel = targetNode ? (targetNode.problem || targetNode.path || `节点 ${targetDocId}`) : `节点 ${targetDocId}`;

            // 构建匹配列表
            const matchesHtml = matches.map((match, index) => `
                <div style="margin-bottom: 12px; padding: 10px; background: white; border-radius: 4px; border-left: 2px solid ${index === 0 ? '#667eea' : '#e0e0e0'};">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <span style="font-size: 11px; font-weight: 600; color: #999;">匹配 #${index + 1}</span>
                        <span style="background: #667eea; color: white; padding: 1px 6px; border-radius: 8px; font-size: 10px;">
                            ${(match.similarity * 100).toFixed(1)}%
                        </span>
                    </div>

                    <div style="font-size: 11px; color: #667eea; margin-bottom: 3px;">
                        ↓ ${granularityNames[match.source_vec_granularity] || match.source_vec_granularity}
                    </div>
                    <div style="font-size: 12px; color: #555; line-height: 1.4; margin-bottom: 6px;">
                        ${match.source_vec_content || '(无内容)'}
                    </div>

                    <div style="font-size: 11px; color: #48bb78; margin-bottom: 3px;">
                        ↑ ${granularityNames[match.target_vec_granularity] || match.target_vec_granularity}
                    </div>
                    <div style="font-size: 12px; color: #555; line-height: 1.4;">
                        ${match.target_vec_content || '(无内容)'}
                    </div>
                </div>
            `).join('');

            return `
                <div style="margin-bottom: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 2px solid #e0e0e0;">
                        <div>
                            <div style="font-weight: 600; color: #333; margin-bottom: 4px;">
                                🔗 ${targetLabel}
                            </div>
                            <div style="font-size: 11px; color: #999;">
                                文档ID: ${targetDocId}
                            </div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 12px; color: #667eea; font-weight: 600;">
                                ${matches.length} 个匹配
                            </div>
                        </div>
                    </div>

                    <div style="max-height: 300px; overflow-y: auto;">
                        ${matchesHtml}
                    </div>
                </div>
            `;
        }).join('');
    }

    infoEl.innerHTML = `
        <h3>🔍 节点关联分析</h3>

        <div class="info-section">
            <div class="info-section-title">源节点</div>
            <div class="info-section-content">
                <strong>${sourceLabel}</strong> (ID: ${sourceDocId})
            </div>
        </div>

        <div class="info-section">
            <div class="info-section-title">统计信息</div>
            <div class="info-section-content">
                <div>关联节点数: <strong>${relatedCount}</strong></div>
                <div>总匹配数: <strong>${totalMatches}</strong></div>
                <div>平均匹配: <strong>${relatedCount > 0 ? (totalMatches / relatedCount).toFixed(1) : 0}</strong> 个/节点</div>
            </div>
        </div>

        <div class="info-section">
            <div class="info-section-title">关联节点详情</div>
            <div style="max-height: 500px; overflow-y: auto;">
                ${relationsHtml}
            </div>
        </div>

        <button class="expand-btn" onclick="selectNode(nodes.get(${sourceDocId}))">
            ← 返回节点信息
        </button>
    `;
}

// 删除节点
async function deleteNode(docId) {
    const node = nodes.get(docId);
    if (!node) {
        showStatus('❌ 节点不存在', 'error');
        return;
    }

    // 显示确认对话框
    const nodeName = node.label || `文档 ${docId}`;
    const confirmed = confirm(`⚠️ 确定要删除节点吗？\n\n节点: ${nodeName}\nID: ${docId}\n\n此操作将：\n• 删除物理文件\n• 删除数据库记录\n• 删除所有向量数据\n• 从图谱中移除节点\n\n此操作不可撤销！`);

    if (!confirmed) {
        return;
    }

    try {
        showStatus(`🗑️ 正在删除节点 ${docId}...`, 'loading');

        const response = await fetch(`${API_BASE}/document/${docId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || '删除失败');
        }

        if (data.success) {
            // 从图谱中移除节点
            nodes.remove(docId);

            // 移除所有与该节点相关的边
            const connectedEdges = edges.get({
                filter: edge => edge.from === docId || edge.to === docId
            });
            const edgeIds = connectedEdges.map(e => e.id);
            edges.remove(edgeIds);

            // 清空节点信息面板
            const infoEl = document.getElementById('nodeInfo');
            infoEl.innerHTML = '<div class="info-empty">节点已删除</div>';

            // 显示成功消息
            const stats = data.stats;
            showStatus(`✅ 成功删除节点 (向量:${stats.vectors}, n-grams:${stats.ngrams})`, 'success');

            console.log('节点删除成功:', data);
        } else {
            throw new Error('删除失败');
        }
    } catch (error) {
        console.error('删除节点失败:', error);
        showStatus(`❌ 删除失败: ${error.message}`, 'error');
    }
}

// 初始提示
showStatus('输入关键词开始搜索', 'success');
