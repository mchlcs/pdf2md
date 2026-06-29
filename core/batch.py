"""
Orquestra conversão em batch de múltiplos arquivos (PDFs, imagens, Word, PPTX, planilhas).
Paraleliza via ThreadPoolExecutor (compatível com PyInstaller one-file).
"""
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from core.converter import pdf_to_md
from core.doc_converter import doc_to_md
from core.formatter import add_obsidian_frontmatter
from core.image_converter import image_to_md
from core.pptx_converter import pptx_to_md
from core.quality import aplicar_pipeline_qualidade
from core.utils import (
    EXTENSOES_DOC,
    EXTENSOES_IMAGEM,
    EXTENSOES_PDF,
    EXTENSOES_PERMITIDAS,
    EXTENSOES_PLANILHA,
    EXTENSOES_PPTX,
    sanitizar_mensagem_erro,
    validar_path_seguro,
)
from core.xlsx_converter import planilha_to_md

# Registry de conversores: mapeia frozenset de extensões → função conversora.
# Adicionar um formato novo = uma linha aqui (antes eram 5 ramos if/elif).
_CONVERSORES: list[tuple[frozenset[str], Callable[[Path], str]]] = [
    (EXTENSOES_PDF, pdf_to_md),
    (EXTENSOES_IMAGEM, image_to_md),
    (EXTENSOES_DOC, doc_to_md),
    (EXTENSOES_PPTX, pptx_to_md),
    (EXTENSOES_PLANILHA, planilha_to_md),
]


class StatusArquivo(Enum):
    AGUARDANDO = "aguardando"
    PROCESSANDO = "processando"
    CONCLUIDO = "concluido"
    ERRO = "erro"
    IGNORADO = "ignorado"


@dataclass
class ResultadoArquivo:
    origem: Path
    destino: Path | None
    status: StatusArquivo
    erro: str | None = None
    duracao: float = 0.0          # segundos gastos na conversão deste arquivo
    avisos: list[str] = field(default_factory=list)  # avisos de qualidade (não impedem CONCLUIDO)


def _nome_destino_unico(arq: Path, usados: set[str]) -> str:
    """
    Gera nome de saída .md único dentro do batch.

    O primeiro arquivo de um stem mantém `<stem>.md`. Colisões subsequentes
    (mesmo stem, extensão diferente — ex: relatorio.pdf + relatorio.docx)
    recebem o sufixo da extensão de origem para evitar sobrescrita silenciosa
    sob ThreadPoolExecutor: `<stem>-<ext>.md`, depois `<stem>-<ext>-2.md`, etc.

    Determinístico porque a lista de arquivos é percorrida em ordem (sorted).
    """
    base = arq.stem + ".md"
    if base not in usados:
        return base
    ext = arq.suffix.lstrip(".").lower()
    candidato = f"{arq.stem}-{ext}.md"
    contador = 2
    while candidato in usados:
        candidato = f"{arq.stem}-{ext}-{contador}.md"
        contador += 1
    return candidato


def _processar_arquivo(
    origem_str: str,
    destino_str: str,
    obsidian: bool,
    sobrescrever: bool,
    usar_llm: bool = False,
    llm_fallback: bool = False,
) -> dict:
    """
    Worker executado em ThreadPoolExecutor. Recebe/retorna tipos simples
    (strings, dict) para uma fronteira de dados limpa entre as threads.
    """
    origem = Path(origem_str)
    destino = Path(destino_str)
    inicio = time.perf_counter()

    # Se não sobrescrever e destino existe, pula — IGNORADO distingue de conversão bem-sucedida
    if not sobrescrever and destino.exists():
        return {
            "origem": origem_str,
            "destino": destino_str,
            "status": StatusArquivo.IGNORADO.value,
            "erro": None,
            "duracao": 0.0,
            "avisos": [],
        }

    try:
        sufixo = origem.suffix.lower()
        conversor = next(
            (fn for exts, fn in _CONVERSORES if sufixo in exts), None
        )
        if conversor is None:
            return {
                "origem": origem_str,
                "destino": None,
                "status": StatusArquivo.IGNORADO.value,
                "erro": None,
                "duracao": 0.0,
                "avisos": [],
            }

        md = conversor(origem)

        # Pipeline de qualidade (ordem importa — ver docstring de quality.py)
        md, avisos = aplicar_pipeline_qualidade(md, origem, usar_llm, llm_fallback)

        if obsidian:
            md = add_obsidian_frontmatter(md, origem)

        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(md, encoding="utf-8")

        return {
            "origem": origem_str,
            "destino": destino_str,
            "status": StatusArquivo.CONCLUIDO.value,
            "erro": None,
            "duracao": round(time.perf_counter() - inicio, 3),
            "avisos": avisos,
        }
    except Exception as exc:
        # Sanitiza mensagem de erro via regex — não expõe paths absolutos.
        # Mais robusto que comparar strings exatas: cobre symlink resolvido
        # (ex: /var → /private/var no macOS), diferença de maiúsculas em
        # filesystems case-insensitive e barra final, que fariam o antigo
        # str.replace(str(origem), ...) falhar silenciosamente.
        msg = sanitizar_mensagem_erro(str(exc))
        return {
            "origem": origem_str,
            "destino": None,
            "status": StatusArquivo.ERRO.value,
            "erro": msg,
            "duracao": round(time.perf_counter() - inicio, 3),
            "avisos": [],
        }


