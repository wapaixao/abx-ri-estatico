#!/usr/bin/env python3
"""Atualiza a base local do RI ABX com DRUs Julho/2026 recebidos via Telegram.

Não publica. Preserva fontes em /root/data/abx/dru_bp_julho_2026_recebidos_2026-08-18/raw.
"""
from __future__ import annotations

import json, shutil, re, math
from pathlib import Path
from datetime import datetime
import openpyxl
from abx_u006_rules import apply_u006_structural_rules, append_u006_month_from_contrib_workbook

ROOT = Path('/root/content/sites/abx-ri-estatico')
DATA = ROOT/'data.json'
RAW_DIR = Path('/root/data/abx/dru_bp_julho_2026_recebidos_2026-08-18/raw')
RAW_DIR.mkdir(parents=True, exist_ok=True)

DRU_SOURCES = {
    '001': Path('/root/.hermes/profiles/abx/cache/documents/doc_0942e21b4b8b_DRU_001.xlsx'),
    '002': Path('/root/.hermes/profiles/abx/cache/documents/doc_dd3462f6df17_DRU_002.xlsx'),
    '003': Path('/root/.hermes/profiles/abx/cache/documents/doc_98c56cb46315_DRU_003.xlsx'),
    '005': Path('/root/.hermes/profiles/abx/cache/documents/doc_df81e443ade9_DRU_005.xlsx'),
    '006': Path('/root/.hermes/profiles/abx/cache/documents/doc_fac130d161c4_DRU_006.xlsx'),
    '007': Path('/root/.hermes/profiles/abx/cache/documents/doc_f613b9d6b4df_DRU_007.xlsx'),
    '008': Path('/root/.hermes/profiles/abx/cache/documents/doc_f4e57731c817_DRU_008.xlsx'),
    '009': Path('/root/.hermes/profiles/abx/cache/documents/doc_eb3a00f46d28_DRU_009.xlsx'),
    '011': Path('/root/.hermes/profiles/abx/cache/documents/doc_6c03e5484de6_DRU_011.xlsx'),
}
BP_SOURCE = Path('/root/.hermes/profiles/abx/cache/documents/doc_d609beb0565c_BP 2025 new.xlsx')

UNIT_NAMES = {
    '001': '001 - Porto Velho', '002': '002 - Cuiabá', '003': '003 - São Paulo',
    '004': '004 - Rio Paranaíba', '005': '005 - Dracena', '006': '006 - Campo Grande',
    '007': '007 - Belém', '008': '008 - Vacaria', '009': '009 - Manaus',
    '010': '010 - Petrolina', '011': '011 - Rio Branco',
    '050': '050 - Hortivan', '100': '100 - Top Frutas', '101': '101 - Água Branca', '103': '103 - Top Verde',
    'TOTAL FILIAIS 001-011': 'TOTAL FILIAIS 001-011', 'TOTAL GRUPO': 'TOTAL GRUPO'
}

# linhas sintéticas/gerenciais que devem continuar no DRU RI; AJ006 fica pendente sem DRE/Receita U006 de julho.
GERENCIAL_ROWS = {
    'AJ006ADM','AJ006FINFIL','AJ006FINDEM','AJ006LAIR','AJ006IRPJ','AJ006CSLL','AJ006LL'
}

EXCLUDE_DESC = {'DISTRIBUICAO LUCRO','DISTRIBUICAO DE LUCROS','PARTICIPACAO NOS RESULTADOS'}


def n(v):
    if v is None or v == '' or (isinstance(v, str) and v.strip().upper() in {'NAN', '-'}):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(float(v)) else 0.0
    try:
        return float(str(v).replace('.', '').replace(',', '.'))
    except Exception:
        return 0.0


def clean_text(v):
    return re.sub(r'\s+', ' ', str(v or '')).strip()


def copy_sources():
    for code, src in DRU_SOURCES.items():
        dst = RAW_DIR/f'DRU_{code}.xlsx'
        if src.exists():
            shutil.copy2(src, dst)
        elif not dst.exists():
            raise FileNotFoundError(f'Fonte DRU {code} não encontrada no cache nem em {dst}')
    if BP_SOURCE.exists():
        shutil.copy2(BP_SOURCE, RAW_DIR/'BP_Agua_Branca_consolidado_julho_2026.xlsx')


