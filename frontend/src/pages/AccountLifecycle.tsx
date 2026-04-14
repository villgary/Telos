import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Row, Col, Card, Typography, Tag, Space, Spin, Button,
  Input, Table, Badge, message, Modal, Form, InputNumber,
  Select, Tooltip,
} from 'antd'
import {
  ReloadOutlined, SettingOutlined, SearchOutlined,
  ClockCircleOutlined, WarningOutlined, CheckCircleOutlined,
  MinusCircleOutlined, QuestionCircleOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import {
  getLifecycleDashboard, listLifecycleStatuses,
  triggerLifecycleCompute, getLifecycleConfig, updateLifecycleConfig,
} from '../api/client'

const { Title, Text } = Typography
const { Option } = Select

const STATUS_COLOR: Record<string, string> = {
  active: 'green',
  dormant: 'orange',
  departed: 'red',
  unknown: 'default',
}

const getStatusLabel = (t: (key: string, opts?: any) => string) => ({
  active: t('status.active'),
  dormant: t('status.dormant'),
  departed: t('status.departed'),
  unknown: t('status.unknown'),
})

const STATUS_ICON: Record<string, React.ReactNode> = {
  active: <CheckCircleOutlined />,
  dormant: <ClockCircleOutlined />,
  departed: <WarningOutlined />,
  unknown: <MinusCircleOutlined />,
}

interface LifecycleStatus {
  snapshot_id: number
  asset_id: number
  asset_code: string
  ip: string
  hostname?: string
  username: string
  uid_sid: string
  is_admin: boolean
  lifecycle_status: string
  previous_status?: string
  last_login?: string
  changed_at?: string
  category: string
}

export default function AccountLifecycle() {
  const { t } = useTranslation()
  const STATUS_LABEL = getStatusLabel(t)
  const [loading, setLoading] = useState(true)
  const [dashboard, setDashboard] = useState<{
    total: number; active: number; dormant: number;
    departed: number; unknown: number;
    threshold_active: number; threshold_dormant: number;
  } | null>(null)
  const [statuses, setStatuses] = useState<LifecycleStatus[]>([])
  const [total, setTotal] = useState(0)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [search, setSearch] = useState('')
  const [computing, setComputing] = useState(false)
  const [configOpen, setConfigOpen] = useState(false)
  const [config, setConfig] = useState({ active_days: 30, dormant_days: 90, auto_alert: true })
  const [savingConfig, setSavingConfig] = useState(false)

  const fetchDashboard = () => {
    getLifecycleDashboard().then(r => setDashboard(r.data)).catch(() => {})
  }

  const fetchStatuses = (page = 1) => {
    setLoading(true)
    listLifecycleStatuses({
      status: statusFilter || undefined,
      search: search || undefined,
      limit: 50,
      offset: (page - 1) * 50,
    }).then(r => {
      setStatuses(r.data.statuses || [])
      setTotal(r.data.total || 0)
    }).catch(() => message.error(t('msg.loadFailed')))
    .finally(() => setLoading(false))
  }

  useEffect(() => { fetchDashboard() }, [])
  useEffect(() => { fetchStatuses() }, [statusFilter, search])

  const handleCompute = async () => {
    setComputing(true)
    try {
      const r = await triggerLifecycleCompute()
      message.success(`${t('lifecycle.computeComplete')} ${r.data.active} / ${r.data.dormant} / ${r.data.departed}`)
      fetchDashboard()
      fetchStatuses()
    } catch { message.error(t('msg.computeFailed')) }
    finally { setComputing(false) }
  }

  const openConfig = () => {
    setConfigOpen(true)
    getLifecycleConfig('global').then(r => {
      setConfig({
        active_days: r.data.active_days,
        dormant_days: r.data.dormant_days,
        auto_alert: r.data.auto_alert,
      })
    }).catch(() => {})
  }

  const handleSaveConfig = async () => {
    setSavingConfig(true)
    try {
      await updateLifecycleConfig(config)
      message.success(t('lifecycle.configSaved'))
      setConfigOpen(false)
      fetchDashboard()
    } catch { message.error(t('msg.saveFailed')) }
    finally { setSavingConfig(false) }
  }

  const columns: ColumnsType<LifecycleStatus> = [
    {
      title: t('table.status'),
      dataIndex: 'lifecycle_status',
      width: 100,
      render: (s: string) => (
        <Tag color={STATUS_COLOR[s]} icon={STATUS_ICON[s]} style={{ fontSize: 12 }}>
          {(STATUS_LABEL as Record<string, string>)[s] || s}
        </Tag>
      ),
      filters: [
        { text: t('status.active'), value: 'active' },
        { text: t('status.dormant'), value: 'dormant' },
        { text: t('status.departed'), value: 'departed' },
        { text: t('status.unknown'), value: 'unknown' },
      ],
      onFilter: (value, record) => record.lifecycle_status === value,
    },
    {
      title: t('lifecycle.account'),
      key: 'account',
      width: 200,
      render: (_: unknown, r: LifecycleStatus) => (
        <Space size={2}>
          {r.is_admin && <Tag color="red" style={{ fontSize: 10 }}>Admin</Tag>}
          <Text strong style={{ fontSize: 13 }}>{r.username}</Text>
          <Text type="secondary" style={{ fontSize: 11 }}>(uid={r.uid_sid})</Text>
        </Space>
      ),
    },
    {
      title: t('table.asset'),
      key: 'asset',
      width: 160,
      render: (_: unknown, r: LifecycleStatus) => (
        <Space size={2} wrap>
          <Tag color="blue" style={{ fontSize: 11 }}>{r.asset_code}</Tag>
          <Text type="secondary" style={{ fontSize: 12 }}>{r.ip}</Text>
        </Space>
      ),
    },
    {
      title: t('table.lastLogin'),
      dataIndex: 'last_login',
      width: 140,
      render: (v?: string) => v ? (
        <Text type="secondary" style={{ fontSize: 12 }}>
          {new Date(v).toLocaleDateString('zh-CN')}
        </Text>
      ) : (
        <Text type="secondary" style={{ fontSize: 12 }}>{t('lifecycle.neverLoggedIn')}</Text>
      ),
      sorter: (a, b) => {
        const ta = a.last_login ? new Date(a.last_login).getTime() : 0
        const tb = b.last_login ? new Date(b.last_login).getTime() : 0
        return ta - tb
      },
      defaultSortOrder: 'ascend',
    },
    {
      title: t('lifecycle.statusChange'),
      key: 'changed',
      width: 160,
      render: (_: unknown, r: LifecycleStatus) => {
        if (!r.changed_at) return <Text type="secondary" style={{ fontSize: 12 }}>—</Text>
        const changed = new Date(r.changed_at)
        const prev = r.previous_status ? (STATUS_LABEL as Record<string, string>)[r.previous_status] : '?'
        const curr = (STATUS_LABEL as Record<string, string>)[r.lifecycle_status] || r.lifecycle_status
        return (
          <Text type="secondary" style={{ fontSize: 12 }}>
            {changed.toLocaleDateString('zh-CN')}: {prev} → {curr}
          </Text>
        )
      },
    },
  ]

  const statCards = [
    { key: 'active', label: t('status.active'), icon: <CheckCircleOutlined />, color: '#52c41a', desc: `<=${dashboard?.threshold_active || 30}${t('lifecycle.days')}` },
    { key: 'dormant', label: t('status.dormant'), icon: <ClockCircleOutlined />, color: '#faad14', desc: `${dashboard?.threshold_active || 30}~${dashboard?.threshold_dormant || 90}${t('lifecycle.days')}` },
    { key: 'departed', label: t('status.departed'), icon: <WarningOutlined />, color: '#ff4d4f', desc: `>${dashboard?.threshold_dormant || 90}${t('lifecycle.days')}` },
    { key: 'unknown', label: t('status.unknown'), icon: <QuestionCircleOutlined />, color: '#999', desc: t('lifecycle.neverLoggedIn') },
  ]

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>
            <ClockCircleOutlined style={{ marginRight: 8 }} />
            {t('lifecycle.title')}
          </Title>
          <Text type="secondary">{t('lifecycle.subtitle')}</Text>
        </div>
        <Space>
          <Tooltip title={t('lifecycle.configTip')}>
            <Button icon={<SettingOutlined />} onClick={openConfig}>{t('lifecycle.configThreshold')}</Button>
          </Tooltip>
          <Button icon={<ReloadOutlined spin={computing} />} onClick={handleCompute} loading={computing}>
            {t('lifecycle.recompute')}
          </Button>
          <Button onClick={() => { fetchDashboard(); fetchStatuses() }}>{t('btn.refresh')}</Button>
        </Space>
      </div>

      {/* Stat cards */}
      {dashboard && (
        <Row gutter={[12, 12]} style={{ marginBottom: 20 }}>
          {statCards.map(({ key, label, icon, color, desc }) => {
            const count = dashboard[key as keyof typeof dashboard] as number
            return (
              <Col xs={12} sm={12} md={6} key={key}>
                <Card
                  bodyStyle={{ padding: '16px', textAlign: 'center' }}
                  style={{ borderTop: `3px solid ${color}` }}
                >
                  <div style={{ color, fontSize: 28, marginBottom: 4 }}>{icon}</div>
                  <div style={{ fontSize: 32, fontWeight: 700, color }}>{count}</div>
                  <div style={{ fontSize: 14, fontWeight: 600 }}>{label}</div>
                  <Text type="secondary" style={{ fontSize: 12 }}>{desc}</Text>
                </Card>
              </Col>
            )
          })}
        </Row>
      )}

      {/* Filter bar */}
      <div style={{ marginBottom: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
        <Text type="secondary" style={{ fontSize: 12 }}>{t('table.status')}: </Text>
        <Select value={statusFilter} onChange={v => { setStatusFilter(v); setStatusFilter(v) }} style={{ width: 120 }} allowClear placeholder={t('filter.all')}>
          <Option value="active">{t('status.active')}</Option>
          <Option value="dormant">{t('status.dormant')}</Option>
          <Option value="departed">{t('status.departed')}</Option>
          <Option value="unknown">{t('status.unknown')}</Option>
        </Select>
        <Input
          placeholder={t('lifecycle.searchPlaceholder')}
          prefix={<SearchOutlined />}
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ width: 220 }}
          allowClear
        />
        <Text type="secondary" style={{ fontSize: 12, marginLeft: 'auto' }}>
          {t('lifecycle.totalRecords', { total })}
        </Text>
      </div>

      {/* Table */}
      <Table
        columns={columns}
        dataSource={statuses}
        rowKey="snapshot_id"
        loading={loading}
        pagination={{ total, pageSize: 50, showSizeChanger: false }}
        size="small"
        scroll={{ x: 800 }}
        rowClassName={r => r.lifecycle_status === 'departed' ? 'lifecycle-departed' : ''}
      />

      {/* Config modal */}
      <Modal
        title={<Space><SettingOutlined />{t('lifecycle.config')}</Space>}
        open={configOpen}
        onCancel={() => setConfigOpen(false)}
        onOk={handleSaveConfig}
        okText={t('btn.save')}
        okButtonProps={{ loading: savingConfig }}
        width={420}
      >
        <Form layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label={t('lifecycle.activeDays')} extra={t('lifecycle.activeDaysTip')}>
            <InputNumber
              value={config.active_days}
              onChange={v => setConfig(c => ({ ...c, active_days: v || 30 }))}
              min={1} max={365}
              style={{ width: '100%' }}
            />
          </Form.Item>
          <Form.Item label={t('lifecycle.dormantDays')} extra={t('lifecycle.dormantDaysTip')}>
            <InputNumber
              value={config.dormant_days}
              onChange={v => setConfig(c => ({ ...c, dormant_days: v || 90 }))}
              min={1} max={365}
              style={{ width: '100%' }}
            />
          </Form.Item>
          <Form.Item
            extra={t('lifecycle.autoAlertTip')}
          >
            <Select
              value={config.auto_alert ? 'yes' : 'no'}
              onChange={v => setConfig(c => ({ ...c, auto_alert: v === 'yes' }))}
              style={{ width: '100%' }}
            >
              <Option value="yes">{t('lifecycle.enableAutoAlert')}</Option>
              <Option value="no">{t('lifecycle.disableAutoAlert')}</Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      <style>{`
        .lifecycle-departed td { background: #fff5f5 !important; }
      `}</style>
    </div>
  )
}
