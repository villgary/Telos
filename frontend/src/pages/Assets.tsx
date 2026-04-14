import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Table, Button, Space, Tag, Typography, Drawer, Form, Input, Select,
  message, Popconfirm, Alert, Divider, Modal, List, Badge, Cascader,
} from 'antd'
const { Title, Text, Paragraph } = Typography
const { Option } = Select
import {
  PlusOutlined, ReloadOutlined, DeleteOutlined, EditOutlined,
  ThunderboltOutlined, SearchOutlined, ExportOutlined,
  RobotOutlined, UserOutlined,
} from '@ant-design/icons'
import api, { naturalLanguageSearch } from '../api/client'

interface Asset {
  id: number
  asset_code: string
  ip: string
  hostname?: string
  asset_category: 'server' | 'database' | 'network' | 'iot'
  asset_category_def_id?: number
  category_slug?: string
  os_type?: 'linux' | 'windows'
  db_type?: 'mysql' | 'postgresql' | 'redis' | 'mongodb' | 'mssql' | 'oracle'
  network_type?: 'cisco' | 'h3c' | 'huawei'
  iot_type?: 'camera' | 'nvr' | 'dvr' | 'sensor' | 'gateway' | 'other'
  group_id?: number
  port: number
  status: string
  last_scan_at?: string
  last_scan_job_id?: number
  credential_id: number
  created_at: string
}

interface Credential {
  id: number
  name: string
  auth_type: string
  username: string
  has_password: boolean
  has_private_key: boolean
}

interface AssetGroup {
  id: number
  name: string
  color: string
  description?: string
}

interface AssetCategoryDef {
  id: number
  slug: string
  name: string
  name_i18n_key?: string
  description?: string
  icon?: string
  sub_type_kind: 'none' | 'os' | 'database' | 'network' | 'iot'
  parent_id?: number | null
}

const STATUS_COLOR: Record<string, string> = {
  online: 'green',
  offline: 'red',
  auth_failed: 'orange',
  untested: 'default',
}

