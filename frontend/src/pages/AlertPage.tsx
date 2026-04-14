import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Table, Tag, Typography, Button, Space, Tabs, Badge, message, Drawer, Tooltip } from 'antd'
import {
  CheckOutlined, BellOutlined, WarningFilled, ExclamationCircleFilled,
  InfoCircleFilled, EyeOutlined, CloseCircleOutlined, ThunderboltOutlined
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import api from '../api/client'
import { acknowledgeAlert, dismissAlert, respondToAlert } from '../api/client'

const { Title, Text } = Typography

interface Alert {
  id: number
  config_id?: number
  asset_id: number
  job_id?: number
  level: string
  title: string
  message: string
  title_key?: string
  title_params?: Record<string, unknown>
  message_key?: string
  message_params?: Record<string, unknown>
  is_read: boolean
  status: string
  created_at: string
}

interface AlertList {
  total: number
  unread_count: number
  alerts: Alert[]
}

export default function AlertPage() {
  const { t } = useTranslation()
  const [data, setData] = useState<AlertList | null>(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<string>('all')
  const [detailAlert, setDetailAlert] = useState<Alert | null>(null)
  const [actionLoading, setActionLoading] = useState<number | null>(null)

  const LEVEL_MAP: Record<string, { color: string; icon: ReactNode; label: string }> = {
    critical: { color: 'red', icon: <WarningFilled />, label: t('alert.critical') },
    warning: { color: 'orange', icon: <ExclamationCircleFilled />, label: t('alert.warning') },
    info: { color: 'blue', icon: <InfoCircleFilled />, label: t('alert.info') },
  }

  const STATUS_MAP: Record<string, { color: string; icon: ReactNode; label: string }> = {
    new:         { color: 'blue',    icon: <BellOutlined />,         label: t('alert.status.new') },
    acknowledged: { color: 'orange', icon: <EyeOutlined />,          label: t('alert.status.acknowledged') },
    dismissed:   { color: 'default', icon: <CloseCircleOutlined />, label: t('alert.status.dismissed') },
    responded:   { color: 'green',  icon: <ThunderboltOutlined />,  label: t('alert.status.responded') },
  }

  const fetchAlerts = () => {
    setLoading(true)
    const params = new URLSearchParams()
    if (tab === 'unread') params.set('is_read', 'false')
    const qs = params.toString() ? `?${params.toString()}` : ''
    api.get(`/alerts${qs}`)
      .then(r => setData(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchAlerts() }, [tab])

  // ── SSE real-time alert stream ──────────────────────────────────────────────
  useEffect(() => {
    let es: EventSource | null = null
    let retryTimer: ReturnType<typeof setTimeout> | null = null

    const connect = () => {
      // Use absolute URL so it works regardless of vite proxy config
      const base = window.location.origin
      es = new EventSource(`${base}/api/v1/alerts/stream`)

      es.onmessage = (event) => {
        try {
          const alert: Alert = JSON.parse(event.data)
          // Prepend new alert to list, update unread count
          setData(prev => {
            if (!prev) return prev
            const alreadyExists = prev.alerts.some(a => a.id === alert.id)
            if (alreadyExists) return prev
            const newAlerts = [alert, ...prev.alerts]
            return {
              ...prev,
              total: prev.total + 1,
              unread_count: alert.is_read ? prev.unread_count : prev.unread_count + 1,
              alerts: newAlerts,
            }
          })
          // Show notification popup
          const levelMeta = LEVEL_MAP[alert.level] || LEVEL_MAP.info
          const notifTitle = alert.title_key ? t(alert.title_key, { id: alert.id, ...(alert.title_params || {}) }) : alert.title
          const notifMsg = alert.message_key ? t(alert.message_key, alert.message_params || {}) : alert.message
          message.open({
            type: 'warning',
            content: (
              <span>
                <strong>{notifTitle}</strong>
                {notifMsg && <br />}
                {notifMsg && <span style={{ fontSize: 12 }}>{notifMsg}</span>}
              </span>
            ),
            duration: 6,
          })
        } catch {
          // ignore parse errors
        }
      }

      es.onerror = () => {
        es?.close()
        es = null
        // Reconnect after 5 seconds
        retryTimer = setTimeout(connect, 5000)
      }
    }

    connect()

    return () => {
      if (retryTimer) clearTimeout(retryTimer)
      if (es) es.close()
    }
  }, [])

  const handleMarkRead = async (id: number) => {
    try {
      await api.post(`/alerts/${id}/read`)
      message.success(t('alert.markedRead'))
      fetchAlerts()
    } catch {
      message.error(t('alert.opFailed'))
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await api.post('/alerts/read-all')
      message.success(t('alert.allRead'))
      fetchAlerts()
    } catch {
      message.error(t('alert.opFailed'))
    }
  }

  const handleAction = async (alert: Alert, action: 'acknowledge' | 'dismiss' | 'respond') => {
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
      fetchAlerts()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('alert.opFailed'))
    } finally {
      setActionLoading(null)
    }
  }

  const columns = [
    {
      title: t('alert.level'),
      dataIndex: 'level',
      key: 'level',
      width: 100,
      render: (v: string) => {
        const cfg = LEVEL_MAP[v] || LEVEL_MAP.info
        return <Tag color={cfg.color} icon={cfg.icon}>{cfg.label}</Tag>
      },
    },
    {
      title: t('alert.alertTitle'),
      dataIndex: 'title',
      key: 'title',
      render: (_: unknown, r: Alert) => {
        const displayTitle = r.title_key ? t(r.title_key, { id: r.id, ...r.title_params }) : r.title
        return (
          <Space>
            {r.status === 'new' && <Badge status="processing" />}
            <Text strong={r.status === 'new'}>{displayTitle}</Text>
          </Space>
        )
      },
    },
    {
      title: t('alert.assetId'),
      dataIndex: 'asset_id',
      key: 'asset_id',
      width: 90,
    },
    {
      title: t('alert.status.label'),
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (v: string) => {
        const cfg = STATUS_MAP[v] || STATUS_MAP.new
        return <Tag color={cfg.color} icon={cfg.icon}>{cfg.label}</Tag>
      },
    },
    {
      title: t('alert.time'),
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (v: string) => new Date(v).toLocaleString('zh-CN'),
    },
    {
      title: t('alert.actions'),
      key: 'actions',
      width: 200,
      render: (_: unknown, r: Alert) => (
        <Space size={4}>
          {r.status === 'new' && (
            <Tooltip title={t('btn.acknowledge')}>
              <Button
                size="small"
                icon={<EyeOutlined />}
                onClick={() => handleAction(r, 'acknowledge')}
                loading={actionLoading === r.id}
              />
            </Tooltip>
          )}
          {r.status !== 'dismissed' && (
            <Tooltip title={t('btn.dismiss')}>
              <Button
                size="small"
                danger
                icon={<CloseCircleOutlined />}
                onClick={() => handleAction(r, 'dismiss')}
                loading={actionLoading === r.id}
              />
            </Tooltip>
          )}
          {r.status !== 'responded' && (
            <Tooltip title={t('btn.respond')}>
              <Button
                size="small"
                type="primary"
                icon={<ThunderboltOutlined />}
                onClick={() => handleAction(r, 'respond')}
                loading={actionLoading === r.id}
              />
            </Tooltip>
          )}
          <Button size="small" onClick={() => setDetailAlert(r)}>
            {t('alert.detail')}
          </Button>
        </Space>
      ),
    },
  ]

  const unreadCount = data?.unread_count ?? 0

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          {t('alert.title')}
          {unreadCount > 0 && (
            <Badge count={unreadCount} style={{ marginLeft: 8 }} />
          )}
        </Title>
        {unreadCount > 0 && (
          <Button icon={<CheckOutlined />} onClick={handleMarkAllRead}>
            {t('alert.markAllRead')}
          </Button>
        )}
      </div>

      <Tabs
        activeKey={tab}
        onChange={setTab}
        items={[
          {
            key: 'all',
            label: (
              <span>{t('alert.all')} {data ? `(${data.total})` : ''}</span>
            ),
          },
          {
            key: 'unread',
            label: (
              <span>
                {t('alert.unread')} <Badge count={unreadCount} size="small" />
              </span>
            ),
          },
        ]}
      />

      <Table
        dataSource={data?.alerts ?? []}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 15 }}
        locale={{ emptyText: <span><BellOutlined style={{ marginRight: 8 }} />{t('alert.noAlerts')}</span> }}
      />

      <Drawer
        title={t('alert.detailTitle')}
        open={!!detailAlert}
        onClose={() => setDetailAlert(null)}
        width={500}
      >
        {detailAlert && (
          <>
            <div style={{ marginBottom: 12 }}>
              {(() => {
                const cfg = LEVEL_MAP[detailAlert.level] || LEVEL_MAP.info
                return <Tag color={cfg.color} icon={cfg.icon} style={{ fontSize: 14 }}>{cfg.label}</Tag>
              })()}
            </div>
            <Title level={5}>
              {detailAlert.title_key
                ? t(detailAlert.title_key, { id: detailAlert.id, ...detailAlert.title_params })
                : detailAlert.title}
            </Title>
            <div style={{ color: '#666', marginBottom: 12 }}>
              {t('alert.assetId')}: {detailAlert.asset_id} &nbsp;|&nbsp;
              {t('alert.jobId')}: {detailAlert.job_id ?? '-'} &nbsp;|&nbsp;
              {t('alert.time')}: {new Date(detailAlert.created_at).toLocaleString('zh-CN')}
            </div>
            <div style={{ marginBottom: 12 }}>
              {(() => {
                const cfg = STATUS_MAP[detailAlert.status] || STATUS_MAP.new
                return <Tag color={cfg.color} icon={cfg.icon}>{cfg.label}</Tag>
              })()}
            </div>
            <pre style={{
              background: '#f5f5f5',
              padding: 16,
              borderRadius: 4,
              whiteSpace: 'pre-wrap',
              fontSize: 13,
              lineHeight: 1.6,
            }}>
              {(() => {
                const base = detailAlert.message_key
                  ? t(detailAlert.message_key, { id: detailAlert.id, ...detailAlert.message_params })
                  : detailAlert.message
                const factor = (detailAlert.message_params?.factor_name ?? detailAlert.message_params?.factor) as string | undefined
                if (!factor) return base
                const prefix = t('risk.factorPrefix', { returnObjects: false }) || ''
                return `${base}${prefix}${factor}`
              })()}
            </pre>
          </>
        )}
      </Drawer>
    </div>
  )
}
