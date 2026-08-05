# ADR 0007: Configuração de LLM na GUI (provider + modelo + key)

## Status
Aceito

## Contexto

`llm_enhancer` lê exclusivamente variáveis de ambiente
(`PDF2MD_LLM_URL`, `PDF2MD_LLM_KEY`, `PDF2MD_LLM_MODEL`). O `BatchProcessor`
criava `Process()` sem definir `.environment` — o `.app` aberto pelo Finder
não herda o env do shell, então `disponivel()` caía no early-return e
`--llm-fallback` era um **no-op silencioso na GUI**.

A correção exigia mais que injetar env: o usuário precisa escolher provedor,
modelo e informar API key — decisões travadas aqui:

| # | Decisão | Escolha | Motivo |
|---|---|---|---|
| D6 | Onde persiste provider/modelo | `@AppStorage` (UserDefaults) | Não é segredo |
| D7 | Onde persiste a API key | **Keychain** (`kSecClassGenericPassword`, service `com.pdf2md.llm`) | UserDefaults é plist em claro no container do app |
| D8 | Como a key chega no Python | `processo.environment` (dict explícito), **nunca em argv** | argv aparece em `ps aux` para qualquer processo do mesmo usuário |
| D9 | Modelo sem visão + OCR fallback | Aviso inline no picker ("Groq não tem visão — OCR de imagem fica só no Tesseract") | Evita expectativa quebrada silenciosa |
| D10 | Sem provider configurado | Toggle **desabilitado** com dica "Configure um provedor" | Melhor que ligar e não fazer nada (bug atual) |

## Decisão

1. **Precedência flag > env > default.** `ConfigLLM` (dataclass) carrega
   `url`/`modelo`/`key`/`timeout` opcionais; `_url()`/`_modelo()`/`_key()`/
   `_timeout()` resolvem na ordem flag → env → default. A API pública de
   `melhorar_markdown`/`ocr_com_visao`/`disponivel` ganha parâmetro `config`
   opcional — zero quebra de compatibilidade (env-only continua funcionando).
2. **Novas flags CLI** `--llm-url` / `--llm-modelo` no `converter`, propagadas
   por `batch_convert` → `aplicar_pipeline_qualidade` → `melhorar_markdown`.
   A key **não** ganha flag: `ps aux` (CWE-522).
3. **Subcomandos `llm modelos --json` e `llm testar --json`.** A GUI não
   reimplementa HTTP; o binário lista modelos (`GET /models` + detecção de
   visão via `/api/show` no Ollama local) e testa conexão com latência.
   Falha → `{"ok": false}` com **exit 0** — JSON é o contrato com a GUI.
   Erros são mensagens seguras (CWE-209): só código HTTP ou categoria.
4. **GUI:** scene `Settings` (Preferências) com Picker de provedor, Picker de
   modelo (populado dinamicamente, fallback estático + campo editável), campo
   de key (Keychain), indicador de status via `llm testar`. Toggle principal
   desabilitado sem provider configurado (D10). Decisão de layout: config na
   janela de Preferências, não no rodapé da janela principal (Parte 5 do
   plano: rodapé ancorado, provider não é decisão por conversão).

## Segurança

- **Key em argv:** proibido (D8). Grep de evidência: `PDF2MD_LLM_KEY` só
  aparece em atribuições de `environment`, nunca em `arguments`.
- **Key em log/JSON:** `llm modelos/testar --json` não emite a key; avisos de
  erro usam `_erro_seguro()` (HTTP code/categoria) — CWE-209/532.
- **SSRF por design:** `_url()` mantém a allowlist http/https e rejeita
  userinfo (ADR-0004). **Não** bloqueamos IP privado: `localhost` é o caso de
  uso principal (Ollama). A URL vem do usuário, não de documento — risco
  aceito e registrado (o `ConfigLLM.url` passa pela mesma validação do env).
- **Entitlements:** o `.app` é **não-sandboxed** (build sem arquivo de
  entitlements) — `com.apple.security.network.client` não se aplica. Se o
  sandbox for adotado no futuro, é obrigatório.
- **Keychain × assinatura ad-hoc:** itens de Keychain criados por app com
  signing ad-hoc podem ser invalidados a cada rebuild. Mitigação: service
  fixo `com.pdf2md.llm` independente do bundle id. Limitação conhecida até
  adoção de Developer ID estável.

## Consequências

- Corrige o bug do toggle no-op silencioso na GUI.
- `disponivel(ConfigLLM(url=...))` força o probe mesmo com URL default sem
  env — o cenário exato da GUI.
- `llm testar` tem latência medida sem lru_cache (probe fresco por design).

## Alternativas rejeitadas

- **Key via flag CLI** (`--llm-key`): vazaria em `ps aux`. Rejeitado.
- **Base64 inline / UserDefaults para a key:** plist em claro. Rejeitado.
- **HTTP no Swift (URLSession):** duplicaria validação de SSRF e o parsing do
  contrato; subcomando `llm` reusa o `_url()` já auditado. Rejeitado.
- **Config no rodapé da janela principal:** espremia a lista em janelas
  pequenas (Parte 5). Rejeitado — Preferências.
