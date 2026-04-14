# Telos 运维手册
# Telos Operations Runbook

> **适用范围 / Audience**: 运维工程师 / SRE / DevOps
> **版本 / Version**: v2.0

---

## 1. 日常巡检清单 / Daily Operations Checklist

### 1.1 每日必检 / Daily Checks

```bash
#!/bin/bash
# Telos 每日巡检脚本 / Telos Daily Health Check Script

echo "=== Telos Daily Health Check ==="
echo "Time: $(date)"
echo ""

# 1. 检查容器状态
echo "[1] Container Status:"
docker compose ps
echo ""

# 2. 检查后端健康
echo "[2] Backend Health:"
curl -s http://localhost:8000/health | jq .
echo ""

# 3. 检查磁盘空间
echo "[3] Disk Usage:"
df -h | grep -E '/dev/|overlay'
echo ""

# 4. 检查内存使用
echo "[4] Memory Usage:"
free -h
echo ""

# 5. 检查数据库连接
echo "[5] Database Connections:"
docker compose exec db psql -U accountscan -d accountscan -c \
  "SELECT count(*) as total, state FROM pg_stat_activity GROUP BY state;" 2>/dev/null
echo ""

# 6. 检查 Redis
echo "[6] Redis Status:"
docker compose exec redis redis-cli ping
echo ""

# 7. 检查扫描任务状态
echo "[7] Recent Scans:"
curl -s http://localhost:8000/api/v1/scans?page_size=5 | jq \
  '.data.items[] | {id, status, account_count, created_at}'
echo ""

# 8. 检查告警统计
echo "[8] Alert Statistics (24h):"
curl -s http://localhost:8000/api/v1/alerts/stats?period=24h | jq '.data.total'
echo ""

# 9. 检查最近的错误日志
echo "[9] Recent Errors (last 5):"
docker compose logs --tail=100 app 2>&1 | grep -i error | tail -5
echo ""

# 10. 检查 CPU 负载
echo "[10] System Load:"
uptime
echo ""

echo "=== Health Check Complete ==="
```

### 1.2 健康阈值 / Health Thresholds

| 指标 / Metric | 正常范围 / Normal | 警告阈值 / Warning | 紧急阈值 / Critical |
|-------------|-----------------|------------------|------------------|
| 磁盘使用率 / Disk usage | < 60% | 60-80% | > 80% |
| 内存使用率 / Memory usage | < 70% | 70-85% | > 85% |
| PostgreSQL 连接数 | < 80/200 | 80-150 | > 150 |
| 后端 API 响应时间 | < 500ms | 500ms-2s | > 2s |
| 扫描失败率 / Scan failure rate | < 5% | 5-15% | > 15% |
| 告警未响应率 / Unacknowledged alerts | < 20% | 20-50% | > 50% |

---

## 2. 监控指标与告警阈值 / Monitoring Metrics & Alert Thresholds

### 2.1 Prometheus 关键指标 / Key Prometheus Metrics

| 指标 / Metric | 说明 / Description | 告警阈值 / Alert Threshold |
|--------------|------------------|------------------------|
| `telos_api_request_duration_seconds` | API 响应时间 | p99 > 5s |
| `telos_api_request_errors_total` | API 错误数 | rate > 0.01/s |
| `telos_scan_jobs_running` | 运行中扫描任务 | > 20 |
| `telos_scan_job_duration_seconds` | 扫描任务耗时 | p95 > 600s |
| `telos_alerts_total{level="critical"}` | 严重告警数量 | > 10/小时 |
| `telos_db_connections_active` | 数据库活跃连接 | > 150 |
| `telos_analysis_duration_seconds` | 分析任务耗时 | p95 > 300s |
| `telos_realtime_monitor_lag_seconds` | 实时监控延迟 | > 60s |

### 2.2 Grafana Dashboard / Grafana 仪表板

建议的 Dashboard 配置：

