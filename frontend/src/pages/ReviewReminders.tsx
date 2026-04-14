import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Card, Row, Col, Table, Tag, Button, Space, Switch, Modal,
  Form, Input, Select, DatePicker, Typography, Popconfirm, message,
  Drawer, Statistic, Descriptions, Empty, Alert,
} from 'antd'
import {
  PlusOutlined, DeleteOutlined, ReloadOutlined,
  ClockCircleOutlined, CheckCircleOutlined, CloseCircleOutlined,
  FieldTimeOutlined, BellOutlined, MailOutlined, GlobalOutlined,
  DownloadOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import {
  listReviewSchedules, createReviewSchedule, updateReviewSchedule,
  deleteReviewSchedule, listReviewReports, getReviewReport,
  triggerReviewGenerate, approveReviewReport, dismissReviewReport,
  exportReviewReport,
} from '../api/client'

const { Text, Title } = Typography

interface ReviewSchedule {
  id: number
  name: string
  period: string
  day_of_month: number | null
  alert_channels: { email?: string[]; webhook?: string } | null
  enabled: boolean
  next_run_at: string | null
  created_at: string
}

interface ReviewReport {
  id: number
  schedule_id: number
  period: string
  period_start: string
  period_end: string
  status: string
  reviewed_by: number | null
  reviewed_at: string | null
  notes: string | null
  content_summary: any
  created_at: string
  schedule_name?: string
  reviewer_name?: string
}

const PERIOD_LABEL = (t: (k: string) => string): Record<string, string> => ({
  monthly: t('review.monthly'), quarterly: t('review.quarterly'),
})
const STATUS_LABEL = (t: (k: string) => string): Record<string, { color: string; text: string }> => ({
  pending_review: { color: 'orange', text: t('review.pendingReviewStatus') },
  approved: { color: 'green', text: t('review.approvedStatus') },
  dismissed: { color: 'default', text: t('review.dismissedStatus') },
})

export default function ReviewReminders() {
  const { t } = useTranslation()
  const [schedules, setSchedules] = useState<ReviewSchedule[]>([])
  const [reports, setReports] = useState<ReviewReport[]>([])
  const [reportTotal, setReportTotal] = useState(0)
  const [loadingSchedules, setLoadingSchedules] = useState(false)
  const [loadingReports, setLoadingReports] = useState(false)
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [reportOffset, setReportOffset] = useState(0)
  const [selectedReport, setSelectedReport] = useState<ReviewReport | null>(null)
  const [reportDrawerOpen, setReportDrawerOpen] = useState(false)
  const [scheduleModalOpen, setScheduleModalOpen] = useState(false)
  const [editingSchedule, setEditingSchedule] = useState<ReviewSchedule | null>(null)
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)
  const [generatingId, setGeneratingId] = useState<number | null>(null)

  const fetchSchedules = useCallback(async () => {
    setLoadingSchedules(true)
    try {
      const r = await listReviewSchedules()
      setSchedules(r.data.schedules || [])
    } catch { /* ignore */ } finally {
      setLoadingSchedules(false)
    }
  }, [])

  const fetchReports = useCallback(async (offset = 0) => {
    setLoadingReports(true)
    try {
      const r = await listReviewReports({ status: statusFilter, limit: 10, offset })
      setReports(r.data.reports || [])
      setReportTotal(r.data.total || 0)
    } catch { /* ignore */ } finally {
      setLoadingReports(false)
    }
  }, [statusFilter])

  useEffect(() => { fetchSchedules() }, [fetchSchedules])
  useEffect(() => { fetchReports() }, [fetchReports])

  const handleToggle = async (s: ReviewSchedule) => {
    try {
      await updateReviewSchedule(s.id, { enabled: !s.enabled })
      fetchSchedules()
    } catch { message.error(t('msg.error')) }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteReviewSchedule(id)
      message.success(t('msg.deleteSuccess'))
      fetchSchedules()
    } catch { message.error(t('msg.deleteFailed')) }
  }

  const handleGenerate = async (scheduleId: number) => {
    setGeneratingId(scheduleId)
    try {
      await triggerReviewGenerate(scheduleId)
      message.success(t('msg.generateSuccess'))
      fetchReports()
    } catch (e: any) {
      message.error(e?.response?.data?.detail || t('msg.generateFailed'))
    } finally {
      setGeneratingId(null)
    }
  }

  const openScheduleModal = (s?: ReviewSchedule) => {
    setEditingSchedule(s || null)
    if (s) {
      form.setFieldsValue({
        name: s.name,
        period: s.period,
        day_of_month: s.day_of_month,
        alert_channels: s.alert_channels,
        enabled: s.enabled,
      })
    } else {
      form.resetFields()
      form.setFieldsValue({ period: 'monthly', day_of_month: 1, enabled: true })
    }
    setScheduleModalOpen(true)
  }

  const handleSaveSchedule = async () => {
    setSaving(true)
    try {
      const vals = await form.validateFields()
      if (editingSchedule) {
        await updateReviewSchedule(editingSchedule.id, vals)
        message.success(t('msg.updated'))
      } else {
        await createReviewSchedule(vals)
        message.success(t('msg.created'))
      }
      setScheduleModalOpen(false)
      fetchSchedules()
    } catch (e: any) {
      if (e?.values) message.error(t('msg.formError'))
    } finally {
      setSaving(false)
    }
  }

  const openReportDrawer = async (report: ReviewReport) => {
    try {
      const r = await getReviewReport(report.id)
      setSelectedReport(r.data)
    } catch {
      setSelectedReport(report)
    }
    setReportDrawerOpen(true)
  }

  const handleApprove = async (id: number) => {
    try {
      await approveReviewReport(id)
      message.success(t('msg.approvedSuccess'))
      setReportDrawerOpen(false)
      fetchReports()
    } catch { message.error(t('msg.error')) }
  }

  const handleDismiss = async (id: number) => {
    try {
      await dismissReviewReport(id)
      message.success(t('msg.dismissedSuccess'))
      setReportDrawerOpen(false)
      fetchReports()
    } catch { message.error(t('msg.error')) }
  }

  const handleExport = async (id: number) => {
    try {
      const res = await exportReviewReport(id)
      const blob = new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${t('review.reportFilePrefix')}_${id}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    } catch { message.error(t('msg.exportFailed')) }
  }

  const reportColumns: ColumnsType<ReviewReport> = [
    {
      title: 'ID', dataIndex: 'id', width: 60,
      render: (id: number) => <Text code>#{id}</Text>,
    },
    {
      title: t('review.scheduleName2'), dataIndex: 'schedule_name',
      render: (v) => v || '-',
    },
    {
      title: t('table.period'), dataIndex: 'period',
      render: (p: string) => <Tag>{PERIOD_LABEL(t)[p] || p}</Tag>,
    },
    {
      title: t('review.periodRange'),
      render: (_: any, r: ReviewReport) => (
        <Text type="secondary" style={{ fontSize: 12 }}>
          {r.period_start?.slice(0, 10)} ~ {r.period_end?.slice(0, 10)}
        </Text>
      ),
    },
    {
      title: t('table.status'), dataIndex: 'status',
      render: (s: string) => {
        const cfg = STATUS_LABEL(t)[s] || { color: 'default', text: s }
        return <Tag color={cfg.color}>{cfg.text}</Tag>
      },
    },
    {
      title: t('review.reviewer'), dataIndex: 'reviewer_name',
      render: (v: string) => v || '-',
    },
    {
      title: t('review.createdAt'), dataIndex: 'created_at',
      render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-',
    },
    {
      title: t('table.action'),
      render: (_: any, r: ReviewReport) => (
        <Space>
          <Button size="small" onClick={() => openReportDrawer(r)}>{t('btn.view')}</Button>
          <Button size="small" icon={<DownloadOutlined />} onClick={() => handleExport(r.id)}>{t('btn.export')}</Button>
          {r.status === 'pending_review' && (
            <>
              <Popconfirm title={t('review.approveConfirm')} onConfirm={() => handleApprove(r.id)}>
                <Button size="small" type="primary" icon={<CheckCircleOutlined />}>{t('review.approve')}</Button>
              </Popconfirm>
              <Popconfirm title={t('review.dismissConfirm')} onConfirm={() => handleDismiss(r.id)}>
                <Button size="small" danger icon={<CloseCircleOutlined />}>{t('review.dismiss')}</Button>
              </Popconfirm>
            </>
          )}
        </Space>
      ),
    },
  ]

  const summary = selectedReport?.content_summary || {}

  return (
    <div style={{ padding: 0 }}>
      <Space style={{ marginBottom: 16 }} align="center">
        <div>
          <Title level={4} style={{ margin: 0 }}>
            <BellOutlined /> {t('review.title')}
          </Title>
          <Text type="secondary" style={{ display: 'block', fontSize: 12 }}>
            {t('review.subtitle')}
          </Text>
        </div>
      </Space>

      {/* ── Schedules ── */}
      <Card
        title={<Space><FieldTimeOutlined /> {t('review.schedules')}</Space>}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => openScheduleModal()}>
            {t('review.newSchedule')}
          </Button>
        }
        style={{ marginBottom: 24 }}
      >
        {schedules.length === 0 ? (
          <Empty description={t('review.noSchedules')} />
        ) : (
          <Row gutter={16}>
            {schedules.map((s) => (
              <Col span={8} key={s.id} style={{ marginBottom: 12 }}>
                <Card
                  size="small"
                  hoverable
                  style={{ borderColor: s.enabled ? '#1890ff' : '#d9d9d9' }}
                  actions={[
                    <Button size="small" icon={<ReloadOutlined />}
                      loading={generatingId === s.id}
                      onClick={() => handleGenerate(s.id)}>{t('review.generate')}</Button>,
                    <Button size="small" onClick={() => openScheduleModal(s)}>{t('btn.edit')}</Button>,
                    <Popconfirm title={t('msg.deleteConfirm')} onConfirm={() => handleDelete(s.id)}>
                      <Button size="small" danger icon={<DeleteOutlined />}>{t('btn.delete')}</Button>
                    </Popconfirm>,
                  ]}
                >
                  <Descriptions size="small" column={1}>
                    <Descriptions.Item label={t('table.name')}>
                      <Text strong>{s.name}</Text>
                    </Descriptions.Item>
                    <Descriptions.Item label={t('table.period')}>
                      <Tag color="blue">{PERIOD_LABEL(t)[s.period] || s.period}</Tag>
                    </Descriptions.Item>
                    <Descriptions.Item label={t('review.dayOfMonth')}>
                      {t('review.dayOfMonthLabel', { day: s.day_of_month || 1 })}
                    </Descriptions.Item>
                    <Descriptions.Item label={t('table.nextRun')}>
                      {s.next_run_at ? new Date(s.next_run_at).toLocaleString('zh-CN') : '-'}
                    </Descriptions.Item>
                    <Descriptions.Item label={t('review.notificationChannels')}>
                      <Space size={4}>
                        {s.alert_channels?.email?.length ? (
                          <Tag icon={<MailOutlined />}>{s.alert_channels.email.length}{t('review.emails', ' emails')}</Tag>
                        ) : null}
                        {s.alert_channels?.webhook ? (
                          <Tag icon={<GlobalOutlined />}>Webhook</Tag>
                        ) : null}
                        {!s.alert_channels?.email?.length && !s.alert_channels?.webhook ? (
                          <Text type="secondary">{t('review.none')}</Text>
                        ) : null}
                      </Space>
                    </Descriptions.Item>
                    <Descriptions.Item label={t('table.status')}>
                      <Switch
                        size="small"
                        checked={s.enabled}
                        onChange={() => handleToggle(s)}
                      />
                    </Descriptions.Item>
                  </Descriptions>
                </Card>
              </Col>
            ))}
          </Row>
        )}
      </Card>

      {/* ── Reports ── */}
      <Card title={<Space><ClockCircleOutlined /> {t('review.reports')}</Space>}>
        <Space style={{ marginBottom: 12 }}>
          <Select
            allowClear placeholder={t('filter.status')} style={{ width: 120 }}
            onChange={(v) => { setStatusFilter(v); setReportOffset(0) }}
            options={[
              { label: t('status.pending_review'), value: 'pending_review' },
              { label: t('status.approved'), value: 'approved' },
              { label: t('status.dismissed'), value: 'dismissed' },
            ]}
          />
        </Space>
        <Table
          columns={reportColumns}
          dataSource={reports}
          rowKey="id"
          loading={loadingReports}
          pagination={{
            total: reportTotal,
            pageSize: 10,
            current: Math.floor(reportOffset / 10) + 1,
            onChange: (page) => fetchReports((page - 1) * 10),
          }}
          size="small"
        />
      </Card>

      {/* ── Schedule Modal ── */}
      <Modal
        title={editingSchedule ? t('review.editSchedule') : t('review.newScheduleModal')}
        open={scheduleModalOpen}
        onOk={handleSaveSchedule}
        onCancel={() => setScheduleModalOpen(false)}
        confirmLoading={saving}
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label={t('review.scheduleName')} rules={[{ required: true, message: t('review.nameRequired') }]}>
            <Input placeholder={t('review.scheduleNamePlaceholder')} />
          </Form.Item>
          <Form.Item name="period" label={t('table.period')} rules={[{ required: true }]}>
            <Select options={[
              { label: t('review.periodMonthly'), value: 'monthly' },
              { label: t('review.periodQuarterly'), value: 'quarterly' },
            ]} />
          </Form.Item>
          <Form.Item name="day_of_month" label={t('review.dayOfMonth')} rules={[{ required: true, message: '1-28' }]}>
            <Input type="number" min={1} max={28} placeholder="1" />
          </Form.Item>
          <Form.Item name="enabled" label={t('review.enabled')} valuePropName="checked" initialValue>
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      {/* ── Report Detail Drawer ── */}
      <Drawer
        title={t('review.reportDetail')}
        open={reportDrawerOpen}
        onClose={() => setReportDrawerOpen(false)}
        width={520}
        extra={
          selectedReport?.status === 'pending_review' && (
            <Space>
              <Popconfirm title={t('review.approveConfirm')} onConfirm={() => handleApprove(selectedReport.id)}>
                <Button type="primary" icon={<CheckCircleOutlined />}>{t('review.approve')}</Button>
              </Popconfirm>
              <Popconfirm title={t('review.dismissConfirm')} onConfirm={() => handleDismiss(selectedReport.id)}>
                <Button danger icon={<CloseCircleOutlined />}>{t('review.dismiss')}</Button>
              </Popconfirm>
            </Space>
          )
        }
      >
        {selectedReport && (
          <div>
            <Descriptions column={2} size="small" bordered style={{ marginBottom: 16 }}>
              <Descriptions.Item label={t('table.status')} span={2}>
                <Tag color={STATUS_LABEL(t)[selectedReport.status]?.color}>
                  {STATUS_LABEL(t)[selectedReport.status]?.text}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label={t('table.period')}>
                {PERIOD_LABEL(t)[selectedReport.period]}
              </Descriptions.Item>
              <Descriptions.Item label={t('review.createdAt')}>
                {new Date(selectedReport.created_at).toLocaleString('zh-CN')}
              </Descriptions.Item>
              <Descriptions.Item label={t('review.reviewer')}>{selectedReport.reviewer_name || '-'}</Descriptions.Item>
              <Descriptions.Item label={t('review.reviewedAt')}>
                {selectedReport.reviewed_at ? new Date(selectedReport.reviewed_at).toLocaleString('zh-CN') : '-'}
              </Descriptions.Item>
              {selectedReport.notes && (
                <Descriptions.Item label={t('review.notes')} span={2}>{selectedReport.notes}</Descriptions.Item>
              )}
            </Descriptions>

            {summary.summary && (
              <Row gutter={8} style={{ marginBottom: 16 }}>
                <Col span={6}><Statistic title={t('review.totalAccounts')} value={summary.summary.total_accounts || 0} /></Col>
                <Col span={6}><Statistic title={t('review.privilegedAccounts')} value={summary.summary.privileged_count || 0} /></Col>
                <Col span={6}><Statistic title={t('review.dormantAccounts')} value={summary.summary.dormant_count || 0} valueStyle={{ color: '#faad14' }} /></Col>
                <Col span={6}><Statistic title={t('review.departedAccounts')} value={summary.summary.departed_count || 0} valueStyle={{ color: '#ff4d4f' }} /></Col>
              </Row>
            )}

            {summary.dormant_accounts?.length > 0 && (
              <>
                <Title level={5} style={{ color: '#faad14' }}>{t('review.dormantAccounts')} ({summary.dormant_accounts.length})</Title>
                <Table
                  dataSource={summary.dormant_accounts.slice(0, 10)}
                  rowKey={(r: any) => r.uid}
                  size="small"
                  pagination={false}
                  columns={[
                    { title: t('table.username'), dataIndex: 'username' },
                    { title: t('table.asset'), dataIndex: 'asset_code' },
                    { title: t('table.ip'), dataIndex: 'ip' },
                    { title: t('table.lastLogin'), dataIndex: 'last_login', render: (v: string) => v ? v.slice(0, 10) : '-' },
                  ]}
                  style={{ marginBottom: 12 }}
                />
              </>
            )}

            {summary.departed_accounts?.length > 0 && (
              <>
                <Title level={5} style={{ color: '#ff4d4f' }}>{t('review.departedAccounts')} ({summary.departed_accounts.length})</Title>
                <Table
                  dataSource={summary.departed_accounts.slice(0, 10)}
                  rowKey={(r: any) => r.uid}
                  size="small"
                  pagination={false}
                  columns={[
                    { title: t('table.username'), dataIndex: 'username' },
                    { title: t('table.asset'), dataIndex: 'asset_code' },
                    { title: t('table.ip'), dataIndex: 'ip' },
                    { title: t('table.status'), dataIndex: 'status', render: (v: string) => <Tag color="red">{v}</Tag> },
                  ]}
                  style={{ marginBottom: 12 }}
                />
              </>
            )}

            {summary.high_risk_assets?.length > 0 && (
              <>
                <Title level={5}>{t('review.highRiskAssets')} ({summary.high_risk_assets.length})</Title>
                <Table
                  dataSource={summary.high_risk_assets.slice(0, 10)}
                  rowKey={(r: any) => r.asset_code}
                  size="small"
                  pagination={false}
                  columns={[
                    { title: t('table.asset'), dataIndex: 'asset_code' },
                    { title: t('table.ip'), dataIndex: 'ip' },
                    { title: t('table.scoreTotal'), dataIndex: 'risk_score', render: (v: number) => <Tag color="red">{v}</Tag> },
                    { title: t('table.level'), dataIndex: 'risk_level', render: (v: string) => <Tag>{v}</Tag> },
                  ]}
                />
              </>
            )}
          </div>
        )}
      </Drawer>
    </div>
  )
}
