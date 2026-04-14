/**
 * NHI Dashboard — Non-Human Identity intelligence overview.
 * Sprint 1: Discovery + Classification + Risk Overview
 */
import { useEffect, useState } from 'react'
import {
  Row, Col, Card, Typography, Spin, Button, Space, Tag, Table,
  Statistic, message, Badge, Alert, Divider, Tooltip, Modal, Form,
  Input, Select,
} from 'antd'
import {
  RobotOutlined, SyncOutlined, WarningOutlined, KeyOutlined,
  UserOutlined, SafetyOutlined, LockOutlined, ClockCircleOutlined,
  ExclamationCircleOutlined, CheckCircleOutlined,
} from '@ant-design/icons'
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis,
  Tooltip as RechartsTooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import { useTranslation } from 'react-i18next'
import {
  getNHIDashboard, listNHIInventory, syncNHI,
  listNHIAlerts, acknowledgeNHIAlert, resolveNHIAlert,
} from '../api/client'

const { Title, Text, Paragraph } = Typography


// ─── Constants ────────────────────────────────────────────────────────────────

const LEVEL_COLORS: Record<string, string> = {
  critical: '#ff4d4f',
  high: '#fa8c16',
  medium: '#faad14',
  low: '#52c41a',
}

const TYPE_COLORS: Record<string, string> = {
  service: '#7c3aed',
  system: '#6b7280',
  cloud: '#3b82f6',
  workload: '#10b981',
  cicd: '#f59e0b',
  application: '#8b5cf6',
  apikey: '#ec4899',
  unknown: '#9ca3af',
}

const TYPE_LABEL_ZH: Record<string, string> = {
  service: '服务账号',
  system: '系统账号',
  cloud: '云身份',
  workload: 'Workload',
  cicd: 'CI/CD',
  application: '应用',
  apikey: 'API Key',
  unknown: '未知',
}

const LEVEL_LABEL_ZH: Record<string, string> = {
  critical: '严重',
  high: '高危',
  medium: '中危',
  low: '低危',
}

const NHI_TYPE_OPTIONS = [
  { value: 'service', label: '服务账号' },
  { value: 'system', label: '系统账号' },
  { value: 'cloud', label: '云身份' },
  { value: 'workload', label: 'Workload' },
  { value: 'cicd', label: 'CI/CD' },
  { value: 'application', label: '应用账号' },
  { value: 'apikey', label: 'API Key' },
  { value: 'ai_agent', label: 'AI Agent' },
  { value: 'unknown', label: '未知' },
]


// ─── Types ────────────────────────────────────────────────────────────────────

interface NHIDashboard {
  total_nhi: number
  total_human: number
  nhi_ratio: number
  by_type: Record<string, number>
  by_level: Record<string, number>
  critical_count: number
  high_count: number
  no_owner_count: number
  rotation_due_count: number
  has_nopasswd_count: number
  top_risks: NHIIdentity[]
  recent_alerts: NHIAlert[]
}

interface NHIIdentity {
  id: number
  snapshot_id: number | null
  asset_id: number | null
  nhi_type: string
  nhi_level: string
  username: string
  uid_sid: string | null
  hostname: string | null
  ip_address: string | null
  is_admin: boolean
  credential_types: string[]
  has_nopasswd_sudo: boolean
  risk_score: number
  risk_signals: Record<string, unknown>[]
  owner_email: string | null
  owner_name: string | null
  rotation_due_days: number | null
  is_monitored: boolean
  last_seen_at: string | null
}

interface NHIAlert {
  id: number
  nhi_id: number
  alert_type: string
  level: string
  title: string
  message: string | null
  is_read: boolean
  status: string
  created_at: string
  nhi_username: string | null
  nhi_type: string | null
  asset_code: string | null
}


// ─── Components ───────────────────────────────────────────────────────────────

