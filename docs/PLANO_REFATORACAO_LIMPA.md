# ABX RI — Plano de refatoração limpa com auditoria

> **Base congelada:** `925c53e`  
> **Backup Git:** `backup/pre-refactor-abx-ri-20260730-141604-925c53e`  
> **Arquivo backup:** `/root/backups/abx-ri-estatico/abx-ri-estatico-pre-refactor-20260730-141604-925c53e.tar.gz`

## Objetivo

Transformar o RI ABX de uma prova de conceito evoluída em uma arquitetura limpa, modular, auditável e testável, sem alterar a experiência validada por Wagner.

## Princípio central

A primeira versão refatorada deve ser **funcionalmente equivalente** à versão atual publicada.  
Não redesenhar nem reinventar visual nesta etapa.

## Arquitetura proposta

```text
abx-ri-estatico/
├── index.html
├── data.json
├── build_abx_ri.py
├── assets/
├── docs/
│   ├── REGRAS_ABX_RI.md
│   ├── PLANO_REFATORACAO_LIMPA.md
│   └── REGRESSOES_ABX_RI.md
├── src/
│   ├── app.js
│   ├── auth.js
│   ├── state.js
│   ├── formatters.js
│   ├── selectors.js
│   ├── rules/
│   │   ├── bp-rules.js
│   │   ├── dru-rules.js
│   │   ├── resumo-rules.js
│   │   ├── lucros-rules.js
│   │   └── u006-rules.js
│   └── renderers/
│       ├── cards.js
│       ├── matrix.js
│       ├── sheet.js
│       ├── resumo.js
│       ├── lucros.js
│       └── organograma.js
├── styles/
│   ├── base.css
│   ├── toolbar.css
│   ├── tables.css
│   ├── bp.css
│   ├── resumo.css
│   ├── lucros.css
│   ├── u006.css
│   ├── org.css
│   └── auth.css
└── tests/
    ├── regression-check.js
    └── fixtures/
```

## Fases

### Fase 1 — Documentação e backup

- [x] Criar tag e branch de backup.
- [x] Criar arquivo `.tar.gz` com SHA256.
- [x] Documentar regras validadas.
- [ ] Commitar documentação inicial.

### Fase 2 — Extrair CSS sem mudar visual

Status: **concluída parcialmente e validada**.

1. Criada pasta `styles/`.
2. CSS inline extraído mecanicamente para `styles/app.css`.
3. `index.html` passou a carregar `styles/app.css?v=clean1`.
4. Regressões locais passaram após a extração.
5. Commit: `3099446 — Refatora CSS para arquivo externo`.

Separação fina concluída depois da extração mecânica:

- `styles/base.css`
- `styles/toolbar.css`
- `styles/cards.css`
- `styles/tables.css`
- `styles/piscofins.css`
- `styles/u006.css`
- `styles/lucros-org.css`
- `styles/layout-overrides.css`
- `styles/resumo.css`
- `styles/responsive.css`

Commits:

- `7a197b6 — Refatora estilos por dominio`.
- `d76d615 — Preserva ordem visual dos estilos`.

### Fase 3 — Extrair JS sem mudar comportamento

Status: **concluída parcialmente e validada**.

1. Criada pasta `src/`.
2. JavaScript inline extraído mecanicamente para `src/app.js`.
3. `index.html` passou a carregar `src/app.js?v=clean1` com `defer`.
4. Regressões locais passaram após a extração.
5. Commit: `265a57b — Refatora JS para arquivo externo`.

Separação fina concluída depois da extração mecânica:

- `src/state.js`
- `src/utils.js`
- `src/auth.js`
- `src/participacoes.js`
- `src/report-helpers.js`
- `src/selection.js`
- `src/selectors.js`
- `src/cards.js`
- `src/matrix.js`
- `src/lucros.js`
- `src/resumo.js`
- `src/sheet.js`
- `src/organograma.js`
- `src/boot.js`

Commit:

- `94dedf1 — Refatora JavaScript por dominio`.

### Fase 4 — Criar testes de regressão

Status: **concluída e validada**.

1. Criado `tests/regression-check.js`.
2. Testado carregamento estrutural de `data.json`.
3. Testadas regras críticas:
   - PL oculto;
   - DRU cards somando períodos;
   - U006 A-B;
   - Resumo Tudo/PIS/Lucros/Participações;
   - Lucros unidade 007 compensando prejuízo;
   - ordenação de sócios preservando linha inteira.
4. Commit: `e507c1a — Adiciona teste de regressao ABX RI`.

### Fase 5 — Limpar HTML

1. Reduzir `index.html` para estrutura sem CSS/JS inline.
2. Manter HTML semântico e simples.
3. Validar localmente.
4. Commit: `refactor: limpa index do RI ABX`.

### Fase 6 — Validação final antes de publicar

1. Rodar testes.
2. Servir localmente via HTTP.
3. Validar `index.html` e `data.json`.
4. Comparar comportamento contra versão backup.
5. Perguntar a Wagner sobre PL antes de publicar.
6. Publicar somente após OK.

## Riscos

1. Quebrar regra financeira ao mover código.
2. Quebrar estilos por especificidade CSS.
3. Quebrar GitHub Pages se módulos JS forem carregados incorretamente.
4. Perder comportamento dos filtros.

## Mitigações

1. Refatorar por camadas pequenas.
2. Commitar cada fase separadamente.
3. Manter backup/tag/arquivo.
4. Criar testes antes de mudanças profundas.
5. Publicar só após validação local e confirmação de Wagner.
