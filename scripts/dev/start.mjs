import { spawn, spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { resolve } from 'node:path';
import { mkdirSync } from 'node:fs';

const root = resolve(import.meta.dirname, '../..');
const token = randomBytes(32).toString('hex');
const port = process.env.STUDYNOTE_DEV_PORT || '18745';
mkdirSync(resolve(root,'tmp'),{recursive:true});
const env = { ...process.env, PYTHONUTF8:'1', PYTHONPATH:resolve(root,'backend/src'),
  TEMP:resolve(root,'tmp'), TMP:resolve(root,'tmp'), STUDYNOTE_DEV_TOKEN:token,
  VITE_STUDYNOTE_DEV_TOKEN:token, VITE_STUDYNOTE_DEV_PORT:port };
const python = resolve(root,'.venv/Scripts/python.exe');
const args = ['-m','studynote.main','--http',port];
if(process.env.STUDYNOTE_DATA_DIR) args.push('--data-dir',process.env.STUDYNOTE_DATA_DIR);
const backend = spawn(python,args,{cwd:root,env,stdio:['ignore','ignore','inherit'],windowsHide:true});
const frontend = spawn(process.platform==='win32'?'pnpm.cmd':'pnpm',['--filter','@studynote/desktop','dev'],{cwd:root,env,stdio:'inherit',shell:process.platform==='win32',windowsHide:true});
let stopping=false;
function killTree(child){if(!child.pid||child.exitCode!==null)return;if(process.platform==='win32')spawnSync('taskkill',['/PID',String(child.pid),'/T','/F'],{stdio:'ignore',windowsHide:true});else child.kill();}
function stop(){if(stopping)return;stopping=true;killTree(backend);killTree(frontend);}
process.on('SIGINT',()=>{stop();process.exit(0);});process.on('SIGTERM',()=>{stop();process.exit(0);});
backend.on('error',error=>{console.error('Backend launch failed:',error.message);stop();process.exit(1);});
backend.on('exit',code=>{if(!stopping){stop();process.exit(code||0);}});
frontend.on('exit',code=>{if(!stopping){stop();process.exit(code||0);}});
