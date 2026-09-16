const fs = require('fs');
const vm = require('vm');

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function makeEl() {
  return {
    innerHTML: '',
    textContent: '',
    value: 'sideTotal',
    style: {},
    classList: { toggle() {}, add() {}, remove() {} },
    querySelectorAll() { return []; },
  };
}

function loadDashboard() {
  const html = fs.readFileSync('index.html', 'utf8');
  const scriptSrcs = [...html.matchAll(/<script src="([^"]+)" defer><\/script>/g)].map(m => m[1].split('?')[0]);
  assert(scriptSrcs.length >= 5, 'index.html deve carregar scripts externos ordenados');
  const js = scriptSrcs.map(src => fs.readFileSync(src, 'utf8')).join('\n').replace(/loadData\(\);\s*$/, '');
  const elems = {
    tables: makeEl(), cards: makeEl(), modeSelect: makeEl(), selectorTitle: makeEl(),
    periodSelectors: makeEl(), companySelectors: makeEl(), allBtn: makeEl(),
    summaryPartBtn: makeEl(), summaryAllBtn: makeEl(), summaryPisBtn: makeEl(), summaryLucrosBtn: makeEl(),
    authScreen: makeEl(), passwordInput: makeEl(), passwordError: makeEl(),
  };
  const document = {
    body: { classList: { remove() {}, add() {} } },
    getElementById(id) { return elems[id] || (elems[id] = makeEl()); },
    querySelector() { return makeEl(); },
    querySelectorAll() { return [makeEl(), makeEl(), makeEl()]; },
  };
  const sandbox = {
    document,
    sessionStorage: { getItem() {}, setItem() {} },
    console,
    Intl,
    window: { location: { href: 'https://wapaixao.github.io/abx-ri-estatico/?test=1' } },
    setTimeout,
  };
  vm.createContext(sandbox);
  vm.runInContext(js, sandbox);
  const data = fs.readFileSync('data.json', 'utf8');
  const css = fs.readFileSync('styles/layout-overrides.css', 'utf8');
  vm.runInContext(`DATA=${data};`, sandbox);
  return { sandbox, elems, html, js, css };
}

