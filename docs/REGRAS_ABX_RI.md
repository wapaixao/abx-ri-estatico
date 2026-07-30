# ABX / Água Branca — Regras funcionais validadas do RI

> Base congelada antes da refatoração limpa: commit `925c53e`.
> Backup Git: `backup/pre-refactor-abx-ri-20260730-141604-925c53e`.

## Objetivo

Preservar todas as regras financeiras, de layout e de interação já validadas no dashboard ABX / Água Branca antes da refatoração limpa.

## Estrutura de módulos atual

- `BP` — Balanço Patrimonial.
- `DRU` — Demonstração Resultado Unidade / gerencial.
- `U006` — Campo Grande / Receita Gerencial U006.
- `PISCOFINS` — Apuração PIS/COFINS.
- `RESUMO` — Resumo PIS/COFINS + Lucros + Participações.
- `DISTRIB` — Lucros / Distribuição de Resultado.
- `ORG` — Organogramas.

## Regras gerais de publicação

1. O site atual usa `index.html` + `data.json` desacoplados.
2. Antes de publicar nova versão ABX, perguntar se Wagner já auditou/corrigiu o Patrimônio Líquido na fonte.
3. Enquanto o PL não for auditado, ocultar a linha `Ajuste / Reclassificação PL` no BP.
4. Publicar só após validação de carregamento de `index.html`, `data.json`, sintaxe JS e regras críticas.
5. DRE fica visível como botão, mas indisponível até envio dos relatórios DRE.

## BP — Balanço Patrimonial

1. A aba BP mantém o campo `Visualização`; ele tem função e não deve ser removido.
2. O campo `Visualização` deve ser compacto e ficar na mesma linha funcional dos seletores de empresa, sem sobrepor/ocupar espaço excessivo.
3. As empresas devem aparecer em botões/logos compactos.
4. A linha `Ajuste / Reclassificação para fechamento` deve ser oculta quando estiver zerada.
5. A linha `Ajuste / Reclassificação PL` deve ficar oculta enquanto Wagner não auditar a fonte.
6. Fonte auditada da linha `Ajuste / Reclassificação PL`:
   - Arquivo: `/root/data/abx/entregas/APRESENTACAO/ABX_BP_Consolidado_2026_APRESENTACAO_SUBGRUPOS_MULTIEMPRESA.xlsx`
   - Aba principal: `Dados Página RI`
   - Linhas: 25, 49, 73, 97, 121 por empresa.

## DRU

1. Os cards superiores devem respeitar os períodos selecionados.
2. Se `1T26` e `2T26` estão marcados, os cards mostram a soma dos dois trimestres, não apenas o último.
3. O texto dos cards deve refletir o conjunto selecionado, exemplo: `RECEITA LÍQUIDA 1T26 + 2T26`.
4. Percentuais de CMV, despesa operacional, EBITDA e lucro líquido devem usar a Receita Líquida somada dos períodos selecionados.
5. A linha base para Lucros/Distribuição 2026 é `LUCRO LÍQUIDO GERENCIAL` quando existir; fallback: `LUCRO LIQUIDO`.
6. Valores abaixo de `LUCRO LÍQUIDO GERENCIAL` não devem poluir a visão principal da DRU quando pertencem a PIS/COFINS/Lucros próprios.

## U006 — Campo Grande / Receita Gerencial U006

1. Fonte:
   - Arquivo: `/root/data/abx/entregas/APRESENTACAO/ABX_Receita_Gerencial_U006_1T_2T2026_VALIDACAO.xlsx`
   - Aba: `Receita Gerencial U006`
2. O site lê a planilha no build em `build_abx_ri.py` via `extract_sheet_report(..., max_row=9, max_col=43)`.
3. Estrutura de linhas:
   - `A` = `CF cobrada das unidades — DRU 261008`.
   - `B` = `Despesa financeira efetiva — DRE`.
   - `A-B` = `CONTRIBUIÇÃO FINANCEIRA LÍQUIDA`.
   - `ADM` = `CONTRIBUIÇÃO ADMINISTRATIVA — RECEITA GERENCIAL U006`.
