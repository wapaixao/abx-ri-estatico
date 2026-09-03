from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils import get_column_letter

U006_COMPANY = '006 - Campo Grande'


def n(v: Any) -> float:
    if v is None or v == '':
        return 0.0
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(float(v)) else 0.0
    try:
        return float(str(v).replace('.', '').replace(',', '.'))
    except Exception:
        return 0.0


def clean(v: Any) -> str:
    return str(v or '').strip()


def row_by_desc(dru_report: dict, desc: str) -> dict | None:
    target = clean(desc).upper()
    for row in dru_report.get('rows', []):
        if clean(row.get('descricao')).upper() == target:
            return row
    return None


def ensure_dru_row(dru_report: dict, codigo: str, descricao: str, nivel: int = 2) -> dict:
    row = row_by_desc(dru_report, descricao)
    if row:
        return row
    companies = dru_report.get('companies', [])
    periods = dru_report.get('periods', [])
    row = {
        'codigo': codigo,
        'secao': 'DRE/DRU',
        'nivel': nivel,
        'descricao': descricao,
        'empresas': {c['name']: {p: 0 for p in periods} for c in companies},
        'grupo': {p: 0 for p in periods},
    }
    dru_report.setdefault('rows', []).append(row)
    return row


def ensure_empresas(row: dict, dru_report: dict) -> None:
    for comp in dru_report.get('companies', []):
        vals = row.setdefault('empresas', {}).setdefault(comp['name'], {})
        for period in dru_report.get('periods', []):
            vals.setdefault(period, 0)
    row.setdefault('grupo', {})
    for period in dru_report.get('periods', []):
        row['grupo'].setdefault(period, 0)


def iter_sheet_blocks(u006_report: dict) -> list[dict]:
    """Return U006 sheet column blocks using row 3 merged-cell spans.

    The extracted sheet stores merged header cells with colspan (`cs`) and skips covered
    cells. Value rows keep physical columns. Therefore the logical start column must be
    reconstructed by accumulating `cs` from the header row.
    """
    rows = u006_report.get('rows', [])
    if len(rows) < 4:
        return []
    header = rows[2]
    period_row = rows[3]
    blocks = []
    col = 0
    for cell in header:
        name = clean(cell.get('v'))
        span = int(cell.get('cs') or 1)
        periods = []
        for off in range(span):
            ci = col + off
            if ci < len(period_row):
                p = clean(period_row[ci].get('v'))
                if p:
                    periods.append((p, ci))
        if name:
            blocks.append({'name': name, 'start': col, 'span': span, 'periods': periods})
        col += span
    return blocks


def find_block(blocks: list[dict], predicate) -> dict | None:
    return next((b for b in blocks if predicate(b['name'])), None)


def ensure_u006_result_row(u006_report: dict, length: int) -> list[dict]:
    rows = u006_report.setdefault('rows', [])
    rows[:] = [r for r in rows if not (len(r) > 1 and clean(r[1].get('v')).startswith('RESULTADO GERENCIAL U006'))]
    def blank():
        return {'v': '', 'cs': 1, 'rs': 1, 'style': {'bg': '#B9D99E'}}
    result = [blank() for _ in range(length)]
    result[0] = {'v': 'TOTAL', 'cs': 1, 'rs': 1, 'style': {'bg': '#B9D99E', 'color': '#102B17', 'bold': True}}
    result[1] = {'v': 'RESULTADO GERENCIAL U006 (A-B + ADM)', 'cs': 1, 'rs': 1, 'style': {'bg': '#B9D99E', 'color': '#102B17', 'bold': True}}
    rows.append(result)
    return result


def set_sheet_value(rows: list, ri: int, ci: int, value: float | int, bg: str | None = None, bold: bool = False) -> None:
    while len(rows[ri]) <= ci:
        rows[ri].append({'v': '', 'cs': 1, 'rs': 1, 'style': {}})
    rows[ri][ci]['v'] = int(round(value)) if abs(value - round(value)) < 0.005 else round(value, 2)
    style = rows[ri][ci].setdefault('style', {})
    style['color'] = '#C00000' if value < 0 else '#000000'
    if bg:
        style['bg'] = bg
    if bold:
        style['bold'] = True


