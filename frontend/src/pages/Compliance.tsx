import { useEffect, useState } from 'react'
import {
  Row, Col, Card, Typography, Tag, Space, Spin, Table, Button,
  message, Progress, Tooltip, Badge, Empty, Alert,
} from 'antd'
import {
  SafetyCertificateOutlined, ReloadOutlined, CheckCircleOutlined,
  CloseCircleOutlined, ExclamationCircleOutlined, HistoryOutlined,
  DownloadOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { useTranslation } from 'react-i18next'
import api, { exportComplianceRun } from '../api/client'

const { Title, Text, Paragraph } = Typography

const SCORE_COLOR = (score: number) =>
  score >= 80 ? '#52c41a' : score >= 50 ? '#faad14' : '#ff4d4f'

const SEVERITY_COLOR: Record<string, string> = {
  critical: 'red',
  high: 'orange',
  medium: 'gold',
  low: 'green',
}

const STATUS_COLOR: Record<string, string> = {
  pass: 'green',
  fail: 'red',
  error: 'orange',
  never_run: 'default',
}

const STATUS_ICON: Record<string, React.ReactNode> = {
  pass: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
  fail: <CloseCircleOutlined style={{ color: '#ff4d4f' }} />,
  error: <ExclamationCircleOutlined style={{ color: '#faad14' }} />,
  never_run: <ExclamationCircleOutlined style={{ color: '#999' }} />,
}

interface EvidenceItem {
  asset_code: string
  ip: string
  hostname?: string
  username?: string
  description: string
  description_key?: string
}

interface CheckItem {
  check_key: string
  title: string
  description?: string
  title_key?: string
  description_key?: string
  severity: string
  status: string
  failed_count: number
  passed_count: number
  evidence: EvidenceItem[]
}

interface FrameworkDashboard {
  slug: string
  name: string
  description?: string
  name_key?: string
  description_key?: string
  score: number
  total: number
  passed: number
  failed: number
  checks: CheckItem[]
}

interface RunItem {
  id: number
  framework_id: number
  framework_slug: string
  framework_name: string
  trigger_type: string
  status: string
  total: number
  passed: number
  failed: number
  started_at: string
  finished_at?: string
}

interface ExpandedRow {
  key: string
  check_key: string
  title: string
  evidence: EvidenceItem[]
}

export default function Compliance() {
  const { t } = useTranslation()
  const [frameworks, setFrameworks] = useState<FrameworkDashboard[]>([])
  const [runs, setRuns] = useState<RunItem[]>([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState<string | null>(null)
  const [expandedKeys, setExpandedKeys] = useState<string[]>([])

  const fetchDashboard = () => {
    setLoading(true)
    Promise.all([
      api.get('/compliance/dashboard'),
      api.get('/compliance/runs', { params: { limit: 10 } }),
    ]).then(([dashRes, runsRes]) => {
      setFrameworks(dashRes.data.frameworks)
      setRuns(runsRes.data.runs)
    }).catch(() => message.error(t('compliance.loadFailed')))
    .finally(() => setLoading(false))
  }

  useEffect(() => { fetchDashboard() }, [])

  const handleRun = async (slug: string) => {
    setRunning(slug)
    try {
      await api.post(`/compliance/frameworks/${slug}/run`)
      message.success(t('compliance.assessmentDone', `${slug.toUpperCase()} Assessment Done`))
      fetchDashboard()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('compliance.assessmentFailed'))
    } finally {
      setRunning(null)
    }
  }

  const handleRunAll = async () => {
    setRunning('all')
    try {
      await api.post('/compliance/run-all')
      message.success(t('compliance.allDone'))
      fetchDashboard()
    } catch {
      message.error(t('compliance.assessmentFailed'))
    } finally {
      setRunning(null)
    }
  }

  const handleExportRun = async (runId: number) => {
    try {
      const res = await exportComplianceRun(runId)
      const blob = new Blob([res.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${t('compliance.reportFileName')}_${runId}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    } catch { message.error(t('compliance.exportFailed')) }
  }

  const allColumns: ColumnsType<CheckItem> = [
    {
      title: t('compliance.checkItems'),
      key: 'title',
      render: (_, r) => (
        <Space direction="vertical" size={0}>
          <Space size={4}>
            <Tag color={SEVERITY_COLOR[r.severity]} style={{ fontSize: 11 }}>
              {r.severity.toUpperCase()}
            </Tag>
            <Text strong style={{ fontSize: 13 }}>
              {r.title_key ? t(r.title_key) : r.title}
            </Text>
          </Space>
          {(r.description_key ? t(r.description_key) : r.description) && (
            <Text type="secondary" style={{ fontSize: 11 }}>
              {r.description_key ? t(r.description_key) : r.description}
            </Text>
          )}
        </Space>
      ),
    },
    {
      title: t('compliance.status'),
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (s: string) => (
        <Space size={4}>
          {STATUS_ICON[s]}
          <Text style={{ color: STATUS_COLOR[s] === 'green' ? '#52c41a' : STATUS_COLOR[s] === 'red' ? '#ff4d4f' : '#999', fontSize: 12 }}>
            {s === 'pass' ? t('status.pass') : s === 'fail' ? t('status.fail') : s === 'error' ? t('compliance.error') : t('compliance.notRun')}
          </Text>
        </Space>
      ),
    },
    {
      title: t('compliance.passFailCounts'),
      key: 'counts',
      width: 120,
      render: (_, r) => (
        <Text style={{ fontSize: 12 }}>
          <Text style={{ color: '#52c41a' }}>{r.passed_count}</Text>
          {' / '}
          <Text style={{ color: '#ff4d4f' }}>{r.failed_count}</Text>
        </Text>
      ),
    },
    {
      title: t('btn.detail'),
      key: 'evidence',
      render: (_, r) => {
        if (!r.evidence || r.evidence.length === 0) {
          return <Text type="secondary" style={{ fontSize: 12 }}>—</Text>
        }
        return (
          <Button
            type="link"
            size="small"
            style={{ fontSize: 12, padding: 0 }}
            onClick={() => {
              const key = `${r.check_key}`
              setExpandedKeys(prev =>
                prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]
              )
            }}
          >
            {t('compliance.viewEvidence')} {r.evidence.length} {t('compliance.items')}
          </Button>
        )
      },
    },
  ]

  const expandedRowRender = (record: CheckItem) => {
    if (!record.evidence || record.evidence.length === 0) {
      return <Text type="secondary">{t('compliance.noFailDetail')}</Text>
    }
    return (
      <Space direction="vertical" size={4} style={{ padding: '8px 16px' }}>
        {record.evidence.map((ev, i) => (
          <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 12 }}>
            <Tag color="blue" style={{ flexShrink: 0 }}>{ev.asset_code || ev.ip}</Tag>
            {ev.username && <Tag color="orange" style={{ flexShrink: 0 }}>{ev.username}</Tag>}
            <Text style={{ fontSize: 12 }}>{ev.description_key ? t(ev.description_key) : ev.description}</Text>
          </div>
        ))}
      </Space>
    )
  }

  const runColumns: ColumnsType<RunItem> = [
    {
      title: t('compliance.time'),
      dataIndex: 'started_at',
      key: 'started_at',
      width: 170,
      render: (v: string) => new Date(v).toLocaleString('zh-CN'),
    },
    {
      title: t('compliance.framework'),
      dataIndex: 'framework_name',
      key: 'framework_name',
      width: 120,
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: t('compliance.trigger'),
      dataIndex: 'trigger_type',
      key: 'trigger_type',
      width: 80,
      render: (v: string) => (
        <Tag color={v === 'manual' ? 'blue' : 'default'} style={{ fontSize: 11 }}>
          {v === 'manual' ? t('compliance.manual') : v === 'scheduled' ? t('compliance.scheduled') : t('compliance.api')}
        </Tag>
      ),
    },
    {
      title: t('compliance.result'),
      key: 'result',
      render: (_, r) => (
        <Space size={4}>
          <Badge status={r.status === 'completed' ? 'success' : r.status === 'failed' ? 'error' : 'processing'} />
          <Text style={{ fontSize: 12 }}>
            <Text style={{ color: '#52c41a' }}>{r.passed}</Text>
            {' / '}
            <Text style={{ color: '#ff4d4f' }}>{r.failed}</Text>
            {' / '}
            {r.total}
          </Text>
        </Space>
      ),
    },
    {
      title: t('compliance.status'),
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (v: string) => (
        <Tag color={v === 'completed' ? 'green' : v === 'failed' ? 'red' : 'processing'}>
          {v === 'completed' ? t('compliance.completed') : v === 'failed' ? t('status.fail') : t('compliance.running')}
        </Tag>
      ),
    },
    {
      title: t('compliance.actions'),
      key: 'actions',
      width: 80,
      render: (_, r: RunItem) =>
        r.status === 'completed' ? (
          <Button size="small" icon={<DownloadOutlined />} onClick={() => handleExportRun(r.id)}>{t('compliance.export')}</Button>
        ) : null,
    },
  ]

  if (loading) return <div style={{ textAlign: 'center', marginTop: 80 }}><Spin size="large" /></div>

  const totalScore = frameworks.length > 0
    ? Math.round(frameworks.reduce((s, f) => s + f.score, 0) / frameworks.length)
    : 0

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>
            <SafetyCertificateOutlined style={{ marginRight: 8 }} />
            {t('compliance.title')}
          </Title>
          <Text type="secondary">{t('compliance.subtitle')}</Text>
        </div>
        <Space>
          <Button
            icon={<ReloadOutlined spin={running === 'all'} />}
            onClick={handleRunAll}
            loading={running === 'all'}
          >
            {t('compliance.runAll')}
          </Button>
          <Button icon={<ReloadOutlined />} onClick={fetchDashboard}>
            {t('compliance.refresh')}
          </Button>
        </Space>
      </div>

      {/* 综合评分 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={24}>
          <Card bodyStyle={{ padding: '16px 24px', textAlign: 'center' }}>
            <Space size={24} wrap>
              <div style={{ textAlign: 'center' }}>
                <Progress
                  type="circle"
                  percent={totalScore}
                  strokeColor={SCORE_COLOR(totalScore)}
                  size={72}
                  format={p => <span style={{ fontSize: 16, fontWeight: 700 }}>{p}%</span>}
                />
                <div style={{ marginTop: 6 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>{t('compliance.overallScore')}</Text>
                </div>
              </div>
              {frameworks.map(fw => (
                <div key={fw.slug} style={{ textAlign: 'center' }}>
                  <Progress
                    type="circle"
                    percent={fw.score}
                    strokeColor={SCORE_COLOR(fw.score)}
                    size={60}
                    format={p => <span style={{ fontSize: 13, fontWeight: 600 }}>{p}%</span>}
                  />
                  <div style={{ marginTop: 4 }}>
                    <Text strong style={{ fontSize: 13 }}>{fw.name_key ? t(fw.name_key) : fw.name}</Text>
                    <br />
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {fw.passed}/{fw.total} {t('compliance.passed')}
                    </Text>
                  </div>
                </div>
              ))}
            </Space>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        {/* Framework Cards */}
        <Col xs={24} lg={14}>
          {frameworks.map(fw => (
            <Card
              key={fw.slug}
              title={
                <Space>
                  <SafetyCertificateOutlined />
                  {fw.name_key ? t(fw.name_key) : fw.name}
                  {fw.description_key && (
                    <Text type="secondary" style={{ fontSize: 12 }}>— {t(fw.description_key)}</Text>
                  )}
                </Space>
              }
              extra={
                <Button
                  type="primary"
                  size="small"
                  icon={<ReloadOutlined spin={running === fw.slug} />}
                  onClick={() => handleRun(fw.slug)}
                  loading={running === fw.slug}
                >
                  {t('compliance.runAssessment')}
                </Button>
              }
              style={{ marginBottom: 16 }}
              bodyStyle={{ padding: 0 }}
            >
              <Table
                columns={allColumns}
                dataSource={fw.checks.map(c => ({ ...c, key: c.check_key }))}
                expandable={{
                  expandedRowRender,
                  expandedRowKeys: expandedKeys,
                  onExpand: (expanded, record) => {
                    setExpandedKeys(expanded ? [record.check_key] : [])
                  },
                }}
                pagination={false}
                size="small"
                rowKey="check_key"
                summary={() => (
                  <Table.Summary fixed>
                    <Table.Summary.Row>
                      <Table.Summary.Cell index={0} colSpan={4}>
                        <Space>
                          <Text style={{ fontSize: 12 }}>
                            {t('compliance.complianceRate')}:
                            <Text strong style={{
                              color: SCORE_COLOR(fw.score),
                              fontSize: 14,
                            }}>
                              {fw.score}%
                            </Text>
                            {' '}({fw.passed}/{fw.total} {t('compliance.passed')}, {fw.failed} {t('compliance.itemsToFix')})
                          </Text>
                        </Space>
                      </Table.Summary.Cell>
                    </Table.Summary.Row>
                  </Table.Summary>
                )}
              />
            </Card>
          ))}

          {frameworks.length === 0 && (
            <Empty description={t('compliance.noFrameworks')} />
          )}
        </Col>

        {/* Run History */}
        <Col xs={24} lg={10}>
          <Card
            title={<Space><HistoryOutlined />{t('compliance.runHistory')}</Space>}
            bodyStyle={{ padding: 0 }}
          >
            {runs.length === 0 ? (
              <Empty description={t('compliance.noHistory')} style={{ margin: '40px 0' }} />
            ) : (
              <Table
                columns={runColumns}
                dataSource={runs.map(r => ({ ...r, key: r.id }))}
                pagination={false}
                size="small"
                rowKey="id"
                scroll={{ x: 500 }}
              />
            )}
          </Card>

          {/* Compliance Tips */}
          <Card title={t('compliance.remediationTips')} style={{ marginTop: 16 }} bodyStyle={{ padding: '12px 16px' }}>
            {frameworks.flatMap(fw =>
              fw.checks
                .filter(c => c.status === 'fail')
                .map(c => (
                  <Alert
                    key={`${fw.slug}-${c.check_key}`}
                    type="warning"
                    showIcon
                    style={{ marginBottom: 8 }}
                    message={
                      <Space size={4}>
                        <Tag color={SEVERITY_COLOR[c.severity]} style={{ fontSize: 10 }}>
                          {fw.name_key ? t(fw.name_key) : fw.name}
                        </Tag>
                        <Text strong style={{ fontSize: 12 }}>
                          {c.title_key ? t(c.title_key) : c.title}
                        </Text>
                      </Space>
                    }
                    description={
                      <Text style={{ fontSize: 11 }}>
                        {(() => {
                          const ev0 = c.evidence?.[0]
                          const evDesc = ev0?.description_key ? t(ev0.description_key) : (ev0?.description || '')
                          const chDesc = c.description_key ? t(c.description_key) : c.description
                          return evDesc || chDesc
                        })()}
                        {c.failed_count > 1 && ` ${t('compliance.andMore')} ${c.failed_count} ${t('compliance.assets')}`}
                      </Text>
                    }
                  />
                ))
            )}
            {frameworks.flatMap(f => f.checks).filter(c => c.status === 'fail').length === 0 && (
              <Text type="secondary" style={{ fontSize: 13 }}>
                {t('compliance.allPassed')}
              </Text>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
