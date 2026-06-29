"""
Pipeline de qualidade para saídas de conversão.

Dois estágios aplicados a todo output antes de salvar:

  1. LIMPEZA automática  — remove artefatos silenciosos que corrompem o texto
     visualmente sem levantar exceção no conversor:
       • Hifens suaves (U+00AD) — causam quebra de palavras em PDFs hifenizados
       • Chars de largura zero (U+200B/C/D, U+FEFF mid-string) — deslocam letras
       • Espaços não-quebráveis (U+00A0) → espaço normal

  2. VALIDAÇÃO — detecta problemas que a limpeza não pode corrigir sozinha e
     retorna lista de avisos para exibição no CLI e GUI:
       • Mojibake PT-BR (Latin-1 decodificado como UTF-8)
       • Chars de substituição U+FFFD (encoding definitivamente corrompido)
       • Output muito curto para o tamanho do arquivo (extração falhou)
       • Hifens suaves residuais após limpeza (PDF com hifenização manual pesada)

ORDEM OBRIGATÓRIA no pipeline:
  1. corrigir_mojibake(texto)   — deve rodar ANTES de limpar_artefatos
  2. limpar_artefatos(texto)    — remove soft hyphens etc.
  3. validar_qualidade(md, ...) — detecta problemas residuais

Motivo: o mojibake de "í" contém U+00AD (soft hyphen) como segundo byte.
Se limpar_artefatos rodar primeiro, o padrão "Ã\xad" vira "Ã" e a correção
de mojibake não consegue mais detectar.
"""
from pathlib import Path

from core.llm_enhancer import disponivel as llm_disponivel
from core.llm_enhancer import melhorar_markdown

# ── Tabela de mojibake PT-BR (gerada programaticamente) ─────────────────────
# Mojibake ocorre quando texto Latin-1/cp1252 é decodificado como UTF-8.
# Cada char Latin-1 vira 2 bytes UTF-8 que, relidos como Latin-1, produzem
# "Ã" + outro char.
#
# Geramos a tabela computando:  char.encode('utf-8').decode('latin-1') → padrão errado
# Isto evita literais de encoding ambíguos no código-fonte.

def _build_mojibake_table(chars: str) -> list[tuple[str, str]]:
    """Gera tabela (padrão_errado, char_correto) para os chars fornecidos."""
    result: list[tuple[str, str]] = []
    for c in chars:
        try:
            errado = c.encode("utf-8").decode("latin-1")
            result.append((errado, c))
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass
    return result


# Chars acentuados PT-BR mais frequentes — minúsculas + maiúsculas
_PT_BR_CHARS = "ãçéóáíúõâêôàÃÇÉÓÁÍÚÕÂÊÔÀ"
_MOJIBAKE: list[tuple[str, str]] = _build_mojibake_table(_PT_BR_CHARS)

# Strings de detecção rápida (só os padrões errados)
_MOJIBAKE_DETECTORES: list[str] = [errado for errado, _ in _MOJIBAKE]


# ── 1a. Correção de mojibake (deve rodar ANTES de limpar_artefatos) ──────────

def corrigir_mojibake(texto: str) -> tuple[str, int]:
    """
    Corrige automaticamente mojibake PT-BR comum.

    Deve ser chamado ANTES de limpar_artefatos: o mojibake de "í" contém
    U+00AD (soft hyphen), que limpar_artefatos removeria antes da correção.

    Aplica substituições da tabela _MOJIBAKE em sequência. Seguro para
    documentos em português: os padrões "Ã£", "Ã§" etc. nunca aparecem
    intencionalmente em texto PT-BR correto — são sempre artefatos de encoding.

    Args:
        texto: String possivelmente corrompida.

    Returns:
        (texto_corrigido, n_substituições_realizadas)
    """
    n_total = 0
    for errado, correto in _MOJIBAKE:
        count = texto.count(errado)
        if count > 0:
            texto = texto.replace(errado, correto)
            n_total += count
    return texto, n_total


# ── 1b. Limpeza de artefatos (deve rodar APÓS corrigir_mojibake) ─────────────

