#!/usr/bin/env bash
# 一键启动完整开发环境: PostgreSQL + Redis + 后端 (FastAPI) + 前端 (Vite)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_BACK=true
RUN_FRONT=true
RUN_DB=true

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BLUE}$1${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() {
  echo -e "${GREEN}✓${NC} $1"
}

print_info() {
  echo -e "${BLUE}ℹ${NC} $1"
}

print_warning() {
  echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
  echo -e "${RED}✗${NC} $1"
}

usage() {
  cat <<'USAGE'
用法:
  ./start_dev.sh [--back|--front|--no-db]

参数:
  --back    仅启动后端
  --front   仅启动前端
  --no-db   跳过数据库检查和启动
  -h, --help 显示帮助信息
USAGE
}

for arg in "$@"; do
  case "$arg" in
    --back)
      RUN_FRONT=false
      ;;
    --front)
      RUN_BACK=false
      RUN_DB=false
      ;;
    --no-db)
      RUN_DB=false
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数: $arg" >&2
      usage
      exit 1
      ;;
  esac
done

print_header "🚀 LLMVoiceDesk 开发环境启动"

# ============================================
# 检查并启动 PostgreSQL
# ============================================
check_and_start_postgres() {
  print_info "检查 PostgreSQL 状态..."
  
  # 首先检查 Docker容器
  if command -v docker >/dev/null 2>&1 || [ -f "/Applications/Docker.app/Contents/Resources/bin/docker" ]; then
    DOCKER_CMD="docker"
    if ! command -v docker >/dev/null 2>&1; then
      DOCKER_CMD="/Applications/Docker.app/Contents/Resources/bin/docker"
    fi
    
    if $DOCKER_CMD ps 2>/dev/null | grep -q llm-voice-agent-db; then
      print_success "PostgreSQL (Docker) 已运行"
      return 0
    fi
    
    # 尝试启动Docker容器
    if [ -f "$ROOT_DIR/docker-compose.yml" ]; then
      print_info "尝试使用 Docker 启动 PostgreSQL..."
      if $DOCKER_CMD compose up -d postgres >/dev/null 2>&1; then
        sleep 3
        if $DOCKER_CMD ps 2>/dev/null | grep -q llm-voice-agent-db; then
          print_success "PostgreSQL (Docker) 启动成功"
          return 0
        fi
      fi
    fi
  fi
  
  # 检查本地 PostgreSQL 是否运行
  if command -v pg_isready >/dev/null 2>&1; then
    if pg_isready -h localhost -p 5432 >/dev/null 2>&1; then
      print_success "PostgreSQL 已运行"
      return 0
    fi
  fi
  
  print_warning "PostgreSQL 未运行,尝试启动..."
  
  # 尝试使用 Homebrew 启动
  if command -v brew >/dev/null 2>&1; then
    if brew services list | grep -q "postgresql.*started"; then
      print_success "PostgreSQL 服务已启动"
      return 0
    fi
    
    # 尝试启动 PostgreSQL
    if brew services start postgresql@14 >/dev/null 2>&1 || brew services start postgresql >/dev/null 2>&1; then
      print_info "等待 PostgreSQL 启动..."
      sleep 3
      if command -v pg_isready >/dev/null 2>&1 && pg_isready -h localhost -p 5432 >/dev/null 2>&1; then
        print_success "PostgreSQL 启动成功"
        return 0
      fi
    fi
  fi
  
  print_error "PostgreSQL 启动失败,请手动启动"
  print_info "提示: docker compose up -d postgres 或 brew services start postgresql"
  return 1
}