def parse_dru_jul(src: Path):
    wb = openpyxl.load_workbook(src, data_only=True, read_only=True)
    ws = wb.active
    header_row = None; value_col = None
    for r in range(1, min(40, ws.max_row)+1):
        vals = [clean_text(ws.cell(r, c).value) for c in range(1, ws.max_column+1)]
        if 'CONTA' in vals and 'DESCRIÇÃO' in vals:
            header_row = r
            for c in range(1, ws.max_column+1):
                if clean_text(ws.cell(r, c).value) == '07/26':
                    value_col = c
                    break
            break
    if not header_row or not value_col:
        raise RuntimeError(f'Não achei cabeçalho/coluna 07/26 em {src}')
    out = {}
    order = []
    seen_row_values = set()
    for r in range(header_row+1, ws.max_row+1):
        code = clean_text(ws.cell(r, 2).value)
        desc = clean_text(ws.cell(r, 4).value)
        if not code and not desc:
            continue
        if desc.upper() in EXCLUDE_DESC:
            continue
        if code.startswith('=') or desc.startswith('='):
            continue
        val = n(ws.cell(r, value_col).value)
        # Conta '00' aparece em várias linhas sintéticas (Receita Líquida, EBITDA, LAIR, Lucro Líquido).
        # Portanto a chave precisa combinar conta + descrição; usar só a conta mistura linhas distintas.
        key = f'{code}|{clean_text(desc).upper()}' if code else clean_text(desc).upper()
        # Export do sistema repete blocos/linhas em alguns arquivos; deduplicar por conta+descrição+valor.
        sig = (key, round(val, 6))
        if sig in seen_row_values:
            continue
        seen_row_values.add(sig)
        if key not in out:
            order.append(key)
            out[key] = {'codigo': code, 'descricao': desc, 'valor': 0.0}
        out[key]['valor'] += val
    return out, order


def row_level(code, desc):
    du = (desc or '').upper()
    if du in ['RECEITA LIQUIDA','RECEITA BRUTA','LUCRO BRUTO','EBITDA','LAIR','LUCRO LIQUIDO','LAIR GERENCIAL','NOVO LUCRO LÍQUIDO','LUCRO LÍQUIDO GERENCIAL']:
        return 1
    if len(str(code or '')) <= 4 or str(code or '').startswith('AJ') or not code:
        return 2
    return 3


