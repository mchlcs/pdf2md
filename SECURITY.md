# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.6.x   | ✅ (versão atual — única com fixes ativos) |
| 0.5.x   | ❌ |
| 0.4.x   | ❌ |
| 0.3.x   | ❌ |
| 0.2.x   | ❌ |
| 0.1.x   | ❌ |

> Apenas a versão mais recente (0.6.x) recebe correções de segurança ativas;
> versões anteriores não recebem backports.

## Reporting a Vulnerability

**Não abra issue pública para vulnerabilidades de segurança.**

Envie e-mail para: phant0um (GitHub) — use a função "Report a vulnerability" privada do GitHub:
`https://github.com/phant0um/pdf2md/security/advisories/new`

Inclua:
- Descrição da vulnerabilidade
- Passos para reproduzir
- Impacto potencial
- Sugestão de fix (opcional)

Resposta esperada: 48h. Fix + release: 7 dias para vulnerabilidades críticas.

## Escopo

Este projeto processa arquivos PDF locais. Superfície de ataque:
- **Path traversal** — input de paths validado antes de qualquer IO
  (`validar_path_seguro` + nomes de asset sempre gerados, ADR-0005)
- **Subprocess injection** — nenhum input de usuário passado diretamente
  ao shell; `.doc` via `textutil` (path fixo, lista de args, timeout)
- **SSRF** — URL do LLM com allowlist http/https e sem userinfo (ADR-0004)
- **Segredos** — API key do LLM só via environment/Keychain, nunca em argv
  (CWE-522, ADR-0007); `detect-secrets` + `gitleaks` no CI
- **Dependências** — `pip-audit` roda no CI a cada push

## Riscos aceitos (threat model documentado)

| Risco | Justificativa | Ref. |
|---|---|---|
| **App não-sandboxed** (sem entitlements) | Distribuição ad-hoc sem Developer ID; sandbox exigiria `com.apple.security.network.client` e re-assinatura estável | ADR-0007 |
| **Keychain sem access group** | App não-sandboxed: qualquer processo do mesmo usuário que conheça service/account lê o item — aceito para app desktop pessoal ad-hoc | ADR-0007 |
| **Prompt injection** | Texto do documento (não-confiável) vai ao LLM sem isolamento de instruções (`core/llm_enhancer.py`) — a saída pode ser influenciada por conteúdo malicioso do PDF | ADR-0004 |
| **SSRF sem blocklist de IP privado/metadata** | A URL do LLM vem do próprio usuário (Settings/env), não de documento — `localhost` é o caso de uso principal (Ollama) | ADR-0004/0007 |

## Fora do escopo

- Ataques que requerem acesso físico à máquina
- PDFs maliciosos que exploram o pymupdf4llm (reportar upstream)