# ============================================
# 检查并启动 Redis
# ============================================
check_and_start_redis() {
  print_info "检查 Redis 状态..."
  
  # 首先检查 Docker容器
  if command -v docker >/dev/null 2>&1 || [ -f "/Applications/Docker.app/Contents/Resources/bin/docker" ]; then
    DOCKER_CMD="docker"
    if ! command -v docker >/dev/null 2>&1; then
      DOCKER_CMD="/Applications/Docker.app/Contents/Resources/bin/docker"
    fi
    
    if $DOCKER_CMD ps 2>/dev/null | grep -q llm-voice-agent-redis; then
      print_success "Redis (Docker) 已运行"
      return 0
    fi
    
    # 尝试启动Docker容器
    if [ -f "$ROOT_DIR/docker-compose.yml" ]; then
      print_info "尝试使用 Docker 启动 Redis..."
      if $DOCKER_CMD compose up -d redis >/dev/null 2>&1; then
        sleep 2
        if $DOCKER_CMD ps 2>/dev/null | grep -q llm-voice-agent-redis; then
          print_success "Redis (Docker) 启动成功"
          return 0
        fi
      fi
    fi
  fi
  
  # 检查本地 Redis 是否运行
  if command -v redis-cli >/dev/null 2>&1; then
    if redis-cli ping >/dev/null 2>&1; then
      print_success "Redis 已运行"
      return 0
    fi
  fi
  
  print_warning "Redis 未运行,尝试启动..."
  
  # 尝试使用 Homebrew 启动
  if command -v brew >/dev/null 2>&1; then
    if brew services list | grep -q "redis.*started"; then
      print_success "Redis 服务已启动"
      return 0
    fi
    
    if brew services start redis >/dev/null 2>&1; then
      sleep 2
      if command -v redis-cli >/dev/null 2>&1 && redis-cli ping >/dev/null 2>&1; then
        print_success "Redis 启动成功"
        return 0
      fi
    fi
  fi
  
  print_warning "Redis 启动失败 (可选服务,可继续)"
  return 0
}

# ============================================
# 确保 Poetry 已安装
# ============================================
ensure_poetry() {
  print_info "检查 Poetry..."
  POETRY_BIN="$(command -v poetry || true)"
  if [ -n "$POETRY_BIN" ]; then
    print_success "Poetry 已安装: $POETRY_BIN"
    return
  fi
  
  print_warning "Poetry 未找到,尝试自动安装..."
  if command -v pip3 >/dev/null 2>&1; then
    pip3 install --user poetry && POETRY_BIN="$(command -v poetry || true)"
  elif command -v pip >/dev/null 2>&1; then
    pip install --user poetry && POETRY_BIN="$(command -v poetry || true)"
  fi
  
  if [ -z "$POETRY_BIN" ]; then
    print_error "Poetry 安装失败,请手动安装"
    exit 1
  fi
  print_success "Poetry 安装成功"
}

# ============================================
# 安装依赖
# ============================================
ensure_dependencies() {
  if [ "$RUN_FRONT" = true ]; then
    print_info "检查前端依赖..."
    if [ ! -d "$ROOT_DIR/frontend/node_modules" ]; then
      print_warning "前端依赖未安装,执行 npm install..."
      (cd "$ROOT_DIR/frontend" && npm install)
      print_success "前端依赖安装完成"
    else
      print_success "前端依赖已安装"
    fi
  fi
  
  if [ "$RUN_BACK" = true ]; then
    print_info "检查后端依赖..."
    if [ ! -d "$ROOT_DIR/backend/.venv" ] && [ -n "$POETRY_BIN" ]; then
      print_warning "后端依赖未安装,执行 poetry install..."
      (cd "$ROOT_DIR/backend" && "$POETRY_BIN" install)
      print_success "后端依赖安装完成"
    else
      print_success "后端依赖已安装"
    fi
  fi
}

# ============================================
# 运行数据库迁移
# ============================================
run_migrations() {
  if [ "$RUN_BACK" = true ] && [ "$RUN_DB" = true ]; then
    print_info "检查数据库迁移..."
    if [ -n "$POETRY_BIN" ]; then
      (cd "$ROOT_DIR/backend" && "$POETRY_BIN" run alembic upgrade head 2>/dev/null) && \
        print_success "数据库迁移完成" || \
        print_warning "数据库迁移跳过 (可能未配置)"
    fi
  fi
}

