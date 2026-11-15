import { api, posterUrl, withTrackers } from './api.js';
import useAutoTrack from './hooks/useAutoTrack.js';
import { fmtTime } from './lib/format.js';
import { Suspense, lazy } from 'react';

const TrackingModals = lazy(() => import('./components/TrackingModals.jsx'));
const SettingsModal = lazy(() => import('./components/SettingsModals.jsx').then(m => ({ default: m.SettingsModal })));
const AiPresetModal = lazy(() => import('./components/SettingsModals.jsx').then(m => ({ default: m.AiPresetModal })));
const AccountModal = lazy(() => import('./components/SettingsModals.jsx').then(m => ({ default: m.AccountModal })));
const TrendingModal = lazy(() => import('./components/TrendingModal.jsx'));
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert, App as AntApp, AutoComplete, Button, Checkbox, Collapse, Col, Divider, Dropdown, Empty, Flex, Form, Image, Input, theme,
  Drawer, InputNumber, Menu, Modal, Popover, Row, Select, Space, Spin, Switch, Table, Tabs, Tag, Tooltip, Typography,
} from 'antd';
import {
  CalendarOutlined, CheckCircleOutlined, DesktopOutlined, EyeOutlined, FileTextOutlined, LogoutOutlined, MenuOutlined, MoonOutlined, PlusOutlined, QrcodeOutlined, SearchOutlined, SyncOutlined,
  SettingOutlined, SlidersOutlined, SunOutlined, FireOutlined,
} from '@ant-design/icons';

const SOURCE_LABELS = {
  all: '全部', pansou: '115分享', 'pansou-magnet': '盘搜磁力', apibay: 'TPB(apibay)',
  nyaa: 'Nyaa', dmhy: '动漫花园', btsearch: 'BTSearch', eztv: 'EZTV',
  knaben: 'knaben', therarbg: 'therarbg', bitmagnet: 'bitmagnet',
};
const SITE_SOURCES = ['apibay', 'nyaa', 'dmhy', 'btsearch', 'eztv', 'knaben', 'therarbg', 'bitmagnet'];
const ALL_KEYS = ['pansou', 'pansou-magnet', ...SITE_SOURCES];
const SOURCE_TAG_COLORS = {
  pansou: 'green', 'pansou-magnet': 'cyan', apibay: 'orange', nyaa: 'blue',
  dmhy: 'magenta', btsearch: 'purple', eztv: 'geekblue', knaben: 'volcano',
  therarbg: 'gold', bitmagnet: 'red',
};
const DEFAULT_SOURCES = {
  pansou: true, apibay: true, nyaa: true, dmhy: true, btsearch: true,
  eztv: true, knaben: true, therarbg: true, bitmagnet: false,
};

function useSwipeDismiss(open, onDismiss) {
  useEffect(() => {
    if (!open) return;
    let start = null;
    const down = e => {
      if (e.pointerType === 'mouse' && e.button !== 0) return;
      const t = e.target;
      if (!t || !t.closest || !t.closest('.ant-modal-content')) return;
      if (t.closest('input,textarea,button,a,select,.ant-input,.ant-input-affix-wrapper,.ant-select,.ant-checkbox-wrapper,.ant-radio-wrapper,.ant-slider,.ant-number-input')) return;
      start = { x: e.clientX, y: e.clientY };
    };
    const move = e => {
      if (!start) return;
      const dx = e.clientX - start.x;
      const dy = e.clientY - start.y;
      if (Math.abs(dx) > 110 && Math.abs(dx) > Math.abs(dy) * 1.5) {
        start = null;
        onDismiss();
      }
    };
    const up = () => { start = null; };
    window.addEventListener('pointerdown', down, true);
    window.addEventListener('pointermove', move, true);
    window.addEventListener('pointerup', up, true);
    window.addEventListener('pointercancel', up, true);
    return () => {
      window.removeEventListener('pointerdown', down, true);
      window.removeEventListener('pointermove', move, true);
      window.removeEventListener('pointerup', up, true);
      window.removeEventListener('pointercancel', up, true);
    };
  }, [open]);
}

function magnetKey(url) {
  const m = /btih:([0-9a-zA-Z]{32,40})/.exec(url || '');
  return m ? m[1].toLowerCase() : (url || '');
}

