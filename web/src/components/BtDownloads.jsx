import React, { useEffect, useRef, useState } from 'react';
import { Button, Descriptions, Empty, Input, Modal, Progress, Space, Table, Tabs, Tag, Typography, message } from 'antd';
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
  const [detail, setDetail] = useState(null);
  const [detailOpen, setDetailOpen] = useState(false);
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

  const showDetail = async t => {
    try {
      const r = await api('/api/bt/detail?hash=' + encodeURIComponent(t.hash));
      if (!r.ok) throw new Error(r.error || '读取详情失败');
      setDetail(r); setDetailOpen(true);
    } catch (e) { message.error(e.message || '读取详情失败'); }
  };

  const trackerStatus = n => ({ 0: '禁用', 1: '未联系', 2: '正常', 3: '更新中', 4: '不工作' }[n] || n);
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
          <Button size="small" onClick={() => showDetail(t)}>详情</Button>
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
      <Modal open={detailOpen} onCancel={() => setDetailOpen(false)} footer={null} width={900} title="任务详情">
        <Descriptions size="small" column={2} style={{ marginBottom: 12 }}>
          <Descriptions.Item label="保存目录" span={2}>{detail?.properties?.save_path}</Descriptions.Item>
          <Descriptions.Item label="总大小">{detail?.properties?.total_size ? (detail.properties.total_size / 1073741824).toFixed(2) + ' GB' : '-'}</Descriptions.Item>
          <Descriptions.Item label="分片大小">{detail?.properties?.piece_size ? (detail.properties.piece_size / 1048576).toFixed(1) + ' MB' : '-'}</Descriptions.Item>
          <Descriptions.Item label="完成量">{detail?.properties?.completed ? (detail.properties.completed / 1073741824).toFixed(2) + ' GB' : '-'}</Descriptions.Item>
          <Descriptions.Item label="分享率">{detail?.properties?.share_ratio ?? '-'}</Descriptions.Item>
        </Descriptions>
        <Tabs items={[
          { key: 'trackers', label: 'Tracker', children: (
            <Table rowKey={(r, i) => r.url + i} size="small" pagination={false} dataSource={detail?.trackers || []}
              columns={[
                { title: 'URL', dataIndex: 'url', ellipsis: true },
                { title: '状态', dataIndex: 'status', width: 90, render: trackerStatus },
                { title: '种子', dataIndex: 'num_seeds', width: 70 },
                { title: '下载', dataIndex: 'num_leeches', width: 70 },
                { title: '消息', dataIndex: 'msg', width: 200, ellipsis: true },
              ]} />
          ) },
          { key: 'peers', label: 'Peer', children: (
            <Table rowKey={r => r.addr} size="small" pagination={false}
              dataSource={Object.entries(detail?.peers || {}).map(([addr, p]) => ({ addr, ...p }))}
              columns={[
                { title: '地址', dataIndex: 'addr', width: 190 },
                { title: '客户端', dataIndex: 'client', ellipsis: true },
                { title: '进度', dataIndex: 'progress', width: 80, render: v => ((v || 0) * 100).toFixed(1) + '%' },
                { title: '下载', dataIndex: 'dl_speed', width: 100, render: rate },
                { title: '上传', dataIndex: 'up_speed', width: 100, render: rate },
                { title: '方向', dataIndex: 'flags', width: 90 },
              ]} />
          ) },
        ]} />
      </Modal>
    </div>
  );
}
