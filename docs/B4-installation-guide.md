# Telos 安装部署手册
# Telos Installation & Deployment Guide

> **适用范围 / Audience**: DevOps 工程师、基础设施团队、安全运营工程师
> **版本 / Version**: v2.0

---

## 目录 / Table of Contents

1. [部署前准备 / Pre-Deployment Preparation](#1-部署前准备)
2. [部署模式选择 / Deployment Mode Selection](#2-部署模式选择)
3. [Docker Compose 部署 / Docker Compose Deployment](#3-docker-compose-部署)
4. [手动部署（非 Docker）/ Manual Deployment](#4-手动部署非-docker)
5. [Go 分析引擎部署（可选）/ Go Analysis Engine Deployment (Optional)](#5-go-分析引擎部署可选)
6. [数据库初始化 / Database Initialization](#6-数据库初始化)
7. [Nginx 反向代理配置 / Nginx Reverse Proxy Configuration](#7-nginx-反向代理配置)
8. [HTTPS/TLS 配置 / HTTPSTLS Configuration](#8-httpstls-配置)
9. [高可用部署 / High Availability Deployment](#9-高可用部署)
10. [备份与恢复 / Backup & Recovery](#10-备份与恢复)
11. [升级与迁移 / Upgrade & Migration](#11-升级与迁移)
12. [卸载 / Uninstallation](#12-卸载)
13. [故障排查 / Troubleshooting](#13-故障排查)

---

## 1. 部署前准备 / Pre-Deployment Preparation

### 1.1 系统要求 / System Requirements

#### 硬件要求 / Hardware Requirements

| 组件 | 最低配置 / Min | 推荐配置 / Recommended | 最大支持 / Max |
|------|---------------|---------------------|--------------|
| Control Plane | 4核/8GB/50GB | 8核/16GB/100GB SSD | — |
| Database (PostgreSQL) | 2核/4GB/100GB | 4核/16GB/500GB SSD | — |
| 每台被扫描资产 | — | 磁盘 5GB+ | — |

#### 软件要求 / Software Requirements

| 软件 | 版本要求 | 说明 |
|------|---------|------|
| Docker | 20.10+ | 容器运行时 |
| Docker Compose | v2.0+ | 容器编排（plugin 或独立版）|
| PostgreSQL | 14+ | 若不使用 Docker 内置 |
| Nginx | 1.18+ | 反向代理（可选）|
| Linux 内核 | 4.19+ | 生产环境推荐 |

#### 网络要求 / Network Requirements

| 端口 | 方向 | 用途 |
|------|------|------|
| 22/TCP | Control Plane → 资产 | SSH 扫描 |
| 443/TCP | 用户浏览器 → 前端 | HTTPS 访问 |
| 5432/TCP | 后端 → 数据库 | 数据库连接（内部）|
| 6379/TCP | 后端 → Redis | 缓存（内部）|
| 5985/TCP | Control Plane → Windows 资产 | WinRM（Windows 扫描）|

### 1.2 环境检查清单 / Pre-Flight Checklist

```bash
# 1. 检查 Docker
docker --version          # >= 20.10
docker compose version     # >= 2.0

# 2. 检查磁盘空间（建议 100GB+）
df -h

# 3. 检查内存
free -h

# 4. 检查 CPU
nproc

# 5. 检查端口占用（确保 3000/8000/5432 可用）
ss -tlnp | grep -E '3000|8000|5432'
```

### 1.3 防火墙配置 / Firewall Configuration

```bash
# Ubuntu/Debian
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 443/tcp    # HTTPS（部署后启用）
sudo ufw allow 3000/tcp   # 前端（仅直接访问时）
sudo ufw reload

# 目标服务器防火墙：确保 Control Plane IP 可访问 SSH(22) 和 WinRM(5985)
```

---

## 2. 部署模式选择 / Deployment Mode Selection

| 模式 | 适用场景 | 复杂度 | 扩展性 |
|------|---------|--------|--------|
| **Docker Compose 单机** | 快速验证、小规模（< 100 资产）| 低 | 差 |
| **Docker Compose 分布式** | 中等规模（100-1000 资产）| 中 | 一般 |
| **Kubernetes** | 大规模生产环境 | 高 | 好 |
| **纯手动部署** | 特殊环境（无 Docker）| 中 | 一般 |

---

## 3. Docker Compose 部署 / Docker Compose Deployment

### 3.1 获取安装包 / Get Installation Package

```bash
# 方式一：Git 克隆
git clone https://github.com/telos-project/telos.git
cd accountscan
git checkout v2.0.0  # 推荐指定版本

# 方式二：下载发布包
# wget https://github.com/telos-project/telos/releases/download/v2.0.0/telos-v2.0.0.tar.gz
# tar xzf accountscan-v2.0.0.tar.gz
# cd accountscan-v2.0.0
```

### 3.2 环境变量配置 / Environment Configuration

```bash
# 复制环境变量模板
cp .env.example .env

# 生成安全密钥
python3 -c "
import secrets
print('ACCOUNTSCAN_MASTER_KEY=' + secrets.token_hex(32))
print('ACCOUNTSCAN_JWT_SECRET=' + secrets.token_hex(32))
"
# 将输出结果填入 .env 文件
```

#### .env 完整参数说明 / Full .env Parameters

```bash
# ============ 必填参数 / REQUIRED ============

# 数据库密码（PostgreSQL）
DB_PASSWORD=YourStrongPassword123

# 主加密密钥（64位十六进制字符串，AES-256-GCM）
ACCOUNTSCAN_MASTER_KEY=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef

# JWT 签名密钥（64位十六进制字符串）
ACCOUNTSCAN_JWT_SECRET=fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210

# ============ 数据库配置 / DATABASE ============

# 数据库连接字符串（Docker 内部使用）
DATABASE_URL=postgresql://accountscan:${DB_PASSWORD}@db:5432/accountscan

# 连接池大小
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_RECYCLE=3600

# ============ 服务端口 / PORTS ============

PORT=8000                    # 后端 API 端口
FRONTEND_PORT=3000           # 前端主机端口（浏览器访问）

# ============ 可选组件 / OPTIONAL ============

# Go SSH 扫描引擎（大规模扫描推荐启用）
GO_SCANNER_URL=http://go-scanner:8081

# 邮件告警
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=alerts@example.com
SMTP_PASSWORD=smtp_password

# Redis（预留，用于未来 Celery 任务队列）
REDIS_URL=redis://redis:6379/0

# 日志级别
LOG_LEVEL=INFO
```

### 3.3 启动服务 / Start Services

```bash
# 构建并启动所有服务（首次运行自动构建镜像）
docker compose up -d --build

# 仅启动，不重新构建
docker compose up -d

# 查看服务状态
docker compose ps

# 查看所有日志
docker compose logs -f
```

### 3.4 验证部署 / Verify Deployment

```bash
# 1. 后端健康检查
curl http://localhost:8000/health
# 期望：
# {"status":"ok","service":"accountscan","version":"2.0.0","checks":{"database":"ok","encryption_key":"ok","scheduler":"running"}}

# 2. 前端健康检查
curl http://localhost:3000 | grep -q "accountscan" && echo "Frontend OK"

# 3. Swagger API 文档
# 访问 http://localhost:8000/docs

# 4. 默认登录
# http://localhost:3000
# 账号: admin / 密码: Admin123!
```

### 3.5 Docker Compose 服务说明 / Services Explained

| 服务名 | 镜像 | 端口 | 功能 |
|--------|------|------|------|
| `db` | postgres:16-alpine | 5432 (内部) | PostgreSQL 16 数据库 |
| `redis` | redis:7-alpine | 6379 (内部) | Redis 缓存（预留）|
| `app` | 本地构建 | 8000 (内部) | FastAPI 后端服务 |
| `frontend` | 本地构建 | 3000→80 | React 前端 + Nginx |

---

## 4. 手动部署（非 Docker）/ Manual Deployment

适用于无 Docker 的特殊环境（如某些合规要求的物理机房）。

### 4.1 系统依赖 / System Dependencies

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y \
    python3.11 python3.11-venv python3.11-dev \
    postgresql-16 postgresql-client-16 \
    nginx \
    build-essential libpq-dev unixodbc-dev \
    curl git
```

### 4.2 数据库安装与初始化 / Database Setup

```bash
# 1. 启动 PostgreSQL
sudo systemctl enable postgresql
sudo systemctl start postgresql

# 2. 创建数据库和用户
sudo -u postgres psql << EOF
CREATE USER accountscan WITH PASSWORD 'YourStrongPassword123';
CREATE DATABASE accountscan OWNER accountscan;
GRANT ALL PRIVILEGES ON DATABASE accountscan TO accountscan;
EOF

# 3. 安装 Python 依赖
cd /opt/accountscan
python3.11 -m venv backend/venv
source backend/venv/bin/activate
pip install -r backend/requirements.txt

# 4. 运行数据库迁移
export DATABASE_URL="postgresql://accountscan:YourStrongPassword123@localhost:5432/accountscan"
alembic upgrade head

# 5. 启动后端
export DATABASE_URL="postgresql://accountscan:YourStrongPassword123@localhost:5432/accountscan"
export ACCOUNTSCAN_MASTER_KEY="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
export ACCOUNTSCAN_JWT_SECRET="fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
export PORT=8000
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 4.3 Nginx 配置 / Nginx Configuration

```nginx
# /etc/nginx/sites-available/accountscan
server {
    listen 80;
    server_name telos.example.com;

    # 前端静态文件
    location / {
        root /opt/accountscan/frontend/dist;
        try_files $uri $uri/ /index.html;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket 支持（如有）
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## 5. Go 扫描引擎部署（可选）/ Go Scanner Engine Deployment (Optional)

Go 扫描引擎提供高性能并发扫描，推荐在**大规模生产环境（1000+ 账号）**时启用。

### 5.1 获取 Go 扫描引擎 / Get Go Scanner Binary

> ⚠️ Go 扫描引擎源码为独立项目，编译后生成 `telos-scanner` 二进制。
> 若已获得二进制，跳过编译步骤直接部署。

```bash
# 编译完成后传输到服务器（若在开发机交叉编译）
scp telos-scanner user@production-server:/opt/telos/
chmod +x /opt/telos/telos-scanner
```

### 5.2 systemd 服务配置 / systemd Service

```ini
# /etc/systemd/system/telos-scanner.service
[Unit]
Description=Telos Go Scanner Engine
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/telos
ExecStart=/opt/telos/telos-scanner -listen :8081
Restart=always
RestartSec=5
Environment=PORT=8081

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable telos-scanner
sudo systemctl start telos-scanner
sudo systemctl status telos-scanner
```

### 5.3 在 Docker Compose 中集成 / Integrate into Docker Compose

在 `.env` 中添加：

```bash
# Go SSH 扫描引擎地址（Docker 内部网络）
GO_SCANNER_URL=http://go-scanner:8081
```

并在 `docker-compose.yml` 中添加服务：

```yaml
services:
  go-scanner:
    image: accountscan/go-scanner:latest
    ports:
      - "8081:8081"        # 主机端口:容器端口
    restart: unless-stopped
    environment:
      - PORT=8081
```

> ⚠️ 主机上访问：`http://localhost:8081`；Docker 内部服务间访问：`http://go-scanner:8081`。

---

## 6. 数据库初始化 / Database Initialization

### 6.1 自动初始化 / Automatic Initialization

Docker Compose 部署时，数据库容器启动时会自动执行 `init.sql` 完成：
- 创建 extensions（pgcrypto 等）
- 创建 schema
- 创建初始管理员账户（admin/Admin123!）

### 6.2 手动数据库迁移 / Manual Database Migration

```bash
# 进入后端容器
docker compose exec app bash

# 运行 Alembic 迁移
alembic upgrade head

# 创建初始管理员
python -c "
from backend.database import get_db
from backend.models import User, UserRole
from backend.auth import hash_password
db = next(get_db())
if not db.query(User).filter(User.username=='admin').first():
    u = User(username='admin', password_hash=hash_password('Admin123!'), role=UserRole.admin)
    db.add(u)
    db.commit()
    print('Admin created')
"
```

### 6.3 数据库维护 / Database Maintenance

```sql
-- 查看数据库大小
SELECT pg_size_pretty(pg_database_size('accountscan'));

-- 查看最大连接数
SHOW max_connections;

-- 清理连接池
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='accountscan' AND pid<>pg_backend_pid();
```

---

## 7. Nginx 反向代理配置 / Nginx Reverse Proxy Configuration

### 7.1 Docker 前端容器内 Nginx 配置 / Container Nginx Config

容器内 Nginx 已预配置（见 frontend/Dockerfile），将 `/api/` 请求代理到 `app:8000`。

### 7.2 独立 Nginx 作为统一入口 / Standalone Nginx

在 Control Plane 主机上安装独立 Nginx，统一处理 HTTPS 并代理到 Docker 容器：

```nginx
# /etc/nginx/sites-available/accountscan
upstream backend {
    server 127.0.0.1:8000;
}

upstream frontend {
    server 127.0.0.1:3000;
}

server {
    listen 80;
    server_name telos.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name telos.yourdomain.com;

    ssl_certificate /etc/ssl/certs/telos.crt;
    ssl_certificate_key /etc/ssl/private/telos.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # 前端（静态文件 + SPA fallback）
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # API 代理
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }

    # SSE 流（实时告警）
    location /api/v1/alerts/stream {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # 上传大文件（如 CSV 导出）
    client_max_body_size 100m;
}
```

```bash
sudo ln -s /etc/nginx/sites-available/accountscan /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 8. HTTPS/TLS 配置 / HTTPS/TLS Configuration

### 8.1 Let's Encrypt 免费证书 / Let's Encrypt Free Certificate

```bash
# 安装 Certbot
sudo apt install -y certbot python3-certbot-nginx

# 获取证书（确保域名已解析）
sudo certbot --nginx -d telos.yourdomain.com

# 自动续期验证
sudo systemctl enable certbot.timer
```

### 8.2 自签名证书（测试环境）/ Self-Signed Certificate (Testing)

```bash
# 生成自签名证书
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/ssl/private/telos.key \
    -out /etc/ssl/certs/telos.crt \
    -subj "/C=CN/ST=Beijing/L=Beijing/O=YourOrg/OU=IT/CN=telos.yourdomain.com"
```

---

## 9. 高可用部署 / High Availability Deployment

### 9.1 HA 架构概述 / HA Architecture Overview

```
                    ┌──────────────┐
                    │   Nginx LB  │  ← HTTPS 终结
                    │ (2+ nodes)  │
                    └──────┬───────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────▼─────┐   ┌──────▼──────┐  ┌──────▼──────┐
    │  Frontend │   │   Frontend  │  │   Frontend  │
    │  Node 1   │   │   Node 2   │  │   Node N    │
    └─────┬─────┘   └──────┬──────┘  └──────┬──────┘
          │                │                │
    ┌─────▼────────────────▼────────────────▼─────┐
    │           PostgreSQL Primary                │
    │        + Streaming Replication              │
    │         (1 primary + 2 replicas)            │
    └────────────────────────────────────────────┘
```

### 9.2 PostgreSQL 主从复制 / PostgreSQL Streaming Replication

```sql
-- 主库创建复制用户
CREATE USER replicator WITH REPLICATION PASSWORD 'repl_password' LOGIN;

-- 主库配置 pg_hba.conf
host replication replicator 10.0.0.0/24 md5

-- 主库修改 postgresql.conf
wal_level = replica
max_wal_senders = 3
wal_keep_size = 1GB
hot_standby = on

-- 从库使用 pg_basebackup 克隆
pg_basebackup -h primary_ip -D /var/lib/postgresql/16/main \
    -U replicator -P -Fp -Xs -R
```

### 9.3 多后端实例负载均衡 / Multiple Backend Instances

```nginx
upstream backend_cluster {
    least_conn;  # 最少连接负载均衡
    server 10.0.1.10:8000;
    server 10.0.1.11:8000;
    server 10.0.1.12:8000;
}
```

---

## 10. 备份与恢复 / Backup & Recovery

### 10.1 自动备份脚本 / Automated Backup Script

```bash
#!/bin/bash
# backup.sh - 每日备份脚本，建议通过 cron 执行
set -e

BACKUP_DIR="/opt/accountscan/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="accountscan"
DB_USER="accountscan"
KEEP_DAYS=30

mkdir -p ${BACKUP_DIR}

# 备份数据库
echo "Backing up database..."
pg_dump -U ${DB_USER} -h localhost ${DB_NAME} | gzip > ${BACKUP_DIR}/db_${DATE}.sql.gz

# 备份配置文件
echo "Backing up config..."
tar czf ${BACKUP_DIR}/config_${DATE}.tar.gz /opt/accountscan/.env /etc/nginx/sites-available/accountscan

# 保留最近 KEEP_DAYS 天备份
find ${BACKUP_DIR} -name "*.gz" -mtime +${KEEP_DAYS} -delete

echo "Backup completed: ${DATE}"
```

**添加 cron 定时任务：**
```bash
# 每天凌晨 3 点执行备份
echo "0 3 * * * root /opt/accountscan/backup.sh >> /var/log/accountscan_backup.log 2>&1" | sudo tee /etc/cron.d/accountscan-backup
```

### 10.2 数据恢复 / Data Recovery

```bash
# 1. 停止服务
docker compose stop app

# 2. 恢复数据库
gunzip < /opt/accountscan/backups/db_20260412_030000.sql.gz | psql -U accountscan -h localhost accountscan

# 3. 恢复配置文件
tar xzf /opt/accountscan/backups/config_20260412_030000.tar.gz -C /

# 4. 重启服务
docker compose restart app
```

---

## 11. 升级与迁移 / Upgrade & Migration

### 11.1 版本升级 / Version Upgrade

```bash
# 1. 备份（必须）
/opt/accountscan/backup.sh

# 2. 下载新版本
git fetch origin
git checkout v2.1.0

# 3. 更新环境变量（如有新参数）
diff .env .env.example

# 4. 重新构建并启动
docker compose up -d --build

# 5. 运行数据库迁移
docker compose exec app alembic upgrade head

# 6. 验证
curl http://localhost:8000/health
```

### 11.2 数据迁移 / Data Migration

```bash
# 迁移数据库到新服务器
pg_dump -U accountscan -h old-server accountscan | \
    psql -U accountscan -h new-server accountscan
```

---

## 12. 卸载 / Uninstallation

### 12.1 Docker Compose 卸载 / Docker Compose Uninstall

```bash
# 1. 停止并删除所有容器
docker compose down

# 2. 删除镜像（可选）
docker compose down --rmi all

# 3. 删除数据卷（⚠️ 会删除所有数据，不可恢复）
docker compose down -v

# 4. 删除安装目录
rm -rf /opt/accountscan
```

### 12.2 清理残留数据 / Clean Up Residual Data

```bash
# 删除 PostgreSQL 数据（如果在主机上安装）
sudo systemctl stop postgresql
sudo rm -rf /var/lib/postgresql/16/main

# 删除 Nginx 配置
sudo rm -f /etc/nginx/sites-enabled/accountscan
sudo nginx -t && sudo systemctl reload nginx
```

---

## 13. 故障排查 / Troubleshooting

### 13.1 常见问题速查 / Quick Diagnosis

| 症状 | 检查命令 | 可能原因 |
|------|---------|---------|
| 后端启动失败 | `docker compose logs app` | 环境变量缺失、端口占用 |
| 前端 502 | `docker compose logs frontend` | 后端未启动 |
| 数据库连接失败 | `docker compose logs db` | 密码错误、网络问题 |
| 扫描超时 | `docker compose logs app` | SSH 凭据错误、网络不通 |
| 告警未触发 | 检查告警服务状态 | 通知渠道未配置 |

### 13.2 日志收集 / Log Collection

```bash
# 后端完整日志
docker compose logs app > /tmp/accountscan-app.log

# 前端日志
docker compose logs frontend > /tmp/accountscan-frontend.log

# 数据库日志
docker compose logs db > /tmp/accountscan-db.log

# 内核日志（如有系统级问题）
dmesg | grep -i accountscan
```

### 13.3 端口检查 / Port Diagnostics

```bash
# 检查端口占用
ss -tlnp | grep -E '3000|8000|5432'

# 检查容器间网络
docker compose exec app ping -c 2 db
docker compose exec app ping -c 2 redis
```

### 13.4 数据库连接问题 / Database Connection Issues

```bash
# 从 app 容器内测试数据库连接
docker compose exec app bash -c "psql '${DATABASE_URL}' -c 'SELECT 1'"

# 检查 pg_hba.conf
docker compose exec db cat /var/lib/postgresql/data/pg_hba.conf | grep -v "^#" | grep -v "^$"
```

---

## 附录 / Appendix

### A. 环境变量完整参考 / Full Environment Variables Reference

| 变量名 | 必填 | 默认值 | 说明 |
|--------|------|--------|------|
| `DB_PASSWORD` | ✅ | — | PostgreSQL 密码 |
| `ACCOUNTSCAN_MASTER_KEY` | ✅ | — | AES-256 加密密钥（64位hex）|
| `ACCOUNTSCAN_JWT_SECRET` | ✅ | — | JWT 签名密钥（64位hex）|
| `DATABASE_URL` | | 自动生成 | PostgreSQL 连接串 |
| `DB_POOL_SIZE` | | 10 | 连接池大小 |
| `DB_MAX_OVERFLOW` | | 20 | 连接池最大溢出 |
| `PORT` | | 8000 | 后端监听端口 |
| `FRONTEND_PORT` | | 3000 | 前端主机端口 |
| `GO_SCANNER_URL` | | — | Go 扫描引擎地址（Docker 内部 `http://go-scanner:8081`，宿主机 `http://localhost:8081`） |
| `REDIS_URL` | | redis://redis:6379/0 | Redis 连接串 |
| `LOG_LEVEL` | | INFO | 日志级别 |
| `SMTP_HOST/PORT/USER/PASSWORD` | | — | 邮件告警配置 |

### B. API 端点快速索引 / API Endpoint Quick Reference

| 端点 | 说明 |
|------|------|
| `GET /health` | 服务健康检查 |
| `POST /api/v1/auth/login` | 用户登录 |
| `GET /api/v1/assets` | 资产列表 |
| `POST /api/v1/scans` | 发起扫描 |
| `GET /api/v1/alerts` | 告警列表 |
| `GET /api/v1/identity-threat/analyses` | 威胁分析列表 |
| `GET /docs` | Swagger API 文档 |
| `GET /redoc` | ReDoc API 文档 |

---

*Telos v2.0 | © 2026 Telos*
