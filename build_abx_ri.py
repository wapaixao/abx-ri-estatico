import json, re, math, unicodedata
from pathlib import Path
from functools import lru_cache
import openpyxl
from openpyxl.utils import get_column_letter, column_index_from_string, range_boundaries
from abx_u006_rules import apply_u006_structural_rules, append_u006_month_from_contrib_workbook

ROOT = Path('/root/content/sites/abx-ri-estatico')
DATA_PATH = ROOT/'data.json'
DRU_XLSX = Path('/root/data/abx/entregas/APRESENTACAO/ABX_DRU_RI_Receita_Gerencial_U006_VALIDACAO_V5_CF_SPLIT.xlsx')
U006_XLSX = Path('/root/data/abx/entregas/APRESENTACAO/ABX_Receita_Gerencial_U006_1T_2T2026_VALIDACAO_MATRIZ_CORRIGIDA.xlsx')
PISCOFINS_XLSX = Path('/root/data/abx/APURACAO_COFINS_PIS_2T2026_COMPLETA_FORMATADA_SEM_OBS.xlsx')
RESUMO_XLSX = Path('/root/data/abx/APURACAO_COFINS_PIS_2T2026_COMPLETA_FORMATADA_SEM_OBS_COM_RESUMO_VALIDACAO_V4.xlsx')
MONTHLY_U006_SOURCES = [
    {
        'period': 'Jul/26',
        'path': Path('/root/data/abx/entregas/APRESENTACAO/ABX_DRE_Apuracoes_Julho_2026_BASE_RI_PREVIA.xlsx'),
        'sheet': 'Contrib Financeira Jul26',
    },
]

DRE_PERIOD_SOURCES = {
    '1T26': {
        'months': ['01/26', '02/26', '03/26'],
        'folder': Path('/root/data/abx/dru_dre_1T2026_recebidos_2026-07-26/raw'),
        'special_files': {
            '050': 'DRE 050 - Hortivan.xlsx',
            '100': 'DRE 100 - Top Frutas.xlsx',
            '101': 'DRE 101 - Maringa.xlsx',
            '103': 'DRE 103 - Top Verde.xlsx',
        },
    },
    '2T26': {
        'months': ['04/26', '05/26', '06/26'],
        'folder': Path('/root/data/abx/dru_dre_fechado_2T2026/DRE'),
    },
    'Jul/26': {
        'months': ['07/26'],
        'folder': Path('/root/data/abx/dru_bp_julho_2026_recebidos_2026-08-18/raw'),
    },
}

REF_RE = re.compile(r"(?:(?:'([^']+)'|([A-Za-z0-9_À-ÿ ]+))!)?(\$?[A-Z]{1,3}\$?[0-9]{1,5})(?![A-Za-z0-9_])")
RANGE_RE = re.compile(r"(?:(?:'([^']+)'|([A-Za-z0-9_À-ÿ ]+))!)?(\$?[A-Z]{1,3}\$?[0-9]{1,5}):(\$?[A-Z]{1,3}\$?[0-9]{1,5})")

def split_args(s):
    args=[]; cur=''; depth=0
    for ch in s:
        if ch=='(': depth+=1; cur+=ch
        elif ch==')': depth-=1; cur+=ch
        elif ch==',' and depth==0: args.append(cur); cur=''
        else: cur+=ch
    args.append(cur)
    return args