def update_dru_report(data):
    report = data['reports']['DRU']
    period = 'Jul/26'
    if period not in report['periods']:
        report['periods'].append(period)
    # ensure companies 001-011 + totals + demais remain present
    existing_names = [c['name'] for c in report['companies']]
    for code in ['001','002','003','004','005','006','007','008','009','010','011','TOTAL FILIAIS 001-011','050','100','101','103','TOTAL GRUPO']:
        name = UNIT_NAMES[code]
        if name not in existing_names:
            report['companies'].append({'name': name, 'code': code if code[:3].isdigit() else 'TOTAL'})
            existing_names.append(name)
    parsed = {}
    seen_order = []
    for code, src in DRU_SOURCES.items():
        actual_src = src if src.exists() else RAW_DIR/f'DRU_{code}.xlsx'
        rows, order = parse_dru_jul(actual_src)
        parsed[code] = rows
        for k in order:
            if k not in seen_order:
                seen_order.append(k)
    # missing units = no movement
    for code in ['004','010']:
        parsed[code] = {}

    by_code_desc = {(str(r.get('codigo','')).strip(), clean_text(r.get('descricao','')).upper()): r for r in report['rows']}
    by_code = {str(r.get('codigo','')).strip(): r for r in report['rows'] if str(r.get('codigo','')).strip() and str(r.get('codigo','')).strip() != '00'}
    by_desc = {clean_text(r.get('descricao','')).upper(): r for r in report['rows'] if clean_text(r.get('descricao',''))}

    def ensure_periods(row):
        for comp in report['companies']:
            vals = row.setdefault('empresas', {}).setdefault(comp['name'], {})
            for p in report['periods']:
                vals.setdefault(p, 0)
        row.setdefault('grupo', {})
        for p in report['periods']:
            row['grupo'].setdefault(p, 0)

    for r in report['rows']:
        ensure_periods(r)
        # default zero for all July values; preserve old periods
        for comp in report['companies']:
            r['empresas'][comp['name']][period] = 0
        r['grupo'][period] = 0

    # add raw rows not already in base
    for key in seen_order:
        sample = next((parsed[u][key] for u in parsed if key in parsed[u]), None)
        if not sample: continue
        code = sample['codigo']; desc = sample['descricao']
        if (code, clean_text(desc).upper()) in by_code_desc or code in by_code or clean_text(desc).upper() in by_desc:
            continue
        row = {'codigo': code, 'secao': 'DRE/DRU', 'nivel': row_level(code, desc), 'descricao': desc, 'empresas': {}, 'grupo': {}}
        ensure_periods(row)
        report['rows'].append(row)
        by_code_desc[(code, clean_text(desc).upper())] = row
        if code and code != '00': by_code[code] = row
        by_desc[clean_text(desc).upper()] = row

    # load filial values
    for code in ['001','002','003','004','005','006','007','008','009','010','011']:
        name = UNIT_NAMES[code]
        for key, rec in parsed[code].items():
            row = by_code_desc.get((rec['codigo'], clean_text(rec['descricao']).upper())) or by_code.get(rec['codigo']) or by_desc.get(clean_text(rec['descricao']).upper())
            if row:
                row['empresas'][name][period] = round(rec['valor'])

    # Regra fiscal validada por Wagner: quando o LAIR do período é negativo,
    # não há IRPJ/CSLL a provisionar. Para apresentação RI, zerar 28/2810/281001/281002
    # e manter Lucro Líquido igual ao LAIR nesses casos.
    lair_row = by_desc.get('LAIR')
    lucro_row = by_desc.get('LUCRO LIQUIDO')
    tax_rows = [by_desc.get(d) for d in ['IMPOSTOS','IMPOSTOS FEDERAIS','CONTRIBUICAO SOCIAL','IMPOSTO DE RENDA PJ']]
    if lair_row and lucro_row:
        for code in ['001','002','003','004','005','006','007','008','009','010','011']:
            name = UNIT_NAMES[code]
            lair_val = n(lair_row['empresas'].get(name,{}).get(period))
            if lair_val < 0:
                for tr in tax_rows:
                    if tr:
                        tr['empresas'][name][period] = 0
                lucro_row['empresas'][name][period] = round(lair_val)

    # total filiais and grupo for July; demais empresas absent = zero/no movement per Wagner's instruction for this set.
    filial_names = [UNIT_NAMES[c] for c in ['001','002','003','004','005','006','007','008','009','010','011']]
    demais_names = [UNIT_NAMES[c] for c in ['050','100','101','103']]
    for row in report['rows']:
        ensure_periods(row)
        total_filiais = sum(n(row['empresas'].get(name,{}).get(period)) for name in filial_names)
        row['empresas'][UNIT_NAMES['TOTAL FILIAIS 001-011']][period] = round(total_filiais)
        for dn in demais_names:
            row['empresas'][dn][period] = 0
        total_grupo = total_filiais
        row['empresas'][UNIT_NAMES['TOTAL GRUPO']][period] = round(total_grupo)
        row['grupo'][period] = round(total_grupo)

    # Sem DRE/Receita U006, manter ajuste gerencial de julho em zero e marcar lucro gerencial igual ao lucro líquido para não inventar ajuste.
    lucro = by_desc.get('LUCRO LIQUIDO')
    llger = by_desc.get('LUCRO LÍQUIDO GERENCIAL') or by_desc.get('LUCRO LIQUIDO GERENCIAL')
    if lucro and llger:
        for comp in report['companies']:
            llger['empresas'][comp['name']][period] = lucro['empresas'].get(comp['name'],{}).get(period,0)
        llger['grupo'][period] = lucro.get('grupo',{}).get(period,0)
    report['source_update_note'] = 'Jul/26 alimentado a partir dos DRU_001,002,003,005,006,007,008,009,011 recebidos em 18/08/2026; unidades 004 e 010 tratadas como sem movimento; 050/100/101/103 sem fonte neste envio. Ajustes gerenciais U006/PIS/Lucros de Jul/26 dependem de DRE/Receita U006.'
    return parsed

