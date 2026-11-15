export async function api(path, { method = 'GET', body, signal } = {}) {
  const opts = { method, credentials: 'same-origin', headers: {} };
  if (signal) opts.signal = signal;
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}

export function posterUrl(p) {
  return p ? '/api/tmdb/img?path=' + encodeURIComponent(p) : '';
}


const PUBLIC_TRACKERS = [
  'udp://tracker.opentrackr.org:1337/announce',
  'udp://open.stealth.si:80/announce',
  'udp://tracker.torrent.eu.org:451/announce',
  'udp://tracker.dler.org:6969/announce',
  'https://tracker.moeblog.cn:443/announce',
  'https://tracker.zhuqiy.com:443/announce',
  'udp://open.dstud.io:6969/announce',
  'udp://open.demonii.com:1337/announce',
  'udp://tracker.openbittorrent.com:6969/announce',
  'udp://exodus.desync.com:6969/announce',
];

export function withTrackers(url) {
  if (!url || !url.startsWith('magnet:')) return url;
  const existing = new Set();
  url.replace(/[?&]tr=([^&]+)/g, (_, t) => { existing.add(decodeURIComponent(t)); });
  const parts = [url];
  for (const t of PUBLIC_TRACKERS) {
    if (existing.has(t)) continue;
    parts.push('tr=' + encodeURIComponent(t));
  }
  return parts.join('&');
}
