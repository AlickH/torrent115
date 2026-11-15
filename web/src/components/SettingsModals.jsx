import React from 'react';
import {
  Alert, AutoComplete, Button, Divider, Flex, Form, Input, InputNumber, Modal, Segmented, Select, Space, Switch, Tag, Typography,
} from 'antd';
import { EyeOutlined, QrcodeOutlined } from '@ant-design/icons';
import { api } from '../api.js';

export function SettingsModal(props) {
  const {
    open, onClose, cfg, onAccount, test115, onSave, inline, mode, setMode,
    cookieText, setCookieText, revealCookie, startQr,
    targetCid, setTargetCid, transferCid, setTransferCid,
    tmdbText, setTmdbText,
    pansouUrl, setPansouUrl, bitmagnetUrl, setBitmagnetUrl, outboundProxy, setOutboundProxy,
    maxEpisodes, setMaxEpisodes, taskTimeout, setTaskTimeout, waitTimeout, setWaitTimeout, drivembyEnabled, setDrivembyEnabled,
    localSavePath, setLocalSavePath, localMoveEnabled, setLocalMoveEnabled, localDonePath, setLocalDonePath,
    localClient, setLocalClient, localQbtUrl, setLocalQbtUrl, localQbtUser, setLocalQbtUser, localQbtPassword, setLocalQbtPassword, localQbtSock, setLocalQbtSock,
    aria2Url, setAria2Url, aria2Secret, setAria2Secret,
    transmissionUrl, setTransmissionUrl, transmissionUser, setTransmissionUser, transmissionPassword, setTransmissionPassword,
    autoForm, setAutoForm, auto, traktToken, setTraktToken, revealTrakt,
    startTraktOauth, traktOauthError,
    aiPresets, newAiPreset, editAiPreset, deleteAiPreset,
  } = props;
  const body = (
    <>
      <Form layout="vertical">
        <Divider orientation="left" style={{ margin: '0 0 12px' }}>外观</Divider>
        <Form.Item label="主题">
          <Segmented value={mode || 'auto'} onChange={setMode}
            options={[{ label: '跟随系统', value: 'auto' }, { label: '亮色', value: 'light' }, { label: '暗色', value: 'dark' }]} />
        </Form.Item>
        <Divider orientation="left" style={{ margin: '0 0 12px' }}>115 账号</Divider>
        <Form.Item label="115 Cookie">
          <Space.Compact style={{ width: '100%' }}>
            <Input.TextArea
              autoSize={{ minRows: 1, maxRows: 6 }}
              value={cookieText}
              placeholder={cfg?.has_cookie ? '已配置（点击右侧眼睛显示 / 可粘贴新的）' : '未配置，可粘贴 Cookie 或扫码登录'}
              onChange={e => setCookieText(e.target.value)}
            />
            <Button icon={<EyeOutlined />} onClick={revealCookie} />
          </Space.Compact>
          <Space wrap style={{ marginTop: 8 }}>
            <Button icon={<QrcodeOutlined />} onClick={startQr}>扫码登录 115</Button>
            <Button onClick={test115}>测试 115</Button>
          </Space>
        </Form.Item>
        <Form.Item label="115 云下载目标目录 CID（留空=自动用云下载目录）">
          <Input value={targetCid} onChange={e => setTargetCid(e.target.value)} />
        </Form.Item>
        <Form.Item label="115 转存目标目录（填目录名如 云下载，或 CID；留空=根目录）">
          <Input value={transferCid} onChange={e => setTransferCid(e.target.value)} placeholder="云下载" />
        </Form.Item>
        <Divider orientation="left" style={{ margin: '4px 0 12px' }}>搜索数据源</Divider>
        <Form.Item label="TMDB API Key">
          <Input.Password
            value={tmdbText}
            placeholder={cfg?.has_tmdb ? '已配置（点击右侧眼睛显示 / 可粘贴新的）' : '未配置，可粘贴 TMDB API Key'}
            onChange={e => setTmdbText(e.target.value)}
            visibilityToggle={{
              visible: !!tmdbText,
              onVisibleChange: async v => {
                if (!v) { setTmdbText(''); return; }
                const r = await api('/api/secrets?name=tmdb');
                setTmdbText(r.value || '');
              },
            }}
          />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            填了用 TMDB 官方英文名做检索词 ·{' '}
            <a href="https://www.themoviedb.org/settings/api" target="_blank" rel="noreferrer">获取 API Key →</a>
          </Typography.Text>
        </Form.Item>
        <Form.Item label="PanSou 地址（留空则搜索源里不显示 PanSou）">
          <Input value={pansouUrl} onChange={e => setPansouUrl(e.target.value)} placeholder="http://127.0.0.1:18080" />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            部署教程：
            <a href="https://github.com/fish2018/pansou" target="_blank" rel="noreferrer">GitHub 仓库 / docker-compose 示例 →</a>
            <span style={{ margin: '0 6px' }}>·</span>
            <a href="https://github.com/fish2018/pansou#docker-%E9%83%A8%E7%BD%B2" target="_blank" rel="noreferrer">Docker 部署说明 →</a>
          </Typography.Text>
        </Form.Item>
        <Form.Item label="bitmagnet GraphQL 地址（留空则搜索源里不显示 bitmagnet）">
          <Input value={bitmagnetUrl} onChange={e => setBitmagnetUrl(e.target.value)} placeholder="http://127.0.0.1:3333/graphql" />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            部署教程：
            <a href="https://bitmagnet.io/setup/installation.html" target="_blank" rel="noreferrer">官方安装文档 →</a>
            <span style={{ margin: '0 6px' }}>·</span>
            <a href="https://github.com/bitmagnet-io/bitmagnet" target="_blank" rel="noreferrer">GitHub 仓库（含 docker-compose）→</a>
          </Typography.Text>
        </Form.Item>
        <Divider orientation="left" style={{ margin: '4px 0 12px' }}>网络</Divider>
        <Form.Item label="出口代理（可选，直连失败时兜底；如 http://user:pass@127.0.0.1:7890）">
          <Input value={outboundProxy} onChange={e => setOutboundProxy(e.target.value)} placeholder="留空 = 只用直连" />
        </Form.Item>
        <Divider orientation="left" style={{ margin: '4px 0 12px' }}>追剧任务</Divider>
        <Form.Item label="单次运行最多处理条数（0=不限，逐条串行处理）">
          <InputNumber min={0} max={500} value={maxEpisodes} onChange={v => setMaxEpisodes(v ?? 0)} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="云下载无进展超时重试（分钟，0=不重试）">
          <InputNumber min={0} max={240} value={taskTimeout} onChange={v => setTaskTimeout(v ?? 10)} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="等待中宽限（分钟，0=不等待；已有任务下载中时会持续排队）">
          <InputNumber min={0} max={240} value={waitTimeout} onChange={v => setWaitTimeout(v ?? 3)} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="转存完成后自动触发 Drivemby 刷新">
          <Switch checked={drivembyEnabled} onChange={setDrivembyEnabled} />
        </Form.Item>
        <Divider orientation="left" style={{ margin: '4px 0 12px' }}>本地下载器</Divider>
        <Form.Item label="使用哪个下载器">
          <Select value={localClient} onChange={setLocalClient} options={[
            { value: 'qbt_local', label: 'fnOS 下载中心（qBittorrent unix socket）' },
            { value: 'qbt_webui', label: 'qBittorrent WebUI（TCP）' },
            { value: 'aria2', label: 'aria2 JSON-RPC' },
            { value: 'transmission', label: 'Transmission RPC' },
          ]} />
        </Form.Item>
        {localClient === 'qbt_webui' ? (
          <>
            <Form.Item label="WebUI 地址"><Input value={localQbtUrl} onChange={e => setLocalQbtUrl(e.target.value)} placeholder="http://127.0.0.1:8080" /></Form.Item>
            <Form.Item label="用户名"><Input value={localQbtUser} onChange={e => setLocalQbtUser(e.target.value)} /></Form.Item>
            <Form.Item label="密码"><Input.Password value={localQbtPassword} onChange={e => setLocalQbtPassword(e.target.value)} placeholder="qBittorrent WebUI 密码" /></Form.Item>
          </>
        ) : localClient === 'aria2' ? (
          <>
            <Form.Item label="JSON-RPC 地址"><Input value={aria2Url} onChange={e => setAria2Url(e.target.value)} placeholder="http://127.0.0.1:6800/jsonrpc" /></Form.Item>
            <Form.Item label="RPC Secret（可选）"><Input.Password value={aria2Secret} onChange={e => setAria2Secret(e.target.value)} /></Form.Item>
          </>
        ) : localClient === 'transmission' ? (
          <>
            <Form.Item label="RPC 地址"><Input value={transmissionUrl} onChange={e => setTransmissionUrl(e.target.value)} placeholder="http://127.0.0.1:9091/transmission/rpc" /></Form.Item>
            <Form.Item label="用户名（可选）"><Input value={transmissionUser} onChange={e => setTransmissionUser(e.target.value)} /></Form.Item>
            <Form.Item label="密码（可选）"><Input.Password value={transmissionPassword} onChange={e => setTransmissionPassword(e.target.value)} /></Form.Item>
          </>
        ) : (
          <Form.Item label="qBittorrent socket 路径"><Input value={localQbtSock} onChange={e => setLocalQbtSock(e.target.value)} placeholder="/run/qbt.sock" /></Form.Item>
        )}
        {localClient !== 'qbt_local' && localClient !== 'qbt_webui' ? (
          <Typography.Paragraph type="secondary" style={{ fontSize: 12 }}>
            该下载器不支持 App 内自动移动完成文件，请用外部脚本/命令处理。
          </Typography.Paragraph>
        ) : null}
        <Form.Item label="保存目录">
          <Input value={localSavePath} onChange={e => setLocalSavePath(e.target.value)} placeholder="/vol1/1000/Downloads" />
        </Form.Item>
        <Form.Item label="完成后移动到目标目录">
          <Switch checked={localMoveEnabled} onChange={setLocalMoveEnabled} />
        </Form.Item>
        <Form.Item label="移动目标目录">
          <Input value={localDonePath} onChange={e => setLocalDonePath(e.target.value)} disabled={!localMoveEnabled} placeholder="/vol1/1000/Downloads/Done" />
        </Form.Item>

        <Divider orientation="left" style={{ margin: '4px 0 12px' }}>Trakt 凭据</Divider>
        <Form.Item label="Trakt Client ID"><Input value={autoForm.traktClientId} onChange={e => setAutoForm({ ...autoForm, traktClientId: e.target.value })} placeholder="可选" /></Form.Item>
        <Form.Item label="Trakt Access Token"><Input.Password value={traktToken} onChange={e => setTraktToken(e.target.value)} placeholder={auto?.has_trakt ? '已配置（点击右侧眼睛显示 / 可粘贴新的）' : '未配置'} visibilityToggle={{ visible: !!traktToken, onVisibleChange: v => { if (!v) setTraktToken(''); else revealTrakt(); } }} /></Form.Item>
        <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 8 }}>
          Trakt 应用里的 <b>Redirect URI</b> 必须填：<Typography.Text code copyable>{window.location.origin + '/api/trakt/callback'}</Typography.Text>
        </Typography.Paragraph>
        <Flex gap={8} align="center" wrap style={{ marginBottom: 4 }}>
          <Button onClick={startTraktOauth}>OAuth 获取 Token</Button>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            创建 Trakt 应用：<a href="https://trakt.tv/oauth/applications" target="_blank" rel="noreferrer">前往 →</a>
          </Typography.Text>
        </Flex>
        {traktOauthError ? <Alert style={{ marginTop: 8 }} type="error" showIcon message={'上次授权失败：' + traktOauthError} /> : null}
        <Divider orientation="left" style={{ margin: '8px 0 12px' }}>AI 预设</Divider>
        <Flex wrap gap={8} style={{ marginBottom: 12 }}>
          {aiPresets.map(a => (
            <Tag key={a.id} closable onClose={() => deleteAiPreset(a.id)} onClick={() => editAiPreset(a)} style={{ cursor: 'pointer' }}>
              {a.name} · {a.model || '模型未设置'}
            </Tag>
          ))}
          {!aiPresets.length ? <Typography.Text type="secondary" style={{ fontSize: 12 }}>还没有 AI 预设</Typography.Text> : null}
        </Flex>
        <Button onClick={newAiPreset}>新建 AI 预设</Button>
      </Form>

    </>
  );
  if (inline) {
    return (
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        <div style={{ flex: 1, overflow: 'auto', padding: '12px 20px' }}>
          <div style={{ fontSize: 17, fontWeight: 600, marginBottom: 12 }}>设置</div>
          {body}
        </div>
        <div style={{ flexShrink: 0, borderTop: `1px solid #303030`, padding: '10px 20px' }}>
          <Flex justify="flex-end" gap={8}>
            <Button onClick={onAccount}>修改账号</Button>
            <Button type="primary" onClick={onSave}>保存</Button>
          </Flex>
        </div>
      </div>
    );
  }
  return (
    <Modal open={open} title="设置" width={640} onCancel={onClose}
      footer={<Flex justify="flex-end" gap={8}><Button onClick={onAccount}>修改账号</Button><Button type="primary" onClick={onSave}>保存</Button></Flex>}>
      {body}
    </Modal>
  );
}

