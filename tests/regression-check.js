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
  vm.runInContext(`DATA=${data};`, sandbox);
  return { sandbox, elems, html, js };
}

function run() {
  const { sandbox, elems, html, js } = loadDashboard();

  assert(html.includes('styles/app.css'), 'CSS externo deve estar linkado');
  assert(js.includes('loadData(attempt=1)'), 'data.json deve carregar via loadData com retry');
  assert(js.includes("d==='Ajuste / Reclassificação PL'"), 'PL pendente deve continuar oculto');

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
  assert(elems.tables.innerHTML.includes('9.148.550'), 'Aba PL deve destacar Reserva de Lucros 31/03');
  assert(elems.tables.innerHTML.includes('10.891.811'), 'Aba PL deve destacar Reserva de Lucros 30/06');
  assert(elems.tables.innerHTML.includes('31/03/2026'), 'Aba PL deve exibir coluna 31/03/2026');
  assert(elems.tables.innerHTML.includes('30/06/2026'), 'Aba PL deve exibir coluna 30/06/2026');
  assert(elems.tables.innerHTML.includes('Devedores duvidosos'), 'Aba PL deve trazer notas explicativas');

  vm.runInContext('reportType="DISTRIB"; initSelection(); selectedPeriods=new Set(["2º TRIM 2026"]); selected=new Set(["BELEM - 007"]); render();', sandbox);
  assert(elems.tables.innerHTML.includes('481.461'), 'Lucros 007 2T deve mostrar Resultado 481.461');
  assert(elems.tables.innerHTML.includes('-25.680'), 'Lucros 007 2T deve abater Negativo Anterior -25.680');
  assert(elems.tables.innerHTML.includes('455.781'), 'Lucros 007 2T deve mostrar Resultado Líquido 455.781');

  const data = JSON.parse(fs.readFileSync('data.json', 'utf8'));
  const rows = data.reports.U006.rows;
  let checked = 0;
  for (let ci = 2; ci < 40; ci++) {
    if (!rows[3][ci] || !['1T26', '2T26'].includes(rows[3][ci].v)) continue;
    const A = rows[4][ci]?.v || 0;
    const B = rows[5][ci]?.v || 0;
    const AB = rows[6][ci]?.v || 0;
    assert(Math.abs((A - B) - AB) <= 1, `U006 A-B não fecha na coluna ${ci}`);
    checked++;
  }
  assert(checked > 20, 'U006 deve validar múltiplas colunas 1T26/2T26');

  console.log('OK — regressões ABX RI passaram');
}

run();
