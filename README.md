# pdf2md

Converte PDFs, imagens e documentos Word em Markdown — em batch, com integração ao Obsidian vault.

![CI](https://github.com/mchlcs/pdf2md/actions/workflows/ci.yml/badge.svg)

## Requisito obrigatório — Tesseract OCR

pdf2md usa o **Tesseract** para reconhecer texto em PDFs escaneados e imagens.  
Sem ele, o app não inicia.

```bash
brew install tesseract tesseract-lang
```

> `tesseract-lang` inclui suporte ao **português** (`por`). Necessário para documentos em PT-BR.

## Formatos suportados

| Formato | Conversão |
|---------|-----------|
| `.pdf` | Extração de texto nativa + OCR automático para páginas-imagem |
| `.docx` | mammoth — preserva headers, negrito, listas |
| `.doc` | antiword (`brew install antiword`) |
| `.png` `.jpg` `.jpeg` `.tiff` `.webp` `.bmp` `.heic` | OCR via Tesseract |

## App macOS (GUI)

1. Baixe `PDF2MD-vX.X.X.dmg` em [Releases](https://github.com/mchlcs/pdf2md/releases)
2. Arraste **PDF2MD.app** para Applications
3. **Primeira abertura:** clique direito → Abrir (bypass Gatekeeper — app sem assinatura paga)
4. Instale o Tesseract (passo acima)

### Modo Obsidian

Ative o toggle **Modo Obsidian** para:
- Adicionar frontmatter YAML automático a cada MD gerado
- Salvar direto na raiz do vault (selecione a pasta raiz do vault)

```yaml
---
title: nome-do-arquivo
source: original.pdf
converted: 2026-05-29
tags:
  - pdf2md
  - converted
---
```

## CLI

```bash
# Instalar dependências
pip3 install pymupdf4llm pytesseract Pillow pillow-heif PyYAML typer rich mammoth python-docx

# Converter arquivo único
pdf2md arquivo.pdf saida/

# Converter pasta inteira (paralelo)
pdf2md pasta/docs/ saida/ --workers 8

# Com frontmatter Obsidian
pdf2md arquivo.pdf saida/ --obsidian

# Direto no vault (raiz do vault)
pdf2md pasta/docs/ --vault ~/Obsidian/meu-vault
```

## Desenvolvimento

```bash
git clone https://github.com/mchlcs/pdf2md
cd pdf2md
pip3 install -e ".[dev]"
python3 -m pytest tests/ -v
```

## Stack

| Componente | Tecnologia |
|-----------|-----------|
| PDF → MD | `pymupdf4llm` + `PyMuPDF` |
| OCR | `tesseract` + `pytesseract` |
| Imagens | `Pillow` + `pillow-heif` (HEIC) |
| DOCX | `mammoth` |
| DOC | `antiword` (brew) |
| CLI | `typer` + `rich` |
| GUI | SwiftUI (macOS 13+) |
| CI | GitHub Actions |

## Licença

Código-fonte: **MIT** — ver [LICENSE](LICENSE).

O binário distribuído (`.dmg`) embarca **PyMuPDF** (AGPL-3.0) e outras
bibliotecas de terceiros. A distribuição do binário está sujeita aos termos
dessas licenças — ver [THIRD-PARTY-LICENSES.md](THIRD-PARTY-LICENSES.md). O
source correspondente é público (este repositório), cumprindo a AGPL.
