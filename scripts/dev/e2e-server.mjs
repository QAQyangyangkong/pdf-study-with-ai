import { spawn, spawnSync } from 'node:child_process';
import { resolve } from 'node:path';
import { mkdirSync } from 'node:fs';
import { randomUUID } from 'node:crypto';

const root=resolve(import.meta.dirname,'../..');const directory=resolve(root,'tmp','e2e-'+randomUUID());
mkdirSync(directory,{recursive:true});
const env={...process.env,PYTHONUTF8:'1',PYTHONPATH:resolve(root,'backend/src'),TEMP:resolve(root,'tmp'),TMP:resolve(root,'tmp'),STUDYNOTE_DATA_DIR:directory};
const seed=spawnSync(resolve(root,'.venv/Scripts/python.exe'),[resolve(root,'scripts/dev/seed_e2e.py'),directory],{cwd:root,env,stdio:'inherit',windowsHide:true});
if(seed.status!==0)process.exit(seed.status||1);
const child=spawn(process.execPath,[resolve(root,'scripts/dev/start.mjs')],{cwd:root,env,stdio:'inherit',windowsHide:true});
function stop(){if(child.pid&&child.exitCode===null){if(process.platform==='win32')spawnSync('taskkill',['/PID',String(child.pid),'/T','/F'],{stdio:'ignore',windowsHide:true});else child.kill('SIGTERM');}process.exit(0);}
process.on('SIGINT',stop);process.on('SIGTERM',stop);
child.on('exit',code=>process.exit(code||0));
