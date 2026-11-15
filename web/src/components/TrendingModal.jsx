import React, { useEffect, useState } from 'react';
import { Button, Empty, Modal, Spin, Tabs, Tag, theme, Tooltip } from 'antd';
import { api, posterUrl } from '../api.js';

export default function TrendingModal({ open, onClose, track, onDirectSearch, inline }) {
  const { token } = theme.useToken();
  const [items, setItems] = useState([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [tab, setTab] = useState('movie');

  useEffect(() => {
    if (!open || items.length) return;
    setLoading(true);
    api('/api/tmdb/trending?page=1')
      .then(r => { setItems(r.results || []); setPage(1); setHasMore(!!r.has_more); })
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [open]);

  const loadMore = async () => {
    if (loadingMore) return;
    setLoadingMore(true);
    try {
      const r = await api('/api/tmdb/trending?page=' + (page + 1));
      setItems(prev => {
        const seen = new Set(prev.map(x => x.media_type + x.tmdb_id));
        return prev.concat((r.results || []).filter(x => !seen.has(x.media_type + x.tmdb_id)));
      });
      setPage(r.page || page + 1);
      setHasMore(!!r.has_more);
    } catch (e) { /* ignore */ }
    setLoadingMore(false);
  };

  const list = items.filter(x => x.media_type === tab);
  const add = it => {
    track.addSearchResult({ item: it });
    track.openAuto();
    onClose();
  };

  const body = (
    <>
      <Tabs
        activeKey={tab}
        onChange={setTab}
        items={[
          { key: 'movie', label: `电影 ${items.filter(x => x.media_type === 'movie').length}` },
          { key: 'tv', label: `剧集 ${items.filter(x => x.media_type === 'tv').length}` },
        ]}
      />
      {loading ? (
        <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
      ) : !list.length ? (
        <Empty description="暂无数据，检查 TMDB 配置或代理" />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 12, maxHeight: inline ? 'none' : '60vh', overflow: inline ? 'visible' : 'auto', padding: 4 }}>
          {list.map(it => (
            <div key={it.media_type + it.tmdb_id} style={{ border: `1px solid ${token.colorBorderSecondary}`, borderRadius: 10, overflow: 'hidden', background: token.colorBgContainer }}>
              <div style={{ aspectRatio: '2/3', background: token.colorFillTertiary }}>
                {it.poster_path ? <img src={posterUrl(it.poster_path)} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} loading="lazy" /> : null}
              </div>
              <div style={{ padding: 8 }}>
                <Tooltip title={it.overview || it.name}>
                  <div style={{ fontSize: 13, fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{it.name}</div>
                </Tooltip>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 2 }}>
                  <span style={{ fontSize: 12, color: token.colorTextSecondary }}>{it.year || '—'}</span>
                  <Tag bordered={false} color={it.media_type === 'movie' ? 'gold' : 'blue'} style={{ marginInlineEnd: 0 }}>
                    {it.media_type === 'movie' ? '电影' : '剧集'}
                  </Tag>
                </div>
                <Button size="small" type="primary" block style={{ marginTop: 6 }} onClick={() => add(it)}>
                  {it.media_type === 'movie' ? '加入想看电影' : '加入追剧'}
                </Button>
                <Button size="small" block style={{ marginTop: 4 }} onClick={() => { onDirectSearch(it.media_type === 'movie' && it.year ? `${it.name} ${it.year}` : it.name); onClose(); }}>
                  直接搜索
                </Button>
              </div>
            </div>
          ))}
          {hasMore ? (
            <div style={{ gridColumn: '1 / -1', textAlign: 'center', marginTop: 12 }}>
              <Button loading={loadingMore} onClick={loadMore}>加载更多</Button>
            </div>
          ) : null}
        </div>
      )}
    </>
  );
  if (inline) {
    return (
      <div style={{ height: '100%', overflow: 'auto', padding: '12px 20px 20px' }}>
        <div style={{ fontSize: 17, fontWeight: 600, marginBottom: 12 }}>TMDB 最近热映</div>
        {body}
      </div>
    );
  }
  return (
    <Modal open={open} onCancel={onClose} footer={null} width={920} title="TMDB 最近热映">
      {body}
    </Modal>
  );
}