class EvalBook:
    def __init__(self, path):
        self.wb = openpyxl.load_workbook(path, data_only=False, read_only=False)
    def clean_addr(self, addr): return addr.replace('$','')
    @lru_cache(None)
    def val(self, sheet, addr):
        addr=self.clean_addr(addr)
        v=self.wb[sheet][addr].value
        if v is None: return 0.0
        if isinstance(v,(int,float)): return float(v)
        if isinstance(v,str) and v.startswith('='):
            try: return self.eval_formula(sheet, v[1:])
            except Exception: return 0.0
        return v
    def range_sum(self, sheet, rng):
        min_col,min_row,max_col,max_row=range_boundaries(rng.replace('$',''))
        total=0.0
        for r in range(min_row,max_row+1):
            for c in range(min_col,max_col+1):
                v=self.val(sheet, f'{get_column_letter(c)}{r}')
                if isinstance(v,(int,float)): total += v
        return total
    def eval_expr(self, sheet, expr):
        expr=str(expr).strip()
        # SUM(...)
        while re.search(r'\bSUM\(', expr, flags=re.I):
            m=re.search(r'\bSUM\(', expr, flags=re.I)
            start=m.end(); depth=1; i=start
            while i < len(expr) and depth:
                if expr[i]=='(': depth+=1
                elif expr[i]==')': depth-=1
                i+=1
            inside=expr[start:i-1]
            total=0.0
            for arg in split_args(inside):
                arg=arg.strip()
                rm=RANGE_RE.fullmatch(arg)
                if rm:
                    sh=rm.group(1) or rm.group(2) or sheet
                    total += self.range_sum(sh, f'{rm.group(3)}:{rm.group(4)}')
                else:
                    v=self.eval_expr(sheet,arg)
                    if isinstance(v,(int,float)): total += v
            expr=expr[:m.start()] + str(total) + expr[i:]
        expr=re.sub(r'(\d+(?:\.\d+)?)%', lambda m: str(float(m.group(1))/100), expr)
        def repl_ref(m):
            sh=m.group(1) or m.group(2) or sheet
            v=self.val(sh, m.group(3))
            return str(v if isinstance(v,(int,float)) else 0)
        expr=REF_RE.sub(repl_ref, expr).replace('^','**')
        return float(eval(expr, {'__builtins__':{}}, {}))
    def eval_formula(self, sheet, f):
        f=str(f).strip()
        if f.upper().startswith('IFERROR('):
            args=split_args(f[8:-1])
            try: return self.eval_expr(sheet,args[0])
            except Exception: return self.eval_expr(sheet,args[1]) if len(args)>1 else 0.0
        if f.upper().startswith('IF('):
            args=split_args(f[3:-1])
            cond=REF_RE.sub(lambda m: str(self.val(m.group(1) or m.group(2) or sheet,m.group(3))), args[0].replace('%','/100'))
            ok=eval(cond, {'__builtins__':{}}, {})
            return self.eval_expr(sheet,args[1] if ok else args[2])
        return self.eval_expr(sheet,f)

def clean_num(v):
    if isinstance(v,(int,float)):
        if math.isfinite(v) and abs(v-round(v))<1e-7: return int(round(v))
        return float(v)
    return v

def cell_value(eb, sheet, r, c):
    v=eb.wb[sheet].cell(r,c).value
    if isinstance(v,str) and v.startswith('='):
        formula=v[1:].strip()
        m=REF_RE.fullmatch(formula)
        if m:
            v=eb.val(m.group(1) or m.group(2) or sheet, m.group(3))
        else:
            v=eb.val(sheet, f'{get_column_letter(c)}{r}')
    return clean_num(v)

