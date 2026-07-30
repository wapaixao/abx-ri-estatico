# ABX RI — Regressões obrigatórias

Este arquivo lista os testes que a versão refatorada deve passar antes de qualquer publicação.

## Backup de referência

- Commit: `925c53e`
- Tag: `backup/pre-refactor-abx-ri-20260730-141604-925c53e`
- Arquivo: `/root/backups/abx-ri-estatico/abx-ri-estatico-pre-refactor-20260730-141604-925c53e.tar.gz`
- SHA256: `fb2c90dbf47d901d81b02bc8a80d340ff42a63df051c0303ca550a239ba3fca2`

## Testes funcionais

### Carregamento

- [ ] `index.html` responde 200 localmente.
- [ ] `data.json` responde 200 localmente.
- [ ] `data.json` carrega com retry/cache-buster.
- [ ] JS passa em `node --check`.

### BP

- [ ] Campo `Visualização` aparece na BP.
- [ ] Campo `Visualização` é compacto.
- [ ] Campo `Visualização` não aparece em DRU/PIS/COFINS/Lucros/Resumo.
- [ ] Linha `Ajuste / Reclassificação PL` fica oculta enquanto PL não auditado.
- [ ] Linha `Ajuste / Reclassificação para fechamento` fica oculta se zerada.

### DRU

- [ ] Cards mostram soma quando `1T26` e `2T26` estão selecionados.
- [ ] Card Receita Líquida exibe rótulo `1T26 + 2T26` quando ambos selecionados.
- [ ] Percentuais usam Receita Líquida somada.

### U006 / Campo Grande

- [ ] Fonte carregada: `ABX_Receita_Gerencial_U006_1T_2T2026_VALIDACAO.xlsx`.
- [ ] A-B fecha para 1T26 e 2T26 em todas as unidades.
- [ ] Linha A em verde claro.
- [ ] Linha B em verde claro.
- [ ] Linha A-B em verde mais escuro.
- [ ] Cabeçalhos centralizados; descrições à esquerda; valores à direita.

### Resumo

- [ ] Visão `Tudo` mostra PIS/COFINS + Lucros.
- [ ] Visão `PIS` mostra só PIS/COFINS.
- [ ] Visão `Lucros` mostra só Lucro Líquido DRU, Lucros a Distribuir e Prejuízo.
- [ ] Visão `Particip.` mostra sócios.
- [ ] Botões de visão são compactos.
- [ ] Não existe linha/faixa em branco entre título do módulo e tabela.
- [ ] Há divisor vertical forte entre 1T26 e 2T26.
- [ ] Corpo alterna verde claro/branco desde a primeira unidade.

### Lucros / Distribuição

- [ ] 2026 usa base compensada do Resumo.
- [ ] Unidade 007 — Belém, 2T26:
  - Resultado: `481.461`
  - Negativo Anterior: `-25.680`
  - Resultado Líquido: `455.781`
- [ ] Participações calculadas sobre `Lucros a Distribuir`.
- [ ] Ordenação por Maior Total mantém linha inteira do sócio.
- [ ] Ordenação A-Z mantém valores do sócio na mesma linha.
- [ ] Ordenação Maior 1T26 e Maior 2T26 preservam 1T26/2T26/Total juntos.

### Publicação

- [ ] Antes de publicar, perguntar a Wagner se o PL já foi auditado.
- [ ] Se não foi auditado, publicar mantendo `Ajuste / Reclassificação PL` oculta.
- [ ] Validar GitHub Pages com cache-buster do commit.
