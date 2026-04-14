import { useState, useEffect } from 'react'
import {
  Card, Table, Button, Space, Tag, Modal, Form, Input,
  Select, Steps, message, Popconfirm, Drawer, Typography,
  Divider, Alert,
} from 'antd'
import {
  PlusOutlined, PlayCircleOutlined, DeleteOutlined,
  EditOutlined, CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import api from '../api/client'

const { Title, Text, Paragraph } = Typography

interface PlaybookStep {
  action: string
  target: string
  params?: Record<string, unknown>
}

interface Playbook {
  id: number
  name: string
  description?: string
  name_key?: string | null
  description_key?: string | null
  trigger_type: string
  trigger_filter: Record<string, unknown>
  steps: PlaybookStep[]
  approval_required: boolean
  enabled: boolean
  created_at: string
}

interface PlaybookExecution {
  id: number
  playbook_id: number
  snapshot_id: number
  status: string
  steps_status: { step_index: number; status: string; detail: string }[]
  result?: string
  triggered_by?: number
  approved_by?: number
  created_at: string
}

const _ACTION_KEYS = [
  { key: 'disable_account', suffix: 'disable_account' },
  { key: 'revoke_nopasswd', suffix: 'revoke_nopasswd' },
  { key: 'notify_owner', suffix: 'notify_owner' },
  { key: 'lock_account', suffix: 'lock_account' },
  { key: 'flag_review', suffix: 'flag_review' },
]

const STATUS_COLORS: Record<string, string> = {
  pending_approval: 'orange',
  approved: 'blue',
  executing: 'processing',
  done: 'success',
  rejected: 'default',
  failed: 'error',
}

const STATUS_ICONS: Record<string, React.ReactNode> = {
  pending_approval: <ClockCircleOutlined />,
  approved: <CheckCircleOutlined />,
  done: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
  rejected: <CloseCircleOutlined />,
  failed: <CloseCircleOutlined style={{ color: '#ff4d4f' }} />,
}

export default function Playbooks() {
  const { t } = useTranslation()
  const [playbooks, setPlaybooks] = useState<Playbook[]>([])
  const [executions, setExecutions] = useState<PlaybookExecution[]>([])
  const [loading, setLoading] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [activePb, setActivePb] = useState<Playbook | null>(null)
  const [execDrawerOpen, setExecDrawerOpen] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingPb, setEditingPb] = useState<Playbook | null>(null)
  const [executeSnapshotId, setExecuteSnapshotId] = useState<number | null>(null)
  const [executeModalOpen, setExecuteModalOpen] = useState(false)
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)

  const loadPlaybooks = () => {
    setLoading(true)
    api.get<Playbook[]>('/playbooks').then(r => setPlaybooks(r.data))
      .catch(() => message.error(t('playbooks.loadFailed')))
      .finally(() => setLoading(false))
  }

  const loadExecutions = () => {
    api.get<PlaybookExecution[]>('/playbook-executions', { params: { limit: 50 } })
      .then(r => setExecutions(r.data))
      .catch(() => {})
  }

  useEffect(() => { loadPlaybooks(); loadExecutions() }, [])

  // Derived options — rebuilt whenever language changes so t() picks up the right locale
  const actionOptions = _ACTION_KEYS.map(a => ({
    value: a.key,
    label: `${t(`playbooks.action.${a.suffix}`)} (${a.suffix})`,
  }))

  const openNew = () => {
    setEditingPb(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEdit = (pb: Playbook) => {
    setEditingPb(pb)
    // Use translated name/description from i18n keys; fall back to raw DB value
    const displayName = pb.name_key ? t(pb.name_key) : pb.name
    const displayDesc = pb.description_key ? t(pb.description_key) : (pb.description ?? '')
    form.setFieldsValue({
      name: displayName,
      description: displayDesc,
      trigger_type: pb.trigger_type,
      approval_required: pb.approval_required,
      enabled: pb.enabled,
      steps: pb.steps,
    })
    setModalOpen(true)
  }

  const savePlaybook = async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      if (editingPb) {
        // Keep name_key/description_key if this is a built-in template
        const payload: Record<string, unknown> = { ...values }
        if (editingPb.name_key) {
          payload.name_key = editingPb.name_key
          payload.description_key = editingPb.description_key
        }
        await api.put(`/playbooks/${editingPb.id}`, payload)
        message.success(t('playbooks.updated'))
      } else {
        await api.post('/playbooks', values)
        message.success(t('playbooks.created'))
      }
      setModalOpen(false)
      loadPlaybooks()
    } catch {
      message.error(t('playbooks.saveFailed'))
    } finally {
      setSaving(false)
    }
  }

  const deletePlaybook = async (id: number) => {
    await api.delete(`/playbooks/${id}`)
    message.success(t('playbooks.deleted'))
    loadPlaybooks()
  }

  const handleExecute = async () => {
    if (!activePb || !executeSnapshotId) return
    setSaving(true)
    try {
      const r = await api.post<PlaybookExecution>(
        `/playbooks/${activePb.id}/execute`,
        null,
        { params: { snapshot_id: executeSnapshotId } },
      )
      message.success(r.data.status === 'pending_approval'
        ? t('playbooks.executionPending')
        : t('playbooks.executed'))
      setExecuteModalOpen(false)
      setExecDrawerOpen(false)
      loadExecutions()
    } catch {
      message.error(t('playbooks.executeFailed'))
    } finally {
      setSaving(false)
    }
  }

  const handleApprove = async (execId: number) => {
    try {
      const r = await api.post<PlaybookExecution>(`/playbook-executions/${execId}/approve`)
      message.success(t('playbooks.approved'))
      loadExecutions()
    } catch {
      message.error(t('playbooks.approveFailed'))
    }
  }

  const handleReject = async (execId: number) => {
    try {
      await api.post(`/playbook-executions/${execId}/reject`)
      message.success(t('playbooks.rejected'))
      loadExecutions()
    } catch {
      message.error(t('playbooks.rejectFailed'))
    }
  }

  const pbColumns = [
    {
      title: t('playbooks.name'),
      dataIndex: 'name',
      key: 'name',
      render: (_: string, pb: Playbook) => {
        const displayName = pb.name_key ? t(pb.name_key) : pb.name
        return (
          <Space>
            <Text strong>{displayName}</Text>
            {!pb.enabled && <Tag>{t('playbooks.disabled')}</Tag>}
            {pb.approval_required && <Tag color="blue">{t('playbooks.requiresApproval')}</Tag>}
          </Space>
        )
      },
    },
    {
      title: t('playbooks.triggerType'),
      dataIndex: 'trigger_type',
      key: 'trigger_type',
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: t('playbooks.steps'),
      key: 'steps',
      render: (_: unknown, pb: Playbook) => (
        <Space wrap>
          {(pb.steps || []).map((s, i) => (
            <Tag key={i}>{s.action}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: t('playbooks.actions'),
      key: 'actions',
      render: (_: unknown, pb: Playbook) => (
        <Space>
          <Button size="small" icon={<PlayCircleOutlined />} onClick={() => { setActivePb(pb); setExecuteModalOpen(true) }}>
            {t('playbooks.execute')}
          </Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(pb)} />
          <Popconfirm title={t('playbooks.confirmDelete')} onConfirm={() => deletePlaybook(pb.id)}>
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const execColumns = [
    {
      title: t('playbooks.playbook'),
      key: 'playbook',
      render: (_: unknown, e: PlaybookExecution) => {
        const pb = playbooks.find(p => p.id === e.playbook_id)
        const displayName = pb?.name_key ? t(pb.name_key) : (pb?.name || `#${e.playbook_id}`)
        return <Text>{displayName}</Text>
      },
    },
    {
      title: t('playbooks.snapshotId'),
      dataIndex: 'snapshot_id',
      key: 'snapshot_id',
    },
    {
      title: t('playbooks.status'),
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => (
        <Space>
          {STATUS_ICONS[s]}
          <Tag color={STATUS_COLORS[s]}>{s}</Tag>
        </Space>
      ),
    },
    {
      title: t('playbooks.result'),
      dataIndex: 'result',
      key: 'result',
      render: (r: string) => r ? <Text type="secondary" style={{ fontSize: 12 }}>{r}</Text> : '—',
    },
    {
      title: t('playbooks.createdAt'),
      dataIndex: 'created_at',
      key: 'created_at',
      render: (d: string) => new Date(d).toLocaleString(),
    },
    {
      title: t('playbooks.actions'),
      key: 'actions',
      render: (_: unknown, e: PlaybookExecution) =>
        e.status === 'pending_approval' ? (
          <Space>
            <Button size="small" type="primary" onClick={() => handleApprove(e.id)}>
              {t('playbooks.approve')}
            </Button>
            <Button size="small" danger onClick={() => handleReject(e.id)}>
              {t('playbooks.reject')}
            </Button>
          </Space>
        ) : null,
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>{t('playbooks.title')}</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openNew}>
          {t('playbooks.create')}
        </Button>
      </Space>

      <Alert
        message={t('playbooks.description')}
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />

      <Card title={t('playbooks.list')} style={{ marginBottom: 16 }}>
        <Table
          dataSource={playbooks}
          columns={pbColumns}
          rowKey="id"
          loading={loading}
          size="small"
          pagination={false}
        />
      </Card>

      <Card title={t('playbooks.executions')}>
        <Table
          dataSource={executions}
          columns={execColumns}
          rowKey="id"
          size="small"
          pagination={{ pageSize: 10 }}
        />
      </Card>

      {/* Create/Edit Modal */}
      <Modal
        open={modalOpen}
        title={editingPb ? t('playbooks.edit') : t('playbooks.create')}
        onCancel={() => setModalOpen(false)}
        onOk={savePlaybook}
        okText={t('common.save')}
        confirmLoading={saving}
        width={600}
      >
        <Form form={form} layout="vertical" initialValues={{ approval_required: true, enabled: true }}>
          <Form.Item name="name" label={t('playbooks.name')} rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label={t('playbooks.description')}>
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="trigger_type" label={t('playbooks.triggerType')} initialValue="manual">
            <Select options={[
              { value: 'manual', label: t('playbooks.trigger.manual') },
              { value: 'alert', label: t('playbooks.trigger.alert') },
              { value: 'schedule', label: t('playbooks.trigger.schedule') },
            ]} />
          </Form.Item>
          <Form.Item label={t('playbooks.steps')} name="steps">
            <Form.List name="steps">
              {(fields, { add, remove }) => (
                <>
                  {fields.map(({ key, name }) => (
                    <Card key={key} size="small" style={{ marginBottom: 8 }}>
                      <Space align="start">
                        <Form.Item name={[name, 'action']} label={t('playbooks.action')} rules={[{ required: true }]}>
                          <Select style={{ width: 200 }} options={actionOptions} />
                        </Form.Item>
                        <Form.Item name={[name, 'target']} label={t('playbooks.target')}>
                          <Select style={{ width: 120 }} options={[
                            { value: 'snapshot', label: t('playbooks.target.snapshot') },
                            { value: 'identity', label: t('playbooks.target.identity') },
                            { value: 'asset', label: t('playbooks.target.asset') },
                          ]} />
                        </Form.Item>
                        <Button size="small" danger onClick={() => remove(name)}>
                          {t('common.delete')}
                        </Button>
                      </Space>
                    </Card>
                  ))}
                  <Button type="dashed" onClick={() => add({ action: 'disable_account', target: 'snapshot' })} block>
                    + {t('playbooks.addStep')}
                  </Button>
                </>
              )}
            </Form.List>
          </Form.Item>
          <Form.Item name="approval_required" valuePropName="checked" label={t('playbooks.approvalRequired')}>
            <Select options={[
              { value: true, label: t('playbooks.approval.yes') },
              { value: false, label: t('playbooks.approval.no') },
            ]} />
          </Form.Item>
          <Form.Item name="enabled" valuePropName="checked" label={t('common.enabled')}>
            <Select options={[
              { value: true, label: t('playbooks.enabled') },
              { value: false, label: t('playbooks.disabled') },
            ]} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Execute Modal */}
      <Modal
        open={executeModalOpen}
        title={t('playbooks.execute')} onCancel={() => setExecuteModalOpen(false)}
        onOk={handleExecute} okText={t('playbooks.execute')} confirmLoading={saving}
      >
        <Paragraph>{t('playbooks.executeHint', { name: activePb?.name })}</Paragraph>
        <Form.Item label={t('playbooks.targetSnapshotId')} required>
          <Input
            type="number"
            value={executeSnapshotId || undefined}
            onChange={e => setExecuteSnapshotId(parseInt(e.target.value) || null)}
            placeholder={t('playbooks.snapshotIdPlaceholder')}
          />
        </Form.Item>
      </Modal>
    </div>
  )
}
