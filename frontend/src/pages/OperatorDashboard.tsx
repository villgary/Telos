import { useState, useEffect } from 'react'
import {
  Card, Typography, Row, Col, Button, Space, Tag, Badge,
  List, message, Progress, Statistic, Alert, Empty, Tooltip,
  Popconfirm
} from 'antd'
import {
  ThunderboltOutlined, WarningOutlined, CheckCircleOutlined,
  CloseCircleOutlined, EyeOutlined, ReloadOutlined,
  BarChartOutlined, BellOutlined, ScanOutlined
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import api from '../api/client'
import { acknowledgeAlert, dismissAlert, respondToAlert } from '../api/client'

const { Title, Text, Paragraph } = Typography

interface AlertItem {
  id: number
  level: string
  title: string
  message: string
  asset_id: number
  status: string
  is_read: boolean
  created_at: string
}

interface ScanJob {
  id: number
  name: string
  status: string
  progress: number
  created_at: string
}

const LEVEL_COLOR: Record<string, string> = {
  critical: 'red',
  warning: 'orange',
  info: 'blue',
}

const STATUS_TAG: Record<string, { color: string; icon: React.ReactNode }> = {
  new:         { color: 'blue',    icon: <BellOutlined /> },
  acknowledged: { color: 'orange', icon: <EyeOutlined /> },
  dismissed:   { color: 'default', icon: <CloseCircleOutlined /> },
  responded:   { color: 'green',   icon: <CheckCircleOutlined /> },
}

export default function OperatorDashboard() {
  const { t, i18n } = useTranslation()
  const isZh = i18n.language.startsWith('zh')
  const navigate = useNavigate()

  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState<number | null>(null)
  const [stats, setStats] = useState({ critical: 0, warning: 0, info: 0, total: 0 })
  const [recentScans, setRecentScans] = useState<ScanJob[]>([])

  const fetchAlerts = async () => {
    setLoading(true)
    try {
      const r = await api.get('/alerts', { params: { is_read: false, limit: 30 } })
      const items: AlertItem[] = r.data.alerts || []
      setAlerts(items)
      setStats({
        critical: items.filter(a => a.level === 'critical').length,
        warning: items.filter(a => a.level === 'warning').length,
        info: items.filter(a => a.level === 'info').length,
        total: items.length,
      })
    } catch {
      message.error(t('msg.error'))
    } finally {
      setLoading(false)
    }
  }

  const fetchScans = async () => {
    try {
      const r = await api.get('/scan-jobs', { params: { limit: 5 } })
      const jobs = (r.data.items || r.data.data || []).filter(
        (j: ScanJob) => j.status === 'running' || j.status === 'pending'
      )
      setRecentScans(jobs)
    } catch { /* ignore */ }
  }

  useEffect(() => {
    fetchAlerts()
    fetchScans()
  }, [])

  const handleAction = async (alert: AlertItem, action: 'acknowledge' | 'dismiss' | 'respond') => {
    setActionLoading(alert.id)
    try {
      if (action === 'acknowledge') {
        await acknowledgeAlert(alert.id)
        message.success(t('alert.acknowledged'))
      } else if (action === 'dismiss') {
        await dismissAlert(alert.id)
        message.success(t('alert.dismissed'))
      } else {
        await respondToAlert(alert.id)
        message.success(t('alert.responded'))
      }
      setAlerts(prev => prev.filter(a => a.id !== alert.id))
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.error'))
    } finally {
      setActionLoading(null)
    }
  }

  const urgentAlerts = alerts.filter(a => a.level === 'critical')
  const warningAlerts = alerts.filter(a => a.level === 'warning')
  const infoAlerts = alerts.filter(a => a.level === 'info')

  const renderAlertCard = (alert: AlertItem) => {
    const cfg = LEVEL_COLOR[alert.level] || 'default'
    const statusCfg = STATUS_TAG[alert.status] || STATUS_TAG.new
    return (
      <Card
        key={alert.id}
        size="small"
        bodyStyle={{ padding: 12 }}
        style={{
          marginBottom: 8,
          borderLeft: `4px solid ${cfg}`,
          background: alert.is_read ? '#fafafa' : '#fff',
        }}
      >
        <Space direction="vertical" size={4} style={{ width: '100%' }}>
          <Space style={{ width: '100%', justifyContent: 'space-between' }}>
            <Space size={4}>
              <Tag color={cfg} icon={<WarningOutlined />}>{t(`alert.${alert.level}`, alert.level)}</Tag>
              <Text strong style={{ fontSize: 13 }}>{alert.title}</Text>
            </Space>
            <Space size={4}>
              <Tag color={statusCfg.color} icon={statusCfg.icon}>
                {t(`alert.status.${alert.status}`, alert.status)}
              </Tag>
            </Space>
          </Space>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {t('operator.assetNumAlert', {
              asset_id: alert.asset_id,
              date: new Date(alert.created_at).toLocaleString(isZh ? 'zh-CN' : 'en-US'),
            })}
          </Text>
          {alert.message && (
            <Paragraph type="secondary" style={{ fontSize: 12 }} ellipsis={{ rows: 2 }}>
              {alert.message}
            </Paragraph>
          )}
          <Space size={4}>
            <Tooltip title={t('btn.acknowledge')}>
              <Button
                size="small"
                icon={<EyeOutlined />}
                onClick={() => handleAction(alert, 'acknowledge')}
                loading={actionLoading === alert.id}
              >
                {t('btn.acknowledge')}
              </Button>
            </Tooltip>
            <Tooltip title={t('btn.dismiss')}>
              <Button
                size="small"
                danger
                icon={<CloseCircleOutlined />}
                onClick={() => handleAction(alert, 'dismiss')}
                loading={actionLoading === alert.id}
              >
                {t('btn.dismiss')}
              </Button>
            </Tooltip>
            <Tooltip title={t('btn.respond')}>
              <Button
                size="small"
                type="primary"
                icon={<ThunderboltOutlined />}
                onClick={() => handleAction(alert, 'respond')}
                loading={actionLoading === alert.id}
              >
                {t('btn.respond')}
              </Button>
            </Tooltip>
            <Button size="small" onClick={() => navigate(`/assets?highlight=${alert.asset_id}`)}>
              {t('kb.viewAsset')}
            </Button>
          </Space>
        </Space>
      </Card>
    )
  }

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          <ThunderboltOutlined style={{ color: '#1890ff' }} />
          {' '}{t('operator.title')}
        </Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchAlerts} loading={loading}>
            {t('btn.refresh')}
          </Button>
          <Button icon={<BarChartOutlined />} onClick={() => navigate('/')}>
            {t('operator.fullDashboard')}
          </Button>
        </Space>
      </div>

      {/* Stats row */}
      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small" bodyStyle={{ padding: 12 }}>
            <Statistic
              title={t('alert.critical')}
              value={stats.critical}
              valueStyle={{ color: '#ff4d4f' }}
              prefix={<WarningOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" bodyStyle={{ padding: 12 }}>
            <Statistic
              title={t('alert.warning')}
              value={stats.warning}
              valueStyle={{ color: '#fa8c16' }}
              prefix={<WarningOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" bodyStyle={{ padding: 12 }}>
            <Statistic
              title={t('alert.info')}
              value={stats.info}
              valueStyle={{ color: '#1890ff' }}
              prefix={<BellOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small" bodyStyle={{ padding: 12 }}>
            <Statistic
              title={t('operator.pendingActions')}
              value={stats.total}
              suffix={stats.total > 0 ? <Badge status="error" /> : null}
            />
          </Card>
        </Col>
      </Row>

      {/* Running scans */}
      {recentScans.length > 0 && (
        <Card
          title={<Space><ScanOutlined />{t('operator.runningScans')}</Space>}
          size="small"
          style={{ marginBottom: 16 }}
          bodyStyle={{ padding: '12px 16px' }}
        >
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
            {recentScans.map(scan => (
              <Row key={scan.id} align="middle">
                <Col span={12}>
                  <Text style={{ fontSize: 13 }}>{scan.name}</Text>
                  <Tag style={{ marginLeft: 8 }}>{scan.status}</Tag>
                </Col>
                <Col span={12}>
                  {scan.status === 'running' && scan.progress != null && (
                    <Progress percent={scan.progress} size="small" />
                  )}
                </Col>
              </Row>
            ))}
          </Space>
        </Card>
      )}

      {/* Alerts */}
      <Row gutter={16}>
        <Col span={8}>
          <Card
            title={
              <Space>
                <Badge status="error" />
                {t('operator.criticalAlerts')} ({urgentAlerts.length})
              </Space>
            }
            size="small"
            bodyStyle={{ padding: 8, maxHeight: 600, overflow: 'auto' }}
          >
            {urgentAlerts.length === 0 ? (
              <Empty description={t('operator.noCritical')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              urgentAlerts.map(renderAlertCard)
            )}
          </Card>
        </Col>
        <Col span={8}>
          <Card
            title={
              <Space>
                <Badge status="warning" />
                {t('operator.warningAlerts')} ({warningAlerts.length})
              </Space>
            }
            size="small"
            bodyStyle={{ padding: 8, maxHeight: 600, overflow: 'auto' }}
          >
            {warningAlerts.length === 0 ? (
              <Empty description={t('operator.noWarning')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              warningAlerts.map(renderAlertCard)
            )}
          </Card>
        </Col>
        <Col span={8}>
          <Card
            title={
              <Space>
                <Badge status="processing" />
                {t('operator.infoAlerts')} ({infoAlerts.length})
              </Space>
            }
            size="small"
            bodyStyle={{ padding: 8, maxHeight: 600, overflow: 'auto' }}
          >
            {infoAlerts.length === 0 ? (
              <Empty description={t('operator.noInfo')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              infoAlerts.map(renderAlertCard)
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
