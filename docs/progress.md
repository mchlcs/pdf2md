# pdf2md — Progress

## Ciclo 1 (Fase 0-1 + Gate 1) — CONCLUÍDO ✅
- Status: Fechado — 2026-05-22
- Commit: `feat: implementação inicial pdf2md v0.1.0-alpha`
- Repo: https://github.com/mchlcs/pdf2md

### Gate 1 — Forge Score
- Score 5E: **91/100** ✅ (threshold: 75)
- Sentinel: **APPROVED** — zero findings críticos pós-fix
- Fixes aplicados: 9 (C1, H3, M2, L3)

### Entregas Ciclo 1
- Core Python: converter + image_converter + formatter + batch + cli + utils
- GUI Swift: ContentView + BatchProcessor (async correto, security loop fix)
- Testes: 30 casos — converter, OCR, formatter, batch
- CI: GitHub Actions configurado
- ADRs: 0001-stack, 0002-ocr, 0003-obsidian

## Ciclo 2 (Fases 4-5 + Gate 2) — PENDENTE
- Status: Aguardando instrução
- Escopo: empacotamento PyInstaller → .app → .dmg + GitHub Release
- Gate 2: Forge (5E ≥75) + Probe (scan estático/dinâmico) antes de release
