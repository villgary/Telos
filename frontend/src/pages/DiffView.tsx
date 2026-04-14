import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Select, Table, Tag, Typography, Card, Space, Empty, Alert, Button } from 'antd'
import {
  PlusCircleFilled, MinusCircleFilled,
  CaretUpFilled, CaretDownFilled, InfoCircleFilled,
  SwapOutlined,
} from '@ant-design/icons'
import api from '../api/client'

const { Title, Text } = Typography

interface Asset {
  id: number
  ip: string
  hostname?: string
  os_type?: string
}

interface ScanJob {
  id: number
  asset_id: number
  status: string
  started_at: string
  success_count: number
}

interface DiffItem {
  diff_type: string
  risk_level: string
  username: string
  uid_sid: string
  field_changes?: Record<string, [unknown, unknown]>
}

interface DiffResponse {
  base_job_id: number
  compare_job_id: number
  items: DiffItem[]
  summary: Record<string, number>
}

const DIFF_ICON: Record<string, React.ReactNode> = {
  added: <PlusCircleFilled style={{ color: '#cf1322' }} />,
  removed: <MinusCircleFilled style={{ color: '#faad14' }} />,
  escalated: <CaretUpFilled style={{ color: '#cf1322' }} />,
  deactivated: <CaretDownFilled style={{ color: '#52c41a' }} />,
  modified: <InfoCircleFilled style={{ color: '#faad14' }} />,
}

const DIFF_COLOR: Record<string, string> = {
  added: '#fff1f0',
  removed: '#fffbe6',
  escalated: '#fff1f0',
  deactivated: '#f6ffed',
  modified: '#fffbe6',
}

const DIFF_LABEL = (t: (k: string) => string): Record<string, string> => ({
  added: t('diff.added'),
  removed: t('diff.removed'),
  escalated: t('diff.escalated'),
  deactivated: t('diff.deactivated'),
  modified: t('diff.modified'),
})

const RISK_LABEL = (t: (k: string) => string): Record<string, string> => ({
  critical: t('diff.riskHigh'),
  warning: t('diff.riskWarning'),
  info: t('diff.riskInfo'),
})

const RISK_COLOR: Record<string, string> = {
  critical: 'red',
  warning: 'orange',
  info: 'green',
}

