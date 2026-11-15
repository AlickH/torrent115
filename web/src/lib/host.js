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
  if (!a) return { error: '当前环境不支持系统文件夹选择器' };
  const label = title || '选择文件夹';
  const attempts = [
    a.pickUserFile && (() => a.pickUserFile({ directory: true, title: label })),
    a.pickFile && (() => a.pickFile({ directory: true, title: label })),
    a.pickSharedFile && (() => a.pickSharedFile({ title: label })),
  ].filter(Boolean);
  let lastError = null;
  for (const run of attempts) {
    try {
      const r = await run();
      if (Array.isArray(r)) return { path: r[0] || null };
      if (r && Array.isArray(r.data)) return { path: r.data[0] || null };
      // undefined / 空结果 = 用户取消，直接返回，不再尝试下一个选择器
      return { path: null };
    } catch (e) {
      lastError = e;
    }
  }
  return { error: (lastError && lastError.message) || '当前环境不支持系统文件夹选择器' };
}
