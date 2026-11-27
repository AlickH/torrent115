import React, { useEffect, useState } from 'react';
import { Breadcrumb, Button, Empty, Progress, Space, Table, Tabs, Tag, Tooltip, Typography, message } from 'antd';
import { CloudDownloadOutlined, FolderOutlined, FileOutlined, ReloadOutlined, PlayCircleOutlined, FontSizeOutlined } from '@ant-design/icons';
import { api, APP_BASE } from '../api.js';

function size(n) {
  if (!n) return '-';
  const u = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0, v = n;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i += 1; }
  return `${v.toFixed(i ? 1 : 0)} ${u[i]}`;
}
function when(ts) {
  if (!ts) return '-';
  if (typeof ts === 'string') return ts;
  return new Date(ts * 1000).toLocaleString();
}

export default function Yun115() {
  const [tab, setTab] = useState('files');
  const [files, setFiles] = useState([]);
  const [stack, setStack] = useState([{ cid: '0', name: '根目录' }]);
  const [tasks, setTasks] = useState([]);
  const [uploads, setUploads] = useState([]);
  const [loading, setLoading] = useState(false);

  const loadFiles = async cid => {
    setLoading(true);
    try {
      const r = await api('/api/115/files?cid=' + encodeURIComponent(cid));
      if (!r.ok) throw new Error(r.error || '读取失败');
      setFiles(r.files || []);
    } catch (e) { message.error(e.message || '读取 115 文件失败'); }
    setLoading(false);
  };
  const loadOffline = async () => {
    setLoading(true);
    try {
      const r = await api('/api/115/offline');
      if (!r.ok) throw new Error(r.error || '读取失败');
      setTasks(r.tasks || []);
    } catch (e) { message.error(e.message || '读取离线任务失败'); }
    setLoading(false);
  };
  useEffect(() => { loadFiles('0'); }, []);
  const loadUploads = async () => {
    try {
      const r = await api('/api/115/uploads');
      setUploads(r.uploads || []);
    } catch { /* ignore */ }
  };
  useEffect(() => { if (tab === 'offline') loadOffline(); }, [tab]);
  useEffect(() => { if (tab !== 'uploads') return; loadUploads(); const t = setInterval(loadUploads, 2000); return () => clearInterval(t); }, [tab]);

  const enter = row => {
    if (!row.is_dir) return;
    const next = [...stack, { cid: row.id, name: row.name }];
    setStack(next); loadFiles(row.id);
  };
  const jump = i => {
    const next = stack.slice(0, i + 1);
    setStack(next); loadFiles(next[next.length - 1].cid);
  };

  const VIDEO_EXT = /\.(mkv|mp4|avi|ts|m2ts|mov|wmv|flv|webm)$/i;
  const playable = r => !r.is_dir && VIDEO_EXT.test(r.name || '') && r.pick_code;
  const play = r => window.open(`${APP_BASE}/api/115/play?pc=${encodeURIComponent(r.pick_code)}`, '_blank');
  const fixSubs = async r => {
    const hide = message.loading('检测字幕中…', 0);
    try {
      const res = await api('/api/subs/fix', { method: 'POST', body: {
        pickcode: r.pick_code, cid: stack[stack.length - 1].cid, name: r.name,
        meta: { title: r.name.replace(VIDEO_EXT, '') },
      } });
      hide();
      const item = (res.results || [])[0];
      if (!res.ok) message.error(res.error || '处理失败');
      else if (item) message.info(item.detail);
    } catch (e) { hide(); message.error(e.message || '处理失败'); }
  };

  const fileCols = [
    { title: '名称', render: (_, r) => (
      <Space>
        {r.is_dir ? <FolderOutlined style={{ color: '#faad14' }} /> : <FileOutlined />}
        <a onClick={() => enter(r)} style={{ cursor: r.is_dir ? 'pointer' : 'default' }}>{r.name}</a>
      </Space>
    ) },
    { title: '大小', width: 120, render: (_, r) => r.is_dir ? '-' : size(r.size) },
    { title: '时间', width: 190, render: (_, r) => when(r.mtime) },
    { title: '操作', width: 150, render: (_, r) => r.is_dir ? '-' : (
      <Space size={4}>
        {playable(r) ? (
          <Tooltip title="播放"><Button size="small" icon={<PlayCircleOutlined />} onClick={() => play(r)} /></Tooltip>
        ) : null}
        {playable(r) ? (
          <Tooltip title="补中文字幕"><Button size="small" icon={<FontSizeOutlined />} onClick={() => fixSubs(r)} /></Tooltip>
        ) : null}
      </Space>
    ) },
  ];
  const taskCols = [
    { title: '任务', dataIndex: 'name', ellipsis: true, render: (v, r) => (
      <div style={{ minWidth: 0 }}>
        <Typography.Text ellipsis={{ tooltip: v }} style={{ maxWidth: '100%' }}>{v}</Typography.Text>
        <div style={{ marginTop: 4 }}><Tag bordered={false}>{r.status_text || r.status}</Tag></div>
      </div>
    ) },
    { title: '进度', width: 200, render: (_, r) => <Progress percent={Math.min(100, r.percent)} size="small" /> },
    { title: '大小', width: 110, render: (_, r) => size(r.size) },
    { title: '速度', width: 110, render: (_, r) => r.rate ? size(r.rate) + '/s' : '-' },
    { title: '添加时间', width: 180, render: (_, r) => when(r.add_time) },
  ];

  const uploadCols = [
    { title: '文件', dataIndex: 'name', ellipsis: true, render: (v, r) => (
      <div style={{ minWidth: 0 }}>
        <Typography.Text ellipsis={{ tooltip: v }} style={{ maxWidth: '100%' }}>{v}</Typography.Text>
        <div style={{ marginTop: 4 }}>
          <Tag bordered={false} color={r.status === 'success' ? 'green' : r.status === 'failed' ? 'red' : 'blue'}>
            {r.status === 'success' ? '上传成功' : r.status === 'failed' ? '上传失败' : '上传中'}
          </Tag>
        </div>
      </div>
    ) },
    { title: '大小', width: 120, render: (_, r) => size(r.size) },
    { title: '时间', width: 180, render: (_, r) => when(r.time) },
    { title: '错误', dataIndex: 'error', ellipsis: true, render: v => v || '-' },
  ];

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '16px 20px' }}>
      <Tabs activeKey={tab} onChange={setTab}
        items={[{ key: 'files', label: '文件列表' }, { key: 'offline', label: '离线下载' }, { key: 'uploads', label: '本地上传' }]}
        tabBarExtraContent={<Button icon={<ReloadOutlined />} onClick={() => tab === 'files' ? loadFiles(stack[stack.length - 1].cid) : tab === 'offline' ? loadOffline() : loadUploads()}>刷新</Button>} />
      {tab === 'files' ? (
        <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <Breadcrumb style={{ marginBottom: 10 }} items={stack.map((s, i) => ({
            title: <a onClick={() => jump(i)}>{s.name}</a>,
          }))} />
          <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
            <Table rowKey="id" size="middle" columns={fileCols} dataSource={files} loading={loading} pagination={false}
              locale={{ emptyText: <Empty description="空目录" /> }} />
          </div>
        </div>
      ) : tab === 'offline' ? (
        <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          <Table rowKey="hash" size="middle" columns={taskCols} dataSource={tasks} loading={loading} pagination={false}
            locale={{ emptyText: <Empty description="没有离线任务" /> }} />
        </div>
      ) : (
        <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          <Table rowKey="name" size="middle" columns={uploadCols} dataSource={uploads} loading={loading} pagination={false}
            locale={{ emptyText: <Empty description="还没有本地上传记录" /> }} />
        </div>
      )}
    </div>
  );
}