def _base_cell(value: Any = '', bg: str | None = None, bold: bool = False) -> dict:
    style = {}
    if bg:
        style['bg'] = bg
    if bold:
        style['bold'] = True
    if isinstance(value, (int, float)) and value < 0:
        style['color'] = '#C00000'
    return {'v': value, 'cs': 1, 'rs': 1, 'style': style}


def append_u006_month_from_contrib_workbook(data: dict, workbook_path: str | Path, period: str, sheet_name: str) -> dict:
    """Append/refresh monthly period in DATA.reports.U006 from Contrib Financeira sheet.

    Source layout: row 1 unit headers, row 2 A, row 3 B, row 4 A-B, row 5 ADM.
    Idempotent: removes an existing column for `period` before appending it to every block.
    """
    from openpyxl import load_workbook

    u006 = data.setdefault('reports', {}).get('U006')
    if not u006:
        return {'applied': False, 'reason': 'missing U006 report'}
    path = Path(workbook_path)
    if not path.exists():
        return {'applied': False, 'reason': f'missing workbook {path}'}
    wb = load_workbook(path, data_only=True, read_only=True)
    if sheet_name not in wb.sheetnames:
        return {'applied': False, 'reason': f'missing sheet {sheet_name}'}
    ws = wb[sheet_name]
    units = [clean(ws.cell(1, c).value) for c in range(2, ws.max_column + 1)]
    vals = {
        'A': {units[i - 2]: n(ws.cell(2, i).value) for i in range(2, ws.max_column + 1)},
        'B': {units[i - 2]: n(ws.cell(3, i).value) for i in range(2, ws.max_column + 1)},
        'AB': {units[i - 2]: n(ws.cell(4, i).value) for i in range(2, ws.max_column + 1)},
        'ADM': {units[i - 2]: n(ws.cell(5, i).value) for i in range(2, ws.max_column + 1)},
    }
    rows = u006.setdefault('rows', [])
    if len(rows) < 8:
        return {'applied': False, 'reason': 'U006 report too short'}

    # Idempotência segura: se o período já existe, não reinserir nem mexer nos colspans.
    # O build principal parte da planilha trimestral limpa; scripts mensais podem rodar depois.
    if any(clean(cell.get('v')) == period for cell in rows[3]):
        return {'applied': True, 'period': period, 'source': str(path), 'already_present': True}

    blocks = iter_sheet_blocks(u006)
    insertions = []
    for b in blocks:
        name = b['name']
        # Only append period columns to real unit/totalizer blocks. Never append values under
        # the fixed Conta/Descrição blocks; that creates the visible "0" description shift.
        if not (name.startswith('TOTAL') or name.startswith('DEMAIS') or (len(name) >= 3 and name[:3].isdigit())):
            continue
        key = 'GERAL' if name.startswith('TOTAL GERAL') else ('DEMAIS' if name.startswith('DEMAIS') else ('TOTAL' if name.startswith('TOTAL FILIAIS') else name[:3]))
        insertions.append((b['start'] + b['span'], key, name))

    for insert_at, key, block_name in sorted(insertions, reverse=True):
        if key == 'DEMAIS':
            a = bv = ab = adm = 0
        elif key in {'TOTAL', 'GERAL'}:
            a, bv, ab, adm = vals['A'].get('TOTAL', 0), vals['B'].get('TOTAL', 0), vals['AB'].get('TOTAL', 0), vals['ADM'].get('TOTAL', 0)
        else:
            unit_label = next((u for u in units if u.startswith(key + ' - ')), None)
            a, bv, ab, adm = vals['A'].get(unit_label, 0), vals['B'].get(unit_label, 0), vals['AB'].get(unit_label, 0), vals['ADM'].get(unit_label, 0)
        values_by_row = {3: period, 4: round(a), 5: round(bv), 6: round(ab), 7: round(adm)}
        for ri, row in enumerate(rows):
            if ri == 2:
                continue
            value = values_by_row.get(ri, '')
            row.insert(insert_at, _base_cell(value, bg=('#1F5F2F' if ri == 3 else ('#D8EAD1' if ri == 6 else None)), bold=ri in {3, 6}))
        for cell in rows[2]:
            if clean(cell.get('v')) == block_name:
                cell['cs'] = int(cell.get('cs') or 1) + 1
                break

    rows[0][0]['v'] = 'RECEITA GERENCIAL U006 — 1T, 2T E JUL/26'
    u006['source_update_note'] = f'{period} alimentado automaticamente por {path.name}/{sheet_name}; regra estrutural U006 aplicada no build.'
    return {'applied': True, 'period': period, 'source': str(path)}


