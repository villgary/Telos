import { useState, useEffect } from 'react'
import {
  Table, Tag, Space, Button, Typography, Card, Select, message,
  Tooltip, Statistic, Row, Col, Progress, Alert, Spin, Modal, Input, Divider
} from 'antd'
import {
  SafetyCertificateOutlined, ReloadOutlined,
  ArrowUpOutlined, ArrowDownOutlined, MinusOutlined, UserOutlined
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { useTranslation } from 'react-i18next'
import {
  listAccountRisks, recomputeAccountRisks,
  getSnapshotOwner, setSnapshotOwner,
  type SnapshotOwner
} from '../api/client'

const { Title, Text } = Typography

const RISK_COLOR: Record<string, string> = {
  critical: 'red',
  high: 'orange',
  medium: 'gold',
  low: 'green',
}

const RISK_ICON: Record<string, React.ReactNode> = {
  critical: <ArrowUpOutlined />,
  high: <ArrowUpOutlined />,
  medium: <MinusOutlined />,
  low: <ArrowDownOutlined />,
}

interface RiskFactor {
  factor: string
  score: number
  description?: string
}

interface AccountRiskRecord {
  id: number
  snapshot_id: number
  risk_score: number
  risk_level: string
  risk_factors: RiskFactor[]
  computed_at: string
  username: string | null
  asset_code: string | null
  asset_ip: string | null
  is_admin: boolean
  last_login: string | null
  identity_id: number | null
  cross_asset_count: number
  owner_identity_id?: number
  owner_email?: string
  owner_name?: string
}

export default function AccountRiskList() {
  const { t } = useTranslation()
  const [data, setData] = useState<AccountRiskRecord[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [recomputing, setRecomputing] = useState(false)
  const [page, setPage] = useState(1)
  const [minScore, setMinScore] = useState(0)
  const [levelFilter, setLevelFilter] = useState<string>('all')
  const [ownerModal, setOwnerModal] = useState<{ snapshotId: number; username: string } | null>(null)
  const [ownerEmail, setOwnerEmail] = useState('')
  const [ownerName, setOwnerName] = useState('')
  const [assigning, setAssigning] = useState(false)
  const [ownerCache, setOwnerCache] = useState<Record<number, SnapshotOwner>>({})
  const pageSize = 20

  // Translate a backend factor name to i18n string
  function translateFactor(factor: string): string {
    if (factor === '特权账号') return t('risk.factor.privileged')
    if (factor === '离机账号') return t('risk.factor.dormant')
    if (factor === '长期未登录') return t('risk.factor.neverLogin')
    const crossMatch = factor.match(/^跨(\d+)系统关联$/)
    if (crossMatch) return t('risk.factor.crossSystem', { count: parseInt(crossMatch[1]) })
    const usernameMatch = factor.match(/^高危用户名\((.+)\)$/)
    if (usernameMatch) return t('risk.factor.dangerousUsername', { username: usernameMatch[1] })
    return factor // fallback to raw value
  }

  const fetchData = async () => {
    setLoading(true)
    try {
      const r = await listAccountRisks({
        limit: pageSize,
        offset: (page - 1) * pageSize,
        min_score: minScore,
      })
      setData(r.data.results || [])
      setTotal(r.data.total || 0)
    } catch {
      message.error(t('msg.error'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [page, minScore, levelFilter])

  // Fetch owner data on modal open
  useEffect(() => {
    if (!ownerModal) return
    setOwnerEmail('')
    setOwnerName('')
    getSnapshotOwner(ownerModal.snapshotId)
      .then(r => {
        setOwnerEmail(r.data.owner_email || '')
        setOwnerName(r.data.owner_name || '')
      })
      .catch(() => {})
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ownerModal])

  const handleAssignOwner = async () => {
    if (!ownerModal || !ownerEmail) return
    setAssigning(true)
    try {
      await setSnapshotOwner(ownerModal.snapshotId, { owner_email: ownerEmail, owner_name: ownerName })
      message.success(t('msg.success'))
      setOwnerModal(null)
      fetchData()
    } catch {
      message.error(t('msg.error'))
    } finally {
      setAssigning(false)
    }
  }

  const handleRecompute = async () => {
    setRecomputing(true)
    try {
      await recomputeAccountRisks()
      message.success(t('msg.recomputeSuccess'))
      setTimeout(() => fetchData(), 2000)
    } catch {
      message.error(t('msg.error'))
    } finally {
      setRecomputing(false)
    }
  }

  // Summary stats
  const criticalCount = data.filter(d => d.risk_level === 'critical').length
  const highCount = data.filter(d => d.risk_level === 'high').length
  const mediumCount = data.filter(d => d.risk_level === 'medium').length
  const lowCount = data.filter(d => d.risk_level === 'low').length

  const filteredData = levelFilter === 'all'
    ? data
    : data.filter(d => d.risk_level === levelFilter)

  const columns: ColumnsType<AccountRiskRecord> = [
    {
      title: t('table.username', '#'),
      dataIndex: 'username',
      key: 'username',
      width: 140,
      render: (v, rec) => (
        <Space>
          {rec.is_admin && <Tag color="red">Admin</Tag>}
          <Text strong>{v || '-'}</Text>
        </Space>
      ),
    },
    {
      title: t('table.assetCode'),
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
      title: t('risk.score'),
      dataIndex: 'risk_score',
      key: 'risk_score',
      width: 120,
      sorter: (a, b) => a.risk_score - b.risk_score,
      defaultSortOrder: 'descend',
      render: (score: number) => {
        const level = score >= 70 ? 'critical' : score >= 45 ? 'high' : score >= 25 ? 'medium' : 'low'
        return (
          <Space>
            <Tag color={RISK_COLOR[level]} style={{ minWidth: 48, textAlign: 'center', fontWeight: 600 }}>
              {score}
            </Tag>
            {RISK_ICON[level]}
          </Space>
        )
      },
    },
    {
      title: t('risk.level'),
      dataIndex: 'risk_level',
      key: 'risk_level',
      width: 90,
      render: (level: string) => (
        <Tag color={RISK_COLOR[level] || 'default'}>
          {t(`risk.${level}`, level)}
        </Tag>
      ),
    },
    {
      title: t('risk.factors'),
      dataIndex: 'risk_factors',
      key: 'risk_factors',
      render: (factors: RiskFactor[]) => (
        <Space wrap size={4}>
          {(factors || []).slice(0, 3).map((f, i) => (
            <Tag key={i} color="blue" style={{ fontSize: 11 }}>
              {translateFactor(f.factor)} (+{f.score})
            </Tag>
          ))}
          {(factors || []).length > 3 && (
            <Tag style={{ fontSize: 11 }}>+{factors.length - 3}</Tag>
          )}
        </Space>
      ),
    },
    {
      title: t('table.lastLogin'),
      dataIndex: 'last_login',
      key: 'last_login',
      width: 110,
      render: (v: string | null) => v
        ? new Date(v).toLocaleDateString()
        : <Text type="secondary">-</Text>,
    },
    {
      title: t('table.computedAt'),
      dataIndex: 'computed_at',
      key: 'computed_at',
      width: 140,
      render: (v: string) => new Date(v).toLocaleString(),
    },
    {
      title: t('owner.title'),
      key: 'owner',
      width: 120,
      render: (_: unknown, rec: AccountRiskRecord) => (
        <Space direction="vertical" size={0}>
          {rec.owner_name
            ? <Text style={{ fontSize: 12 }}>{rec.owner_name}</Text>
            : <Text type="secondary" style={{ fontSize: 12 }}>—</Text>}
          {rec.owner_email
            ? <Text type="secondary" style={{ fontSize: 11 }}>{rec.owner_email}</Text>
            : !rec.owner_name && <Tag color="orange" style={{ fontSize: 10 }}>{t('owner.unassigned')}</Tag>}
          <Button
            type="link"
            size="small"
            icon={<UserOutlined />}
            style={{ fontSize: 11, padding: 0, height: 'auto' }}
            onClick={() => setOwnerModal({ snapshotId: rec.snapshot_id, username: rec.username || '' })}
          >
            {rec.owner_name ? t('owner.change') : t('owner.assign')}
          </Button>
        </Space>
      ),
    },
  ]

  const expandedRowRender = (record: AccountRiskRecord) => (
    <Card size="small" bodyStyle={{ padding: '12px 16px' }}>
      <Row gutter={[16, 8]}>
        {(record.risk_factors || []).map((f, i) => (
          <Col span={12} key={i}>
            <Space size={4}>
              <Tag color="blue">+{f.score}</Tag>
              <Text style={{ fontSize: 13 }}>{translateFactor(f.factor)}</Text>
              {f.description && (
                <Text type="secondary" style={{ fontSize: 12 }}>— {f.description}</Text>
              )}
            </Space>
          </Col>
        ))}
      </Row>
      {record.identity_id && (
        <Row style={{ marginTop: 8 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {t('identity.linked')} #{record.identity_id} · {t('identity.crossAsset')} {record.cross_asset_count}
          </Text>
        </Row>
      )}
    </Card>
  )

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>{t('nav.accountRiskList')}</Title>
        <Tooltip title={t('risk.recomputeTip')}>
          <Button
            icon={<ReloadOutlined />}
            onClick={handleRecompute}
            loading={recomputing}
          >
            {t('btn.recomputeAll')}
          </Button>
        </Tooltip>
      </div>

      {/* Summary */}
      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card bodyStyle={{ padding: '12px 16px' }}>
            <Statistic
              title={t('risk.totalAccounts')}
              value={total}
              valueStyle={{ fontSize: 22 }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card bodyStyle={{ padding: '12px 16px' }}>
            <Statistic
              title={<Space><Tag color="red" style={{ margin: 0 }}>{criticalCount}</Tag>{t('risk.critical')}</Space>}
              value={criticalCount}
              valueStyle={{ fontSize: 22, color: '#ff4d4f' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card bodyStyle={{ padding: '12px 16px' }}>
            <Statistic
              title={<Space><Tag color="orange" style={{ margin: 0 }}>{highCount}</Tag>{t('risk.high')}</Space>}
              value={highCount}
              valueStyle={{ fontSize: 22, color: '#fa8c16' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card bodyStyle={{ padding: '12px 16px' }}>
            <Statistic
              title={<Space><Tag color="gold" style={{ margin: 0 }}>{mediumCount}</Tag>{t('risk.medium')}</Space>}
              value={mediumCount}
              valueStyle={{ fontSize: 22, color: '#faad14' }}
            />
          </Card>
        </Col>
      </Row>

      {/* Filters */}
      <Card bodyStyle={{ padding: '12px 16px', marginBottom: 12 }}>
        <Space size={16} wrap>
          <Space>
            <Text type="secondary">{t('filter.level')}:</Text>
            <Select value={levelFilter} onChange={v => { setLevelFilter(v); setPage(1) }} style={{ width: 120 }}>
              <Select.Option value="all">{t('filter.all')}</Select.Option>
              <Select.Option value="critical">{t('risk.critical')}</Select.Option>
              <Select.Option value="high">{t('risk.high')}</Select.Option>
              <Select.Option value="medium">{t('risk.medium')}</Select.Option>
              <Select.Option value="low">{t('risk.low')}</Select.Option>
            </Select>
          </Space>
          <Space>
            <Text type="secondary">{t('filter.minScore')}:</Text>
            <Select value={minScore} onChange={v => { setMinScore(v); setPage(1) }} style={{ width: 100 }}>
              <Select.Option value={0}>{t('filter.any')}</Select.Option>
              <Select.Option value={25}>≥ 25</Select.Option>
              <Select.Option value={45}>≥ 45</Select.Option>
              <Select.Option value={70}>≥ 70</Select.Option>
            </Select>
          </Space>
        </Space>
      </Card>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
      ) : (
        <Table
          columns={columns}
          dataSource={filteredData}
          rowKey="id"
          expandable={{
            expandedRowRender,
            expandRowByClick: true,
          }}
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

      <Modal
        title={t('owner.assignTitle', { username: ownerModal?.username || '' })}
        open={!!ownerModal}
        onCancel={() => setOwnerModal(null)}
        onOk={handleAssignOwner}
        confirmLoading={assigning}
        okText={t('btn.confirm')}
        cancelText={t('btn.cancel')}
      >
        <Space direction="vertical" size={12} style={{ width: '100%', marginTop: 12 }}>
          <Text type="secondary">{t('owner.assignDesc')}</Text>
          <Input
            prefix="Email"
            placeholder={t('owner.emailPlaceholder')}
            value={ownerEmail}
            onChange={e => setOwnerEmail(e.target.value)}
            type="email"
          />
          <Input
            prefix={t('owner.nameLabel')}
            placeholder={t('owner.namePlaceholder')}
            value={ownerName}
            onChange={e => setOwnerName(e.target.value)}
          />
          <Text type="secondary" style={{ fontSize: 12 }}>
            {t('owner.hint')}
          </Text>
        </Space>
      </Modal>
    </div>
  )
}