export default function App({ mode, setMode, dark }) {
  const { token } = theme.useToken();
  const { message, notification } = AntApp.useApp();
  const [cfg, setCfg] = useState(null);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const searchSeq = useRef(0);
  const searchAbort = useRef(null);
  const [results, setResults] = useState({ all: [] });
  const [activeTab, setActiveTab] = useState('all');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [trendingOpen, setTrendingOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [srcOpen, setSrcOpen] = useState(false);
  const [tabOverflow, setTabOverflow] = useState(false);
  const [checks, setChecks] = useState({});
  const checkQueue = useRef([]);
  const checking = useRef(false);
  const tabScrollRef = useRef(null);
  const [topH, setTopH] = useState(0);
  const [page, setPage] = useState(1);
  const [isMobile, setIsMobile] = useState(() => window.innerWidth <= 700);
  useEffect(() => {
    const fn = () => setIsMobile(window.innerWidth <= 700);
    window.addEventListener('resize', fn);
    return () => window.removeEventListener('resize', fn);
  }, []);

  const [sources, setSources] = useState(() => {
    try { return { ...DEFAULT_SOURCES, ...JSON.parse(localStorage.getItem('t115_srcs') || '{}') }; }
    catch { return DEFAULT_SOURCES; }
  });
  const [dedupe, setDedupe] = useState(() => localStorage.getItem('t115_dedupe') !== '0');
  const [expand, setExpand] = useState(() => localStorage.getItem('t115_expand') !== '0');
  const [minSeeds, setMinSeeds] = useState(() => parseInt(localStorage.getItem('t115_seeds') || '0', 10) || 0);
  const [pageSize, setPageSize] = useState(() => parseInt(localStorage.getItem('t115_page_size') || '50', 10) || 50);
  const [hideInvalid, setHideInvalid] = useState(() => localStorage.getItem('t115_hide_invalid') === '1');
  useEffect(() => { localStorage.setItem('t115_srcs', JSON.stringify(sources)); }, [sources]);
  useEffect(() => { localStorage.setItem('t115_dedupe', dedupe ? '1' : '0'); }, [dedupe]);
  useEffect(() => { localStorage.setItem('t115_expand', expand ? '1' : '0'); }, [expand]);
  useEffect(() => { localStorage.setItem('t115_seeds', String(minSeeds)); }, [minSeeds]);
  useEffect(() => { localStorage.setItem('t115_page_size', String(pageSize)); }, [pageSize]);
  useEffect(() => { localStorage.setItem('t115_hide_invalid', hideInvalid ? '1' : '0'); }, [hideInvalid]);

  // form state
  const [cookieText, setCookieText] = useState('');
  const [tmdbText, setTmdbText] = useState('');
  const [pansouUrl, setPansouUrl] = useState('');
  const [bitmagnetUrl, setBitmagnetUrl] = useState('');
  const [targetCid, setTargetCid] = useState('');
  const [transferCid, setTransferCid] = useState('');
  const [outboundProxy, setOutboundProxy] = useState('');
  const [accUser, setAccUser] = useState('');
  const [accOld, setAccOld] = useState('');
  const [accNew, setAccNew] = useState('');
  const [accNew2, setAccNew2] = useState('');
  const [qrOpen, setQrOpen] = useState(false);
  const [qrData, setQrData] = useState(null);
  const qrTimer = useRef(null);
  useSwipeDismiss(settingsOpen, () => setSettingsOpen(false));
  useSwipeDismiss(srcOpen, () => setSrcOpen(false));
  useSwipeDismiss(qrOpen, () => setQrOpen(false));

  const loadConfig = useCallback(async () => {
    const d = await api('/api/config');
    setCfg(d);
    setPansouUrl(d.pansou_url || '');
    setBitmagnetUrl(d.bitmagnet_url || '');
    setTargetCid(d.p115_target_cid || '');
    setTransferCid(d.p115_transfer_cid || '');
    setOutboundProxy(d.outbound_proxy || '');
  }, []);
  useEffect(() => { loadConfig().catch(e => message.error(e.message)); }, [loadConfig, message]);

  const topRef = useRef(null);
  useEffect(() => {
    if (!topRef.current) return;
    const ro = new ResizeObserver(() => setTopH(topRef.current?.offsetHeight || 0));
    ro.observe(topRef.current);
    setTopH(topRef.current.offsetHeight);
    return () => ro.disconnect();
  }, []);

  const rebuildAll = (res, useDedupe) => {
    const seen = new Set();
    const out = [];
    ALL_KEYS.forEach(k => {
      (res[k] || []).forEach(it => {
        if (useDedupe) {
          const key = magnetKey(it.url);
          if (seen.has(key)) return;
          seen.add(key);
        }
        out.push(it);
      });
    });
    res.all = out;
  };

  const doSearch = async term => {
    const q = (typeof term === 'string' ? term : query).trim();
    if (!q) return;
    const seq = ++searchSeq.current;
    if (searchAbort.current) searchAbort.current.abort();
    const ac = new AbortController();
    searchAbort.current = ac;
    const tasks = [];
    if (sources.pansou && cfg?.pansou_url) tasks.push('pansou');
    SITE_SOURCES.forEach(k => { if (sources[k] && (k !== 'bitmagnet' || cfg?.bitmagnet_url)) tasks.push(k); });
    if (!tasks.length) { message.warning('至少选择一个搜索源'); return; }

    const res = { all: [] };
    setResults(res);
    setActiveTab('all');
    setPage(1);
    setLoading(true);
    message.info(`正在搜索 ${tasks.length} 个来源…`);
    let resolvedTag = '';
    let done = 0;

    const finish = (key, items, errMsg) => {
      if (seq !== searchSeq.current) return;
      done += 1;
      notification.destroy('search-info');
      if (errMsg) {
        notification.error({ key: 'src-' + key, message: SOURCE_LABELS[key] || key, description: errMsg, duration: 6, placement: 'topRight' });
      } else {
        notification.success({ key: 'src-' + key, message: SOURCE_LABELS[key] || key, description: `✓ ${items.length} 条`, duration: 3, placement: 'topRight' });
      }
      rebuildAll(res, dedupe);
      res.all = res.all || [];
      setResults({ ...res });
      if (done === tasks.length) {
        setLoading(false);
        if (!resolvedTag) message.info('搜索完成');
        else message.success('搜索完成 · 已识别：' + resolvedTag);
      }
    };

    const promises = tasks.map(async key => {
      try {
        if (key === 'pansou') {
          const r = await api('/api/search/pansou?q=' + encodeURIComponent(q), { signal: ac.signal });
          const items = r.items || [];
          res.pansou = items.filter(x => x.source === 'pansou');
          res['pansou-magnet'] = items.filter(x => x.source === 'pansou-magnet');
          const err = r.errors && Object.keys(r.errors).length ? Object.values(r.errors)[0] : null;
          finish('pansou', items, err);
        } else {
          const extra = `&expand=${expand ? 1 : 0}&min_seeds=${minSeeds || 0}`;
          const r = await api(`/api/search/site?source=${key}&q=${encodeURIComponent(q)}${extra}`, { signal: ac.signal });
          res[key] = r.items || [];
          const rv = r.resolved || {};
          if (!resolvedTag && rv.title_en) {
            resolvedTag = rv.title_en + (rv.year ? ` (${rv.year})` : '') + (rv.imdb_id ? ` [${rv.imdb_id}]` : '');
          }
          const err = r.errors && Object.keys(r.errors).length ? Object.values(r.errors)[0] : null;
          finish(key, res[key], err);
        }
      } catch (e) {
        if (seq !== searchSeq.current || e.name === 'AbortError') return;
        finish(key, [], e.message || '请求失败');
      }
    });
    await Promise.allSettled(promises);
    if (seq === searchSeq.current) setLoading(false);
  };

  const transfer = async item => {
    try {
      if (item.kind === '115') {
        const r = await api('/api/transfer115', { method: 'POST', body: { url: item.url, password: item.password || '' } });
        if (r.ok) message.success('转存成功');
        else message.error(r.error || '转存失败');
      } else {
        const r = await api('/api/add115', { method: 'POST', body: { urls: [item.url] } });
        if (r.ok) message.success('已发送到 115 云下载');
        else message.error(r.error || '发送失败');
      }
    } catch (e) { message.error(e.message); }
  };

  const checkShare = async item => {
    setChecks(prev => ({ ...prev, [item.url]: { loading: true } }));
    try {
      const r = await api('/api/115/share_check?url=' + encodeURIComponent(item.url) + '&password=' + encodeURIComponent(item.password || ''));
      setChecks(prev => ({ ...prev, [item.url]: r.available ? { ok: true, msg: '可转存' } : { ok: false, msg: r.reason || r.error || '已失效' } }));
    } catch (e) {
      setChecks(prev => ({ ...prev, [item.url]: { ok: false, msg: e.message } }));
    }
  };

  const runCheckQueue = async () => {
    if (checking.current) return;
    checking.current = true;
    while (checkQueue.current.length) {
      const it = checkQueue.current.shift();
      setChecks(prev => ({ ...prev, [it.url]: { loading: true } }));
      try {
        const r = await api('/api/115/share_check?url=' + encodeURIComponent(it.url) + '&password=' + encodeURIComponent(it.password || ''));
        setChecks(prev => ({ ...prev, [it.url]: r.available ? { ok: true, msg: '可转存' } : { ok: false, msg: '已失效', reason: r.reason || '' } }));
      } catch (e) {
        setChecks(prev => ({ ...prev, [it.url]: { ok: false, msg: '检测失败' } }));
      }
      await new Promise(res => setTimeout(res, 300));
    }
    checking.current = false;
  };

  useEffect(() => {
    const seen = new Set();
    const add = [];
    Object.values(results).forEach(arr => {
      (arr || []).forEach(it => {
        if (it.kind !== '115' || !it.url || seen.has(it.url)) return;
        seen.add(it.url);
        if (!checks[it.url]) add.push(it);
      });
    });
    if (add.length) {
      checkQueue.current.push(...add);
      runCheckQueue();
    }
  }, [results]);

  const copyUrl = async item => {
    const raw = item.url || '';
    const text = withTrackers(raw);
    const tip = text !== raw ? '已复制（已附带 tracker）' : '已复制';
    try { await navigator.clipboard.writeText(text); message.success(tip); }
    catch {
      const el = document.createElement('textarea');
      el.value = text; document.body.appendChild(el); el.select();
      document.execCommand('copy'); el.remove(); message.success(tip);
    }
  };
  const openShare = item => window.open(item.url, '_blank');

  const sourceColumn = {
      title: '来源', width: 120,
      render: (_, it) => (
        <Space direction="vertical" size={2}>
          <Tag bordered={false} color={SOURCE_TAG_COLORS[it.source] || 'default'} style={{ marginInlineEnd: 0 }}>{it.source}</Tag>
          <Tag bordered={false} style={{ marginInlineEnd: 0 }}>{it.kind === '115' ? '115分享' : it.kind}</Tag>
        </Space>
      ),
    };
  const columns = [
    ...(isMobile ? [] : [sourceColumn]),
    {
      title: '标题',
      render: (_, it) => (
        <div className="title-cell">
          <div>
            {isMobile ? <Tag bordered={false} color={SOURCE_TAG_COLORS[it.source] || 'default'} style={{ marginRight: 6 }}>{it.source}</Tag> : null}
            <Typography.Text strong>{it.title}</Typography.Text>
            {it.seeders ? <Typography.Text type="secondary"> · {it.seeders} seeds</Typography.Text> : null}
            {checks[it.url] && (checks[it.url].loading || !checks[it.url].ok) ? (
              <Tag style={{ marginLeft: 8 }} bordered={false} color={checks[it.url].loading ? 'processing' : 'error'} title={checks[it.url].reason || ''}>
                {checks[it.url].loading ? '检测中…' : '已失效'}
              </Tag>
            ) : null}
          </div>
          {(it.meta || it.tmdb) && (
            <Flex wrap gap={4} style={{ margin: '4px 0' }}>
              {(it.meta || '').split(' · ').filter(Boolean).map((t, i) => <Tag key={i} bordered={false} style={{ marginInlineEnd: 0 }}>{t}</Tag>)}
              {it.tmdb ? <Tag bordered={false} color="green" style={{ marginInlineEnd: 0 }}>TMDB: {it.tmdb}</Tag> : null}
            </Flex>
          )}
          <Typography.Text className="mono" type="secondary" title={it.password ? `${it.url}  密码:${it.password}` : it.url}>
            {(it.password ? `${it.url}  密码:${it.password}` : it.url)}
          </Typography.Text>
        </div>
      ),
    },
    {
      title: '操作', width: isMobile ? 96 : 130,
      render: (_, it) => (
        <Space direction="vertical" style={{ width: '100%' }}>
          <Button type="primary" size="small" block onClick={() => transfer(it)}>
            {it.kind === '115' ? (isMobile ? '转存' : '转存到115') : (isMobile ? '云下载' : '发到115云下载')}
          </Button>
          <Button size="small" block onClick={() => (it.kind === '115' ? openShare(it) : copyUrl(it))}>
            {it.kind === '115' ? '打开' : '复制'}
          </Button>
        </Space>
      ),
    },
  ];

  const displayResults = useMemo(() => {
    const isInvalid = it => checks[it.url] && !checks[it.url].loading && checks[it.url].ok === false;
    if (!hideInvalid) return results;
    const out = {};
    Object.entries(results).forEach(([k, arr]) => {
      out[k] = (arr || []).filter(it => !isInvalid(it));
    });
    return out;
  }, [results, checks, hideInvalid]);

  const tabItems = useMemo(() => {
    return Object.keys(displayResults)
      .filter(k => (displayResults[k] || []).length > 0 || k === 'all')
      .sort((a, b) => (a === 'all' ? -1 : b === 'all' ? 1 : 0))
      .map(k => ({ key: k, label: `${SOURCE_LABELS[k] || k} ${(displayResults[k] || []).length}` }));
  }, [displayResults]);

  useEffect(() => {
    const el = tabScrollRef.current;
    if (!el) return;
    const check = () => setTabOverflow(el.scrollWidth > el.clientWidth + 1);
    check();
    const ro = new ResizeObserver(check);
    ro.observe(el);
    return () => ro.disconnect();
  }, [tabItems.length, isMobile]);

  const scrollTabIntoView = key => {
    const el = tabScrollRef.current;
    if (!el) return;
    const target = el.querySelector('[data-key="' + key + '"]');
    if (target) target.scrollIntoView({ inline: 'nearest', block: 'nearest', behavior: 'smooth' });
  };

  const rows = displayResults[activeTab] || [];
  const rowKey = it => `${it.source}-${magnetKey(it.url)}-${it.title}`;
  const themeIcon = mode === 'auto' ? <DesktopOutlined /> : mode === 'light' ? <SunOutlined /> : <MoonOutlined />;
  const themeTip = mode === 'auto' ? '主题：跟随系统（点击切换）' : mode === 'light' ? '主题：亮色（点击切换）' : '主题：暗色（点击切换）';
  const cycleTheme = () => setMode(mode === 'auto' ? 'light' : mode === 'light' ? 'dark' : 'auto');

  const sourcePanel = (
    <div style={{ width: isMobile ? '100%' : 520, padding: '4px 2px' }}>
      <Typography.Text type="secondary">搜索源</Typography.Text>
      <Flex wrap gap={12} style={{ margin: '8px 0 12px' }}>
        {cfg?.pansou_url ? (
          <Checkbox checked={sources.pansou} onChange={e => setSources({ ...sources, pansou: e.target.checked })}>PanSou</Checkbox>
        ) : null}
        {SITE_SOURCES.filter(k => k !== 'bitmagnet' || !!cfg?.bitmagnet_url).map(k => (
          <Checkbox key={k} checked={!!sources[k]} onChange={e => setSources({ ...sources, [k]: e.target.checked })}>
            {SOURCE_LABELS[k]}
          </Checkbox>
        ))}
      </Flex>
      <Divider style={{ margin: '8px 0' }} />
      <Typography.Text type="secondary">选项</Typography.Text>
      <Flex wrap gap={16} align="center" style={{ marginTop: 8 }}>
        <Checkbox checked={dedupe} onChange={e => setDedupe(e.target.checked)}>去重合并</Checkbox>
        <Checkbox checked={expand} onChange={e => setExpand(e.target.checked)}>季集展开</Checkbox>
        <Space>最少种子 <InputNumber min={0} value={minSeeds} onChange={v => setMinSeeds(v || 0)} style={{ width: 72 }} /></Space>
        <Space>每页 <InputNumber min={10} max={200} step={10} value={pageSize} onChange={v => { setPageSize(v || 50); setPage(1); }} style={{ width: 80 }} /> 条</Space>
        <Checkbox checked={hideInvalid} onChange={e => setHideInvalid(e.target.checked)}>隐藏失效115资源</Checkbox>
      </Flex>
    </div>
  );

  const track = useAutoTrack({ message, setCfg });

  // ---- settings helpers ----
  const openSettings = () => {
    setCookieText(''); setTmdbText(''); setAccUser(''); setAccOld(''); setAccNew(''); setAccNew2('');
    setSettingsOpen(true);
  };
  const revealCookie = async () => {
    if (cookieText) { setCookieText(''); return; }
    const r = await api('/api/secrets?name=cookie');
    setCookieText(r.value || '');
  };
  const saveSettings = async () => {
    const body = {
      pansou_url: pansouUrl,
      bitmagnet_url: bitmagnetUrl,
      p115_target_cid: targetCid,
      p115_transfer_cid: transferCid,
      outbound_proxy: outboundProxy,
    };
    if (tmdbText) body.tmdb_api_key = tmdbText;
    if (cookieText) body.p115_cookie = cookieText;
    const r = await api('/api/config', { method: 'POST', body });
    setCfg(r);
    message.success('已保存');
    setSettingsOpen(false);
  };
  const test115 = async () => {
    const r = await api('/api/115/test');
    if (r.ok) message.success(`115 连接正常，默认云下载目录 CID: ${r.default_cid}`);
    else message.error(r.error || '测试失败');
  };
  const saveAccount = async () => {
    if (accNew && accNew !== accNew2) { message.error('两次输入的新密码不一致'); return; }
    const r = await api('/api/account', { method: 'POST', body: { user: accUser, old: accOld, password: accNew } });
    if (r.ok) { message.success('账号已更新'); setAccUser(''); setAccOld(''); setAccNew(''); setAccNew2(''); setCfg({ ...cfg, auth_user: r.auth_user }); }
    else message.error(r.error || '保存失败');
  };
  const startQr = async () => {
    const r = await api('/api/115/qr/start', { method: 'POST', body: {} });
    if (!r.ok) { message.error(r.error || '获取二维码失败'); return; }
    setQrData(r); setQrOpen(true);
    clearInterval(qrTimer.current);
    qrTimer.current = setInterval(async () => {
      try {
        const s = await api(`/api/115/qr/status?uid=${encodeURIComponent(r.uid)}&time=${encodeURIComponent(r.time)}&sign=${encodeURIComponent(r.sign)}`);
        if (s.ok && s.status === 2) {
          clearInterval(qrTimer.current);
          message.success('115 登录成功');
          setQrOpen(false); loadConfig();
        } else if (s.status === -1 || s.status === -2) {
          clearInterval(qrTimer.current);
          message.error(s.msg || '二维码已失效'); setQrOpen(false);
        }
      } catch { clearInterval(qrTimer.current); }
    }, 2000);
  };

  const bg = token.colorBgLayout;
  const navMenu = (
    <Menu
      className="app-sidebar-menu"
      mode="inline"
      selectedKeys={['search']}
      style={{ border: 'none', background: 'transparent' }}
      items={[
        { key: 'search', icon: <SearchOutlined />, label: '搜索' },
        { key: 'auto', icon: <CalendarOutlined />, label: '追剧自动转存' },
        { key: 'trending', icon: <FireOutlined />, label: 'TMDB 最近热映' },
        { key: 'sources', icon: <SlidersOutlined />, label: '搜索源与选项' },
        { type: 'divider' },
        { key: 'settings', icon: <SettingOutlined />, label: '设置' },
        { key: 'theme', icon: themeIcon, label: themeTip },
        { key: 'logout', icon: <LogoutOutlined />, label: '退出登录' },
      ]}
      onClick={({ key }) => {
        setNavOpen(false);
        if (key === 'auto') track.openAuto();
        else if (key === 'trending') setTrendingOpen(true);
        else if (key === 'sources') setSrcOpen(true);
        else if (key === 'settings') openSettings();
        else if (key === 'theme') cycleTheme();
        else if (key === 'logout') window.location.href = '/logout';
      }}
    />
  );
  const brandMark = (
    <Flex align="center" gap={8} style={{ padding: '6px 10px 14px' }}>
      <svg viewBox="0 0 32 32" aria-hidden="true" style={{ width: 22, height: 22 }}><rect width="32" height="32" rx="8" fill={token.colorPrimary}/><path d="M9 7v10a7 7 0 0 0 14 0V7" fill="none" stroke="#fff" strokeWidth="3.2" strokeLinecap="round"/><path d="M9 7h4v6H9zM19 7h4v6h-4z" fill="#fff"/></svg>
      <Typography.Text strong style={{ fontSize: 15 }}>Torrent115</Typography.Text>
    </Flex>
  );
  return (
    <div className="page" style={{ minHeight: '100vh', background: bg }}>
      {!isMobile ? (
        <aside style={{ position: 'fixed', left: 0, top: 0, bottom: 0, width: 200, zIndex: 30, display: 'flex', flexDirection: 'column', padding: '10px 8px', background: bg }}>
          {brandMark}
          <div style={{ flex: 1, overflow: 'auto' }}>{navMenu}</div>
          <Typography.Text type="secondary" style={{ fontSize: 11, padding: 8 }}>磁力搜索 → 115 云下载</Typography.Text>
        </aside>
      ) : null}
      <Drawer open={navOpen} onClose={() => setNavOpen(false)} placement="left" width={250} title="Torrent115" styles={{ body: { padding: 8 } }}>
        {navMenu}
      </Drawer>
      <div className="page-inner" style={isMobile ? { padding: 12, height: '100vh', overflow: 'auto' } : { marginLeft: 208, marginRight: 8, marginTop: 8, marginBottom: 8, height: 'calc(100vh - 16px)', overflow: 'auto', maxWidth: 'none', background: token.colorBgContainer, borderRadius: 12, padding: 20, boxShadow: '0 1px 2px rgba(0,0,0,.04)' }}>
        {track.auto?.running ? (
          <div style={{ position: 'fixed', right: 20, bottom: 20, zIndex: 1000, background: token.colorBgContainer, border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 24, padding: '8px 16px', boxShadow: '0 6px 20px rgba(0,0,0,.12)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Spin size="small" />
            <span style={{ fontSize: 13 }}>自动任务运行中…</span>
          </div>
        ) : null}
        <div ref={topRef} className="topbar" style={{ position: 'sticky', top: 0, zIndex: 20, background: token.colorBgContainer, paddingBottom: 8 }}>
          <div className="pad-x" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {isMobile ? <Button type="text" icon={<MenuOutlined />} onClick={() => setNavOpen(true)} /> : null}
            <Typography.Text strong style={{ fontSize: 17 }}>磁力搜索</Typography.Text>
          </div>
          {cfg?.is_default_auth ? (
            <div style={{ marginTop: 8, padding: '6px 12px', background: token.colorWarningBg, borderRadius: token.borderRadius }}>
              ⚠️ 正在使用默认账号 admin / admin，请尽快修改
              <Button size="small" type="link" onClick={openSettings}>去修改</Button>
            </div>
          ) : null}
          <div className="pad-x">
          <Input.Search
            size="large"
            value={query}
            placeholder="输入片名，回车搜索…"
            onChange={e => setQuery(e.target.value)}
            onSearch={doSearch}
            enterButton="搜索"
            allowClear
            style={{ marginTop: 12 }}
          />
          </div>
          <div style={{ borderBottom: `1px solid ${token.colorBorderSecondary}`, marginTop: 8, display: 'flex', alignItems: 'stretch' }}>
            <div
              ref={tabScrollRef}
              className="tabscroll"
              style={{ display: 'flex', gap: 0, overflowX: 'auto', overflowY: 'hidden', scrollbarWidth: 'none', msOverflowStyle: 'none', flex: 1, minWidth: 0 }}
            >
              {tabItems.map(it => {
                const active = it.key === activeTab;
                return (
                  <button
                    key={it.key}
                    data-key={it.key}
                    onClick={() => { setActiveTab(it.key); setPage(1); window.scrollTo({ top: 0, behavior: 'auto' }); }}
                    style={{
                      background: 'transparent', border: 0, cursor: 'pointer', padding: '10px 2px', marginRight: 28,
                      color: active ? token.colorPrimary : token.colorTextSecondary,
                      borderBottom: active ? `2px solid ${token.colorPrimary}` : '2px solid transparent',
                      marginBottom: -1, fontSize: 14, whiteSpace: 'nowrap',
                    }}
                  >
                    {SOURCE_LABELS[it.key] || it.key}
                    <span style={{ color: token.colorTextTertiary, marginLeft: 6, fontSize: 12 }}>{(displayResults[it.key] || []).length}</span>
                  </button>
                );
              })}
            </div>
            {tabOverflow ? (
              <Dropdown
                trigger={['click']}
                menu={{
                  items: tabItems.map(it => ({ key: it.key, label: (SOURCE_LABELS[it.key] || it.key) + ' ' + (results[it.key] || []).length })),
                  onClick: ({ key }) => { setActiveTab(key); setPage(1); window.scrollTo({ top: 0, behavior: 'auto' }); scrollTabIntoView(key); },
                }}
              >
                <button style={{ background: 'transparent', border: 0, cursor: 'pointer', padding: '0 8px', color: token.colorTextSecondary, fontSize: 16 }} title="更多">⋯</button>
              </Dropdown>
            ) : null}
          </div>
        </div>
        <div>
          <Table
            size="middle"
            rowKey={rowKey}
            columns={columns}
            dataSource={rows}
            pagination={{ current: page, pageSize, onChange: setPage, showSizeChanger: false, showTotal: t => `共 ${t} 条`, size: 'small' }}
            loading={loading && !rows.length}
            sticky={{ offsetHeader: topH }}
            scroll={isMobile ? undefined : { x: 860 }}
            locale={{ emptyText: <Empty description={loading ? '搜索中…' : '还没有结果，先搜索吧'} /> }}
          />
        </div>
      </div>

      <Modal
        open={srcOpen}
        onCancel={() => setSrcOpen(false)}
        footer={null}
        title="搜索源与选项"
        width={Math.min(420, typeof window !== 'undefined' ? window.innerWidth - 24 : 400)}
        styles={{ body: { paddingTop: 8 } }}
      >
        {sourcePanel}
      </Modal>

      {trendingOpen ? (
        <Suspense fallback={null}>
          <TrendingModal open={trendingOpen} onClose={() => setTrendingOpen(false)} track={track} onDirectSearch={t => { setTrendingOpen(false); setQuery(t); doSearch(t); }} />
        </Suspense>
      ) : null}

      {track.autoOpen || track.traktOauthOpen ? (
        <Suspense fallback={null}><TrackingModals {...track} cfg={cfg} token={token} /></Suspense>
      ) : null}

      {track.aiPresetOpen ? (
        <Suspense fallback={null}>
          <AiPresetModal
            {...track}
            open={!!track.aiPresetOpen}
            draft={track.aiPresetDraft}
            onClose={() => { track.setAiPresetOpen(false); track.setAiPresetDraft(null); }}
          />
        </Suspense>
      ) : null}

      {settingsOpen ? (
        <Suspense fallback={null}>
        <SettingsModal
          {...track}
          open={settingsOpen}
          onClose={() => setSettingsOpen(false)}
          cfg={cfg}
          onAccount={() => setAccountOpen(true)}
          test115={test115}
          onSave={async () => { await track.saveAuto(); await saveSettings(); }}
          cookieText={cookieText}
          setCookieText={setCookieText}
          revealCookie={revealCookie}
          startQr={startQr}
          targetCid={targetCid}
          setTargetCid={setTargetCid}
          transferCid={transferCid}
          setTransferCid={setTransferCid}
          tmdbText={tmdbText}
          setTmdbText={setTmdbText}
          pansouUrl={pansouUrl}
          setPansouUrl={setPansouUrl}
          bitmagnetUrl={bitmagnetUrl}
          setBitmagnetUrl={setBitmagnetUrl}
          outboundProxy={outboundProxy}
          setOutboundProxy={setOutboundProxy}
        />
        </Suspense>
      ) : null}

      {accountOpen ? (
        <Suspense fallback={null}>
        <AccountModal
          open={accountOpen}
          onClose={() => setAccountOpen(false)}
          cfg={cfg}
          accUser={accUser}
          setAccUser={setAccUser}
          accOld={accOld}
          setAccOld={setAccOld}
          accNew={accNew}
          setAccNew={setAccNew}
          accNew2={accNew2}
          setAccNew2={setAccNew2}
          saveAccount={saveAccount}
        />
        </Suspense>
      ) : null}

      <Modal open={qrOpen} title="扫码登录 115" onCancel={() => setQrOpen(false)} footer={null} width={360}>
        <Flex vertical align="center" gap={12}>
          {qrData?.image ? <Image src={qrData.image} width={240} preview={false} alt="115 二维码" /> : <Spin />}
          <Typography.Text type="secondary">请用 115 App 扫码，登录成功后会自动保存 Cookie</Typography.Text>
        </Flex>
      </Modal>
    </div>
  );
}
