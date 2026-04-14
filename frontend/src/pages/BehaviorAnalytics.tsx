import { useState, useEffect } from 'react'
import {
  Table, Tag, Space, Button, Typography, Card, Row, Col, Statistic,
  Select, message, Timeline, Tooltip, Spin, Divider
} from 'antd'
import {
  BellOutlined, ThunderboltOutlined, UserOutlined,
  ArrowUpOutlined, ArrowDownOutlined, WarningOutlined,
  ExclamationCircleOutlined, CheckCircleOutlined
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { useTranslation } from 'react-i18next'
import api from '../api/client'

const { Title, Text } = Typography

const SEVERITY_COLOR: Record<string, string> = {
  critical: 'red',
  high: 'orange',
  medium: 'gold',
  low: 'green',
}

const SEVERITY_ICON: Record<string, React.ReactNode> = {
  critical: <ExclamationCircleOutlined />,
  high: <WarningOutlined />,
  medium: <ArrowDownOutlined />,
  low: <ArrowUpOutlined />,
}

const EVENT_TYPE_COLOR: Record<string, string> = {
  dormant_to_active: 'blue',
  went_dormant: 'gold',
  new_privileged_account: 'orange',
  privileged_no_login: 'purple',
  privilege_escalation: 'red',
  cross_asset_awakening: 'magenta',
}

interface BehaviorEvent {
  id: number
  event_type: string
  severity: string
  username: string
  asset_code: string | null
  asset_ip: string | null
  description: string | null
  description_key: string | null
  description_params: Record<string, any> | null
  snapshot_id: number | null
  detected_at: string
}

interface EventTypeInfo {
  type: string
  label_zh: string
  label_en: string
  severity: string
  description_zh: string
  description_en: string
}

const EVENT_TYPE_LABELS = (t: (k: string) => string): Record<string, { zh: string; en: string }> => ({
  dormant_to_active: { zh: t('ueba.eventDormantToActive'), en: 'Reactivated' },
  went_dormant: { zh: t('ueba.eventWentDormant'), en: 'Went Dormant' },
  new_privileged_account: { zh: t('ueba.eventNewPrivileged'), en: 'New Privileged' },
  privileged_no_login: { zh: t('ueba.eventPrivilegeNoLogin'), en: 'Never Logged In' },
  privilege_escalation: { zh: t('ueba.eventPrivilegeEscalation'), en: 'Privilege Escalation' },
  cross_asset_awakening: { zh: t('ueba.eventCrossAssetActive'), en: 'Cross-Asset Active' },
})

export default function BehaviorAnalytics() {
  const { t, i18n } = useTranslation()
  const isZh = i18n.language.startsWith('zh')

  const [summary, setSummary] = useState<any>(null)
  const [events, setEvents] = useState<BehaviorEvent[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [detecting, setDetecting] = useState(false)
  const [page, setPage] = useState(1)
  const [severity, setSeverity] = useState<string>('all')
  const [eventType, setEventType] = useState<string>('all')
  const [days, setDays] = useState(7)
  const pageSize = 20

  const fetchSummary = async () => {
    try {
      const r = await api.get('/ueba/summary')
      setSummary(r.data)
    } catch { /* ignore */ }
  }

  const fetchEvents = async () => {
    setLoading(true)
    try {
      const params: Record<string, any> = { days, limit: pageSize, offset: (page - 1) * pageSize }
      if (severity !== 'all') params.severity = severity
      if (eventType !== 'all') params.event_type = eventType
      const r = await api.get('/ueba/events', { params })
      setEvents(r.data.events || [])
      setTotal(r.data.total || 0)
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.error'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchSummary() }, [])
  useEffect(() => { fetchEvents() }, [page, severity, eventType, days])

  const handleDetect = async () => {
    setDetecting(true)
    try {
      const r = await api.post('/ueba/detect')
      message.success(t('ueba.detectSuccessCount', { count: r.data.detected }))
      fetchSummary()
      fetchEvents()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.error'))
    } finally {
      setDetecting(false)
    }
  }

  const columns: ColumnsType<BehaviorEvent> = [
    {
      title: t('ueba.severity'),
      dataIndex: 'severity',
      key: 'severity',
      width: 100,
      render: (sev: string) => (
        <Space>
          <Tag color={SEVERITY_COLOR[sev] || 'default'} icon={SEVERITY_ICON[sev]}>
            {t(`risk.${sev}`, sev)}
          </Tag>
        </Space>
      ),
    },
    {
      title: t('ueba.eventType'),
      dataIndex: 'event_type',
      key: 'event_type',
      width: 140,
      render: (type: string) => {
        const labels = EVENT_TYPE_LABELS(t)[type] || { zh: type, en: type }
        return (
          <Tag color={EVENT_TYPE_COLOR[type] || 'default'}>
            {isZh ? labels.zh : labels.en}
          </Tag>
        )
      },
    },
    {
      title: t('table.username'),
      dataIndex: 'username',
      key: 'username',
      width: 140,
      render: (v: string) => <Text strong>{v}</Text>,
    },
    {
      title: t('table.asset'),
      key: 'asset',
      width: 160,
      render: (_, rec) => (
        <Space direction="vertical" size={0}>
          <Text style={{ fontSize: 13 }}>{rec.asset_code || '-'}</Text>
          <Text type="secondary" style={{ fontSize: 11 }}>{rec.asset_ip || ''}</Text>
        </Space>
      ),
    },
    {
      title: t('ueba.description'),
      dataIndex: 'description',
      key: 'description',
      render: (v: string | null, rec: BehaviorEvent) => {
        // New events: description_key + params → fully translated
        if (rec.description_key && rec.description_params) {
          return <Text style={{ fontSize: 13 }}>
            {t(rec.description_key, { id: rec.id, ...rec.description_params })}
          </Text>
        }
        // Old events (backfilled): no params available, use raw description
        return <Text style={{ fontSize: 13 }}>{v || '-'}</Text>
      },
    },
    {
      title: t('table.detectedAt'),
      dataIndex: 'detected_at',
      key: 'detected_at',
      width: 150,
      render: (v: string) => new Date(v).toLocaleString(isZh ? 'zh-CN' : 'en-US'),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>{t('nav.ueba')}</Title>
        <Tooltip title={t('ueba.detectTip')}>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            onClick={handleDetect}
            loading={detecting}
          >
            {t('btn.detectAnomalies')}
          </Button>
        </Tooltip>
      </div>

      {/* Summary Cards */}
      {summary ? (
        <Row gutter={12} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Card bodyStyle={{ padding: '12px 16px' }}>
              <Statistic
                title={t('ueba.activeAccounts')}
                value={summary.active_accounts}
                prefix={<UserOutlined />}
                valueStyle={{ fontSize: 22 }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card bodyStyle={{ padding: '12px 16px' }}>
              <Statistic
                title={t('ueba.dormantAccounts')}
                value={summary.dormant_accounts}
                valueStyle={{ fontSize: 22, color: '#fa8c16' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card bodyStyle={{ padding: '12px 16px' }}>
              <Statistic
                title={t('ueba.recentAnomalies')}
                value={summary.recent_anomaly_count}
                prefix={<BellOutlined />}
                valueStyle={{ fontSize: 22, color: '#ff4d4f' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card bodyStyle={{ padding: '12px 16px' }}>
              <Statistic
                title={t('ueba.criticalEvents')}
                value={summary.critical_anomaly_count}
                prefix={<ExclamationCircleOutlined />}
                valueStyle={{ fontSize: 22, color: '#cf1322' }}
              />
            </Card>
          </Col>
        </Row>
      ) : (
        <div style={{ textAlign: 'center', padding: 20 }}><Spin /></div>
      )}

      {/* Timeline of Recent Events */}
      {summary && summary.recent_events && summary.recent_events.length > 0 && (
        <Card
          title={t('ueba.recentTimeline')}
          bodyStyle={{ padding: '12px 24px' }}
          style={{ marginBottom: 16 }}
          size="small"
        >
          <Timeline
            items={summary.recent_events.slice(0, 8).map((e: BehaviorEvent) => {
              const labels = EVENT_TYPE_LABELS(t)[e.event_type] || { zh: e.event_type, en: e.event_type }
              return {
                color: SEVERITY_COLOR[e.severity] || 'blue',
                children: (
                  <Space size={4} wrap>
                    <Tag color={SEVERITY_COLOR[e.severity]} style={{ fontSize: 11 }}>
                      {t(`risk.${e.severity}`, e.severity)}
                    </Tag>
                    <Tag color={EVENT_TYPE_COLOR[e.event_type]} style={{ fontSize: 11 }}>
                      {isZh ? labels.zh : labels.en}
                    </Tag>
                    <Text style={{ fontSize: 13 }} strong>{e.username}</Text>
                    {e.asset_code && <Text type="secondary" style={{ fontSize: 12 }}>@{e.asset_code}</Text>}
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {new Date(e.detected_at).toLocaleDateString(isZh ? 'zh-CN' : 'en-US')}
                    </Text>
                  </Space>
                ),
              }
            })}
          />
        </Card>
      )}

      {/* Event Type Legend */}
      <Card
        title={t('ueba.eventTypes')}
        bodyStyle={{ padding: '12px 16px' }}
        style={{ marginBottom: 16 }}
        size="small"
      >
        <Row gutter={[12, 8]}>
          {Object.entries(EVENT_TYPE_LABELS(t)).map(([type, labels]) => (
            <Col span={8} key={type}>
              <Space size={4}>
                <Tag color={EVENT_TYPE_COLOR[type] || 'default'}>{isZh ? labels.zh : labels.en}</Tag>
                <Text type="secondary" style={{ fontSize: 12 }}>{type}</Text>
              </Space>
            </Col>
          ))}
        </Row>
      </Card>

      {/* Filters */}
      <Card bodyStyle={{ padding: '12px 16px', marginBottom: 12 }} size="small">
        <Space size={16} wrap>
          <Space>
            <Text type="secondary">{t('filter.timeRange')}:</Text>
            <Select value={days} onChange={v => { setDays(v); setPage(1) }} style={{ width: 100 }}>
              <Select.Option value={7}>7 {t('unit.days')}</Select.Option>
              <Select.Option value={14}>14 {t('unit.days')}</Select.Option>
              <Select.Option value={30}>30 {t('unit.days')}</Select.Option>
              <Select.Option value={90}>90 {t('unit.days')}</Select.Option>
            </Select>
          </Space>
          <Space>
            <Text type="secondary">{t('filter.severity')}:</Text>
            <Select value={severity} onChange={v => { setSeverity(v); setPage(1) }} style={{ width: 100 }}>
              <Select.Option value="all">{t('filter.all')}</Select.Option>
              <Select.Option value="critical">{t('risk.critical')}</Select.Option>
              <Select.Option value="high">{t('risk.high')}</Select.Option>
              <Select.Option value="medium">{t('risk.medium')}</Select.Option>
              <Select.Option value="low">{t('risk.low')}</Select.Option>
            </Select>
          </Space>
          <Space>
            <Text type="secondary">{t('filter.eventType')}:</Text>
            <Select value={eventType} onChange={v => { setEventType(v); setPage(1) }} style={{ width: 160 }}>
              <Select.Option value="all">{t('filter.all')}</Select.Option>
              {Object.entries(EVENT_TYPE_LABELS(t)).map(([type, labels]) => (
                <Select.Option key={type} value={type}>{isZh ? labels.zh : labels.en}</Select.Option>
              ))}
            </Select>
          </Space>
        </Space>
      </Card>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
      ) : (
        <Table
          columns={columns}
          dataSource={events}
          rowKey="id"
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: false,
            showTotal: (tot, range) => `${range[0]}-${range[1]} / ${tot}`,
            onChange: (p) => setPage(p),
          }}
          size="small"
        />
      )}
    </div>
  )
}
