#!/usr/bin/env bash
#
# build_app.sh — Empacota o pdf2md como .app + .dmg para macOS (Apple Silicon).
#
# Pipeline:
#   1. PyInstaller: core/cli.py → binário one-file `pdf2md`
#   2. swiftc: gui/PDF2MD/*.swift → executável `PDF2MD` (sem Xcode, só CLT)
#   3. Monta PDF2MD.app (Info.plist + ícone + binário Python embarcado)
#   4. Codesign ad-hoc (sem Apple Developer ID — usuário usa "abrir mesmo assim")
#   5. hdiutil → PDF2MD-v<versão>.dmg
#
# Sem paths hardcoded: tudo derivado do local do script, do pyproject e do
# ambiente Python ativo. Pré-requisito: `pip install ".[dev]"` no venv ativo
# (pyinstaller + deps) e Command Line Tools (swiftc, hdiutil, codesign).
#
# Uso: ./scripts/build_app.sh
set -euo pipefail

# ── Paths base (derivados, nunca hardcoded) ─────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAIZ="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${RAIZ}"

DIST="${RAIZ}/dist"
BUILD="${RAIZ}/build"
APP="${DIST}/PDF2MD.app"

# ── Versão: fonte única é o pyproject.toml ──────────────────────────────────
VERSAO="$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")"
# Número de build incremental e reproduzível (contagem de commits)
BUILD_NUM="$(git rev-list --count HEAD 2>/dev/null || echo 1)"

echo "▶ pdf2md build — versão ${VERSAO} (build ${BUILD_NUM})"

# ── 1. PyInstaller: binário Python one-file ─────────────────────────────────
# pymupdf precisa dos resources de layout embarcados (senão FileNotFoundError
# em runtime no binário congelado).
PYMUPDF_RES="$(python3 -c "import pymupdf, os; print(os.path.join(os.path.dirname(pymupdf.__file__), 'layout', 'resources'))")"
if [[ ! -d "${PYMUPDF_RES}" ]]; then
    echo "✗ resources do pymupdf não encontrados: ${PYMUPDF_RES}" >&2
    exit 1
fi

echo "▶ [1/5] PyInstaller → dist/pdf2md"
pyinstaller core/cli.py \
    --onefile \
    --name pdf2md \
    --add-data "${PYMUPDF_RES}:pymupdf/layout/resources" \
    --collect-submodules pymupdf4llm \
    --collect-submodules mammoth \
    --hidden-import pillow_heif \
    --distpath "${DIST}" \
    --workpath "${BUILD}/pyinstaller" \
    --specpath "${BUILD}" \
    --noconfirm \
    --clean

[[ -f "${DIST}/pdf2md" ]] || { echo "✗ binário pdf2md não gerado" >&2; exit 1; }

# ── 2. swiftc: executável da GUI ────────────────────────────────────────────
echo "▶ [2/5] swiftc → PDF2MD (executável SwiftUI)"
rm -rf "${APP}"
mkdir -p "${APP}/Contents/MacOS" "${APP}/Contents/Resources"

swiftc -parse-as-library -O \
    -target arm64-apple-macos13 \
    gui/PDF2MD/PDF2MDApp.swift \
    gui/PDF2MD/ContentView.swift \
    gui/PDF2MD/BatchProcessor.swift \
    -o "${APP}/Contents/MacOS/PDF2MD"

# ── 3. Monta o bundle .app ──────────────────────────────────────────────────
echo "▶ [3/5] Montando PDF2MD.app"
cp "${DIST}/pdf2md" "${APP}/Contents/Resources/pdf2md"
cp "gui/PDF2MD/Assets.xcassets/AppIcon.appiconset/AppIcon.icns" \
   "${APP}/Contents/Resources/AppIcon.icns"

cat > "${APP}/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>pdf2md</string>
    <key>CFBundleDisplayName</key><string>pdf2md</string>
    <key>CFBundleIdentifier</key><string>com.mchlcs.pdf2md</string>
    <key>CFBundleVersion</key><string>${BUILD_NUM}</string>
    <key>CFBundleShortVersionString</key><string>${VERSAO}</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleExecutable</key><string>PDF2MD</string>
    <key>CFBundleIconFile</key><string>AppIcon</string>
    <key>LSMinimumSystemVersion</key><string>13.0</string>
    <key>NSHighResolutionCapable</key><true/>
    <key>NSSupportsAutomaticGraphicsSwitching</key><true/>
    <key>NSPrincipalClass</key><string>NSApplication</string>
</dict>
</plist>
PLIST

# ── 4. Codesign ad-hoc ──────────────────────────────────────────────────────
# Sem Apple Developer ID: assinatura ad-hoc (-). Gatekeeper exige
# "clicar com botão direito → Abrir" na primeira execução.
echo "▶ [4/5] Codesign ad-hoc"
codesign --force --deep --sign - "${APP}"
codesign --verify --deep --strict "${APP}" && echo "  ✓ assinatura válida"

# ── 5. DMG ──────────────────────────────────────────────────────────────────
# NÃO usar `hdiutil create -srcfolder` com o symlink /Applications: o auto-size
# segue o symlink e estoura a imagem ("no space"). Em vez disso: imagem RW com
# tamanho EXPLÍCITO → monta → copia app + symlink → desmonta → comprime (UDZO).
echo "▶ [5/5] hdiutil → DMG"
VOLNAME="pdf2md ${VERSAO}"
DMG_RW="${BUILD}/pdf2md-rw.dmg"
DMG_OUT="${DIST}/PDF2MD-v${VERSAO}.dmg"

# Limpa montagens/artefatos de execuções anteriores (volumes pdf2md stale)
for v in /Volumes/pdf2md*; do
    [[ -d "${v}" ]] && hdiutil detach "${v}" >/dev/null 2>&1 || true
done
rm -f "${DMG_RW}" "${DMG_OUT}"

# Tamanho = app + 40MB de margem
TAM_MB="$(du -sm "${APP}" | awk '{print $1 + 40}')"
# Imagem RW vazia: -size + -fs (SEM -format, que exigiria -srcfolder).
hdiutil create -volname "${VOLNAME}" -fs HFS+ \
    -size "${TAM_MB}m" -ov "${DMG_RW}" -quiet

# Monta em /Volumes/<volname>, captura o device node (detach por device +
# -force é confiável; detach por mountpoint falha com "resource busy" logo
# após o cp).
MONTADO="/Volumes/${VOLNAME}"
DEV="$(hdiutil attach "${DMG_RW}" -nobrowse -noverify | grep -E '^/dev/' | head -1 | awk '{print $1}')"
cp -RP "${APP}" "${MONTADO}/"
ln -s /Applications "${MONTADO}/Applications"
sync
hdiutil detach "${DEV}" -force -quiet

# Converte read-write → comprimido (UDZO) — o .dmg final de distribuição
hdiutil convert "${DMG_RW}" -format UDZO -o "${DMG_OUT}" -quiet
rm -f "${DMG_RW}"

echo ""
echo "✓ Build completo:"
echo "  .app → ${APP}"
echo "  .dmg → ${DMG_OUT}"
echo ""
echo "Próximo: gh release create v${VERSAO} \"${DMG_OUT}\""
