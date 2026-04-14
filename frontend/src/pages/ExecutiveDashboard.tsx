import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Row, Col, Card, Typography, Tag, Space, Spin, Button,
  Progress, Statistic, message, Alert, Tooltip, Descriptions, Badge, Divider,
} from 'antd'
import {
  ReloadOutlined, ThunderboltOutlined,
  SafetyCertificateOutlined, UserOutlined, BellOutlined,
  WarningOutlined, CheckCircleOutlined, BarChartOutlined,
} from '@ant-design/icons'
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip,
  ResponsiveContainer, CartesianGrid,
} from 'recharts'
import { useTranslation } from 'react-i18next'
import api, {
  getExecutiveDashboard, getRiskHotspots, getRiskOverview,
} from '../api/client'

const { Title, Text } = Typography

interface ExecutiveMetrics {
  risk_score: number
  risk_level: string
  total_assets: number
  total_accounts: number
  high_risk_accounts: number
  dormant_accounts: number
  unlogin_admin_accounts: number
  compliance_ready: number
  trends: Record<string, number>
  ai_summary: string | null
}

const RISK_COLOR: Record<string, string> = {
  low: '#52c41a',
  medium: '#faad14',
  high: '#fa8c16',
  critical: '#ff4d4f',
}

const RISK_LABEL: Record<string, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  critical: 'Critical',
}

const CATEGORY_COLOR: Record<string, string> = {
  server: '#1677ff',
  database: '#fa8c16',
  network: '#52c41a',
  iot: '#eb2f96',
}

function RiskGauge({ score, level }: { score: number; level: string }) {
  const { t } = useTranslation()
  const color = RISK_COLOR[level] || '#999'
  const descriptions: Record<string, string> = {
    low: t('dashboard.lowRisk'),
    medium: t('dashboard.mediumRisk'),
    high: t('dashboard.highRisk'),
    critical: t('dashboard.criticalRisk'),
  }
  return (
    <Card
      style={{
        textAlign: 'center',
        borderTop: `4px solid ${color}`,
        borderRadius: 8,
      }}
      bodyStyle={{ padding: '24px 16px' }}
    >
      <div style={{
        width: 140, height: 140, borderRadius: '50%',
        background: `conic-gradient(${color} ${score * 3.6}deg, #f0f0f0 0deg)`,
        margin: '0 auto 16px',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        position: 'relative',
      }}>
        <div style={{
          width: 110, height: 110, borderRadius: '50%',
          background: '#fff', display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
        }}>
          <span style={{ fontSize: 32, fontWeight: 700, color, lineHeight: 1 }}>{score}</span>
          <span style={{ fontSize: 12, color: '#999' }}>/100</span>
        </div>
      </div>
      <Tag color={color} style={{ fontSize: 14, padding: '4px 12px', marginBottom: 8 }}>
        {RISK_LABEL[level]}
      </Tag>
      <Text type="secondary" style={{ display: 'block', fontSize: 13 }}>
        {descriptions[level]}
      </Text>
    </Card>
  )
}


interface PropagationNode {
  asset_code: string
  ip: string
  hostname?: string
  risk_score: number
  relation?: string
  is_entry_point: boolean
}

interface RiskHotspot {
  entry_asset: { asset_code: string; ip: string; hostname?: string; risk_score: number }
  root_asset: { asset_code: string; ip: string }
  max_risk_score: number
  path: string[]
  risk_description: string
  chain_length: number
  nodes: PropagationNode[]
}