```
Dashboard: Telos 运营仪表板 / Telos Operations Dashboard
├── 系统概览 / System Overview
│   ├── 容器 CPU/内存使用率 / Container CPU/Memory
│   ├── API 请求 QPS 和响应时间 / API QPS & Latency
│   └── 数据库连接数 / DB Connections
├── 扫描健康 / Scan Health
│   ├── 扫描任务状态分布 / Scan Job Status Distribution
│   ├── 扫描成功率趋势 / Scan Success Rate Trend
│   └── 平均扫描时间 / Average Scan Duration
├── 告警态势 / Alert Posture
│   ├── 告警数量趋势 / Alert Count Trend
│   ├── 未响应告警数量 / Unacknowledged Alert Count
│   └── 按级别分布 / Alerts by Level
└── 安全态势 / Security Posture
    ├── 全局风险评分趋势 / Global Risk Score Trend
    └── ATT&CK 战术覆盖 / ATT&CK Tactic Coverage
```

---

## 3. 性能调优指南 / Performance Tuning Guide

### 3.1 PostgreSQL 调优 / PostgreSQL Tuning

```sql
-- 查看当前慢查询
SELECT query, calls, mean_time, total_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- 查看未使用索引
SELECT indexrelname, idx_scan, idx_tup_read
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY pg_relation_size(indexrelid) DESC;

-- 查看表大小
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 10;
```

**推荐配置 / Recommended Settings:**

```ini
# postgresql.conf
max_connections = 200
shared_buffers = 256MB          # 宿主机内存的 1/4
effective_cache_size = 1GB      # 宿主机内存的 1/2
work_mem = 64MB
maintenance_work_mem = 128MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1          # SSD 设置为 1.1，HDD 设置为 4.0
```

### 3.2 Redis 调优 / Redis Tuning

```bash
# 查看 Redis 内存使用
docker compose exec redis redis-cli info memory

# 查看慢命令
docker compose exec redis redis-cli slowlog get 10

# 设置最大内存（根据可用内存调整）
docker compose exec redis redis-cli config set maxmemory 512mb
docker compose exec redis redis-cli config set maxmemory-policy allkeys-lru
```

### 3.3 扫描性能优化 / Scan Performance Optimization

> ⚠️ 以下环境变量需在 `.env` 中配置，修改后执行 `docker compose restart app` 使配置生效。

```bash
# 调整扫描并发数
SCAN_CONCURRENCY=20    # 默认 5，可提升到 20-50（视网络质量而定）

# 调整单台资产扫描超时（秒）
SCAN_TIMEOUT_SECONDS=300  # 默认 120 秒，大规模网络环境可调大

# Redis 缓存 TTL（秒）
SCAN_RESULT_CACHE_TTL=3600  # 扫描结果缓存有效时间
```

---

## 4. 数据库维护 / Database Maintenance

### 4.1 定期维护任务 / Scheduled Maintenance Tasks

```bash
#!/bin/bash
# /opt/accountscan/scripts/db_maintenance.sh
# 建议通过 cron 每周执行一次

set -e

echo "=== Database Maintenance ==="
echo "Start: $(date)"

# 1. VACUUM ANALYZE（清理死元组并更新统计信息）
docker compose exec -T db psql -U accountscan -d accountscan -c \
  "VACUUM (VERBOSE, ANALYZE)"

# 2. 重建失效索引
docker compose exec -T db psql -U accountscan -d accountscan -c \
  "REINDEX DATABASE accountscan"

# 3. 清理过期扫描快照（保留最近 90 天）
docker compose exec -T db psql -U accountscan -d accountscan -c \
  "DELETE FROM scans WHERE started_at < NOW() - INTERVAL '90 days'"

# 4. 清理过期审计日志（保留 180 天）
docker compose exec -T db psql -U accountscan -d accountscan -c \
  "DELETE FROM audit_logs WHERE created_at < NOW() - INTERVAL '180 days'"

# 5. 清理过期分析记录（保留 90 天）
docker compose exec -T db psql -U accountscan -d accountscan -c \
  "DELETE FROM analysis_jobs WHERE started_at < NOW() - INTERVAL '90 days'"

echo "=== Database Maintenance Complete ==="
echo "End: $(date)"
```

