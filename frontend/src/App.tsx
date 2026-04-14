import { Routes, Route, Outlet } from 'react-router-dom'
import { Layout, Menu, Badge, Dropdown, List, Tag, Typography, Button, Space, Segmented } from 'antd'
import {
  DashboardOutlined,
  CloudServerOutlined,
  ScanOutlined,
  LockOutlined,
  BellOutlined,
  UserOutlined,
  SafetyCertificateOutlined,
  SafetyOutlined,
  ToolOutlined,
  ThunderboltOutlined,
  BookOutlined,
  TeamOutlined,
  AlertOutlined,
  LineChartOutlined,
  ClockCircleOutlined,
  KeyOutlined,
  CheckCircleOutlined,
  SettingOutlined,
  AppstoreOutlined,
  ClusterOutlined,
  NodeIndexOutlined,
  DiffOutlined,
  DatabaseOutlined,
  FolderOutlined,
  ApiOutlined,
  AimOutlined,
} from '@ant-design/icons'
import { Link, useNavigate } from 'react-router-dom'
import { useEffect, useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import Login from './pages/Login'
import Dashboard from './pages/ExecutiveDashboard'
import Assets from './pages/Assets'
import AssetCategories from './pages/AssetCategories'
import AssetGroups from './pages/AssetGroups'
import Credentials from './pages/Credentials'
import Users from './pages/Users'
import ScanJobs from './pages/ScanJobs'
import DiffView from './pages/DiffView'
import SchedulePage from './pages/SchedulePage'
import AlertPage from './pages/AlertPage'
import AssetTopology from './pages/AssetTopology'
import Compliance from './pages/Compliance'
import IdentityFusion from './pages/IdentityFusion'
import AccountLifecycle from './pages/AccountLifecycle'
import PAMIntegration from './pages/PAMIntegration'
import ReviewReminders from './pages/ReviewReminders'
import AISecurityAnalysis from './pages/AISecurityAnalysis'
import AccountRiskList from './pages/AccountRiskList'
import BehaviorAnalytics from './pages/BehaviorAnalytics'
import PolicyManagement from './pages/PolicyManagement'
import KnowledgeBase from './pages/KnowledgeBase'
import KBAdmin from './pages/KBAdmin'
import IdentityThreatAnalysis from './pages/IdentityThreatAnalysis'
import OperatorDashboard from './pages/OperatorDashboard'
import SystemSettings from './pages/SystemSettings'
import Playbooks from './pages/Playbooks'
import NHIDashboard from './pages/NHIDashboard'
import ATTCKCoverage from './pages/ATTCKCoverage'
import LanguageSwitcher from './LanguageSwitcher'
import api from './api/client'

const { Header, Sider, Content } = Layout
const { Text } = Typography

interface Alert {
  id: number
  level: string
  title: string
  asset_id: number
  is_read: boolean
  created_at: string
}

interface AppLayoutProps {
  viewMode: 'operator' | 'admin'
  setViewMode: (v: 'operator' | 'admin') => void
}

function AppLayout({ viewMode, setViewMode }: AppLayoutProps) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const token = localStorage.getItem('token')

  // Force re-render when language changes (e.g., switched on login page)
  const [, forceRender] = useState(0)
  useEffect(() => {
    const sync = () => forceRender(n => n + 1)
    i18n.on('languageChanged', sync)
    return () => { i18n.off('languageChanged', sync) }
  }, [i18n])

  const isOperator = viewMode === 'operator'

  const LEVEL_TAG = {
    critical: { color: 'red', label: t('alert.critical') },
    warning: { color: 'orange', label: t('alert.warning') },
    info: { color: 'blue', label: t('alert.info') },
  }

  const [unreadCount, setUnreadCount] = useState(0)
  const [recentAlerts, setRecentAlerts] = useState<Alert[]>([])

  useEffect(() => {
    if (!token) navigate('/login', { replace: true })
  }, [token, navigate])

  const fetchUnreadCount = useCallback(async () => {
    if (!token) return
    try {
      const r = await api.get('/alerts?limit=5')
      setUnreadCount(r.data.unread_count)
      setRecentAlerts(r.data.alerts.slice(0, 5))
    } catch { /* ignore */ }
  }, [token])

  useEffect(() => {
    fetchUnreadCount()
    const interval = setInterval(fetchUnreadCount, 30000)
    return () => clearInterval(interval)
  }, [fetchUnreadCount])

  const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    navigate('/login')
  }

  const lang = i18n.language === 'en-US' ? 'en' : 'zh-CN'

  const bellContent = (
    <div style={{ width: 360, background: '#fff', borderRadius: 8, boxShadow: '0 4px 16px rgba(0,0,0,0.12)' }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text strong>{t('header.alerts')}</Text>
        {unreadCount > 0 && (
          <Button size="small" type="link" onClick={() => navigate('/alerts')}>
            {t('header.viewAll')}
          </Button>
        )}
      </div>
      {recentAlerts.length === 0 ? (
        <div style={{ padding: 24, textAlign: 'center', color: '#999' }}>
          <BellOutlined style={{ fontSize: 24, marginBottom: 8 }} />
          <div>{t('header.noAlerts')}</div>
        </div>
      ) : (
        <List
          size="small"
          dataSource={recentAlerts}
          renderItem={(item: Alert) => {
            const cfg = LEVEL_TAG[item.level as keyof typeof LEVEL_TAG] || LEVEL_TAG.info
            return (
              <List.Item
                style={{ padding: '10px 16px', cursor: 'pointer', background: item.is_read ? '#fff' : '#f0f7ff' }}
                onClick={() => navigate('/alerts')}
              >
                <div style={{ width: '100%' }}>
                  <Space style={{ marginBottom: 4 }}>
                    {!item.is_read && <Badge status="processing" />}
                    <Tag color={cfg.color}>{cfg.label}</Tag>
                    <Text type="secondary" style={{ fontSize: 12 }}>{t('table.asset')} #{item.asset_id}</Text>
                  </Space>
                  <div style={{ fontSize: 13 }}>{item.title}</div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {new Date(item.created_at).toLocaleString(lang)}
                  </Text>
                </div>
              </List.Item>
            )
          }}
        />
      )}
    </div>
  )

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ background: '#001529', padding: '0 24px', display: 'flex', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', marginRight: 32 }}>
          <img src="/logo.svg" alt="Logo" style={{ width: 32, height: 32, marginRight: 10 }} />
          <span style={{ color: '#fff', fontSize: 18, fontWeight: 'bold' }}>{t('app.name')}</span>
        </div>
        <div style={{ color: '#aaa', fontSize: 13, flex: 1 }}>{t('header.system')}</div>

        {/* View mode switcher */}
        <div style={{ marginRight: 16 }}>
          <Segmented
            value={viewMode}
            onChange={v => setViewMode(v as 'operator' | 'admin')}
            options={[
              { label: <Space size={4}><ThunderboltOutlined />{t('operator.label', '运营')}</Space>, value: 'operator' },
              { label: <Space size={4}><ToolOutlined />{t('admin.label', '管理')}</Space>, value: 'admin' },
            ]}
            size="small"
          />
        </div>

        <Dropdown dropdownRender={() => bellContent} trigger={['click']} placement="bottomRight">
          <div style={{ color: '#fff', cursor: 'pointer', marginRight: 16, fontSize: 18 }}>
            <Badge count={unreadCount} size="small" offset={[4, -4]}>
              <BellOutlined />
            </Badge>
          </div>
        </Dropdown>

        <div style={{ marginRight: 16 }}>
          <LanguageSwitcher />
        </div>

        <div style={{ color: '#fff', cursor: 'pointer' }} onClick={handleLogout}>
          {t('header.logout')}
        </div>
      </Header>
      <Layout>
        <Sider width={220} style={{ background: '#fff' }}>
          <Menu
            mode="inline"
            defaultSelectedKeys={['dashboard']}
            style={{ height: '100%', borderRight: 0 }}
          >
            <Menu.Item key="dashboard" icon={<DashboardOutlined />}>
              <Link to="/">{t('nav.dashboard')}</Link>
            </Menu.Item>

            <Menu.Item key="ai" icon={<SafetyCertificateOutlined />}>
              <Link to="/ai">{t('nav.aiAnalysis')}</Link>
            </Menu.Item>

            <Menu.Item key="identity-threat" icon={<SafetyOutlined />}>
              <Link to="/identity-threat">{t('threat.title')}</Link>
            </Menu.Item>
            <Menu.Item key="attck-coverage" icon={<AimOutlined />}>
              <Link to="/attck-coverage">{t('attck.title') || 'ATT&CK Coverage'}</Link>
            </Menu.Item>

            <Menu.SubMenu key="asset-group" icon={<CloudServerOutlined />} title={t('nav.assetManagement')}>
              <Menu.Item key="assets" icon={<AppstoreOutlined />}><Link to="/assets">{t('nav.assetList')}</Link></Menu.Item>
              <Menu.Item key="asset-categories" icon={<FolderOutlined />}><Link to="/asset-categories">{t('nav.assetCategories')}</Link></Menu.Item>
              <Menu.Item key="asset-groups" icon={<ClusterOutlined />}><Link to="/asset-groups">{t('nav.assetGroups')}</Link></Menu.Item>
              <Menu.Item key="asset-topology" icon={<NodeIndexOutlined />}><Link to="/asset-topology">{t('nav.assetTopology')}</Link></Menu.Item>
            </Menu.SubMenu>

            <Menu.SubMenu key="scan-group" icon={<ScanOutlined />} title={t('nav.scanJobs')}>
              <Menu.Item key="scans" icon={<ScanOutlined />}><Link to="/scans">{t('nav.scanTasks')}</Link></Menu.Item>
              <Menu.Item key="schedules" icon={<ClockCircleOutlined />}><Link to="/schedules">{t('nav.scheduledScans')}</Link></Menu.Item>
              <Menu.Item key="diff" icon={<DiffOutlined />}><Link to="/diff">{t('nav.diffView')}</Link></Menu.Item>
            </Menu.SubMenu>

            <Menu.SubMenu key="security-group" icon={<SafetyCertificateOutlined />} title={t('nav.security')}>
              <Menu.Item key="alerts" icon={<BellOutlined />}><Link to="/alerts">{t('nav.alerts')}</Link></Menu.Item>
              <Menu.Item key="compliance" icon={<SafetyOutlined />}><Link to="/compliance">{t('nav.compliance')}</Link></Menu.Item>
              <Menu.Item key="identities" icon={<TeamOutlined />}><Link to="/identities">{t('nav.identities')}</Link></Menu.Item>
              <Menu.Item key="account-risk" icon={<AlertOutlined />}><Link to="/account-risk">{t('nav.accountRiskList')}</Link></Menu.Item>
              <Menu.Item key="ueba" icon={<LineChartOutlined />}><Link to="/ueba">{t('nav.ueba')}</Link></Menu.Item>
              <Menu.Item key="lifecycle" icon={<ClockCircleOutlined />}><Link to="/lifecycle">{t('nav.lifecycle')}</Link></Menu.Item>
              <Menu.Item key="pam" icon={<KeyOutlined />}><Link to="/pam">{t('nav.pam')}</Link></Menu.Item>
              <Menu.Item key="nhi" icon={<ApiOutlined />}><Link to="/nhi">{t('nav.nhi')}</Link></Menu.Item>
              <Menu.Item key="review" icon={<CheckCircleOutlined />}><Link to="/review">{t('nav.review')}</Link></Menu.Item>
              <Menu.Item key="policies" icon={<SettingOutlined />}><Link to="/policies">{t('nav.policyManagement')}</Link></Menu.Item>
              <Menu.SubMenu key="kb-group" icon={<BookOutlined />} title={t('nav.knowledgeBase')}>
                <Menu.Item key="knowledge-base"><Link to="/knowledge-base">{t('kb.browse')}</Link></Menu.Item>
                <Menu.Item key="kb-admin"><Link to="/kb-admin">{t('kb.admin')}</Link></Menu.Item>
              </Menu.SubMenu>
            </Menu.SubMenu>

            <Menu.SubMenu key="system-group" icon={<ToolOutlined />} title={t('nav.system')}>
              <Menu.Item key="credentials" icon={<LockOutlined />}><Link to="/credentials">{t('nav.credentials')}</Link></Menu.Item>
              <Menu.Item key="users" icon={<UserOutlined />}><Link to="/users">{t('nav.users')}</Link></Menu.Item>
              <Menu.Item key="system-settings" icon={<SettingOutlined />}><Link to="/system-settings">{t('nav.systemSettings')}</Link></Menu.Item>
              <Menu.Item key="playbooks" icon={<ToolOutlined />}><Link to="/playbooks">{t('nav.playbooks')}</Link></Menu.Item>
            </Menu.SubMenu>
          </Menu>
        </Sider>
        <Layout style={{ padding: '0 24px 24px' }}>
          <Content style={{ margin: '16px 0', minHeight: 280 }}>
            <Outlet />
          </Content>
        </Layout>
      </Layout>
    </Layout>
  )
}

