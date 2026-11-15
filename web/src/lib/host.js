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
  if (!a) return null;
  const label = title || '选择文件夹';
  const methods = [
    () => a.pickUserFile && a.pickUserFile({ directory: true, title: label }),
    () => a.pickFile && a.pickFile({ directory: true, title: label }),
    () => a.pickSharedFile && a.pickSharedFile({ title: label }),
  ];
  for (const run of methods) {
    try {
      const r = await run();
      if (Array.isArray(r) && r[0]) return r[0];
      if (r && r.data && r.data[0]) return r.data[0];
    } catch { /* try next */ }
  }
  return null;
}
