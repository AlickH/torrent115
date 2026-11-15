import React from 'react';
import { createRoot } from 'react-dom/client';
import { ConfigProvider, App as AntApp, theme as antTheme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import App from './App.jsx';
import './styles.css';

const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');
function resolve(mode) {
  if (mode === 'light') return false;
  if (mode === 'dark') return true;
  return darkQuery.matches;
}

function Root() {
  const [mode, setMode] = React.useState(() => localStorage.getItem('t115_theme_mode') || 'auto');
  const [dark, setDark] = React.useState(() => resolve(localStorage.getItem('t115_theme_mode') || 'auto'));
  React.useEffect(() => {
    const fn = () => setDark(resolve(mode));
    fn();
    darkQuery.addEventListener('change', fn);
    return () => darkQuery.removeEventListener('change', fn);
  }, [mode]);
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
          colorPrimary: '#1677ff', borderRadius: 8, borderRadiusLG: 12,
          colorBgLayout: dark ? '#000000' : '#ffffff',
          colorBorderSecondary: dark ? '#303030' : '#f0f0f0',
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
