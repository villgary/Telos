import { useEffect, useState } from 'react'
import { Row, Col, Card, Statistic, Tag, Table, Typography } from 'antd'
import {
  PieChart, Pie, Cell, Tooltip, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer,
} from 'recharts'
import {
  CloudServerOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  WarningOutlined,
  ScanOutlined,
  UserAddOutlined,
} from '@ant-design/icons'
import api from '../api/client'
import { useTranslation } from 'react-i18next'

const { Title } = Typography

interface CategoryCount {
  category: string
  count: number
}

interface RecentJobStat {
  id: number
  asset_id: number
  status: string
  success_count: number
  failed_count: number
  started_at: string
}

interface DashboardStats {
  total_assets: number
  online_assets: number
  offline_assets: number
  auth_failed_assets: number
  total_snapshots: number
  total_jobs: number
  recent_added_accounts: number
  assets_by_category: CategoryCount[]
  recent_jobs: RecentJobStat[]
}

const STATUS_MAP = (t: (k: string) => string): Record<string, { color: string; label: string }> => ({
  success: { color: '#52c41a', label: t('status.success') },
  failed: { color: '#ff4d4f', label: t('status.failed') },
  running: { color: '#1677ff', label: t('status.running') },
  pending: { color: '#d9d9d9', label: t('status.pending') },
  partial_success: { color: '#faad14', label: t('status.partialSuccess') },
  cancelled: { color: '#8c8c8c', label: t('status.cancelled') },
})

const CATEGORY_COLOR: Record<string, string> = {
  server: '#1677ff',
  database: '#52c41a',
  network: '#722ed1',
}

const CATEGORY_LABEL = (t: (k: string) => string): Record<string, string> => ({
  server: t('category.server'),
  database: t('category.database'),
  network: t('category.networkDevice'),
})

const JOB_COLUMNS = (t: (k: string) => string, isZh: boolean): Record<string, unknown>[] => [
  { title: t('scanJob.id'), dataIndex: 'id', key: 'id', width: 60 },
  { title: t('scanJob.asset'), dataIndex: 'asset_id', key: 'asset_id', width: 70 },
  {
    title: t('scanJob.status'),
    dataIndex: 'status',
    key: 'status',
    width: 90,
    render: (v: string) => {
      const s = STATUS_MAP(t)[v] || { color: 'default', label: v }
      return <Tag color={s.color}>{s.label}</Tag>
    },
  },
  {
    title: t('scanJob.result'),
    key: 'counts',
    render: (_: unknown, r: RecentJobStat) =>
      <span>
        <span style={{ color: '#52c41a' }}>{r.success_count}</span>
        {' / '}
        <span style={{ color: '#ff4d4f' }}>{r.failed_count}</span>
      </span>,
  },
  {
    title: t('scanJob.time'),
    dataIndex: 'started_at',
    key: 'started_at',
    render: (v: string) => new Date(v).toLocaleString(isZh ? 'zh-CN' : 'en-US'),
  },
]

export default function Dashboard() {
  const { t, i18n } = useTranslation()
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/snapshots/dashboard')
      .then(r => setStats(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const isZh = i18n.language.startsWith('zh')
  const categoryData = stats?.assets_by_category.map(c => ({
    name: CATEGORY_LABEL(t)[c.category] || c.category,
    value: c.count,
    color: CATEGORY_COLOR[c.category] || '#d9d9d9',
  })) ?? []

  // Recent jobs in chronological order for bar chart
  const jobBarData = [...(stats?.recent_jobs ?? [])]
    .reverse()
    .slice(-8)
    .map(j => ({
      date: new Date(j.started_at).toLocaleDateString(isZh ? 'zh-CN' : 'en-US', { month: 'numeric', day: 'numeric' }),
      [t('status.success')]: j.success_count,
      [t('status.failed')]: j.failed_count,
    }))

  return (
    <div>
      <Title level={4}>{t('dashboard.title')}</Title>

      {/* Stats Row */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card loading={loading}>
            <Statistic title={t('dashboard.totalAssets')} value={stats?.total_assets ?? '-'} prefix={<CloudServerOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card loading={loading}>
            <Statistic
              title={t('dashboard.onlineAssets')}
              value={stats?.online_assets ?? '-'}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card loading={loading}>
            <Statistic
              title={t('dashboard.scanFailed')}
              value={stats?.auth_failed_assets ?? '-'}
              prefix={<WarningOutlined />}
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card loading={loading}>
            <Statistic
              title={t('dashboard.newPrivilegedAccounts')}
              value={stats?.recent_added_accounts ?? '-'}
              prefix={<UserAddOutlined />}
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
      </Row>

      {/* Charts Row */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card loading={loading} title={t('dashboard.assetTypeDistribution')}>
            {categoryData.length === 0 ? (
              <div style={{ textAlign: 'center', color: '#999', padding: 40 }}>{t('dashboard.noData')}</div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={categoryData}
                    cx="50%"
                    cy="50%"
                    innerRadius={45}
                    outerRadius={80}
                    dataKey="value"
                    nameKey="name"
                  >
                    {categoryData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v) => `${v ?? 0}`} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            )}
          </Card>
        </Col>
        <Col span={16}>
          <Card loading={loading} title={t('dashboard.scanTrend')}>
            {jobBarData.length === 0 ? (
              <div style={{ textAlign: 'center', color: '#999', padding: 40 }}>{t('dashboard.noData')}</div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={jobBarData} margin={{ left: -10 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey={t('status.success')} fill="#52c41a" name={t('status.success')} radius={[3, 3, 0, 0]} />
                  <Bar dataKey={t('status.failed')} fill="#ff4d4f" name={t('status.failed')} radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>
        </Col>
      </Row>

      {/* Recent Jobs */}
      <Card loading={loading} title={t('dashboard.recentScanJobs')}>
        <Table
          dataSource={stats?.recent_jobs ?? []}
          columns={JOB_COLUMNS(t, isZh)}
          rowKey="id"
          pagination={false}
          size="small"
        />
      </Card>
    </div>
  )
}