4. Regra financeira: `CONTRIBUIÇÃO FINANCEIRA LÍQUIDA = A - B`.
5. A regra deve fechar para `1T26` e `2T26` em todas as unidades.
6. Layout:
   - títulos/cabeçalhos centralizados;
   - descrições à esquerda;
   - valores à direita;
   - cabeçalho em verde escuro;
   - linhas `A` e `B` em verde claro;
   - linha `A-B` em verde mais escuro;
   - não centralizar o conteúdo numérico.

## PIS/COFINS

1. Fonte atual:
   - `/root/data/abx/APURACAO_COFINS_PIS_2T2026_COMPLETA_FORMATADA_SEM_OBS.xlsx`
   - Aba `Cofins e Pis`.
2. Deve ser módulo próprio, não misturado dentro da DRU.
3. Layout deve preservar modelo verde operacional da planilha.
4. Seletores de unidade devem ser compactos.
5. `Visualização` não deve aparecer nesta aba por padrão.

## Resumo

1. Fonte atual:
   - `/root/data/abx/APURACAO_COFINS_PIS_2T2026_COMPLETA_FORMATADA_SEM_OBS_COM_RESUMO_VALIDACAO_V4.xlsx`
   - Aba `Resumo`.
2. Deve ter seletores compactos para:
   - períodos: `1T26`, `2T26`;
   - unidades;
   - visão: `Tudo`, `PIS`, `Lucros`, `Particip.`.
3. `Tudo`: mostra `PIS/COFINS`, `Lucro Líquido DRU`, `Lucros a Distribuir`, `Prejuízo a Compensar`.
4. `PIS`: mostra só PIS/COFINS.
5. `Lucros`: mostra só `Lucro Líquido DRU`, `Lucros a Distribuir`, `Prejuízo a Compensar`.
6. `Particip.`: mostra visão por sócios usando percentuais gerenciais por unidade.
7. O botão/controle `Particip.` deve ser compacto e não sobrepor filtros.
8. Cabeçalho do Resumo em verde escuro; corpo alternado verde claro/branco; total em verde claro destacado.
9. Não deve haver faixa/linha de observação entre cabeçalho do módulo e a tabela.
10. Deve haver borda vertical forte separando blocos de trimestre.

## Lucros / Distribuição

1. Para 2026, a aba Lucros deve usar a mesma base compensada da aba Resumo.
2. Regra de prejuízo: prejuízo de uma unidade em trimestre anterior deve ser abatido quando a mesma unidade tiver lucro futuro.
3. Se a unidade tem prejuízo no trimestre, não distribui naquele trimestre.
4. O prejuízo permanece em `Prejuízo a Compensar` até haver lucro futuro na própria unidade.
5. Unidade 007 — Belém é caso crítico de regressão:
   - No `2T26`, deve abater o prejuízo do `1T26`.
   - Resultado esperado atual: `Resultado 481.461`, `Negativo Anterior -25.680`, `Resultado Líquido 455.781`.
6. Percentuais gerenciais atuais por unidade devem ser preservados em `PARTICIP`.
7. A visão de sócios deve poder ordenar por:
   - Maior Total;
   - A-Z;
   - Maior 1T26;
   - Maior 2T26.
8. A ordenação deve mover a linha inteira do sócio, preservando `1T26`, `2T26` e `Total` juntos.

## Organogramas

1. Deve conter Organograma Água Branca e Organograma ABX.
2. Layout deve usar paleta verde/Água Branca.
3. Imagens devem ficar legíveis e responsivas.

## Regras visuais globais

1. Paleta principal em tons de verde Água Branca.
2. Verde escuro só para cabeçalhos/elementos de destaque.
3. Corpo das tabelas deve usar branco/verde claro, evitando sombras escuras excessivas.
4. Botões arredondados são padrão aprovado.
5. Filtros devem ficar compactos; não criar campos/botões enormes que sobreponham outros controles.
6. Preferir área de tabela ampla; evitar filtros laterais ou componentes que consumam largura.
7. Títulos/cabeçalhos podem ser centralizados; conteúdo financeiro deve preservar alinhamento legível: descrição à esquerda, números à direita.

## Regras de carregamento

1. `data.json` deve carregar com `cache: no-store` e cache-buster.
2. Deve haver retry de carregamento para reduzir erro intermitente `NetworkError when attempting to fetch resource`.
3. Mensagem de erro deve orientar atualizar página/limpar cache após 3 tentativas.
