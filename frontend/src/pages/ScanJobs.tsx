import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Table, Tag, Typography, Button, Drawer, Descriptions, message, Popconfirm, Space } from 'antd'
import { EyeOutlined, DeleteOutlined, FlagOutlined } from '@ant-design/icons'
import api from '../api/client'

const { Title } = Typography

interface ScanJob {
  id: number
  asset_id: number
  asset_ip?: string
  trigger_type: string
  status: string
  success_count: number
  failed_count: number
  error_message?: string
  started_at: string
  finished_at?: string
  created_at: string
}

interface Snapshot {
  id: number
  username: string
  uid_sid: string
  is_admin: boolean
  account_status?: string
  home_dir?: string
  shell?: string
  groups: unknown[]
  last_login?: string
  snapshot_time: string
  is_baseline?: boolean
}

interface JobDetail extends ScanJob {
  snapshots: Snapshot[]
}

const STATUS_MAP = (t: (k: string) => string): Record<string, { color: string; label: string }> => ({
  success: { color: 'green', label: t('status.success') },
  failed: { color: 'red', label: t('status.failed') },
  running: { color: 'blue', label: t('status.running') },
  pending: { color: 'default', label: t('status.pending') },
  partial_success: { color: 'orange', label: t('status.partialSuccess') },
  cancelled: { color: 'default', label: t('status.cancelled') },
})

