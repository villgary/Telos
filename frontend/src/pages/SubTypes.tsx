import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Table, Button, Space, Typography, Drawer, Form, Input, Select,
  message, Popconfirm, Tag, Card, Row, Col,
} from 'antd'
import {
  PlusOutlined, EditOutlined, DeleteOutlined,
} from '@ant-design/icons'
import api from '../api/client'

const { Title, Text } = Typography
const { Option } = Select

interface SubTypeDef {
  id: number
  slug: string
  name: string
  description?: string
  sub_type_kind: 'network' | 'iot' | 'database' | 'os' | 'cloud'
  icon?: string
  color?: string
  sort_order: number
}

const KIND_COLOR_FALLBACK: Record<string, string> = {
  network: 'blue',
  iot: 'green',
  database: 'purple',
  os: 'orange',
  cloud: 'cyan',
}

function getKindLabel(kind: string, t: (k: string) => string): string {
  const key = `subtype.kind.${kind}`
  const translated = t(key)
  if (translated && translated !== key) return translated
  // Hardcoded fallbacks - these should match zh-CN translations
  const zhDefaults: Record<string, string> = {
    network: '网络厂商',
    iot: 'IoT设备类型',
    database: '数据库类型',
    os: '操作系统类型',
    cloud: '云服务商',
  }
  return zhDefaults[kind] || kind
}

function getKindColor(kind: string, subTypes: SubTypeDef[]): string {
  const first = subTypes.find(s => s.sub_type_kind === kind && s.color)
  return first?.color || KIND_COLOR_FALLBACK[kind] || '#999'
}

