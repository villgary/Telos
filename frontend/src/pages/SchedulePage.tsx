import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Table, Button, Space, Tag, Typography, Drawer, Form, Input, Select, Switch, Popconfirm, message, TimePicker, Divider } from 'antd'
import { PlusOutlined, DeleteOutlined, EditOutlined, ClockCircleOutlined, CheckCircleOutlined, StopOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import api from '../api/client'

const { Title } = Typography
const { Option } = Select

interface Asset {
  id: number
  ip: string
  hostname?: string
  os_type?: string
  asset_category?: string
  db_type?: string
}

interface Schedule {
  id: number
  name: string
  asset_id: number
  cron_expr: string
  enabled: boolean
  next_run_at?: string
  last_run_at?: string
  created_at: string
}

// Parse cron expression back to period type + form values
function parseCron(expr: string): { periodType: string; values: Record<string, any> } {
  const parts = expr.trim().split(/\s+/)
  if (parts.length !== 5) return { periodType: 'custom', values: { cron_expr: expr } }
  const [min, hour, dom, mon, dow] = parts

  const intervalHour = hour.includes('/') ? parseInt(hour.split('/')[1]) : null
  const intervalDay = dom.includes('/') ? parseInt(dom.split('/')[1]) : null
  const hourOffset = hour.includes('/') ? parseInt(hour.split('/')[0]) : parseInt(hour) || 0

  // Hourly: */N * * *  or  N */N * *
  if (intervalHour !== null && intervalDay === null && mon === '*' && dow === '*') {
    return {
      periodType: 'hourly',
      values: {
        every_n_hours: intervalHour,
        hourly_offset: hourOffset,
        time: dayjs().hour(hourOffset).minute(parseInt(min) || 0),
      },
    }
  }

  // Daily (simple): HH:MM * * *  (fixed hour, no interval)
  if (intervalDay === null && mon === '*' && dow === '*') {
    return {
      periodType: 'daily',
      values: {
        every_n_days: 1,
        time: dayjs().hour(parseInt(hour) || 0).minute(parseInt(min) || 0),
      },
    }
  }

  // Daily/Every N days: HH:MM */N * *
  if (intervalDay !== null && mon === '*' && dow === '*') {
    return {
      periodType: 'daily',
      values: {
        every_n_days: intervalDay,
        time: dayjs().hour(parseInt(hour) || 0).minute(parseInt(min) || 0),
      },
    }
  }

  // Weekly: HH:MM * * N
  if (dom === '*' && mon === '*' && !isNaN(Number(dow))) {
    return {
      periodType: 'weekly',
      values: {
        day_of_week: Number(dow),
        time: dayjs().hour(parseInt(hour) || 0).minute(parseInt(min) || 0),
      },
    }
  }

  // Monthly: HH:MM D * *
  if (!isNaN(Number(dom)) && mon === '*' && dow === '*') {
    return {
      periodType: 'monthly',
      values: {
        day_of_month: Number(dom),
        time: dayjs().hour(parseInt(hour) || 0).minute(parseInt(min) || 0),
      },
    }
  }

  return { periodType: 'custom', values: { cron_expr: expr } }
}

// Build cron from period type + values
function buildCron(periodType: string, values: Record<string, any>): string {
  switch (periodType) {
    case 'hourly': {
      const interval = values.every_n_hours ?? 1
      const offset = values.hourly_offset ?? 0
      return `${offset} */${interval} * * *`
    }
    case 'daily': {
      const interval = values.every_n_days ?? 1
      const t = values.time || dayjs().hour(3).minute(0)
      return interval === 1
        ? `${t.minute()} ${t.hour()} * * *`
        : `${t.minute()} ${t.hour()} */${interval} * *`
    }
    case 'weekly': {
      const t = values.time || dayjs().hour(3).minute(0)
      const dow = values.day_of_week ?? 1
      return `${t.minute()} ${t.hour()} * * ${dow}`
    }
    case 'monthly': {
      const t = values.time || dayjs().hour(3).minute(0)
      const dom = values.day_of_month ?? 1
      return `${t.minute()} ${t.hour()} ${dom} * *`
    }
    case 'custom':
    default:
      return values.cron_expr || ''
  }
}

function parseCronToLabel(expr: string): string {
  const parts = expr.trim().split(/\s+/)
  if (parts.length !== 5) return expr
  const [min, hour, dom, mon, dow] = parts

  const dayNames = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  const dayNamesEn = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

  const isEn = dayNamesEn.some(d => expr.includes(d)) || (/\d/.test(dow) && Number(dow) <= 6 && !isNaN(Number(dow)))

  // Try to parse interval patterns
  const intervalHour = hour.includes('/') ? parseInt(hour.split('/')[1]) : null
  const intervalDay = dom.includes('/') ? parseInt(dom.split('/')[1]) : null

  if (intervalHour && intervalDay === null && mon === '*' && dow === '*') {
    const h = hour.split('/')[0]
    if (intervalHour === 1) return isEn ? 'Every hour' : '每小时'
    return isEn ? `Every ${intervalHour}h` : `每${intervalHour}小时`
  }

  if (intervalDay && intervalDay > 1 && mon === '*' && dow === '*') {
    const timeStr = `${String(hour).padStart(2,'0')}:${String(min).padStart(2,'0')}`
    return isEn ? `Every ${intervalDay} days ${timeStr}` : `每${intervalDay}天 ${timeStr}`
  }

  if (intervalDay === 1 && mon === '*' && dow === '*') {
    const timeStr = `${String(hour).padStart(2,'0')}:${String(min).padStart(2,'0')}`
    return isEn ? `Daily ${timeStr}` : `每天 ${timeStr}`
  }

  // Simple daily: fixed hour, no interval (e.g. 0 2 * * *)
  if (intervalDay === null && mon === '*' && dow === '*') {
    const timeStr = `${String(hour).padStart(2,'0')}:${String(min).padStart(2,'0')}`
    return isEn ? `Daily ${timeStr}` : `每天 ${timeStr}`
  }

  if (dom === '*' && mon === '*' && !isNaN(Number(dow))) {
    const day = (isEn ? dayNamesEn : dayNames)[Number(dow)] || `周${dow}`
    const prefix = isEn ? 'Weekly' : '每周'
    return `${prefix} ${day} ${String(hour).padStart(2,'0')}:${String(min).padStart(2,'0')}`
  }

  if (!isNaN(Number(dom)) && mon === '*' && dow === '*') {
    return isEn ? `Monthly Day ${dom} ${String(hour).padStart(2,'0')}:${String(min).padStart(2,'0')}` : `每月${dom}日 ${String(hour).padStart(2,'0')}:${String(min).padStart(2,'0')}`
  }

  return `Cron: ${expr}`
}

export default function SchedulePage() {
  const { t, i18n } = useTranslation()
  const [schedules, setSchedules] = useState<Schedule[]>([])
  const [assets, setAssets] = useState<Asset[]>([])
  const [loading, setLoading] = useState(true)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)
  const [switchingId, setSwitchingId] = useState<number | null>(null)
  const [periodType, setPeriodType] = useState<string>('daily')
  const [editSchedule, setEditSchedule] = useState<Schedule | null>(null)

  const fetchSchedules = () => {
    setLoading(true)
    api.get('/schedules')
      .then(r => setSchedules(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  const fetchAssets = () => {
    api.get('/assets').then(r => setAssets(r.data)).catch(console.error)
  }

  useEffect(() => {
    fetchSchedules()
    fetchAssets()
  }, [])

  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      const cron_expr = buildCron(periodType, values)
      if (!cron_expr) {
        message.error(t('schedule.selectOrInputCron'))
        return
      }
      setSaving(true)
      const payload = { ...values, cron_expr }
      if (editSchedule) {
        await api.put(`/schedules/${editSchedule.id}`, payload)
        message.success(t('schedule.updated'))
      } else {
        await api.post('/schedules', payload)
        message.success(t('schedule.created'))
      }
      setDrawerOpen(false)
      form.resetFields()
      setPeriodType('daily')
      setEditSchedule(null)
      fetchSchedules()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || (editSchedule ? t('schedule.updateFailed') : t('schedule.createFailed')))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/schedules/${id}`)
      message.success(t('msg.deleted'))
      fetchSchedules()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.deleteFailed'))
    }
  }

  const handleEdit = (schedule: Schedule) => {
    setEditSchedule(schedule)
    const { periodType: pt, values } = parseCron(schedule.cron_expr)
    setPeriodType(pt)
    form.setFieldsValue({
      name: schedule.name,
      asset_id: schedule.asset_id,
      ...values,
    })
    setDrawerOpen(true)
  }

  const handleToggle = async (schedule: Schedule) => {
    setSwitchingId(schedule.id)
    try {
      await api.put(`/schedules/${schedule.id}`, { enabled: !schedule.enabled })
      fetchSchedules()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('schedule.updateFailed'))
    } finally {
      setSwitchingId(null)
    }
  }

  const dayOpts = i18n.language === 'en-US'
    ? [
        { label: 'Sunday', value: 0 }, { label: 'Monday', value: 1 }, { label: 'Tuesday', value: 2 },
        { label: 'Wednesday', value: 3 }, { label: 'Thursday', value: 4 }, { label: 'Friday', value: 5 },
        { label: 'Saturday', value: 6 },
      ]
    : [
        { label: t('schedule.daySun'), value: 0 }, { label: t('schedule.dayMon'), value: 1 },
        { label: t('schedule.dayTue'), value: 2 }, { label: t('schedule.dayWed'), value: 3 },
        { label: t('schedule.dayThu'), value: 4 }, { label: t('schedule.dayFri'), value: 5 },
        { label: t('schedule.daySat'), value: 6 },
      ]

  const monthDayOpts = i18n.language === 'en-US'
    ? Array.from({ length: 31 }, (_, i) => ({ label: `Day ${i + 1}`, value: i + 1 }))
    : Array.from({ length: 31 }, (_, i) => ({ label: `${i + 1}日`, value: i + 1 }))

  const hourIntOpts = i18n.language === 'en-US'
    ? [1, 2, 3, 4, 6, 8, 12].map(v => ({ label: v === 1 ? '1 hour (hourly)' : `${v} hours`, value: v }))
    : [1, 2, 3, 4, 6, 8, 12].map(v => ({ label: v === 1 ? '1小时（每小时）' : `${v}小时`, value: v }))

  const dayIntOpts = i18n.language === 'en-US'
    ? [1, 2, 3, 4, 5, 7, 14, 30].map(v => ({ label: v === 1 ? '1 day (daily)' : `${v} days`, value: v }))
    : [1, 2, 3, 4, 5, 7, 14, 30].map(v => ({ label: v === 1 ? '1天（每天）' : `${v}天`, value: v }))

  const columns = [
    {
      title: t('schedule.scheduleName'),
      dataIndex: 'name',
      key: 'name',
      width: 180,
    },
    {
      title: t('schedule.targetAsset'),
      dataIndex: 'asset_id',
      key: 'asset_id',
      width: 180,
      render: (asset_id: number) => {
        const asset = assets.find(a => a.id === asset_id)
        if (!asset) return `ID ${asset_id}`
        return `${asset.ip} (${asset.os_type === 'linux' ? 'Linux' : 'Windows'})`
      },
    },
    {
      title: t('schedule.execPeriod'),
      dataIndex: 'cron_expr',
      key: 'cron_expr',
      width: 220,
      render: (v: string) => (
        <Tag icon={<ClockCircleOutlined />} style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {parseCronToLabel(v)}
        </Tag>
      ),
    },
    {
      title: t('table.status'),
      dataIndex: 'enabled',
      key: 'enabled',
      width: 90,
      render: (v: boolean) => (
        <Tag color={v ? 'green' : 'default'} icon={v ? <CheckCircleOutlined /> : <StopOutlined />}>
          {v ? t('schedule.enabled') : t('schedule.disabled')}
        </Tag>
      ),
    },
    {
      title: t('table.nextRun'),
      dataIndex: 'next_run_at',
      key: 'next_run_at',
      render: (v?: string) => v ? new Date(v).toLocaleString('zh-CN') : '-',
    },
    {
      title: t('schedule.lastRun'),
      dataIndex: 'last_run_at',
      key: 'last_run_at',
      render: (v?: string) => v ? new Date(v).toLocaleString('zh-CN') : '-',
    },
    {
      title: t('table.actions'),
      key: 'actions',
      width: 140,
      render: (_: unknown, record: Schedule) => (
        <Space size="small">
          <Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>
            {t('btn.edit')}
          </Button>
          <Switch
            size="small"
            checked={record.enabled}
            loading={switchingId === record.id}
            onChange={() => handleToggle(record)}
          />
          <Popconfirm
            title={t('schedule.confirmDelete')}
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

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>{t('schedule.title')}</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); setPeriodType('daily'); setEditSchedule(null); setDrawerOpen(true) }}>
          {t('schedule.newSchedule')}
        </Button>
      </div>

      <Table
        dataSource={schedules}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10 }}
        locale={{ emptyText: t('schedule.noSchedules') }}
      />

      <Drawer
        title={editSchedule ? t('schedule.editTitle') : t('schedule.newScan')}
        onClose={() => { setDrawerOpen(false); form.resetFields(); setEditSchedule(null); setPeriodType('daily') }}
        open={drawerOpen}
        width={450}
        footer={
          <div style={{ textAlign: 'right' }}>
            <Button onClick={() => { setDrawerOpen(false); form.resetFields(); setEditSchedule(null); setPeriodType('daily') }} style={{ marginRight: 8 }}>{t('btn.cancel')}</Button>
            <Button type="primary" onClick={handleSave} loading={saving}>
              {editSchedule ? t('btn.save') : t('btn.save')}
            </Button>
          </div>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label={t('schedule.scheduleName')} rules={[{ required: true, message: t('schedule.enterScheduleName') }]}>
            <Input placeholder={t('schedule.scanWindowsAssetDaily')} />
          </Form.Item>
          <Form.Item name="asset_id" label={t('schedule.targetAsset')} rules={[{ required: true, message: t('schedule.selectAsset') }]}>
            <Select placeholder={t('schedule.selectAssetToScan')}>
              {assets.map(a => (
                <Option key={a.id} value={a.id}>
                  {a.ip} — {a.hostname || t('schedule.noHostname')} ({a.asset_category === 'database' && a.db_type ? a.db_type.toUpperCase() : (a.os_type === 'linux' ? 'Linux' : 'Windows')})
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Divider style={{ margin: '12px 0' }}>{t('schedule.execPeriod')}</Divider>

          {/* 周期类型选择 */}
          <Form.Item label={t('schedule.periodType')}>
            <Select
              value={periodType}
              onChange={v => { setPeriodType(v); form.setFieldsValue({ cron_expr: '' }) }}
              style={{ width: '100%' }}
            >
              <Option value="hourly">{t('schedule.periodHourly')}</Option>
              <Option value="daily">{t('schedule.periodDaily')}</Option>
              <Option value="weekly">{t('schedule.periodWeekly')}</Option>
              <Option value="monthly">{t('schedule.periodMonthly')}</Option>
              <Option value="custom">{t('schedule.periodCustom')}</Option>
            </Select>
          </Form.Item>

          {/* 每N小时 */}
          {periodType === 'hourly' && (
            <Form.Item label={t('schedule.everyNHours')}>
              <Space>
                <Form.Item name="every_n_hours" initialValue={1} noStyle>
                  <Select style={{ width: 130 }}>
                    {hourIntOpts.map(o => <Option key={o.value} value={o.value}>{o.label}</Option>)}
                  </Select>
                </Form.Item>
                <span>{t('schedule.startOffset')}</span>
                <Form.Item name="hourly_offset" initialValue={0} noStyle>
                  <Select style={{ width: 90 }}>
                    {Array.from({ length: 24 }, (_, i) => (
                      <Option key={i} value={i}>{String(i).padStart(2,'0')}:00</Option>
                    ))}
                  </Select>
                </Form.Item>
              </Space>
            </Form.Item>
          )}

          {/* 每N天 */}
          {periodType === 'daily' && (
            <Form.Item label={t('schedule.everyNdays')}>
              <Space>
                <Form.Item name="every_n_days" initialValue={1} noStyle>
                  <Select style={{ width: 120 }}>
                    {dayIntOpts.map(o => <Option key={o.value} value={o.value}>{o.label}</Option>)}
                  </Select>
                </Form.Item>
                <span>{t('schedule.atTime')}</span>
                <Form.Item name="time" initialValue={dayjs().hour(3).minute(0)} noStyle>
                  <TimePicker format="HH:mm" style={{ width: 90 }} />
                </Form.Item>
              </Space>
            </Form.Item>
          )}

          {/* 每周 */}
          {periodType === 'weekly' && (
            <Form.Item label={t('schedule.dayOfWeek')}>
              <Space wrap>
                <Form.Item name="day_of_week" initialValue={1} noStyle>
                  <Select style={{ width: 120 }}>
                    {dayOpts.map(o => <Option key={o.value} value={o.value}>{o.label}</Option>)}
                  </Select>
                </Form.Item>
                <span>{t('schedule.atTime')}</span>
                <Form.Item name="time" initialValue={dayjs().hour(3).minute(0)} noStyle>
                  <TimePicker format="HH:mm" style={{ width: 90 }} />
                </Form.Item>
              </Space>
            </Form.Item>
          )}

          {/* 每月 */}
          {periodType === 'monthly' && (
            <Form.Item label={t('schedule.dayOfMonth')}>
              <Space wrap>
                <Form.Item name="day_of_month" initialValue={1} noStyle>
                  <Select style={{ width: 120 }}>
                    {monthDayOpts.map(o => <Option key={o.value} value={o.value}>{o.label}</Option>)}
                  </Select>
                </Form.Item>
                <span>{t('schedule.atTime')}</span>
                <Form.Item name="time" initialValue={dayjs().hour(3).minute(0)} noStyle>
                  <TimePicker format="HH:mm" style={{ width: 90 }} />
                </Form.Item>
              </Space>
            </Form.Item>
          )}

          {/* 自定义 cron */}
          {periodType === 'custom' && (
            <>
              <Form.Item
                name="cron_expr"
                label={t('schedule.customCron')}
                rules={[{ required: true, message: t('schedule.enterCronExpr') }]}
              >
                <Input placeholder="0 3 * * *" />
              </Form.Item>
              <Form.Item style={{ marginBottom: 0 }}>
                <div style={{ fontSize: 12, color: '#999', lineHeight: 1.6 }}>
                  <div style={{ marginBottom: 4, color: '#666', fontWeight: 500 }}>{t('schedule.cronFormat')}</div>
                  <div><code>分 时 日 月 周</code></div>
                  <div style={{ marginTop: 4 }}>
                    <span style={{ color: '#52c41a' }}>0 3 * * *</span> → {t('schedule.cronDaily')}<br />
                    <span style={{ color: '#52c41a' }}>30 2 * * 1</span> → {t('schedule.cronWeekly')}<br />
                    <span style={{ color: '#52c41a' }}>0 */2 * * *</span> → {t('schedule.cronEvery2h')}<br />
                    <span style={{ color: '#52c41a' }}>0 0 1 * *</span> → {t('schedule.cronMonthly')}
                  </div>
                </div>
              </Form.Item>
            </>
          )}
        </Form>
      </Drawer>
    </div>
  )
}