export default function ScanJobs() {
  const { t } = useTranslation()
  const [jobs, setJobs] = useState<ScanJob[]>([])
  const [loading, setLoading] = useState(true)
  const [detail, setDetail] = useState<JobDetail | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)

  const fetchJobs = () => {
    setLoading(true)
    api.get('/scan-jobs')
      .then(r => setJobs(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchJobs() }, [])

  const handleSetBaseline = async (jobId: number) => {
    try {
      await api.post(`/scan-jobs/${jobId}/set-baseline`)
      message.success(t('scan.setBaselineSuccess'))
      fetchJobs()
      setDetail(null)
      setDrawerOpen(false)
    } catch {
      message.error(t('scan.setBaselineFailed'))
    }
  }

  const handleDelete = async (jobId: number) => {
    try {
      await api.delete(`/scan-jobs/${jobId}`)
      message.success(t('msg.deleteSuccess'))
      fetchJobs()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.deleteFailed'))
    }
  }

  const openDetail = async (job: ScanJob) => {
    setDrawerOpen(true)
    setDetailLoading(true)
    try {
      const r = await api.get(`/scan-jobs/${job.id}`)
      setDetail(r.data)
    } catch (e) {
      console.error(e)
    } finally {
      setDetailLoading(false)
    }
  }

  const snapColumns = [
    {
      title: t('snapshot.username'),
      dataIndex: 'username',
      key: 'username',
      width: 120,
      render: (v: string, r: Snapshot) => (
        <span>
          {r.is_baseline && <Tag color="blue" style={{ marginRight: 4 }}>{t('snapshot.baseline')}</Tag>}
          {v}
        </span>
      ),
    },
    {
      title: t('snapshot.uid'),
      dataIndex: 'uid_sid',
      key: 'uid_sid',
      width: 80,
    },
    {
      title: t('snapshot.isAdmin'),
      dataIndex: 'is_admin',
      key: 'is_admin',
      width: 90,
      render: (v: boolean) => (v ? <Tag color="red">{t('snapshot.yes')}</Tag> : <Tag>{t('snapshot.no')}</Tag>),
    },
    {
      title: t('snapshot.status'),
      dataIndex: 'account_status',
      key: 'account_status',
      width: 90,
      render: (v?: string) => v || '-',
    },
    {
      title: t('snapshot.homeDir'),
      dataIndex: 'home_dir',
      key: 'home_dir',
      ellipsis: true,
    },
    {
      title: t('snapshot.shell'),
      dataIndex: 'shell',
      key: 'shell',
      width: 120,
    },
  ]

  const columns = [
    {
      title: t('scan.jobId'),
      dataIndex: 'id',
      key: 'id',
      width: 80,
    },
    {
      title: t('asset.ipAddress'),
      key: 'asset',
      width: 160,
      render: (_: unknown, r: ScanJob) => (
        <span>
          <Tag color="blue">{r.asset_ip || `#${r.asset_id}`}</Tag>
        </span>
      ),
    },
    {
      title: t('scan.triggerType'),
      dataIndex: 'trigger_type',
      key: 'trigger_type',
      width: 90,
      render: (v: string) => (v === 'manual' ? t('scan.manual') : t('scan.scheduled')),
    },
    {
      title: t('scan.status'),
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (v: string) => {
        const s = STATUS_MAP(t)[v] || { color: 'default', label: v }
        return <Tag color={s.color}>{s.label}</Tag>
      },
    },
    {
      title: t('scan.accountsFound'),
      key: 'counts',
      render: (_: unknown, r: ScanJob) => `${r.success_count} ${t('scan.success')} / ${r.failed_count} ${t('scan.failed')}`,
    },
    {
      title: t('scan.startedAt'),
      dataIndex: 'started_at',
      key: 'started_at',
      render: (v: string) => new Date(v).toLocaleString('zh-CN'),
    },
    {
      title: t('scan.duration'),
      key: 'duration',
      render: (_: unknown, r: ScanJob) => {
        if (!r.finished_at) return '-'
        const ms = new Date(r.finished_at).getTime() - new Date(r.started_at).getTime()
        return `${(ms / 1000).toFixed(1)}s`
      },
    },
    {
      title: t('table.actions'),
      key: 'actions',
      width: 120,
      render: (_: unknown, r: ScanJob) => (
        <Space size="small">
          <Button size="small" icon={<EyeOutlined />} onClick={() => openDetail(r)}>
            {t('btn.detail')}
          </Button>
          <Popconfirm
            title={t('msg.deleteConfirm')}
            onConfirm={() => handleDelete(r.id)}
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

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>{t('scan.title')}</Title>
        <Button onClick={fetchJobs}>{t('btn.refresh')}</Button>
      </div>

      <Table
        dataSource={jobs}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10 }}
      />

      <Drawer
        title={`${t('scan.jobDetail')} #${detail?.id ?? ''} — ${detail?.asset_ip ?? `资产 #${detail?.asset_id}`}`}
        onClose={() => { setDrawerOpen(false); setDetail(null) }}
        open={drawerOpen}
        width={700}
        footer={
          detail?.status === 'success' ? (
            <div style={{ textAlign: 'right' }}>
              <Button
                type="primary"
                icon={<FlagOutlined />}
                onClick={() => handleSetBaseline(detail.id)}
              >
                {t('scan.setAsBaseline')}
              </Button>
            </div>
          ) : null
        }
      >
        {detail && (
          <>
            <Descriptions column={2} bordered size="small" style={{ marginBottom: 16 }}>
              <Descriptions.Item label={t('asset.ipAddress')}>
                <Tag color="blue">{detail.asset_ip || detail.asset_id}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label={t('scan.status')}>
                <Tag color={STATUS_MAP(t)[detail.status]?.color}>{STATUS_MAP(t)[detail.status]?.label}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label={t('scan.triggerType')}>
                {detail.trigger_type === 'manual' ? t('scan.manual') : t('scan.scheduled')}
              </Descriptions.Item>
              <Descriptions.Item label={t('scan.startedAt')}>
                {new Date(detail.started_at).toLocaleString('zh-CN')}
              </Descriptions.Item>
              {detail.error_message && (
                <Descriptions.Item label={t('scan.errorMsg')} span={2}>
                  <span style={{ color: 'red' }}>{detail.error_message}</span>
                </Descriptions.Item>
              )}
            </Descriptions>

            <Title level={5}>{t('scan.accountSnapshots')} ({detail.snapshots?.length ?? 0})</Title>
            <Table
              dataSource={detail.snapshots ?? []}
              columns={snapColumns}
              rowKey="id"
              loading={detailLoading}
              pagination={{ pageSize: 10 }}
              size="small"
              scroll={{ x: 700 }}
            />
          </>
        )}
      </Drawer>
    </div>
  )
}
