import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Table, Button, Space, Tag, Typography, Drawer, Form, Input, Select,
  message, Popconfirm, Switch,
} from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import api from '../api/client'

const { Title } = Typography
const { Option } = Select

interface AppUser {
  id: number
  username: string
  role: 'admin' | 'operator' | 'viewer'
  email?: string
  is_active: boolean
  is_password_changed: boolean
  created_at: string
}

const ROLE_LABEL: Record<string, { color: string; labelKey: string }> = {
  admin:    { color: 'red',    labelKey: 'user.roleAdmin' },
  operator: { color: 'blue',   labelKey: 'user.roleOperator' },
  viewer:   { color: 'default', labelKey: 'user.roleViewer' },
}

const PASSWORD_HINT_KEY = 'user.passwordHint'

export default function Users() {
  const { t } = useTranslation()
  const [users, setUsers] = useState<AppUser[]>([])
  const [loading, setLoading] = useState(true)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editUser, setEditUser] = useState<AppUser | null>(null)
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)

  const fetchUsers = () => {
    setLoading(true)
    api.get('/users')
      .then(r => setUsers(r.data))
      .catch(() => message.error(t('msg.loadFailed')))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchUsers() }, [])

  const openAdd = () => {
    setEditUser(null)
    form.resetFields()
    setDrawerOpen(true)
  }

  const openEdit = (u: AppUser) => {
    setEditUser(u)
    form.setFieldsValue({ username: u.username, role: u.role, email: u.email || '', is_active: u.is_active })
    setDrawerOpen(true)
  }

  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)
      if (editUser) {
        const payload: Record<string, unknown> = {
          role: values.role,
          email: values.email || null,
          is_active: values.is_active,
        }
        if (values.password) payload.password = values.password
        await api.put(`/users/${editUser.id}`, payload)
        message.success(t('msg.userUpdated'))
      } else {
        await api.post('/users', values)
        message.success(t('msg.userCreated'))
      }
      setDrawerOpen(false)
      form.resetFields()
      fetchUsers()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.saveFailed'))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/users/${id}`)
      message.success(t('msg.deleted'))
      fetchUsers()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.deleteFailed'))
    }
  }

  const handleToggleActive = async (u: AppUser) => {
    try {
      await api.put(`/users/${u.id}`, { is_active: !u.is_active })
      message.success(u.is_active ? t('msg.disabled') : t('msg.enabled'))
      fetchUsers()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || t('msg.operationFailed'))
    }
  }

  const columns = [
    {
      title: t('user.username'),
      dataIndex: 'username',
      key: 'username',
      width: 160,
      render: (v: string, r: AppUser) => (
        <Space>
          {v}
          {!r.is_active && <Tag color="default">{t('status.disabled')}</Tag>}
          {!r.is_password_changed && <Tag color="orange">{t('user.needPwdChange')}</Tag>}
        </Space>
      ),
    },
    {
      title: t('user.role'),
      dataIndex: 'role',
      key: 'role',
      width: 120,
      render: (v: string) => {
        const cfg = ROLE_LABEL[v] || ROLE_LABEL.viewer
        return <Tag color={cfg.color}>{t(cfg.labelKey, cfg.labelKey)}</Tag>
      },
    },
    {
      title: t('user.email'),
      dataIndex: 'email',
      key: 'email',
      render: (v?: string) => v || '-',
    },
    {
      title: t('user.createdAt'),
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => new Date(v).toLocaleString('zh-CN'),
    },
    {
      title: t('user.status'),
      key: 'active',
      width: 90,
      render: (_: unknown, r: AppUser) => (
        <Switch
          checked={r.is_active}
          size="small"
          onChange={() => handleToggleActive(r)}
          checkedChildren={t('status.enabled')}
          unCheckedChildren={t('status.disabled')}
        />
      ),
    },
    {
      title: t('table.actions'),
      key: 'actions',
      render: (_: unknown, r: AppUser) => (
        <Space size="small">
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)}>{t('btn.edit')}</Button>
          <Popconfirm
            title={t('user.confirmDelete')}
            onConfirm={() => handleDelete(r.id)}
            okText={t('btn.delete')}
            cancelText={t('btn.cancel')}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>{t('btn.delete')}</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>{t('user.title')}</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>
          {t('btn.addUser')}
        </Button>
      </div>

      <Table
        dataSource={users}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10 }}
      />

      <Drawer
        title={editUser ? `${t('btn.editUser')}: ${editUser.username}` : t('btn.addUser')}
        onClose={() => { setDrawerOpen(false); form.resetFields() }}
        open={drawerOpen}
        width={420}
        footer={
          <div style={{ textAlign: 'right' }}>
            <Button onClick={() => { setDrawerOpen(false); form.resetFields() }} style={{ marginRight: 8 }}>{t('btn.cancel')}</Button>
            <Button type="primary" onClick={handleSave} loading={saving}>{t('btn.save')}</Button>
          </div>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="username"
            label={t('user.username')}
            rules={[{ required: true, message: t('user.enterUsername') }, { min: 2, message: t('user.min2Chars') }]}
          >
            <Input placeholder={t('user.loginUsername')} disabled={!!editUser} />
          </Form.Item>

          <Form.Item name="role" label={t('user.role')} rules={[{ required: true }]}>
            <Select placeholder={t('user.selectRole')}>
              <Option value="admin">
                <Tag color="red" style={{ marginRight: 8 }}>{t('user.roleAdmin')}</Tag>
                {t('user.roleAdminDesc')}
              </Option>
              <Option value="operator">
                <Tag color="blue" style={{ marginRight: 8 }}>{t('user.roleOperator')}</Tag>
                {t('user.roleOperatorDesc')}
              </Option>
              <Option value="viewer">
                <Tag color="default" style={{ marginRight: 8 }}>{t('user.roleViewer')}</Tag>
                {t('user.roleViewerDesc')}
              </Option>
            </Select>
          </Form.Item>

          <Form.Item name="email" label={t('user.emailOptional')}>
            <Input type="email" placeholder={t('user.notificationEmail')} />
          </Form.Item>

          {editUser && (
            <>
              <Form.Item name="is_active" label={t('user.accountStatus')} valuePropName="checked">
                <Switch checkedChildren={t('status.enabled')} unCheckedChildren={t('status.disabled')} />
              </Form.Item>

              <Form.Item
                name="password"
                label={t('user.newPassword') + ` (${t(PASSWORD_HINT_KEY, 'Leave blank to keep original. Min 8 chars with upper+lower+digit+special')})`}
                rules={[
                  { min: 8, message: t('user.pwdMin8') },
                  {
                    pattern: /(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[!@#$%^&*(),.?":{}|<>])/,
                    message: t('user.pwdComplexity'),
                  },
                ]}
              >
                <Input.Password placeholder={t('user.leaveBlankPwd')} />
              </Form.Item>
            </>
          )}

          {!editUser && (
            <Form.Item
              name="password"
              label={t('user.initialPassword')}
              rules={[
                { required: true, message: t('user.enterPwd') },
                { min: 8, message: t('user.pwdMin8') },
                {
                  pattern: /(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[!@#$%^&*(),.?":{}|<>])/,
                  message: t('user.pwdComplexity'),
                },
              ]}
            >
              <Input.Password placeholder="Admin123!" />
            </Form.Item>
          )}
        </Form>
      </Drawer>
    </div>
  )
}
