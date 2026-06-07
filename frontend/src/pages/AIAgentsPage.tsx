/**
 * AI Agents Dashboard — peer to NHIDashboard.
 * Sprint 1: list + overview + scan trigger.
 */
import { useEffect, useState } from 'react'
import {
  Row, Col, Card, Typography, Spin, Button, Space, Tag, Table,
  Statistic, message, Empty, Tabs, Tooltip,
} from 'antd'
import {
  RobotOutlined, ScanOutlined, WarningOutlined, UserOutlined,
  ApiOutlined,
} from '@ant-design/icons'
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis,
  Tooltip as RechartsTooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import {
  listAIAgents, getAIAgentsStats, triggerAIAgentScan,
} from '../api/client'

const { Title, Text } = Typography

const LEVEL_COLORS: Record<string, string> = {
  critical: '#ff4d4f',
  high: '#fa8c16',
  medium: '#faad14',
  low: '#52c41a',
}

const FRAMEWORK_COLORS: Record<string, string> = {
  langchain: '#7c3aed',
  autogen: '#ec4899',
  crewai: '#f59e0b',
  claude_code: '#3b82f6',
  openai_assistant: '#10b981',
  llamaindex: '#8b5cf6',
  custom: '#6b7280',
  unknown: '#9ca3af',
}

export default function AIAgentsPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [agents, setAgents] = useState<any[]>([])
  const [stats, setStats] = useState<any>(null)
  const [frameworkFilter, setFrameworkFilter] = useState<string | undefined>()

  const load = async () => {
    setLoading(true)
    try {
      const params: any = {}
      if (frameworkFilter) params.framework = frameworkFilter
      const [list, s] = await Promise.all([
        listAIAgents(params),
        getAIAgentsStats(),
      ])
      setAgents(list.data.agents || [])
      setStats(s.data)
    } catch (e) {
      message.error(t('nhi.loadFailed'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [frameworkFilter])

  const onScan = async () => {
    setScanning(true)
    try {
      const r = await triggerAIAgentScan()
      message.success(t('aiAgent.scanSuccess', {
        discovered: r.data.agents_discovered,
        updated: r.data.agents_updated,
      }))
      await load()
    } catch (e) {
      message.error(t('nhi.syncFailed'))
    } finally {
      setScanning(false)
    }
  }

  if (loading && !stats) {
    return <Spin tip={t('nhi.loading')} style={{ width: '100%', marginTop: 80 }} />
  }

  const frameworkChart = stats ? Object.entries(stats.by_framework || {})
    .map(([name, value]) => ({ name, value: Number(value) })) : []
  const riskChart = stats ? Object.entries(stats.by_risk_level || {})
    .map(([name, value]) => ({ name, value: Number(value) })) : []

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
        <div style={{ flex: 1 }}>
          <Title level={4} style={{ margin: 0 }}>
            <RobotOutlined /> {t('aiAgent.title')}
          </Title>
          <Text type="secondary">{t('aiAgent.subtitle')}</Text>
        </div>
        <Space>
          <Button
            icon={<ApiOutlined />}
            onClick={() => navigate('/ai-agents/discovery')}
          >
            {t('aiAgent.discovery.title')}
          </Button>
          <Button
            type="primary"
            icon={<ScanOutlined />}
            loading={scanning}
            onClick={onScan}
          >
            {t('aiAgent.scan')}
          </Button>
        </Space>
      </div>

      {/* Stat cards */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card><Statistic title={t('aiAgent.totalAgents')} value={stats?.total ?? 0} prefix={<ApiOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title={t('aiAgent.activeAgents')} value={stats?.active ?? 0} prefix={<RobotOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title={t('aiAgent.criticalRisk')} value={stats?.critical_risk ?? 0} valueStyle={{ color: '#ff4d4f' }} prefix={<WarningOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title={t('aiAgent.noOwner')} value={stats?.no_owner ?? 0} valueStyle={{ color: '#fa8c16' }} prefix={<UserOutlined />} /></Card>
        </Col>
      </Row>

      <Tabs
        items={[
          {
            key: 'overview',
            label: t('aiAgent.tab.overview'),
            children: (
              <Row gutter={16}>
                <Col span={12}>
                  <Card title="Framework">
                    {frameworkChart.length === 0 ? <Empty /> : (
                      <ResponsiveContainer width="100%" height={280}>
                        <PieChart>
                          <Pie data={frameworkChart} dataKey="value" nameKey="name"
                               outerRadius={100} label>
                            {frameworkChart.map((e, i) => (
                              <Cell key={i} fill={FRAMEWORK_COLORS[e.name] || '#9ca3af'} />
                            ))}
                          </Pie>
                          <RechartsTooltip />
                        </PieChart>
                      </ResponsiveContainer>
                    )}
                  </Card>
                </Col>
                <Col span={12}>
                  <Card title="Risk Level">
                    {riskChart.length === 0 ? <Empty /> : (
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={riskChart}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="name" />
                          <YAxis allowDecimals={false} />
                          <RechartsTooltip />
                          <Bar dataKey="value">
                            {riskChart.map((e, i) => (
                              <Cell key={i} fill={LEVEL_COLORS[e.name] || '#9ca3af'} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    )}
                  </Card>
                </Col>
              </Row>
            ),
          },
          {
            key: 'list',
            label: t('aiAgent.tab.list'),
            children: (
              <Table
                rowKey="id"
                dataSource={agents}
                loading={loading}
                pagination={{ pageSize: 20 }}
                onRow={(r) => ({ onClick: () => navigate(`/ai-agents/${r.id}`) })}
                columns={[
                  { title: 'Agent', dataIndex: 'agent_name',
                    render: (n, r) => (
                      <Space>
                        <Text strong>{n}</Text>
                        {r.risk_level === 'critical' && <Tag color="red">!</Tag>}
                      </Space>
                    )},
                  { title: 'Framework', dataIndex: 'framework',
                    render: (fw: string) => <Tag color={FRAMEWORK_COLORS[fw]}>{t(`aiAgent.framework.${fw}`, fw)}</Tag> },
                  { title: 'Model', dataIndex: 'model', render: (m) => m || '—' },
                  { title: 'Owner', dataIndex: 'owner_team',
                    render: (team, r) => team || r.owner_user || <Text type="warning">No owner</Text> },
                  { title: 'Risk', dataIndex: 'risk_level',
                    render: (lvl) => <Tag color={LEVEL_COLORS[lvl]}>{lvl.toUpperCase()}</Tag> },
                  { title: 'Status', dataIndex: 'status',
                    render: (s) => <Tag>{s}</Tag> },
                ]}
              />
            ),
          },
        ]}
      />
    </div>
  )
}
