from pathlib import Path
import re, json, base64, mimetypes, shutil, subprocess
ROOT = Path('/root/content/sites/abx-ri-estatico')
OUT = Path('/root/data/abx/entregas/APRESENTACAO/ABX_RI_REFERENCIA_JULHO26.html')
ZIP = Path('/root/data/abx/entregas/APRESENTACAO/ABX_RI_REFERENCIA_JULHO26.zip')
html = (ROOT/'index.html').read_text(encoding='utf-8')
# Inline all CSS imported by app.css; browsers do not resolve @import well inside a standalone file.
app_css = (ROOT/'styles/app.css').read_text(encoding='utf-8')
css_parts = []
for m in re.finditer(r"@import url\('./([^']+)'\);", app_css):
    rel = m.group(1).split('?')[0]
    css_parts.append('/* '+rel+' */\n'+(ROOT/'styles'/rel).read_text(encoding='utf-8'))
css = '\n'.join(css_parts)
revision_css = """
.auth-screen .auth-card p:last-child{display:none!important}
"""
html = re.sub(r'<link rel="stylesheet" href="styles/app\.css\?v=[^"]+">', '<style>\n'+css+'\n'+revision_css+'\n</style>', html)
# Versão limpa para apresentação: sem banner/nota de revisão no topo.
# Título original preservado para apresentação aos sócios.
# Inline scripts except boot, then embed data.
script_tags = re.findall(r'\s*<script src="src/([^"?]+)\?v=[^"]+" defer></script>', html)
html = re.sub(r'\s*<script src="src/[^>]+></script>', '', html)
inline = ''
for s in script_tags:
    if s == 'boot.js':
        continue
    inline += f"\n<script>\n/* {s} */\n" + (ROOT/'src'/s).read_text(encoding='utf-8') + "\n</script>\n"
# Embed logos/images referenced in data.json as data URIs where possible.
data = json.loads((ROOT/'data.json').read_text(encoding='utf-8'))
def data_uri(rel):
    p = ROOT/rel
    if not p.exists():
        return rel
    mt = mimetypes.guess_type(str(p))[0] or 'application/octet-stream'
    return 'data:'+mt+';base64,'+base64.b64encode(p.read_bytes()).decode('ascii')
for rep in data.get('reports', {}).values():
    if isinstance(rep, dict):
        for comp in rep.get('companies', []) or []:
            if isinstance(comp, dict) and comp.get('logo_asset'):
                comp['logo_asset'] = data_uri(comp['logo_asset'])
# Organograma source images/PDF links can remain local text in existing JS; add embedded asset map for future JS compatibility.
asset_map = {}
for p in (ROOT/'assets').rglob('*'):
    if p.is_file() and p.suffix.lower() in ['.png','.jpg','.jpeg','.pdf']:
        asset_map[str(p.relative_to(ROOT))] = data_uri(str(p.relative_to(ROOT)))
data.setdefault('meta', {})['status'] = 'REFERENCIA_SOCIOS_NAO_PUBLICADO'
data['meta']['revision_note'] = 'Material de referência para validação interna; não publicado.'
boot = """
<script>
/* embedded data.json — standalone revisão */
const EMBEDDED_ASSETS = ASSET_MAP_JSON;
DATA = DATA_JSON;
initSelection();
setReport('U006');
selectedPeriods = new Set(['Jul/26']);
viewMode = 'sideTotal';
renderSelectors();
render();
initAuth();
</script>
""".replace('DATA_JSON', json.dumps(data, ensure_ascii=False)).replace('ASSET_MAP_JSON', json.dumps(asset_map, ensure_ascii=False))
html = html.replace('</body>', inline + boot + '\n</body>')
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(html, encoding='utf-8')
# ZIP com HTML único para facilitar envio, se o Telegram preferir zip.
if ZIP.exists(): ZIP.unlink()
shutil.make_archive(str(ZIP.with_suffix('')), 'zip', OUT.parent, OUT.name)
print('HTML', OUT, OUT.stat().st_size)
print('ZIP', ZIP, ZIP.stat().st_size)
