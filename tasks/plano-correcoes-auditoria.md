# Plano de correções — auditoria 2026-08-05

> Execução: **subagentes deepseek-v4-flash** (1 subagente = 1 tarefa, com
> fronteira de evidência) orquestrados por **GPT-5.6 Luna max** (decide
> ordens, resolve bloqueios, faz o gate de cada tarefa).
> Fonte: `docs/auditoria-principal-2026-08-05.md` (Grok 4.5 max, validação
> cruzada da preliminar) + `docs/auditoria-2026-08-05.md` (preliminar).
> **Veredito Grok: 2 críticas · 1 alta · 12 médias · 9 baixas.** Ajustes do
> Grok incorporados: `cancelar()` FUNCIONA via Task (rebaixado p/ dead code
> enganoso — M2 vira limpeza, não correção funcional); Pillow = 13 CVEs
> únicos (não 16); SECURITY.md cita antiword mas runtime usa textutil (B9).
> Cada tarefa entrega evidência (teste/verificação) antes de avançar.

---

## Grafo de execução

```
C1 ──> M2 ──> M9a ─┐
C2 ────────────────┤
M1 ────────────────┼──> PR3 (fixes altos) ──> PR4 (fixes médios) ──> PR5 (limpeza)
M3 ────────────────┘
M4 ──> M6 ──> B1 ──┘
B2 ─────────────────────────────────────────┘
```

## Fase 1 — PR "fix/cli-gui" (bloqueante — o app não converte)

| # | Tarefa | Agente | Done criterion (Evidence) |
|---|---|---|---|
| **C1** | CLI: mover options do `converter` para o callback do app (`invoke_without_command=True`); `pdf2md <file> <out>` canônico; `llm` continua subcomando | stratum | `pdf2md arquivo.pdf saida/ --imagens extrair` e `pdf2md llm testar --json` funcionam; args EXATOS da GUI (`<file> <dir> --json`) convertem; testes do cli atualizados; golden intactos |
| **C1b** | Binário congelado revalidado com os args da GUI | stratum | `dist/pdf2md <file> <dir> --json` → JSON de resultado, exit 0 |
| **M1** | GUI: avisos propagados — `atualizarProgresso` guarda `item.avisos`; `statusIcon` mostra âmbar | facet | PDF com aviso de qualidade → ícone âmbar na lista |

## Fase 2 — PR "fix/seguranca-deps"

| # | Tarefa | Agente | Done criterion (Evidence) |
|---|---|---|---|
| **C2** | `Pillow>=12.3.0` (13 CVEs únicos) + `uv lock` | stratum | `pip-audit` sem vuln em runtime; `pytest tests/ -v` verde; binário congelado converte PDF com imagem |
| **M3** | `.secrets.baseline` atualizado (2 falsos positivos auditados) | **sentinel** | `detect-secrets scan` limpo com baseline; pre-commit detect-secrets passa |
| **M4** | SECURITY.md: seção "riscos aceitos" (app não-sandboxed, Keychain service fixo sem access group, SSRF localhost aceito — threat model do usuário) **+ corrigir referência obsoleta a antiword (runtime usa textutil — B9)** | herald | SECURITY.md documenta os riscos com referência aos ADRs 0004/0007; sem menção a antiword |
| **M5** | `python-docx` → dev deps; `THIRD-PARTY-LICENSES.md` corrigido (add python-pptx/openpyxl, remove python-docx) | stratum | `uv run pip list` reflete; licenças batem com METADATA instalados |
| **M6** | gitleaks no CI + CI com `uv` (`uv sync --frozen`) + job smoke PyInstaller com os args da GUI | 🏗️ Infra | `ci.yml` roda `uv sync --frozen`, `uv run pytest`, `uv run ruff`, `gitleaks detect`, e smoke do binário com args da GUI |

## Fase 3 — PR "fix/melhorias-codigo"