def extract_dru():
    eb=EvalBook(DRU_XLSX); ws=eb.wb['Trimestral - Valores']
    # value columns identified by header row 6 == Valor
    companies=[]; colmap=[]; current=None
    for c in range(3, ws.max_column+1):
        h=ws.cell(4,c).value
        if h: current=str(h).strip()
        if str(ws.cell(6,c).value or '').strip().upper()=='VALOR':
            period=str(ws.cell(5,c).value or '').strip()
            if current and period:
                if current not in [x['name'] for x in companies]:
                    code=current.split(' - ')[0].replace('TOTAL FILIAIS 001-011','TOTAL').replace('TOTAL GRUPO','TOTAL')
                    companies.append({'name':current,'code':code})
                colmap.append((current, period, c))
    periods=[]
    for _,p,_ in colmap:
        if p not in periods: periods.append(p)
    rows=[]
    for r in range(7, ws.max_row+1):
        if ws.row_dimensions[r].hidden: continue
        desc=str(ws.cell(r,2).value or '').strip()
        code=str(ws.cell(r,1).value or '').strip()
        if not desc and not code: continue
        dupper=desc.upper()
        if dupper in ['DISTRIBUICAO LUCRO','DISTRIBUICAO DE LUCROS','PARTICIPACAO NOS RESULTADOS']: continue
        empresas={c['name']:{p:0 for p in periods} for c in companies}
        for comp,p,c in colmap:
            empresas[comp][p]=cell_value(eb,'Trimestral - Valores',r,c) or 0
        if dupper in ['RECEITA LIQUIDA','RECEITA BRUTA','LUCRO BRUTO','EBITDA','LAIR','LUCRO LIQUIDO','LAIR GERENCIAL','NOVO LUCRO LÍQUIDO','LUCRO LÍQUIDO GERENCIAL']:
            nivel=1
        elif len(code)<=4 or code.startswith('AJ') or not code:
            nivel=2
        else:
            nivel=3
        rows.append({'codigo':code,'secao':'DRE/DRU','nivel':nivel,'descricao':desc,'empresas':empresas,'grupo':empresas.get('TOTAL GRUPO',{})})
    return {'label':'Demonstração do Resultado da Unidade (DRU)','periods':periods,'companies':companies,'rows':rows}

def normalized_text(value):
    text=unicodedata.normalize('NFKD', str(value or ''))
    text=''.join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r'\s+', ' ', text).strip().upper()

def normalized_account(value):
    text=str(value or '').strip()
    return text[:-2] if text.endswith('.0') else text

def finite_number(value):
    if isinstance(value,(int,float)) and math.isfinite(value): return float(value)
    return 0.0

def read_dre_period(path, months):
    """Read one DRE export and deduplicate repeated blocks by account+description+values."""
    wb=openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws=wb['Page1'] if 'Page1' in wb.sheetnames else wb[wb.sheetnames[0]]
    raw=list(ws.iter_rows(values_only=True))
    header_idx=-1; month_cols={}
    for idx,row in enumerate(raw[:40]):
        found={str(v).strip():c for c,v in enumerate(row) if v is not None and str(v).strip() in months}
        if len(found)>len(month_cols): header_idx=idx; month_cols=found
    if any(month not in month_cols for month in months):
        raise ValueError(f'Cabeçalhos mensais ausentes em {path}: esperado {months}, localizado {sorted(month_cols)}')
    order=[]; display={}; values={}; seen=set()
    for row in raw[header_idx+1:]:
        account=normalized_account(row[0] if len(row)>0 else '')
        description=str(row[2] if len(row)>2 and row[2] is not None else '').strip()
        if not description: continue
        key=(account, normalized_text(description))
        monthly=tuple(finite_number(row[month_cols[m]] if month_cols[m]<len(row) else 0) for m in months)
        signature=(key,monthly)
        if signature in seen: continue
        seen.add(signature)
        if key not in values:
            order.append(key); display[key]=description; values[key]=0.0
        values[key]+=sum(monthly)
    return order, display, values

def dre_row_sort_key(key, first_seen):
    account,description=key
    special={'RECEITA LIQUIDA':0,'RECEITA BRUTA':9,'LUCRO BRUTO':39,'EBITDA':49,'LAIR':69,'LUCRO LIQUIDO':79}
    if description in special: return (special[description],0,0,first_seen[key])
    groups={'10':10,'15':20,'20':30,'22':40,'24':50,'26':60,'28':70}
    group=next((rank for prefix,rank in groups.items() if account.startswith(prefix)),90)
    level=0 if len(account)<=2 else (1 if len(account)<=4 else 2)
    numeric=int(account) if account.isdigit() else 999999999
    return (group,level,numeric,first_seen[key])

