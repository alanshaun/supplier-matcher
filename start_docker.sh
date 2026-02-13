#!/bin/bash
# Docker一键启动脚本 - 2026 兼容版

echo "=========================================="
echo "🐳 供应商智能匹配系统 - Docker部署"
echo "=========================================="

# 检查Docker是否运行
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker未运行"
    echo "请先启动Docker Desktop"
    exit 1
fi

echo "✅ Docker运行正常"
echo ""

# 检查.env文件
if [ ! -f .env ]; then
    echo "❌ 未找到 .env 文件"
    echo "请确保 .env 文件存在并包含API Keys"
    exit 1
fi

echo "✅ 配置文件存在"
echo ""

# 停止旧容器 - 已改为 docker compose
echo "🔄 停止旧容器..."
docker compose down 2>/dev/null

echo ""
echo "🏗️  构建Docker镜像..."
docker compose build  # 👈 这里改成了空格

if [ $? -ne 0 ]; then
    echo "❌ 构建失败"
    exit 1
fi

echo ""
echo "🚀 启动容器..."
docker compose up -d  # 👈 这里改成了空格

if [ $? -ne 0 ]; then
    echo "❌ 启动失败"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ 部署成功！"
echo "=========================================="
echo ""
echo "🌐 Web界面地址: http://localhost:8501"
echo "📊 查看日志:   docker compose logs -f"
echo "🛑 停止服务:   docker compose down"
echo "=========================================="

# 等待并检查
echo "⏳ 等待服务启动..."
sleep 5

if docker ps | grep supplier-matcher > /dev/null; then
    echo "✅ 容器运行中"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        open http://localhost:8501
    fi
else
    echo "⚠️  容器可能未正常启动"
    echo "查看日志: docker compose logs"
fi