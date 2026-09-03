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
  assert(elems.tables.innerHTML.includes('10.783.261'), 'Aba PL deve destacar Reserva de Lucros 30/06 corrigida');
  assert(elems.tables.innerHTML.includes('10.987.631'), 'Aba PL deve destacar Total da Reserva de Lucros 30/06 corrigido');
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
    '1T26': { cf: 1820931, adm: 775710, lairGer: 1642638, llGer: 1084141.08 },
    '2T26': { cf: 1492756, adm: 843850, lairGer: 1392571, llGer: 919096.86 },
    'Jul/26': { cf: 250177, adm: 282727, lairGer: 575347, llGer: 379729.02 },
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

  vm.runInContext('reportType="DRU"; initSelection(); selected=new Set(["006 - Campo Grande"]); selectedPeriods=new Set(["Jul/26"]); renderSelectors(); render();', sandbox);
  assert(!elems.tables.innerHTML.includes('MATERIAIS PARA OBRA'), 'DRU deve ocultar Materiais para obra quando zerado');

  console.log('OK — regressões ABX RI passaram');
}

run();
