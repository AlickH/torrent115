import React, { useEffect, useRef, useState } from 'react';
import { Button, Empty, Input, Progress, Space, Table, Tag, Typography, message } from 'antd';
import { DownloadOutlined, PauseCircleOutlined, PlayCircleOutlined, DeleteOutlined } from '@ant-design/icons';
import { api } from '../api.js';

function rate(n) {
  if (!n) return '0 B/s';
  const units = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
  let i = 0, v = n;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i += 1; }
  return `${v.toFixed(1)} ${units[i]}`;
}

export default function BtDownloads() {
  const [tasks, setTasks] = useState([]);
  const [magnet, setMagnet] = useState('');
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const timer = useRef(null);

  const load = async () => {
    try {
      const r = await api('/api/bt/tasks');
      setTasks(r.tasks || []);
      setLoading(false);
    } catch (e) {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    timer.current = setInterval(load, 2000);
    return () => clearInterval(timer.current);
  }, []);

  const add = async () => {
    const v = magnet.trim();
    if (!v) return;
    setAdding(true);
    try {
      const r = await api('/api/bt/add', { method: 'POST', body: { magnet: v } });
      if (!r.ok) throw new Error(r.error || '添加失败');
      setMagnet('');
      message.success('已添加');
      load();
    } catch (e) {
      message.error(e.message || '添加失败');
    }
    setAdding(false);
  };

  const action = async (path, hash) => {
    try {
      await api(path, { method: 'POST', body: { hash } });
      load();
    } catch (e) {
      message.error(e.message || '操作失败');
    }
  };

  const columns = [
    {
      title: '任务',
      render: (_, t) => (
        <div>
          <Typography.Text strong>{t.name || t.hash.slice(0, 12)}</Typography.Text>
          <div><Typography.Text type="secondary" style={{ fontSize: 12 }}>{t.hash}</Typography.Text></div>
          <div style={{ marginTop: 4 }}>
            <Tag bordered={false}>{t.state}</Tag>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {t.done && t.total ? `${(t.done / 1073741824).toFixed(2)} / ${(t.total / 1073741824).toFixed(2)} GB` : ''}
            </Typography.Text>
          </div>
        </div>
      ),
    },
    {
      title: '进度', width: 220,
      render: (_, t) => <Progress percent={Math.min(100, t.progress || 0)} size="small" />,
    },
    {
      title: '速度 / Peer', width: 180,
      render: (_, t) => (
        <div style={{ fontSize: 12 }}>
          <div>↓ {rate(t.download_rate)}</div>
          <div>↑ {rate(t.upload_rate)}</div>
          <div>种子 {t.seeders} · 连接 {t.peers}</div>
        </div>
      ),
    },
    {
      title: '操作', width: 150,
      render: (_, t) => (
        <Space>
          {t.state === 'paused'
            ? <Button size="small" icon={<PlayCircleOutlined />} onClick={() => action('/api/bt/resume', t.hash)} />
            : <Button size="small" icon={<PauseCircleOutlined />} onClick={() => action('/api/bt/pause', t.hash)} />}
          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => action('/api/bt/delete', t.hash)} />
        </Space>
      ),
    },
  ];

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '16px 20px' }}>
      <Typography.Text strong style={{ fontSize: 17, marginBottom: 12 }}>BT 下载</Typography.Text>
      <Space.Compact style={{ width: '100%', marginBottom: 12 }}>
        <Input placeholder="粘贴磁力链接" value={magnet} onChange={e => setMagnet(e.target.value)} onPressEnter={add} />
        <Button type="primary" icon={<DownloadOutlined />} loading={adding} onClick={add}>添加</Button>
      </Space.Compact>
      <div style={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
        <Table rowKey="hash" size="middle" columns={columns} dataSource={tasks}
          loading={loading} pagination={false}
          locale={{ emptyText: <Empty description="还没有 BT 任务" /> }} />
      </div>
    </div>
  );
}