**Cron 配置 / Cron Configuration:**
```cron
# 每周日凌晨 3 点执行数据库维护
0 3 * * 0 /opt/accountscan/scripts/db_maintenance.sh >> /var/log/accountscan/db_maintenance.log 2>&1
```

### 4.2 备份与恢复 / Backup & Restore

**备份 / Backup:**
```bash
#!/bin/bash
# /opt/accountscan/scripts/backup.sh
# 建议通过 cron 每日执行

BACKUP_DIR="/var/backups/accountscan"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# 1. 数据库全量备份
docker compose exec -T db pg_dump -U accountscan -d accountscan \
  | gzip > "$BACKUP_DIR/postgres_full_$DATE.sql.gz"

# 2. 上传到对象存储（示例：S3）
aws s3 cp "$BACKUP_DIR/postgres_full_$DATE.sql.gz" \
  s3://your-bucket/telos-backups/ 2>/dev/null || \
  echo "S3 upload skipped (aws cli not configured)"

# 3. 清理本地备份（保留 30 天）
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete

echo "Backup complete: $BACKUP_DIR/postgres_full_$DATE.sql.gz"
```

**恢复 / Restore:**
```bash
# 从备份文件恢复
gunzip < /var/backups/accountscan/postgres_full_20260401_030000.sql.gz \
  | docker compose exec -T db psql -U accountscan -d accountscan

# 从 S3 恢复
aws s3 cp s3://your-bucket/telos-backups/postgres_full_20260401_030000.sql.gz - \
  | gunzip | docker compose exec -T db psql -U accountscan -d accountscan
```

---

## 5. 故障应急响应流程 / Incident Response Playbook

### 5.1 故障分级 / Incident Severity

| 级别 / Severity | 定义 / Definition | 响应时间 / Response Time | 示例 / Example |
|---------------|-----------------|----------------------|--------------|
| P0 / Critical | 全系统不可用，数据泄露风险 | 15 分钟 | 数据库崩溃，后端无法启动 |
| P1 / High | 核心功能不可用 | 1 小时 | 扫描失败，告警无法触发 |
| P2 / Medium | 非核心功能异常 | 4 小时 | Webhook 推送失败 |
| P3 / Low | 界面/体验问题 | 24 小时 | 加载慢，UI 显示异常 |

### 5.2 P0 故障处理流程 / P0 Incident Response

```
⏱️ T+0: 发现/接到告警
  └── 立即确认：检查 docker compose ps，查看告警详情
      ↓
⏱️ T+5min: 评估影响范围
  └── 哪些服务受影响？数据是否受损？
      ├── 容器重启：`docker compose restart <service>`
      ├── 查看日志：`docker compose logs -f <service>`
      └── 如数据库问题：检查磁盘空间、连接数
      ↓
⏱️ T+15min: 启动应急预案
  └── 如果后端崩溃：
      1. `docker compose logs app > /tmp/app_crash.log`
      2. `docker compose restart app`
      3. 确认恢复：`curl http://localhost:8000/health`
      ↓
⏱️ T+30min: 上报并通知
  └── 向管理层和客户（如有 SLA）通报故障情况
      ↓
⏱️ T+2h: 完成故障报告（RCA）
  └── 记录：故障时间线、根因、处置过程、改进措施
```

### 5.3 常见故障处理 / Common故障 Handling

**故障：后端 API 返回 500 错误 / Backend API 500 Errors**

```bash
# 1. 查看后端错误日志
docker compose logs app --tail=100 | grep -E "ERROR|Exception|Traceback"

# 2. 检查数据库连接
docker compose exec app python -c \
  "from app.core.db import engine; engine.connect()" 2>&1

# 3. 重启后端
docker compose restart app