# Simple BP Água Branca extraction: add 31/07/2026 to existing BP rows when source label matches.
def parse_bp_july():
    wb = openpyxl.load_workbook(BP_SOURCE, data_only=False, read_only=False)
    ws = wb['Balanco Analitico']
    jul_col = None
    for c in range(2, ws.max_column+1):
        v = ws.cell(1,c).value
        if hasattr(v, 'date') and v.year == 2026 and v.month == 7:
            jul_col = c; break
    if not jul_col:
        raise RuntimeError('Não achei coluna 31/07/2026 no BP')
    values = {}
    for r in range(2, ws.max_row+1):
        label = clean_text(ws.cell(r,1).value)
        if not label: continue
        val = ws.cell(r,jul_col).value
        # Formula caches are not available; evaluate only direct numeric for line/detail and common source formulas are ignored here.
        if isinstance(val,(int,float)):
            values[label.upper()] = float(val)
    return values


def update_bp_report(data):
    report = data['reports'].get('BP')
    if not report: return {}
    period = '31/07/2026'
    if period not in report['periods']:
        report['periods'].append(period)
    vals = parse_bp_july()
    abx_name = 'Água Branca matriz/filiais'
    matched = 0
    for row in report['rows']:
        for comp in report['companies']:
            row.setdefault('empresas', {}).setdefault(comp['name'], {})
            row['empresas'][comp['name']].setdefault(period, 0)
        row.setdefault('grupo', {}).setdefault(period, 0)
        key = clean_text(row.get('descricao','')).upper()
        if key in vals:
            row['empresas'][abx_name][period] = round(vals[key])
            matched += 1
        # other company periods left zero because source sent is only Água Branca consolidado
        row['grupo'][period] = row['empresas'][abx_name].get(period,0)
    report['source_update_note'] = '31/07/2026 alimentado do BP consolidado Água Branca recebido em 18/08/2026; demais empresas não foram atualizadas neste envio.'
    return {'matched_rows': matched, 'available_labels': len(vals)}


def audit_dru(parsed):
    wanted = ['RECEITA LIQUIDA','EBITDA','LUCRO LIQUIDO']
    rows = []
    for code in ['001','002','003','004','005','006','007','008','009','010','011']:
        vals = {}
        for label in wanted:
            rec = next((r for r in parsed.get(code,{}).values() if clean_text(r['descricao']).upper()==label), None)
            vals[label] = round(rec['valor']) if rec else 0
        rows.append((code, vals))
    return rows


def main():
    copy_sources()
    backup = DATA.with_suffix(f'.backup_julho_2026_{datetime.now():%Y%m%d_%H%M%S}.json')
    shutil.copy2(DATA, backup)
    data = json.loads(DATA.read_text(encoding='utf-8'))
    parsed = update_dru_report(data)
    append_u006_month_from_contrib_workbook(
        data,
        Path('/root/data/abx/entregas/APRESENTACAO/ABX_DRE_Apuracoes_Julho_2026_BASE_RI_PREVIA.xlsx'),
        'Jul/26',
        'Contrib Financeira Jul26'
    )
    apply_u006_structural_rules(
        data,
        ROOT/'audit_hidden'/'AUDITORIA_U006_REGRA_ESTRUTURAL_JULHO.xlsx'
    )
    # BP julho preservado como fonte, mas não alimentado automaticamente no RI:
    # depende de auditoria PL/passivo antes de apresentação/publicação.
    bp_info = {'status': 'preservado_sem_atualizar_ri', 'motivo': 'aguardando auditoria BP/PL'}
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print('BACKUP_DATA', backup)
    print('RAW_DIR', RAW_DIR)
    print('DRU_AUDIT_JUL')
    print('unidade|receita_liquida|ebitda|lucro_liquido')
    for code, vals in audit_dru(parsed):
        print(f"{code}|{vals['RECEITA LIQUIDA']}|{vals['EBITDA']}|{vals['LUCRO LIQUIDO']}")
    print('BP_INFO', bp_info)

if __name__ == '__main__':
    main()
