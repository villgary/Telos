import { useState, useEffect } from 'react'
import {
  Space, Tag, Button, Table, Badge, Drawer, Typography,
} from 'antd'
const { Text } = Typography
import { useTranslation } from 'react-i18next'
import { getAttackPaths, AttackPathsResponse, AttackPathEntry } from '../api/client'

// ─── System account detection ───────────────────────────────────────────────────
const DB_SYSTEM_PATTERNS: RegExp[] = [
  /^root$/i, /^daemon$/i, /^bin$/i, /^sys$/i, /^sync$/i,
  /^games$/i, /^man$/i, /^lp$/i, /^mail$/i, /^news$/i,
  /^uucp$/i, /^proxy$/i, /^www-data$/i, /^nobody$/i,
  /^sshd$/i, /^systemd-/i, /^operator$/i, /^backup$/i,
  /^app$/i, /^guest$/i, /^default$/i, /^aws_.*$/i,
  /^azure_.*$/i, /^docker-/i, /^k8s_.*$/i, /^eks_.*$/i,
  /^nfsnobody$/i, /^statd$/i, /^rpc$/i, /^rpcuser$/i,
  /^avahi$/i, /^colord$/i, /^geoclue$/i, /^rtkit$/i,
  /^pulse$/i, /^gnome-.*$/i, /^lightdm$/i, /^gdm$/i,
  /^cupsys$/i, /^hplip$/i, /^scard$/i, /^uuidd$/i,
  /^dnsmasq$/i, /^ntp$/i, /^chrony$/i, /^polkitd$/i,
  /^usbmux$/i, /^_apt$/i, /^landscape$/i, /^tss$/i,
  /^gnats$/i, /^irmgr$/i, /^ids$/i, /^omsagent$/i,
  /^syslog$/i, /^adm$/i,
]
const HUMAN_SERVICE_KEYWORDS = [
  'admin', 'backup', 'test', 'monitor', 'deploy', 'automation',
  'jenkins', 'nginx', 'apache', 'tomcat', 'docker', 'redis',
  'mysql', 'postgres', 'oracle', 'mongodb', 'zabbix', 'prometheus',
  'grafana', 'elk', 'kibana', 'gitlab', 'jira',
  'service', 'svc', 'daemon', 'app', 'application',
]

function isHumanAccount(username: string): boolean {
  const lower = username.toLowerCase()
  if (DB_SYSTEM_PATTERNS.some(p => p.test(lower))) return false
  if (HUMAN_SERVICE_KEYWORDS.some(k => lower.includes(k))) return false
  if (/^\d+$/.test(username)) return false
  return true
}

function filterHumanTargets(targets: AttackPathEntry['targets']) {
  const human: typeof targets = []
  const system: typeof targets = []
  for (const t of targets) {
    if (isHumanAccount(t.username)) { human.push(t) } else { system.push(t) }
  }
  return { human, system }
}

// ─── Component ───────────────────────────────────────────────────────────────────
interface AttackPathsTabProps { analysisId: number }

