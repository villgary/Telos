import { Drawer, Typography, List, Divider, Tag } from 'antd'
import { useTranslation } from 'react-i18next'
import { useLocation } from 'react-router-dom'
import { ReactNode } from 'react'

const { Title, Text, Paragraph } = Typography

interface HelpDrawerProps {
  open: boolean
  onClose: () => void
}

interface HelpContent {
  titleKey: string
  paragraphs: string[]
  lists?: { key: string; items: { label?: string; text: string }[] }[]
}

const HELP_CONTENT: Record<string, HelpContent> = {
  '/': {
    titleKey: 'help.dashboard.title',
    paragraphs: ['help.dashboard.p1', 'help.dashboard.p2'],
    lists: [
      {
        key: 'help.dashboard.actions',
        items: [
          { text: 'help.dashboard.action1' },
          { text: 'help.dashboard.action2' },
          { text: 'help.dashboard.action3' },
        ],
      },
    ],
  },
  '/assets': {
    titleKey: 'help.assets.title',
    paragraphs: ['help.assets.p1'],
    lists: [
      {
        key: 'help.assets.steps',
        items: [
          { text: 'help.assets.step1' },
          { text: 'help.assets.step2' },
          { text: 'help.assets.step3' },
          { text: 'help.assets.step4' },
        ],
      },
      {
        key: 'help.assets.categories',
        items: [
          { text: 'help.assets.category1' },
          { text: 'help.assets.category2' },
        ],
      },
    ],
  },
  '/sub-types': {
    titleKey: 'help.subtypes.title',
    paragraphs: ['help.subtypes.p1'],
    lists: [
      {
        key: 'help.subtypes.kinds',
        items: [
          { label: 'help.subtypes.networkVendor', text: 'help.subtypes.networkVendorDesc' },
          { label: 'help.subtypes.iotDeviceType', text: 'help.subtypes.iotDeviceTypeDesc' },
          { label: 'help.subtypes.dbType', text: 'help.subtypes.dbTypeDesc' },
          { label: 'help.subtypes.osType', text: 'help.subtypes.osTypeDesc' },
          { label: 'help.subtypes.cloudProvider', text: 'help.subtypes.cloudProviderDesc' },
        ],
      },
    ],
  },
  '/scans': {
    titleKey: 'help.scans.title',
    paragraphs: ['help.scans.p1'],
    lists: [
      {
        key: 'help.scans.types',
        items: [
          { label: 'help.scans.fullScan', text: 'help.scans.fullScanDesc' },
          { label: 'help.scans.incrementalScan', text: 'help.scans.incrementalScanDesc' },
        ],
      },
    ],
  },
  '/schedules': {
    titleKey: 'help.schedules.title',
    paragraphs: ['help.schedules.p1'],
    lists: [
      {
        key: 'help.schedules.cron',
        items: [
          { label: 'help.schedules.min', text: 'help.schedules.minDesc' },
          { label: 'help.schedules.hour', text: 'help.schedules.hourDesc' },
          { label: 'help.schedules.day', text: 'help.schedules.dayDesc' },
          { label: 'help.schedules.month', text: 'help.schedules.monthDesc' },
          { label: 'help.schedules.weekday', text: 'help.schedules.weekdayDesc' },
        ],
      },
    ],
  },
  '/diff': {
    titleKey: 'help.diff.title',
    paragraphs: ['help.diff.p1'],
    lists: [
      {
        key: 'help.diff.types',
        items: [
          { label: 'help.diff.added', text: 'help.diff.addedDesc' },
          { label: 'help.diff.removed', text: 'help.diff.removedDesc' },
          { label: 'help.diff.escalated', text: 'help.diff.escalatedDesc' },
          { label: 'help.diff.deactivated', text: 'help.diff.deactivatedDesc' },
        ],
      },
    ],
  },
  '/alerts': {
    titleKey: 'help.alerts.title',
    paragraphs: ['help.alerts.p1'],
    lists: [
      {
        key: 'help.alerts.levels',
        items: [
          { label: 'help.alerts.critical', text: 'help.alerts.criticalDesc' },
          { label: 'help.alerts.warning', text: 'help.alerts.warningDesc' },
          { label: 'help.alerts.info', text: 'help.alerts.infoDesc' },
        ],
      },
    ],
  },
  '/compliance': {
    titleKey: 'help.compliance.title',
    paragraphs: ['help.compliance.p1'],
    lists: [
      {
        key: 'help.compliance.frameworks',
        items: [
          { label: 'help.compliance.soc2', text: 'help.compliance.soc2Desc' },
          { label: 'help.compliance.iso27001', text: 'help.compliance.iso27001Desc' },
          { label: 'help.compliance.dengbao2', text: 'help.compliance.dengbao2Desc' },
        ],
      },
    ],
  },
  '/policies': {
    titleKey: 'help.policies.title',
    paragraphs: ['help.policies.p1'],
    lists: [
      {
        key: 'help.policies.categories',
        items: [
          { label: 'help.policies.privilege', text: 'help.policies.privilegeDesc' },
          { label: 'help.policies.lifecycle', text: 'help.policies.lifecycleDesc' },
          { label: 'help.policies.compliance', text: 'help.policies.complianceDesc' },
          { label: 'help.policies.custom', text: 'help.policies.customDesc' },
        ],
      },
    ],
  },
  '/identities': {
    titleKey: 'help.identities.title',
    paragraphs: ['help.identities.p1'],
    lists: [
      {
        key: 'help.identities.methods',
        items: [
          { label: 'help.identities.uidMatch', text: 'help.identities.uidMatchDesc' },
          { label: 'help.identities.usernameMatch', text: 'help.identities.usernameMatchDesc' },
          { label: 'help.identities.emailMatch', text: 'help.identities.emailMatchDesc' },
          { label: 'help.identities.manual', text: 'help.identities.manualDesc' },
        ],
      },
    ],
  },
  '/lifecycle': {
    titleKey: 'help.lifecycle.title',
    paragraphs: ['help.lifecycle.p1'],
    lists: [
      {
        key: 'help.lifecycle.states',
        items: [
          { label: 'help.lifecycle.active', text: 'help.lifecycle.activeDesc' },
          { label: 'help.lifecycle.dormant', text: 'help.lifecycle.dormantDesc' },
          { label: 'help.lifecycle.departed', text: 'help.lifecycle.departedDesc' },
        ],
      },
    ],
  },
  '/nhi': {
    titleKey: 'help.nhi.title',
    paragraphs: ['help.nhi.p1'],
    lists: [
      {
        key: 'help.nhi.types',
        items: [
          { label: 'help.nhi.serviceAccount', text: 'help.nhi.serviceAccountDesc' },
          { label: 'help.nhi.cloudIdentity', text: 'help.nhi.cloudIdentityDesc' },
          { label: 'help.nhi.apiKey', text: 'help.nhi.apiKeyDesc' },
          { label: 'help.nhi.cicd', text: 'help.nhi.cicdDesc' },
        ],
      },
    ],
  },
  '/ueba': {
    titleKey: 'help.ueba.title',
    paragraphs: ['help.ueba.p1'],
    lists: [
      {
        key: 'help.ueba.detection',
        items: [
          { label: 'help.ueba.critical', text: 'help.ueba.criticalDesc' },
          { label: 'help.ueba.high', text: 'help.ueba.highDesc' },
          { label: 'help.ueba.medium', text: 'help.ueba.mediumDesc' },
        ],
      },
    ],
  },
  '/credentials': {
    titleKey: 'help.credentials.title',
    paragraphs: ['help.credentials.p1'],
    lists: [
      {
        key: 'help.credentials.methods',
        items: [
          { label: 'help.credentials.password', text: 'help.credentials.passwordDesc' },
          { label: 'help.credentials.sshKey', text: 'help.credentials.sshKeyDesc' },
        ],
      },
    ],
  },
  '/users': {
    titleKey: 'help.users.title',
    paragraphs: ['help.users.p1'],
    lists: [
      {
        key: 'help.users.roles',
        items: [
          { label: 'help.users.admin', text: 'help.users.adminDesc' },
          { label: 'help.users.operator', text: 'help.users.operatorDesc' },
          { label: 'help.users.viewer', text: 'help.users.viewerDesc' },
        ],
      },
    ],
  },
  '/system-settings': {
    titleKey: 'help.settings.title',
    paragraphs: ['help.settings.p1'],
    lists: [
      { key: 'help.settings.ai', items: [{ text: 'help.settings.aiDesc' }] },
      { key: 'help.settings.notifications', items: [{ text: 'help.settings.notificationsDesc' }] },
    ],
  },
  '/knowledge-base': {
    titleKey: 'help.kb.title',
    paragraphs: ['help.kb.p1'],
    lists: [
      {
        key: 'help.kb.types',
        items: [
          { label: 'help.kb.mitre', text: 'help.kb.mitreDesc' },
          { label: 'help.kb.cve', text: 'help.kb.cveDesc' },
          { label: 'help.kb.practices', text: 'help.kb.practicesDesc' },
        ],
      },
    ],
  },
  '/playbooks': {
    titleKey: 'help.playbooks.title',
    paragraphs: ['help.playbooks.p1'],
    lists: [
      {
        key: 'help.playbooks.actions',
        items: [
          { label: 'help.playbooks.disable', text: 'help.playbooks.disableDesc' },
          { label: 'help.playbooks.revoke', text: 'help.playbooks.revokeDesc' },
          { label: 'help.playbooks.notify', text: 'help.playbooks.notifyDesc' },
          { label: 'help.playbooks.flag', text: 'help.playbooks.flagDesc' },
        ],
      },
    ],
  },
  '/account-risk': {
    titleKey: 'help.accountRisk.title',
    paragraphs: ['help.accountRisk.p1'],
    lists: [
      {
        key: 'help.accountRisk.factors',
        items: [
          { label: 'help.accountRisk.privileged', text: 'help.accountRisk.privilegedDesc' },
          { label: 'help.accountRisk.dormant', text: 'help.accountRisk.dormantDesc' },
          { label: 'help.accountRisk.crossSystem', text: 'help.accountRisk.crossSystemDesc' },
          { label: 'help.accountRisk.neverLogin', text: 'help.accountRisk.neverLoginDesc' },
          { label: 'help.accountRisk.dangerous', text: 'help.accountRisk.dangerousDesc' },
        ],
      },
    ],
  },
}

function renderContent(content: HelpContent, t: (key: string) => string): ReactNode {
  return (
    <>
      {content.paragraphs.map((key, i) => (
        <Paragraph key={i}>{t(key)}</Paragraph>
      ))}
      {content.lists?.map((list) => (
        <List key={list.key} size="small" bordered>
          {list.items.map((item, i) => (
            <List.Item key={i}>
              {item.label && <Tag>{t(item.label)}</Tag>}
              <Text>{t(item.text)}</Text>
            </List.Item>
          ))}
        </List>
      ))}
    </>
  )
}

export function HelpDrawer({ open, onClose }: HelpDrawerProps) {
  const { t } = useTranslation()
  const location = useLocation()

  const path = Object.keys(HELP_CONTENT).find(p =>
    p !== '/' && location.pathname.startsWith(p)
  ) || (HELP_CONTENT[location.pathname] ? location.pathname : '/')

  const content = HELP_CONTENT[path] || HELP_CONTENT['/']

  return (
    <Drawer
      title={`${t('help.title')} — ${t(content.titleKey)}`}
      placement="right"
      width={480}
      onClose={onClose}
      open={open}
    >
      {renderContent(content, t)}
    </Drawer>
  )
}

export default HelpDrawer
