"""Exercise packaged PDF, FTS5 and Markdown behavior through production JSONL."""
import argparse
import base64
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

import pymupdf


def verify(executable, fixture, workspace):
    original_digest = hashlib.sha256(fixture.read_bytes()).digest()
    with pymupdf.open(fixture) as source_pdf:
        expected_texts = [source_pdf[index].get_text() for index in range(2)]
    requests = [
        ('workspace.get', {}),
        ('documents.import', {'path': str(fixture.resolve()), 'kind': 'textbook', 'course': '打包验证'}),
        ('reader.page', {'document_id': 1, 'page': 2}),
        ('chapters.create', {'document_id': 1, 'title': '打包测试章节', 'start_page': 1, 'end_page': 2}),
        ('notes.save', {'title': '电路基础验证', 'body': '# 欧姆定律\n电压电流电阻', 'tags': ['电路']}),
        ('notes.search', {'query': '电压电流'}),
    ]
    source = ''.join(json.dumps({'protocol_version': 1, 'id': str(index), 'method': method,
                                'params': params}, ensure_ascii=False) + '\n'
                     for index, (method, params) in enumerate(requests))
    result = subprocess.run([str(executable.resolve()), '--data-dir', str(workspace)], input=source,
                            text=True, encoding='utf-8', capture_output=True, timeout=45)
    if result.returncode:
        raise RuntimeError('Packaged sidecar exited with an error.')
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    if len(responses) != len(requests) or not all(response.get('ok') for response in responses):
        # Do not echo arbitrary stdout/stderr or application payloads.
        raise RuntimeError('Packaged sidecar protocol or business validation failed.')
    if responses[0]['result']['schema_version'] != 3:
        raise RuntimeError('Packaged sidecar did not open the expected database schema.')
    preview = responses[2]['result']
    with pymupdf.open(stream=base64.b64decode(preview['pdf_base64']), filetype='pdf') as page_pdf:
        if preview['page'] != 2 or page_pdf.page_count != 1 or page_pdf[0].get_text() != expected_texts[1]:
            raise RuntimeError('Packaged PDF preview did not return only the requested physical page.')
    chapters = list((workspace / 'chapters').glob('*.pdf'))
    if len(chapters) != 1:
        raise RuntimeError('Packaged chapter file was not created.')
    with pymupdf.open(chapters[0]) as chapter_pdf:
        if chapter_pdf.page_count != 2 or [page.get_text() for page in chapter_pdf] != expected_texts:
            raise RuntimeError('Packaged chapter file did not preserve the requested pages and text.')
    if hashlib.sha256(fixture.read_bytes()).digest() != original_digest:
        raise RuntimeError('Packaged PDF operations modified the source fixture.')
    notes = responses[5]['result']['notes']
    if len(notes) != 1 or notes[0]['title'] != '电路基础验证':
        raise RuntimeError('Packaged full-text search failed.')
    print('Packaged PDF import, single-page preview, chapter split and FTS5 verified.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('executable', type=Path)
    parser.add_argument('fixture', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='studynote-package-') as directory:
        verify(args.executable, args.fixture, Path(directory))


if __name__ == '__main__':
    main()