export default function AttackPathsTab({ analysisId }: AttackPathsTabProps) {
  const { t } = useTranslation()
  const [data, setData] = useState<AttackPathsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [maxHops, setMaxHops] = useState(3)
  const [expandedRow, setExpandedRow] = useState<number | null>(null)
  const [drawerEntry, setDrawerEntry] = useState<AttackPathEntry | null>(null)

  useEffect(() => {
    setLoading(true)
    getAttackPaths(analysisId, { max_hops: maxHops })
      .then(r => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [analysisId, maxHops])

  if (!data) return <Text type="secondary">{t('threat.noAttackPaths')}</Text>

  const EDGE_TYPE_LABELS: Record<string, string> = {
    ssh_key_reuse: t('threat.edgeSshKeyReuse'),
    auth_chain: t('threat.edgeAuthChain'),
    permission_propagation: t('threat.edgePermissionPropagation'),
  }
  const edgeColor = (et: string) =>
    et === 'ssh_key_reuse' ? '#ff4d4f' : et === 'auth_chain' ? '#fa8c16' : '#1890ff'

  const pathsWithFilter = (data.paths || []).map(row => ({
    ...row,
    _filtered: filterHumanTargets(row.targets),
  }))
  const allHumanCount = pathsWithFilter.reduce((s, r) => s + r._filtered.human.length, 0)
  const totalFiltered = pathsWithFilter.reduce((s, r) => s + r._filtered.system.length, 0)

  const columns = [
    {
      title: t('threat.attackSource'),
      key: 'source',
      width: 180,
      render: (_: any, row: AttackPathEntry & { _filtered: ReturnType<typeof filterHumanTargets> }) => (
        <Space direction="vertical" size="small">
          <Space>
            <Tag color={row.source_has_credential_leak ? 'red' : row.source_has_nopasswd ? 'orange' : 'blue'}>
              {row.source_name}
            </Tag>
            {row.source_ip && <Text type="secondary" style={{ fontSize: 11 }}>{row.source_ip}</Text>}
          </Space>
          <Space size={4}>
            {row.source_has_credential_leak && <Tag color="red" style={{ fontSize: 10 }}>{t('threat.credLeak')}</Tag>}
            {row.source_has_nopasswd && <Tag color="orange" style={{ fontSize: 10 }}>{t('threat.nopasswd')}</Tag>}
          </Space>
        </Space>
      ),
    },
    {
      title: t('threat.attackTargets'),
      key: 'targets',
      render: (_: any, row: AttackPathEntry & { _filtered: ReturnType<typeof filterHumanTargets> }) => {
        const { human, system } = row._filtered
        const visible = human.slice(0, 5)
        const hidden = human.length > 5 ? human.slice(5) : []
        return (
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            {visible.map(tgt => (
              <Tag key={tgt.snapshot_id} color={tgt.is_admin ? 'red' : 'green'}>
                {tgt.username} / {tgt.ip || tgt.hostname || `asset:${tgt.asset_id}`}{tgt.is_admin && ' ★'}
              </Tag>
            ))}
            {hidden.length > 0 && (
              <Text type="secondary" style={{ fontSize: 12, cursor: 'pointer' }} onClick={() => setDrawerEntry(row)}>
                +{hidden.length} more targets
              </Text>
            )}
            {human.length === 0 && system.length > 0 && (
              <Text type="secondary" style={{ fontSize: 12 }}>{t('threat.onlySystemAccounts', { count: system.length })}</Text>
            )}
          </Space>
        )
      },
    },
    {
      title: t('threat.attackHops'),
      key: 'hops',
      render: (_: any, row: AttackPathEntry) =>
        row.hops.length === 0 ? <Text type="secondary">—</Text> : (
          <Space wrap size="small">
            {row.hops.map((hop, i) => (
              <span key={i}>
                <Tag color={edgeColor(hop.edge_type)} style={{ fontSize: 11 }}>
                  {EDGE_TYPE_LABELS[hop.edge_type] || hop.edge_type}
                </Tag>
                {i < row.hops.length - 1 && <span style={{ margin: '0 1px', color: '#aaa' }}>→</span>}
              </span>
            ))}
          </Space>
        ),
    },
    {
      title: t('threat.reachableCount'),
      key: 'count',
      width: 120,
      render: (_: any, row: AttackPathEntry & { _filtered: ReturnType<typeof filterHumanTargets> }) => {
        const humanCount = row._filtered.human.length
        const sysCount = row._filtered.system.length
        return (
          <Space direction="vertical" size={2}>
            {humanCount > 0 && <Badge count={humanCount} style={{ backgroundColor: '#52c41a' }} />}
            {sysCount > 0 && <Text type="secondary" style={{ fontSize: 11 }}>+{sysCount} system</Text>}
          </Space>
        )
      },
    },
    {
      title: '',
      key: 'expand',
      width: 40,
      render: (_: any, row: AttackPathEntry & { _filtered: ReturnType<typeof filterHumanTargets> }) =>
        (row._filtered.system.length > 0 || row._filtered.human.length > 5)
          ? <Button size="small" type="text" onClick={() => setDrawerEntry(row)}>...</Button>
          : null,
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 12 }}>
        <Text>{t('threat.maxHops')}:</Text>
        {[1, 2, 3, 4, 5].map(n => (
          <Tag key={n} color={maxHops === n ? 'blue' : 'default'} onClick={() => setMaxHops(n)} style={{ cursor: 'pointer' }}>
            {n}
          </Tag>
        ))}
        <Text type="secondary" style={{ marginLeft: 16 }}>
          {t('threat.totalPaths')}: <strong>{data.total_paths}</strong>
          {' '}{t('threat.fromSources')}: <strong>{data.paths.length}</strong>
          {allHumanCount > 0 && <> · <strong>{allHumanCount}</strong> human targets</>}
          {totalFiltered > 0 && <> · <Text type="secondary">{totalFiltered} system filtered</Text></>}
        </Text>
      </Space>

      <Table
        rowKey="source_id"
        dataSource={pathsWithFilter as any}
        columns={columns}
        loading={loading}
        pagination={false}
        size="small"
        locale={{ emptyText: t('threat.noAttackPaths') }}
        expandable={{
          expandedRowKeys: expandedRow ? [expandedRow] : [],
          onExpandedRowsChange: keys => setExpandedRow(keys.length > 0 ? keys[0] as number : null),
          expandedRowRender: (row: AttackPathEntry & { _filtered: ReturnType<typeof filterHumanTargets> }) => {
            const { human, system } = row._filtered
            const extra = [...human.slice(5), ...system]
            if (extra.length === 0) return null
            return (
              <div style={{ padding: '4px 0' }}>
                <Text type="secondary" style={{ fontSize: 11, marginBottom: 6, display: 'block' }}>
                  {t('threat.allTargets')}:
                </Text>
                <Space wrap size="small">
                  {extra.map(tgt => (
                    <Tag key={tgt.snapshot_id} color={isHumanAccount(tgt.username) ? (tgt.is_admin ? 'red' : 'green') : 'default'}>
                      {tgt.username} / {tgt.ip || tgt.hostname || `asset:${tgt.asset_id}`}{tgt.is_admin && ' ★'}{!isHumanAccount(tgt.username) && ' [system]'}
                    </Tag>
                  ))}
                </Space>
              </div>
            )
          },
        }}
      />

      <Drawer
        title={drawerEntry ? `${drawerEntry.source_name} → ${t('threat.attackTargets')}` : ''}
        open={!!drawerEntry}
        onClose={() => setDrawerEntry(null)}
        width={480}
      >
        {drawerEntry && (() => {
          const { human, system } = filterHumanTargets(drawerEntry.targets)
          return (
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              {drawerEntry.hops.length > 0 && (
                <div>
                  <Text strong>{t('threat.attackHops')}:</Text>
                  <div style={{ marginTop: 8 }}>
                    <Space wrap size="small">
                      {drawerEntry.hops.map((hop, i) => (
                        <span key={i}>
                          <Tag color={edgeColor(hop.edge_type)} style={{ fontSize: 11 }}>
                            {EDGE_TYPE_LABELS[hop.edge_type] || hop.edge_type}
                          </Tag>
                          {i < drawerEntry.hops.length - 1 && <span style={{ color: '#aaa', margin: '0 2px' }}>→</span>}
                        </span>
                      ))}
                    </Space>
                  </div>
                </div>
              )}
              {human.length > 0 && (
                <div>
                  <Text strong style={{ marginBottom: 8, display: 'block' }}>{t('threat.humanTargets')} ({human.length})</Text>
                  <Space direction="vertical" style={{ width: '100%' }} size="small">
                    {human.map(tgt => (
                      <div key={tgt.snapshot_id} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Tag color={tgt.is_admin ? 'red' : 'green'}>{tgt.username}</Tag>
                        <Text type="secondary" style={{ fontSize: 12 }}>{tgt.ip || tgt.hostname || `asset:${tgt.asset_id}`}</Text>
                        {tgt.is_admin && <Tag color="red">★ admin</Tag>}
                      </div>
                    ))}
                  </Space>
                </div>
              )}
              {system.length > 0 && (
                <div>
                  <Text type="secondary" style={{ marginBottom: 8, display: 'block' }}>
                    {t('threat.systemAccountsFiltered')} ({system.length})
                  </Text>
                  <Space wrap size="small">
                    {system.map(tgt => (
                      <Tag key={tgt.snapshot_id} color="default" style={{ fontSize: 11 }}>
                        {tgt.username} [system]
                      </Tag>
                    ))}
                  </Space>
                </div>
              )}
            </Space>
          )
        })()}
      </Drawer>
    </div>
  )
}