def extract_dre(dru_report):
    periods=list(DRE_PERIOD_SOURCES)
    real_companies=[c for c in dru_report['companies'] if not str(c['name']).startswith('TOTAL')]
    companies=real_companies + [
        {'name':'TOTAL FILIAIS 001-011','code':'TOTAL'},
        {'name':'TOTAL GRUPO','code':'TOTAL'},
    ]
    values_by_company={c['name']:{p:{} for p in periods} for c in real_companies}
    coverage={c['name']:{p:False for p in periods} for c in real_companies}
    display={}; first_seen={}; source_files=[]
    for period,config in DRE_PERIOD_SOURCES.items():
        for company in real_companies:
            code=company['code']
            filename=config.get('special_files',{}).get(code, f'DRE_{code}.xlsx')
            path=config['folder']/filename
            if not path.exists(): continue
            order,local_display,local_values=read_dre_period(path,config['months'])
            coverage[company['name']][period]=True
            values_by_company[company['name']][period]=local_values
            source_files.append({'period':period,'company':company['name'],'file':path.name})
            for key in order:
                if key not in first_seen: first_seen[key]=len(first_seen)
                display.setdefault(key,local_display[key])
    ordered=sorted(first_seen,key=lambda key:dre_row_sort_key(key,first_seen))
    rows=[]
    total_filiais_name='TOTAL FILIAIS 001-011'; total_group_name='TOTAL GRUPO'
    filial_names=[c['name'] for c in real_companies if c['code'].isdigit() and 1<=int(c['code'])<=11]
    all_names=[c['name'] for c in real_companies]
    for key in ordered:
        account,description_key=key; description=display[key]
        empresas={}
        for company in real_companies:
            empresas[company['name']]={p:clean_num(values_by_company[company['name']][p].get(key,0.0)) for p in periods}
        empresas[total_filiais_name]={p:clean_num(sum(empresas[n][p] for n in filial_names)) for p in periods}
        empresas[total_group_name]={p:clean_num(sum(empresas[n][p] for n in all_names)) for p in periods}
        if description_key in ['RECEITA LIQUIDA','RECEITA BRUTA','LUCRO BRUTO','EBITDA','LAIR','LUCRO LIQUIDO']:
            nivel=1
        elif len(account)<=4:
            nivel=2
        else:
            nivel=3
        rows.append({'codigo':account,'secao':'DRE','nivel':nivel,'descricao':description,'empresas':empresas,'grupo':empresas[total_group_name]})
    coverage[total_filiais_name]={p:True for p in periods}
    coverage[total_group_name]={p:True for p in periods}
    return {
        'label':'Demonstração do Resultado do Exercício (DRE)',
        'periods':periods,
        'companies':companies,
        'rows':rows,
        'coverage':coverage,
        'missing_treatment':'Arquivo DRE não recebido: competência tratada como sem movimento e apresentada de forma opaca.',
        'sources':source_files,
    }

def fill_hex(cell):
    fg=cell.fill.fgColor
    if fg.type=='rgb' and fg.rgb and fg.rgb!='00000000': return '#'+fg.rgb[-6:]
    return ''

def font_hex(cell):
    fc=cell.font.color
    try:
        if fc and fc.type=='rgb' and fc.rgb: return '#'+fc.rgb[-6:]
    except Exception: pass
    return ''

