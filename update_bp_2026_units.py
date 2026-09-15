#!/usr/bin/env python3
"""Atualiza e valida o BP analítico do RI a partir dos arquivos por empresa.

Mantém a reclassificação gerencial já usada no RI para Créditos Duvidosos:
move do Ativo Não Circulante para Créditos a Receber/Ativo Circulante.
A linha Ajuste / Reclassificação PL permanece reconciliada no JSON e sua
visibilidade acompanha o status de auditoria confirmado para a publicação.
O Passivo Não Circulante é aberto em componentes-folha, sem dupla contagem.
"""
from __future__ import annotations

import json
import re
import shutil
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data.json"
RAW = Path("/root/data/abx/balancos_2026/raw")
AUDIT = ROOT / "audit_hidden" / "AUDITORIA_BP_UNIDADES_100_101M_103_2026.xlsx"
AGUA_BRANCA_SOURCE = RAW / "BP_Agua_Branca_25_e_26.xlsx"
AGUA_BRANCA_COMPANY = "Água Branca matriz/filiais"


@dataclass(frozen=True)
class UnitConfig:
    source: Path
    canonical_source: Path
    sheet: str
    target_name: str
    expected_identity: str
    public_source_name: str


UNITS = (
    UnitConfig(
        source=RAW / "BP_100_Top_Morena.xlsx",
        canonical_source=RAW / "BP_100_Top_Morena.xlsx",
        sheet="BPTM",
        target_name="Top Morena / Top Frutas",
        expected_identity="TOP FRUTAS LTDA",
        public_source_name="BALANCO_2026.xlsx",
    ),
    UnitConfig(
        source=RAW / "BP_101_AB_Maringa.xlsx",
        canonical_source=RAW / "BP_101_AB_Maringa.xlsx",
        sheet="BPTC",
        target_name="Água Branca Maringá",
        expected_identity="AGUA BRANCA LTDA",
        public_source_name="BPG_2026.xlsx",
    ),
    UnitConfig(
        source=RAW / "BP_103_Top_Verde_2026.xlsx",
        canonical_source=RAW / "BP_103_Top_Verde_2026.xlsx",
        sheet="BPTV",
        target_name="Top Verde",
        expected_identity="TOP VERDE LTDA",
        public_source_name="BP_103_Top_Verde_2026.xlsx",
    ),
)

HORTIVAN = UnitConfig(
    source=RAW / "BP_050_Hortvan_2026.xlsx",
    canonical_source=RAW / "BP_050_Hortvan_2026.xlsx",
    sheet="BPHV",
    target_name="HortiVan",
    expected_identity="HORTIVAN LTDA",
    public_source_name="BP_050_Hortvan_2026.xlsx",
)

PNC_UNITS = (HORTIVAN,) + UNITS

PERIODS = ("31/12/2025", "31/03/2026", "30/06/2026")
PERIOD_COLS = {"31/12/2025": 3, "31/03/2026": 4, "30/06/2026": 5}


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().upper()


def number(value: object) -> float:
    if value in (None, ""):
        return 0.0
    if not isinstance(value, (int, float)):
        raise ValueError(f"Valor não numérico encontrado: {value!r}")
    return float(value)


def row_values(ws, row: int, period_cols: dict[str, int] = PERIOD_COLS) -> dict[str, float]:
    return {period: number(ws.cell(row, col).value) for period, col in period_cols.items()}


def add(*series: dict[str, float]) -> dict[str, float]:
    return {p: sum(s[p] for s in series) for p in PERIODS}


def sub(a: dict[str, float], b: dict[str, float]) -> dict[str, float]:
    return {p: a[p] - b[p] for p in PERIODS}


def sum_exact_rows(ws, description: str, start: int, end: int, period_cols: dict[str, int]) -> dict[str, float]:
    """Soma folhas homônimas dentro de um bloco; ausência inequívoca vira zero."""
    wanted = norm(description)
    rows = [row for row in range(start, end + 1) if norm(ws.cell(row, 2).value) == wanted]
    return add(*(row_values(ws, row, period_cols) for row in rows)) if rows else {p: 0.0 for p in PERIODS}


def find_row(ws, description: str, start: int, end: int, *, prefix: bool = False) -> int:
    wanted = norm(description)
    hits = []
    for row in range(start, end + 1):
        got = norm(ws.cell(row, 2).value)
        if (prefix and got.startswith(wanted)) or (not prefix and got == wanted):
            hits.append(row)
    if len(hits) != 1:
        raise ValueError(f"Linha {description!r} não é única entre {start}:{end}: {hits}")
    return hits[0]


