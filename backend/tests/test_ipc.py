import base64
import io
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import pymupdf
from studynote.ai.generation import AIService
from studynote.core.workspace import Workspace
from studynote.ipc.router import Router
from studynote.main import serve_stdio
from tests.helpers import FakeKeys, fake_response, make_pdf


class IPCTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.workspace=Workspace(self.root/'workspace')
        self.workspace.ai=AIService(self.workspace.db,FakeKeys(),lambda *args:fake_response())
        self.router=Router(self.workspace)

    def tearDown(self):
        self.router.close()
        self.workspace.keys.delete()
        self.temp.cleanup()

    def call(self,method,params=None):
        response=self.router.handle({'protocol_version':1,'id':'test-request','method':method,'params':params or {}})
        self.assertTrue(response['ok'],response.get('error'))
        self.assertEqual(response['id'],'test-request')
        return response['result']

    def test_end_to_end_import_chapter_generation_edit_search_export(self):
        path=make_pdf(self.root/'book.pdf')
        book=self.call('documents.import',{'path':str(path),'kind':'textbook','course':'电路'})['document_id']
        chapter=self.call('chapters.create',{'document_id':book,'title':'欧姆定律','start_page':1,'end_page':2})['chapter_id']
        prepared=self.call('generation.prepare',{'kind':'chapter','chapter_id':chapter,'preference':'解释公式'})
        self.assertIn('PDF 第 1 页',prepared['prompt'])
        task_id=self.call('generation.start',{'token':prepared['token']})['task_id']
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            task=self.call('tasks.get',{'task_id':task_id})
            if task['status'] in {'completed','failed'}:break
            time.sleep(.01)
        self.assertEqual(task['status'],'completed',task)
        note_id=task['result']['note_id']
        self.call('notes.save',{'note_id':note_id,'title':'新的理解','body':'公式与应用','tags':['电路','基础']})
        result=self.call('notes.search',{'query':'公式','topic':'电路'})['notes']
        self.assertEqual(len(result),1)
        self.assertIn('PDF 第 1-2 页',result[0]['sources'][0])
        versions=self.call('notes.versions',{'note_id':note_id})['versions']
        self.assertEqual(len(versions),2)
        self.call('notes.restore',{'note_id':note_id,'version_id':versions[-1]['id']})
        self.assertEqual(self.workspace.db.get('notes',note_id)['title'],'欧姆定律')
        destination=self.call('export.obsidian',{'destination':str(self.root/'vault')})['path']
        self.assertEqual(len(list((Path(destination)/'笔记').glob('*.md'))),1)

    def test_reader_returns_exact_requested_page(self):
        book=self.call('documents.import',{'path':str(make_pdf(self.root/'book.pdf')),'kind':'textbook'})['document_id']
        response=self.call('reader.page',{'document_id':book,'page':2})
        with pymupdf.open(stream=base64.b64decode(response['pdf_base64']), filetype='pdf') as pdf:
            self.assertEqual(pdf.page_count,1)
            self.assertEqual(pdf[0].get_text().strip(),'Circuit current')
        self.assertEqual(response['page'],2)
        self.assertEqual(response['total'],3)

    def test_invalid_protocol_method_unknown_fields_and_ids_are_rejected(self):
        for request in [[],{'protocol_version':2,'id':'a','method':'workspace.get','params':{}},
                        {'protocol_version':1,'id':'a','method':'arbitrary.shell','params':{}},
                        {'protocol_version':1,'id':'a','method':'workspace.get','params':{'secret':'do-not-echo'}},
                        {'protocol_version':1,'id':'a','method':'reader.page','params':{'document_id':True,'page':1}}]:
            response=self.router.handle(request)
            self.assertFalse(response['ok'])
            self.assertNotIn('do-not-echo',json.dumps(response))

    def test_response_never_contains_saved_key(self):
        key='mock-secret-not-for-production'
        self.workspace.keys.save(key)
        snapshot=self.call('workspace.get')
        self.assertTrue(snapshot['key_configured'])
        self.assertNotIn(key,json.dumps(snapshot))
        self.assertNotIn('api_key',snapshot['config'])

    def test_preview_is_single_use_and_obsolete_preview_expires(self):
        old=self.call('generation.prepare',{'kind':'connection'})
        current=self.call('generation.prepare',{'kind':'connection'})
        rejected=self.router.handle({'protocol_version':1,'id':'x','method':'generation.start','params':{'token':old['token']}})
        self.assertFalse(rejected['ok'])
        self.assertNotEqual(current['token'],old['token'])

    def test_jsonl_continues_after_bad_input_and_preserves_utf8(self):
        good={'protocol_version':1,'id':'中文请求','method':'workspace.get','params':{}}
        source=io.StringIO('not-json\n'+json.dumps(good,ensure_ascii=False)+'\n')
        output=io.StringIO()
        serve_stdio(self.router,source,output)
        lines=[json.loads(line) for line in output.getvalue().splitlines()]
        self.assertFalse(lines[0]['ok'])
        self.assertTrue(lines[1]['ok'])
        self.assertEqual(lines[1]['id'],'中文请求')

    def test_real_stdio_subprocess_handles_two_requests_and_exits_at_eof(self):
        requests=[{'protocol_version':1,'id':str(i),'method':'workspace.get','params':{}} for i in range(2)]
        process=subprocess.run([sys.executable,'-m','studynote.main','--data-dir',str(self.root/'process')],
            input=''.join(json.dumps(request)+'\n' for request in requests),capture_output=True,text=True,encoding='utf-8',timeout=15)
        self.assertEqual(process.returncode,0,process.stderr)
        lines=[json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual([line['id'] for line in lines],['0','1'])
        self.assertTrue(all(line['ok'] for line in lines))

    def test_shared_contract_is_identical_to_packaged_python_schema(self):
        project=Path(__file__).resolve().parents[2]
        shared=json.loads((project/'packages/contracts/protocol.schema.json').read_text(encoding='utf-8'))
        copied=json.loads((project/'backend/src/studynote/ipc/protocol.schema.json').read_text(encoding='utf-8'))
        self.assertEqual(shared,copied)
