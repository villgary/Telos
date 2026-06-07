/**
 * Cloud Agent Discovery page — peer to /ai-agents.
 * Lists connections, supports add / edit (name only) / delete / rotate / sync-now.
 * Shows the per-connection audit log in a drawer.
 */
import { useEffect, useState } from 'react'
import {
  Table, Button, Space, Typography, Tag, message, Modal, Form, Input,
  Select, Drawer, Empty, Spin, Popconfirm, Tooltip,
} from 'antd'
import {
  PlusOutlined, SyncOutlined, EditOutlined, DeleteOutlined,
  KeyOutlined, HistoryOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import {
  listCloudConnections, createCloudConnection, updateCloudConnection,
  deleteCloudConnection, rotateCloudConnection, syncCloudConnection,
  getCloudConnectionAudit,
  CloudConnection, CloudConnectionAuditEntry,
} from '../api/client'

const { Title, Text } = Typography

export default function CloudAgentDiscoveryPage() {
  const { t } = useTranslation()
  const [loading, setLoading] = useState(true)
  const [connections, setConnections] = useState<CloudConnection[]>([])
  const [addOpen, setAddOpen] = useState(false)
  const [editing, setEditing] = useState<CloudConnection | null>(null)
  const [rotating, setRotating] = useState<CloudConnection | null>(null)
  const [auditConn, setAuditConn] = useState<CloudConnection | null>(null)
  const [auditEntries, setAuditEntries] = useState<CloudConnectionAuditEntry[]>([])
  const [syncingId, setSyncingId] = useState<number | null>(null)
  const [addForm] = Form.useForm()
  const [editForm] = Form.useForm()
  const [rotateForm] = Form.useForm()

  const refresh = async () => {
    setLoading(true)
    try {
      const r = await listCloudConnections()
      setConnections(r.data.connections)
    } catch {
      message.error('Failed to load connections')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  const handleAdd = async () => {
    const values = await addForm.validateFields()
    try {
      await createCloudConnection(values)
      message.success(t('aiAgent.discovery.addSuccess'))
      setAddOpen(false)
      addForm.resetFields()
      refresh()
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t('aiAgent.discovery.addError'))
    }
  }

  const handleRename = async () => {
    if (!editing) return
    const values = await editForm.validateFields()
    try {
      await updateCloudConnection(editing.id, values)
      message.success('Renamed')
      setEditing(null)
      refresh()
    } catch {
      message.error('Failed to rename')
    }
  }

  const handleRotate = async () => {
    if (!rotating) return
    const values = await rotateForm.validateFields()
    try {
      await rotateCloudConnection(rotating.id, values.api_key)
      message.success('Key rotated')
      setRotating(null)
      rotateForm.resetFields()
      refresh()
    } catch {
      message.error('Failed to rotate key')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteCloudConnection(id)
      message.success('Deleted')
      refresh()
    } catch {
      message.error('Failed to delete')
    }
  }

  const handleSync = async (c: CloudConnection) => {
    setSyncingId(c.id)
    try {
      const r = await syncCloudConnection(c.id)
      message.success(
        t('aiAgent.discovery.agentsDiscovered', { count: r.data.agents_discovered })
      )
      refresh()
    } catch (e: any) {
      if (e?.response?.status === 409) {
        message.warning(t('aiAgent.discovery.syncInProgress'))
      } else {
        message.error('Sync failed')
      }
    } finally {
      setSyncingId(null)
    }
  }

  const openAudit = async (c: CloudConnection) => {
    setAuditConn(c)
    try {
      const r = await getCloudConnectionAudit(c.id, 100, 0)
      setAuditEntries(r.data.entries)
    } catch {
      setAuditEntries([])
    }
  }

  const columns = [
    {
      title: t('aiAgent.discovery.name'),
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: t('aiAgent.discovery.provider'),
      dataIndex: 'provider',
      key: 'provider',
      render: (p: string) => t(`aiAgent.discovery.providerLabel.${p}`),
    },
    {
      title: 'Fingerprint',
      dataIndex: 'api_key_fingerprint',
      key: 'api_key_fingerprint',
      render: (fp: string) => <Text code>{fp}</Text>,
    },
    {
      title: t('aiAgent.discovery.lastSync'),
      key: 'last_sync',
      render: (_: any, c: CloudConnection) => {
        if (!c.last_sync_at) return <Text type="secondary">{t('aiAgent.discovery.lastSyncNever')}</Text>
        return (
          <Space direction="vertical" size={0}>
            <Text>{new Date(c.last_sync_at).toLocaleString()}</Text>
            {c.last_sync_status && (
              <Tag color={
                c.last_sync_status === 'success' ? 'green' :
                c.last_sync_status === 'partial' ? 'orange' :
                c.last_sync_status === 'running' ? 'blue' : 'red'
              }>
                {t(`aiAgent.discovery.status.${c.last_sync_status}`)}
              </Tag>
            )}
            {c.last_sync_error && (
              <Tooltip title={c.last_sync_error}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {c.last_sync_error.slice(0, 40)}
                </Text>
              </Tooltip>
            )}
          </Space>
        )
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, c: CloudConnection) => (
        <Space>
          <Button
            size="small"
            icon={<SyncOutlined />}
            loading={syncingId === c.id || c.last_sync_status === 'running'}
            onClick={() => handleSync(c)}
          >
            {syncingId === c.id
              ? t('aiAgent.discovery.syncing')
              : t('aiAgent.discovery.syncNow')}
          </Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => {
            setEditing(c); editForm.setFieldsValue({ name: c.name })
          }}>
            {t('aiAgent.discovery.edit')}
          </Button>
          <Button size="small" icon={<KeyOutlined />} onClick={() => setRotating(c)}>
            {t('aiAgent.discovery.rotate')}
          </Button>
          <Button size="small" icon={<HistoryOutlined />} onClick={() => openAudit(c)}>
            {t('aiAgent.discovery.auditLog')}
          </Button>
          <Popconfirm
            title={t('aiAgent.discovery.deleteConfirm')}
            onConfirm={() => handleDelete(c.id)}
            okText="Delete"
            okButtonProps={{ danger: true }}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              {t('aiAgent.discovery.delete')}
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <div>
          <Title level={3} style={{ margin: 0 }}>{t('aiAgent.discovery.title')}</Title>
          <Text type="secondary">{t('aiAgent.subtitle')}</Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setAddOpen(true)}>
          {t('aiAgent.discovery.add')}
        </Button>
      </Space>

      {loading ? (
        <Spin />
      ) : connections.length === 0 ? (
        <Empty description="No connections yet" />
      ) : (
        <Table rowKey="id" dataSource={connections} columns={columns} pagination={false} />
      )}

      {/* Add dialog */}
      <Modal
        title={t('aiAgent.discovery.addTitle')}
        open={addOpen}
        onCancel={() => setAddOpen(false)}
        onOk={handleAdd}
        okText={t('aiAgent.discovery.add')}
        destroyOnClose
      >
        <Form form={addForm} layout="vertical" preserve={false}>
          <Form.Item name="name" label={t('aiAgent.discovery.name')}
                     rules={[{ required: true, max: 64 }]}>
            <Input placeholder="acme-prod" />
          </Form.Item>
          <Form.Item name="provider" label={t('aiAgent.discovery.provider')}
                     rules={[{ required: true }]}>
            <Select>
              <Select.Option value="anthropic">
                {t('aiAgent.discovery.providerLabel.anthropic')}
              </Select.Option>
              <Select.Option value="openai">
                {t('aiAgent.discovery.providerLabel.openai')}
              </Select.Option>
            </Select>
          </Form.Item>
          <Form.Item name="api_key" label={t('aiAgent.discovery.apiKey')}
                     rules={[{ required: true }]}
                     extra={t('aiAgent.discovery.apiKeyHint')}>
            <Input.Password placeholder="sk-ant-admin-..." />
          </Form.Item>
        </Form>
      </Modal>

      {/* Edit name dialog */}
      <Modal
        title={t('aiAgent.discovery.edit')}
        open={!!editing}
        onCancel={() => setEditing(null)}
        onOk={handleRename}
        destroyOnClose
      >
        <Form form={editForm} layout="vertical" preserve={false}>
          <Form.Item name="name" label={t('aiAgent.discovery.name')}
                     rules={[{ required: true, max: 64 }]}>
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      {/* Rotate key dialog */}
      <Modal
        title={t('aiAgent.discovery.rotate')}
        open={!!rotating}
        onCancel={() => { setRotating(null); rotateForm.resetFields() }}
        onOk={handleRotate}
        destroyOnClose
      >
        <Form form={rotateForm} layout="vertical" preserve={false}>
          <Form.Item name="api_key" label={t('aiAgent.discovery.apiKey')}
                     rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>

      {/* Audit drawer */}
      <Drawer
        title={auditConn ? `${t('aiAgent.discovery.auditLog')} — ${auditConn.name}` : ''}
        open={!!auditConn}
        onClose={() => setAuditConn(null)}
        width={600}
      >
        {auditEntries.length === 0 ? (
          <Empty />
        ) : (
          <Table
            rowKey="id"
            dataSource={auditEntries}
            pagination={false}
            size="small"
            columns={[
              {
                title: 'Time',
                dataIndex: 'created_at',
                render: (s: string) => new Date(s).toLocaleString(),
              },
              {
                title: 'Action',
                dataIndex: 'action',
                render: (a: string) => t(`aiAgent.discovery.auditAction.${a}`),
              },
              {
                title: 'Note',
                dataIndex: 'note',
                render: (n: string | null) => n || '—',
              },
            ]}
          />
        )}
      </Drawer>
    </div>
  )
}