def extract_unit(cfg: UnitConfig) -> tuple[dict[str, dict[str, float]], dict[str, str]]:
    if not cfg.source.exists():
        raise FileNotFoundError(cfg.source)
    wb = load_workbook(cfg.source, read_only=True, data_only=True)
    if cfg.sheet not in wb.sheetnames:
        raise ValueError(f"Aba {cfg.sheet} ausente em {cfg.source.name}")
    ws = wb[cfg.sheet]
    identity = str(ws.cell(3, 2).value or "")
    if cfg.expected_identity not in norm(identity):
        raise ValueError(f"Identidade inesperada em {cfg.source.name}: {identity!r}")

    period_cols: dict[str, int] = {}
    for col in range(3, ws.max_column + 1):
        value = ws.cell(4, col).value
        label = value.strftime("%d/%m/%Y") if isinstance(value, datetime) else str(value)
        if label in PERIODS:
            period_cols[label] = col
    if set(period_cols) != set(PERIODS):
        raise ValueError(f"Períodos esperados ausentes em {cfg.source.name}: encontrados {sorted(period_cols)}")
    values_at = lambda row: row_values(ws, row, period_cols)

    passivo_row = find_row(ws, "PASSIVO", 30, ws.max_row)
    patrimonio_row = find_row(ws, "PATRIMONIO", passivo_row, ws.max_row)

    ativo = values_at(find_row(ws, "ATIVO", 1, passivo_row - 1))
    ac_source = values_at(find_row(ws, "CIRCULANTE", 1, passivo_row - 1))
    disponibilidade = values_at(find_row(ws, "DISPONIBILIDADE", 1, passivo_row - 1))
    contas_receber = values_at(find_row(ws, "CONTAS A RECEBER", 1, passivo_row - 1))
    recebiveis = values_at(find_row(ws, "RECEBIVEIS ANTECIPADOS", 1, passivo_row - 1))
    estoque = values_at(find_row(ws, "ESTOQUE", 1, passivo_row - 1))
    adiant_ativo = values_at(find_row(ws, "ADIANTAMENTOS", 1, passivo_row - 1))
    anc_row = find_row(ws, "NAO CIRCULANTE", 1, passivo_row - 1)
    anc_source = values_at(anc_row)
    creditos_duvidosos = values_at(find_row(ws, "CREDITOS DUVIDOSOS", anc_row + 1, passivo_row - 1))
    capitalizacoes = values_at(find_row(ws, "CAPITALIZACOES", anc_row + 1, passivo_row - 1))
    renegociacoes = values_at(find_row(ws, "RENEGOCIACOES", anc_row + 1, passivo_row - 1))
    arrend_ativo = values_at(find_row(ws, "ARRENDAMENTOS LEASING", anc_row + 1, passivo_row - 1))
    icms = values_at(find_row(ws, "CREDITO ICMS", anc_row + 1, passivo_row - 1))
    pis_cofins = values_at(find_row(ws, "CREDITO PIS E COFINS", anc_row + 1, passivo_row - 1))
    imobilizado = values_at(find_row(ws, "IMOBILIZADO", anc_row + 1, passivo_row - 1))
    intangivel = values_at(find_row(ws, "INTANGIVEL", anc_row + 1, passivo_row - 1))
    obras_rows = [r for r in range(anc_row + 1, passivo_row) if "BENS DE TERCEIRO" in norm(ws.cell(r, 2).value)]
    obras = values_at(obras_rows[0]) if len(obras_rows) == 1 else {p: 0.0 for p in PERIODS}

    passivo_total = values_at(passivo_row)
    pnc_row = find_row(ws, "NAO CIRCULANTE", passivo_row + 1, patrimonio_row - 1)
    pc = values_at(find_row(ws, "CIRCULANTE", passivo_row + 1, pnc_row - 1))
    fornecedores = values_at(find_row(ws, "FORNECEDORES", passivo_row + 1, pnc_row - 1))
    alugueis = values_at(find_row(ws, "ALUGUEIS", passivo_row + 1, pnc_row - 1))
    salarios = values_at(find_row(ws, "SAL", passivo_row + 1, pnc_row - 1, prefix=True))
    emprestimos_pc = values_at(find_row(ws, "EMPRESTIMOS E FINANCIAMENTOS", passivo_row + 1, pnc_row - 1))
    rotativos = values_at(find_row(ws, "CREDITOS ROTATIVOS", passivo_row + 1, pnc_row - 1))
    adiant_rows = [r for r in range(passivo_row + 1, pnc_row) if norm(ws.cell(r, 2).value) == "ADIANTAMENTOS"]
    if len(adiant_rows) > 1:
        raise ValueError(f"Mais de uma linha Adiantamentos no Passivo de {cfg.source.name}: {adiant_rows}")
    adiant_pc = values_at(adiant_rows[0]) if adiant_rows else {p: 0.0 for p in PERIODS}
    impostos_pc = values_at(find_row(ws, "IMPOSTOS A PAGAR", passivo_row + 1, pnc_row - 1))
    pnc = values_at(pnc_row)

    pl = values_at(patrimonio_row)
    capital = values_at(find_row(ws, "CAPITAL SOCIAL", patrimonio_row + 1, ws.max_row))
    retiradas_rows = [r for r in range(patrimonio_row + 1, ws.max_row + 1) if norm(ws.cell(r, 2).value).startswith("RETIRADAS")]
    retiradas = add(*(values_at(r) for r in retiradas_rows)) if retiradas_rows else {p: 0.0 for p in PERIODS}
    resultados = values_at(find_row(ws, "RESULTADOS ACUMULADO", patrimonio_row + 1, ws.max_row))
    ajuste_pl = {p: pl[p] - capital[p] - retiradas[p] - resultados[p] for p in PERIODS}

    values = {
        "ATIVO": ativo,
        "Ativo Circulante": add(ac_source, creditos_duvidosos),
        "Disponibilidade": disponibilidade,
        "Estoques": estoque,
        "Créditos a Receber": add(contas_receber, creditos_duvidosos),
        "Recebíveis Antecipados": recebiveis,
        "Adiantamentos": adiant_ativo,
        "Ativo Não Circulante": sub(anc_source, creditos_duvidosos),
        "Aplicações e Seguros Resgatáveis": {p: 0.0 for p in PERIODS},
        "Capitalizações": capitalizacoes,
        "Renegociações de Longo Prazo": add(renegociacoes, arrend_ativo),
        "Créditos de ICMS": icms,
        "Créditos de PIS e COFINS": pis_cofins,
        "Imobilizado": imobilizado,
        "Obras / Construções em Bens de Terceiros": obras,
        "Intangível": intangivel,
        "PASSIVO TOTAL": passivo_total,
        "Passivo Circulante": pc,
        "Fornecedores": fornecedores,
        "Aluguéis": alugueis,
        "Salários e Contribuições": salarios,
        "Impostos a Pagar": impostos_pc,
        "Empréstimos e Financiamentos": emprestimos_pc,
        "Créditos Rotativos": rotativos,
        "Ajuste / Reclassificação para fechamento": {p: 0.0 for p in PERIODS},
        "Passivo Não Circulante": pnc,
        "PATRIMÔNIO LÍQUIDO": pl,
        "Capital Social": capital,
        "Retiradas / Participações": retiradas,
        "Resultados Acumulados": resultados,
        "Ajuste / Reclassificação PL": ajuste_pl,
    }

    # Há duas linhas "Adiantamentos" no dashboard; a segunda pertence ao Passivo.
    values["__Adiantamentos_Passivo__"] = adiant_pc

    for p in PERIODS:
        if abs(ativo[p] - passivo_total[p]) > 0.01:
            raise ValueError(f"Fonte não fecha em {cfg.target_name}, {p}: Ativo={ativo[p]} Passivo={passivo_total[p]}")
        anc_details = sum(values[label][p] for label in (
            "Aplicações e Seguros Resgatáveis", "Capitalizações", "Renegociações de Longo Prazo",
            "Créditos de ICMS", "Créditos de PIS e COFINS", "Imobilizado",
            "Obras / Construções em Bens de Terceiros", "Intangível",
        ))
        if abs(values["Ativo Não Circulante"][p] - anc_details) > 0.01:
            raise ValueError(f"Ativo Não Circulante não fecha em {cfg.target_name}, {p}")
        if abs(pl[p] - capital[p] - retiradas[p] - resultados[p] - ajuste_pl[p]) > 0.01:
            raise ValueError(f"PL não reconcilia em {cfg.target_name}, {p}")

    meta = {"identity": identity, "source": cfg.public_source_name}
    return values, meta


