import { Select } from 'antd'
import { useTranslation } from 'react-i18next'

const LANGUAGES = [
  { value: 'zh-CN', label: '中文' },
  { value: 'en-US', label: 'English' },
]

export default function LanguageSwitcher() {
  const { i18n } = useTranslation()

  return (
    <Select
      value={i18n.language}
      options={LANGUAGES}
      onChange={(v) => i18n.changeLanguage(v)}
      style={{ width: 100 }}
      size="small"
    />
  )
}