export default function SubTypes() {
  const { t } = useTranslation()
  const [subTypes, setSubTypes] = useState<SubTypeDef[]>([])
  const [loading, setLoading] = useState(true)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editSubType, setEditSubType] = useState<SubTypeDef | null>(null)
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)

  const fetchSubTypes = () => {
    setLoading(true)
    api.get('/sub-types')
      .then(r => setSubTypes(r.data))
      .catch(() => message.error(t('subtype.loadError') || 'Failed to load sub-types'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchSubTypes() }, [])

  const openEdit = (st: SubTypeDef) => {
    setEditSubType(st)
    form.setFieldsValue({
      name: st.name,
      description: st.description,
      sub_type_kind: st.sub_type_kind,
      color: st.color,
      sort_order: st.sort_order,
    })
    setDrawerOpen(true)
  }

  const openAdd = () => {
    setEditSubType(null)
    form.resetFields()
    setDrawerOpen(true)
  }

  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)
      if (editSubType) {
        await api.put(`/sub-types/${editSubType.id}`, values)
        message.success(t('subtype.updated') || 'Sub-type updated')
      } else {
        await api.post('/sub-types', { ...values, slug: values.slug || values.name.toLowerCase().replace(/\s+/g, '_') })
        message.success(t('subtype.created') || 'Sub-type created')
      }
      setDrawerOpen(false)
      form.resetFields()
      fetchSubTypes()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('subtype.saveError') || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/sub-types/${id}`)
      message.success(t('subtype.deleted') || 'Sub-type deleted')
      fetchSubTypes()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('subtype.deleteError') || 'Delete failed')
    }
  }

  const columns = [
    {
      title: t('subtype.column.name'),
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: SubTypeDef) => (
        <Space>
          <Tag color={record.color || '#999'}>{name}</Tag>
        </Space>
      ),
    },
    {
      title: t('subtype.column.slug'),
      dataIndex: 'slug',
      key: 'slug',
      render: (slug: string) => <Tag>{slug}</Tag>,
    },
    {
      title: t('subtype.column.kind'),
      dataIndex: 'sub_type_kind',
      key: 'sub_type_kind',
      render: (kind: string) => (
        <Tag color={getKindColor(kind, subTypes) || 'default'}>{getKindLabel(kind, t)}</Tag>
      ),
    },
    {
      title: t('subtype.column.description'),
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: t('subtype.column.sortOrder'),
      dataIndex: 'sort_order',
      key: 'sort_order',
    },
    {
      title: t('subtype.column.actions'),
      key: 'actions',
      width: 120,
      render: (_: unknown, record: SubTypeDef) => (
        <Space size="small">
          <Button size="small" type="text" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Popconfirm
            title={t('subtype.deleteConfirm')}
            onConfirm={() => handleDelete(record.id)}
            okText={t('btn.delete')}
            okButtonProps={{ danger: true, size: 'small' }}
            cancelText={t('btn.cancel')}
          >
            <Button size="small" type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  // Group sub-types by kind
  const grouped = {
    network: subTypes.filter(s => s.sub_type_kind === 'network'),
    iot: subTypes.filter(s => s.sub_type_kind === 'iot'),
    database: subTypes.filter(s => s.sub_type_kind === 'database'),
    os: subTypes.filter(s => s.sub_type_kind === 'os'),
    cloud: subTypes.filter(s => s.sub_type_kind === 'cloud'),
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>{t('subtype.title') || 'Sub-Types'}</Title>
          <Text type="secondary" style={{ fontSize: 13 }}>
            {t('subtype.subtitle') || 'Manage network vendors, IoT types, DB types, and OS types'}
          </Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>
          {t('btn.addSubType') || 'Add Sub-Type'}
        </Button>
      </div>

      {loading ? (
        <Card><Text type="secondary">{t('subtype.loading')}</Text></Card>
      ) : (
        <Row gutter={16}>
          {(['network', 'iot', 'database', 'os', 'cloud'] as const).map(kind => (
            <Col span={6} key={kind}>
              <Card
                title={<Tag color={getKindColor(kind, subTypes)}>{getKindLabel(kind, t)}</Tag>}
                size="small"
                style={{ marginBottom: 16 }}
              >
                {grouped[kind].length === 0 ? (
                  <Text type="secondary" style={{ fontSize: 12 }}>{t('subtype.noItems', { kind: getKindLabel(kind, t) })}</Text>
                ) : (
                  grouped[kind].map(st => (
                    <div key={st.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0', borderBottom: '1px solid #f0f0f0' }}>
                      <Space>
                        <Tag color={st.color || '#999'} style={{ marginRight: 4 }}>{st.name}</Tag>
                      </Space>
                      <Space size="small">
                        <Button size="small" type="text" icon={<EditOutlined />} onClick={() => openEdit(st)} />
                        <Popconfirm
                          title={t('subtype.deleteConfirmShort')}
                          onConfirm={() => handleDelete(st.id)}
                          okText={t('btn.delete')}
                          okButtonProps={{ danger: true, size: 'small' }}
                          cancelText={t('btn.cancel')}
                        >
                          <Button size="small" type="text" danger icon={<DeleteOutlined />} />
                        </Popconfirm>
                      </Space>
                    </div>
                  ))
                )}
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Drawer
        title={editSubType ? t('subtype.drawer.edit') : t('subtype.drawer.add')}
        open={drawerOpen}
        onClose={() => { setDrawerOpen(false); form.resetFields() }}
        width={400}
      >
        <Form form={form} layout="vertical" onFinish={handleSave}>
          <Form.Item
            name="name"
            label={t('subtype.form.name')}
            rules={[{ required: true, message: t('subtype.form.nameRequired') || 'Name is required' }]}
          >
            <Input placeholder={t('subtype.form.namePlaceholder')} />
          </Form.Item>

          <Form.Item
            name="slug"
            label={t('subtype.form.slug')}
            extra={t('subtype.form.slugHint')}
          >
            <Input placeholder={t('subtype.form.slugPlaceholder')} disabled={!!editSubType} />
          </Form.Item>

          <Form.Item
            name="sub_type_kind"
            label={t('subtype.form.kind')}
            rules={[{ required: true, message: t('subtype.form.kindRequired') || 'Kind is required' }]}
          >
            <Select placeholder={t('subtype.form.kindPlaceholder') || 'Select kind'}>
              <Option value="network">{t('subtype.networkVendor')}</Option>
              <Option value="iot">{t('subtype.iotDeviceType')}</Option>
              <Option value="database">{t('subtype.dbType')}</Option>
              <Option value="os">{t('subtype.osType')}</Option>
              <Option value="cloud">{t('subtype.cloudProvider')}</Option>
            </Select>
          </Form.Item>

          <Form.Item name="color" label={t('subtype.form.color')}>
            <Input type="color" style={{ width: 100, height: 32 }} defaultValue="#1890ff" />
          </Form.Item>

          <Form.Item name="description" label={t('subtype.form.description')}>
            <Input.TextArea placeholder={t('subtype.form.descriptionPlaceholder')} />
          </Form.Item>

          <Form.Item name="sort_order" label={t('subtype.form.sortOrder')}>
            <Input type="number" placeholder={t('subtype.form.sortOrderPlaceholder')} />
          </Form.Item>

          <Form.Item style={{ marginTop: 24 }}>
            <Space>
              <Button type="primary" htmlType="submit" loading={saving}>
                {editSubType ? t('btn.update') : t('btn.create')}
              </Button>
              <Button onClick={() => { setDrawerOpen(false); form.resetFields() }}>
                {t('btn.cancel')}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Drawer>
    </div>
  )
}
