import { Routes, Route } from 'react-router-dom'
import { lazy, Suspense, useState, useEffect } from 'react'
import { Spin } from 'antd'
import { AppLayout } from './components/AppLayout'

// Lazy load all page components
const AIAgentsPage = lazy(() => import('./pages/AIAgentsPage'))
const AIAgentDetailPage = lazy(() => import('./pages/AIAgentDetailPage'))
const CloudConnectionsPage = lazy(() => import('./pages/CloudConnectionsPage'))
const Login = lazy(() => import('./pages/Login'))
const Dashboard = lazy(() => import('./pages/ExecutiveDashboard'))
const Assets = lazy(() => import('./pages/Assets'))
const AssetCategories = lazy(() => import('./pages/AssetCategories'))
const AssetGroups = lazy(() => import('./pages/AssetGroups'))
const SubTypes = lazy(() => import('./pages/SubTypes'))
const Credentials = lazy(() => import('./pages/Credentials'))
const Users = lazy(() => import('./pages/Users'))
const ScanJobs = lazy(() => import('./pages/ScanJobs'))
const DiffView = lazy(() => import('./pages/DiffView'))
const SchedulePage = lazy(() => import('./pages/SchedulePage'))
const AlertPage = lazy(() => import('./pages/AlertPage'))
const AssetTopology = lazy(() => import('./pages/AssetTopology'))
const Compliance = lazy(() => import('./pages/Compliance'))
const IdentityFusion = lazy(() => import('./pages/IdentityFusion'))
const AccountLifecycle = lazy(() => import('./pages/AccountLifecycle'))
const PAMIntegration = lazy(() => import('./pages/PAMIntegration'))
const ReviewReminders = lazy(() => import('./pages/ReviewReminders'))
const AISecurityAnalysis = lazy(() => import('./pages/AISecurityAnalysis'))
const AccountRiskList = lazy(() => import('./pages/AccountRiskList'))
const BehaviorAnalytics = lazy(() => import('./pages/BehaviorAnalytics'))
const PolicyManagement = lazy(() => import('./pages/PolicyManagement'))
const KnowledgeBase = lazy(() => import('./pages/KnowledgeBase'))
const KBAdmin = lazy(() => import('./pages/KBAdmin'))
const IdentityThreatAnalysis = lazy(() => import('./pages/IdentityThreatAnalysis'))
const OperatorDashboard = lazy(() => import('./pages/OperatorDashboard'))
const SystemSettings = lazy(() => import('./pages/SystemSettings'))
const Playbooks = lazy(() => import('./pages/Playbooks'))
const NHIDashboard = lazy(() => import('./pages/NHIDashboard'))
const ATTCKCoverage = lazy(() => import('./pages/ATTCKCoverage'))

function LoadingFallback() {
  return <div style={{ display: 'flex', justifyContent: 'center', padding: 50 }}><Spin /></div>
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
    <Suspense fallback={<LoadingFallback />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<AppLayout viewMode={viewMode} setViewMode={setViewMode} />}>
          <Route index element={isOperator ? <OperatorDashboard /> : <Dashboard />} />
          <Route path="/assets" element={<Assets />} />
          <Route path="/asset-categories" element={<AssetCategories />} />
          <Route path="/asset-topology" element={<AssetTopology />} />
          <Route path="/asset-groups" element={<AssetGroups />} />
          <Route path="/sub-types" element={<SubTypes />} />
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
          <Route path="/ai-agents" element={<AIAgentsPage />} />
          <Route path="/ai-agents/connections" element={<CloudConnectionsPage />} />
          <Route path="/ai-agents/:id" element={<AIAgentDetailPage />} />
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
    </Suspense>
  )
}
