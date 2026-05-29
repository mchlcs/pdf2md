# ADR 0002: OCR via Tesseract

## Status
Aceito

## Contexto
O app precisa extrair texto de PDFs escaneados e imagens. A solução deve ser gratuita, suportar PT-BR e EN, e não exigir modelos de ML pesados.

## Decisão
Usar Tesseract OCR via pytesseract com pré-processamento Pillow.

## Razão
- Free, MIT license.
- Integrado via pip (pytesseract).
- Suporte nativo a PT-BR + EN (lang=por+eng).
- Sem modelos ML pesados (diferente de EasyOCR que exige ~1GB de modelos).
- Pré-processamento Pillow (escala de cinza, redimensionamento) melhora qualidade OCR.

## Alternativas rejeitadas
- **Apple Vision:** Requer Swift, complica a CLI standalone.
- **EasyOCR:** ~1GB de modelos, overhead significativo.
- **Google Cloud Vision API:** Paga, requer conectividade.

## Consequências
- Dependência de Tesseract instalado no sistema (brew install tesseract).
- Necessidade de verificar instalação antes de executar OCR.
- Pré-processamento de imagem adiciona overhead mas melhora acurácia.
