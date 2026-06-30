"""
LLM enhancer — fallback de qualidade via modelo local (Ollama) ou remoto.

Provider-agnostic: usa API compatível com OpenAI via urllib.request (stdlib,
sem deps extras). Funciona com Ollama, Gemini, OpenRouter, Groq etc.

Configuração via variáveis de ambiente:
  PDF2MD_LLM_URL    URL base da API  (default: http://localhost:11434/v1 = Ollama)
  PDF2MD_LLM_KEY    API key          (default: "ollama" — Ollama não valida)
  PDF2MD_LLM_MODEL  Modelo           (default: llama3.2-vision)
  PDF2MD_LLM_TIMEOUT Timeout em seg  (default: 120)

Exemplos de configuração:
  # Ollama local (padrão — grátis, offline, privado)
  PDF2MD_LLM_URL=http://localhost:11434/v1
  PDF2MD_LLM_MODEL=llama3.2-vision

  # Gemini Flash (grátis com limite, excelente qualidade)
  PDF2MD_LLM_URL=https://generativelanguage.googleapis.com/v1beta/openai/
  PDF2MD_LLM_KEY=sua_chave_do_aistudio
  PDF2MD_LLM_MODEL=gemini-2.0-flash

  # Groq (ultra rápido, grátis, sem visão — só texto)
  PDF2MD_LLM_URL=https://api.groq.com/openai/v1
  PDF2MD_LLM_KEY=sua_chave_groq
  PDF2MD_LLM_MODEL=llama-3.1-8b-instant
"""

import base64
import json
import os
import urllib.request
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

# ── Configuração ──────────────────────────────────────────────────────────────

_URL_PADRAO = "http://localhost:11434/v1"
_MODELO_PADRAO = "llama3.2-vision"
_TIMEOUT_PADRAO = 120
_MAX_CHARS_LLM = 12000       # ~3k tokens — evita estourar contexto do modelo
_MAX_TOKENS_RESPOSTA = 4096
_TIMEOUT_VERIFICACAO = 2     # segundos — timeout rápido para checagem de disponibilidade

# Schemes aceitos para a URL do LLM — bloqueia file://, ftp://, gopher:// etc.
# que permitiriam SSRF/leitura arbitrária de arquivo via urlopen (CWE-918).
_SCHEMES_PERMITIDOS = frozenset({"http", "https"})


def _url() -> str:
    """
    Lê e valida PDF2MD_LLM_URL.

    Aplica allowlist de scheme (http/https) e rejeita credenciais embutidas
    na URL (user:pass@host) — mitigação de SSRF (CWE-918) e de leak de
    credenciais em logs/erros (CWE-209/532).

    Returns:
        URL validada, sem barra final.

    Raises:
        ValueError: Se scheme não permitido, host vazio ou houver userinfo.
    """
    bruta = os.getenv("PDF2MD_LLM_URL", _URL_PADRAO).rstrip("/")
    partes = urlsplit(bruta)

    if partes.scheme not in _SCHEMES_PERMITIDOS:
        raise ValueError("PDF2MD_LLM_URL deve usar http ou https")
    if not partes.hostname:
        raise ValueError("PDF2MD_LLM_URL deve conter um host válido")
    if partes.username:
        raise ValueError("credenciais não devem ser embutidas na URL")

    return bruta


def _modelo() -> str:
    return os.getenv("PDF2MD_LLM_MODEL", _MODELO_PADRAO)


def _key() -> str:
    return os.getenv("PDF2MD_LLM_KEY", "ollama")


def _timeout() -> int:
    try:
        return int(os.getenv("PDF2MD_LLM_TIMEOUT", str(_TIMEOUT_PADRAO)))
    except ValueError:
        return _TIMEOUT_PADRAO


# ── Prompts ───────────────────────────────────────────────────────────────────

_PROMPT_MELHORIA = """\
O texto abaixo foi extraído automaticamente de '{nome}'.
Corrija os problemas de qualidade sem alterar o conteúdo:
- Junte palavras quebradas por hifenização (ex: "pala-\nvra" → "palavra")
- Corrija acentuação PT-BR quando evidente (ã, ç, é, ó, á, etc.)
- Preserve estrutura Markdown (headings, listas, tabelas, código)
- NÃO adicione nem remova informação — só corrija forma

Retorne APENAS o Markdown corrigido, sem explicação ou comentários.

{md}"""