# ============================================
# 主动启动 Docker 服务（一键启动的核心）
# ============================================
start_docker_services() {
  # 检查 Docker 是否可用
  DOCKER_CMD=""
  if command -v docker >/dev/null 2>&1; then
    DOCKER_CMD="docker"
  elif [ -f "/Applications/Docker.app/Contents/Resources/bin/docker" ]; then
    DOCKER_CMD="/Applications/Docker.app/Contents/Resources/bin/docker"
  fi
  
  if [ -z "$DOCKER_CMD" ]; then
    return 0  # Docker不可用，跳过
  fi
  
  # 检查是否有 docker-compose.yml
  if [ ! -f "$ROOT_DIR/docker-compose.yml" ]; then
    return 0  # 没有docker-compose文件，跳过
  fi
  
  print_info "检测到 docker-compose.yml，启动 Docker 服务..."
  
  # 一键启动所有Docker服务
  if $DOCKER_CMD compose up -d >/dev/null 2>&1; then
    print_success "Docker 服务启动成功"
    sleep 2  # 等待服务初始化
  else
    print_warning "Docker 服务启动失败，将尝试其他方式"
  fi
}

# ============================================
# 主流程
# ============================================

# 优先启动 Docker 服务（如果可用）
if [ "$RUN_DB" = true ]; then
  print_header "📦 数据库服务"
  start_docker_services
  check_and_start_postgres
  check_and_start_redis
fi

# 依赖检查
print_header "🔧 依赖检查"
if [ "$RUN_BACK" = true ]; then
  ensure_poetry
fi
ensure_dependencies

# 数据库迁移
if [ "$RUN_DB" = true ]; then
  run_migrations
fi

# 启动服务
print_header "🎯 启动服务"

BACKEND_CMD="cd \"$ROOT_DIR/backend\" && $POETRY_BIN run uvicorn app.main:app --reload --port 8000"
FRONTEND_CMD="cd \"$ROOT_DIR/frontend\" && npm run dev"

# 捕获退出信号,清理子进程
cleanup() {
  echo ""
  print_warning "停止服务..."
  pkill -P $$ 2>/dev/null || true
  print_success "服务已停止"
}
trap cleanup EXIT INT TERM

if [ "$RUN_BACK" = true ]; then
  print_info "启动后端: http://localhost:8000"
  /bin/bash -c "$BACKEND_CMD" &
  BACK_PID=$!
else
  BACK_PID=""
fi

if [ "$RUN_FRONT" = true ]; then
  print_info "启动前端: http://localhost:5173"
  /bin/bash -c "$FRONTEND_CMD" &
  FRONT_PID=$!
else
  FRONT_PID=""
fi

sleep 2
print_header "✅ 开发环境已启动"
echo ""
print_success "后端: http://localhost:8000"
print_success "前端: http://localhost:5173"
print_success "API文档: http://localhost:8000/docs"
echo ""
print_info "按 Ctrl+C 停止所有服务"
echo ""

# 轮询监控任一子进程退出
while true; do
  if [ -n "$BACK_PID" ] && ! kill -0 $BACK_PID 2>/dev/null; then
    print_error "后端进程已退出"
    [ -n "$FRONT_PID" ] && kill $FRONT_PID 2>/dev/null || true
    break
  fi
  if [ -n "$FRONT_PID" ] && ! kill -0 $FRONT_PID 2>/dev/null; then
    print_error "前端进程已退出"
    [ -n "$BACK_PID" ] && kill $BACK_PID 2>/dev/null || true
    break
  fi
  if [ -z "$BACK_PID" ] && [ -z "$FRONT_PID" ]; then
    break
  fi
  sleep 1
done

# 等待清理
[ -n "$BACK_PID" ] && wait $BACK_PID 2>/dev/null || true
[ -n "$FRONT_PID" ] && wait $FRONT_PID 2>/dev/null || true
