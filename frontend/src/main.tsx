import React, { useState, useEffect } from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import { I18nextProvider, useTranslation } from 'react-i18next'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import zhCN from 'antd/locale/zh_CN'
import enUS from 'antd/locale/en_US'
import i18n from './i18n'
import App from './App'

function getAntdLocale(lang: string) {
  return lang === 'en-US' ? enUS : zhCN
}

function getDayjsLocale(lang: string) {
  return lang === 'en-US' ? 'en' : 'zh-cn'
}

function LangSync() {
  const { i18n } = useTranslation()
  useEffect(() => {
    const sync = () => dayjs.locale(getDayjsLocale(i18n.language))
    sync()
    return () => { i18n.off('languageChanged', sync) }
  }, [i18n])
  return null
}

function Root() {
  const [lang, setLang] = useState(() => i18n.language || 'zh-CN')
  useEffect(() => {
    const sync = () => setLang(i18n.language)
    return () => { i18n.off('languageChanged', sync) }
  }, [])
  return (
    <ConfigProvider
      locale={getAntdLocale(lang)}
      theme={{
        token: {
          colorPrimary: '#1677ff',
          fontFamily: 'Chinese, sans-serif',
        },
      }}
    >
      <LangSync />
      <App />
    </ConfigProvider>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <I18nextProvider i18n={i18n}>
      <BrowserRouter>
        <Root />
      </BrowserRouter>
    </I18nextProvider>
  </React.StrictMode>,
)
