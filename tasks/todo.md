# pdf2md — Task Tracker

## Fase 0 — Bootstrap (🏗️ Infra & Cloud)
- [x] 0.1 Criar diretório do projeto
- [x] 0.2 Estrutura de pastas (`core/`, `gui/`, `tests/`, `tasks/`)
- [x] 0.3 `pyproject.toml` + dependências
- [x] 0.4 `.gitignore` completo
- [x] 0.5 `SECURITY.md`, `LICENSE MIT`, `README.md` skeleton
- [x] 0.6 `CLAUDE.md` do projeto (≤80 linhas)
- [x] 0.7 `.pre-commit-config.yaml` (detect-secrets + gitleaks)
- [x] 0.8 `ci.yml` GitHub Actions
- [ ] 0.9 `git init` + primeiro commit
- [ ] 0.10 `gh repo create mchlcs/pdf2md --public` + push
- [ ] 0.11 Branch protection `main` no GitHub

## Fase 1 — Core CLI Python (🔧 Backend Dev)
- [ ] 1.1 `core/converter.py` — `pdf_to_md(path: Path) -> str` + OCR páginas-imagem
- [ ] 1.2 `core/image_converter.py` — `image_to_md(path: Path) -> str` via Tesseract
- [ ] 1.3 `core/batch.py` — `batch_convert(in_dir, out_dir, workers=4)` mix PDF+imagem
- [ ] 1.4 `core/cli.py` — Typer CLI unificado
- [ ] 1.5 Error handling + rich log (inclui erro Tesseract ausente)
- [ ] 1.6 Validação de input (whitelist extensões, path traversal)
- [ ] 1.7 `core/__main__.py`

## Fase 2 — Testes (🧪 QA Agent)
- [ ] 2.1 Fixtures PDF: 5 tipos (texto, tabela, multi-col, lista, header/footer)
- [ ] 2.2 Fixtures imagem: PNG texto claro, JPG doc escaneado, HEIC captura tela
- [ ] 2.3 Golden MDs por fixture (PDF + imagem)
- [ ] 2.4 `test_converter.py`
- [ ] 2.5 `test_image_converter.py`
- [ ] 2.6 `test_batch.py` — mix PDF+imagem
- [ ] 2.7 Edge cases (PDF vazio, imagem sem texto, Tesseract ausente)
- [ ] 2.8 CI verde

## Fase 3 — GUI SwiftUI (🎨 Frontend Dev)
- [ ] 3.1 Xcode project `PDF2MD.app`
- [ ] 3.2 `ContentView.swift` drag-drop
- [ ] 3.3 Lista de arquivos com estado
- [ ] 3.4 Output folder picker
- [ ] 3.5 `BatchProcessor.swift` bridge Python
- [ ] 3.6 Progress bar
- [ ] 3.7 Notificação macOS on done
- [ ] 3.8 Sanitização de paths no bridge

## Fase 4 — Empacotamento (☁️ Infra & Cloud)
- [ ] 4.1 PyInstaller → binário standalone
- [ ] 4.2 Embute binário no .app
- [ ] 4.3 Build .app release
- [ ] 4.4 create-dmg → PDF2MD-v0.1.0.dmg
- [ ] 4.5 GitHub Release (⚠️ RED TASK — confirmar)

## Fase 5 — Review + Docs (🔒 Security Agent)
- [ ] 5.1 Code review (simplify)
- [ ] 5.2 Security review
- [ ] 5.3 README final
- [ ] 5.4 lessons.md atualizado
- [ ] 5.5 Tag v0.1.0

## Results
_Preencher após conclusão_