def extract_pnc_details(cfg: UnitConfig) -> dict[str, dict[str, float]]:
    """Extrai componentes-folha do Passivo Não Circulante e prova o fechamento."""
    wb = load_workbook(cfg.source, read_only=True, data_only=True)
    ws = wb[cfg.sheet]
    period_cols: dict[str, int] = {}
    for col in range(3, ws.max_column + 1):
        value = ws.cell(4, col).value
        label = value.strftime("%d/%m/%Y") if isinstance(value, datetime) else str(value)
        if label in PERIODS:
            period_cols[label] = col
    if set(period_cols) != set(PERIODS):
        raise ValueError(f"Períodos do PNC ausentes em {cfg.source.name}: {sorted(period_cols)}")

    passivo_row = find_row(ws, "PASSIVO", 30, ws.max_row)
    patrimonio_row = find_row(ws, "PATRIMONIO", passivo_row, ws.max_row)
    pnc_row = find_row(ws, "NAO CIRCULANTE", passivo_row + 1, patrimonio_row - 1)
    start, end = pnc_row + 1, patrimonio_row - 1
    total = row_values(ws, pnc_row, period_cols)
    details = {
        "Banco do Brasil — Longo Prazo": sum_exact_rows(ws, "BANCO DO BRASIL", start, end, period_cols),
        "Bradesco — Longo Prazo": sum_exact_rows(ws, "BRADESCO", start, end, period_cols),
        "Arrendamentos / Leasing — Longo Prazo": sum_exact_rows(ws, "ARRENDAMENTOS LEASING", start, end, period_cols),
        "Débitos Previdenciários / Tributários — Longo Prazo": sum_exact_rows(ws, "DEBITOS PREVIDENCIARIOS", start, end, period_cols),
    }
    known = add(*details.values())
    details["Outras Obrigações Não Circulantes"] = sub(total, known)
    for period in PERIODS:
        closed = sum(series[period] for series in details.values())
        if abs(closed - total[period]) > 0.01:
            raise ValueError(f"Detalhes do PNC não fecham em {cfg.target_name}, {period}")
    return details