export default function App() {
  const [viewMode, setViewMode] = useState<'operator' | 'admin'>(
    (localStorage.getItem('viewMode') as 'operator' | 'admin') || 'admin'
  )
  useEffect(() => {
    localStorage.setItem('viewMode', viewMode)
  }, [viewMode])
  const isOperator = viewMode === 'operator'

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<AppLayout viewMode={viewMode} setViewMode={setViewMode} />}>
        <Route index element={isOperator ? <OperatorDashboard /> : <Dashboard />} />
        <Route path="/assets" element={<Assets />} />
        <Route path="/asset-categories" element={<AssetCategories />} />
        <Route path="/asset-topology" element={<AssetTopology />} />
        <Route path="/asset-groups" element={<AssetGroups />} />
        <Route path="/scans" element={<ScanJobs />} />
        <Route path="/schedules" element={<SchedulePage />} />
        <Route path="/diff" element={<DiffView />} />
        <Route path="/alerts" element={<AlertPage />} />
        <Route path="/credentials" element={<Credentials />} />
        <Route path="/compliance" element={<Compliance />} />
        <Route path="/identities" element={<IdentityFusion />} />
        <Route path="/lifecycle" element={<AccountLifecycle />} />
        <Route path="/pam" element={<PAMIntegration />} />
        <Route path="/review" element={<ReviewReminders />} />
        <Route path="/users" element={<Users />} />
        <Route path="/ai" element={<AISecurityAnalysis />} />
        <Route path="/identity-threat" element={<IdentityThreatAnalysis />} />
        <Route path="/nhi" element={<NHIDashboard />} />
        <Route path="/account-risk" element={<AccountRiskList />} />
        <Route path="/ueba" element={<BehaviorAnalytics />} />
        <Route path="/policies" element={<PolicyManagement />} />
        <Route path="/knowledge-base" element={<KnowledgeBase />} />
        <Route path="/kb-admin" element={<KBAdmin />} />
        <Route path="/system-settings" element={<SystemSettings />} />
        <Route path="/playbooks" element={<Playbooks />} />
        <Route path="/attck-coverage" element={<ATTCKCoverage />} />
      </Route>
    </Routes>
  )
}
