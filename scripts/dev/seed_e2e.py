"""Synthetic fixtures and a precomputed cache; never uses a key or network."""
import sys
from pathlib import Path
import pymupdf
from studynote.ai.generation import chapter_prompt
from studynote.core.workspace import Workspace
from studynote.documents.service import extract_pdf, read_pdf

root=Path(__file__).resolve().parents[2]
path=root/'tests/fixtures/sample.pdf'
path.parent.mkdir(parents=True,exist_ok=True)
with pymupdf.open() as pdf:
    for text in ('Ohm law: voltage equals current times resistance.','Example: 12 volts across 4 ohms gives 3 amperes.'):
        page=pdf.new_page(width=360,height=480)
        page.insert_text((24,60),text,fontsize=12)
    pdf.set_toc([[1,'Ohm law',1]])
    pdf.save(path,no_new_id=True)
workspace=Workspace(Path(sys.argv[1]))
with read_pdf(path) as pdf:
    chapter={'title':'第一章','start_page':1,'end_page':2,'text':extract_pdf(pdf,1,2)}
prompt=chapter_prompt(chapter,{'title':'sample'},'面向初学者，保留推导过程，用简短例子解释。')
fingerprint=workspace.ai.estimate(workspace.config(),prompt).fingerprint
workspace.db.cache(fingerprint,'# 欧姆定律\n\n电压、电流、电阻之间满足 **V = IR**。\n\n## 例子\n12 V / 4 Ω = 3 A。\n\n材料来源：PDF 第 1–2 页。')
