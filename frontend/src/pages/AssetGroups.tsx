import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Table, Button, Space, Tag, Typography, Drawer, Form, Input, Popconfirm, message,
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons'
import api from '../api/client'

const { Title } = Typography

interface Asset {
  id: number
  asset_code: string
  ip: string
  hostname?: string
  asset_category: string
  status: string
  port: number
  group_id?: number
}

interface AssetGroup {
  id: number
  name: string
  description?: string
  color: string
  created_by?: number
  created_at: string
}

const ASSET_CATEGORY_LABEL: Record<string, string> = {
  server: 'Server',
  database: 'Database',
  network: 'Network',
  iot: 'IoT',
}

const ASSET_STATUS_COLOR: Record<string, string> = {
  online: 'green',
  offline: 'red',
  auth_failed: 'orange',
  untested: 'default',
}

export default function AssetGroups() {
  const { t } = useTranslation()
  const [groups, setGroups] = useState<AssetGroup[]>([])
  const [loading, setLoading] = useState(true)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editGroup, setEditGroup] = useState<AssetGroup | null>(null)
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)
  const [expandedRowKeys, setExpandedRowKeys] = useState<React.Key[]>([])
  // groupId -> assets list
  const [groupAssets, setGroupAssets] = useState<Record<number, Asset[]>>({})
  const [loadingAssets, setLoadingAssets] = useState<Record<number, boolean>>({})

  const fetchGroups = () => {
    setLoading(true)
    api.get('/asset-groups')
      .then(r => setGroups(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchGroups() }, [])

  // Fetch assets for a specific group
  const fetchGroupAssets = (groupId: number) => {
    if (groupAssets[groupId]) return  // already loaded
    setLoadingAssets(prev => ({ ...prev, [groupId]: true }))
    api.get('/assets', { params: { group_id: groupId } })
      .then(r => {
        setGroupAssets(prev => ({ ...prev, [groupId]: r.data }))
      })
      .catch(console.error)
      .finally(() => {
        setLoadingAssets(prev => ({ ...prev, [groupId]: false }))
      })
  }

  const handleRowExpand = (expanded: boolean, record: AssetGroup) => {
    const newKeys = expanded
      ? [...expandedRowKeys, record.id]
      : expandedRowKeys.filter(k => k !== record.id)
    setExpandedRowKeys(newKeys)
    if (expanded) {
      fetchGroupAssets(record.id)
    }
  }

  const openAdd = () => {
    setEditGroup(null)
    form.resetFields()
    setDrawerOpen(true)
  }

  const openEdit = (g: AssetGroup) => {
    setEditGroup(g)
    form.setFieldsValue({ name: g.name, description: g.description, color: g.color })
    setDrawerOpen(true)
  }

  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)
      if (editGroup) {
        await api.put(`/asset-groups/${editGroup.id}`, values)
        message.success(t('group.updated'))
      } else {
        await api.post('/asset-groups', values)
        message.success(t('group.created'))
      }
      setDrawerOpen(false)
      fetchGroups()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.saveFailed'))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/asset-groups/${id}`)
      message.success(t('group.deleted'))
      fetchGroups()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.deleteFailed'))
    }
  }

  const PRESET_COLORS = [
    '#1890ff', '#52c41a', '#faad14', '#f5222d',
    '#722ed1', '#13c2c2', '#eb2f96', '#fa8c16',
  ]

  const columns = [
    {
      title: t('group.color'),
      key: 'color',
      width: 80,
      render: (_: unknown, r: AssetGroup) => (
        <div style={{ width: 20, height: 20, borderRadius: 4, background: r.color }} />
      ),
    },
    { title: t('group.name'), dataIndex: 'name', key: 'name' },
    {
      title: t('table.description'),
      dataIndex: 'description',
      key: 'description',
      render: (v?: string) => v || '-',
    },
    {
      title: t('group.preview'),
      render: (_: unknown, r: AssetGroup) => <Tag color={r.color}>{r.name}</Tag>,
    },
    {
      title: t('table.actions'),
      key: 'actions',
      render: (_: unknown, record: AssetGroup) => (
        <Space size="small">
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Popconfirm
            title={t('group.confirmDelete')}
            onConfirm={() => handleDelete(record.id)}
            okText={t('btn.delete')}
            cancelText={t('btn.cancel')}
          >
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  // Columns for the expanded asset sub-table
  const assetColumns = [
    {
      title: t('table.assetCode'),
      dataIndex: 'asset_code',
      key: 'asset_code',
      width: 110,
      render: (v: string) => <Tag color="blue">{v}</Tag>,
    },
    { title: 'IP', dataIndex: 'ip', key: 'ip', width: 150 },
    {
      title: t('table.hostname'),
      dataIndex: 'hostname',
      key: 'hostname',
      width: 150,
      render: (v?: string) => v || '-',
    },
    {
      title: t('table.type'),
      dataIndex: 'asset_category',
      key: 'asset_category',
      width: 100,
      render: (v: string) => ASSET_CATEGORY_LABEL[v] || v,
    },
    {
      title: t('table.status'),
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (v: string) => (
        <Tag color={ASSET_STATUS_COLOR[v] || 'default'}>
          {t(`status.${v}`)}
        </Tag>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>{t('group.title')}</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>
          {t('btn.createGroup')}
        </Button>
      </div>

      <Table
        dataSource={groups}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={false}
        expandable={{
          expandedRowKeys,
          onExpand: handleRowExpand,
          expandedRowRender: (record: AssetGroup) => {
            const assets = groupAssets[record.id] || []
            const loadingGroup = loadingAssets[record.id]
            return (
              <Table
                dataSource={assets}
                columns={assetColumns}
                rowKey="id"
                pagination={false}
                loading={loadingGroup}
                size="small"
                style={{ marginLeft: 40, marginRight: 20 }}
                locale={{ emptyText: t('group.noAssets') }}
              />
            )
          },
          rowExpandable: () => true,
        }}
      />

      <Drawer
        title={editGroup ? t('group.editTitle') : t('group.addTitle')}
        onClose={() => setDrawerOpen(false)}
        open={drawerOpen}
        width={360}
        footer={
          <div style={{ textAlign: 'right' }}>
            <Button onClick={() => setDrawerOpen(false)} style={{ marginRight: 8 }}>{t('btn.cancel')}</Button>
            <Button type="primary" onClick={handleSave} loading={saving}>
              {t('btn.save')}
            </Button>
          </div>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label={t('group.groupName')} rules={[{ required: true, message: t('group.enterName') }]}>
            <Input placeholder={t('group.namePlaceholder')} maxLength={128} />
          </Form.Item>
          <Form.Item name="description" label={t('group.descriptionOptional')}>
            <Input.TextArea placeholder={t('group.descPlaceholder')} rows={3} maxLength={512} />
          </Form.Item>
          <Form.Item name="color" label={t('group.colorLabel')} rules={[{ required: true }]}>
            <Space wrap>
              {PRESET_COLORS.map(c => (
                <div
                  key={c}
                  onClick={() => form.setFieldValue('color', c)}
                  style={{
                    width: 28, height: 28, borderRadius: 4, background: c, cursor: 'pointer',
                    border: form.getFieldValue('color') === c ? '2px solid #333' : '2px solid transparent',
                  }}
                />
              ))}
            </Space>
          </Form.Item>
        </Form>
      </Drawer>
    </div>
  )
}
