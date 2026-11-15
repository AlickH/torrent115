import React from 'react';
import { TrimApp } from '@trimjs/web-app';
import { createRoot } from 'react-dom/client';
import { ConfigProvider, App as AntApp, theme as antTheme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import App from './App.jsx';
import './styles.css';

const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');
let trimApp = null;
if (typeof window !== 'undefined' && window.self !== window.top) {
  try { trimApp = new TrimApp(); } catch { trimApp = null; }
}

function resolve(mode, hostTheme) {
  if (mode === 'light') return false;
  if (mode === 'dark') return true;
  if (hostTheme) return hostTheme === 'dark';
  return darkQuery.matches;
}

function Root() {
  const [mode, setMode] = React.useState(() => localStorage.getItem('t115_theme_mode') || 'auto');
  const [hostTheme, setHostTheme] = React.useState(null);
  const [dark, setDark] = React.useState(() => resolve(localStorage.getItem('t115_theme_mode') || 'auto'));
  React.useEffect(() => {
    if (!trimApp) return;
    try {
      const title = trimApp.setTitle && trimApp.setTitle('Torrent115');
      if (title && title.catch) title.catch(() => {});
      const cfgPromise = trimApp.getPlatformConfig && trimApp.getPlatformConfig();
      if (cfgPromise && cfgPromise.then) {
        cfgPromise
          .then(cfg => { if (cfg && cfg.theme) setHostTheme(cfg.theme); })
          .catch(() => {});
      }
      trimApp.$on && trimApp.$on('os/theme', t => setHostTheme(t));
    } catch { /* 非 fnOS 宿主环境 */ }
  }, []);
  React.useEffect(() => {
    const fn = () => setDark(resolve(mode, hostTheme));
    fn();
    darkQuery.addEventListener('change', fn);
    return () => darkQuery.removeEventListener('change', fn);
  }, [mode, hostTheme]);
  React.useEffect(() => {
    localStorage.setItem('t115_theme_mode', mode);
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
    document.documentElement.style.colorScheme = dark ? 'dark' : 'light';
  }, [mode, dark]);
  return (
    <ConfigProvider
      locale={zhCN}
      button={{ autoInsertSpace: false }}
      theme={{
        algorithm: dark ? antTheme.darkAlgorithm : antTheme.defaultAlgorithm,
        token: {
          colorPrimary: '#1677ff', borderRadius: 8, borderRadiusLG: 10,
          colorBgLayout: dark ? '#0b0b0b' : '#f2f2f2',
          colorBgContainer: dark ? '#1c1c1c' : '#ffffff',
          colorBorderSecondary: dark ? '#2a2a2a' : '#ececec',
        },
      }}
    >
      <AntApp>
        <App mode={mode} setMode={setMode} dark={dark} />
      </AntApp>
    </ConfigProvider>
  );
}

createRoot(document.getElementById('root')).render(<Root />);