export default function DiffView() {
  const { t } = useTranslation()
  const [assets, setAssets] = useState<Asset[]>([])
  const [jobs, setJobs] = useState<ScanJob[]>([])
  const [assetJobs, setAssetJobs] = useState<ScanJob[]>([])
  const [selectedAssetId, setSelectedAssetId] = useState<number | null>(null)
  const [baseJobId, setBaseJobId] = useState<number | null>(null)
  const [compareJobId, setCompareJobId] = useState<number | null>(null)
  const [diffResult, setDiffResult] = useState<DiffResponse | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.get('/assets').then(r => setAssets(r.data)).catch(console.error)
    api.get('/scan-jobs').then(r => setJobs(r.data)).catch(console.error)
  }, [])

  useEffect(() => {
    if (!selectedAssetId) { setAssetJobs([]); return }
    const filtered = jobs
      .filter(j => j.asset_id === selectedAssetId)
      .sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())
    setAssetJobs(filtered)
    setBaseJobId(null)
    setCompareJobId(null)
    setDiffResult(null)
  }, [selectedAssetId, jobs])

  const handleDiff = async () => {
    if (!baseJobId || !compareJobId) return
    setLoading(true)
    try {
      const r = await api.get('/snapshots/diff', {
        params: { base_job_id: baseJobId, compare_job_id: compareJobId },
      })
      setDiffResult(r.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const getAssetLabel = (assetId: number) => {
    const a = assets.find(a => a.id === assetId)
    if (!a) return `${t('diff.asset')} #${assetId}`
    return `${a.ip}${a.hostname ? ` (${a.hostname})` : ''}`
  }

  const getJobLabel = (job: ScanJob) => {
    const d = new Date(job.started_at)
    const dateStr = d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
    return `${dateStr} · ${job.success_count} ${t('diff.accounts')}`
  }

  const columns = [
    {
      title: t('diff.type'),
      key: 'diff_type',
      width: 140,
      render: (_: unknown, r: DiffItem) => (
        <Space>
          {DIFF_ICON[r.diff_type]}
          <Tag color={DIFF_COLOR[r.diff_type] ? RISK_COLOR[r.risk_level] : 'default'}>
            {DIFF_LABEL(t)[r.diff_type] || r.diff_type}
          </Tag>
        </Space>
      ),
    },
    {
      title: t('diff.risk'),
      dataIndex: 'risk_level',
      key: 'risk_level',
      width: 80,
      render: (v: string) => <Tag color={RISK_COLOR[v]}>{RISK_LABEL(t)[v]}</Tag>,
    },
    { title: t('diff.username'), dataIndex: 'username', key: 'username', width: 140 },
    { title: t('diff.uidSid'), dataIndex: 'uid_sid', key: 'uid_sid', width: 100 },
    {
      title: t('diff.changeDetail'),
      key: 'changes',
      render: (_: unknown, r: DiffItem) => {
        if (!r.field_changes) return '-'
        return (
          <Space direction="vertical" size={0}>
            {Object.entries(r.field_changes).map(([k, [oldV, newV]]) => (
              <Text key={k} type="secondary" style={{ fontSize: 12 }}>
                {k}: <s>{String(oldV ?? '—')}</s> → <b>{String(newV ?? '—')}</b>
              </Text>
            ))}
          </Space>
        )
      },
    },
  ]

  return (
    <div>
      <Title level={4}>{t('diff.title')}</Title>

      <Card style={{ marginBottom: 16 }}>
        <Space size="large" wrap style={{ alignItems: 'flex-start' }}>
          <div>
            <Text strong>{t('diff.selectAsset')}:</Text>
            <Select
              style={{ width: 220, marginLeft: 8 }}
              placeholder={t('diff.selectAssetFirst')}
              value={selectedAssetId}
              onChange={v => setSelectedAssetId(v)}
              allowClear
              showSearch
              filterOption={(input, opt) =>
                (opt?.children as unknown as string)?.toLowerCase().includes(input.toLowerCase())
              }
            >
              {[...new Map(jobs.map(j => [j.asset_id, j])).entries()].map(([aid]) => {
                const a = assets.find(a => a.id === aid)
                return (
                  <Select.Option key={aid} value={aid}>
                    {getAssetLabel(aid)}
                  </Select.Option>
                )
              })}
            </Select>
          </div>

          {assetJobs.length >= 2 && (
            <>
              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>{t('diff.baseSnapshot')} ({t('diff.older')})</Text>
                <div style={{ marginTop: 4 }}>
                  <Select
                    style={{ width: 200 }}
                    placeholder={t('diff.selectBase')}
                    value={baseJobId}
                    onChange={v => setBaseJobId(v)}
                    optionLabelProp="label"
                  >
                    {assetJobs.map((j, i) => (
                      <Select.Option key={j.id} value={j.id} label={getJobLabel(j)}>
                        <Space size={4}>
                          <Tag color="blue" style={{ marginRight: 0 }}>{i + 1}</Tag>
                          {getJobLabel(j)}
                        </Space>
                      </Select.Option>
                    ))}
                  </Select>
                </div>
              </div>

              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>{t('diff.compareSnapshot')} ({t('diff.newer')})</Text>
                <div style={{ marginTop: 4 }}>
                  <Select
                    style={{ width: 200 }}
                    placeholder={t('diff.selectCompare')}
                    value={compareJobId}
                    onChange={v => setCompareJobId(v)}
                    optionLabelProp="label"
                  >
                    {assetJobs.map((j, i) => (
                      <Select.Option key={j.id} value={j.id} label={getJobLabel(j)}>
                        <Space size={4}>
                          <Tag color="purple" style={{ marginRight: 0 }}>{i + 1}</Tag>
                          {getJobLabel(j)}
                        </Space>
                      </Select.Option>
                    ))}
                  </Select>
                </div>
              </div>

              <div style={{ marginTop: 22 }}>
                <Button
                  type="primary"
                  icon={<SwapOutlined />}
                  onClick={handleDiff}
                  loading={loading}
                  disabled={!baseJobId || !compareJobId}
                >
                  {t('diff.executeCompare')}
                </Button>
              </div>
            </>
          )}
        </Space>

        {assetJobs.length >= 2 && (
          <div style={{ marginTop: 12, color: '#999', fontSize: 12 }}>
            {t('diff.hint')}
          </div>
        )}
      </Card>

      {diffResult && (
        <>
          <Card title={t('diff.summary')} style={{ marginBottom: 16 }}>
            <Space size="large">
              <Tag color="red" style={{ padding: '4px 12px' }}>
                {t('diff.addedAccounts')}: {diffResult.summary.added ?? 0}
              </Tag>
              <Tag color="orange" style={{ padding: '4px 12px' }}>
                {t('diff.removedAccounts')}: {diffResult.summary.removed ?? 0}
              </Tag>
              <Tag color="red" style={{ padding: '4px 12px' }}>
                {t('diff.privilegeUpgrades')}: {diffResult.summary.escalated ?? 0}
              </Tag>
              <Tag color="green" style={{ padding: '4px 12px' }}>
                {t('diff.privilegeDowngrades')}: {diffResult.summary.deactivated ?? 0}
              </Tag>
              <Tag color="orange" style={{ padding: '4px 12px' }}>
                {t('diff.modifiedAccounts')}: {diffResult.summary.modified ?? 0}
              </Tag>
            </Space>
          </Card>

          <Card>
            {diffResult.items.length === 0 ? (
              <Empty description={t('diff.noDifferences')} />
            ) : (
              <Table
                dataSource={diffResult.items}
                columns={columns}
                rowKey={(_, i) => String(i)}
                loading={loading}
                pagination={{ pageSize: 20 }}
                size="small"
              />
            )}
          </Card>
        </>
      )}

      {selectedAssetId && assetJobs.length === 0 && (
        <Alert type="info" message={t('diff.noJobsForAsset')} showIcon />
      )}

      {!selectedAssetId && jobs.length === 0 && (
        <Alert type="info" message={t('diff.noJobsYet')} showIcon />
      )}

      {assetJobs.length === 1 && (
        <Alert type="info" message={t('diff.need2Scans')} showIcon />
      )}
    </div>
  )
}
