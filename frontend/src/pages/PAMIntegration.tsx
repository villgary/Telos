import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Row, Col, Card, Typography, Tag, Space, Spin, Button,
  Modal, Form, Input, Select, message, Popconfirm,
  Table, Tooltip, Divider,
} from 'antd'
import {
  CloudSyncOutlined, ReloadOutlined, PlusOutlined,
  DeleteOutlined, CheckCircleOutlined, WarningOutlined,
  ApiOutlined, QuestionCircleOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import {
  listPAMIntegrations, createPAMIntegration, deletePAMIntegration,
  syncPAMIntegration, listPAMAccounts, getPAMComparison,
} from '../api/client'

const { Title, Text } = Typography
const { Option } = Select
const { TextArea } = Input

interface PAMIntegration {
  id: number
  name: string
  provider: string
  status: string
  last_sync_at: string | null
  last_error: string | null
  account_count: number
  created_at: string
}

interface PAMAccount {
  id: number
  account_name: string
  account_type: string
  pam_status: string
  last_used: string | null
  matched_asset_code: string | null
  matched_asset_ip: string | null
  matched_username: string | null
  is_admin: boolean
  match_confidence: number
  comparison_result: string
}

const RESULT_COLOR: Record<string, string> = {
  matched: 'green',
  privileged_gap: 'red',
  unmatched_pam: 'orange',
  compliant: 'green',
  unmanaged: 'orange',
}

export default function PAMIntegration() {
  const { t } = useTranslation()
  const [integrations, setIntegrations] = useState<PAMIntegration[]>([])
  const [loading, setLoading] = useState(true)
  const [syncId, setSyncId] = useState<number | null>(null)
  const [addOpen, setAddOpen] = useState(false)
  const [accounts, setAccounts] = useState<PAMAccount[]>([])
  const [accountsLoading, setAccountsLoading] = useState(false)
  const [detailIntegrationId, setDetailIntegrationId] = useState<number | null>(null)
  const [filter, setFilter] = useState<string>('')
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)

  const PROVIDER_LABEL = {
    custom_api: t('pam.customApi'),
    tencent_cloud_bastion: t('pam.tencent'),
    aliyun_bastion: t('pam.alibaba'),
    cyberark: t('pam.cyberark'),
  }
  const PROVIDER_DESC = {
    custom_api: t('pam.customApiDesc'),
    tencent_cloud_bastion: t('pam.tencentDesc'),
    aliyun_bastion: t('pam.alibabaDesc'),
    cyberark: t('pam.cyberarkDesc'),
  }
  const RESULT_LABEL = {
    matched: t('pam.matched'),
    privileged_gap: t('pam.privilegedGap'),
    unmatched_pam: t('pam.unmatchedPam'),
    compliant: t('pam.compliant'),
    unmanaged: t('pam.unmanaged'),
  }

  const fetchIntegrations = () => {
    setLoading(true)
    listPAMIntegrations().then(r => setIntegrations(r.data.integrations || []))
      .catch(() => message.error(t('msg.loadFailed')))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchIntegrations() }, [])

  const handleSync = async (id: number) => {
    setSyncId(id)
    try {
      const r = await syncPAMIntegration(id)
      message.success(t('pam.syncComplete', { count: r.data.accounts_fetched }))
      fetchIntegrations()
      if (detailIntegrationId === id) {
        loadAccounts(id)
      }
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.syncFailed'))
    } finally {
      setSyncId(null)
    }
  }

  const loadAccounts = (integrationId: number) => {
    setDetailIntegrationId(integrationId)
    setAccountsLoading(true)
    listPAMAccounts(integrationId).then(r => setAccounts(r.data.accounts || []))
      .catch(() => message.error(t('pam.loadAccountsFailed')))
      .finally(() => setAccountsLoading(false))
  }

  const handleAdd = async (values: Record<string, unknown>) => {
    setSaving(true)
    try {
      // Parse config JSON if custom_api
      let config: Record<string, string> = {}
      if (values.config_json) {
        try { config = JSON.parse(values.config_json as string) } catch { throw new Error(t('pam.configJsonError')) }
      }
      await createPAMIntegration({
        name: values.name as string,
        provider: values.provider as string,
        config,
      })
      message.success(t('pam.integrationCreated'))
      setAddOpen(false)
      form.resetFields()
      fetchIntegrations()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.createFailed'))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deletePAMIntegration(id)
      message.success(t('msg.deleted'))
      if (detailIntegrationId === id) setDetailIntegrationId(null)
      fetchIntegrations()
    } catch { message.error(t('msg.deleteFailed')) }
  }

  const filteredAccounts = filter
    ? accounts.filter(a => a.comparison_result === filter || a.comparison_result === (filter === 'compliant' ? 'matched' : filter))
    : accounts

  const accountColumns: ColumnsType<PAMAccount> = [
    {
      title: t('pam.comparisonResult'),
      dataIndex: 'comparison_result',
      width: 120,
      render: (r: string) => (
        <Tag color={RESULT_COLOR[r]} icon={r === 'privileged_gap' ? <WarningOutlined /> : r === 'matched' || r === 'compliant' ? <CheckCircleOutlined /> : <QuestionCircleOutlined />}>
          {(RESULT_LABEL as Record<string, string>)[r] || r}
        </Tag>
      ),
    },
    {
      title: t('pam.pamAccount'),
      key: 'pam_account',
      width: 200,
      render: (_: unknown, r: PAMAccount) => (
        <Space size={2}>
          <Tag color={r.account_type === 'privileged' ? 'red' : 'default'} style={{ fontSize: 11 }}>
            {r.account_type}
          </Tag>
          <Text strong>{r.account_name}</Text>
        </Space>
      ),
    },
    {
      title: t('pam.ascoreAccount'),
      key: 'ascore_account',
      width: 180,
      render: (_: unknown, r: PAMAccount) => {
        if (!r.matched_asset_code) return <Text type="secondary">{t('pam.unmatched')}</Text>
        return (
          <Space size={2}>
            {r.is_admin && <Tag color="red" style={{ fontSize: 10 }}>Admin</Tag>}
            <Text>{r.matched_username}</Text>
            <Text type="secondary" style={{ fontSize: 11 }}>@{r.matched_asset_code}</Text>
          </Space>
        )
      },
    },
    {
      title: t('pam.pamStatus'),
      dataIndex: 'pam_status',
      width: 100,
      render: (s: string) => (
        <Tag color={s === 'active' ? 'green' : s === 'disabled' ? 'default' : 'orange'} style={{ fontSize: 11 }}>
          {s}
        </Tag>
      ),
    },
    {
      title: t('pam.lastUsed'),
      dataIndex: 'last_used',
      width: 140,
      render: (v?: string) => v ? (
        <Text type="secondary" style={{ fontSize: 12 }}>{new Date(v).toLocaleDateString('zh-CN')}</Text>
      ) : <Text type="secondary" style={{ fontSize: 12 }}>—</Text>,
    },
  ]

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>
            <ApiOutlined style={{ marginRight: 8 }} />
            {t('pam.title')}
          </Title>
          <Text type="secondary">{t('pam.subtitle')}</Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchIntegrations}>{t('btn.refresh')}</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setAddOpen(true)}>{t('pam.newIntegration')}</Button>
        </Space>
      </div>

      {loading ? <Spin /> : (
        <>
          {/* Integration cards */}
          <Row gutter={[16, 16]} style={{ marginBottom: 20 }}>
            {integrations.map(integ => (
              <Col xs={24} md={12} lg={8} key={integ.id}>
                <Card
                  size="small"
                  title={
                    <Space>
                      <CloudSyncOutlined />
                      <Text strong>{integ.name}</Text>
                    </Space>
                  }
                  extra={
                    <Space size={4}>
                      <Tag color={integ.status === 'active' ? 'green' : integ.status === 'error' ? 'red' : 'default'}>
                        {integ.status === 'active' ? t('pam.normal') : integ.status === 'error' ? t('pam.error') : t('pam.offline')}
                      </Tag>
                    </Space>
                  }
                  bodyStyle={{ padding: 0 }}
                >
                  <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0' }}>
                    <Space wrap size={8}>
                      <Tag icon={<ApiOutlined />}>{(PROVIDER_LABEL as Record<string, string>)[integ.provider] || integ.provider}</Tag>
                      <Tag>{t('pam.accounts', { count: integ.account_count })}</Tag>
                    </Space>
                    {integ.last_sync_at && (
                      <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4 }}>
                        {t('pam.lastSync')}: {new Date(integ.last_sync_at).toLocaleString('zh-CN')}
                      </Text>
                    )}
                    {integ.last_error && (
                      <Tooltip title={integ.last_error}>
                        <Text type="danger" style={{ fontSize: 11, display: 'block' }}>
                          ⚠ {integ.last_error.substring(0, 60)}...
                        </Text>
                      </Tooltip>
                    )}
                  </div>
                  <div style={{ padding: '8px 16px' }}>
                    <Space>
                      <Button
                        size="small" icon={<ReloadOutlined spin={syncId === integ.id} />}
                        onClick={() => handleSync(integ.id)}
                        loading={syncId === integ.id}
                      >
                        {t('btn.sync')}
                      </Button>
                      <Button
                        size="small"
                        type={detailIntegrationId === integ.id ? 'primary' : 'default'}
                        onClick={() => detailIntegrationId === integ.id ? setDetailIntegrationId(null) : loadAccounts(integ.id)}
                      >
                        {t('pam.viewAccounts')}
                      </Button>
                      <Popconfirm
                        title={t('pam.deleteConfirm')}
                        onConfirm={() => handleDelete(integ.id)}
                        okText={t('btn.delete')}
                        okButtonProps={{ danger: true }}
                      >
                        <Button size="small" danger icon={<DeleteOutlined />}>{t('btn.delete')}</Button>
                      </Popconfirm>
                    </Space>
                  </div>
                </Card>
              </Col>
            ))}

            {/* Add card placeholder */}
            <Col xs={24} md={12} lg={8}>
              <Card
                size="small"
                style={{ border: '2px dashed #d9d9d9', cursor: 'pointer', minHeight: 140 }}
                bodyStyle={{ padding: 0 }}
                onClick={() => setAddOpen(true)}
              >
                <div style={{ textAlign: 'center', padding: '40px 16px', color: '#999' }}>
                  <PlusOutlined style={{ fontSize: 24, marginBottom: 8, display: 'block' }} />
                  <Text type="secondary">{t('pam.addIntegration')}</Text>
                </div>
              </Card>
            </Col>
          </Row>

          {/* Account detail table */}
          {detailIntegrationId !== null && (
            <Card
              title={
                <Space>
                  <CloudSyncOutlined />
                  {t('pam.accountComparisonDetail')}
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    ({integrations.find(i => i.id === detailIntegrationId)?.name})
                  </Text>
                </Space>
              }
              extra={
                <Space>
                  <Select value={filter} onChange={setFilter} style={{ width: 140 }} allowClear placeholder={t('filter.all')}>
                    <Option value="matched">{t('pam.matched')}</Option>
                    <Option value="privileged_gap">{t('pam.privilegedGap')}</Option>
                    <Option value="unmatched_pam">{t('pam.unmatchedPam')}</Option>
                  </Select>
                  <Text type="secondary">{filteredAccounts.length} / {accounts.length}</Text>
                </Space>
              }
              bodyStyle={{ padding: 0 }}
            >
              <Table
                columns={accountColumns}
                dataSource={filteredAccounts}
                rowKey="id"
                loading={accountsLoading}
                size="small"
                scroll={{ x: 800 }}
                pagination={{ pageSize: 20, showSizeChanger: false }}
                rowClassName={r => r.comparison_result === 'privileged_gap' ? 'pam-privileged-gap' : r.comparison_result === 'unmatched_pam' ? 'pam-unmatched' : ''}
              />
            </Card>
          )}
        </>
      )}

      {/* Add integration modal */}
      <Modal
        title={<Space><CloudSyncOutlined />{t('pam.addIntegrationModal')}</Space>}
        open={addOpen}
        onCancel={() => { setAddOpen(false); form.resetFields() }}
        footer={null}
        width={520}
      >
        <Form form={form} layout="vertical" onFinish={handleAdd} style={{ marginTop: 16 }}>
          <Form.Item
            name="name"
            label={t('table.name')}
            rules={[{ required: true, message: t('pam.nameRequired') }]}
          >
            <Input placeholder={t('pam.namePlaceholder')} />
          </Form.Item>
          <Form.Item
            name="provider"
            label={t('pam.integrationType')}
            rules={[{ required: true, message: t('pam.typeRequired') }]}
          >
            <Select placeholder={t('pam.typePlaceholder')} optionLabelProp="label">
              {Object.entries(PROVIDER_LABEL).map(([k, v]) => (
                <Option key={k} value={k} label={v}>
                  <Space direction="vertical" size={0}>
                    <Text>{v}</Text>
                    <Text type="secondary" style={{ fontSize: 11 }}>{(PROVIDER_DESC as Record<string, string>)[k]}</Text>
                  </Space>
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Divider plain style={{ margin: '8px 0', fontSize: 12, color: '#999' }}>
            {t('pam.connectionConfig')}
          </Divider>
          <Form.Item
            name="config_json"
            label={t('pam.configParams')}
            extra={
              <Text type="secondary" style={{ fontSize: 11 }}>
                custom_api: {"{"}"api_url": "...", "api_key": "...", "auth_type": "bearer"{"}"}
              </Text>
            }
          >
            <TextArea
              rows={4}
              placeholder={'{"api_url": "https://your-pam-api.com/accounts", "api_key": "sk-...", "auth_type": "bearer"}'}
            />
          </Form.Item>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <Button onClick={() => { setAddOpen(false); form.resetFields() }}>{t('btn.cancel')}</Button>
            <Button type="primary" htmlType="submit" loading={saving}>{t('pam.createAndSync')}</Button>
          </div>
        </Form>
      </Modal>

      <style>{`
        .pam-privileged-gap td { background: #fff5f5 !important; }
        .pam-unmatched td { background: #fff5f5 !important; }
      `}</style>
    </div>
  )
}