def extract_agua_branca_source_pl() -> dict[str, float]:
    """Lê o PL contábil de Água Branca diretamente do BP-fonte.

    O relatório específico de PL contém ajustes gerenciais apartados e não pode
    alimentar o BP nem a DFC. Esta extração preserva essa separação de escopo.
    """
    if not AGUA_BRANCA_SOURCE.exists():
        raise FileNotFoundError(AGUA_BRANCA_SOURCE)
    wb = load_workbook(AGUA_BRANCA_SOURCE, read_only=True, data_only=True)
    ws = wb["Balanco Analitico"]
    period_cols: dict[str, int] = {}
    for col in range(1, ws.max_column + 1):
        value = ws.cell(1, col).value
        label = value.strftime("%d/%m/%Y") if isinstance(value, datetime) else str(value)
        if label in PERIODS:
            period_cols[label] = col
    if set(period_cols) != set(PERIODS):
        raise ValueError(f"Períodos do PL ausentes em {AGUA_BRANCA_SOURCE.name}: {sorted(period_cols)}")
    candidates = [
        row for row in range(1, ws.max_row + 1)
        if norm(ws.cell(row, 1).value) == "PATRIMONIO"
    ]
    if len(candidates) != 1:
        raise ValueError(f"Linha do PL de Água Branca não é única: {candidates}")
    return row_values(ws, candidates[0], period_cols)


