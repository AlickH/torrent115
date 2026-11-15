import { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';

export default function useAutoTrack({ message, setCfg }) {
  const [autoOpen, setAutoOpen] = useState(false);
  const [presetListOpen, setPresetListOpen] = useState(false);
  const [presetTab, setPresetTab] = useState('tv');
  const [logsOpen, setLogsOpen] = useState(false);
  const [doneOpen, setDoneOpen] = useState(false);
  const [doneItems, setDoneItems] = useState([]);
  const [pendingItems, setPendingItems] = useState([]);
  const [autoTab, setAutoTab] = useState('tv');
  const [addOpen, setAddOpen] = useState(false);
  const [addQuery, setAddQuery] = useState('');
  const [editItem, setEditItem] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const [editForm, setEditForm] = useState({});
  const [auto, setAuto] = useState(null);
  const [autoShows, setAutoShows] = useState([]);
  const [addShowId, setAddShowId] = useState('');
  const [showOptions, setShowOptions] = useState([]);
  const [showSearching, setShowSearching] = useState(false);
  const [aiKey, setAiKey] = useState('');
  const [traktToken, setTraktToken] = useState('');
  const [presets, setPresets] = useState([]);
  const [aiPresets, setAiPresets] = useState([]);
  const [aiPresetOpen, setAiPresetOpen] = useState(false);
  const [aiPresetDraft, setAiPresetDraft] = useState(null);
  const [aiTesting, setAiTesting] = useState(false);
  const [aiModels, setAiModels] = useState([]);
  const [aiModelsLoading, setAiModelsLoading] = useState(false);
  const [calendarSource, setCalendarSource] = useState('tmdb');
  const [maxEpisodes, setMaxEpisodes] = useState(10);
  const [taskTimeout, setTaskTimeout] = useState(10);
  const [waitTimeout, setWaitTimeout] = useState(3);
  const [drivembyEnabled, setDrivembyEnabled] = useState(true);
  const [traktOauthOpen, setTraktOauthOpen] = useState(false);
  const [traktAuthUrl, setTraktAuthUrl] = useState('');
  const [traktRedirectUri, setTraktRedirectUri] = useState('');
  const [traktOauthError, setTraktOauthError] = useState('');
  const [tvPreset, setTvPreset] = useState('');
  const [moviePreset, setMoviePreset] = useState('');
  const [presetOpen, setPresetOpen] = useState(null);
  const [presetDraft, setPresetDraft] = useState(null);
  const showSearchTimer = useRef(null);
  const [rankOrder, setRankOrder] = useState(['shares', 'seeders', 'resolution', 'size', 'codec']);
  const [seedTiers, setSeedTiers] = useState('10,100,1000,10000');
  const [autoForm, setAutoForm] = useState({
    enabled: false, interval: 180, days: 2, dryRun: true, maxSize: 0, minSeeds: 1, strict: true,
    resOrder: ['2160p', '1080p', '720p'], codec: '', aiEnabled: false,
    aiBase: 'https://api.openai.com/v1', aiModel: 'gpt-4o-mini', traktClientId: '',
  });

  const loadAuto = async () => {
    const d = await api('/api/auto/status');
    setAuto(d);
    setAutoShows(d.auto_shows || []);
    setAutoForm({
      enabled: !!d.auto_enabled, interval: d.auto_interval || 180, days: d.auto_days || 2,
      dryRun: d.auto_dry_run !== false, maxSize: d.auto_max_size_gb || 0, minSeeds: d.auto_min_seeders || 0, strict: d.auto_strict_match !== false,
      resOrder: d.auto_res_order || ['2160p', '1080p', '720p'], codec: d.auto_codec || '',
      aiEnabled: !!d.ai_enabled, aiBase: d.ai_base_url || 'https://api.openai.com/v1',
      aiModel: d.ai_model || 'gpt-4o-mini', traktClientId: d.trakt_client_id || '',
    });
    setPresets(d.auto_presets || []);
    setAiPresets(d.ai_presets || []);
    setCalendarSource(d.calendar_source || 'tmdb');
    setMaxEpisodes(d.auto_max_episodes != null ? d.auto_max_episodes : 10);
    setTaskTimeout(d.auto_task_timeout != null ? d.auto_task_timeout : 10);
    setWaitTimeout(d.auto_wait_timeout != null ? d.auto_wait_timeout : 3);
    setDrivembyEnabled(d.drivemby_enabled !== false);
    setRankOrder(d.auto_rank_order || ['shares', 'seeders', 'resolution', 'size', 'codec']);
    setSeedTiers((d.auto_seed_tiers || [10, 100, 1000, 10000]).join(','));
    setTvPreset(d.auto_tv_preset || '');
    setMoviePreset(d.auto_movie_preset || '');
  };
  const refreshAutoStatus = async () => {
    try {
      const d = await api('/api/auto/status');
      setAuto(d);
    } catch (e) { /* ignore */ }
  };
  useEffect(() => { loadAuto().catch(() => {}); }, []);
  useEffect(() => {
    const t = setInterval(() => { refreshAutoStatus(); }, 8000);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    if (!autoOpen) return;
    const t = setInterval(() => { loadAuto().catch(() => {}); }, 4000);
    return () => clearInterval(t);
  }, [autoOpen]);

  const openAuto = async () => { await loadAuto().catch(() => {}); setAutoOpen(true); };
  const searchShows = q => {
    clearTimeout(showSearchTimer.current);
    const kw = (q || '').trim();
    if (kw.length < 2) { setShowOptions([]); setShowSearching(false); return; }
    setShowSearching(true);
    showSearchTimer.current = setTimeout(async () => {
      try {
        const r = await api('/api/tmdb/search?q=' + encodeURIComponent(kw));
        setShowOptions((r.results || []).map(x => ({ value: `${x.media_type || 'tv'}:${x.tmdb_id}`, label: `${x.name}${x.year ? ' (' + x.year + ')' : ''} · ${x.media_type === 'movie' ? '电影' : '剧集'}`, item: x })));
      } finally { setShowSearching(false); }
    }, 400);
  };
  const addShowOption = (value, label) => {
    const [mt, id] = String(value).split(':');
    const name = (label || '').replace(/\s*·\s*(电影|剧集)\s*$/, '').replace(/\s*\(\d{4}\)\s*$/, '');
    const next = autoShows
      .filter(x => !(String(x.tmdb_id) === String(id) && (x.media_type || 'tv') === mt))
      .concat([{ tmdb_id: Number(id), title: name, media_type: mt || 'tv' }]);
    setAutoShows(next);
  };
  const runItem = async (it, dry) => {
    const r = await api('/api/auto/run', { method: 'POST', body: { dry_run: !!dry, show: { tmdb_id: it.tmdb_id, media_type: it.media_type || 'tv' } } });
    if (!r.ok) { message.warning(r.error || '启动失败'); return; }
    message.info(dry ? '已开始预览该条目（不转存）' : '已开始检查该条目');
    setTimeout(() => refreshAutoStatus(), 800);
  };
  const loadDone = async () => {
    const r = await api('/api/auto/done');
    setDoneItems(r.items || []);
    const st = await api('/api/auto/status');
    setPendingItems(st.pending || []);
  };
  const openDone = async () => { await loadDone(); setDoneOpen(true); };
  const deleteDone = async key => {
    await api('/api/auto/done/remove', { method: 'POST', body: { keys: [key] } });
    message.success('已移除记录');
    loadDone();
  };
  const clearDone = async () => {
    await api('/api/auto/done/clear', { method: 'POST', body: {} });
    setDoneItems([]);
    message.success('已完成记录已清空');
    refreshAutoStatus();
  };
  const clearLogs = async () => {
    await api('/api/auto/logs/clear', { method: 'POST', body: {} });
    message.success('日志已清空');
    refreshAutoStatus();
  };
  const runAll = async () => {
    const r = await api('/api/auto/run', { method: 'POST', body: { dry_run: false } });
    if (!r.ok) { message.warning(r.error || '启动失败'); return; }
    message.info('已开始检查全部条目');
    setTimeout(() => refreshAutoStatus(), 800);
  };
  const openPresets = async () => { await loadAuto().catch(() => {}); setPresetListOpen(true); };

  const addShow = async () => {
    const id = addShowId.trim();
    if (!id) return;
    const r = await api('/api/tmdb/tv?id=' + encodeURIComponent(id));
    if (!r.ok) { message.error(r.error || '添加失败'); return; }
    const next = autoShows.filter(x => String(x.tmdb_id) !== String(r.tmdb_id)).concat([{ tmdb_id: r.tmdb_id, title: r.name }]);
    setAutoShows(next); setAddShowId('');
  };
  const newPreset = type => {
    setPresetDraft({
      id: 'p' + Date.now(), name: '', media_type: type, res_order: ['2160p', '1080p', '720p'],
      codec: '', max_size_gb: 0, min_seeders: 1, strict_match: true, days: type === 'tv' ? 2 : undefined,
      ai_enabled: false, ai_base_url: 'https://api.openai.com/v1', ai_model: 'gpt-4o-mini', ai_api_key: '',
      trakt_client_id: '', trakt_token: '', calendar_source: calendarSource, interval: autoForm.interval,
      rank_order: ['shares', 'seeders', 'resolution', 'size', 'codec'], seed_tiers_text: '10,100,1000,10000', size_big: true, source_order: [], wait_timeout: undefined, use_local: false, _new: true,
    });
    setPresetOpen(true);
  };
  const editPreset = async p => {
    const draft = { ...p, _new: false, ai_enabled: !!p.ai_enabled, ai_base_url: p.ai_base_url || 'https://api.openai.com/v1', ai_model: p.ai_model || 'gpt-4o-mini', ai_api_key: '', trakt_client_id: p.trakt_client_id || '', trakt_token: '' };
    setPresetDraft(draft); setPresetOpen(true);
    try {
      const [ai, tr] = await Promise.all([
        api('/api/secrets?name=preset_ai&id=' + encodeURIComponent(p.id)),
        api('/api/secrets?name=preset_trakt&id=' + encodeURIComponent(p.id)),
      ]);
      setPresetDraft(d => d ? { ...d, ai_api_key: ai.value || '', trakt_token: tr.value || '' } : d);
    } catch (e) { /* ignore */ }
  };
  const persistAiPresets = async list => {
    const r = await api('/api/config', { method: 'POST', body: { ai_presets: list, calendar_source: calendarSource } });
    setCfg(r);
  };
  const newAiPreset = () => {
    setAiPresetDraft({ id: 'a' + Date.now(), name: '', base_url: 'https://api.openai.com/v1', model: 'gpt-4o-mini', api_key: '', _new: true });
    setAiPresetOpen(true);
  };
  const editAiPreset = async p => {
    setAiPresetDraft({ ...p, api_key: '', _new: false });
    setAiPresetOpen(true);
    try {
      const r = await api('/api/secrets?name=ai_preset&id=' + encodeURIComponent(p.id));
      setAiPresetDraft(d => d ? { ...d, api_key: r.value || '' } : d);
    } catch (e) { /* ignore */ }
  };
  const saveAiPreset = async () => {
    if (!aiPresetDraft?.name?.trim()) { message.error('请填写 AI 预设名称'); return; }
    const { _new, has_key, ...p } = aiPresetDraft;
    const list = _new ? [...aiPresets, p] : aiPresets.map(x => x.id === p.id ? p : x);
    setAiPresets(list);
    setAiPresetOpen(false); setAiPresetDraft(null);
    await persistAiPresets(list);
    message.success('AI 预设已保存');
  };
  const testAiPreset = async () => {
    if (!aiPresetDraft) return;
    setAiTesting(true);
    try {
      const r = await api('/api/ai/test', { method: 'POST', body: {
        id: aiPresetDraft.id, base_url: aiPresetDraft.base_url, model: aiPresetDraft.model, api_key: aiPresetDraft.api_key || '',
      } });
      if (r.ok) message.success('AI 连接正常：' + (r.reply ? '回复「' + r.reply + '」' : r.model));
      else message.error(r.error || '测试失败');
    } catch (e) { message.error(e.message); }
    finally { setAiTesting(false); }
  };
  const fetchAiModels = async () => {
    if (!aiPresetDraft) return;
    setAiModelsLoading(true);
    try {
      const r = await api('/api/ai/models', { method: 'POST', body: {
        id: aiPresetDraft.id, base_url: aiPresetDraft.base_url, api_key: aiPresetDraft.api_key || '',
      } });
      if (r.ok) {
        setAiModels(r.models || []);
        message.success(`拉取到 ${(r.models || []).length} 个模型`);
      } else message.error(r.error || '拉取失败');
    } catch (e) { message.error(e.message); }
    finally { setAiModelsLoading(false); }
  };
  const deleteAiPreset = async id => {
    const list = aiPresets.filter(x => x.id !== id);
    setAiPresets(list);
    await persistAiPresets(list);
    message.success('AI 预设已删除');
  };
  const saveCalendarSource = async v => {
    setCalendarSource(v);
    const r = await api('/api/config', { method: 'POST', body: { calendar_source: v } });
    setCfg(r);
  };
  const startTraktOauth = async () => {
    if (!autoForm.traktClientId.trim()) { message.error('请先填写 Trakt Client ID'); return; }
    const r = await api('/api/trakt/oauth/start', { method: 'POST', body: { client_id: autoForm.traktClientId.trim() } });
    if (!r.ok) { message.error(r.error || '启动授权失败'); return; }
    setTraktAuthUrl(r.auth_url);
    setTraktRedirectUri(r.redirect_uri);
    setTraktOauthOpen(true);
    window.open(r.auth_url, '_blank');
  };
  useEffect(() => {
    if (!traktOauthOpen) return;
    const t = setInterval(async () => {
      try {
        const r = await api('/api/trakt/oauth/status');
        if (r.has_token) {
          clearInterval(t);
          setTraktOauthOpen(false);
          message.success('Trakt 授权成功');
          await loadAuto().catch(() => {});
          revealTrakt();
        } else if (r.last_error) {
          setTraktOauthError(r.last_error);
        }
      } catch (e) { /* ignore */ }
    }, 2500);
    return () => clearInterval(t);
  }, [traktOauthOpen]);

  const saveInterval = async v => {
    const val = Math.max(5, v || 180);
    setAutoForm(f => ({ ...f, interval: val }));
    const r = await api('/api/config', { method: 'POST', body: { auto_interval: val } });
    setCfg(r);
  };

  const persistPresets = async list => {
    const r = await api('/api/config', { method: 'POST', body: { auto_presets: list, auto_tv_preset: tvPreset, auto_movie_preset: moviePreset } });
    setCfg(r);
  };
  const deletePreset = async id => {
    const list = presets.filter(x => x.id !== id);
    setPresets(list);
    if (tvPreset === id) setTvPreset('');
    if (moviePreset === id) setMoviePreset('');
    await persistPresets(list);
    message.success('预设已删除');
  };
  const savePreset = async () => {
    if (!presetDraft?.name?.trim()) { message.error('请填写预设名称'); return; }
    const { _new, has_ai, has_trakt, seed_tiers_text, ...rest } = presetDraft;
    const p = { ...rest, seed_tiers: String(seed_tiers_text || '10,100,1000,10000').split(',').map(x => parseInt(x, 10)).filter(x => x > 0) };
    const list = _new ? [...presets, p] : presets.map(x => x.id === p.id ? p : x);
    setPresets(list);
    setPresetOpen(null); setPresetDraft(null);
    await persistPresets(list);
    message.success('预设已保存');
  };

  const saveAuto = async () => {
    const body = {
      auto_enabled: autoForm.enabled, auto_interval: autoForm.interval, auto_days: autoForm.days,
      auto_dry_run: autoForm.dryRun, auto_max_size_gb: autoForm.maxSize, auto_min_seeders: autoForm.minSeeds, auto_strict_match: autoForm.strict,
      auto_res_order: autoForm.resOrder, auto_codec: autoForm.codec, auto_shows: autoShows,
      ai_enabled: autoForm.aiEnabled, ai_base_url: autoForm.aiBase, ai_model: autoForm.aiModel,
      trakt_client_id: autoForm.traktClientId, auto_presets: presets,
      ai_presets: aiPresets, calendar_source: calendarSource, auto_max_episodes: maxEpisodes, auto_task_timeout: taskTimeout, auto_wait_timeout: waitTimeout, drivemby_enabled: drivembyEnabled,
      auto_rank_order: rankOrder, auto_seed_tiers: seedTiers.split(',').map(x => parseInt(x, 10)).filter(x => x > 0),
      auto_tv_preset: tvPreset, auto_movie_preset: moviePreset,
    };
    if (aiKey) body.ai_api_key = aiKey;
    if (traktToken) body.trakt_token = traktToken;
    const r = await api('/api/config', { method: 'POST', body });
    setCfg(r); setAiKey(''); setTraktToken('');
    message.success('追剧设置已保存'); loadAuto().catch(() => {});
  };
  const runAuto = async dryRun => {
    const r = await api('/api/auto/run', { method: 'POST', body: { dry_run: !!dryRun } });
    if (!r.ok) { message.warning(r.error || '启动失败'); return; }
    message.info(dryRun ? '已开始预览（只匹配，不转存）' : '已开始自动转存');
    setTimeout(() => refreshAutoStatus(), 1000);
  };
  const revealAi = async () => {
    if (aiKey) { setAiKey(''); return; }
    const r = await api('/api/secrets?name=ai'); setAiKey(r.value || '');
  };
  const revealTrakt = async () => {
    if (traktToken) { setTraktToken(''); return; }
    const r = await api('/api/secrets?name=trakt'); setTraktToken(r.value || '');
  };

  const saveShowsList = async list => {
    const r = await api('/api/config', { method: 'POST', body: { auto_shows: list } });
    setCfg(r); setAutoShows(list);
    const d = await api('/api/auto/status'); setAuto(d);
  };
  const addSearchResult = opt => {
    const it = opt.item || {};
    const draft = { tmdb_id: it.tmdb_id, title: it.name, media_type: it.media_type || 'tv', year: it.year || '', poster_path: it.poster_path || '', enabled: true, _new: true };
    setEditItem(draft);
    setEditTitle(draft.title);
    const firstPreset = presets.find(p => (p.media_type || 'tv') === (draft.media_type || 'tv'));
    setEditForm({ preset_id: firstPreset ? firstPreset.id : '' });
    setAddOpen(false); setAddQuery(''); setShowOptions([]);
  };
  const openEditItem = it => {
    setEditItem(it);
    setEditTitle(it.title || '');
    setEditForm({
      enabled: it.enabled !== false,
      res_order: it.res_order || [],
      codec: it.codec || '',
      max_size_gb: it.max_size_gb,
      min_seeders: it.min_seeders,
      strict_match: it.strict_match,
      ai_rank: it.ai_rank,
      days: it.days,
      preset_id: it.preset_id || '',
    });
  };
  const saveEditItem = async () => {
    const item = {
      ...editItem,
      title: editTitle,
      enabled: editForm.enabled !== false,
      res_order: editForm.res_order && editForm.res_order.length ? editForm.res_order : undefined,
      codec: editForm.codec || undefined,
      max_size_gb: editForm.max_size_gb === '' || editForm.max_size_gb == null ? undefined : editForm.max_size_gb,
      min_seeders: editForm.min_seeders === '' || editForm.min_seeders == null ? undefined : editForm.min_seeders,
      strict_match: editForm.strict_match,
      ai_rank: editForm.ai_rank,
      days: editForm.days === '' || editForm.days == null ? undefined : editForm.days,
      preset_id: editForm.preset_id || undefined,
    };
    delete item._new;
    const exists = autoShows.some(x => String(x.tmdb_id) === String(item.tmdb_id) && (x.media_type || 'tv') === (item.media_type || 'tv'));
    const list = exists
      ? autoShows.map(x => (String(x.tmdb_id) === String(item.tmdb_id) && (x.media_type || 'tv') === (item.media_type || 'tv')) ? item : x)
      : [...autoShows, item];
    await saveShowsList(list);
    setAutoTab(item.media_type || 'tv');
    setEditItem(null); message.success(exists ? '已保存' : '已加入列表');
  };
  const removeItem = async () => {
    if (editItem._new) { setEditItem(null); return; }
    const list = autoShows.filter(x => !(String(x.tmdb_id) === String(editItem.tmdb_id) && (x.media_type || 'tv') === (editItem.media_type || 'tv')));
    await saveShowsList(list);
    setEditItem(null); message.success('已移除');
  };
  const toggleItem = async it => {
    const list = autoShows.map(x => (x.tmdb_id === it.tmdb_id && (x.media_type || 'tv') === (it.media_type || 'tv')) ? { ...x, enabled: x.enabled === false } : x);
    await saveShowsList(list);
  };


  return {
    autoForm,
    rankOrder,
    setRankOrder,
    seedTiers,
    setSeedTiers,
    setAutoForm,
    autoOpen,
    presetListOpen,
    presetTab,
    logsOpen,
    doneOpen,
    doneItems,
    pendingItems,
    autoTab,
    addOpen,
    addQuery,
    editItem,
    editTitle,
    editForm,
    auto,
    autoShows,
    addShowId,
    showOptions,
    showSearching,
    aiKey,
    traktToken,
    presets,
    aiPresets,
    aiPresetOpen,
    aiPresetDraft,
    aiTesting,
    aiModels,
    aiModelsLoading,
    calendarSource,
    maxEpisodes,
    taskTimeout,
    waitTimeout,
    drivembyEnabled,
    traktOauthOpen,
    traktAuthUrl,
    traktRedirectUri,
    traktOauthError,
    tvPreset,
    moviePreset,
    presetOpen,
    presetDraft,
    setAutoOpen,
    setPresetListOpen,
    setPresetTab,
    setLogsOpen,
    setDoneOpen,
    setDoneItems,
    setPendingItems,
    setAutoTab,
    setAddOpen,
    setAddQuery,
    setEditItem,
    setEditTitle,
    setEditForm,
    setAuto,
    setAutoShows,
    setAddShowId,
    setShowOptions,
    setShowSearching,
    setAiKey,
    setTraktToken,
    setPresets,
    setAiPresets,
    setAiPresetOpen,
    setAiPresetDraft,
    setAiTesting,
    setAiModels,
    setAiModelsLoading,
    setCalendarSource,
    setMaxEpisodes,
    setTaskTimeout,
    setWaitTimeout,
    setDrivembyEnabled,
    setTraktOauthOpen,
    setTraktAuthUrl,
    setTraktRedirectUri,
    setTraktOauthError,
    setTvPreset,
    setMoviePreset,
    setPresetOpen,
    setPresetDraft,
    loadAuto,
    refreshAutoStatus,
    openAuto,
    addShowOption,
    runItem,
    loadDone,
    openDone,
    clearDone,
    clearLogs,
    runAll,
    openPresets,
    addShow,
    newAiPreset,
    saveAiPreset,
    testAiPreset,
    fetchAiModels,
    startTraktOauth,
    savePreset,
    saveAuto,
    revealAi,
    revealTrakt,
    saveEditItem,
    removeItem,
    searchShows,
    deleteDone,
    newPreset,
    editPreset,
    persistAiPresets,
    editAiPreset,
    deleteAiPreset,
    saveCalendarSource,
    saveInterval,
    persistPresets,
    deletePreset,
    runAuto,
    saveShowsList,
    addSearchResult,
    openEditItem,
    toggleItem,
    showSearchTimer,
  };
}