def extract_sheet_report(path, sheet, label, max_row=None, max_col=None):
    eb=EvalBook(path); ws=eb.wb[sheet]
    max_row=max_row or ws.max_row; max_col=max_col or ws.max_column
    merged={}
    covered=set()
    for rng in ws.merged_cells.ranges:
        minc,minr,maxc,maxr=rng.bounds
        if minr>max_row or minc>max_col: continue
        merged[(minr,minc)]=(min(maxc,max_col)-minc+1, min(maxr,max_row)-minr+1)
        for rr in range(minr,min(maxr,max_row)+1):
            for cc in range(minc,min(maxc,max_col)+1):
                if (rr,cc)!=(minr,minc): covered.add((rr,cc))
    rows=[]
    for r in range(1,max_row+1):
        if ws.row_dimensions[r].hidden: continue
        row=[]; any_value=False
        for c in range(1,max_col+1):
            if (r,c) in covered: continue
            cell=ws.cell(r,c)
            v=cell_value(eb,sheet,r,c)
            if v not in [None,'']: any_value=True
            cs,rs=merged.get((r,c),(1,1))
            style={}
            bg=fill_hex(cell); color=font_hex(cell)
            if bg: style['bg']=bg
            if color: style['color']=color
            if cell.font.bold: style['bold']=True
            row.append({'v':v if v is not None else '', 'cs':cs, 'rs':rs, 'style':style})
        if any_value or r<=5:
            rows.append(row)
    return {'label':label,'type':'sheet','rows':rows}

def extract_piscofins_control():
    eb=EvalBook(PISCOFINS_XLSX); ws=eb.wb['Cofins e Pis']
    block_rows=[2,11,20,29]
    periods=[]; units=[]; rows_by_desc={}; desc_order=[]
    for br in block_rows:
        period=str(ws.cell(br,1).value or '').strip()
        if not period: continue
        periods.append(period)
        local_units=[]
        for c in range(2, ws.max_column+1):
            name=str(ws.cell(br,c).value or '').strip()
            if not name: continue
            local_units.append((name,c))
            if name not in units: units.append(name)
        for rr in range(br+1, br+6):
            desc=str(ws.cell(rr,1).value or '').strip()
            if not desc: continue
            if desc not in rows_by_desc:
                rows_by_desc[desc]={}; desc_order.append(desc)
            for u in units:
                rows_by_desc[desc].setdefault(u,{})
                for p in periods: rows_by_desc[desc][u].setdefault(p,0)
            for name,c in local_units:
                rows_by_desc[desc][name][period]=cell_value(eb,'Cofins e Pis',rr,c) or 0
    companies=[{'name':u,'code':u.split(' - ')[0]} for u in units]
    outrows=[]
    for desc in desc_order:
        nivel=1 if desc.upper()=='TOTAL' else 2
        outrows.append({'descricao':desc,'nivel':nivel,'empresas':rows_by_desc[desc]})
    return {'label':'PIS / COFINS','type':'unit_period_control','periods':periods,'companies':companies,'rows':outrows}

def apply_2026_negative_previous_rule(report):
    # For Distribuição 2026 blocks only, move negative Resultado to Negativo Anterior.
    for ridx,row in enumerate(report['rows']):
        for i,cell in enumerate(row):
            v=cell.get('v')
            if isinstance(v,str) and '2026' in v:
                try:
                    resultado=report['rows'][ridx+1][i+1]['v']
                    neg_cell=report['rows'][ridx+2][i+1]
                    liq_cell=report['rows'][ridx+3][i+1]
                except Exception:
                    continue
                if isinstance(resultado,(int,float)) and resultado < 0:
                    neg_cell['v']=resultado
                    liq_cell['v']=resultado
    return report

def unit_code_from_label(label):
    s=str(label or '')
    m=re.search(r'(\d{3})', s)
    return m.group(1) if m else None

