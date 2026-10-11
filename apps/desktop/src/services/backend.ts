import { invoke, isTauri } from '@tauri-apps/api/core';
import { open, save } from '@tauri-apps/plugin-dialog';
import { requestSchema, responseSchema, type Method } from '@studynote/contracts';

export async function rpc<T>(method: Method, params: Record<string, unknown> = {}): Promise<T> {
  const request = requestSchema.parse({ protocol_version: 1, id: crypto.randomUUID(), method, params });
  let raw: unknown;
  if (isTauri()) {
    raw = await invoke('backend_request', { request });
  } else {
    const token = import.meta.env.VITE_STUDYNOTE_DEV_TOKEN;
    if (!token) throw new Error('预览后端未启动，请通过项目的开发启动命令打开。');
    const response = await fetch(`http://127.0.0.1:${import.meta.env.VITE_STUDYNOTE_DEV_PORT || '18745'}/ipc`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(request),
    });
    if (!response.ok) throw new Error('本地工作区连接失败，请重新启动应用。');
    raw = await response.json();
  }
  const response = responseSchema.parse(raw);
  if (response.id !== request.id) throw new Error('本地响应标识不匹配。');
  if (!response.ok) throw new Error(response.error.message);
  return response.result as T;
}

export async function pickFile(): Promise<string | null> {
  if (isTauri()) {
    const result = await open({ multiple: false, filters: [{ name: 'PDF 教材', extensions: ['pdf'] }] });
    return typeof result === 'string' ? result : null;
  }
  return window.prompt('开发预览：输入本机 PDF 的完整路径');
}

export async function pickDestination(kind: 'export' | 'backup'): Promise<string | null> {
  if (isTauri()) {
    const result = kind === 'export' ? await open({ directory: true })
      : await save({ defaultPath: 'StudyNote-backup.zip', filters: [{name:'备份文件',extensions:['zip']}] });
    return typeof result === 'string' ? result : null;
  }
  return window.prompt(kind === 'export' ? '开发预览：输入导出目录完整路径' : '开发预览：输入 ZIP 备份完整路径');
}