export default function ExecutiveDashboard() {
  const { t } = useTranslation()
  const [metrics, setMetrics] = useState<ExecutiveMetrics | null>(null)
  const [assetsByCategory, setAssetsByCategory] = useState<{ category: string; count: number }[]>([])
  const [loading, setLoading] = useState(true)
  const [hotspots, setHotspots] = useState<RiskHotspot[]>([])
  const [highRiskCount, setHighRiskCount] = useState(0)
  const [recentAlerts, setRecentAlerts] = useState<Array<{ id: number; level: string; title: string; is_read: boolean; created_at: string }>>([])
  const [unreadCount, setUnreadCount] = useState(0)

  const fetchAll = () => {
    setLoading(true)
    Promise.all([
      getExecutiveDashboard(),
      api.get('/snapshots/dashboard'),
      getRiskHotspots({ threshold: 50 }),
      getRiskOverview({ limit: 5, min_score: 45 }),
      api.get('/alerts?limit=5'),
    ]).then(([dashRes, statsRes, hotspotsRes, overviewRes, alertsRes]) => {
      setMetrics(dashRes.data)
      setAssetsByCategory(statsRes.data.assets_by_category || [])
      setHotspots((hotspotsRes.data.hotspots || []).slice(0, 3) as RiskHotspot[])
      setHighRiskCount((overviewRes.data.results || []).length)
      setUnreadCount(alertsRes.data.unread_count || 0)
      setRecentAlerts(alertsRes.data.alerts || [])
    }).catch(() => message.error(t('msg.error')))
    .finally(() => setLoading(false))
  }

  useEffect(() => { fetchAll() }, [])

  if (loading || !metrics) {
    return <div style={{ textAlign: 'center', marginTop: 80 }}><Spin size="large" /></div>
  }

  const { risk_score, risk_level, trends, compliance_ready } = metrics
  const pieData = assetsByCategory.map(c => ({
    name: { server: 'Server', database: 'Database', network: 'Network', iot: 'IoT' }[c.category] || c.category,
    value: c.count,
    color: CATEGORY_COLOR[c.category] || '#999',
  }))

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <Title level={4} style={{ margin: 0 }}>{t('dashboard.title')}</Title>
          <Text type="secondary">{t('dashboard.poweredBy')} · {t('dashboard.realtimeRisk')}</Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchAll}>{t('btn.refresh')}</Button>
        </Space>
      </div>

      <Row gutter={[16, 16]}>
        {/* Risk Gauge */}
        <Col xs={24} sm={24} md={8} lg={6}>
          <RiskGauge score={risk_score} level={risk_level} />
        </Col>

        {/* Key Stats */}
        <Col xs={24} sm={24} md={16} lg={18}>
          <Row gutter={[12, 12]} style={{ height: '100%' }}>
            <Col span={8}>
              <Card bodyStyle={{ padding: '16px', height: '100%' }}>
                <Statistic
                  title={<Space><SafetyCertificateOutlined />{t('dashboard.adminAccounts')}</Space>}
                  value={trends.admin_accounts}
                  valueStyle={{ color: trends.admin_accounts > 3 ? '#ff4d4f' : undefined }}
                  suffix={<Text type="secondary" style={{ fontSize: 13 }}>{t('dashboard.accountsUnit', '')}</Text>}
                />
                {trends.unlogin_admin_accounts > 0 && (
                  <Tag color="red" style={{ marginTop: 4 }}>
                    ⚠ {trends.unlogin_admin_accounts} {t('dashboard.unloggedIn')}
                  </Tag>
                )}
              </Card>
            </Col>
            <Col span={8}>
              <Card bodyStyle={{ padding: '16px', height: '100%' }}>
                <Statistic
                  title={<Space><UserOutlined />{t('dashboard.totalAccounts')}</Space>}
                  value={metrics.total_accounts}
                  suffix={<Text type="secondary" style={{ fontSize: 13 }}>{t('dashboard.accountsUnit', '')}</Text>}
                />
                {trends.new_accounts_7d > 0 && (
                  <Tag color="blue" style={{ marginTop: 4 }}>
                    +{trends.new_accounts_7d} {t('dashboard.last7days')}
                  </Tag>
                )}
              </Card>
            </Col>
            <Col span={8}>
              <Card bodyStyle={{ padding: '16px', height: '100%' }}>
                <Statistic
                  title={<Space><BarChartOutlined />{t('dashboard.complianceCoverage')}</Space>}
                  value={compliance_ready}
                  precision={0}
                  suffix="%"
                  valueStyle={{ color: compliance_ready < 60 ? '#ff4d4f' : compliance_ready < 80 ? '#faad14' : '#52c41a' }}
                />
                <Progress
                  percent={compliance_ready}
                  showInfo={false}
                  strokeColor={compliance_ready < 60 ? '#ff4d4f' : compliance_ready < 80 ? '#faad14' : '#52c41a'}
                  size="small"
                  style={{ marginTop: 6 }}
                />
              </Card>
            </Col>
            <Col span={8}>
              <Card bodyStyle={{ padding: '16px', height: '100%' }}>
                <Statistic
                  title={t('dashboard.offlineAssets')}
                  value={trends.offline_assets}
                  valueStyle={{ color: trends.offline_assets > 0 ? '#fa8c16' : undefined }}
                  suffix={<Text type="secondary" style={{ fontSize: 13 }}>{t('dashboard.units', '')}</Text>}
                />
              </Card>
            </Col>
            <Col span={8}>
              <Card bodyStyle={{ padding: '16px', height: '100%' }}>
                <Statistic
                  title={t('dashboard.authFailed')}
                  value={trends.auth_failed_assets}
                  valueStyle={{ color: trends.auth_failed_assets > 0 ? '#ff4d4f' : undefined }}
                  suffix={<Text type="secondary" style={{ fontSize: 13 }}>{t('dashboard.units', '')}</Text>}
                />
              </Card>
            </Col>
            <Col span={8}>
              <Card bodyStyle={{ padding: '16px', height: '100%' }}>
                <Statistic
                  title={<Space><WarningOutlined />{t('dashboard.highRiskAssets')}</Space>}
                  value={highRiskCount}
                  suffix={<Text type="secondary" style={{ fontSize: 13 }}>{t('dashboard.assetsWithScore', '(≥45pts)')}</Text>}
                  valueStyle={{ color: highRiskCount > 0 ? '#ff4d4f' : undefined }}
                />
              </Card>
            </Col>
          </Row>
        </Col>
      </Row>

      {/* Asset Distribution + Recent Alerts */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={14}>
          <Card
            id="asset-distribution-card"
            title={t('dashboard.assetTypeDistribution')}
            extra={
              <Link to="/assets">
                <Button type="link" size="small" style={{ color: '#1677ff' }}>
                  {t('btn.viewAllAssets')} →
                </Button>
              </Link>
            }
            bodyStyle={{ padding: '12px 16px' }}
          >
            {pieData.length === 0 ? (
              <Text type="secondary">{t('msg.noData')}</Text>
            ) : (
              <Row gutter={16} align="middle">
                <Col span={10}>
                  <ResponsiveContainer width="100%" height={180}>
                    <PieChart>
                      <Pie
                        data={pieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={50}
                        outerRadius={80}
                        dataKey="value"
                        stroke="none"
                      >
                        {pieData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <RechartsTooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </Col>
                <Col span={14}>
                  <Space direction="vertical" size={10} style={{ width: '100%' }}>
                    {pieData.map(d => (
                      <Row key={d.name} align="middle" justify="space-between">
                        <Space size={8}>
                          <div style={{ width: 12, height: 12, borderRadius: 3, background: d.color }} />
                          <Text style={{ fontSize: 14 }}>{d.name}</Text>
                        </Space>
                        <Space>
                          <Tag color={d.color} style={{ minWidth: 32, textAlign: 'center' }}>{d.value}</Tag>
                        </Space>
                      </Row>
                    ))}
                    <Divider style={{ margin: '4px 0' }} />
                    <Row align="middle" justify="space-between">
                      <Text strong>{t('dashboard.totalAssets')}</Text>
                      <Text strong style={{ fontSize: 16, color: '#1677ff' }}>
                        {pieData.reduce((s, d) => s + d.value, 0)}
                      </Text>
                    </Row>
                  </Space>
                </Col>
              </Row>
            )}
          </Card>
        </Col>

        <Col xs={24} lg={10}>
          <Card
            title={
              <Space>
                <BellOutlined style={{ color: unreadCount > 0 ? '#1677ff' : undefined }} />
                {t('header.alerts')}
              </Space>
            }
            extra={
              <Link to="/alerts">
                <Button type="link" size="small" style={{ color: '#1677ff' }}>
                  {t('btn.view')} →
                </Button>
              </Link>
            }
            bodyStyle={{ padding: '12px 16px' }}
          >
            {recentAlerts.length === 0 ? (
              <Text type="secondary">{t('header.noAlerts')}</Text>
            ) : (
              <Space direction="vertical" size={6} style={{ width: '100%' }}>
                {recentAlerts.map(a => (
                  <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0', borderBottom: '1px solid #f0f0f0' }}>
                    {!a.is_read && <Badge status="processing" />}
                    <Tag color={{ critical: 'red', warning: 'orange', info: 'blue' }[a.level] || 'default'} style={{ minWidth: 48 }}>
                      {t(`alert.${a.level}`, a.level)}
                    </Tag>
                    <Text style={{ fontSize: 13, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {a.title}
                    </Text>
                    <Text type="secondary" style={{ fontSize: 11, flexShrink: 0 }}>
                      {new Date(a.created_at).toLocaleDateString()}
                    </Text>
                  </div>
                ))}
              </Space>
            )}
          </Card>
        </Col>
      </Row>

      {/* Lateral Movement Risk Hotspots */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24}>
          <Card
            title={
              <Space>
                <WarningOutlined style={{ color: hotspots.length > 0 ? '#fa8c16' : undefined }} />
                {t('dashboard.lateralRisk')}
              </Space>
            }
            extra={<Text type="secondary" style={{ fontSize: 12 }}>{t('dashboard.topNThreshold')}</Text>}
            bodyStyle={{ padding: '12px 16px' }}
          >
            {hotspots.length === 0 ? (
              <Text type="secondary" style={{ fontSize: 13 }}>
                {t('dashboard.noRiskHotspots')}
              </Text>
            ) : (
              <Row gutter={[16, 16]}>
                {hotspots.map((h, i) => {
                  const level = h.max_risk_score >= 70 ? 'critical' : 'high'
                  const relLabel: Record<string, string> = {
                    hosts_vm: t('topology.vm'),
                    hosts_container: t('topology.container'),
                    runs_service: t('topology.service'),
                    network_peer: t('topology.network'),
                    belongs_to: t('topology.belongs'),
                  }
                  // Render a compact horizontal chain: [节点] ← [节点] ← [节点]
                  const chainNodes = h.nodes || []
                  return (
                    <Col xs={24} sm={12} md={8} key={i}>
                      <div
                        style={{
                          padding: '10px 12px',
                          borderRadius: 6,
                          border: `1px solid ${RISK_COLOR[level]}40`,
                          background: `${RISK_COLOR[level]}08`,
                        }}
                      >
                        <Space style={{ marginBottom: 6 }}>
                          <Tag color={RISK_COLOR[level]} style={{ fontSize: 12, padding: '2px 8px' }}>
                            {h.max_risk_score}/100
                          </Tag>
                          <Text type="secondary" style={{ fontSize: 11 }}>{t('topology.propagationLayer')} {h.chain_length}</Text>
                        </Space>
                        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 4 }}>
                          {chainNodes.map((node, ni) => (
                            <span key={ni} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                              {ni > 0 && (
                                <Text type="secondary" style={{ fontSize: 12, flexShrink: 0 }}>
                                  ← <Tag color="purple" style={{ fontSize: 10, margin: '0 2px' }}>
                                    {relLabel[node.relation || ''] || node.relation || ''}
                                  </Tag>
                                </Text>
                              )}
                              <Tag color="blue" style={{ fontSize: 11 }}>{node.asset_code}</Tag>
                              {node.is_entry_point && (
                                <Tag color={RISK_COLOR[level]} style={{ fontSize: 10 }}>
                                  {node.risk_score}/100
                                </Tag>
                              )}
                            </span>
                          ))}
                        </div>
                        <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4 }}>
                          {h.risk_description}
                        </Text>
                      </div>
                    </Col>
                  )
                })}
              </Row>
            )}
          </Card>
        </Col>
      </Row>

    </div>
  )
}
