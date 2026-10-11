import { useCallback, useEffect, useState } from 'react';
import type { Workspace } from '../types';
import { rpc } from '../services/backend';

export function useWorkspace() {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [error, setError] = useState('');
  const refresh = useCallback(async () => {
    try { setWorkspace(await rpc<Workspace>('workspace.get')); setError(''); }
    catch (error) { setError(error instanceof Error ? error.message : '本地工作区暂不可用。'); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  return { workspace, refresh, error };
}
