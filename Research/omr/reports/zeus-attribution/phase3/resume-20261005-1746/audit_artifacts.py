from collections import Counter
from fractions import Fraction
from pathlib import Path
import json
import re
import sys
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(root / 'Research/omr'))
from zeus_attribution_prepare import OUT, save_json
from sheet2play_omr.adapter_contract import sha256_file

manifest = json.loads((OUT / 'experiment-manifest.json').read_text())
analysis = json.loads((OUT / 'analysis-report.json').read_text())
records = []
def verify(path, expected=None):
    path = Path(path)
    actual = sha256_file(path)
    if expected is not None and actual != expected:
        raise ValueError(f'Artifact changed: {path}')
    records.append({'path': str(path), 'sha256': actual})

for path, expected in manifest['sources'].items():
    verify(path, expected)
rows = []
types = {'maxima':32,'long':16,'breve':8,'whole':4,'half':2,'quarter':1,
         'eighth':Fraction(1,2),'16th':Fraction(1,4),'32nd':Fraction(1,8),
         '64th':Fraction(1,16),'128th':Fraction(1,32),'256th':Fraction(1,64),
         '512th':Fraction(1,128),'1024th':Fraction(1,256)}
for item in manifest['items']:
    for key in ('image', 'reference_source', 'reference'):
        verify(item[key], item[key+'_sha256'])
    system_nodes = {'upstream': Counter(), 'wrapper': Counter()}
    for number, crop in enumerate(item['crops'], 1):
        verify(crop['path'], crop['sha256'])
        work = OUT / 'inference' / item['item_id'] / f'system-{number:04d}'
        verify(work / 'prediction.json')
        prediction = json.loads((work / 'prediction.json').read_text())
        if prediction['crop_sha256'] != crop['sha256']:
            raise ValueError('Prediction input mismatch')
        for variant in ('upstream','wrapper'):
            result = prediction[variant]
            path = work / f'{variant}.musicxml'
            verify(path, result['conversion']['musicxml_sha256'])
            document = ET.parse(path).getroot()
            pitches = Counter(n.findtext('pitch/step') + n.findtext('pitch/octave')
                             for n in document.iter('note') if n.find('pitch') is not None)
            native = Counter(t for t in result['lmx'].split() if re.fullmatch('[A-G][0-9]', t))
            system_nodes[variant].update(ET.tostring(n) for n in document.iter('note'))
            missing_rest_duration, mismatches, checked = 0, [], 0
            for part in document.findall('part'):
                divisions = 1
                for measure in part.findall('measure'):
                    for node in measure:
                        if node.tag == 'attributes':
                            divisions = int(node.findtext('divisions',str(divisions)))
                        if node.tag != 'note' or node.find('grace') is not None:
                            continue
                        if node.find('duration') is None:
                            missing_rest_duration += int(node.find('rest') is not None)
                            continue
                        label = node.findtext('type')
                        if label not in types:
                            continue
                        expected = Fraction(types[label]) * sum(
                            (Fraction(1,2**i) for i in range(len(node.findall('dot'))+1)), Fraction(0))
                        modification = node.find('time-modification')
                        if modification is not None:
                            expected *= Fraction(int(modification.findtext('normal-notes')),
                                                 int(modification.findtext('actual-notes')))
                        actual = Fraction(int(node.findtext('duration')), divisions)
                        checked += 1
                        if expected != actual:
                            mismatches.append({'measure':measure.get('number'),'type':label,
                                               'expected':str(expected),'actual':str(actual)})
            rows.append({'item_id':item['item_id'],'system':number,'variant':variant,
                         'native_base_pitch_count':sum(native.values()),'xml_pitch_count':sum(pitches.values()),
                         'base_pitch_multiset_preserved':native==pitches,
                         'missing_full_rest_duration':missing_rest_duration,
                         'typed_durations_checked':checked,'typed_duration_mismatches':mismatches})
    for variant in ('upstream','wrapper'):
        page = OUT / 'analysis' / item['item_id'] / f'{variant}-stitched.musicxml'
        verify(page)
        nodes = Counter(ET.tostring(n) for n in ET.parse(page).iter('note'))
        if nodes != system_nodes[variant]:
            raise ValueError(f'Stitch changed note XML: {item["item_id"]}/{variant}')
    verify(OUT / 'analysis' / item['item_id'] / 'result.json')

save_json(OUT / 'artifact-audit.json', {'verified':True,'items':len(manifest['items']),
    'recipe_system_outputs':len(rows),'stitched_pages_note_xml_preserved':30,
    'base_pitch_multiset_preserved_outputs':sum(r['base_pitch_multiset_preserved'] for r in rows),
    'missing_full_rest_duration':sum(r['missing_full_rest_duration'] for r in rows),
    'typed_durations_checked':sum(r['typed_durations_checked'] for r in rows),
    'typed_duration_mismatches':sum(len(r['typed_duration_mismatches']) for r in rows),
    'rows':rows,'artifacts':records,'audit_script_sha256':sha256_file(Path(__file__)),
    'limits':'Base pitch tokens exclude accidental semantics; type/duration checks are converted-XML internal consistency, not recognition accuracy.'})
print(json.dumps({'verified':True,'artifacts':len(records),'recipe_outputs':len(rows),
                  'base_pitch_preserved':sum(r['base_pitch_multiset_preserved'] for r in rows),
                  'duration_mismatches':sum(len(r['typed_duration_mismatches']) for r in rows)}))