def apply_u006_structural_rules(data: dict, audit_path: str | Path | None = None) -> dict:
    """Apply Wagner's permanent U006/Campo Grande managerial rule to all existing periods.

    Rule, independent of month/quarter:
    CF líquida U006 = CF cobrada de todas as unidades (filiais + demais unidades/Pedras) -
    despesa financeira efetiva de todas as unidades (DRE 261001-261006).
    Resultado/incremento gerencial = CF líquida U006 + contribuição administrativa das unidades
    administradas pela matriz/filiais, sem Demais Empresas/Pedras.

    The audit is written to a separate workbook/file when requested; it is not embedded in
    the partners presentation.
    """
    reports = data.setdefault('reports', {})
    u006 = reports.get('U006')
    dru = reports.get('DRU')
    if not u006 or not dru:
        return {'applied': False, 'reason': 'missing DRU or U006 report'}

    blocks = iter_sheet_blocks(u006)
    b_u006 = find_block(blocks, lambda s: s.startswith('006'))
    b_filiais = find_block(blocks, lambda s: s.upper().startswith('TOTAL FILIAIS'))
    b_demais = find_block(blocks, lambda s: s.upper().startswith('DEMAIS'))
    b_total = find_block(blocks, lambda s: s.upper().startswith('TOTAL GERAL'))
    if not b_u006 or not b_filiais:
        return {'applied': False, 'reason': 'missing U006 or TOTAL FILIAIS block'}

    rows = u006['rows']
    max_len = max(len(r) for r in rows)
    result_row = ensure_u006_result_row(u006, max_len)

    # DRU rows needed in the presentation. Create if missing so future builds don't silently skip.
    old_cf_row = row_by_desc(dru, 'CONTRIBUIÇÃO FINANCEIRA FILIAIS')
    if old_cf_row:
        old_cf_row['descricao'] = 'CONTRIBUIÇÃO FINANCEIRA LÍQUIDA U006'
    cf_row = ensure_dru_row(dru, 'AJ006FINFIL', 'CONTRIBUIÇÃO FINANCEIRA LÍQUIDA U006')
    adm_row = ensure_dru_row(dru, 'AJ006ADM', 'CONTRIBUIÇÃO ADMINISTRATIVA FILIAIS')
    lair_original = row_by_desc(dru, 'LAIR')
    lair_ger = ensure_dru_row(dru, 'AJ006LAIR', 'LAIR GERENCIAL', 1)
    irpj = ensure_dru_row(dru, 'AJ006IRPJ', 'IRPJ SOBRE NOVO LAIR (25%)')
    csll = ensure_dru_row(dru, 'AJ006CSLL', 'CSLL SOBRE NOVO LAIR (9%)')
    novo_ll = ensure_dru_row(dru, 'AJ006LL', 'NOVO LUCRO LÍQUIDO', 1)
    ll_ger = ensure_dru_row(dru, 'AJ006LLGER', 'LUCRO LÍQUIDO GERENCIAL', 1)
    for row in [cf_row, adm_row, lair_ger, irpj, csll, novo_ll, ll_ger]:
        ensure_empresas(row, dru)

    period_to_u006_col = {p: ci for p, ci in b_u006['periods']}
    period_to_filiais_col = {p: ci for p, ci in b_filiais['periods']}
    period_to_demais_col = {p: ci for p, ci in (b_demais or {}).get('periods', [])}
    period_to_total_col = {p: ci for p, ci in (b_total or {}).get('periods', [])}

    audit_rows = []
    for period, u_col in period_to_u006_col.items():
        if period not in period_to_filiais_col:
            continue
        f_col = period_to_filiais_col[period]
        # A vem de todas as unidades cobradas (filiais + demais/Pedras). Se não houver bloco Total Geral
        # no período, cai com segurança para Total Filiais.
        a_source_col = period_to_total_col.get(period, f_col)
        a_total_unidades = n(rows[4][a_source_col].get('v'))
        b_source_col = period_to_total_col.get(period, u_col)
        b_total_unidades = n(rows[5][b_source_col].get('v'))
        # ADM vem só das unidades administradas pela matriz/filiais; Demais/Pedras ficam fora.
        adm_total_filiais = n(rows[7][f_col].get('v'))
        cf_liquida = a_total_unidades - b_total_unidades
        incremento = cf_liquida + adm_total_filiais

        # U006 grid: show the structural/economic U006 calculation in the Campo Grande column.
        set_sheet_value(rows, 4, u_col, a_total_unidades)
        set_sheet_value(rows, 5, u_col, b_total_unidades)
        set_sheet_value(rows, 6, u_col, cf_liquida, bg='#D8EAD1', bold=True)
        set_sheet_value(rows, 7, u_col, adm_total_filiais)
        set_sheet_value([result_row], 0, u_col, incremento, bg='#B9D99E', bold=True)
        # Total Filiais must close with its own block values (A-B + ADM), not repeat U006's
        # managerial result. U006 uses A and B from Total Geral, while ADM excludes Demais/Pedras.
        f_a, f_b, f_adm = n(rows[4][f_col].get('v')), n(rows[5][f_col].get('v')), n(rows[7][f_col].get('v'))
        set_sheet_value(rows, 6, f_col, f_a - f_b, bg='#D8EAD1', bold=True)
        set_sheet_value([result_row], 0, f_col, (f_a - f_b) + f_adm, bg='#B9D99E', bold=True)

        # Make Demais and Total Geral blocks internally consistent whenever present.
        if period in period_to_demais_col:
            d_col = period_to_demais_col[period]
            d_a, d_b, d_adm = n(rows[4][d_col].get('v')), n(rows[5][d_col].get('v')), n(rows[7][d_col].get('v'))
            set_sheet_value(rows, 6, d_col, d_a - d_b, bg='#D8EAD1', bold=True)
            set_sheet_value([result_row], 0, d_col, (d_a - d_b) + d_adm, bg='#B9D99E', bold=True)
        if period in period_to_total_col:
            t_col = period_to_total_col[period]
            t_a, t_b = n(rows[4][t_col].get('v')), n(rows[5][t_col].get('v'))
            d_adm = n(rows[7][period_to_demais_col[period]].get('v')) if period in period_to_demais_col else 0
            # Total Geral must sum the displayed blocks. ADM excludes Demais/Pedras, so it equals
            # Total Filiais ADM + Demais ADM (normally zero), not the legacy source Total Geral ADM.
            t_adm = f_adm + d_adm
            set_sheet_value(rows, 6, t_col, t_a - t_b, bg='#D8EAD1', bold=True)
            set_sheet_value(rows, 7, t_col, t_adm)
            set_sheet_value([result_row], 0, t_col, (t_a - t_b) + t_adm, bg='#B9D99E', bold=True)

        if period in dru.get('periods', []) and U006_COMPANY in cf_row.get('empresas', {}):
            cf_row['empresas'][U006_COMPANY][period] = round(cf_liquida)
            adm_row['empresas'][U006_COMPANY][period] = round(adm_total_filiais)
            lair0 = n((lair_original or {}).get('empresas', {}).get(U006_COMPANY, {}).get(period))
            lair_val = lair0 + incremento
            irpj_val = -(lair_val * 0.25) if lair_val > 0 else 0
            csll_val = -(lair_val * 0.09) if lair_val > 0 else 0
            ll_val = lair_val + irpj_val + csll_val
            lair_ger['empresas'][U006_COMPANY][period] = round(lair_val)
            irpj['empresas'][U006_COMPANY][period] = round(irpj_val, 2)
            csll['empresas'][U006_COMPANY][period] = round(csll_val, 2)
            novo_ll['empresas'][U006_COMPANY][period] = round(ll_val, 2)
            ll_ger['empresas'][U006_COMPANY][period] = round(ll_val, 2)
            audit_rows.append({
                'periodo': period,
                'cf_cobrada_unidades': round(a_total_unidades),
                'despesa_financeira_unidades_dre_261001_261006': round(b_total_unidades),
                'contrib_financeira_liquida': round(cf_liquida),
                'contrib_administrativa': round(adm_total_filiais),
                'incremento_gerencial': round(incremento),
                'lair_original': round(lair0),
                'lair_gerencial': round(lair_val),
                'irpj_25': round(irpj_val, 2),
                'csll_9': round(csll_val, 2),
                'lucro_liquido_gerencial': round(ll_val, 2),
            })

    u006['source_update_note'] = 'Regra estrutural U006 aplicada: CF líquida = CF cobrada de todas as unidades (filiais + demais unidades/Pedras) - despesa financeira efetiva de todas as unidades DRE 261001-261006; resultado gerencial = CF líquida + contribuição administrativa das filiais/matriz, sem Demais Empresas/Pedras.'
    dru['source_update_note'] = (dru.get('source_update_note', '') + ' | Regra U006 estrutural aplicada automaticamente para todos os períodos existentes.').strip(' |')

    if audit_path:
        write_u006_audit(audit_rows, audit_path)
    return {'applied': True, 'periods': audit_rows}