def apply_dru_lucro_to_distrib(report, dru_report):
    """For 2026 distribution blocks, use DRU Lucro Líquido as Resultado/Lucro source."""
    # Wagner validou que, para Lucros/Distribuição 2026, a base correta é a última linha
    # apresentada do DRU: LUCRO LÍQUIDO GERENCIAL, já considerando os ajustes da U006.
    lucro_rows=[r for r in dru_report['rows'] if str(r.get('descricao','')).strip().upper()=='LUCRO LÍQUIDO GERENCIAL']
    if not lucro_rows:
        lucro_rows=[r for r in dru_report['rows'] if str(r.get('descricao','')).strip().upper()=='LUCRO LIQUIDO']
    if not lucro_rows: return report
    lucro=lucro_rows[0]['empresas']
    dru_by_code={unit_code_from_label(name): vals for name, vals in lucro.items() if unit_code_from_label(name) and not str(name).upper().startswith('TOTAL')}
    header_units=[c.get('v') for c in report['rows'][0] if unit_code_from_label(c.get('v'))]
    periods={'1º TRIM 2026':'1T26','2º TRIM 2026':'2T26'}
    for ridx,row in enumerate(report['rows']):
        vals=[c.get('v') for c in row]
        period_label=next((v for v in vals if isinstance(v,str) and v in periods), None)
        if not period_label: continue
        period=periods[period_label]
        result_label_positions=[i for i,c in enumerate(report['rows'][ridx+1]) if str(c.get('v')).strip().upper()=='RESULTADO']
        partner_label_positions=[i for i,c in enumerate(report['rows'][ridx+4]) if str(c.get('v')).strip().upper()=='PARCEIRO'] if ridx+4 < len(report['rows']) else []
        for idx,label_pos in enumerate(result_label_positions):
            if idx >= len(header_units): break
            code=unit_code_from_label(header_units[idx])
            val=float(dru_by_code.get(code,{}).get(period,0) or 0)
            value_pos=label_pos+1
            if value_pos < len(report['rows'][ridx+1]):
                report['rows'][ridx+1][value_pos]['v']=val if val>0 else 0
            if value_pos < len(report['rows'][ridx+2]):
                report['rows'][ridx+2][value_pos]['v']=val if val<0 else 0
            if value_pos < len(report['rows'][ridx+3]):
                report['rows'][ridx+3][value_pos]['v']=val
            # Distribution values: only distribute positive Resultado Líquido.
            if idx < len(partner_label_positions):
                ppos=partner_label_positions[idx]
                for pr in range(ridx+5, min(ridx+10, len(report['rows']))):
                    if ppos+2 >= len(report['rows'][pr]): continue
                    pct=report['rows'][pr][ppos+1].get('v')
                    partner=report['rows'][pr][ppos].get('v')
                    if partner in ['', None] or not isinstance(pct,(int,float)):
                        if report['rows'][pr][ppos+2].get('v') not in ['', None]: report['rows'][pr][ppos+2]['v']=''
                        continue
                    report['rows'][pr][ppos+2]['v']=(val*pct/100) if val>0 else 0
    return report

def main():
    data=json.loads(DATA_PATH.read_text())
    reports=data.setdefault('reports',{})
    reports['DRU']=extract_dru()
    reports['DRE']=extract_dre(reports['DRU'])
    reports['U006']=extract_sheet_report(U006_XLSX,'Receita Gerencial U006','Receita Gerencial U006',max_row=9,max_col=43)
    monthly_u006 = []
    for src in MONTHLY_U006_SOURCES:
        monthly_u006.append(append_u006_month_from_contrib_workbook(data, src['path'], src['period'], src['sheet']))
    u006_audit = apply_u006_structural_rules(
        data,
        ROOT/'audit_hidden'/'AUDITORIA_U006_REGRA_ESTRUTURAL.xlsx'
    )
    reports['PISCOFINS']=extract_piscofins_control()
    reports['RESUMO']=extract_sheet_report(RESUMO_XLSX,'Resumo','Resumo — PIS/COFINS e Lucros',max_row=20,max_col=10)
    reports['DISTRIB']=apply_dru_lucro_to_distrib(extract_sheet_report(PISCOFINS_XLSX,'APRESENTAÇÃO','Distribuição de Resultado',max_row=51,max_col=60), reports['DRU'])
    DATA_PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print('wrote',DATA_PATH)
    print('reports',list(reports.keys()))
    print('monthly U006 sources', monthly_u006)
    print('U006 structural audit', u006_audit)
    print('DRU rows',len(reports['DRU']['rows']),'PIS rows',len(reports['PISCOFINS']['rows']),'DISTR rows',len(reports['DISTRIB']['rows']))

if __name__=='__main__': main()
