import { TrimApp } from '@trimjs/web-app';

let app = null;

export function hostApp() {
  if (typeof window === 'undefined' || window.self === window.top) return null;
  if (!app) {
    try { app = new TrimApp(); } catch { app = null; }
  }
  return app;
}

export async function pickFolder(title) {
  const a = hostApp();
  if (!a || !a.pickUserFile) return null;
  try {
    const r = await a.pickUserFile({ directory: true, title: title || '选择文件夹' });
    return (r && r.data && r.data[0]) || null;
  } catch {
    return null;
  }
}
