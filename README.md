# pdf2md

Converte PDFs, imagens, Word, PPTX e planilhas em Markdown — em batch, com integração ao Obsidian vault e fallback de qualidade via LLM local.

![CI](https://github.com/mchlcs/pdf2md/actions/workflows/ci.yml/badge.svg)

## Formatos suportados

| Formato | Conversão |
|---------|-----------|
| `.pdf` | Extração nativa + OCR automático para páginas-imagem |
| `.docx` | mammoth — preserva headers, negrito, listas, tabelas |
| `.doc` | antiword (`brew install antiword`) |
| `.pptx` | python-pptx — slides, títulos, tabelas |
| `.xlsx` | openpyxl — cada sheet vira tabela Markdown |
| `.csv` | stdlib — suporta BOM, UTF-8, Latin-1 (exports PT-BR) |
| `.png` `.jpg` `.jpeg` `.tiff` `.webp` `.bmp` `.heic` | OCR via Tesseract |

## Requisito — Tesseract OCR

Necessário para PDFs escaneados e imagens com texto.

```bash
brew install tesseract tesseract-lang
```

> `tesseract-lang` inclui suporte ao **português** (`por`). Necessário para documentos PT-BR.

## App macOS (GUI)

1. Baixe `PDF2MD-vX.X.X.dmg` em [Releases](https://github.com/mchlcs/pdf2md/releases)
2. Arraste **PDF2MD.app** para Applications
3. **Primeira abertura:** clique direito → Abrir (bypass Gatekeeper — app sem assinatura paga)
4. Instale o Tesseract (passo acima)

### Adicionar arquivos

Três formas de adicionar arquivos para conversão:
- **Arrastar** arquivos ou pastas para a zona de drop
- **Procurar arquivos…** — abre seletor com todos os formatos suportados
- **Colar imagem** — cola imagem do clipboard direto na fila (screenshots, cópias de browser)

### Modo Obsidian

Ative o toggle **Modo Obsidian** para:
- Adicionar frontmatter YAML automático a cada MD gerado
- Salvar direto na raiz do vault (selecione a pasta raiz do vault)

```yaml
---
title: nome-do-arquivo
source: original.pdf
converted: 2026-05-30
tags:
  - pdf2md
  - converted
---
```

### ⚡ Melhorar com IA (fallback)

Ative o toggle **Melhorar com IA** para usar um LLM local (Ollama) quando a conversão detecta problemas de qualidade (palavras quebradas, encoding corrompido, output muito curto).

Requer [Ollama](https://ollama.com) e a variável `PDF2MD_LLM_URL`:

```bash
brew install ollama
ollama pull llama3.2-vision
export PDF2MD_LLM_URL=http://localhost:11434/v1
```

Funciona também com Gemini, Groq, OpenRouter — ver seção CLI abaixo.

## CLI

```bash
# Instalar
pip3 install "pdf2md[dev]"  # ou: uv sync

# Converter arquivo único
pdf2md arquivo.pdf saida/
pdf2md apresentacao.pptx saida/
pdf2md planilha.xlsx saida/

# Converter pasta inteira (paralelo)
pdf2md pasta/docs/ saida/ --workers 8

# Com frontmatter Obsidian
pdf2md arquivo.pdf saida/ --obsidian

# Direto no vault
pdf2md pasta/docs/ --vault ~/Obsidian/meu-vault

# LLM fallback: melhora qualidade quando há problemas detectados
export PDF2MD_LLM_URL=http://localhost:11434/v1   # Ollama (grátis, local)
pdf2md scan_corrompido.pdf saida/ --llm-fallback

# LLM sempre (independente da qualidade)
pdf2md docs/ saida/ --llm
```

### Configuração LLM

| Provider | PDF2MD_LLM_URL | PDF2MD_LLM_MODEL |
|----------|----------------|------------------|
| Ollama (local, grátis) | `http://localhost:11434/v1` | `llama3.2-vision` |
| Gemini Flash (grátis, limite) | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.0-flash` |
| Groq (rápido, grátis) | `https://api.groq.com/openai/v1` | `llama-3.1-8b-instant` |

## Pipeline de qualidade

Cada conversão passa por um pipeline automático:

1. **Correção de mojibake** — corrige acentos PT-BR corrompidos (`Ã£`→`ã`, `Ã§`→`ç` etc.)
2. **Limpeza de artefatos** — remove hifens suaves (U+00AD), espaços de largura zero, BOM mid-string
3. **Validação** — detecta problemas residuais e exibe avisos ⚠ no CLI e GUI

Arquivos com problemas de qualidade aparecem com ícone âmbar (✓ laranja) na GUI e status `concluido⚠` no CLI.

## Desenvolvimento

```bash
git clone https://github.com/mchlcs/pdf2md
cd pdf2md
uv sync --extra dev
uv run pytest tests/ -v
uv run ruff check core/ tests/
```

## Stack

| Componente | Tecnologia |
|-----------|-----------|
| PDF → MD | `pymupdf4llm` + `PyMuPDF` |
| OCR | `tesseract` + `pytesseract` |
| Imagens | `Pillow` + `pillow-heif` (HEIC) |
| DOCX | `mammoth` |
| DOC | `antiword` (brew) |
| PPTX | `python-pptx` |
| XLSX | `openpyxl` |
| LLM fallback | OpenAI-compatible (Ollama/Gemini/Groq) via urllib |
| CLI | `typer` + `rich` |
| GUI | SwiftUI (macOS 13+) |
| CI | GitHub Actions |

## Licença

Código-fonte: **MIT** — ver [LICENSE](LICENSE).

O binário distribuído (`.dmg`) embarca **PyMuPDF** (AGPL-3.0) e outras
bibliotecas de terceiros. A distribuição do binário está sujeita aos termos
dessas licenças — ver [THIRD-PARTY-LICENSES.md](THIRD-PARTY-LICENSES.md). O
source correspondente é público (este repositório), cumprindo a AGPL.
