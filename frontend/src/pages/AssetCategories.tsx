import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Tree, Button, Space, Typography, Drawer, Form, Input, Select,
  message, Popconfirm, Tag, Divider,
} from 'antd'
import type { DataNode } from 'antd/es/tree'
import {
  PlusOutlined, EditOutlined, DeleteOutlined, CloudServerOutlined,
  DatabaseOutlined, GlobalOutlined, AppstoreOutlined, CameraOutlined,
  FolderOutlined, SafetyCertificateOutlined, CloudOutlined, DesktopOutlined,
} from '@ant-design/icons'
import api from '../api/client'

const { Title, Text } = Typography
const { Option } = Select

interface AssetCategoryDef {
  id: number
  slug: string
  name: string
  name_i18n_key?: string
  description?: string
  icon?: string
  sub_type_kind: string
  parent_id: number | null
  children?: AssetCategoryDef[]
}

const ICON_MAP: Record<string, React.ReactNode> = {
  CloudServerOutlined:       <CloudServerOutlined />,
  DatabaseOutlined:          <DatabaseOutlined />,
  GlobalOutlined:           <GlobalOutlined />,
  CameraOutlined:          <CameraOutlined />,
  AppstoreOutlined:        <AppstoreOutlined />,
  SafetyCertificateOutlined:<SafetyCertificateOutlined />,
  CloudOutlined:           <CloudOutlined />,
  DesktopOutlined:         <DesktopOutlined />,
}

const ICON_OPTIONS: Array<{ value: string; i18nKey: string }> = [
  { value: 'CloudServerOutlined',         i18nKey: 'icon.server' },
  { value: 'DatabaseOutlined',             i18nKey: 'icon.database' },
  { value: 'GlobalOutlined',              i18nKey: 'icon.network' },
  { value: 'CameraOutlined',              i18nKey: 'icon.camera' },
  { value: 'AppstoreOutlined',            i18nKey: 'icon.app' },
  { value: 'SafetyCertificateOutlined',   i18nKey: 'icon.security' },
  { value: 'CloudOutlined',               i18nKey: 'icon.cloud' },
  { value: 'DesktopOutlined',             i18nKey: 'icon.desktop' },
]