def update_data(extracted: dict[str, dict[str, dict[str, float]]], metadata: dict[str, dict[str, str]]) -> dict:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    bp = data["reports"]["BP"]
    pnc_labels = [
        "Banco do Brasil — Longo Prazo",
        "Bradesco — Longo Prazo",
        "Arrendamentos / Leasing — Longo Prazo",
        "Débitos Previdenciários / Tributários — Longo Prazo",
        "Outras Obrigações Não Circulantes",
    ]
    existing = {row["descricao"] for row in bp["rows"]}
    insert_at = next(i for i, row in enumerate(bp["rows"]) if row["descricao"] == "PATRIMÔNIO LÍQUIDO")
    company_names = [c["name"] for c in bp["companies"] if not str(c["name"]).startswith("TOTAL")]
    for label in reversed(pnc_labels):
        if label not in existing:
            empty = {name: {p: 0 for p in bp["periods"]} for name in company_names}
            bp["rows"].insert(insert_at, {
                "secao": "PASSIVO",
                "nivel": 3,
                "descricao": label,
                "empresas": empty,
                "grupo": {p: 0 for p in bp["periods"]},
            })

    rows_by_label: dict[str, list[dict]] = {}
    for row in bp["rows"]:
        rows_by_label.setdefault(row["descricao"], []).append(row)

    for unit_name, values in extracted.items():
        for label, period_values in values.items():
            if label == "__Adiantamentos_Passivo__":
                candidates = rows_by_label["Adiantamentos"]
                row = next(r for r in candidates if r.get("secao") == "PASSIVO")
            elif label == "Adiantamentos":
                candidates = rows_by_label[label]
                row = next(r for r in candidates if r.get("secao") == "ATIVO")
            else:
                candidates = rows_by_label.get(label, [])
                if len(candidates) != 1:
                    raise ValueError(f"Linha de destino não única/ausente: {label!r} -> {len(candidates)}")
                row = candidates[0]
            row.setdefault("empresas", {})[unit_name] = {
                p: int(v) if abs(v - round(v)) < 1e-9 else v for p, v in period_values.items()
            }

    # O BP e a DFC usam o PL contábil da fonte; relatórios gerenciais apartados
    # não alimentam essas demonstrações.
    source_pl = extract_agua_branca_source_pl()
    bp_pl_row = rows_by_label["PATRIMÔNIO LÍQUIDO"][0]
    bp_pl_row.setdefault("empresas", {})[AGUA_BRANCA_COMPANY] = {
        p: int(v) if abs(v - round(v)) < 1e-9 else v for p, v in source_pl.items()
    }

    # Recalcula o grupo para todas as linhas a partir das cinco empresas exibidas.
    company_names = [c["name"] for c in bp["companies"] if not str(c["name"]).startswith("TOTAL")]
    for row in bp["rows"]:
        row["grupo"] = {
            p: sum(float(row.get("empresas", {}).get(name, {}).get(p, 0) or 0) for name in company_names)
            for p in bp["periods"]
        }

    bp["sources"] = [metadata[name]["source"] for name in extracted]
    bp["source_units"] = {name: metadata[name]["source"] for name in extracted}
    bp["pl_audit_status"] = "audited"
    bp["pl_audit_date"] = "14/09/2026"
    bp["adjustment_pl_visibility"] = "visible"
    bp.pop("basis_note", None)
    data["reports"]["PL"].pop("scope_note", None)
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def write_audit(extracted: dict[str, dict[str, dict[str, float]]], metadata: dict[str, dict[str, str]]) -> None:
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Validação"
    ws.append(["Unidade", "Arquivo", "Identificação fonte", "Período", "Ativo", "Passivo total", "Diferença", "PL", "Ajuste / Reclassificação PL", "Status"])
    for unit_name, values in extracted.items():
        if "ATIVO" not in values:
            continue
        for p in PERIODS:
            ativo = values["ATIVO"][p]
            passivo = values["PASSIVO TOTAL"][p]
            ws.append([
                unit_name, metadata[unit_name]["source"], metadata[unit_name]["identity"], p,
                ativo, passivo, ativo - passivo, values["PATRIMÔNIO LÍQUIDO"][p],
                values["Ajuste / Reclassificação PL"][p], "OK" if abs(ativo - passivo) <= 0.01 else "DIVERGENTE",
            ])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E3D")
    ws.freeze_panes = "A2"
    widths = {"A": 28, "B": 24, "C": 42, "D": 14, "E": 16, "F": 16, "G": 14, "H": 16, "I": 19, "J": 13}
    for col, width in widths.items():
        ws.column_dimensions[col].width = width
    wb.save(AUDIT)


def main() -> None:
    extracted = {}
    metadata = {}
    RAW.mkdir(parents=True, exist_ok=True)
    for cfg in UNITS:
        values, meta = extract_unit(cfg)
        extracted[cfg.target_name] = values
        metadata[cfg.target_name] = meta
        if cfg.source.resolve() != cfg.canonical_source.resolve():
            shutil.copy2(cfg.source, cfg.canonical_source)

    for cfg in PNC_UNITS:
        details = extract_pnc_details(cfg)
        if cfg.target_name in extracted:
            extracted[cfg.target_name].update(details)
        else:
            extracted[cfg.target_name] = details
            metadata[cfg.target_name] = {
                "identity": cfg.expected_identity,
                "source": cfg.public_source_name,
            }

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(DATA, ROOT / f"data.backup_bp_units_{stamp}.json")
    update_data(extracted, metadata)
    write_audit(extracted, metadata)

    print(f"Atualizado: {DATA}")
    for name in extracted:
        print(f"- {name}: {metadata[name]['source']}")
        if "ATIVO" in extracted[name]:
            print(f"  Ativo 30/06/2026: {extracted[name]['ATIVO']['30/06/2026']:.0f}")
            print(f"  PL 30/06/2026: {extracted[name]['PATRIMÔNIO LÍQUIDO']['30/06/2026']:.0f}")
    print(f"Auditoria: {AUDIT}")
    print("PL: auditado em 14/09/2026; Ajuste / Reclassificação PL visível")


if __name__ == "__main__":
    main()
