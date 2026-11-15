import React, { useEffect, useRef } from 'react';
import * as Antd from 'antd';
import { CheckCircleOutlined, PlusOutlined, SettingOutlined, SyncOutlined } from '@ant-design/icons';
import { posterUrl } from '../api.js';
import { fmtTime } from '../lib/format.js';

const { Alert, Button, Col, Collapse, Divider, Empty, Flex, Form, Input, InputNumber, Modal, Row, Select, Space, Spin, Switch, Tabs, Tag, Typography } = Antd;

export default function TrackingModals(p) {
  const {
    addOpen,
    addQuery,
    addSearchResult,
    aiPresets,
    auto,
    autoOpen,
    autoShows,
    autoTab,
    calendarSource,
    cfg,
    clearDone,
    clearLogs,
    deleteDone,
    doneItems,
    doneOpen,
    editForm,
    editItem,
    editPreset,
    editTitle,
    newPreset,
    openDone,
    openEditItem,
    openPresets,
    pendingItems,
    presetDraft,
    presetListOpen,
    presetOpen,
    presetTab,
    presets,
    refreshAutoStatus,
    removeItem,
    runAll,
    runItem,
    saveEditItem,
    savePreset,
    searchShows,
    setAddOpen,
    setAddQuery,
    setAutoOpen,
    setAutoTab,
    setDoneOpen,
    setEditForm,
    setEditItem,
    setEditTitle,
    setPresetDraft,
    setPresetListOpen,
    setPresetOpen,
    setPresetTab,
    setShowOptions,
    setTraktOauthOpen,
    showOptions,
    showSearching,
    traktAuthUrl,
    traktOauthError,
    traktOauthOpen,
    traktRedirectUri,
    token,
  } = p;
  const logRef = useRef(null);
  const logCount = (auto?.log || []).length;
  const setLogRef = node => {
    logRef.current = node;
    if (node) node.scrollTop = node.scrollHeight;
  };
  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [logCount]);
  return (
    <>
            <Modal
              open={autoOpen}
              onCancel={() => setAutoOpen(false)}
              title="追剧 / 想看电影"
              width={920}
              footer={null}
            >
              <Flex justify="space-between" align="center" wrap="wrap" gap={8} style={{ marginBottom: 12 }}>
                <Tabs
                  activeKey={autoTab}
                  onChange={setAutoTab}
                  items={[
                    { key: 'tv', label: `剧集 ${autoShows.filter(x => (x.media_type || 'tv') === 'tv').length}` },
                    { key: 'movie', label: `电影 ${autoShows.filter(x => x.media_type === 'movie').length}` },
                  ]}
                  style={{ marginBottom: 0 }}
                />
                <Space wrap>
                  <Button type="primary" icon={<PlusOutlined />} onClick={() => setAddOpen(true)}>添加</Button>
                  <Button icon={<SettingOutlined />} onClick={openPresets}>预设</Button>
                  <Button icon={<SyncOutlined />} onClick={runAll}>检查全部</Button>
                  <Button icon={<CheckCircleOutlined />} onClick={openDone}>已完成</Button>
                </Space>
              </Flex>
              <div style={{ maxHeight: '54vh', overflow: 'auto', padding: 4 }}>
                {['tv', 'movie'].map(tab => {
                  const list = autoShows.filter(x => (x.media_type || 'tv') === tab);
                  return (
                    <div key={tab} style={{ display: autoTab === tab ? 'grid' : 'none', gridTemplateColumns: 'repeat(auto-fill,minmax(130px,1fr))', gap: 16 }}>
                      {list.length ? list.map(it => (
                        <div
                          key={(it.media_type || 'tv') + '-' + it.tmdb_id}
                          className="poster-card"
                          onClick={() => openEditItem(it)}
                          style={{ cursor: 'pointer', opacity: it.enabled === false ? 0.45 : 1, position: 'relative' }}
                        >
                          <div style={{ position: 'relative', aspectRatio: '2 / 3', borderRadius: 8, overflow: 'hidden', background: token.colorFillTertiary }}>
                            {it.poster_path ? <img src={posterUrl(it.poster_path)} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : (
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: token.colorTextTertiary, fontSize: 12 }}>无封面</div>
                            )}
                            <Tag style={{ position: 'absolute', top: 6, left: 6, margin: 0 }} color={it.media_type === 'movie' ? 'gold' : 'blue'} bordered={false}>
                              {it.media_type === 'movie' ? '电影' : '剧集'}
                            </Tag>
                            {it.enabled === false ? <Tag style={{ position: 'absolute', top: 6, right: 6, margin: 0 }} bordered={false}>停用</Tag> : null}
                            <div className="poster-actions" onClick={e => e.stopPropagation()}>
                              <Button size="small" block onClick={() => runItem(it, true)}>预览</Button>
                              <Button size="small" block type="primary" onClick={() => runItem(it, false)}>立即检查</Button>
                            </div>
                            <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, padding: '24px 8px 6px', background: 'linear-gradient(transparent, rgba(0,0,0,.78))', color: '#fff', pointerEvents: 'none' }}>
                              <div style={{ fontSize: 12, fontWeight: 600, lineHeight: 1.3, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{it.title || it.tmdb_id}</div>
                              <div style={{ fontSize: 11, opacity: 0.8 }}>{it.year || ''}</div>
                            </div>
                          </div>
                        </div>
                      )) : <Empty style={{ gridColumn: '1 / -1' }} description="还没有内容，点击右上角「添加」" />}
                    </div>
                  );
                })}
              </div>
              <Collapse
                size="small"
                style={{ marginTop: 12 }}
                onChange={() => refreshAutoStatus()}
                items={[{
                  key: 'log',
                  label: (
                    <Flex justify="space-between" align="center">
                      <span>任务日志（上次运行：{auto?.last_run ? fmtTime(auto.last_run) : '从未'}）</span>
                      <Button size="small" type="text" onClick={e => { e.stopPropagation(); clearLogs(); }}>清空</Button>
                    </Flex>
                  ),
                  children: (
                    <div ref={setLogRef} style={{ maxHeight: 220, overflow: 'auto', fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 12 }}>
                      {(auto?.log || []).slice(-100).map((l, i) => (
                        <div key={i} style={{ padding: '2px 0' }}>{fmtTime(l.ts)} {l.msg}</div>
                      ))}
                      {!(auto?.log || []).length ? <Typography.Text type="secondary">暂无日志</Typography.Text> : null}
                    </div>
                  ),
                }]}
              />
            </Modal>
      
            <Modal
              open={addOpen}
              title="添加剧集 / 电影"
              width={620}
              footer={null}
              onCancel={() => { setAddOpen(false); setAddQuery(''); setShowOptions([]); }}
            >
              <Input
                size="large"
                allowClear
                value={addQuery}
                placeholder="输入剧名或电影名（至少 2 个字符）搜索 TMDB…"
                onChange={e => { setAddQuery(e.target.value); searchShows(e.target.value); }}
              />
              <div style={{ maxHeight: 420, overflow: 'auto', marginTop: 12 }}>
                {showOptions.map(o => (
                  <Flex
                    key={o.value}
                    align="center"
                    gap={12}
                    onClick={() => addSearchResult(o)}
                    style={{ padding: 8, cursor: 'pointer', borderBottom: `1px solid ${token.colorBorderSecondary}` }}
                  >
                    <div style={{ width: 46, height: 69, borderRadius: 6, overflow: 'hidden', background: token.colorFillTertiary, flex: '0 0 auto' }}>
                      {o.item?.poster_path ? <img src={posterUrl(o.item.poster_path)} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : null}
                    </div>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 600 }}>{o.item?.name}</div>
                      <Space size={6}>
                        <Tag bordered={false} color={o.item?.media_type === 'movie' ? 'gold' : 'blue'}>{o.item?.media_type === 'movie' ? '电影' : '剧集'}</Tag>
                        <Typography.Text type="secondary">{o.item?.year || ''}</Typography.Text>
                      </Space>
                    </div>
                  </Flex>
                ))}
                {showSearching ? <div style={{ padding: 16, textAlign: 'center' }}><Spin /></div> : null}
                {!showSearching && addQuery && !showOptions.length ? <Empty description="没有找到" /> : null}
              </div>
            </Modal>
      
            <Modal
              open={!!editItem}
              onCancel={() => setEditItem(null)}
              title={editItem?._new ? '加入追剧 / 想看电影' : '编辑'}
              width={600}
              footer={
                <Flex justify="space-between">
                  {editItem?._new ? <span /> : <Button danger onClick={removeItem}>移除</Button>}
                  <Space>
                    <Button onClick={() => setEditItem(null)}>取消</Button>
                    <Button type="primary" onClick={saveEditItem}>保存</Button>
                  </Space>
                </Flex>
              }
            >
              {editItem ? (
                <Flex gap={16} align="flex-start">
                  <div style={{ width: 110, height: 165, borderRadius: 8, overflow: 'hidden', background: token.colorFillTertiary, flex: '0 0 auto' }}>
                    {editItem.poster_path ? <img src={posterUrl(editItem.poster_path)} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : null}
                  </div>
                  <div style={{ flex: 1, maxHeight: '62vh', overflowY: 'auto', overflowX: 'hidden', paddingRight: 4 }}>
                    <Form layout="vertical" size="small">
                      <Form.Item label="名称"><Input value={editTitle} onChange={e => setEditTitle(e.target.value)} /></Form.Item>
                      <Form.Item label="类型">
                        <Space>
                          <Tag bordered={false} color={editItem.media_type === 'movie' ? 'gold' : 'blue'}>{editItem.media_type === 'movie' ? '电影' : '剧集'}</Tag>
                          <Typography.Text type="secondary">TMDB ID：{editItem.tmdb_id}</Typography.Text>
                        </Space>
                      </Form.Item>
                      <Form.Item label="启用自动检查">
                        <Switch checked={editForm.enabled !== false} onChange={v => setEditForm({ ...editForm, enabled: v })} />
                      </Form.Item>
                      <Form.Item label="使用的预设">
                        <Select
                          allowClear
                          value={editForm.preset_id || undefined}
                          placeholder="默认设置"
                          onChange={v => setEditForm({ ...editForm, preset_id: v || '' })}
                          options={presets.filter(p => (p.media_type || 'tv') === (editItem.media_type || 'tv')).map(p => ({ value: p.id, label: p.name }))}
                        />
                      </Form.Item>
                      <Divider style={{ margin: '4px 0 12px' }}>单独设置（留空/跟随全局）</Divider>
                      <Row gutter={12}>
                        <Col span={12}>
                          <Form.Item label="清晰度优先级">
                            <Select mode="tags" allowClear value={editForm.res_order || []} placeholder="跟随全局"
                              onChange={v => setEditForm({ ...editForm, res_order: v })}
                              options={['2160p', '1080p', '720p', '480p'].map(v => ({ value: v, label: v }))} />
                          </Form.Item>
                        </Col>
                        <Col span={12}>
                          <Form.Item label="编码偏好">
                            <Select allowClear value={editForm.codec || undefined} placeholder="跟随全局"
                              onChange={v => setEditForm({ ...editForm, codec: v || '' })}
                              options={['x265', 'HEVC', 'x264', 'H264'].map(v => ({ value: v, label: v }))} />
                          </Form.Item>
                        </Col>
                        <Col span={12}>
                          <Form.Item label="最大体积（GB，0=不限）">
                            <InputNumber min={0} value={editForm.max_size_gb} placeholder="跟随全局" style={{ width: '100%' }}
                              onChange={v => setEditForm({ ...editForm, max_size_gb: v })} />
                          </Form.Item>
                        </Col>
                        <Col span={12}>
                          <Form.Item label="最小种子数">
                            <InputNumber min={0} value={editForm.min_seeders} placeholder="跟随全局" style={{ width: '100%' }}
                              onChange={v => setEditForm({ ...editForm, min_seeders: v })} />
                          </Form.Item>
                        </Col>
                        <Col span={12}>
                          <Form.Item label="严格匹配">
                            <Select allowClear value={editForm.strict_match === undefined ? undefined : editForm.strict_match} placeholder="跟随全局"
                              onChange={v => setEditForm({ ...editForm, strict_match: v })}
                              options={[{ value: true, label: '开启' }, { value: false, label: '关闭' }]} />
                          </Form.Item>
                        </Col>
                        <Col span={12}>
                          <Form.Item label="AI 选种">
                            <Select allowClear value={editForm.ai_rank === undefined ? undefined : editForm.ai_rank} placeholder="跟随全局"
                              onChange={v => setEditForm({ ...editForm, ai_rank: v })}
                              options={[{ value: true, label: '开启' }, { value: false, label: '关闭' }]} />
                          </Form.Item>
                        </Col>
                        {editItem.media_type !== 'movie' ? (
                          <Col span={12}>
                            <Form.Item label="检索最近几天播出">
                              <InputNumber min={1} max={30} value={editForm.days} placeholder="跟随全局" style={{ width: '100%' }}
                                onChange={v => setEditForm({ ...editForm, days: v })} />
                            </Form.Item>
                          </Col>
                        ) : null}
                      </Row>
                    </Form>
                  </div>
                </Flex>
              ) : null}
            </Modal>
      
            <Modal
              open={!!presetOpen}
              title={presetDraft?._new ? '新建预设' : '编辑预设'}
              width={720}
              onCancel={() => { setPresetOpen(null); setPresetDraft(null); }}
              footer={<Flex justify="flex-end" gap={8}><Button onClick={() => { setPresetOpen(null); setPresetDraft(null); }}>取消</Button><Button type="primary" onClick={savePreset}>保存</Button></Flex>}
            >
              {presetDraft ? (
                <Form layout="vertical">
                  <Typography.Title level={5} style={{ marginTop: 0 }}>基本信息</Typography.Title>
                  <Row gutter={12}>
                    <Col span={12}><Form.Item label="名称"><Input value={presetDraft.name} onChange={e => setPresetDraft({ ...presetDraft, name: e.target.value })} placeholder="如：4K 洗版 / 小体积" /></Form.Item></Col>
                    <Col span={12}><Form.Item label="预设类型"><Select value={presetDraft.media_type} onChange={v => setPresetDraft({ ...presetDraft, media_type: v })} options={[{ value: 'tv', label: '追剧（剧集）' }, { value: 'movie', label: '追影（电影）' }]} /></Form.Item></Col>
                    <Col span={12}><Form.Item label="日历来源"><Select value={presetDraft.calendar_source || 'tmdb'} onChange={v => setPresetDraft({ ...presetDraft, calendar_source: v })} options={[{ value: 'tmdb', label: 'TMDB' }, { value: 'trakt', label: 'Trakt' }]} /></Form.Item></Col>
                    <Col span={12}><Form.Item label="刷新周期（分钟）"><InputNumber min={5} value={presetDraft.interval || 180} onChange={v => setPresetDraft({ ...presetDraft, interval: v || 180 })} style={{ width: '100%' }} /></Form.Item></Col>
                  </Row>
                  <Divider style={{ margin: '4px 0 12px' }} />
                  <Typography.Title level={5}>搜索偏好</Typography.Title>
                  <Row gutter={12}>
                    {presetDraft.media_type === 'tv' ? (
                      <Col span={12}><Form.Item label="检索最近几天播出"><InputNumber min={1} max={30} value={presetDraft.days} onChange={v => setPresetDraft({ ...presetDraft, days: v || 2 })} style={{ width: '100%' }} /></Form.Item></Col>
                    ) : null}
                    <Col span={12}><Form.Item label="最小种子数"><InputNumber min={0} value={presetDraft.min_seeders} onChange={v => setPresetDraft({ ...presetDraft, min_seeders: v || 0 })} style={{ width: '100%' }} /></Form.Item></Col>
                    <Col span={12}><Form.Item label="最大体积（GB，0=不限）"><InputNumber min={0} value={presetDraft.max_size_gb} onChange={v => setPresetDraft({ ...presetDraft, max_size_gb: v || 0 })} style={{ width: '100%' }} /></Form.Item></Col>
                    <Col span={12}><Form.Item label="编码偏好"><Select allowClear value={presetDraft.codec || undefined} onChange={v => setPresetDraft({ ...presetDraft, codec: v || '' })} options={['x265', 'HEVC', 'x264', 'H264'].map(v => ({ value: v, label: v }))} placeholder="不限" style={{ width: '100%' }} /></Form.Item></Col>
                    <Col span={12}><Form.Item label="严格匹配"><Select allowClear value={presetDraft.strict_match} onChange={v => setPresetDraft({ ...presetDraft, strict_match: v })} options={[{ value: true, label: '开启' }, { value: false, label: '关闭' }]} placeholder="默认" style={{ width: '100%' }} /></Form.Item></Col>
                    <Col span={12}><Form.Item label="启用 AI 选种"><Switch checked={!!presetDraft.ai_enabled} onChange={v => setPresetDraft({ ...presetDraft, ai_enabled: v })} /></Form.Item></Col>
                    <Col span={12}><Form.Item label="AI 预设"><Select allowClear value={presetDraft.ai_preset_id || undefined} onChange={v => setPresetDraft({ ...presetDraft, ai_preset_id: v || '' })} options={aiPresets.map(a => ({ value: a.id, label: a.name + ' · ' + (a.model || '') }))} placeholder="选择 AI 预设" style={{ width: '100%' }} /></Form.Item></Col>
                    <Col span={24}><Form.Item label="清晰度优先级"><Select mode="tags" value={presetDraft.res_order || []} onChange={v => setPresetDraft({ ...presetDraft, res_order: v })} options={['2160p', '1080p', '720p', '480p'].map(v => ({ value: v, label: v }))} /></Form.Item></Col>
<Col span={12}><Form.Item label="体积偏好（大优先）"><Switch checked={presetDraft.size_big !== false} onChange={v => setPresetDraft({ ...presetDraft, size_big: v })} /></Form.Item></Col>
                    <Col span={12}><Form.Item label="种子分档（同档视为差不多）"><Input value={presetDraft.seed_tiers_text || ''} onChange={e => setPresetDraft({ ...presetDraft, seed_tiers_text: e.target.value })} placeholder="10,100,1000,10000" /></Form.Item></Col>
                    <Col span={24}><Form.Item label="选种排序优先级（按顺序从高到低）">
                      <Select mode="multiple" value={presetDraft.rank_order || ['shares', 'seeders', 'resolution', 'size', 'codec']}
                        onChange={v => setPresetDraft({ ...presetDraft, rank_order: v })}
                        options={[
                          { value: 'shares', label: '115 分享优先' },
                          { value: 'seeders', label: '种子数' },
                          { value: 'resolution', label: '清晰度' },
                          { value: 'size', label: '体积' },
                          { value: 'codec', label: '编码偏好' },
                        ]} />
                    </Form.Item></Col>
                    <Col span={12}><Form.Item label="同时添加本地下载器（fnOS 下载中心）">
                      <Switch checked={!!presetDraft.use_local} onChange={v => setPresetDraft({ ...presetDraft, use_local: v })} />
                    </Form.Item></Col>
                    <Col span={12}><Form.Item label="离线等待超时（分钟，留空=跟随全局）">
                      <InputNumber min={0} max={240} value={presetDraft.wait_timeout}
                        onChange={v => setPresetDraft({ ...presetDraft, wait_timeout: v })} style={{ width: '100%' }} placeholder="跟随全局" />
                    </Form.Item></Col>
                    <Col span={24}><Form.Item label="搜索源优先级（按顺序从高到低，留空=不限制）">
                      <Select mode="multiple" value={presetDraft.source_order || []}
                        onChange={v => setPresetDraft({ ...presetDraft, source_order: v })}
                        options={[
                          { value: 'pansou', label: '115 分享（PanSou）' },
                          { value: 'pansou-magnet', label: '盘搜磁力' },
                          { value: 'apibay', label: 'TPB(apibay)' },
                          { value: 'nyaa', label: 'Nyaa' },
                          { value: 'dmhy', label: '动漫花园' },
                          { value: 'btsearch', label: 'BTSearch' },
                          { value: 'eztv', label: 'EZTV' },
                          { value: 'knaben', label: 'knaben' },
                          { value: 'therarbg', label: 'therarbg' },
                          { value: 'bitmagnet', label: 'bitmagnet' },
                        ]} />
                    </Form.Item></Col>
                  </Row>
                </Form>
              ) : null}
            </Modal>
      
            <Modal
              open={doneOpen}
              onCancel={() => setDoneOpen(false)}
              title="已完成剧集"
              width={640}
              footer={<Flex justify="space-between"><Button danger onClick={clearDone}>清空全部</Button><Button onClick={() => setDoneOpen(false)}>关闭</Button></Flex>}
            >
              {pendingItems.length ? (
                <div style={{ marginBottom: 12 }}>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>下载中（下轮自动确认）</Typography.Text>
                  {pendingItems.map(it => (
                    <Flex key={it.key} justify="space-between" align="center" style={{ padding: '6px 4px', borderBottom: `1px solid ${token.colorBorderSecondary}` }}>
                      <span style={{ fontSize: 13 }}>{it.key}</span>
                      <Tag bordered={false} color="processing">下载中</Tag>
                    </Flex>
                  ))}
                </div>
              ) : null}
              <div style={{ maxHeight: '60vh', overflowY: 'auto', overflowX: 'hidden' }}>
                {doneItems.length ? doneItems.map(it => (
                  <Flex key={it.key} justify="space-between" align="center" style={{ padding: '8px 4px', borderBottom: `1px solid ${token.colorBorderSecondary}` }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{it.title} <span style={{ color: token.colorTextTertiary }}>{it.label}</span></div>
                      <div style={{ fontSize: 12, color: token.colorTextTertiary }}>
                        {it.done_at ? fmtTime(it.done_at) : ''}
                      </div>
                    </div>
                    <Button size="small" danger onClick={() => deleteDone(it.key)}>删除记录</Button>
                  </Flex>
                )) : <Empty description="还没有已完成的剧集" />}
              </div>
              <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginTop: 8, marginBottom: 0 }}>
                删除某条记录后，下次运行会重新搜索并转存对应剧集。
              </Typography.Paragraph>
            </Modal>
      
            <Modal
              open={presetListOpen}
              onCancel={() => setPresetListOpen(false)}
              title="预设"
              width={780}
              footer={null}
            >
              <Flex justify="space-between" align="center" wrap="wrap" gap={8} style={{ marginBottom: 12 }}>
                <Tabs
                  activeKey={presetTab}
                  onChange={setPresetTab}
                  items={[
                    { key: 'tv', label: '追剧预设' },
                    { key: 'movie', label: '追影预设' },
                  ]}
                  style={{ marginBottom: 0 }}
                />
                <Space>
                  <Button type="primary" icon={<PlusOutlined />} onClick={() => newPreset(presetTab)}>添加</Button>
                </Space>
              </Flex>
              {calendarSource === 'trakt' && !auto?.has_trakt ? (
                <Alert style={{ marginBottom: 12 }} type="warning" showIcon message="已选择 Trakt 日历，但 Trakt Client ID / Access Token 未配置，请到「设置 → Trakt 凭据」填写" />
              ) : null}
              {calendarSource === 'tmdb' && !cfg?.has_tmdb ? (
                <Alert style={{ marginBottom: 12 }} type="warning" showIcon message="已选择 TMDB 日历，但 TMDB API Key 未配置，请到「设置」填写" />
              ) : null}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(230px,1fr))', gap: 12, maxHeight: '60vh', overflow: 'auto' }}>
                {presets.filter(p => (p.media_type || 'tv') === presetTab).length ? presets.filter(p => (p.media_type || 'tv') === presetTab).map(p => (
                  <div
                    key={p.id}
                    onClick={() => editPreset(p)}
                    style={{ border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 10, padding: 12, cursor: 'pointer', background: token.colorBgContainer }}
                  >
                    <Flex justify="space-between" align="center">
                      <Typography.Text strong>{p.name}</Typography.Text>
                      <Tag bordered={false} color={p.media_type === 'movie' ? 'gold' : 'blue'}>{p.media_type === 'movie' ? '电影' : '剧集'}</Tag>
                    </Flex>
                    <div style={{ marginTop: 8, fontSize: 12, color: token.colorTextSecondary }}></div>
                    <div style={{ marginTop: 8, fontSize: 12, color: token.colorTextSecondary }}>
                      {(p.media_type === 'tv') ? `近 ${p.days || 2} 天 · ` : ''}
                      清晰度 {(p.res_order || []).join(' > ') || '默认'}
                    </div>
                    <div style={{ marginTop: 4, fontSize: 12, color: token.colorTextSecondary }}>
                      最小种子 {p.min_seeders ?? '默认'} · 体积 {p.max_size_gb ? p.max_size_gb + ' GB' : '不限'} · 编码 {p.codec || '不限'}
                    </div>
                  </div>
                )) : <Empty style={{ gridColumn: '1 / -1' }} description="还没有预设，点击右上角「添加」" />}
              </div>
            </Modal>
      
            <Modal
              open={traktOauthOpen}
              onCancel={() => setTraktOauthOpen(false)}
              title="Trakt 授权"
              width={560}
              footer={<Button onClick={() => setTraktOauthOpen(false)}>关闭</Button>}
            >
              <Typography.Paragraph>
                1. 在 Trakt 应用设置里把 <b>Redirect URI</b> 填为（必须完全一致）：
              </Typography.Paragraph>
              <Typography.Paragraph copyable code>{traktRedirectUri || (window.location.origin + '/api/trakt/callback')}</Typography.Paragraph>
              <Typography.Paragraph>
                2. 点击下方按钮重新打开授权页，登录并授权后本窗口会自动完成。
              </Typography.Paragraph>
              {traktOauthError ? <Alert style={{ marginBottom: 12 }} type="error" showIcon message={traktOauthError} /> : null}
              <Space>
                <Button type="primary" onClick={() => traktAuthUrl && window.open(traktAuthUrl, '_blank')}>打开授权页面</Button>
                <Typography.Text type="secondary">等待授权中…</Typography.Text>
              </Space>
            </Modal>    </>
  );
}