| # | Tarefa | Agente | Done criterion (Evidence) |
|---|---|---|---|
| **M7** | Teste-fantasma: `__all__` em `llm_enhancer` ou rename no teste | stratum | `pytest --collect-only` não lista `testar`; suíte sem chamada de rede |
| **M8** | `_MARGEM_PADRAO_PCT` removido; docstrings "PDF-only" corrigidas (converter/batch/utils); `_extrair_chunks_markdown` anexa aviso ao contexto | stratum | `rg "PDF-only|MARGEM_PADRAO"` limpo; `pytest` verde |
| **M9** | `pdf_to_md`/`doc_to_md`: params de assets → `ContextoAssets \| None` único; `_montar_contexto` compartilhado em `image_assets` com `.resolve()` em ambos (bug latente `/var` — Grok confirmou que `converter.py:91-96` não resolve na montagem) | stratum | Assinatura reduzida; teste com assets_dir sob `/var/folders` passa; golden intactos |
| **M10** | GUI: `llmConfigurado` cacheado em `@State` (`.task`); SettingsView com debounce ~400ms nos probes | facet | 1 chamada de Keychain por estado, não por body eval; probes não disparam por keystroke |
| **M11** | Tabela MD unificada (`utils.tabela_md`); `_MIME_PARA_EXT` e `_EXTENSOES_SEGURAS` consolidados (papéis distintos — MIME→ext vs allowlist; decidir se consolidar) | stratum | pptx/xlsx goldens idênticos; sem duplicação |
| **M2b** | `processoAtivo`/`cancelar()` — código morto enganoso (cancel REAL funciona via Task+box): remover campo morto ou unificar no box | facet | `rg processoAtivo` limpo; cancel continua funcionando |

## Fase 4 — PR "chore/limpeza" (herald)

| # | Tarefa | Agente | Done criterion (Evidence) |
|---|---|---|---|
| **B1** | CHANGELOG [0.6.0] ganha os fixes da Emenda 2 (crash GIF+ambos, bomb de scan, colisão de stem) | herald | CHANGELOG cita cf9ab44/#22 |
| **B2** | `tasks/todo.md` arquivado (ou apontado para os planos atuais); `composer_*.md` movido para `tasks/historico/`; branch `feat/browse-paste-fixes` deletada; commit uv.lock direto em main documentado na lesson | herald | `git branch -r` limpo; raiz sem artefatos soltos |
| **B3** | "pdf2md" duplicado: remover texto do header (ContentView) mantendo título da janela | facet | Janela com 1 ocorrência |
| **B4** | PR #18 (layout) rebaseado no main atual e mergeado; PR #19 mergeado | 🏗️ | PRs fechados; ContentView sem conflito |
| **B5** | README: exemplos alinhados com C1 (forma canônica); `pip3 install "pdf2md[dev]"` → `uv sync --extra dev` | herald | README sem exemplo quebrado |

## Backlog pós-crítico (avaliar depois)

- Cobertura: cli.py 67% (branches `--json`, subcomandos llm), branches de
  limite/bytes de `_persistir_render_pagina`, `_base_ollama`/`_visao_modelo`
  (neuron).
- `_silenciar_stdout_nativo` → avaliar fd-local por worker (baixa).
- `waitUntilExit` sem watchdog no ProcessRunner (Grok: risco baixo — hang
  só se filho zumbi; timeout LLM já no Python); I/O de `colarImagem` fora
  do main thread; `ProcessoBox @unchecked Sendable` documentado (facet).
- SSRF metadata (169.254.169.254): defense-in-depth OPCIONAL — threat
  model atual (URL do próprio usuário) não exige (Grok [KIMI]).
- PR 3 (parser-inspector) e PR 4 (anydoc) — **bloqueados no corpus real do
  usuário** (ver `tasks/plano-pr4-anydoc.md`).

## Regras de execução

1. **1 subagente por tarefa** — fronteira limpa, sem 2 agentes no mesmo
   arquivo na mesma fase.
2. **Gate por tarefa:** evidência (teste novo/verificação) obrigatória;
   `pytest tests/ -v` verde antes de qualquer PR; ruff limpo.
3. **Ordem de merge:** Fase 1 → 2 → 3 → 4, PR separado por fase, sem push
   direto (branch protection ativa — verificada hoje).
4. **C1 é bloqueante:** nada de novos binários `.app` antes dele.
5. **Validação cruzada** (Grok 4.5 max) já incorporada no plano; revisar
   com GPT-5.6 Luna max os gates antes de cada merge.
6. Lessons (tasks/lessons.md, máx. 30): registrar o push direto em main e
   a falha do padrão subcomando/GUI.
