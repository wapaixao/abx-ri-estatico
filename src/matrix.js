function dreSemMovimento(company,period){return reportType==='DRE'&&rep().coverage?.[company.name]?.[period]===false}
function drePeriodHeader(company,period,first){const missing=dreSemMovimento(company,period);return '<th class="period-head '+(first?'sep-left ':'')+(missing?'sem-movimento':'')+'"'+(missing?' title="Sem movimento — DRE não recebido"':'')+'>'+esc(period)+(missing?'<small class="movement-status">Sem movimento</small>':'')+'</th>'}
function renderMatrix(){
  const comps=effectiveCompanies(),ps=activePeriods(),rows=rep().rows.filter(shouldShowRow),synthetic=viewMode==='summary',tableMode=synthetic?'sideTotal':viewMode;
  const dfcNote=reportType==='DFC'?'<div class="dfc-disclaimer"><strong>DFC indireta preliminar.</strong> Base exclusiva: BP contábil e DRE formal. O ajuste gerencial de R$ 108.550 do relatório específico de PL não integra esta DFC.</div>':'';
  let out='<section class="panel table-panel report-'+reportType+'"><div class="table-head"><h2>'+esc(rep().label)+' — '+(synthetic?'visualização sintética':(tableMode==='total'?'Total':(ps.length>1?'períodos por bloco':'período por bloco')))+'</h2><span class="pill">'+comps.length+' selecionada(s)'+(synthetic?' · sintético':'')+'</span></div>'+dfcNote+'<div class="table-wrap"><table>';
  if(tableMode==='total'){
    out+='<thead><tr><th class="desc">Descrição</th>'+ps.map((p,i)=>'<th class="period-head '+(i===0?'sep-left':'')+'">'+esc(p)+'</th>').join('')+'</tr></thead><tbody>';
    rows.forEach(r=>{out+='<tr class="lvl'+Math.floor(Number(r.nivel))+'"><td class="desc" title="'+esc(r.descricao)+'">'+esc(r.descricao)+'</td>'+ps.map((p,i)=>cell(rowTotal(r,p),i===0?'sep-left':'',true)).join('')+'</tr>'});
  }else{
    out+='<thead><tr><th class="desc" rowspan="2">Descrição</th>'+comps.map((c,i)=>'<th class="company-head '+(i===0?'sep-left ':'')+(ps.every(p=>dreSemMovimento(c,p))?'sem-movimento':'')+'" colspan="'+ps.length+'">'+esc(displayHeader(c))+'</th>').join('')+(tableMode==='sideTotal'?'<th class="company-head sep-left" colspan="'+ps.length+'">TOTAL</th>':'')+'</tr><tr>'+comps.map(c=>ps.map((p,i)=>drePeriodHeader(c,p,i===0)).join('')).join('')+(tableMode==='sideTotal'?ps.map(p=>'<th class="period-head sep-left">'+esc(p)+'</th>').join(''):'')+'</tr></thead><tbody>';
    rows.forEach(r=>{out+='<tr class="lvl'+Math.floor(Number(r.nivel))+'"><td class="desc" title="'+esc(r.descricao)+'">'+esc(r.descricao)+'</td>'+comps.map(c=>ps.map((p,i)=>cell(r.empresas[c.name]?.[p]||0,i===0?'sep-left':'',false,dreSemMovimento(c,p))).join('')).join('')+(tableMode==='sideTotal'?ps.map(p=>cell(rowTotal(r,p),'sep-left',true)).join(''):'')+'</tr>'});
  }
  out+='</tbody></table></div></section>';document.getElementById('tables').innerHTML=out;
}
function fmtCell(v){if(typeof v==='number')return fmt.format(v);return esc(v)}function fmtNum(v){return typeof v==='number'?fmt.format(v):esc(v??'')}