export default function AssetCategories() {
  const { t } = useTranslation()
  const [flatCategories, setFlatCategories] = useState<AssetCategoryDef[]>([])
  const [treeData, setTreeData] = useState<DataNode[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([])
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editCat, setEditCat] = useState<AssetCategoryDef | null>(null)
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)

  const fetchTree = () => {
    setLoading(true)
    // Fetch both tree and flat list in parallel
    Promise.all([
      api.get('/asset-categories/tree'),
      api.get('/asset-categories'),
    ]).then(([treeRes, flatRes]: [any, any]) => {
        setFlatCategories(flatRes.data)
        const convert = (cats: AssetCategoryDef[]): DataNode[] =>
          cats.map(cat => ({
            key: cat.id,
            title: (
              <Space size={4}>
                <span style={{ fontSize: 16, color: '#1677ff' }}>
                  {cat.icon ? ICON_MAP[cat.icon] || <FolderOutlined /> : <FolderOutlined />}
                </span>
                <span style={{ fontWeight: 500 }}>{cat.name}</span>
                <Tag color="blue" style={{ fontSize: 11 }}>{cat.slug}</Tag>
                {cat.sub_type_kind && cat.sub_type_kind !== 'none' && (
                  <Tag style={{ fontSize: 11 }}>{cat.sub_type_kind}</Tag>
                )}
                <Space size={2} onClick={e => e.stopPropagation()}>
                  <Button
                    size="small" type="text" icon={<PlusOutlined />}
                    onClick={() => openAdd(cat.id)}
                    title={t('btn.addChild')}
                  />
                  <Button
                    size="small" type="text" icon={<EditOutlined />}
                    onClick={() => openEdit(cat)}
                    title={t('btn.edit')}
                  />
                  <Popconfirm
                    title={t('category.confirmDelete')}
                    onConfirm={() => handleDelete(cat.id)}
                    okText={t('btn.delete')}
                    okButtonProps={{ danger: true, size: 'small' }}
                    cancelText={t('btn.cancel')}
                  >
                    <Button size="small" type="text" danger icon={<DeleteOutlined />} title={t('btn.delete')} />
                  </Popconfirm>
                </Space>
              </Space>
            ),
            children: cat.children?.length ? convert(cat.children) : undefined,
          }))
        setTreeData(convert(treeRes.data))
        // Expand all by default
        const allKeys = (cats: AssetCategoryDef[]): React.Key[] =>
          cats.flatMap(c => [c.id, ...(c.children ? allKeys(c.children) : [])])
        setExpandedKeys(allKeys(treeRes.data))
      })
      .catch(() => message.error(t('msg.loadFailedAdmin')))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchTree() }, [])

  const openEdit = (cat: AssetCategoryDef) => {
    setEditCat(cat)
    form.setFieldsValue({
      name: cat.name,
      description: cat.description,
      icon: cat.icon,
      sub_type_kind: cat.sub_type_kind,
      parent_id: cat.parent_id,
    })
    setDrawerOpen(true)
  }

  const openAdd = (parentId?: number) => {
    setEditCat(null)
    form.resetFields()
    if (parentId !== undefined) {
      form.setFieldsValue({ parent_id: parentId })
    }
    setDrawerOpen(true)
  }

  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)
      if (editCat) {
        await api.put(`/asset-categories/${editCat.id}`, values)
        message.success(t('category.updated'))
      } else {
        await api.post('/asset-categories', values)
        message.success(t('category.created'))
      }
      setDrawerOpen(false)
      form.resetFields()
      fetchTree()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.saveFailed'))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/asset-categories/${id}`)
      message.success(t('msg.deleted'))
      fetchTree()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.deleteFailed'))
    }
  }

  // Parent options: flat list, indented by depth
  const getDepth = (id: number, cats: AssetCategoryDef[], depth = 0): number => {
    for (const c of cats) {
      if (c.id === id) return depth
      if (c.children) {
        const found = getDepth(id, c.children, depth + 1)
        if (found >= 0) return found
      }
    }
    return -1
  }

  const flatCats: Array<{ cat: AssetCategoryDef; depth: number }> = []
  const flatten = (cats: AssetCategoryDef[], depth = 0) => {
    for (const c of cats) {
      flatCats.push({ cat: c, depth })
      if (c.children) flatten(c.children, depth + 1)
    }
  }
  flatten(flatCategories.length > 0 ? flatCategories : [])

  // Get parent label for display
  const getParentLabel = (parentId: number | null) => {
    if (!parentId) return t('category.rootCategory')
    const all: AssetCategoryDef[] = flatCategories
    const find = (cats: AssetCategoryDef[]): AssetCategoryDef | null => {
      for (const c of cats) {
        if (c.id === parentId) return c
        if (c.children) { const f = find(c.children); if (f) return f }
      }
      return null
    }
    const found = find(all)
    return found ? `${found.name} (${found.slug})` : `ID ${parentId}`
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>{t('category.title')}</Title>
          <Text type="secondary" style={{ fontSize: 13 }}>{t('category.subtitle')}</Text>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => openAdd()}>
          {t('btn.addCategory')}
        </Button>
      </div>

      <div
        style={{
          background: '#fff',
          border: '1px solid #f0f0f0',
          borderRadius: 8,
          padding: '16px 8px',
          minHeight: 400,
        }}
      >
        {loading ? (
          <div style={{ textAlign: 'center', padding: 48, color: '#999' }}>
            {t('msg.loading')}
          </div>
        ) : (
          <Tree
            treeData={treeData}
            expandedKeys={expandedKeys}
          onExpand={keys => setExpandedKeys(keys)}
          showLine={{ showLeafIcon: false }}
          blockNode
          style={{ minHeight: 360 }}
        />
        )}
        {!loading && treeData.length === 0 && (
          <div style={{ textAlign: 'center', padding: 48, color: '#999' }}>
            {t('category.noCategories')}
          </div>
        )}
      </div>

      <Drawer
        title={editCat ? t('category.editTitle', { name: editCat.name }) : t('category.addTitle')}
        onClose={() => { setDrawerOpen(false); form.resetFields() }}
        open={drawerOpen}
        width={440}
        footer={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            {editCat && (
              <Popconfirm
                title={t('category.confirmDelete')}
                onConfirm={() => { setDrawerOpen(false); handleDelete(editCat.id) }}
                okText={t('btn.delete')}
                okButtonProps={{ danger: true }}
                cancelText={t('btn.cancel')}
              >
                <Button danger size="small">{t('btn.deleteCategory')}</Button>
              </Popconfirm>
            )}
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
              <Button onClick={() => { setDrawerOpen(false); form.resetFields() }}>{t('btn.cancel')}</Button>
              <Button type="primary" onClick={handleSave} loading={saving}>{t('btn.save')}</Button>
            </div>
          </div>
        }
      >
        <Form form={form} layout="vertical">
          {editCat ? (
            <Form.Item label={t('category.slugImmutable')}>
              <Input value={editCat.slug} disabled />
            </Form.Item>
          ) : (
            <Form.Item
              name="slug"
              label={t('category.slug')}
              rules={[
                { required: true, message: t('category.enterSlug') },
                { pattern: /^[a-z0-9-]+$/, message: t('category.slugPattern') },
              ]}
              extra={t('category.slugExtra')}
            >
              <Input placeholder={t('category.slugPlaceholder')} maxLength={32} />
            </Form.Item>
          )}
          <Form.Item
            name="name"
            label={t('category.displayName')}
            rules={[{ required: true, message: t('category.enterName') }]}
          >
            <Input placeholder={t('category.namePlaceholder')} maxLength={64} />
          </Form.Item>
          <Form.Item
            name="parent_id"
            label={t('category.parentCategory')}
          >
            <Select
              placeholder={t('category.rootIfEmpty')}
              allowClear
              disabled={!editCat && form.getFieldValue('parent_id') === undefined}
            >
              {flatCats.map(({ cat, depth }) => (
                <Option key={cat.id} value={cat.id}>
                  {'　'.repeat(depth)}{cat.name}
                  {' '}<Text type="secondary">({cat.slug})</Text>
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            name="sub_type_kind"
            label={t('category.subtypeKind')}
            extra={t('category.subtypeExtra')}
          >
            <Input placeholder={t('category.subtypePlaceholder')} maxLength={64} />
          </Form.Item>
          <Form.Item name="description" label={t('table.description')}>
            <Input.TextArea rows={2} maxLength={256} />
          </Form.Item>
          <Form.Item name="icon" label={t('category.iconOptional')}>
            <Select placeholder={t('category.selectIcon')} allowClear>
              {ICON_OPTIONS.map(o => (
                <Option key={o.value} value={o.value}>
                  {ICON_MAP[o.value] || <FolderOutlined />} {t(o.i18nKey)}
                </Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Drawer>
    </div>
  )
}