_PROMPT_OCR = """\
Transcreva todo o texto visível nesta imagem para Markdown.
- Preserve estrutura: títulos, listas, tabelas, parágrafos
- Corrija acentuação PT-BR quando evidente
- Se houver tabela, use formato Markdown de tabela
- Retorne APENAS o Markdown, sem explicação"""

# ── Cliente HTTP (stdlib — sem deps extras) ───────────────────────────────────


def _completar(mensagens: list[dict]) -> str:
    """
    Chama /chat/completions via urllib.request (sem deps extras).
    Compatível com qualquer API no formato OpenAI.
    """
    payload = json.dumps({
        "model": _modelo(),
        "messages": mensagens,
        "max_tokens": _MAX_TOKENS_RESPOSTA,
        "temperature": 0.1,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{_url()}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_key()}",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=_timeout()) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    return data["choices"][0]["message"]["content"]


# ── API pública ───────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def disponivel() -> bool:
    """
    Verifica se o endpoint LLM está acessível (timeout rápido de 2s).

    Resultado é cacheado (lru_cache) — só testa uma vez por processo,
    evitando latência em cada arquivo do batch.

    Returns:
        True se o endpoint respondeu. False se não configurado ou inacessível.
    """
    try:
        url = _url()
    except ValueError:
        # URL malformada/insegura — trata como indisponível, não propaga.
        return False
    # Se usar o default e PDF2MD_LLM_URL não estiver definido, só testa se
    # explicitamente configurado — evita timeout em máquinas sem Ollama.
    if url == _URL_PADRAO and "PDF2MD_LLM_URL" not in os.environ:
        return False
    try:
        req = urllib.request.Request(f"{url}/models", method="GET")
        with urllib.request.urlopen(req, timeout=_TIMEOUT_VERIFICACAO):
            return True
    except Exception:
        return False


def melhorar_markdown(md: str, origem: Path) -> tuple[str, list[str]]:
    """
    Melhora qualidade do Markdown via LLM (pós-processamento de texto).

    Útil quando o conversor produziu texto com palavras quebradas, acentos
    corrompidos ou formatação perdida.

    Falha graciosamente: se o LLM não estiver disponível ou retornar erro,
    retorna o markdown original com um aviso — nunca bloqueia a conversão.

    Args:
        md: Markdown bruto (já limpo por quality.py).
        origem: Path do arquivo de origem (para contexto no prompt).

    Returns:
        (md_melhorado, avisos_adicionais) — avisos_adicionais é [] se OK.
    """
    # Trunca para não estourar o contexto (12k chars ≈ ~3k tokens)
    md_input = md[:_MAX_CHARS_LLM]
    prompt = _PROMPT_MELHORIA.format(nome=origem.name, md=md_input)

    try:
        resultado = _completar([{"role": "user", "content": prompt}])
        if len(md) > _MAX_CHARS_LLM:
            resultado = resultado + "\n\n" + md[_MAX_CHARS_LLM:]
        return resultado, []
    except Exception as exc:
        # Não inclui str(exc) no aviso — pode conter URL, credencial ou path
        # do ambiente (CWE-209/532). Só o nome do tipo é exposto.
        return md, [f"LLM enhancement falhou ({type(exc).__name__})"]


def ocr_com_visao(imagem_path: Path) -> tuple[str, list[str]]:
    """
    Transcreve imagem usando visão do LLM (OCR fallback).

    Útil quando pytesseract falha ou retorna texto muito curto
    (ex: imagens escaneadas com fontes incomuns, manuscrito, etc.).

    Falha graciosamente: retorna string vazia + aviso se LLM indisponível.

    Args:
        imagem_path: Path para arquivo de imagem (PNG recomendado).

    Returns:
        (texto_md, avisos) — avisos é [] se OCR com visão foi bem-sucedido.
    """
    if not imagem_path.exists():
        return "", [f"Imagem não encontrada: {imagem_path.name}"]

    try:
        img_b64 = base64.standard_b64encode(imagem_path.read_bytes()).decode("ascii")

        mensagem_visao = {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                },
                {"type": "text", "text": _PROMPT_OCR},
            ],
        }

        resultado = _completar([mensagem_visao])
        return resultado, []
    except Exception as exc:
        # Idem: não inclui str(exc) no aviso (CWE-209/532).
        return "", [f"OCR com visão falhou ({type(exc).__name__})"]