def batch_convert(
    origem: Path,
    destino: Path,
    workers: int = 4,
    sobrescrever: bool = False,
    vault: Path | None = None,
    obsidian: bool = False,
    usar_llm: bool = False,
    llm_fallback: bool = False,
) -> list[ResultadoArquivo]:
    """
    Converte todos os arquivos suportados em `origem` para Markdown em `destino`.

    Comportamento:
    - Se `origem` é arquivo único: processa só ele
    - Se `origem` é diretório: varre recursivamente (não recursivo por padrão — só nível raiz)
    - Arquivos com extensão não suportada: StatusArquivo.IGNORADO (sem erro)
    - Formatos suportados: PDF, imagens (PNG/JPG/TIFF/WEBP/BMP/HEIC), DOC, DOCX, PPTX, XLSX, CSV
    - `sobrescrever=False`: pula arquivos já existentes no destino
    - `vault` definido: output vai direto para `vault/` (cria se não existir)
    - `obsidian=True` (ou vault definido): aplica frontmatter antes de salvar
    - Paraleliza via `concurrent.futures.ThreadPoolExecutor(max_workers=workers)`
    - Erros individuais não interrompem o batch — capturados em ResultadoArquivo.erro

    Args:
        origem: Arquivo ou diretório de entrada.
        destino: Diretório de saída (criado se não existir). Ignorado se vault definido.
        workers: Número de processos paralelos.
        sobrescrever: Se True, sobrescreve MDs existentes.
        vault: Path para raiz do Obsidian vault. Output vai direto para vault/.
        obsidian: Se True, adiciona frontmatter Obsidian ao MD gerado.

    Returns:
        Lista de ResultadoArquivo com status de cada arquivo processado.

    Raises:
        FileNotFoundError: Se `origem` não existe.
        NotADirectoryError: Se `vault` definido mas não é diretório.
    """
    # Valida traversal antes de qualquer I/O — previne ../../etc/passwd.pdf
    validar_path_seguro(origem)

    if not origem.exists():
        raise FileNotFoundError(f"Origem não encontrada: {origem.name}")

    if vault is not None:
        if not vault.is_dir():
            raise NotADirectoryError(f"Vault inválido: {vault.name} não é um diretório")
        destino = vault
        obsidian = True

    destino.mkdir(parents=True, exist_ok=True)

    # Coleta arquivos
    arquivos = [origem] if origem.is_file() else sorted(origem.iterdir())

    # Valida traversal em cada arquivo coletado
    for arq in arquivos:
        validar_path_seguro(arq)

    # Prepara tarefas
    tarefas: list[tuple[Path, Path]] = []
    resultados: list[ResultadoArquivo] = []
    nomes_usados: set[str] = set()

    for arq in arquivos:
        if arq.is_dir():
            continue
        if arq.suffix.lower() not in EXTENSOES_PERMITIDAS:
            resultados.append(ResultadoArquivo(
                origem=arq,
                destino=None,
                status=StatusArquivo.IGNORADO,
                erro=None,
            ))
            continue

        nome_md = _nome_destino_unico(arq, nomes_usados)
        nomes_usados.add(nome_md)
        destino_arq = destino / nome_md
        tarefas.append((arq, destino_arq))

    # Executa em paralelo via threads (compatível com PyInstaller one-file)
    # fitz e pytesseract liberam GIL em operações C, então threads têm paralelismo real
    if tarefas:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    _processar_arquivo,
                    str(arq),
                    str(dest),
                    obsidian,
                    sobrescrever,
                    usar_llm,
                    llm_fallback,
                ): (arq, dest)
                for arq, dest in tarefas
            }

            for future in as_completed(futures):
                arq, dest = futures[future]
                try:
                    res = future.result()
                    resultados.append(ResultadoArquivo(
                        origem=Path(res["origem"]),
                        destino=Path(res["destino"]) if res["destino"] else None,
                        status=StatusArquivo(res["status"]),
                        erro=res["erro"],
                        duracao=res.get("duracao", 0.0),
                        avisos=res.get("avisos", []),
                    ))
                except Exception as exc:
                    # Mesma sanitização aplicada em _processar_arquivo (linha
                    # ~164) — este handler captura falhas do próprio
                    # ThreadPoolExecutor (ex: future cancelada/exceção não
                    # tratada) e também pode propagar paths absolutos do
                    # usuário em str(exc) (CWE-209).
                    resultados.append(ResultadoArquivo(
                        origem=arq,
                        destino=None,
                        status=StatusArquivo.ERRO,
                        erro=sanitizar_mensagem_erro(str(exc)),
                    ))

    return resultados
