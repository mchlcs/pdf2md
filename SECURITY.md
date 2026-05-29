# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ |

## Reporting a Vulnerability

**Não abra issue pública para vulnerabilidades de segurança.**

Envie e-mail para: mchlcs (GitHub) — use a função "Report a vulnerability" privada do GitHub:
`https://github.com/mchlcs/pdf2md/security/advisories/new`

Inclua:
- Descrição da vulnerabilidade
- Passos para reproduzir
- Impacto potencial
- Sugestão de fix (opcional)

Resposta esperada: 48h. Fix + release: 7 dias para vulnerabilidades críticas.

## Escopo

Este projeto processa arquivos PDF locais. Superfície de ataque:
- **Path traversal** — input de paths validado antes de qualquer IO
- **Subprocess injection** — nenhum input de usuário passado diretamente ao shell
- **Dependências** — `pip audit` roda no CI a cada push

## Fora do escopo

- Ataques que requerem acesso físico à máquina
- PDFs maliciosos que exploram o pymupdf4llm (reportar upstream)
