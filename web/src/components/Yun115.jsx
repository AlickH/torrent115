import React, { useEffect, useState } from 'react';
import { Breadcrumb, Button, Empty, Progress, Space, Table, Tabs, Tag, Typography, message } from 'antd';
import { CloudDownloadOutlined, FolderOutlined, FileOutlined, ReloadOutlined } from '@ant-design/icons';
import { api } from '../api.js';

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
  useEffect(() => { if (tab === 'offline') loadOffline(); }, [tab]);

  const enter = row => {
    if (!row.is_dir) return;
    const next = [...stack, { cid: row.id, name: row.name }];
    setStack(next); loadFiles(row.id);
  };
  const jump = i => {
    const next = stack.slice(0, i + 1);
    setStack(next); loadFiles(next[next.length - 1].cid);
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
  ];
  const taskCols = [
    { title: '任务', dataIndex: 'name', ellipsis: true, render: (v, r) => (
      <div>
        <Typography.Text>{v}</Typography.Text>
        <div style={{ marginTop: 4 }}><Tag bordered={false}>{r.status_text || r.status}</Tag></div>
      </div>
    ) },
    { title: '进度', width: 200, render: (_, r) => <Progress percent={Math.min(100, r.percent)} size="small" /> },
    { title: '大小', width: 110, render: (_, r) => size(r.size) },
    { title: '速度', width: 110, render: (_, r) => r.rate ? size(r.rate) + '/s' : '-' },
    { title: '添加时间', width: 180, render: (_, r) => when(r.add_time) },
  ];

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '16px 20px' }}>
      <Tabs activeKey={tab} onChange={setTab} items={[{ key: 'files', label: '文件列表' }, { key: 'offline', label: '离线下载' }]}
        tabBarExtraContent={<Button icon={<ReloadOutlined />} onClick={() => tab === 'files' ? loadFiles(stack[stack.length - 1].cid) : loadOffline()}>刷新</Button>} />
      {tab === 'files' ? (
        <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <Breadcrumb style={{ marginBottom: 10 }} items={stack.map((s, i) => ({
            title: <a onClick={() => jump(i)}>{s.name}</a>,
          }))} />
          <Table rowKey="id" size="middle" columns={fileCols} dataSource={files} loading={loading} pagination={false}
            locale={{ emptyText: <Empty description="空目录" /> }} />
        </div>
      ) : (
        <Table rowKey="hash" size="middle" columns={taskCols} dataSource={tasks} loading={loading} pagination={false}
          locale={{ emptyText: <Empty description="没有离线任务" /> }} />
      )}
    </div>
  );
}
