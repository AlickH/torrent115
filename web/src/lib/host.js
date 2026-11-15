import { TrimApp } from '@trimjs/web-app';

let app = null;

export function hostApp() {
  if (typeof window === 'undefined' || window.self === window.top) return null;
  if (!app) {
    try { app = new TrimApp(); } catch { app = null; }
  }
  return app;
}

function findPath(value) {
  if (typeof value === 'string') {
    if (value.startsWith('/')) return value;
    const trimmed = value.trim();
    if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
      try { return findPath(JSON.parse(trimmed)); } catch { /* ignore */ }
    }
    const m = trimmed.match(/\/[^\s"'\]]+/);
    return m ? m[0] : null;
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      const p = findPath(item);
      if (p) return p;
    }
    return null;
  }
  if (value && typeof value === 'object') {
    for (const key of ['path', 'paths', 'data', 'result', 'files', 'value']) {
      if (key in value) {
        const p = findPath(value[key]);
        if (p) return p;
      }
    }
    for (const v of Object.values(value)) {
      const p = findPath(v);
      if (p) return p;
    }
  }
  return null;
}

export async function pickFolder(title) {
  const a = hostApp();
  if (!a) return { error: '当前环境不支持系统文件夹选择器' };
  const label = title || '选择文件夹';
  const attempts = [
    a.pickFile && (() => a.pickFile({ directory: true, title: label })),
    a.pickUserFile && (() => a.pickUserFile({ directory: true, title: label })),
    a.pickSharedFile && (() => a.pickSharedFile({ title: label })),
  ].filter(Boolean);
  let lastError = null;
  for (const run of attempts) {
    try {
      const r = await run();
      const path = findPath(r);
      if (path) return { path };
      if (r === undefined || r === null) return { path: null };
      return { error: '无法解析选择结果：' + JSON.stringify(r).slice(0, 160) };
    } catch (e) {
      lastError = e;
    }
  }
  return { error: (lastError && lastError.message) || '当前环境不支持系统文件夹选择器' };
}