# 4. 如果持续 500，查看完整错误日志
docker compose logs app --tail=500 > /tmp/app_full.log
```

**故障：扫描任务全部失败 / All Scan Jobs Failing**

```bash
# 1. 检查最近一次扫描的错误详情
docker compose logs app --tail=200 | grep -i "scan.*error"

# 2. 手动测试 SSH 连接
ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no \
  user@target_ip "echo ok" 2>&1

# 3. 检查凭据是否过期
curl -s http://localhost:8000/api/v1/credentials | jq \
  '.data.items[] | {id, type, last_used_at}'

# 4. 批量重试失败的扫描任务
curl -X POST http://localhost:8000/api/v1/scans/batch-retry \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"status": "failed"}'
```

---

## 6. 灾难恢复计划 / Disaster Recovery Plan

### 6.1 RTO / RPO 目标 / Recovery Objectives

| 目标 / Objective | 定义 / Definition | 目标值 / Target |
|----------------|------------------|----------------|
| RTO（恢复时间目标）| 系统中断到恢复的时间 | < 30 分钟 |
| RPO（恢复点目标）| 最大可接受数据丢失量 | < 5 分钟（WAL）|

### 6.2 灾难恢复步骤 / Disaster Recovery Steps

**Step 1: 确认灾难范围 / Confirm Disaster Scope**
```bash
# 检查哪些组件受影响
docker compose ps
curl http://localhost:8000/health
```

**Step 2: 数据库灾难恢复 / Database DR**
```bash
# 如果主库不可用，切换到备库
# 1. 停止主库写入
docker compose stop app

# 2. 从备库拉取最新备份（如果有）
aws s3 cp s3://your-bucket/telos-backups/latest/ /tmp/backup/ --recursive

# 3. 在备库恢复
gunzip < /tmp/backup/latest.sql.gz | docker compose exec -T db psql -U accountscan

# 4. 更新连接字符串，切换到备库
# 5. 重启应用
docker compose restart app
```

**Step 3: 全量服务恢复 / Full Service Recovery**
```bash
# 完整重建所有服务
cd /opt/accountscan
docker compose down
docker compose up -d
sleep 60  # 等待服务就绪
docker compose ps
curl http://localhost:8000/health
```

---

## 7. 容量规划 / Capacity Planning

### 7.1 资源需求估算 / Resource Estimation

| 规模 / Scale | 服务器数 / Servers | 账号规模 / Accounts | CPU | 内存 / Memory | 磁盘 / Disk |
|------------|----------------|----------------|---|---|------------|
| 小规模 / Small | < 100 | < 5,000 | 4 核 | 8 GB | 100 GB |
| 中规模 / Medium | 100-1,000 | 5,000-50,000 | 8 核 | 16 GB | 200 GB |
| 大规模 / Large | 1,000-5,000 | 50,000-200,000 | 16 核 | 32 GB | 500 GB |
| 超大规模 / X-Large | 5,000+ | 200,000+ | 32+ 核 | 64 GB | 1 TB+ |

### 7.2 扩容步骤 / Scaling Steps

**垂直扩容 / Vertical Scaling（推荐优先）:**
```bash
# 增加资源（Docker Desktop / 虚拟机）
# 1. 停止服务
docker compose down

# 2. 增加 CPU/内存配置
# 编辑 docker-compose.yml 中的资源限制

# 3. 重启服务
docker compose up -d

# 4. 验证
docker stats
```

**水平扩容 / Horizontal Scaling（大规模）:**
```bash
# 添加更多扫描节点
# 1. 部署新的扫描节点服务器
# 2. 配置 Redis 队列共享
# 3. 配置 Nginx 负载均衡

# Go 分析引擎扩容（每个实例处理独立扫描队列）
# Go 引擎通过 systemd 管理（监听 0.0.0.0:8082），水平扩容需部署多个实例
# 并配置 Nginx upstream:
# upstream go_engine { server 10.0.1.10:8082; server 10.0.1.11:8082; }
```

---

*Telos v2.0 | © 2026 Telos.*
