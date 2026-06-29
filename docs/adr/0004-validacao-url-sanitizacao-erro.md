# ADR 0004: Validação de URL do LLM e Sanitização Centralizada de Erros

## Status
Aceito

## Contexto
A auditoria de segurança confirmou por PoC três vulnerabilidades com veto de deploy ativo:

1. **SSRF / leitura arbitrária de arquivo (CVSS 8.1, CWE-918):** `core/llm_enhancer.py`
   lia `PDF2MD_LLM_URL` sem validar o scheme. Como `urllib.request.urlopen` honra
   `file://`, `ftp://` e `gopher://`, um atacante com controle da env var (ex: via
   `.env` injetado, CI mal configurado, ou supply-chain) podia ler arquivos
   arbitrários do filesystem (`file:///etc/passwd`) ou pivotar para serviços
   internos via protocolos não-HTTP.
2. **Leak de credencial/informação (CWE-209/532):** os blocos `except Exception as
   exc` em `melhorar_markdown` e `ocr_com_visao` propagavam `str(exc)` para a lista
   de `avisos`, que é serializada no JSON de saída do CLI (stdout). Mensagens de
   exceção de bibliotecas HTTP frequentemente incluem a URL completa da requisição
   (incluindo querystring/credenciais) ou paths do sistema.
3. **Leak de path absoluto (CWE-209):** `core/batch.py` sanitizava erros com
   `msg.replace(str(origem), origem.name)` — comparação de string exata. Isso falha
   silenciosamente quando o path na mensagem de exceção não é byte-a-byte idêntico
   ao path original: resolução de symlink (`/tmp` → `/private/var/folders/...` no
   macOS), diferença de capitalização em filesystems case-insensitive, ou barra
   final adicionada pela lib que lançou a exceção.

## Decisão

1. **Allowlist de scheme no LLM enhancer.** `_url()` agora usa `urllib.parse.urlsplit`
   e só aceita `scheme in {"http", "https"}`. Hostname vazio é rejeitado. URLs com
   `userinfo` embutido (`user:senha@host`) são rejeitadas — isso também mitiga a
   causa raiz da vuln #2 ao impedir que uma credencial chegue a ser parte da URL
   (e, por consequência, de uma mensagem de exceção HTTP).
2. **Erros de LLM expõem apenas `type(exc).__name__`.** Os dois pontos de captura em
   `llm_enhancer.py` não interpolam mais `{exc}` no aviso — só o nome da classe da
   exceção (ex: `OSError`, `TimeoutError`), suficiente para diagnóstico sem vazar
   payload, URL ou credencial.
3. **Política centralizada de redação de path.** Nova função
   `core/utils.sanitizar_mensagem_erro(msg: str) -> str`, usada por `core/batch.py`,
   que aplica regex sobre QUALQUER path absoluto na mensagem (não depende de
   comparação exata com o path original) e reduz para o basename — exceto dentro do
   home do usuário, onde preserva a notação `~/...` para manter algum contexto de
   debug sem expor o path absoluto do sistema.

## Razão
- Allowlist de scheme é a mitigação canônica para SSRF via `urlopen`/`requests` —
  mais simples e robusta que blocklist (que sempre fica incompleta).
- Rejeitar credencial-na-URL na origem (`_url()`) é mais robusto que tentar redigir
  credenciais depois, em todos os pontos onde a URL possa aparecer em log/erro.
- Expor só `type(exc).__name__` é suficiente para triagem (timeout vs. conexão
  recusada vs. erro de parsing) sem o risco de vazar payload sensível.
- Regex sobre qualquer path absoluto é robusta a symlink, case-mismatch e barra
  final — falhas reais observadas na abordagem anterior de `str.replace` com
  comparação exata.

## Alternativas rejeitadas
- **Blocklist de schemes perigosos** (`file`, `ftp`, `gopher`, ...): sempre incompleta
  — novos schemes/handlers podem ser registrados por outras libs no processo.
- **Sanitizar apenas a mensagem final do JSON de saída** (em vez de na origem):
  superfície maior de pontos a manter sincronizados; preferimos resolver na função
  central (`_url()`, `sanitizar_mensagem_erro()`).
- **Sempre reduzir a basename, mesmo dentro do home:** perderia contexto útil de
  debug (qual subdiretório do projeto). A notação `~/...` é um compromisso razoável.

## Consequências
- `PDF2MD_LLM_URL` com scheme não-HTTP(S) agora levanta `ValueError` em vez de ser
  silenciosamente aceita por `urlopen`. `disponivel()` trata esse `ValueError` como
  "indisponível" (retorna `False`) — não bloqueia a conversão (falha graciosa).
- URLs com credencial embutida (`https://user:key@host`) passam a ser rejeitadas;
  usuários devem usar `PDF2MD_LLM_KEY` para autenticação, nunca a URL.
- Avisos de falha do LLM ficam menos detalhados (`"LLM enhancement falhou
  (OSError)"` em vez de incluir a mensagem completa) — trade-off aceito em favor de
  não vazar dados sensíveis no JSON de saída.
- Toda sanitização de path em mensagens de erro deve passar por
  `core/utils.sanitizar_mensagem_erro` — novo código que capture exceções com paths
  do usuário deve reusar essa função em vez de reimplementar `str.replace`.
