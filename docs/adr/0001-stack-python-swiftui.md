# ADR 0001: Stack Python + SwiftUI

## Status
Aceito

## Contexto
Precisamos de um app macOS que converta PDFs e imagens para Markdown, com batch processing e integração ao Obsidian vault. O app deve ser leve, sem custos de licença, e sem dependências de APIs pagas.

## Decisão
Usar Python CLI como engine de conversão + SwiftUI como wrapper nativo macOS.

## Razão
- Zero custo de licenças.
- Ecossistema Python rico para PDF/OCR (pymupdf4llm, pytesseract, Pillow).
- SwiftUI nativo macOS proporciona experiência de usuário integrada ao sistema.
- Sem modelos ML pesados ou APIs pagas.

## Alternativas rejeitadas
- **Tauri (Rust):** Sem OCR libs maduras, curva de aprendizado alta para Rust.
- **Electron:** Pesado (~200MB overhead), performance inferior para batch processing.
- **Apple Vision (Swift nativo):** Requer Swift para OCR, complica a CLI standalone.

## Consequências
- Duas linguagens no projeto (Python + Swift).
- Necessidade de bridge via Process() no Swift para chamar binário Python.
- CLI Python testável standalone.
