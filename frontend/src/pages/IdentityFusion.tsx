import { useEffect, useState } from 'react'
import {
  Row, Card, Typography, Tag, Space, Spin, Button,
  Input, Empty, message, Popconfirm, Modal, Select,
  Tooltip, Table,
} from 'antd'
import {
  UserOutlined, ReloadOutlined, LinkOutlined, DisconnectOutlined,
  SearchOutlined, CheckCircleOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import type { ColumnsType } from 'antd/es/table'
import {
  listIdentities, rematchIdentities,
  linkIdentityAccount, unlinkIdentityAccount, getIdentitySuggestions,
} from '../api/client'

const { Title, Text } = Typography
const { Option } = Select

interface AccountItem {
  id: number
  snapshot_id: number
  asset_id: number
  asset_code: string
  ip: string
  hostname?: string
  username: string
  uid_sid: string
  is_admin: boolean
  account_status: string | null
  last_login: string | null
  match_type: string
  match_confidence: number
}

interface IdentityItem {
  id: number
  display_name: string | null
  email: string | null
  confidence: number
  source: string
  account_count: number
  admin_count: number
  asset_count: number
  max_risk_score: number
  latest_login: string | null
  accounts: AccountItem[]
}

const MATCH_COLOR: Record<string, string> = {
  uid: 'green',
  username: 'blue',
  email: 'cyan',
  manual: 'purple',
}

const RISK_COLOR: Record<string, string> = {
  low: '#52c41a', medium: '#faad14', high: '#fa8c16', critical: '#ff4d4f',
}

function riskLevel(score: number): string {
  if (score >= 70) return 'critical'
  if (score >= 45) return 'high'
  if (score >= 20) return 'medium'
  return 'low'
}

// Truncate long uid_sid for display, keep tooltip for full value
function UidSidDisplay({ value }: { value: string }) {
  const MAX = 36
  if (value.length <= MAX) return <Text style={{ fontSize: 12 }}>{value}</Text>
  return (
    <Tooltip title={<Text style={{ fontSize: 11, wordBreak: 'break-all' }}>{value}</Text>}>
      <Text style={{ fontSize: 12 }}>{value.slice(0, MAX)}…</Text>
    </Tooltip>
  )
}

export default function IdentityFusion() {
  const { t } = useTranslation()
  const [identities, setIdentities] = useState<IdentityItem[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [total, setTotal] = useState(0)
  const [rematching, setRematching] = useState(false)
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())

  const MATCH_LABEL: Record<string, string> = {
    uid: t('identity.uidMatch'),
    username: t('identity.usernameMatch'),
    email: t('identity.emailMatch'),
    manual: t('identity.manual'),
  }

  const [linkModalOpen, setLinkModalOpen] = useState(false)
  const [linkTargetIdentity, setLinkTargetIdentity] = useState<IdentityItem | null>(null)
  const [suggestions, setSuggestions] = useState<{
    snapshot_id: number; asset_code: string; ip: string;
    username: string; uid_sid: string; is_admin: boolean; match_reason: string;
    candidate_identities: number[]
  }[]>([])
  const [linkSnapshotId, setLinkSnapshotId] = useState<number | null>(null)
  const [linkLoading, setLinkLoading] = useState(false)

  const fetchIdentities = () => {
    setLoading(true)
    listIdentities({ search: search || undefined, limit: 100 })
      .then(r => {
        setIdentities(r.data.identities)
        setTotal(r.data.total)
      })
      .catch(() => message.error(t('identity.loadFailed')))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchIdentities() }, [search])

  const handleRematch = async () => {
    setRematching(true)
    try {
      const r = await rematchIdentities()
      message.success(t('identity.matchDone', { count: r.data.identities }))
      fetchIdentities()
    } catch { message.error(t('identity.matchFailed')) }
    finally { setRematching(false) }
  }

  const handleUnlink = async (identId: number, accId: number) => {
    try {
      await unlinkIdentityAccount(identId, accId)
      message.success(t('identity.unlinked'))
      fetchIdentities()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('identity.unlinkFailed'))
    }
  }

  const openLinkModal = (ident: IdentityItem) => {
    setLinkTargetIdentity(ident)
    setLinkModalOpen(true)
    setLinkSnapshotId(null)
    setSuggestions([])
    const query = ident.display_name || ident.accounts[0]?.username || ''
    if (query) {
      getIdentitySuggestions(query).then(r => setSuggestions(r.data.suggestions || [])).catch(() => {})
    }
  }

  const handleLink = async () => {
    if (!linkTargetIdentity || !linkSnapshotId) return
    setLinkLoading(true)
    try {
      await linkIdentityAccount({
        identity_id: linkTargetIdentity.id,
        snapshot_id: linkSnapshotId,
        match_type: 'manual',
        match_confidence: 100,
      })
      message.success(t('identity.linked'))
      setLinkModalOpen(false)
      fetchIdentities()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('identity.linkFailed'))
    } finally { setLinkLoading(false) }
  }

  const toggleExpand = (id: number) => {
    setExpandedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  // ── Identity table columns ────────────────────────────────────────────────
  const identityColumns: ColumnsType<IdentityItem> = [
    {
      title: t('identity.identityName'),
      key: 'name',
      render: (_, r) => (
        <Space>
          <UserOutlined />
          <Text strong>
            {r.display_name || r.accounts[0]?.username || t('identity.unknown')}
          </Text>
        </Space>
      ),
    },
    {
      title: t('identity.confidence'),
      key: 'confidence',
      width: 90,
      render: (_, r) => (
        <Tag color={r.source === 'manual' ? 'purple' : r.confidence >= 100 ? 'green' : 'blue'}>
          {r.confidence}%
        </Tag>
      ),
    },
    {
      title: t('identity.accounts'),
      key: 'account_count',
      width: 90,
      render: (_, r) => (
        <Space size={4}>
          <CheckCircleOutlined style={{ color: '#1890ff' }} />
          <Text style={{ fontSize: 13 }}>{r.account_count}</Text>
        </Space>
      ),
    },
    {
      title: t('identity.admins'),
      key: 'admin_count',
      width: 80,
      render: (_, r) => r.admin_count > 0
        ? <Tag color="red">{r.admin_count}</Tag>
        : <Text type="secondary" style={{ fontSize: 12 }}>—</Text>,
    },
    {
      title: t('identity.assets'),
      key: 'asset_count',
      width: 80,
      render: (_, r) => r.asset_count,
    },
    {
      title: t('identity.lastLogin'),
      key: 'latest_login',
      width: 120,
      render: (_, r) => r.latest_login
        ? new Date(r.latest_login).toLocaleDateString('zh-CN')
        : <Text type="secondary" style={{ fontSize: 12 }}>{t('identity.neverLogin')}</Text>,
    },
    {
      title: t('risk.score'),
      key: 'risk_score',
      width: 80,
      render: (_, r) => {
        if (!r.max_risk_score) return <Text type="secondary" style={{ fontSize: 12 }}>—</Text>
        const lvl = riskLevel(r.max_risk_score)
        return (
          <Tag color={RISK_COLOR[lvl]}>
            {r.max_risk_score}
          </Tag>
        )
      },
    },
  ]

  // ── Expanded account table columns ───────────────────────────────────────
  const accountColumns: ColumnsType<AccountItem> = [
    {
      title: t('identity.matchSource'),
      key: 'match_type',
      width: 100,
      render: (_, acc) => (
        <Tag color={MATCH_COLOR[acc.match_type]} style={{ fontSize: 11 }}>
          {MATCH_LABEL[acc.match_type] || acc.match_type}
        </Tag>
      ),
    },
    {
      title: t('table.username'),
      key: 'username',
      render: (_, acc) => (
        <Space size={4}>
          <Text strong={acc.is_admin} style={{ fontSize: 13 }}>
            {acc.username}
          </Text>
          {acc.is_admin && <Tag color="red" style={{ fontSize: 10 }}>Admin</Tag>}
        </Space>
      ),
    },
    {
      title: t('identity.uidSid'),
      key: 'uid_sid',
      render: (_, acc) => <UidSidDisplay value={acc.uid_sid} />,
    },
    {
      title: t('table.assetCode'),
      key: 'asset_code',
      width: 110,
      render: (_, acc) => (
        <Tooltip title={`${acc.hostname || ''} ${acc.ip}`}>
          <Tag color="blue" style={{ fontSize: 11 }}>{acc.asset_code}</Tag>
        </Tooltip>
      ),
    },
    {
      title: t('table.ip'),
      key: 'ip',
      width: 130,
      render: (_, acc) => (
        <Text type="secondary" style={{ fontSize: 12 }}>{acc.ip}</Text>
      ),
    },
    {
      title: t('table.lastLogin'),
      key: 'last_login',
      width: 110,
      render: (_, acc) => acc.last_login
        ? new Date(acc.last_login).toLocaleDateString('zh-CN')
        : <Text type="secondary" style={{ fontSize: 12 }}>{t('identity.neverLogin')}</Text>,
    },
    {
      title: t('table.actions'),
      key: 'actions',
      width: 60,
      render: (_, acc) => {
        if (acc.match_type === 'manual') return null
        return (
          <Tooltip title={t('identity.manualUnlink')}>
            <Button
              type="text" size="small" danger icon={<DisconnectOutlined />}
              onClick={() => handleUnlink(
                identities.find(id => id.accounts.some(a => a.id === acc.id))?.id ?? 0, acc.id
              )}
            />
          </Tooltip>
        )
      },
    },
  ]

  const expandedRowRender = (record: IdentityItem) => (
    <div style={{ padding: '8px 0' }}>
      {/* Identity summary + add button row */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
        <Button size="small" icon={<LinkOutlined />} onClick={() => openLinkModal(record)}>
          {t('identity.addLinkedAccount')}
        </Button>
      </div>
      <Table
        columns={accountColumns}
        dataSource={record.accounts}
        rowKey="id"
        size="small"
        pagination={false}
        scroll={{ x: 700 }}
        style={{ marginLeft: 40 }}
      />
    </div>
  )

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>
            <UserOutlined style={{ marginRight: 8 }} />
            {t('identity.title')}
          </Title>
          <Text type="secondary">
            {t('identity.subtitle')} · {t('identity.totalIdentities', { count: total })}
          </Text>
        </div>
        <Space>
          <Input
            placeholder={t('identity.searchPlaceholder')}
            prefix={<SearchOutlined />}
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ width: 220 }}
            allowClear
          />
          <Button icon={<ReloadOutlined spin={rematching} />} onClick={handleRematch} loading={rematching}>
            {t('identity.rematch')}
          </Button>
          <Button onClick={fetchIdentities}>{t('identity.refresh')}</Button>
        </Space>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', marginTop: 80 }}><Spin size="large" /></div>
      ) : identities.length === 0 ? (
        <Empty description={t('identity.noIdentities')} style={{ marginTop: 80 }} />
      ) : (
        <Card bodyStyle={{ padding: 0 }}>
          <Table
            columns={identityColumns}
            dataSource={identities}
            rowKey="id"
            expandable={{
              expandedRowRender,
              expandedRowKeys: Array.from(expandedIds),
              onExpand: (expanded, record) => toggleExpand(record.id),
            }}
            pagination={false}
            size="small"
            scroll={{ x: 700 }}
          />
        </Card>
      )}

      {/* Link modal */}
      <Modal
        title={<Space><LinkOutlined />{t('identity.addAccountTo')}: {linkTargetIdentity?.display_name}</Space>}
        open={linkModalOpen}
        onCancel={() => setLinkModalOpen(false)}
        onOk={handleLink}
        okText={t('identity.link')}
        okButtonProps={{ loading: linkLoading, disabled: !linkSnapshotId }}
        width={520}
      >
        <Text type="secondary" style={{ fontSize: 12 }}>
          {t('identity.addAccountHint')}
        </Text>
        <Select
          showSearch
          placeholder={t('identity.searchUsername')}
          style={{ width: '100%', marginTop: 12 }}
          value={linkSnapshotId}
          onChange={setLinkSnapshotId}
          filterOption={(input, option) =>
            (option?.label as string)?.toLowerCase().includes(input.toLowerCase())
          }
        >
          {suggestions.map(s => (
            <Option key={s.snapshot_id} value={s.snapshot_id}
              label={`${s.username} (${s.asset_code})`}>
              <Space>
                <Tag color={s.is_admin ? 'red' : 'default'} style={{ fontSize: 11 }}>Admin</Tag>
                <Text strong>{s.username}</Text>
                <Text type="secondary" style={{ fontSize: 11 }}>
                  <UidSidDisplay value={s.uid_sid} />
                </Text>
                <Text type="secondary" style={{ fontSize: 11 }}>@{s.asset_code}({s.ip})</Text>
              </Space>
            </Option>
          ))}
        </Select>
      </Modal>
    </div>
  )
}