def write_u006_audit(audit_rows: list[dict], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = 'Auditoria U006 oculta'
    headers = [
        'Período', 'CF cobrada unidades', 'Desp. financeira unidades DRE 261001-261006',
        'Contrib. financeira líquida', 'Contrib. administrativa', 'Incremento gerencial',
        'LAIR original', 'LAIR gerencial', 'IRPJ 25%', 'CSLL 9%', 'Lucro líquido gerencial'
    ]
    ws.append(headers)
    fill = PatternFill('solid', fgColor='1F5B45')
    thin = Side(style='thin', color='B7C9BE')
    for c in range(1, len(headers) + 1):
        cell = ws.cell(1, c)
        cell.fill = fill
        cell.font = Font(color='FFFFFF', bold=True)
        cell.alignment = Alignment(horizontal='center', wrap_text=True)
        cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for row in audit_rows:
        ws.append([
            row['periodo'], row['cf_cobrada_unidades'], row['despesa_financeira_unidades_dre_261001_261006'],
            row['contrib_financeira_liquida'], row['contrib_administrativa'], row['incremento_gerencial'],
            row['lair_original'], row['lair_gerencial'], row['irpj_25'], row['csll_9'], row['lucro_liquido_gerencial']
        ])
    for r in range(2, ws.max_row + 1):
        for c in range(2, ws.max_column + 1):
            ws.cell(r, c).number_format = '#,##0;[Red]-#,##0;0'
    for c in range(1, ws.max_column + 1):
        ws.column_dimensions[get_column_letter(c)].width = 18 if c > 1 else 12
    # Hidden workbook sheet: audit exists in the file but is not a presentation element.
    ws.sheet_state = 'visible'
    wb.save(path)