function run() {
  const { sandbox, elems, html, js, css } = loadDashboard();

  assert(html.includes('styles/app.css'), 'CSS externo deve estar linkado');
  const legacyHtml = fs.readFileSync('abx-ri-2T26.html', 'utf8');
  assert(!/Senha:\s*ABX/i.test(html + legacyHtml), 'Páginas publicadas não devem exibir dica com a senha');
  assert(js.includes('loadData(attempt=1)'), 'data.json deve carregar via loadData com retry');
  assert(js.includes("adjustment_pl_visibility!=='visible'"), 'Visibilidade do ajuste de PL deve respeitar o status auditado');

  assert(/id="btn-DRE"(?![^>]*class="disabled")/.test(html), 'Botão DRE deve estar habilitado');
  assert(css.includes('.report-buttons #btn-DRE{display:inline-flex!important;align-items:center;justify-content:center;text-align:center}'), 'Texto DRE deve estar centralizado no botão');
  const initialData = JSON.parse(fs.readFileSync('data.json', 'utf8'));
  assert(initialData.reports.DRE, 'data.json deve conter o relatório DRE');
  assert(JSON.stringify(initialData.reports.DRE.periods) === JSON.stringify(['1T26', '2T26', 'Jul/26']), 'DRE deve conter 1T26, 2T26 e Jul/26');
  assert(initialData.reports.DRE.companies.some(c => c.code === '004'), 'DRE deve preservar unidade 004');
  assert(initialData.reports.DRE.companies.some(c => c.code === '010'), 'DRE deve preservar unidade 010');
  assert(initialData.reports.DRE.coverage['004 - Rio Paranaíba']['2T26'] === false, 'DRE 004 2T26 deve ser marcado sem movimento');
  assert(initialData.reports.DRE.coverage['010 - Petrolina']['Jul/26'] === false, 'DRE 010 Jul/26 deve ser marcado sem movimento');
  assert(initialData.reports.DRE.coverage['050 - Hortivan']['Jul/26'] === false, 'DRE 050 Jul/26 deve ser marcado sem movimento');
  assert(!JSON.stringify(initialData.reports.DRE.sources).includes('/root/'), 'DRE publicado não deve expor caminhos absolutos do servidor');
  vm.runInContext('reportType="DRE"; initSelection(); selected=new Set(["004 - Rio Paranaíba"]); selectedPeriods=new Set(["2T26"]); renderSelectors(); render();', sandbox);
  assert(elems.tables.innerHTML.includes('sem-movimento'), 'DRE deve renderizar coluna opaca de período sem movimento');
  assert(elems.tables.innerHTML.includes('Sem movimento'), 'DRE deve identificar visualmente período sem movimento');

  vm.runInContext('reportType="DRU"; initSelection(); renderSelectors(); render();', sandbox);
  assert(elems.cards.innerHTML.includes('1T26 + 2T26'), 'DRU cards devem somar 1T26 + 2T26 quando ambos selecionados');

  vm.runInContext('reportType="RESUMO"; initSelection(); summaryMetric="all"; summaryParticipations=false; renderSelectors(); render();', sandbox);
  assert(elems.tables.innerHTML.includes('TOTAL SELECIONADO'), 'Resumo Tudo deve renderizar total selecionado');
  assert(elems.tables.innerHTML.includes('period-sep'), 'Resumo deve ter divisor entre trimestres');
  assert(elems.tables.innerHTML.includes('PIS/COFINS'), 'Resumo Tudo deve conter PIS/COFINS');
  assert(elems.tables.innerHTML.includes('Lucros a Distribuir'), 'Resumo Tudo deve conter Lucros a Distribuir');

  vm.runInContext("setSummaryMetric('piscofins')", sandbox);
  assert(elems.tables.innerHTML.includes('Só PIS/COFINS'), 'Resumo PIS deve alterar título');
  assert(!elems.tables.innerHTML.includes('Lucro Líquido DRU'), 'Resumo PIS não deve exibir Lucro Líquido DRU');

  vm.runInContext("setSummaryMetric('lucros')", sandbox);
  assert(elems.tables.innerHTML.includes('Só Lucros'), 'Resumo Lucros deve alterar título');
  assert(elems.tables.innerHTML.includes('Lucro Líquido DRU'), 'Resumo Lucros deve exibir Lucro Líquido DRU');
  assert(!elems.tables.innerHTML.includes('PIS/COFINS</th>'), 'Resumo Lucros não deve exibir coluna PIS/COFINS');

  vm.runInContext('summaryParticipations=true; render();', sandbox);
  assert(elems.tables.innerHTML.includes('Resumo — Participações por sócio'), 'Resumo Participações deve renderizar sócios');
  assert(elems.tables.innerHTML.includes('Maior Total'), 'Participações deve ter ordenador Maior Total');

  vm.runInContext('reportType="PL"; initSelection(); renderSelectors(); render();', sandbox);
  assert(elems.tables.innerHTML.includes('Patrimônio Líquido'), 'Aba PL deve renderizar título/linha de PL');
  assert(elems.tables.innerHTML.includes('10.783.261'), 'Aba PL deve destacar Reserva de Lucros 30/06 corrigida');
  assert(elems.tables.innerHTML.includes('10.987.631'), 'Aba PL deve destacar Total da Reserva de Lucros 30/06 corrigido');
  assert(!elems.tables.innerHTML.includes('108.550'), 'Aba PL não deve exibir nota explicativa sobre o ajuste gerencial');
  assert(!elems.tables.innerHTML.includes('31/03/2026'), 'Aba PL não deve exibir coluna 31/03/2026');
  assert(elems.tables.innerHTML.includes('30/06/2026'), 'Aba PL deve exibir coluna 30/06/2026');
  assert(elems.tables.innerHTML.includes('Devedores duvidosos'), 'Aba PL deve trazer notas explicativas');

  vm.runInContext('reportType="U006"; initSelection(); renderSelectors(); render();', sandbox);
  assert(elems.periodSelectors.innerHTML.includes('1T26') && elems.periodSelectors.innerHTML.includes('2T26'), 'Campo Grande deve exibir botões de trimestre');
  assert(elems.companySelectors.innerHTML.includes('001') && elems.companySelectors.innerHTML.includes('103'), 'Campo Grande deve exibir botões das unidades');
  assert(elems.tables.innerHTML.includes('001 - Porto') && elems.tables.innerHTML.includes('103 - Top Verde'), 'Campo Grande deve renderizar unidades selecionadas');

  vm.runInContext('reportType="DISTRIB"; initSelection(); selectedPeriods=new Set(["2º TRIM 2026"]); selected=new Set(["BELEM - 007"]); render();', sandbox);
  assert(elems.tables.innerHTML.includes('481.461'), 'Lucros 007 2T deve mostrar Resultado 481.461');
  assert(elems.tables.innerHTML.includes('-25.680'), 'Lucros 007 2T deve abater Negativo Anterior -25.680');
  assert(elems.tables.innerHTML.includes('455.781'), 'Lucros 007 2T deve mostrar Resultado Líquido 455.781');

  const data = JSON.parse(fs.readFileSync('data.json', 'utf8'));

  const bp = data.reports.BP;
  const bpSubtotal = bp.rows.find(r => r.descricao === 'Ativo Não Circulante');
  const bpDetailLabels = [
    'Aplicações e Seguros Resgatáveis',
    'Capitalizações',
    'Renegociações de Longo Prazo',
    'Créditos de ICMS',
    'Créditos de PIS e COFINS',
    'Imobilizado',
    'Obras / Construções em Bens de Terceiros',
    'Intangível',
  ];
  const bpDetails = bpDetailLabels.map(label => {
    const row = bp.rows.find(r => r.descricao === label);
    assert(row, `BP deve conter detalhe do Ativo Não Circulante: ${label}`);
    return row;
  });
  for (const company of bp.companies.filter(c => !String(c.name).startsWith('TOTAL'))) {
    for (const period of bp.periods) {
      const detailTotal = bpDetails.reduce((sum, row) => sum + (row.empresas[company.name]?.[period] || 0), 0);
      const subtotal = bpSubtotal.empresas[company.name]?.[period] || 0;
      assert(Math.abs(detailTotal - subtotal) <= 1, `Ativo Não Circulante deve fechar para ${company.name} em ${period}`);
    }
  }

  const pncSubtotal = bp.rows.find(r => r.descricao === 'Passivo Não Circulante');
  const pncDetailLabels = [
    'Banco do Brasil — Longo Prazo',
    'Bradesco — Longo Prazo',
    'Arrendamentos / Leasing — Longo Prazo',
    'Débitos Previdenciários / Tributários — Longo Prazo',
    'Outras Obrigações Não Circulantes',
  ];
  const pncDetails = pncDetailLabels.map(label => {
    const row = bp.rows.find(r => r.descricao === label);
    assert(row, `BP deve conter detalhe do Passivo Não Circulante: ${label}`);
    return row;
  });
  for (const company of bp.companies.filter(c => !String(c.name).startsWith('TOTAL'))) {
    for (const period of bp.periods) {
      const detailTotal = pncDetails.reduce((sum, row) => sum + (row.empresas[company.name]?.[period] || 0), 0);
      const subtotal = pncSubtotal.empresas[company.name]?.[period] || 0;
      assert(Math.abs(detailTotal - subtotal) <= 1, `Passivo Não Circulante deve fechar para ${company.name} em ${period}`);
    }
  }
  for (const period of bp.periods) {
    const detailTotal = pncDetails.reduce((sum, row) => sum + (row.grupo[period] || 0), 0);
    assert(Math.abs(detailTotal - (pncSubtotal.grupo[period] || 0)) <= 1, `Passivo Não Circulante do grupo deve fechar em ${period}`);
  }

  vm.runInContext('reportType="BP"; initSelection(); selected=new Set(["HortiVan"]); selectedPeriods=new Set(["30/06/2026"]); render();', sandbox);
  assert(elems.tables.innerHTML.includes('Banco do Brasil — Longo Prazo'), 'BP deve renderizar abertura bancária do Passivo Não Circulante');
  assert(elems.tables.innerHTML.includes('Bradesco — Longo Prazo'), 'BP deve renderizar abertura do Bradesco no Passivo Não Circulante');
  assert(!elems.tables.innerHTML.includes('Outras Obrigações Não Circulantes'), 'BP deve ocultar detalhe residual zerado');

  vm.runInContext('reportType="BP"; initSelection(); selected=new Set(["Água Branca matriz/filiais"]); render();', sandbox);
  assert(elems.tables.innerHTML.includes('Créditos de PIS e COFINS'), 'BP deve renderizar detalhe do Ativo Não Circulante');
  assert(elems.tables.innerHTML.includes('16.928.587'), 'BP deve manter o subtotal de Ativo Não Circulante de 30/06/2026');

  const bpRow = label => bp.rows.find(r => r.descricao === label);
  const maringa = 'Água Branca Maringá';
  const topFrutas = 'Top Morena / Top Frutas';
  assert(bp.companies.some(c => c.name === maringa && c.code === '101-M'), 'BP deve manter Maringá como unidade 101-M separada');
  assert(bp.companies.some(c => c.name === topFrutas && c.code === '100'), 'BP deve manter Top Frutas/Top Morena como unidade 100 separada');
  assert(bpRow('ATIVO').empresas[maringa]['30/06/2026'] === 6073963, 'Maringá deve usar Ativo 30/06 do BPG_2026');
  assert(bpRow('PATRIMÔNIO LÍQUIDO').empresas[maringa]['30/06/2026'] === -881854, 'Maringá deve usar PL 30/06 do BPG_2026');
  assert(bpRow('ATIVO').empresas[topFrutas]['30/06/2026'] === 6414951, 'Top Frutas deve usar Ativo 30/06 do BALANCO_2026');
  assert(bpRow('PATRIMÔNIO LÍQUIDO').empresas[topFrutas]['30/06/2026'] === 1617464, 'Top Frutas deve usar PL 30/06 do BALANCO_2026');
  assert(bpRow('PATRIMÔNIO LÍQUIDO').empresas['Água Branca matriz/filiais']['30/06/2026'] === 15891811, 'BP Água Branca deve usar o PL contábil da fonte');
  assert(!data.reports.PL.scope_note, 'Relatório PL não deve carregar nota explicativa do ajuste gerencial');
  const topVerde = 'Top Verde';
  assert(bpRow('Salários e Contribuições').empresas[topVerde]['31/12/2025'] === 72221, 'Top Verde deve reconhecer Salrios/Salários em 31/12/2025');
  assert(bpRow('Salários e Contribuições').empresas[topVerde]['31/03/2026'] === 92205, 'Top Verde deve reconhecer Salrios/Salários em 31/03/2026');
  assert(bpRow('Salários e Contribuições').empresas[topVerde]['30/06/2026'] === 68741, 'Top Verde deve reconhecer Salrios/Salários em 30/06/2026');
  for (const company of bp.companies.map(c => c.name)) {
    for (const period of bp.periods) {
      assert(bpRow('ATIVO').empresas[company][period] === bpRow('PASSIVO TOTAL').empresas[company][period], `BP fonte deve fechar Ativo=Passivo para ${company}, ${period}`);
    }
  }
  for (const period of bp.periods) {
    assert(bpRow('ATIVO').grupo[period] === bpRow('PASSIVO TOTAL').grupo[period], `BP consolidado deve fechar Ativo=Passivo em ${period}`);
  }
  assert(bp.pl_audit_status === 'audited', 'PL deve estar marcado como auditado');
  assert(bp.pl_audit_date === '14/09/2026', 'PL deve registrar a data da auditoria');
  assert(bp.adjustment_pl_visibility === 'visible', 'Ajuste / Reclassificação PL deve estar visível após auditoria');
  assert(bp.source_units[maringa] === 'BPG_2026.xlsx', 'Rastreabilidade de Maringá deve apontar para BPG_2026.xlsx');
  assert(bp.source_units[topFrutas] === 'BALANCO_2026.xlsx', 'Rastreabilidade de Top Frutas deve apontar para BALANCO_2026.xlsx');
  assert(bp.source_units[topVerde] === 'BP_103_Top_Verde_2026.xlsx', 'Rastreabilidade de Top Verde deve apontar para a fonte 103');
  vm.runInContext('reportType="BP"; initSelection(); selectedPeriods=new Set(["30/06/2026"]); render();', sandbox);
  assert(elems.tables.innerHTML.includes('Ajuste / Reclassificação PL'), 'BP auditado deve renderizar a linha de ajuste/reclassificação do PL');

  const rows = data.reports.U006.rows;
  let checked = 0;
  for (let ci = 2; ci < rows[3].length; ci++) {
    if (!rows[3][ci] || !['1T26', '2T26', 'Jul/26'].includes(rows[3][ci].v)) continue;
    const A = rows[4][ci]?.v || 0;
    const B = rows[5][ci]?.v || 0;
    const AB = rows[6][ci]?.v || 0;
    assert(Math.abs((A - B) - AB) <= 1, `U006 A-B não fecha na coluna ${ci}`);
    checked++;
  }
  assert(checked > 20, 'U006 deve validar múltiplas colunas/períodos');

  const dru = data.reports.DRU;
  const u006Name = '006 - Campo Grande';
  const findDru = (desc) => dru.rows.find(r => String(r.descricao || '').toUpperCase() === desc);
  const cf = findDru('CONTRIBUIÇÃO FINANCEIRA LÍQUIDA U006').empresas[u006Name];
  const adm = findDru('CONTRIBUIÇÃO ADMINISTRATIVA FILIAIS').empresas[u006Name];
  const lair = findDru('LAIR').empresas[u006Name];
  const lairGer = findDru('LAIR GERENCIAL').empresas[u006Name];
  const irpj = findDru('IRPJ SOBRE NOVO LAIR (25%)').empresas[u006Name];
  const csll = findDru('CSLL SOBRE NOVO LAIR (9%)').empresas[u006Name];
  const llGer = findDru('LUCRO LÍQUIDO GERENCIAL').empresas[u006Name];
  const expected = {
    '1T26': { cf: 1305283, adm: 775710, lairGer: 1126990, llGer: 743813.40 },
    '2T26': { cf: 921655, adm: 843850, lairGer: 821470, llGer: 542170.20 },
    'Jul/26': { cf: 240603, adm: 282727, lairGer: 565773, llGer: 373410.18 },
  };
  for (const [p, e] of Object.entries(expected)) {
    if (!dru.periods.includes(p)) continue;
    assert(Math.abs(cf[p] - e.cf) <= 1, `U006 CF estrutural ${p} incorreta`);
    assert(Math.abs(adm[p] - e.adm) <= 1, `U006 ADM ${p} incorreta`);
    assert(Math.abs(lairGer[p] - e.lairGer) <= 1, `U006 LAIR gerencial ${p} incorreto`);
    assert(Math.abs(irpj[p] - (-lairGer[p] * 0.25)) <= 1, `U006 IRPJ ${p} incorreto`);
    assert(Math.abs(csll[p] - (-lairGer[p] * 0.09)) <= 1, `U006 CSLL ${p} incorreta`);
    assert(Math.abs(llGer[p] - e.llGer) <= 1, `U006 Lucro Líquido Gerencial ${p} incorreto`);
    assert(Math.abs(lairGer[p] - (lair[p] + cf[p] + adm[p])) <= 1, `U006 LAIR gerencial ${p} deve partir do LAIR original + ajustes`);
  }

  const totalizerNames = ['TOTAL FILIAIS 001 A 011', 'DEMAIS EMPRESAS', 'TOTAL GERAL'];
  for (const name of totalizerNames) {
    const header = rows[2];
    let col = 0;
    for (const cell of header) {
      const h = String(cell.v || '').trim();
      const span = cell.cs || 1;
      if (h === name) {
        for (let off = 0; off < span; off++) {
          const ci = col + off;
          const p = rows[3][ci]?.v;
          if (!['1T26', '2T26', 'Jul/26'].includes(p)) continue;
          const ab = rows[6][ci]?.v || 0;
          const admv = rows[7][ci]?.v || 0;
          const result = rows[8][ci]?.v || 0;
          assert(Math.abs((ab + admv) - result) <= 1, `${name} ${p} deve fechar Resultado = A-B + ADM`);
          if (name === 'TOTAL GERAL') {
            const header = rows[2];
            let fCol = null, dCol = null, pos = 0;
            for (const hcell of header) {
              const hname = String(hcell.v || '').trim();
              const hspan = hcell.cs || 1;
              if (hname === 'TOTAL FILIAIS 001 A 011') fCol = pos + off;
              if (hname === 'DEMAIS EMPRESAS') dCol = pos + off;
              pos += hspan;
            }
            if (fCol !== null && dCol !== null) {
              const expectedAdm = (rows[7][fCol]?.v || 0) + (rows[7][dCol]?.v || 0);
              const expectedResult = (rows[8][fCol]?.v || 0) + (rows[8][dCol]?.v || 0);
              assert(Math.abs(admv - expectedAdm) <= 1, `TOTAL GERAL ADM ${p} deve somar Filiais + Demais`);
              assert(Math.abs(result - expectedResult) <= 1, `TOTAL GERAL Resultado ${p} deve somar Filiais + Demais`);
            }
          }
        }
      }
      col += span;
    }
  }

  const dfc = data.reports.DFC;
  assert(dfc, 'data.json deve conter o relatório DFC');
  assert(/id="btn-DFC"/.test(html), 'Botão DFC deve existir no RI');
  assert(html.indexOf('id="btn-BP"') < html.indexOf('id="btn-DRE"') && html.indexOf('id="btn-DRE"') < html.indexOf('id="btn-DFC"'), 'Ordem inicial dos relatórios deve ser BP, DRE, DFC');
  assert(JSON.stringify(dfc.periods) === JSON.stringify(['1T26', '2T26']), 'DFC deve conter somente 1T26 e 2T26');
  assert(dfc.companies.length === 5, 'DFC deve conter os cinco blocos de tesouraria');
  assert(dfc.companies.some(c => c.name === 'Água Branca matriz/filiais'), 'DFC deve consolidar 001-011 no bloco Água Branca');
  assert(!JSON.stringify(dfc.sources).includes('/root/'), 'DFC publicada não deve expor caminhos absolutos do servidor');
  const dfcRows = Object.fromEntries(dfc.rows.map(r => [r.codigo, r]));
  const dfcCompanies = dfc.companies.map(c => c.name);
  for (const company of dfcCompanies) {
    for (const p of dfc.periods) {
      const start = dfcRows.CASH_START.empresas[company][p];
      const fco = dfcRows.FCO.empresas[company][p];
      const fci = dfcRows.FCI.empresas[company][p];
      const fcf = dfcRows.FCF.empresas[company][p];
      const difference = dfcRows.RECON.empresas[company][p];
      const end = dfcRows.CASH_END.empresas[company][p];
      assert(Math.abs(start + fco + fci + fcf + difference - end) <= 1, `DFC ${company} ${p} deve reconciliar caixa`);
      assert(Math.abs(difference) <= 1, `DFC ${company} ${p} deve fechar sem ajustes gerenciais`);
    }
  }
  assert(Math.abs(dfcRows.RECON.empresas['Água Branca matriz/filiais']['2T26']) <= 1, 'DFC Água Branca 2T26 deve estar conciliada');
  assert(Math.abs(dfcRows.RECON.grupo['2T26']) <= 1, 'DFC Grupo 2T26 deve estar conciliada');
  assert(dfc.group_status['2T26'] === 'CONCILIADO', 'DFC Grupo 2T26 deve estar conciliado');
  assert(!JSON.stringify(dfc).includes('108.550'), 'DFC não deve conter nota explicativa sobre o ajuste gerencial');
  assert(Math.abs(dfcRows.FCO.grupo['1T26'] - 2735084) <= 1, 'FCO Grupo 1T26 incorreto');
  assert(Math.abs(dfcRows.FCI.grupo['2T26'] - (-591867)) <= 1, 'FCI Grupo 2T26 incorreto');
  assert(Math.abs(dfcRows.FCF.grupo['2T26'] - 4306845) <= 1, 'FCF Grupo 2T26 incorreto');
  vm.runInContext('reportType="DFC"; initSelection(); selectedPeriods=new Set(["2T26"]); renderSelectors(); render();', sandbox);
  assert(!elems.tables.innerHTML.includes('DFC indireta preliminar'), 'DFC não deve exibir a nota metodológica removida');
  assert(!elems.tables.innerHTML.includes('Elaborada a partir do BP contábil e da DRE formal'), 'DFC não deve exibir texto metodológico removido');
  assert(!elems.tables.innerHTML.includes('108.550'), 'DFC não deve exibir nota explicativa sobre o ajuste gerencial');
  assert(!elems.tables.innerHTML.includes('permanece explicitamente pendente'), 'DFC não deve apresentar o ajuste gerencial como pendência');
  assert(elems.tables.innerHTML.includes('Diferença de conciliação'), 'DFC deve renderizar a diferença de conciliação');
  assert(elems.cards.innerHTML === '', 'DFC não deve renderizar cartões-resumo');
  assert(elems.selectorTitle.textContent === 'Blocos de tesouraria', 'DFC deve identificar corretamente o seletor');

  vm.runInContext('reportType="DRU"; initSelection(); selected=new Set(["006 - Campo Grande"]); selectedPeriods=new Set(["Jul/26"]); renderSelectors(); render();', sandbox);
  assert(!elems.tables.innerHTML.includes('MATERIAIS PARA OBRA'), 'DRU deve ocultar Materiais para obra quando zerado');

  console.log('OK — regressões ABX RI passaram');
}

run();
