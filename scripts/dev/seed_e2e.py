"""Synthetic fixtures and a precomputed cache; never uses a key or network."""
import sys
from pathlib import Path
from pypdf import PdfWriter, PdfReader
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from studynote.ai.generation import chapter_prompt
from studynote.core.workspace import Workspace
from studynote.documents.service import extract_pdf

root=Path(__file__).resolve().parents[2]
path=root/'tests/fixtures/sample.pdf'
path.parent.mkdir(parents=True,exist_ok=True)
writer=PdfWriter()
for text in ('Ohm law: voltage equals current times resistance.','Example: 12 volts across 4 ohms gives 3 amperes.'):
    page=writer.add_blank_page(width=360,height=480)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream=DecodedStreamObject();stream.set_data(f'BT /F1 12 Tf 24 420 Td ({text}) Tj ET'.encode('ascii'));page[NameObject('/Contents')]=writer._add_object(stream)
writer.add_outline_item('Ohm law',0)
with path.open('wb') as stream:writer.write(stream)
workspace=Workspace(Path(sys.argv[1]))
chapter={'title':'第一章','start_page':1,'end_page':2,'text':extract_pdf(PdfReader(path),1,2)}
prompt=chapter_prompt(chapter,{'title':'sample'},'面向初学者，保留推导过程，用简短例子解释。')
fingerprint=workspace.ai.estimate(workspace.config(),prompt).fingerprint
workspace.db.cache(fingerprint,'# 欧姆定律\n\n电压、电流、电阻之间满足 **V = IR**。\n\n## 例子\n12 V / 4 Ω = 3 A。\n\n材料来源：PDF 第 1–2 页。')
