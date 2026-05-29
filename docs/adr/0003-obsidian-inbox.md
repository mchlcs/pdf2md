# ADR 0003: Obsidian Inbox

## Status
Aceito

## Contexto
O usuário utiliza Obsidian como sistema de notas. O output do pdf2md deve integrar-se naturalmente ao workflow de triage de documentos.

## Decisão
Output para `vault/_inbox/` com frontmatter YAML compatível com Obsidian Properties.

## Razão
- `_inbox/` é padrão de triage nativo no Obsidian.
- Frontmatter YAML é compatível com Obsidian Properties (metadados nativos).
- Tags padrão (`pdf2md`, `converted`) permitem filtragem fácil.
- Campo `source` preserva referência ao arquivo original.

## Formato frontmatter
```yaml
---
title: nome-do-arquivo
source: nome-original.pdf
converted: 2026-05-22
tags:
  - pdf2md
  - converted
---
```

## Consequências
- Vault path deve ser passado como parâmetro (sem hardcoding).
- Diretório `_inbox/` é criado automaticamente se não existir.
- Frontmatter sempre presente quando `--vault` ou `--obsidian` ativo.