def limpar_artefatos(texto: str) -> str:
    """
    Remove artefatos comuns de extração de PDF que corrompem o texto visualmente.

    Deve ser chamado APÓS corrigir_mojibake (ver docstring do módulo).

    Artefatos removidos:
    - U+00AD: SOFT HYPHEN — invisível em editores, mas quebra palavras
      em renderizadores que o respeitam (Obsidian, browsers, Word)
    - U+200B: ZERO WIDTH SPACE
    - U+200C: ZERO WIDTH NON-JOINER
    - U+200D: ZERO WIDTH JOINER
    - U+FEFF: BOM mid-string (BOM no início é preservado; mid-string é artefato)
    - U+00A0: NO-BREAK SPACE → espaço ASCII normal
    - Linhas que ficaram com só whitespace → linha vazia (preserva parágrafos)

    Args:
        texto: String extraída pelo conversor (já com mojibake corrigido).

    Returns:
        String limpa. Nunca modifica conteúdo semântico real.
    """
    texto = texto.replace("\u00ad", "")   # SOFT HYPHEN
    texto = texto.replace("\u200b", "")   # ZERO WIDTH SPACE
    texto = texto.replace("\u200c", "")   # ZERO WIDTH NON-JOINER
    texto = texto.replace("\u200d", "")   # ZERO WIDTH JOINER
    texto = texto.replace("\ufeff", "")  # BOM mid-string
    texto = texto.replace("\u00a0", " ") # NO-BREAK SPACE → espaço normal

    # Colapsa linhas que ficaram só com whitespace (preserva estrutura de parágrafos)
    linhas = [linha if linha.strip() else "" for linha in texto.split("\n")]
    texto = "\n".join(linhas)

    return texto


# ── 2. Validação ──────────────────────────────────────────────────────────────

def validar_qualidade(md: str, origem: Path) -> list[str]:
    """
    Valida qualidade do Markdown gerado e retorna lista de avisos humanos.

    Chamado APÓS corrigir_mojibake e limpar_artefatos — detecta problemas
    que as etapas de limpeza não puderam resolver.

    Verifica:
    1. Mojibake residual (padrões que a tabela não cobriu)
    2. Chars de substituição U+FFFD (encoding definitivamente corrompido)
    3. Output muito curto para o tamanho do arquivo (extração provavelmente falhou)
    4. Hifens suaves residuais acima de threshold (só se não foram removidos)

    Args:
        md: Markdown após limpeza completa.
        origem: Path do arquivo de origem (para comparar tamanho).

    Returns:
        Lista de strings de aviso. Vazia se qualidade OK.
    """
    avisos: list[str] = []

    if not md.strip():
        return []  # output vazio é ERRO, não aviso de qualidade

    # 1. Mojibake residual
    n_mojibake = sum(md.count(p) for p in _MOJIBAKE_DETECTORES)
    if n_mojibake > 0:
        avisos.append(
            f"Encoding possivelmente corrompido — {n_mojibake} padrão(s) de "
            f"mojibake PT-BR residual(is) detectado(s)"
        )

    # 2. Chars de substituição U+FFFD
    n_fffd = md.count("\ufffd")
    if n_fffd > 0:
        avisos.append(
            f"{n_fffd} caractere(s) de substituição (U+FFFD) detectado(s) — "
            f"texto provavelmente corrompido por problema de encoding"
        )

    # 3. Output muito curto para o tamanho do arquivo
    try:
        tamanho_kb = origem.stat().st_size / 1024
        chars_util = len(md.strip())
        if tamanho_kb > 10 and chars_util < 100:
            avisos.append(
                f"Output muito curto ({chars_util} chars) para arquivo de "
                f"{tamanho_kb:.0f} KB — possível falha na extração de texto"
            )
    except OSError:
        pass

    # 4. Hifens suaves residuais acima de threshold
    n_soft_hyphen = md.count("\u00ad")
    if n_soft_hyphen > 5:
        avisos.append(
            f"{n_soft_hyphen} hifens suaves (U+00AD) residuais — palavras podem "
            f"aparecer quebradas em alguns renderizadores (Obsidian, browsers)"
        )

    return avisos


# ── 3. Orquestração do pipeline completo ──────────────────────────────────────

def aplicar_pipeline_qualidade(
    md: str,
    origem: Path,
    usar_llm: bool = False,
    llm_fallback: bool = False,
) -> tuple[str, list[str]]:
    """
    Aplica o pipeline completo de qualidade ao Markdown extraído.

    Ordem obrigatória (ver docstring do módulo):
    1. corrigir_mojibake — antes de limpar_artefatos
    2. limpar_artefatos — remove soft hyphens etc.
    3. validar_qualidade — detecta problemas residuais → avisos
    4. LLM enhancement (opcional) — melhora qualidade via LLM

    Args:
        md: Markdown bruto extraído pelo conversor.
        origem: Path do arquivo de origem (para contexto no LLM e validar_qualidade).
        usar_llm: Se True, sempre aplica LLM (--llm).
        llm_fallback: Se True, aplica LLM só quando há avisos (--llm-fallback).

    Returns:
        (md_tratado, avisos) — avisos é lista vazia se qualidade OK.
    """
    md, _ = corrigir_mojibake(md)
    md = limpar_artefatos(md)
    avisos = validar_qualidade(md, origem)

    if usar_llm or (llm_fallback and avisos):
        if llm_disponivel():
            md, avisos_llm = melhorar_markdown(md, origem)
            avisos = validar_qualidade(md, origem) + avisos_llm
        elif usar_llm:
            avisos.append(
                "LLM não disponível — verifique PDF2MD_LLM_URL e se Ollama está rodando"
            )

    return md, avisos