function StatCard({ label, value, icon, color, suffix }: {
  label: string; value: number; icon: React.ReactNode; color: string; suffix?: string
}) {
  return (
    <Card size="small" style={{ textAlign: 'center', borderTop: `3px solid ${color}` }}>
      <div style={{ color, fontSize: 22, marginBottom: 4 }}>{icon}</div>
      <Text type="secondary" style={{ fontSize: 12 }}>{label}</Text>
      <div style={{ fontSize: 28, fontWeight: 700, color }}>
        {value}{suffix && <span style={{ fontSize: 12, fontWeight: 400 }}>{suffix}</span>}
      </div>
    </Card>
  )
}


// ─── Main Component ────────────────────────────────────────────────────────────

export default function NHIDashboard() {
  const { t } = useTranslation()
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [dashboard, setDashboard] = useState<NHIDashboard | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'inventory' | 'alerts'>('overview')
  const [inventory, setInventory] = useState<NHIIdentity[]>([])
  const [invTotal, setInvTotal] = useState(0)
  const [invLoading, setInvLoading] = useState(false)
  const [filterType, setFilterType] = useState<string | undefined>()
  const [filterLevel, setFilterLevel] = useState<string | undefined>()
  const [noOwner, setNoOwner] = useState(false)
  const [alertList, setAlertList] = useState<NHIAlert[]>([])
  const [alertLoading, setAlertLoading] = useState(false)
  const [ownerModal, setOwnerModal] = useState<NHIIdentity | null>(null)
  const [ownerForm] = Form.useForm()

  const loadDashboard = () => {
    setLoading(true)
    getNHIDashboard()
      .then(r => setDashboard(r.data))
      .catch(() => message.error(t('nhi.loadFailed')))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadDashboard()
  }, [])

  const handleSync = async () => {
    setSyncing(true)
    try {
      const r = await syncNHI()
      message.success(t('nhi.syncSuccess', {
        nhi: r.data.nhi_count,
        human: r.data.human_count,
        alerts: r.data.alerts_created,
      }))
      loadDashboard()
    } catch {
      message.error(t('nhi.syncFailed'))
    } finally {
      setSyncing(false)
    }
  }

  const loadInventory = (resetPage = false) => {
    setInvLoading(true)
    listNHIInventory({
      nhi_type: filterType,
      level: filterLevel,
      no_owner: noOwner || undefined,
      limit: 30,
    })
      .then(r => {
        setInventory(r.data.items)
        setInvTotal(r.data.total)
      })
      .catch(() => message.error(t('nhi.loadFailed')))
      .finally(() => setInvLoading(false))
  }

  useEffect(() => {
    if (activeTab === 'inventory') loadInventory()
  }, [activeTab, filterType, filterLevel, noOwner])

  const loadAlerts = () => {
    setAlertLoading(true)
    listNHIAlerts({ limit: 50 })
      .then(r => setAlertList(r.data))
      .catch(() => message.error(t('nhi.loadFailed')))
      .finally(() => setAlertLoading(false))
  }

  useEffect(() => {
    if (activeTab === 'alerts') loadAlerts()
  }, [activeTab])

  const handleAck = async (id: number) => {
    try {
      await acknowledgeNHIAlert(id)
      loadAlerts()
      message.success(t('nhi.ackSuccess'))
    } catch { message.error(t('nhi.loadFailed')) }
  }

  const handleResolve = async (id: number) => {
    try {
      await resolveNHIAlert(id)
      loadAlerts()
      message.success(t('nhi.resolveSuccess'))
    } catch { message.error(t('nhi.loadFailed')) }
  }

  const handleAssignOwner = async (values: { email: string; name?: string }) => {
    if (!ownerModal) return
    try {
      const { assignNhiOwner } = await import('../api/client')
      await assignNhiOwner(ownerModal.id, values.email, values.name)
      message.success(t('nhi.ownerAssigned'))
      setOwnerModal(null)
      loadInventory()
    } catch { message.error(t('nhi.loadFailed')) }
  }

  // ─── Chart data ──────────────────────────────────────────────────────────

  const typeChartData = dashboard
    ? Object.entries(dashboard.by_type).map(([name, value]) => ({
        name: t('nhi.type.' + name) || name,
        value,
        color: TYPE_COLORS[name] || '#9ca3af',
      }))
    : []

  const levelChartData = dashboard
    ? Object.entries(dashboard.by_level).map(([name, value]) => ({
        name: t('nhi.level.' + name) || name,
        value,
        color: LEVEL_COLORS[name] || '#9ca3af',
      }))
    : []

  // Human vs NHI ratio chart
  const ratioData = dashboard
    ? [
        { name: 'NHI', value: dashboard.total_nhi, color: '#7c3aed' },
        { name: 'Human', value: dashboard.total_human, color: '#3b82f6' },
      ]
    : []

  // ─── Inventory columns ──────────────────────────────────────────────────────

  const invColumns = [
    {
      title: t('nhi.username'),
      dataIndex: 'username',
      key: 'username',
      render: (u: string, r: NHIIdentity) => (
        <Space>
          <RobotOutlined style={{ color: '#7c3aed' }} />
          <Text strong>{u}</Text>
          {r.is_admin && <Tag color="purple">admin</Tag>}
        </Space>
      ),
    },
    {
      title: t('nhi.type'),
      dataIndex: 'nhi_type',
      key: 'nhi_type',
      width: 100,
      render: (v: string) => (
        <Tag color={TYPE_COLORS[v] || '#9ca3af'}>
          {t('nhi.type.' + v) || v}
        </Tag>
      ),
    },
    {
      title: t('nhi.level'),
      dataIndex: 'nhi_level',
      key: 'nhi_level',
      width: 80,
      render: (v: string) => (
        <Tag color={LEVEL_COLORS[v] || 'default'}>
          {t('nhi.level.' + v) || v}
        </Tag>
      ),
    },
    {
      title: t('nhi.score'),
      dataIndex: 'risk_score',
      key: 'risk_score',
      width: 80,
      render: (s: number) => (
        <Text style={{ color: s >= 80 ? '#ff4d4f' : s >= 50 ? '#fa8c16' : '#52c41a', fontWeight: 700 }}>
          {s}
        </Text>
      ),
    },
    {
      title: t('nhi.credentials'),
      dataIndex: 'credential_types',
      key: 'credential_types',
      render: (ct: string[]) => (
        <Space size={4} wrap>
          {ct.includes('nopasswd_sudo') && <Tag color="red">NOPASSWD</Tag>}
          {ct.includes('ssh_key') && <Tag color="blue">SSH Key</Tag>}
          {ct.includes('credential_findings') && <Tag color="orange">凭据泄露</Tag>}
          {!ct.length && <Text type="secondary">—</Text>}
        </Space>
      ),
    },
    {
      title: t('nhi.owner'),
      dataIndex: 'owner_email',
      key: 'owner_email',
      render: (e: string | null, r: NHIIdentity) => (
        e
          ? <Text type="secondary">{e}</Text>
          : <Button size="small" onClick={() => setOwnerModal(r)}>
              {t('nhi.assignOwner')}
            </Button>
      ),
    },
    {
      title: t('nhi.rotationDue'),
      dataIndex: 'rotation_due_days',
      key: 'rotation_due_days',
      width: 90,
      render: (d: number | null) => {
        if (d === null) return <Text type="secondary">—</Text>
        const color = d <= 7 ? '#ff4d4f' : d <= 30 ? '#fa8c16' : '#52c41a'
        return <Text style={{ color }}>{d}d</Text>
      },
    },
  ]

  // ─── Alert columns ────────────────────────────────────────────────────────

  const alertColumns = [
    {
      title: t('nhi.level'),
      dataIndex: 'level',
      key: 'level',
      width: 80,
      render: (v: string) => (
        <Badge color={LEVEL_COLORS[v] || '#d9d9d9'} text={t('nhi.level.' + v) || v} />
      ),
    },
    {
      title: t('nhi.title'),
      dataIndex: 'title',
      key: 'title',
      render: (t: string, r: NHIAlert) => (
        <Space direction="vertical" size={0}>
          <Text>{r.title}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {r.nhi_username} · {r.asset_code || '—'}
          </Text>
        </Space>
      ),
    },
    {
      title: t('nhi.alertType'),
      dataIndex: 'alert_type',
      key: 'alert_type',
      width: 140,
      render: (v: string) => {
        const map: Record<string, string> = {
          risk_alert: '风险告警', no_owner: '无Owner', rotation_due: '轮换到期',
          privilege_escalation: '权限升级', credential_leak: '凭据泄露',
        }
        return <Tag>{map[v] || v}</Tag>
      },
    },
    {
      title: t('nhi.status'),
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (v: string) => {
        const map: Record<string, { color: string; icon: React.ReactNode }> = {
          new: { color: 'error', icon: <ExclamationCircleOutlined /> },
          acknowledged: { color: 'warning', icon: <ClockCircleOutlined /> },
          resolved: { color: 'success', icon: <CheckCircleOutlined /> },
          dismissed: { color: 'default', icon: <CheckCircleOutlined /> },
        }
        const s = map[v] || map.new
        return <Badge color={s.color === 'error' ? '#ff4d4f' : s.color === 'warning' ? '#faad14' : s.color === 'success' ? '#52c41a' : '#d9d9d9'} text={v} />
      },
    },
    {
      title: t('nhi.actions'),
      key: 'actions',
      width: 150,
      render: (_: unknown, r: NHIAlert) => (
        <Space size={4}>
          {r.status === 'new' && (
            <Button size="small" onClick={() => handleAck(r.id)}>
              {t('nhi.acknowledge')}
            </Button>
          )}
          {(r.status === 'new' || r.status === 'acknowledged') && (
            <Button size="small" type="primary" onClick={() => handleResolve(r.id)}>
              {t('nhi.resolve')}
            </Button>
          )}
        </Space>
      ),
    },
  ]

  // ─── Render ────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}><Text type="secondary">{t('nhi.loading')}</Text></div>
      </div>
    )
  }

  if (!dashboard) return null

  const pieProps = { cx: 80, cy: 80, innerRadius: 40, outerRadius: 70, paddingAngle: 2 }

  return (
    <div style={{ padding: 0 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>
            <RobotOutlined style={{ marginRight: 8, color: '#7c3aed' }} />
            {t('nhi.title')}
          </Title>
          <Text type="secondary">{t('nhi.subtitle')}</Text>
        </div>
        <Button icon={<SyncOutlined spin={syncing} />} onClick={handleSync} loading={syncing}>
          {t('nhi.sync')}
        </Button>
      </div>

      {/* Critical alerts */}
      {dashboard.critical_count > 0 && (
        <Alert
          type="error"
          icon={<WarningOutlined />}
          message={t('nhi.criticalAlert', { count: dashboard.critical_count })}
          description={t('nhi.criticalAlertDesc')}
          style={{ marginBottom: 16 }}
          showIcon
        />
      )}

      {/* Key stats */}
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col span={12} md={6}>
          <StatCard
            label={t('nhi.totalNHI')}
            value={dashboard.total_nhi}
            icon={<RobotOutlined />}
            color="#7c3aed"
          />
        </Col>
        <Col span={12} md={6}>
          <StatCard
            label={t('nhi.totalHuman')}
            value={dashboard.total_human}
            icon={<UserOutlined />}
            color="#3b82f6"
          />
        </Col>
        <Col span={12} md={6}>
          <StatCard
            label={t('nhi.criticalCount')}
            value={dashboard.critical_count}
            icon={<WarningOutlined />}
            color="#ff4d4f"
          />
        </Col>
        <Col span={12} md={6}>
          <StatCard
            label={t('nhi.nopasswdCount')}
            value={dashboard.has_nopasswd_count}
            icon={<LockOutlined />}
            color="#ea580c"
          />
        </Col>
      </Row>

      {/* Tabs */}
      <Card size="small">
        <div style={{ marginBottom: 12 }}>
          {(['overview', 'inventory', 'alerts'] as const).map(k => (
            <Button
              key={k}
              type={activeTab === k ? 'primary' : 'default'}
              size="small"
              style={{ marginRight: 8 }}
              onClick={() => setActiveTab(k)}
            >
              {k === 'overview' && t('nhi.tabOverview')}
              {k === 'inventory' && t('nhi.tabInventory')}
              {k === 'alerts' && `${t('nhi.tabAlerts')} (${dashboard.recent_alerts.length})`}
            </Button>
          ))}
        </div>

        {/* Overview tab */}
        {activeTab === 'overview' && (
          <Row gutter={[16, 16]}>
            {/* Human vs NHI ratio */}
            <Col xs={24} md={8}>
              <Card size="small" title={t('nhi.humanVsNHI')}>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie data={ratioData} dataKey="value" {...pieProps} cx="50%" cy="50%">
                      {ratioData.map((e, i) => <Cell key={i} fill={e.color} />)}
                    </Pie>
                    <RechartsTooltip formatter={(v: unknown, name: unknown) => [`${v} ${t('nhi.accounts')}`, String(name)]} />
                  </PieChart>
                </ResponsiveContainer>
                <div style={{ textAlign: 'center', fontSize: 12, color: '#6b7280' }}>
                  {t('nhi.nhiRatio')} {Math.round(dashboard.nhi_ratio * 100)}%
                </div>
              </Card>
            </Col>

            {/* Risk level breakdown */}
            <Col xs={24} md={8}>
              <Card size="small" title={t('nhi.riskByLevel')}>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={levelChartData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" />
                    <YAxis type="category" dataKey="name" width={50} tick={{ fontSize: 12 }} />
                    <RechartsTooltip />
                    <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                      {levelChartData.map((e, i) => <Cell key={i} fill={e.color} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </Col>

            {/* NHI type breakdown */}
            <Col xs={24} md={8}>
              <Card size="small" title={t('nhi.riskByType')}>
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart {...pieProps}>
                    <Pie data={typeChartData} dataKey="value" {...pieProps}>
                      {typeChartData.map((e, i) => <Cell key={i} fill={e.color} />)}
                    </Pie>
                    <RechartsTooltip formatter={(v: unknown, name: unknown) => [`${v}`, String(name)]} />
                  </PieChart>
                </ResponsiveContainer>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, justifyContent: 'center', marginTop: 4 }}>
                  {typeChartData.map(e => (
                    <Space key={e.name} size={4}>
                      <div style={{ width: 8, height: 8, borderRadius: '50%', background: e.color }} />
                      <Text style={{ fontSize: 11 }}>{e.name}</Text>
                    </Space>
                  ))}
                </div>
              </Card>
            </Col>

            {/* Top risks table */}
            <Col span={24}>
              <Card size="small" title={t('nhi.topRisks')}>
                <Table
                  size="small"
                  dataSource={dashboard.top_risks}
                  rowKey="id"
                  pagination={false}
                  columns={[
                    { title: t('nhi.username'), dataIndex: 'username', render: (u: string) => <Text strong>{u}</Text> },
                    {
                      title: t('nhi.type'),
                      dataIndex: 'nhi_type',
                      render: (v: string) => <Tag color={TYPE_COLORS[v] || '#9ca3af'}>{t('nhi.type.' + v) || v}</Tag>,
                    },
                    {
                      title: t('nhi.level'),
                      dataIndex: 'nhi_level',
                      render: (v: string) => <Tag color={LEVEL_COLORS[v] || 'default'}>{t('nhi.level.' + v) || v}</Tag>,
                    },
                    {
                      title: t('nhi.score'),
                      dataIndex: 'risk_score',
                      render: (s: number) => (
                        <Text style={{ color: s >= 80 ? '#ff4d4f' : s >= 50 ? '#fa8c16' : '#52c41a', fontWeight: 700 }}>
                          {s}
                        </Text>
                      ),
                    },
                    {
                      title: t('nhi.signals'),
                      dataIndex: 'risk_signals',
                      render: (sigs: Record<string, unknown>[]) => (
                        <Space wrap size={4}>
                          {sigs.slice(0, 2).map((sig, i) => (
                            <Tooltip key={i} title={(sig.detail as string) || ''}>
                              <Tag color={LEVEL_COLORS[sig.severity as string] || 'default'} style={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {sig.type as string}
                              </Tag>
                            </Tooltip>
                          ))}
                          {sigs.length > 2 && <Tag>+{sigs.length - 2}</Tag>}
                        </Space>
                      ),
                    },
                    {
                      title: t('nhi.owner'),
                      dataIndex: 'owner_email',
                      render: (e: string | null) => e ? (
                        <Text type="secondary">{e}</Text>
                      ) : (
                        <Text type="danger"><ExclamationCircleOutlined /> {t('nhi.noOwner')}</Text>
                      ),
                    },
                    {
                      title: t('nhi.rotationDue'),
                      dataIndex: 'rotation_due_days',
                      render: (d: number | null) => {
                        if (d === null) return <Text type="secondary">—</Text>
                        return <Text style={{ color: d <= 7 ? '#ff4d4f' : d <= 30 ? '#fa8c16' : '#52c41a' }}>{d}d</Text>
                      },
                    },
                  ]}
                />
              </Card>
            </Col>
          </Row>
        )}

        {/* Inventory tab */}
        {activeTab === 'inventory' && (
          <>
            <Space style={{ marginBottom: 12 }} wrap>
              <Select
                placeholder={t('nhi.filterType')}
                allowClear
                style={{ width: 130 }}
                options={NHI_TYPE_OPTIONS}
                onChange={v => setFilterType(v || undefined)}
              />
              <Select
                placeholder={t('nhi.filterLevel')}
                allowClear
                style={{ width: 100 }}
                options={[
                  { value: 'critical', label: '严重' },
                  { value: 'high', label: '高危' },
                  { value: 'medium', label: '中危' },
                  { value: 'low', label: '低危' },
                ]}
                onChange={v => setFilterLevel(v || undefined)}
              />
              <Button
                size="small"
                type={noOwner ? 'primary' : 'default'}
                onClick={() => setNoOwner(p => !p)}
              >
                {t('nhi.onlyNoOwner')} {noOwner && `(${dashboard.no_owner_count})`}
              </Button>
              <Text type="secondary" style={{ fontSize: 12 }}>{invTotal} {t('nhi.total')}</Text>
            </Space>
            <Table
              size="small"
              dataSource={inventory}
              rowKey="id"
              loading={invLoading}
              columns={invColumns}
              pagination={{ pageSize: 20 }}
            />
          </>
        )}

        {/* Alerts tab */}
        {activeTab === 'alerts' && (
          <Table
            size="small"
            dataSource={alertList}
            rowKey="id"
            loading={alertLoading}
            columns={alertColumns}
            pagination={{ pageSize: 15 }}
            rowClassName={(r) => r.is_read ? 'nhi-alert-read' : ''}
          />
        )}
      </Card>

      {/* Assign owner modal */}
      <Modal
        title={t('nhi.assignOwnerTitle', { username: ownerModal?.username })}
        open={!!ownerModal}
        onCancel={() => setOwnerModal(null)}
        onOk={() => ownerForm.submit()}
        okText={t('nhi.confirm')}
        cancelText={t('nhi.cancel')}
      >
        <Form form={ownerForm} onFinish={handleAssignOwner} layout="vertical">
          <Form.Item
            name="email"
            label={t('nhi.ownerEmail')}
            rules={[{ required: true, type: 'email', message: t('nhi.emailRequired') }]}
          >
            <Input placeholder="owner@example.com" />
          </Form.Item>
          <Form.Item name="name" label={t('nhi.ownerName')}>
            <Input placeholder={t('nhi.ownerNamePlaceholder')} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