export default function Assets() {
  const { t } = useTranslation()
  const [assets, setAssets] = useState<Asset[]>([])
  const [credentials, setCredentials] = useState<Credential[]>([])
  const [groups, setGroups] = useState<AssetGroup[]>([])
  const [categories, setCategories] = useState<AssetCategoryDef[]>([])
  const [loading, setLoading] = useState(true)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editAsset, setEditAsset] = useState<Asset | null>(null)
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)
  const [testingId, setTestingId] = useState<number | null>(null)
  const [scanningId, setScanningId] = useState<number | null>(null)
  const [credLoading, setCredLoading] = useState(false)
  // Cascader options for category filter (loaded from tree API)
  const [catCascaderOptions, setCatCascaderOptions] = useState<any[]>([])

  // Drawer category state (controlled outside Form for reliable reactivity)
  const [drawerCategory, setDrawerCategory] = useState<string | undefined>()
  const [parentAssetId, setParentAssetId] = useState<number | undefined>()
  // Search & filter state
  const [searchQ, setSearchQ] = useState('')
  const [filterCategoryId, setFilterCategoryId] = useState<number | undefined>()
  const [filterStatus, setFilterStatus] = useState<string | undefined>()
  const [filterGroup, setFilterGroup] = useState<number | undefined>()
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [bulkDeleting, setBulkDeleting] = useState(false)

  // Natural language search state
  const [nlSearchOpen, setNlSearchOpen] = useState(false)
  const [nlQuery, setNlQuery] = useState('')
  const [nlLoading, setNlLoading] = useState(false)

  const STATUS_LABEL: Record<string, string> = {
    online: t('status.online'),
    offline: t('status.offline'),
    auth_failed: t('status.authFailed'),
    untested: t('status.untested'),
  }

  // Asset detail drawer state
  const [detailAsset, setDetailAsset] = useState<Asset | null>(null)
  const [detailDrawerOpen, setDetailDrawerOpen] = useState(false)
  const [detailAccounts, setDetailAccounts] = useState<any[]>([])
  const [detailLoading, setDetailLoading] = useState(false)

  const [nlResults, setNlResults] = useState<{
    query: string
    filter_explanation: string[]
    llm_powered: boolean
    total_found: number
    results: Array<{
      id: number
      asset_code: string
      ip: string
      hostname?: string
      asset_category: string
      status: string
      account_count: number
      admin_count: number
      latest_accounts: Array<{ id: number; username: string; is_admin: boolean; account_status: string | null; last_login: string | null }>
    }>
  } | null>(null)

  const EXAMPLES = [
    t('nlSearch.exampleUnloggedAdmin'),
    t('nlSearch.exampleLinuxRoot'),
    t('nlSearch.exampleMysqlFailed'),
    t('nlSearch.exampleOffline90d'),
    t('nlSearch.example192Network'),
    t('nlSearch.exampleOnlineAdmin'),
  ]

  const handleNlSearch = async (query?: string) => {
    const q = query ?? nlQuery
    if (!q.trim()) return
    setNlLoading(true)
    try {
      const r = await naturalLanguageSearch(q)
      setNlResults(r.data)
      if (query) setNlQuery(q)
    } catch {
      message.error(t('msg.searchFailed'))
    } finally {
      setNlLoading(false)
    }
  }

  const fetchAssets = () => {
    setLoading(true)
    const params: Record<string, string | number> = {}
    if (searchQ) params.q = searchQ
    if (filterCategoryId) params.category_id = filterCategoryId
    if (filterStatus) params.status = filterStatus
    if (filterGroup) params.group_id = filterGroup
    api.get('/assets', { params })
      .then(r => setAssets(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  const fetchCredentials = () => {
    setCredLoading(true)
    api.get('/credentials')
      .then(r => setCredentials(r.data))
      .catch(() => setCredentials([]))
      .finally(() => setCredLoading(false))
  }

  const fetchGroups = () => {
    api.get('/asset-groups')
      .then(r => setGroups(r.data))
      .catch(() => setGroups([]))
  }

  const fetchCategories = () => {
    api.get('/asset-categories')
      .then(r => setCategories(r.data))
      .catch(() => setCategories([]))
  }

  const fetchCatTree = () => {
    api.get('/asset-categories/tree')
      .then(r => {
        const convert = (nodes: any[]): any[] =>
          nodes.map(n => ({
            value: n.id,
            label: n.name,
            children: n.children?.length ? convert(n.children) : undefined,
          }))
        setCatCascaderOptions(convert(r.data))
      })
      .catch(() => setCatCascaderOptions([]))
  }

  // Build category tree from flat list (used by drawer form, not filter)
  const catMap = new Map<number, AssetCategoryDef>()
  categories.forEach(c => catMap.set(c.id, c))

  useEffect(() => {
    fetchAssets()
    fetchCredentials()
    fetchGroups()
    fetchCategories()
    fetchCatTree()
  }, [])

  const openAdd = () => {
    setEditAsset(null)
    setDrawerCategory(undefined)
    setParentAssetId(undefined)
    form.resetFields()
    setDrawerOpen(true)
  }

  const openEdit = (asset: Asset) => {
    setEditAsset(asset)
    setDrawerCategory(asset.category_slug || asset.asset_category)
    form.setFieldsValue({
      asset_category: asset.asset_category,
      ip: asset.ip,
      hostname: asset.hostname,
      asset_category_def_id: (asset as Asset & { asset_category_def_id?: number }).asset_category_def_id,
      os_type: asset.os_type,
      db_type: asset.db_type,
      network_type: asset.network_type,
      iot_type: (asset as Asset & { iot_type?: string }).iot_type,
      group_id: asset.group_id,
      port: asset.port || undefined,
      credential_id: asset.credential_id,
    })
    // Find this asset's parent relationship (if any)
    api.get('/asset-relationships', { params: { asset_id: asset.id } })
      .then(r => {
        const rel = r.data.find((rel: { child_id: number }) => rel.child_id === asset.id)
        setParentAssetId(rel?.parent_id)
      })
      .catch(() => setParentAssetId(undefined))
    setDrawerOpen(true)
  }

  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      if (!drawerCategory) {
        message.error(t('asset.selectCategory'))
        return
      }
      // Use category_slug for custom categories; backend derives asset_category enum from parent
      const payload = { ...values, category_slug: drawerCategory }
      setSaving(true)
      let assetId: number
      if (editAsset) {
        const r = await api.put(`/assets/${editAsset.id}`, payload)
        assetId = r.data.id
        message.success(t('asset.updated'))
      } else {
        const r = await api.post('/assets', payload)
        assetId = r.data.id
        message.success(t('asset.added'))
      }

      // Sync parent relationship
      // Find existing "child" relationship for this asset
      const relR = await api.get('/asset-relationships', { params: { asset_id: assetId } })
      const existingChildRel = relR.data.find(
        (rel: { child_id: number }) => rel.child_id === assetId
      ) as { id: number } | undefined

      if (parentAssetId && parentAssetId !== editAsset?.id) {
        if (existingChildRel) {
          // Already has a parent — update would need a different approach; just warn
          message.warning(t('asset.hasRelationship'))
        } else {
          await api.post('/asset-relationships', {
            parent_id: parentAssetId,
            child_id: assetId,
            relation_type: 'hosts_vm',
            description: t('asset.parentChildRelation'),
          })
        }
      } else if (!parentAssetId && existingChildRel) {
        await api.delete(`/asset-relationships/${existingChildRel.id}`)
      }

      setDrawerOpen(false)
      fetchAssets()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.saveFailed'))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/assets/${id}`)
      message.success(t('msg.deleted'))
      fetchAssets()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.deleteFailed'))
    }
  }

  const handleTest = async (asset: Asset) => {
    setTestingId(asset.id)
    try {
      const r = await api.post(`/assets/${asset.id}/test`)
      const { success, status: connStatus, error } = r.data as { success: boolean; status: string; error?: string }
      if (success) {
        message.success(t('msg.connectSuccess', { status: connStatus }))
      } else {
        message.warning(t('msg.connectFailed', { reason: error || connStatus }))
      }
      fetchAssets()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.testFailed'))
    } finally {
      setTestingId(null)
    }
  }

  const handleScan = async (asset: Asset) => {
    setScanningId(asset.id)
    try {
      const r = await api.post(`/scan-jobs?asset_id=${asset.id}`)
      const job = r.data as { id: number; status: string }
      if (job.status === 'success') {
        message.success(t('msg.scanSuccess', { count: (r.data as any).success_count ?? 0 }))
        fetchAssets()
        setScanningId(null)
        return
      }
      if (job.status === 'failed') {
        message.error(t('msg.scanFailed', { reason: (r.data as any).error_message || job.status }))
        setScanningId(null)
        return
      }
      // Poll until done
      let finalJob: { id: number; status: string; success_count?: number; error_message?: string } = job
      for (let i = 0; i < 30; i++) {
        await new Promise(r => setTimeout(r, 2000))
        try {
          const pr = await api.get(`/scan-jobs/${job.id}`)
          finalJob = pr.data as { id: number; status: string; success_count?: number; error_message?: string }
          if (finalJob.status === 'success' || finalJob.status === 'failed') break
        } catch { break }
      }
      if (finalJob.status === 'success') {
        message.success(t('msg.scanSuccess', { count: finalJob.success_count ?? 0 }))
      } else if (finalJob.status === 'failed') {
        message.error(t('msg.scanFailed', { reason: finalJob.error_message || finalJob.status }))
      }
      fetchAssets()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.scanFailed'))
    } finally {
      setScanningId(null)
    }
  }

  const handleBulkDelete = async () => {
    if (selectedRowKeys.length === 0) return
    setBulkDeleting(true)
    try {
      await api.post('/assets/bulk-delete', selectedRowKeys)
      message.success(t('msg.bulkDeleteSuccess', { count: selectedRowKeys.length }))
      setSelectedRowKeys([])
      fetchAssets()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.bulkDeleteFailed'))
    } finally {
      setBulkDeleting(false)
    }
  }

  const handleExportCSV = () => {
    const params: Record<string, string | number> = {}
    if (searchQ) params.q = searchQ
    if (filterCategoryId) params.category_id = filterCategoryId
    api.get('/assets/export.csv', { params, responseType: 'blob' })
      .then(r => {
        const url = URL.createObjectURL(new Blob([r.data], { type: 'text/csv' }))
        const a = document.createElement('a')
        a.href = url
        a.download = 'assets.csv'
        a.click()
        URL.revokeObjectURL(url)
      })
      .catch(() => message.error(t('msg.exportFailed')))
  }

  const getGroupName = (groupId?: number) => {
    if (!groupId) return null
    const g = groups.find(g => g.id === groupId)
    return g ? { name: g.name, color: g.color } : null
  }

  const handleOpenDetail = async (asset: Asset) => {
    setDetailAsset(asset)
    setDetailDrawerOpen(true)
    setDetailLoading(true)
    setDetailAccounts([])
    try {
      const r = await api.get(`/snapshots/by-asset/${asset.id}/accounts`)
      setDetailAccounts(r.data)
    } catch {
      message.error(t('msg.loadFailed'))
    } finally {
      setDetailLoading(false)
    }
  }

  const columns = [
    { title: t('table.assetCode'), dataIndex: 'asset_code', key: 'asset_code', width: 110,
      render: (v: string, r: Asset) => (
        <Tag color="blue" style={{ cursor: 'pointer' }} onClick={() => handleOpenDetail(r)}>{v}</Tag>
      ) },
    { title: 'IP', dataIndex: 'ip', key: 'ip', width: 150 },
    { title: t('table.hostname'), dataIndex: 'hostname', key: 'hostname', width: 150 },
    {
      title: t('table.group'),
      key: 'group',
      width: 120,
      render: (_: unknown, r: Asset) => {
        const g = getGroupName(r.group_id)
        return g
          ? <Tag color={g.color}>{g.name}</Tag>
          : <span style={{ color: '#aaa' }}>-</span>
      },
    },
    {
      title: t('table.type'),
      key: 'type',
      width: 140,
      render: (_: unknown, r: Asset) => {
        if (r.asset_category === 'database') {
          const DB_TAG: Record<string, { color: string; label: string }> = {
            mysql: { color: 'orange', label: 'MySQL' },
            postgresql: { color: 'blue', label: 'PostgreSQL' },
            redis: { color: 'red', label: 'Redis' },
            mongodb: { color: 'green', label: 'MongoDB' },
            mssql: { color: 'purple', label: 'MSSQL' },
            oracle: { color: 'red', label: 'Oracle' },
          }
          const dbTag = DB_TAG[r.db_type || ''] || { color: 'default', label: r.db_type || 'DB' }
          return <Tag color={dbTag.color}>{dbTag.label}</Tag>
        }
        if (r.asset_category === 'network') {
          const NW_TAG: Record<string, { color: string; label: string }> = {
            cisco: { color: '#049fd9', label: 'Cisco' },
            h3c: { color: '#00a870', label: 'H3C' },
            huawei: { color: '#e60012', label: t('status.huawei') },
          }
          const nwTag = NW_TAG[r.network_type || ''] || { color: 'default', label: r.network_type || t('asset.networkDevice') }
          return <Tag color={nwTag.color}>{nwTag.label}</Tag>
        }
        if (r.asset_category === 'iot') {
          const IOT_TAG: Record<string, { color: string; label: string }> = {
            camera: { color: '#eb2f96', label: t('asset.camera') },
            nvr: { color: '#722ed1', label: 'NVR' },
            dvr: { color: '#531dab', label: 'DVR' },
            sensor: { color: '#0891b2', label: t('asset.sensor') },
            gateway: { color: '#fa8c16', label: t('asset.gateway') },
            other: { color: '#8c8c8c', label: t('asset.iotDevice') },
          }
          const iotTag = IOT_TAG[(r as Asset & { iot_type?: string }).iot_type || ''] || { color: 'default', label: 'IoT' }
          return <Tag color={iotTag.color}>{iotTag.label}</Tag>
        }
        return <Tag>{r.os_type === 'linux' ? 'Linux' : 'Windows'}</Tag>
      },
    },
    {
      title: t('table.status'),
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (v: string) => (
        <Tag color={STATUS_COLOR[v]}>{STATUS_LABEL[v] || v}</Tag>
      ),
    },
    {
      title: t('table.lastScan'),
      dataIndex: 'last_scan_at',
      key: 'last_scan_at',
      render: (v?: string) => v ? new Date(v).toLocaleString('zh-CN') : '-',
    },
    {
      title: t('table.actions'),
      key: 'actions',
      width: 220,
      render: (_: unknown, record: Asset) => (
        <Space size="small">
          <Button
            size="small"
            icon={<ReloadOutlined spin={testingId === record.id} />}
            onClick={() => handleTest(record)}
            loading={testingId === record.id}
          >
            {t('btn.test')}
          </Button>
          <Button
            size="small"
            type="primary"
            icon={<ThunderboltOutlined />}
            onClick={() => handleScan(record)}
            loading={scanningId === record.id}
          >
            {t('btn.scan')}
          </Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          <Popconfirm
            title={t('asset.confirmDelete')}
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

  const rowSelection = {
    selectedRowKeys,
    onChange: (keys: React.Key[]) => setSelectedRowKeys(keys),
  }

  const hasSelection = selectedRowKeys.length > 0

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>{t('nav.assetManagement')}</Title>
        <Space>
          <Button icon={<RobotOutlined />} onClick={() => setNlSearchOpen(true)}>
            {t('nav.aiSearch')}
          </Button>
          <Button icon={<ExportOutlined />} onClick={handleExportCSV}>{t('btn.exportCsv')}</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>
            {t('btn.addAsset')}
          </Button>
        </Space>
      </div>

      {/* Search & Filter Bar */}
      <div style={{ marginBottom: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <Input
          placeholder={t('placeholder.searchIp')}
          prefix={<SearchOutlined />}
          value={searchQ}
          onChange={e => setSearchQ(e.target.value)}
          onPressEnter={fetchAssets}
          style={{ width: 220 }}
          allowClear
        />
        <Cascader
          placeholder={t('placeholder.allCategories')}
          options={catCascaderOptions}
          value={filterCategoryId ? [filterCategoryId] : []}
          onChange={(vals) => {
            // vals is array of selected IDs; use last (most specific)
            setFilterCategoryId(vals.length > 0 ? vals[vals.length - 1] as number : undefined)
            fetchAssets()
          }}
          allowClear
          style={{ width: 220 }}
          changeOnSelect
          displayRender={(labels) => labels.join(' / ')}
        />
        <Select
          placeholder={t('placeholder.allStatuses')}
          value={filterStatus}
          onChange={v => { setFilterStatus(v); fetchAssets() }}
          allowClear
          style={{ width: 140 }}
        >
          <Option value="online">{t('status.online')}</Option>
          <Option value="offline">{t('status.offline')}</Option>
          <Option value="auth_failed">{t('status.authFailed')}</Option>
          <Option value="untested">{t('status.untested')}</Option>
        </Select>
        <Select
          placeholder={t('asset.selectGroup')}
          value={filterGroup}
          onChange={v => { setFilterGroup(v); fetchAssets() }}
          allowClear
          style={{ width: 160 }}
        >
          {groups.map(g => <Option key={g.id} value={g.id}>{g.name}</Option>)}
        </Select>
        <Button onClick={fetchAssets} icon={<ReloadOutlined />}>{t('btn.refresh')}</Button>
      </div>

      {/* Bulk Action Bar */}
      {hasSelection && (
        <div style={{ marginBottom: 8, padding: '8px 12px', background: '#f0f0ff', borderRadius: 4, display: 'flex', alignItems: 'center', gap: 12 }}>
          <span>{t('asset.selectedCount', { count: selectedRowKeys.length })}</span>
          <Popconfirm
            title={t('asset.confirmBulkDelete', { count: selectedRowKeys.length })}
            onConfirm={handleBulkDelete}
            okText={t('btn.delete')}
            okButtonProps={{ danger: true }}
            cancelText={t('btn.cancel')}
          >
            <Button size="small" danger icon={<DeleteOutlined />} loading={bulkDeleting}>
              {t('btn.bulkDelete')}
            </Button>
          </Popconfirm>
          <Button size="small" onClick={() => setSelectedRowKeys([])}>{t('btn.clearSelection')}</Button>
        </div>
      )}

      <Table
        dataSource={assets}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10 }}
        rowSelection={rowSelection}
      />

      <Drawer
        title={editAsset ? t('asset.editTitle') : t('asset.addTitle')}
        onClose={() => setDrawerOpen(false)}
        open={drawerOpen}
        width={400}
        footer={
          <div style={{ textAlign: 'right' }}>
            <Button onClick={() => setDrawerOpen(false)} style={{ marginRight: 8 }}>{t('btn.cancel')}</Button>
            <Button type="primary" onClick={handleSave} loading={saving}>
              {t('btn.save')}
            </Button>
          </div>
        }
      >
        {editAsset && (
          <>
            <div style={{ marginBottom: 8, fontSize: 13 }}>
              <Text type="secondary">{t('table.assetCode')}：</Text>
              <Tag color="blue" style={{ marginLeft: 4 }}>{editAsset.asset_code}</Tag>
            </div>
            <Alert
              type={editAsset.status === 'online' ? 'success' : editAsset.status === 'offline' ? 'error' : 'info'}
              message={`${t('table.status')}：${STATUS_LABEL[editAsset.status] || editAsset.status}`}
              style={{ marginBottom: 16 }}
              showIcon
            />
          </>
        )}
        <Form form={form} layout="vertical">
          <Form.Item name="ip" label={t('asset.ipAddress')} rules={[{ required: true, message: t('asset.enterIp') }]}>
            <Input placeholder="192.168.1.100" disabled={!!editAsset} />
          </Form.Item>
          <Form.Item name="hostname" label={t('asset.hostnameOptional')}>
            <Input placeholder="web-prod-01" />
          </Form.Item>

          {/* 品类选择（选完自动推导资产大类） */}
          <Form.Item label={t('asset.category')} required>
            <Select
              placeholder={t('asset.selectCategoryFirst')}
              value={drawerCategory}
              onChange={val => {
                setDrawerCategory(val)
                const cat = categories.find(c => c.slug === val)
                if (cat) {
                  const parent = cat.parent_id ? categories.find(c => c.id === cat.parent_id) : null
                  const slug = (parent?.slug || cat.slug || '').toLowerCase()
                  if (slug === 'database') form.setFieldValue('asset_category', 'database')
                  else if (slug === 'network') form.setFieldValue('asset_category', 'network')
                  else if (slug === 'iot') form.setFieldValue('asset_category', 'iot')
                  else form.setFieldValue('asset_category', 'server')
                }
                form.setFieldValue('os_type', undefined)
                form.setFieldValue('db_type', undefined)
                form.setFieldValue('network_type', undefined)
                form.setFieldValue('iot_type', undefined)
              }}
            >
              {categories.map(c => (
                <Option key={c.slug} value={c.slug}>
                  {'　'.repeat(c.parent_id ? 1 : 0)}{c.name}
                </Option>
              ))}
            </Select>
          </Form.Item>

          {/* 归属父资产 */}
          <Form.Item label={t('asset.parentAssetOptional')}>
            <Select
              placeholder={t('asset.selectParentHost')}
              allowClear
              value={parentAssetId}
              onChange={(val) => setParentAssetId(val)}
              showSearch
              filterOption={(input, opt) =>
                (opt?.children as unknown as string)?.toLowerCase().includes(input.toLowerCase())
              }
            >
              {assets
                .filter(a => a.id !== editAsset?.id)
                .map(a => (
                  <Option key={a.id} value={a.id}>
                    {a.asset_code} — {a.ip} {a.hostname ? `(${a.hostname})` : ''}
                  </Option>
                ))}
            </Select>
          </Form.Item>

          <Divider plain style={{ margin: '4px 0', fontSize: 12, color: '#999' }}>{t('asset.subtype')}</Divider>

          {/* 子类型（子品类继承父级 sub_type_kind，这样 Linux 子品类仍可选择具体 OS） */}
          {(() => {
            const catDef = categories.find(c => c.slug === drawerCategory)
            // Determine effective sub_type_kind: own value, or inherited from parent
            let subKind = catDef?.sub_type_kind
            if ((!subKind || subKind === 'none') && catDef?.parent_id) {
              const parent = categories.find(c => c.id === catDef.parent_id)
              subKind = parent?.sub_type_kind
            }
            // Skip if still none/undefined
            if (!subKind || subKind === 'none') return null
            if (subKind === 'database') {
              return (
                <Form.Item name="db_type" label={t('asset.dbType')} rules={[{ required: true, message: t('asset.selectDbType') }]}>
                  <Select placeholder={t('asset.selectDbType')}>
                    <Option value="mysql">{t('asset.dbMysql')}</Option>
                    <Option value="postgresql">{t('asset.dbPostgresql')}</Option>
                    <Option value="redis">{t('asset.dbRedis')}</Option>
                    <Option value="mongodb">{t('asset.dbMongodb')}</Option>
                    <Option value="mssql">{t('asset.dbMssql')}</Option>
                    <Option value="oracle">{t('asset.dbOracle')}</Option>
                  </Select>
                </Form.Item>
              )
            }
            if (subKind === 'network') {
              return (
                <Form.Item name="network_type" label={t('asset.vendor')} rules={[{ required: true, message: t('asset.selectVendor') }]}>
                  <Select placeholder={t('asset.selectVendor')}>
                    <Option value="cisco">{t('asset.cisco')}</Option>
                    <Option value="h3c">{t('asset.h3c')}</Option>
                    <Option value="huawei">{t('status.huawei')}</Option>
                  </Select>
                </Form.Item>
              )
            }
            if (subKind === 'iot') {
              return (
                <Form.Item name="iot_type" label={t('asset.iotDeviceType')} rules={[{ required: true, message: t('asset.selectIotType') }]}>
                  <Select placeholder={t('asset.selectIotType')}>
                    <Option value="camera">{t('asset.ipCamera')}</Option>
                    <Option value="nvr">{t('asset.nvr')}</Option>
                    <Option value="dvr">{t('asset.dvr')}</Option>
                    <Option value="sensor">{t('asset.sensor')}</Option>
                    <Option value="gateway">{t('asset.iotGateway')}</Option>
                    <Option value="other">{t('asset.otherIot')}</Option>
                  </Select>
                </Form.Item>
              )
            }
            if (subKind === 'os') {
              return (
                <Form.Item name="os_type" label={t('asset.os')} rules={[{ required: true, message: t('asset.selectOs') }]}>
                  <Select placeholder={t('asset.selectOs')}>
                    <Option value="linux">{t('asset.osLinux')}</Option>
                    <Option value="windows">{t('asset.osWindows')}</Option>
                  </Select>
                </Form.Item>
              )
            }
            return null
          })()}
          <Form.Item name="group_id" label={t('asset.groupOptional')}>
            <Select placeholder={t('asset.selectGroup')} allowClear>
              {groups.map(g => (
                <Option key={g.id} value={g.id}>
                  <Tag color={g.color}>{g.name}</Tag>
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="port" label={t('asset.portOptional')}>
            <Input type="number" placeholder={t('asset.defaultPortHint')} />
          </Form.Item>
          <Form.Item name="credential_id" label={t('asset.credential')} rules={[{ required: true, message: t('asset.selectCredential') }]}>
            <Select placeholder={t('asset.selectCredential')} loading={credLoading}>
              {credentials.map(c => (
                <Option key={c.id} value={c.id}>
                  {c.name} ({c.username}, {c.auth_type})
                </Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Drawer>

      {/* Asset account detail drawer */}
      <Drawer
        title={
          <Space>
            <UserOutlined />
            {detailAsset ? `${detailAsset.ip} — ${detailAsset.asset_code}` : ''}
          </Space>
        }
        onClose={() => setDetailDrawerOpen(false)}
        open={detailDrawerOpen}
        width={680}
        destroyOnClose
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <UserOutlined style={{ fontSize: 32, color: '#ccc' }} />
              <Text type="secondary">{t('msg.loading')}</Text>
            </Space>
          </div>
        ) : detailAccounts.length === 0 ? (
          <Alert type="info" message={t('asset.noAccounts')} showIcon />
        ) : (
          <>
            <div style={{ marginBottom: 12 }}>
              <Space>
                <Badge count={detailAccounts.length} style={{ backgroundColor: '#1890ff' }} />
                <Text type="secondary">
                  {detailAccounts.filter((a: any) => a.is_admin).length} {t('asset.adminAccounts')}
                </Text>
              </Space>
            </div>
            <List
              size="small"
              dataSource={detailAccounts}
              style={{ maxHeight: 'calc(100vh - 220px)', overflowY: 'auto' }}
              renderItem={(account: any) => (
                <List.Item
                  style={{ padding: '10px 4px' }}
                  extra={
                    <Space>
                      {account.has_credential_findings && (
                        <Tag color="red" style={{ fontSize: 11 }}>
                          {t('asset.credentialLeak')}
                        </Tag>
                      )}
                      {account.has_nopasswd_sudo && (
                        <Tag color="orange" style={{ fontSize: 11 }}>
                          {t('asset.nopasswdSudo')}
                        </Tag>
                      )}
                      {account.is_baseline && (
                        <Tag color="green" style={{ fontSize: 11 }}>
                          {t('scan.baseline')}
                        </Tag>
                      )}
                    </Space>
                  }
                >
                  <List.Item.Meta
                    title={
                      <Space>
                        <Text strong>{account.username}</Text>
                        <Tag color={account.is_admin ? 'red' : 'default'} style={{ fontSize: 11 }}>
                          {account.is_admin ? t('asset.admin') : '普通账号'}
                        </Tag>
                        <Tag style={{ fontSize: 11 }}>{account.account_status || '-'}</Tag>
                      </Space>
                    }
                    description={
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        UID: {account.uid_sid}
                        {account.home_dir && ` · ${account.home_dir}`}
                        {account.shell && ` · ${account.shell}`}
                        {account.last_login && ` · ${t('asset.lastLogin')}: ${account.last_login}`}
                      </Text>
                    }
                  />
                </List.Item>
              )}
            />
          </>
        )}
      </Drawer>

      {/* Natural Language Search Modal */}
      <Modal
        title={
          <Space>
            <RobotOutlined />
            {t('nav.aiAssetSearch')}
          </Space>
        }
        open={nlSearchOpen}
        onCancel={() => { setNlSearchOpen(false); setNlResults(null) }}
        footer={null}
        width={720}
        destroyOnClose
      >
        <div style={{ marginTop: 8 }}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            <Input.Search
              placeholder={t('nlSearch.placeholder')}
              value={nlQuery}
              onChange={e => setNlQuery(e.target.value)}
              onSearch={handleNlSearch}
              enterButton={t('btn.search')}
              loading={nlLoading}
              size="large"
              allowClear
            />
          </div>

          {/* Example chips */}
          <div style={{ marginBottom: 16 }}>
            <Text type="secondary" style={{ fontSize: 12, marginBottom: 6, display: 'block' }}>{t('nlSearch.examples')}</Text>
            <Space wrap size={4}>
              {EXAMPLES.map(ex => (
                <Button
                  key={ex}
                  size="small"
                  onClick={() => { setNlQuery(ex); handleNlSearch(ex) }}
                  style={{ fontSize: 12 }}
                >
                  {ex}
                </Button>
              ))}
            </Space>
          </div>

          {nlLoading && (
            <div style={{ textAlign: 'center', padding: 24 }}>
              <Badge status="processing" text={t('nlSearch.searching')} />
            </div>
          )}

          {nlResults && !nlLoading && (
            <>
              {/* Filter explanation */}
              {nlResults.filter_explanation.length > 0 && (
                <div style={{ marginBottom: 12, display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    <RobotOutlined style={{ marginRight: 4 }} />
                    {nlResults.llm_powered ? t('nlSearch.aiParse') : t('nlSearch.patternMatch')} · {t('nlSearch.parsedConditions')}
                  </Text>
                  {nlResults.filter_explanation.map(e => (
                    <Tag key={e} color="blue" style={{ fontSize: 12 }}>{e}</Tag>
                  ))}
                  <Tag color={nlResults.total_found > 0 ? 'green' : 'orange'} style={{ marginLeft: 4 }}>
                    {nlResults.total_found} {t('nlSearch.results')}
                  </Tag>
                </div>
              )}

              {/* Results */}
              {nlResults.results.length === 0 ? (
                <Alert type="info" message={t('nlSearch.noResults')} showIcon />
              ) : (
                <List
                  size="small"
                  dataSource={nlResults.results}
                  style={{ maxHeight: 400, overflowY: 'auto', border: '1px solid #f0f0f0', borderRadius: 6 }}
                  renderItem={item => (
                    <List.Item
                      style={{ padding: '10px 12px', cursor: 'pointer' }}
                      onClick={() => {
                        const asset = assets.find(a => a.id === item.id)
                        if (asset) openEdit(asset)
                      }}
                    >
                      <div style={{ width: '100%' }}>
                        <Space style={{ marginBottom: 4 }}>
                          <Tag color="blue">{item.asset_code}</Tag>
                          <Text strong>{item.ip}</Text>
                          {item.hostname && <Text type="secondary">{item.hostname}</Text>}
                          <Tag color={STATUS_COLOR[item.status]}>{STATUS_LABEL[item.status]}</Tag>
                          <Tag>{item.asset_category === 'server' ? t('asset.server') : item.asset_category === 'database' ? t('asset.database') : item.asset_category === 'network' ? t('asset.network') : 'IoT'}</Tag>
                        </Space>
                        <div style={{ display: 'flex', gap: 16, fontSize: 12 }}>
                          <Text type="secondary">
                            <UserOutlined style={{ marginRight: 4 }} />
                            {t('asset.accounts', { count: item.account_count })}
                            {item.admin_count > 0 && <Tag color="red" style={{ marginLeft: 4, fontSize: 11 }}>{t('asset.withAdmin', { count: item.admin_count })}</Tag>}
                          </Text>
                        </div>
                        {item.latest_accounts.length > 0 && (
                          <div style={{ marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                            {item.latest_accounts.slice(0, 4).map(a => (
                              <Tag
                                key={a.id}
                                color={a.is_admin ? 'red' : 'default'}
                                style={{ fontSize: 11 }}
                              >
                                {a.username}
                              </Tag>
                            ))}
                          </div>
                        )}
                      </div>
                    </List.Item>
                  )}
                />
              )}
            </>
          )}

          {!nlResults && !nlLoading && (
            <Paragraph type="secondary" style={{ textAlign: 'center', fontSize: 13 }}>
              {t('nlSearch.hint')}
            </Paragraph>
          )}
        </div>
      </Modal>
    </div>
  )
}