export function AccountModal(props) {
  const { open, onClose, cfg, accUser, setAccUser, accOld, setAccOld, accNew, setAccNew, accNew2, setAccNew2, saveAccount } = props;
  return (
    <Modal
      open={open}
      title={'修改账号 · 当前用户：' + (cfg?.auth_user || '')}
      width={480}
      onCancel={onClose}
      footer={<Flex justify="flex-end" gap={8}><Button onClick={onClose}>取消</Button><Button type="primary" onClick={saveAccount}>保存账号修改</Button></Flex>}
    >
      <Form layout="vertical">
        <Form.Item label="新用户名（留空不改）"><Input value={accUser} onChange={e => setAccUser(e.target.value)} /></Form.Item>
        <Form.Item label="当前密码（必填）"><Input.Password value={accOld} onChange={e => setAccOld(e.target.value)} /></Form.Item>
        <Form.Item label="新密码（留空不改，至少 5 位）"><Input.Password value={accNew} onChange={e => setAccNew(e.target.value)} /></Form.Item>
        <Form.Item label="确认新密码"><Input.Password value={accNew2} onChange={e => setAccNew2(e.target.value)} /></Form.Item>
      </Form>
    </Modal>
  );
}

export function AiPresetModal(props) {
  const {
    open, draft, onClose, testAiPreset, aiTesting, saveAiPreset, setAiPresetDraft,
    aiModels, fetchAiModels, aiModelsLoading,
  } = props;
  return (
    <Modal
      open={open}
      title={draft?._new ? '新建 AI 预设' : '编辑 AI 预设'}
      width={520}
      onCancel={onClose}
      footer={<Flex justify="space-between"><Button onClick={testAiPreset} loading={aiTesting}>测试连接</Button><Space><Button onClick={onClose}>取消</Button><Button type="primary" onClick={saveAiPreset}>保存</Button></Space></Flex>}
    >
      {draft ? (
        <Form layout="vertical">
          <Form.Item label="名称"><Input value={draft.name} onChange={e => setAiPresetDraft({ ...draft, name: e.target.value })} placeholder="如：GPT-4o-mini / 本地 Ollama" /></Form.Item>
          <Form.Item label="Base URL"><Input value={draft.base_url} onChange={e => setAiPresetDraft({ ...draft, base_url: e.target.value })} placeholder="https://api.openai.com/v1" /></Form.Item>
          <Form.Item label="模型">
            <Space.Compact style={{ width: '100%' }}>
              <AutoComplete
                style={{ flex: 1 }}
                value={draft.model}
                onChange={v => setAiPresetDraft({ ...draft, model: v })}
                options={aiModels.map(m => ({ value: m, label: m }))}
                placeholder="gpt-4o-mini（可手填或拉取）"
                filterOption={(input, option) => (option?.value || '').toLowerCase().includes((input || '').toLowerCase())}
              />
              <Button onClick={fetchAiModels} loading={aiModelsLoading}>拉取模型</Button>
            </Space.Compact>
          </Form.Item>
          <Form.Item label="API Key"><Input.Password value={draft.api_key || ''} onChange={e => setAiPresetDraft({ ...draft, api_key: e.target.value })} placeholder={draft.has_key ? '已配置（可粘贴新的覆盖）' : '未配置'} /></Form.Item>
        </Form>
      ) : null}
    </Modal>
  );
}
