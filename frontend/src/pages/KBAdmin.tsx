import { useState, useEffect, useMemo } from 'react'
import {
  Card, Table, Button, Space, Drawer, Form, Input, Select,
  Tag, Popconfirm, message, Typography, Row, Col, Divider, Alert,
} from 'antd'
import {
  PlusOutlined, EditOutlined, DeleteOutlined, BookOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import i18n from 'i18next'
import {
  listKBEntries, createKBEntry, updateKBEntry, deleteKBEntry,
  KBEntryData,
} from '../api/client'

const { Title } = Typography
const { TextArea } = Input

interface KBEntryRow {
  id: number
  entry_type: string
  title: string
  title_en?: string
  description?: string
  description_en?: string
  extra_data: Record<string, unknown>
  enabled: boolean
  created_at: string
  updated_at: string
}


const SEVERITY_OPTIONS = [
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
]

const TYPE_COLOR: Record<string, string> = {
  mitre: 'purple',
  cve: 'red',
  practice: 'blue',
}

export default function KBAdmin() {
  const { t } = useTranslation()
  const isZh = !i18n.language?.startsWith('en')

  const typeOptions = useMemo(() => [
    { value: 'mitre', label: t('kb.mitreType') },
    { value: 'cve', label: t('kb.cveType') },
    { value: 'practice', label: t('kb.practiceType') },
  ], [t])

  const [entries, setEntries] = useState<KBEntryRow[]>([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)

  const [filterType, setFilterType] = useState<string>('')
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 20

  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editEntry, setEditEntry] = useState<KBEntryRow | null>(null)
  const [saving, setSaving] = useState(false)
  const [form] = Form.useForm()

  const fetchEntries = async () => {
    setLoading(true)
    try {
      const params: Record<string, unknown> = { limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE }
      if (filterType) params.type = filterType
      const r = await listKBEntries(params as { type?: string; limit?: number; offset?: number })
      setEntries(r.data as KBEntryRow[])
      // total might be in headers or we estimate
      setTotal(Array.isArray(r.data) ? r.data.length : 0)
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.loadFailed'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchEntries() }, [page, filterType])

  // Re-fetch when filter type changes (reset page)
  useEffect(() => {
    setPage(1)
    fetchEntries()
  }, [filterType])

  const openAdd = () => {
    setEditEntry(null)
    form.resetFields()
    setDrawerOpen(true)
  }

  const openEdit = (entry: KBEntryRow) => {
    setEditEntry(entry)
    form.setFieldsValue({
      entry_type: entry.entry_type,
      title: entry.title,
      title_en: entry.title_en || '',
      description: entry.description || '',
      description_en: entry.description_en || '',
      enabled: entry.enabled,
      // metadata fields
      id: entry.extra_data?.id || '',
      sub: entry.extra_data?.sub || '',
      platforms: (entry.extra_data?.platforms as string[] || []).join(', '),
      indicators: (entry.extra_data?.indicators as string[] || []).join(', '),
      indicators_en: (entry.extra_data?.indicators_en as string[] || []).join(', '),
      detection: entry.extra_data?.detection || '',
      detection_en: entry.extra_data?.detection_en || '',
      mitigation: entry.extra_data?.mitigation || '',
      mitigation_en: entry.extra_data?.mitigation_en || '',
      related_cves: (entry.extra_data?.related_cves as string[] || []).join(', '),
      product: entry.extra_data?.product || '',
      severity: entry.extra_data?.severity || '',
      cvss: entry.extra_data?.cvss || '',
      affected_versions: entry.extra_data?.affected_versions || '',
      exploitation: entry.extra_data?.exploitation || '',
      exploitation_en: entry.extra_data?.exploitation_en || '',
      remediation: entry.extra_data?.remediation || '',
      remediation_en: entry.extra_data?.remediation_en || '',
      mitre: entry.extra_data?.mitre || '',
      detection_hints: (entry.extra_data?.detection_hints as string[] || []).join(', '),
      detection_hints_en: (entry.extra_data?.detection_hints_en as string[] || []).join(', '),
      category: entry.extra_data?.category || '',
      category_en: entry.extra_data?.category_en || '',
      principle: entry.extra_data?.principle || '',
      principle_en: entry.extra_data?.principle_en || '',
      implementation: entry.extra_data?.implementation || '',
      implementation_en: entry.extra_data?.implementation_en || '',
      risk_if_missing: entry.extra_data?.risk_if_missing || '',
      risk_if_missing_en: entry.extra_data?.risk_if_missing_en || '',
      mitre_ref: entry.extra_data?.mitre_ref || '',
      standard: entry.extra_data?.standard || '',
    })
    setDrawerOpen(true)
  }

  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)

      const entryType = values.entry_type as string
      const extra_data: Record<string, unknown> = {}

      if (entryType === 'mitre') {
        if (values.id) extra_data.id = values.id
        if (values.sub) extra_data.sub = values.sub
        if (values.platforms) extra_data.platforms = (values.platforms as string).split(',').map((s: string) => s.trim()).filter(Boolean)
        if (values.indicators) extra_data.indicators = (values.indicators as string).split(',').map((s: string) => s.trim()).filter(Boolean)
        if (values.indicators_en) extra_data.indicators_en = (values.indicators_en as string).split(',').map((s: string) => s.trim()).filter(Boolean)
        if (values.detection) extra_data.detection = values.detection
        if (values.detection_en) extra_data.detection_en = values.detection_en
        if (values.mitigation) extra_data.mitigation = values.mitigation
        if (values.mitigation_en) extra_data.mitigation_en = values.mitigation_en
        if (values.related_cves) extra_data.related_cves = (values.related_cves as string).split(',').map((s: string) => s.trim()).filter(Boolean)
      } else if (entryType === 'cve') {
        if (values.product) extra_data.product = values.product
        if (values.severity) extra_data.severity = values.severity
        if (values.cvss) extra_data.cvss = Number(values.cvss)
        if (values.affected_versions) extra_data.affected_versions = values.affected_versions
        if (values.exploitation) extra_data.exploitation = values.exploitation
        if (values.exploitation_en) extra_data.exploitation_en = values.exploitation_en
        if (values.remediation) extra_data.remediation = values.remediation
        if (values.remediation_en) extra_data.remediation_en = values.remediation_en
        if (values.mitre) extra_data.mitre = values.mitre
        if (values.detection_hints) extra_data.detection_hints = (values.detection_hints as string).split(',').map((s: string) => s.trim()).filter(Boolean)
        if (values.detection_hints_en) extra_data.detection_hints_en = (values.detection_hints_en as string).split(',').map((s: string) => s.trim()).filter(Boolean)
      } else if (entryType === 'practice') {
        if (values.category) extra_data.category = values.category
        if (values.category_en) extra_data.category_en = values.category_en
        if (values.principle) extra_data.principle = values.principle
        if (values.principle_en) extra_data.principle_en = values.principle_en
        if (values.implementation) extra_data.implementation = values.implementation
        if (values.implementation_en) extra_data.implementation_en = values.implementation_en
        if (values.risk_if_missing) extra_data.risk_if_missing = values.risk_if_missing
        if (values.risk_if_missing_en) extra_data.risk_if_missing_en = values.risk_if_missing_en
        if (values.mitre_ref) extra_data.mitre_ref = values.mitre_ref
        if (values.standard) extra_data.standard = values.standard
      }

      const payload: KBEntryData & { enabled?: boolean } = {
        entry_type: entryType,
        title: values.title,
        title_en: values.title_en || undefined,
        description: values.description || undefined,
        description_en: values.description_en || undefined,
        extra_data,
      }

      if (editEntry) {
        await updateKBEntry(editEntry.id, { ...payload, enabled: values.enabled })
        message.success(t('kb.updated'))
      } else {
        await createKBEntry(payload)
        message.success(t('kb.created'))
      }

      setDrawerOpen(false)
      fetchEntries()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      if (!err.response?.data?.detail) {
        message.error(t('msg.saveFailed'))
      }
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteKBEntry(id)
      message.success(t('kb.deleted'))
      fetchEntries()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.deleteFailed'))
    }
  }

  const selectedType = Form.useWatch('entry_type', form)

  const columns = [
    {
      title: t('kb.type'),
      dataIndex: 'entry_type',
      width: 120,
      render: (type: string) => (
        <Tag color={TYPE_COLOR[type] || 'default'}>
          {typeLabel(type)}
        </Tag>
      ),
    },
    {
      title: `${t('kb.entryName')} (${t('kb.fieldZh')})`,
      dataIndex: 'title',
      ellipsis: true,
    },
    {
      title: `${t('kb.entryName')} (${t('kb.fieldEn')})`,
      dataIndex: 'title_en',
      ellipsis: true,
      render: (v: string) => v || '-',
    },
    {
      title: t('kb.description'),
      dataIndex: 'description',
      ellipsis: true,
      render: (v: string) => v || '-',
      width: 200,
    },
    {
      title: t('table.actions'),
      width: 140,
      render: (_: unknown, record: KBEntryRow) => (
        <Space size="small">
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
            {t('btn.edit')}
          </Button>
          <Popconfirm
            title={t('kb.confirmDelete')}
            onConfirm={() => handleDelete(record.id)}
            okText={t('btn.confirm')}
            cancelText={t('btn.cancel')}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              {t('btn.delete')}
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const typeLabel = (type: string) =>
    type === 'mitre' ? t('kb.mitreType') : type === 'cve' ? t('kb.cveType') : t('kb.practiceType')

  return (
    <div style={{ padding: 0 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          <BookOutlined /> {t('kb.admin')}
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>
          {t('kb.addEntry')}
        </Button>
      </div>

      <Alert
        message={`${t('kb.customEntries')} — ${entries.length > 0 ? t('table.total') + ': ' + total : ''}`}
        type="info"
        showIcon
        style={{ marginBottom: 12 }}
      />

      <Card size="small" bodyStyle={{ padding: 0 }}>
        <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0' }}>
          <Space>
            <Select
              value={filterType}
              onChange={v => { setFilterType(v); setPage(1) }}
              allowClear
              placeholder={t('kb.allTypes')}
              style={{ width: 160 }}
              options={[
                { value: '', label: t('kb.allTypes') },
                ...typeOptions,
              ]}
            />
          </Space>
        </div>

        <Table
          dataSource={entries}
          columns={columns}
          rowKey="id"
          loading={loading}
          size="small"
          pagination={{
            current: page,
            pageSize: PAGE_SIZE,
            total,
            onChange: p => setPage(p),
            showSizeChanger: false,
          }}
        />
      </Card>

      {/* ── Drawer Form ─────────────────────────────────────────────────── */}
      <Drawer
        title={editEntry ? `${t('kb.editEntry')} — ${typeLabel(editEntry.entry_type)}` : t('kb.addEntry')}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={560}
        destroyOnClose
        footer={
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <Button onClick={() => setDrawerOpen(false)}>{t('btn.cancel')}</Button>
            <Button type="primary" loading={saving} onClick={handleSave}>
              {t('btn.save')}
            </Button>
          </div>
        }
      >
        <Form form={form} layout="vertical">
          {/* Type selector — only on add */}
          <Form.Item
            name="entry_type"
            label={t('kb.type')}
            rules={[{ required: true, message: t('placeholder.select') }]}
          >
            <Select
              placeholder={t('placeholder.select')}
              options={typeOptions}
              disabled={!!editEntry}
            />
          </Form.Item>

          {/* Common fields */}
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item
                name="title"
                label={`${t('kb.entryName')} (${t('kb.fieldZh')})`}
                rules={isZh ? [{ required: true, message: t('kb.nameRequired') }] : []}
              >
                <Input placeholder={t('kb.entryName')} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="title_en"
                label={`${t('kb.entryName')} (${t('kb.fieldEn')})`}
                rules={!isZh ? [{ required: true, message: t('kb.nameRequired') }] : []}
              >
                <Input placeholder={t('kb.entryName')} />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="description" label={`${t('kb.description')} (${t('kb.fieldZh')})`}>
                <TextArea rows={2} placeholder={t('kb.description')} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="description_en" label={`${t('kb.description')} (${t('kb.fieldEn')})`}>
                <TextArea rows={2} placeholder={t('kb.description')} />
              </Form.Item>
            </Col>
          </Row>

          {editEntry && (
            <Form.Item name="enabled" valuePropName="checked" style={{ marginBottom: 8 }}>
              <Space>
                <span style={{ fontSize: 12, color: '#888' }}>{t('status.enabled')}:</span>
              </Space>
            </Form.Item>
          )}

          <Divider orientation="left" plain style={{ fontSize: 12 }}>
            {t('kb.metaSection')}
          </Divider>

          {/* ── MITRE fields ── */}
          {(!selectedType || selectedType === 'mitre') && (
            <>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item name="id" label={t('kb.mitreId')}>
                    <Input placeholder="T1078" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="sub" label="Sub-technique">
                    <Input placeholder="T1078.003" />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item name="platforms" label={t('kb.platforms')}>
                <Input placeholder="Linux, Windows, Cloud" />
              </Form.Item>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item name="detection" label={`${t('kb.detectionHint')} (${t('kb.fieldZh')})`}>
                    <Input placeholder={t('kb.detectionHint')} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="detection_en" label={`${t('kb.detectionHint')} (${t('kb.fieldEn')})`}>
                    <Input placeholder={t('kb.detectionHint')} />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item name="mitigation" label={`${t('kb.mitigation')} (${t('kb.fieldZh')})`}>
                    <Input placeholder={t('kb.mitigation')} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="mitigation_en" label={`${t('kb.mitigation')} (${t('kb.fieldEn')})`}>
                    <Input placeholder={t('kb.mitigation')} />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item name="related_cves" label={t('kb.relatedCVE')}>
                <Input placeholder="CVE-2021-3156, CVE-2016-6664" />
              </Form.Item>
            </>
          )}

          {/* ── CVE fields ── */}
          {(!selectedType || selectedType === 'cve') && (
            <>
              <Row gutter={12}>
                <Col span={8}>
                  <Form.Item name="product" label={t('kb.product')}>
                    <Input placeholder="sudo" />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="severity" label={t('kb.severity')}>
                    <Select placeholder={t('placeholder.select')} options={SEVERITY_OPTIONS} allowClear />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="cvss" label="CVSS">
                    <Input placeholder="7.8" />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item name="affected_versions" label={t('kb.affectedVersion')}>
                <Input placeholder="sudo <= 1.9.5p2" />
              </Form.Item>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item name="exploitation" label={`${t('kb.exploitation')} (${t('kb.fieldZh')})`}>
                    <Input placeholder={t('kb.exploitation')} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="exploitation_en" label={`${t('kb.exploitation')} (${t('kb.fieldEn')})`}>
                    <Input placeholder={t('kb.exploitation')} />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item name="remediation" label={`${t('kb.remediation')} (${t('kb.fieldZh')})`}>
                    <Input placeholder={t('kb.remediation')} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="remediation_en" label={`${t('kb.remediation')} (${t('kb.fieldEn')})`}>
                    <Input placeholder={t('kb.remediation')} />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item name="mitre" label={t('kb.relatedATTACK')}>
                <Input placeholder="T1078.003" />
              </Form.Item>
              <Form.Item name="detection_hints" label={`${t('kb.detectionHint')} (${t('kb.fieldZh')})`}>
                <Input placeholder={t('kb.detectionHint')} />
              </Form.Item>
            </>
          )}

          {/* ── Practice fields ── */}
          {(!selectedType || selectedType === 'practice') && (
            <>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item name="category" label={`${t('kb.category')} (${t('kb.fieldZh')})`}>
                    <Input placeholder={t('kb.category')} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="category_en" label={`${t('kb.category')} (${t('kb.fieldEn')})`}>
                    <Input placeholder={t('kb.category')} />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item name="principle" label={`${t('kb.principle')} (${t('kb.fieldZh')})`}>
                    <TextArea rows={2} placeholder={t('kb.principle')} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="principle_en" label={`${t('kb.principle')} (${t('kb.fieldEn')})`}>
                    <TextArea rows={2} placeholder={t('kb.principle')} />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item name="implementation" label={`${t('kb.implementation')} (${t('kb.fieldZh')})`}>
                    <TextArea rows={2} placeholder={t('kb.implementation')} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="implementation_en" label={`${t('kb.implementation')} (${t('kb.fieldEn')})`}>
                    <TextArea rows={2} placeholder={t('kb.implementation')} />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item name="risk_if_missing" label={`${t('kb.riskMissing')} (${t('kb.fieldZh')})`}>
                    <TextArea rows={2} placeholder={t('kb.riskMissing')} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="risk_if_missing_en" label={`${t('kb.riskMissing')} (${t('kb.fieldEn')})`}>
                    <TextArea rows={2} placeholder={t('kb.riskMissing')} />
                  </Form.Item>
                </Col>
              </Row>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item name="mitre_ref" label={t('kb.relatedATTACK')}>
                    <Input placeholder="T1078.003" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="standard" label={t('kb.standard')}>
                    <Input placeholder="CIS Linux Benchmark" />
                  </Form.Item>
                </Col>
              </Row>
            </>
          )}
        </Form>
      </Drawer>
    </div>
  )
}
