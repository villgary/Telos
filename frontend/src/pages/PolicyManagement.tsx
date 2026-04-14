import { useState, useEffect } from 'react'
import {
  Table, Tag, Card, Button, Space, Typography, Modal, Form, Input,
  Select, message, Tooltip, Tabs, Row, Col, Statistic, Divider,
  Badge
} from 'antd'
import {
  SafetyCertificateOutlined, PlusOutlined, DeleteOutlined,
  EditOutlined, PlayCircleOutlined, CheckCircleOutlined,
  CloseCircleOutlined, FileTextOutlined
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { useTranslation } from 'react-i18next'
import {
  listPolicies, createPolicy, updatePolicy, deletePolicy,
  evaluatePolicy, evaluateAllPolicies, getPolicyResults, listRecentSnapshots
} from '../api/client'

interface RecentSnapshot {
  id: number
  username: string
  asset_id: number
  asset_code: string | null
  asset_ip: string | null
  is_admin: boolean
  snapshot_time: string | null
  last_login: string | null
}

const { Title, Text, Paragraph } = Typography
const { confirm } = Modal

const SEVERITY_COLOR: Record<string, string> = {
  critical: 'red',
  high: 'orange',
  medium: 'gold',
  low: 'green',
}

interface Policy {
  id: number
  name: string
  description: string | null
  name_key: string | null
  description_key: string | null
  category: string | null
  severity: string
  rego_code: string
  enabled: boolean
  is_built_in: boolean
  created_at: string
}

interface PolicyResult {
  id: number
  policy_id: number
  policy_name: string
  policy_name_key: string | null
  snapshot_id: number
  username: string
  asset_code: string | null
  passed: boolean
  message: string | null
  evaluated_at: string
}

const CATEGORY_OPTIONS = (t: (k: string) => string) => [
  { value: 'privilege', label: t('policy.categoryPrivilege') },
  { value: 'lifecycle', label: t('policy.categoryLifecycle') },
  { value: 'compliance', label: t('policy.categoryCompliance') },
  { value: 'custom', label: t('policy.categoryCustom') },
]

export default function PolicyManagement() {
  const { t, i18n } = useTranslation()
  const isZh = i18n.language.startsWith('zh')

  const [policies, setPolicies] = useState<Policy[]>([])
  const [results, setResults] = useState<PolicyResult[]>([])
  const [totalResults, setTotalResults] = useState(0)
  const [loading, setLoading] = useState(false)
  const [policyLoading, setPolicyLoading] = useState(false)
  const [policyModalOpen, setPolicyModalOpen] = useState(false)
  const [editingPolicy, setEditingPolicy] = useState<Policy | null>(null)
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)
  const [activeTab, setActiveTab] = useState('policies')
  const [snapshotInput, setSnapshotInput] = useState<string | undefined>()
  const [recentSnapshots, setRecentSnapshots] = useState<RecentSnapshot[]>([])
  const [evalLoading, setEvalLoading] = useState(false)
  const [evalResult, setEvalResult] = useState<any>(null)
  const [evalDrawerOpen, setEvalDrawerOpen] = useState(false)
  const [resultsDays, setResultsDays] = useState(7)

  const fetchPolicies = async () => {
    setPolicyLoading(true)
    try {
      const r = await listPolicies()
      setPolicies(r.data)
    } catch {
      message.error(t('msg.error'))
    } finally {
      setPolicyLoading(false)
    }
  }

  const fetchResults = async () => {
    setLoading(true)
    try {
      const r = await getPolicyResults({ days: resultsDays, limit: 50 })
      setResults(r.data.results || [])
      setTotalResults(r.data.total || 0)
    } catch {
      message.error(t('msg.error'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchPolicies() }, [])
  useEffect(() => {
    if (activeTab === 'evaluate') fetchRecentSnapshots()
  }, [activeTab])
  useEffect(() => { if (activeTab === 'results') fetchResults() }, [activeTab, resultsDays])

  const fetchRecentSnapshots = async () => {
    try {
      const r = await listRecentSnapshots(50)
      setRecentSnapshots(r.data || [])
    } catch { /* ignore */ }
  }

  const openCreate = () => {
    setEditingPolicy(null)
    form.resetFields()
    setPolicyModalOpen(true)
  }

  const openEdit = (pol: Policy) => {
    if (pol.is_built_in) { message.warning(t('policy.builtInNotEditable')); return }
    setEditingPolicy(pol)
    form.setFieldsValue({
      name: pol.name,
      description: pol.description,
      category: pol.category,
      severity: pol.severity,
      rego_code: pol.rego_code,
      enabled: pol.enabled,
    })
    setPolicyModalOpen(true)
  }

  const handleSave = async (values: Record<string, unknown>) => {
    setSaving(true)
    try {
      if (editingPolicy) {
        await updatePolicy(editingPolicy.id, values as Parameters<typeof updatePolicy>[1])
        message.success(t('msg.updateSuccess'))
      } else {
        await createPolicy(values as Parameters<typeof createPolicy>[0])
        message.success(t('msg.addSuccess'))
      }
      setPolicyModalOpen(false)
      fetchPolicies()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.error'))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (pol: Policy) => {
    if (pol.is_built_in) { message.warning(t('policy.builtInNotDeletable')); return }
    confirm({
      title: t('msg.deleteConfirm'),
      onOk: async () => {
        try {
          await deletePolicy(pol.id)
          message.success(t('msg.deleteSuccess'))
          fetchPolicies()
        } catch {
          message.error(t('msg.error'))
        }
      },
    })
  }

  const handleEvaluate = async () => {
    if (!snapshotInput) {
      message.error(t('policy.selectSnapshot'))
      return
    }
    setEvalLoading(true)
    try {
      const r = await evaluateAllPolicies(parseInt(snapshotInput))
      setEvalResult(r.data)
      setEvalDrawerOpen(true)
      fetchResults()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.error'))
    } finally {
      setEvalLoading(false)
    }
  }

  const policyColumns: ColumnsType<Policy> = [
    {
      title: t('table.name'),
      dataIndex: 'name',
      key: 'name',
      width: 200,
      render: (v: string, rec: Policy) => (
        <Space direction="vertical" size={0}>
          <Space size={4}>
            {rec.is_built_in && <Tag color="purple" style={{ fontSize: 10 }}>{t('policy.builtIn')}</Tag>}
            <Text strong style={{ fontSize: 13 }}>
              {rec.name_key ? t(rec.name_key) : v}
            </Text>
          </Space>
          {rec.description && (
            <Text type="secondary" style={{ fontSize: 11 }}>
              {rec.description_key ? t(rec.description_key) : rec.description}
            </Text>
          )}
        </Space>
      ),
    },
    {
      title: t('filter.level'),
      dataIndex: 'severity',
      key: 'severity',
      width: 90,
      render: (sev: string) => (
        <Tag color={SEVERITY_COLOR[sev] || 'default'}>{t(`risk.${sev}`, sev)}</Tag>
      ),
    },
    {
      title: t('table.category'),
      dataIndex: 'category',
      key: 'category',
      width: 100,
      render: (v: string | null) => {
        const cats: Record<string, string> = {
          privilege: t('policy.categoryPrivilege'),
          lifecycle: t('policy.categoryLifecycle'),
          compliance: t('policy.categoryCompliance'),
          custom: t('policy.categoryCustom'),
        }
        return v ? <Tag>{cats[v] || v}</Tag> : <Text type="secondary">-</Text>
      },
    },
    {
      title: t('policy.status'),
      dataIndex: 'enabled',
      key: 'enabled',
      width: 80,
      render: (v: boolean) => v
        ? <Badge status="success" text={t('status.enabled')} />
        : <Badge status="default" text={t('status.disabled')} />,
    },
    {
      title: t('policy.rego'),
      dataIndex: 'rego_code',
      key: 'rego_code',
      width: 250,
      render: (code: string) => (
        <Paragraph
          style={{ fontSize: 11, fontFamily: 'monospace', margin: 0 }}
          ellipsis={{ rows: 2, expandable: false }}
          copyable={{ text: code }}
        >
          {code}
        </Paragraph>
      ),
    },
    {
      title: t('table.actions'),
      key: 'actions',
      width: 120,
      render: (_, rec) => (
        <Space size={4}>
          <Tooltip title={t('btn.edit')}>
            <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(rec)} disabled={rec.is_built_in} />
          </Tooltip>
          <Tooltip title={t('btn.delete')}>
            <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(rec)} disabled={rec.is_built_in} />
          </Tooltip>
        </Space>
      ),
    },
  ]

  const resultColumns: ColumnsType<PolicyResult> = [
    {
      title: t('table.asset'),
      key: 'asset',
      width: 160,
      render: (_, rec) => (
        <Space direction="vertical" size={0}>
          <Text style={{ fontSize: 13 }}>{rec.asset_code || `#${rec.snapshot_id}`}</Text>
          <Text type="secondary" style={{ fontSize: 11 }}>{rec.username}</Text>
        </Space>
      ),
    },
    {
      title: t('table.name'),
      dataIndex: 'policy_name',
      key: 'policy_name',
      width: 180,
      render: (v: string, rec: PolicyResult) => (
        <Text style={{ fontSize: 13 }}>{rec.policy_name_key ? t(rec.policy_name_key) : v}</Text>
      ),
    },
    {
      title: t('policy.result'),
      key: 'result',
      width: 80,
      render: (_, rec) => rec.passed
        ? <Tag color="green" icon={<CheckCircleOutlined />}>PASS</Tag>
        : <Tag color="red" icon={<CloseCircleOutlined />}>FAIL</Tag>,
    },
    {
      title: t('policy.message'),
      dataIndex: 'message',
      key: 'message',
      render: (v: string | null) => <Text style={{ fontSize: 12 }}>{v || '-'}</Text>,
    },
    {
      title: t('table.detectedAt'),
      dataIndex: 'evaluated_at',
      key: 'evaluated_at',
      width: 140,
      render: (v: string) => new Date(v).toLocaleString(isZh ? 'zh-CN' : 'en-US'),
    },
  ]

  const tabs = [
    {
      key: 'policies',
      label: t('policy.tabPolicies'),
      children: (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
            <Text type="secondary">{policies.length} {t('policy.policies')}</Text>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
              {t('btn.add')}
            </Button>
          </div>
          <Table
            columns={policyColumns}
            dataSource={policies}
            rowKey="id"
            loading={policyLoading}
            size="small"
            pagination={false}
          />
        </>
      ),
    },
    {
      key: 'evaluate',
      label: t('policy.tabEvaluate'),
      children: (
        <Card bodyStyle={{ padding: '24px' }}>
          <Title level={5}>{t('policy.evaluateTitle')}</Title>
          <Space size={12} style={{ marginTop: 12 }} wrap>
            <Select
              placeholder={t('policy.selectSnapshot')}
              value={snapshotInput}
              onChange={v => setSnapshotInput(v)}
              allowClear
              showSearch
              filterOption={(input, option) =>
                (option?.label as string)?.toLowerCase().includes(input.toLowerCase())
              }
              style={{ minWidth: 320 }}
              options={recentSnapshots.map(s => ({
                value: s.id,
                label: `${s.username} @ ${s.asset_code || s.asset_ip || '#' + s.asset_id} (ID: ${s.id})${s.is_admin ? ' ★' : ''}`,
              }))}
            />
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={handleEvaluate}
              loading={evalLoading}
              disabled={!snapshotInput}
            >
              {t('btn.evaluate')}
            </Button>
          </Space>
          <Divider />
          <Text type="secondary" style={{ fontSize: 12 }}>
            {t('policy.evalTip')}
          </Text>

          {evalResult && (
            <div style={{ marginTop: 16 }}>
              <Row gutter={12}>
                <Col span={6}><Statistic title={t('policy.totalPolicies')} value={evalResult.total_policies} /></Col>
                <Col span={6}><Statistic title={t('policy.passed')} value={evalResult.passed} valueStyle={{ color: '#52c41a' }} /></Col>
                <Col span={6}><Statistic title={t('policy.failed')} value={evalResult.failed} valueStyle={{ color: '#ff4d4f' }} /></Col>
              </Row>
              {evalResult.violations && evalResult.violations.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <Text strong>{t('policy.violations')}:</Text>
                  <Space wrap style={{ marginTop: 8 }}>
                    {evalResult.violations.map((v: any, i: number) => (
                      <Tag key={i} color={SEVERITY_COLOR[v.severity] || 'default'} icon={<CloseCircleOutlined />}>
                        {v.policy_name_key ? t(v.policy_name_key) : v.policy_name}: {v.message}
                      </Tag>
                    ))}
                  </Space>
                </div>
              )}
            </div>
          )}
        </Card>
      ),
    },
    {
      key: 'results',
      label: `${t('policy.tabResults')} (${totalResults})`,
      children: (
        <>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
            <Select value={resultsDays} onChange={v => setResultsDays(v)} style={{ width: 120 }}>
              <Select.Option value={7}>7 {t('unit.days')}</Select.Option>
              <Select.Option value={30}>30 {t('unit.days')}</Select.Option>
              <Select.Option value={90}>90 {t('unit.days')}</Select.Option>
            </Select>
          </div>
          <Table
            columns={resultColumns}
            dataSource={results}
            rowKey="id"
            loading={loading}
            size="small"
            pagination={{ total: totalResults, pageSize: 20, showTotal: (tot: number) => `${tot} ${t('unit.items')}` }}
          />
        </>
      ),
    },
  ]

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>{t('nav.policyManagement')}</Title>
        <Text type="secondary" style={{ fontSize: 12 }}>{t('policy.subtitle')}</Text>
      </div>
      <Tabs items={tabs} onChange={k => setActiveTab(k)} />
      {activeTab === 'policies' && (
        <Modal
          title={<Space><FileTextOutlined />{editingPolicy ? t('btn.edit') : t('btn.add')} {t('policy.policy')}</Space>}
          open={policyModalOpen}
          onCancel={() => setPolicyModalOpen(false)}
          footer={null}
          width={700}
        >
          <Form form={form} layout="vertical" onFinish={handleSave} style={{ marginTop: 16 }}>
            <Row gutter={12}>
              <Col span={16}>
                <Form.Item name="name" label={t('table.name')} rules={[{ required: true }]}>
                  <Input placeholder={t('policy.namePlaceholder')} />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item name="severity" label={t('filter.level')} initialValue="high">
                  <Select>
                    <Select.Option value="critical">{t('risk.critical')}</Select.Option>
                    <Select.Option value="high">{t('risk.high')}</Select.Option>
                    <Select.Option value="medium">{t('risk.medium')}</Select.Option>
                    <Select.Option value="low">{t('risk.low')}</Select.Option>
                  </Select>
                </Form.Item>
              </Col>
            </Row>
            <Form.Item name="description" label={t('table.description')}>
              <Input.TextArea rows={2} placeholder={t('policy.descriptionPlaceholder')} />
            </Form.Item>
            <Form.Item name="category" label={t('table.category')}>
              <Select allowClear placeholder={t('policy.categoryPlaceholder')}>
                {CATEGORY_OPTIONS(t).map(o => <Select.Option key={o.value} value={o.value}>{o.label}</Select.Option>)}
              </Select>
            </Form.Item>
            <Form.Item
              name="rego_code"
              label={t('policy.regoLabel')}
              rules={[{ required: true }]}
              extra={
                <Text type="secondary" style={{ fontSize: 11 }}>
                  {t('policy.regoHelper')}
                  <br />
                  {t('policy.regoFunctions')}
                </Text>
              }
            >
              <Input.TextArea rows={6} placeholder={'deny["violation message"] {\n  contains(input.account.username, "admin")\n}'} style={{ fontFamily: 'monospace' }} />
            </Form.Item>
            <Form.Item name="enabled" label={t('policy.status')} valuePropName="checked" initialValue={true}>
              <Input type="checkbox" />
            </Form.Item>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <Button onClick={() => setPolicyModalOpen(false)}>{t('btn.cancel')}</Button>
              <Button type="primary" htmlType="submit" loading={saving}>{t('btn.save')}</Button>
            </div>
          </Form>
        </Modal>
      )}
    </div>
  )
}
