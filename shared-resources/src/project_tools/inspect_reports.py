"""Index PDF contents; do not equate figures/reports with raw survey/model files."""
from project_paths import resolve_runtime_path, archive_relative
import json
import re
import sys
from pathlib import Path
import pymupdf

from rdr.storage import DATA, save_json

def main():
    result=[]
    for path in (resolve_runtime_path(DATA/'sources/alberta_flood_studies/static/flood_studies')).rglob('*.pdf'):
        target=resolve_runtime_path(DATA/'processed/report_text'/path.with_suffix('.txt').name)
        index_path=resolve_runtime_path(DATA/'processed/report_text'/path.with_suffix('.index.json').name)
        if index_path.exists():
            result.append(json.loads(index_path.read_text()));continue
        reader=pymupdf.open(path);matches=[];pages=[]
        for i,page in enumerate(reader):
            text=page.get_text() or '';pages.append(f'\n--- PDF PAGE {i+1} ---\n'+text)
            terms=[term for term in ['cross section','cross-section','bathymetr','station-elevation','survey data',
                                   'HEC-RAS','digital data','provided separately','riverbed'] if term.lower() in text.lower()]
            if terms:matches.append({'pdf_page':i+1,'terms':terms})
        target.parent.mkdir(parents=True,exist_ok=True);target.write_text('\n'.join(pages),encoding='utf-8')
        entry={'pdf':str(archive_relative(path, DATA)),'pages':len(reader),'text':str(archive_relative(target, DATA)),
               'keyword_pages':matches,'data_form':'PDF report; raw numerical survey/model files not implied'}
        save_json(index_path,entry);result.append(entry)
        print(path.name,'pages',len(reader),'relevant pages',len(matches),flush=True)
    save_json(resolve_runtime_path(DATA/'reports/pdf_content_inventory.json'),result)

if __name__=='__main__':main()
