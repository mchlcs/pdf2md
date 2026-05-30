// ContentView.swift
// Interface principal: drag-drop + configurações + progresso
import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @StateObject private var processador = BatchProcessor()
    @State private var arquivosSelecionados: [URL] = []
    @State private var caminho: URL?          // único campo: pasta saída ou vault
    @State private var modoObsidian: Bool = false
    @State private var isDragOver: Bool = false
    @State private var tarefaConversao: Task<Void, Never>?
    @State private var erroColagem: String? = nil  // nil = sem alert; non-nil = mensagem exibida

    // Tipos permitidos no picker — calculado uma vez (fix: eficiência + UTType.doc via UTI canônica)
    private static let tiposPermitidos: [UTType] = {
        var tipos: [UTType] = [.pdf, .png, .jpeg, .tiff, .bmp, .heic]
        let wordUTIs = [
            "org.openxmlformats.officedocument.wordprocessingml.document",  // docx
            "com.microsoft.word.doc",                                        // doc
        ]
        tipos += wordUTIs.compactMap { UTType($0) }
        if let webp = UTType(filenameExtension: "webp") { tipos.append(webp) }
        return tipos
    }()

    // Pasta temporária para imagens coladas — compartilhada entre colarImagem e limpar
    private var pasteDir: URL {
        let base = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first
            ?? FileManager.default.temporaryDirectory
        return base.appendingPathComponent("pdf2md/pastes")
    }

    // Label e picker mudam conforme modo
    private var labelCaminho: String {
        modoObsidian ? "Vault Obsidian" : "Pasta de saída"
    }
    private var placeholderCaminho: String {
        modoObsidian ? "Selecionar vault…" : "Selecionar pasta…"
    }
    private var mensagemPicker: String {
        modoObsidian ? "Selecione a raiz do vault Obsidian" : "Selecione a pasta de saída"
    }

    var body: some View {
        VStack(spacing: 0) {
            // Header com logo
            cabecalho

            Divider()

            ScrollView {
                VStack(spacing: 16) {
                    // Zona drag-drop + ações
                    zonaArrastar
                        .padding(.top, 16)

                    botoesAdicionarArquivos

                    // Lista de arquivos
                    if !arquivosSelecionados.isEmpty {
                        listaArquivos
                    }

                    // Saída / Vault (campo unificado)
                    campoCaminho

                    // Toggle Obsidian
                    GroupBox {
                        Toggle("Modo Obsidian", isOn: $modoObsidian)
                            .onChange(of: modoObsidian) { _ in
                                caminho = nil  // limpa ao trocar modo
                            }
                            // Travado durante conversão: trocar o modo zeraria o
                            // caminho enquanto o job já roda com o path antigo.
                            .disabled(processador.estaProcessando)
                    }

                    // Botões de ação
                    botoesAcao

                    // Progresso
                    if processador.estaProcessando {
                        barraProgresso
                    }

                    // Tempo total ao concluir
                    if processador.concluido, let t = processador.duracaoTotal {
                        Text("Concluído em \(BatchProcessor.formatarDuracao(t))")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    Spacer(minLength: 16)
                }
                .padding(.horizontal, 16)
            }
        }
        .frame(minWidth: 480, minHeight: 420)
        // Alert com mensagem dinâmica — distingue clipboard vazio de erro de I/O
        .alert(
            "Erro ao colar imagem",
            isPresented: Binding(get: { erroColagem != nil }, set: { if !$0 { erroColagem = nil } })
        ) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(erroColagem ?? "")
        }
    }

    // MARK: — Subviews

    private var cabecalho: some View {
        HStack(spacing: 10) {
            Image("AppIcon")
                .resizable()
                .frame(width: 32, height: 32)
                .clipShape(RoundedRectangle(cornerRadius: 7))
            Text("pdf2md")
                .font(.headline)
            Spacer()
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(.bar)
    }

    private var botoesAdicionarArquivos: some View {
        HStack(spacing: 8) {
            Button {
                adicionarArquivos()
            } label: {
                Label("Procurar arquivos…", systemImage: "folder.badge.plus")
            }
            .buttonStyle(.bordered)
            .controlSize(.small)
            .disabled(processador.estaProcessando)

            Button {
                colarImagem()
            } label: {
                Label("Colar imagem", systemImage: "doc.on.clipboard")
            }
            .buttonStyle(.bordered)
            .controlSize(.small)
            .disabled(processador.estaProcessando)
            // Sem .keyboardShortcut("v") — evita interceptar Cmd+V de text fields futuros

            Spacer()
        }
    }

    private var zonaArrastar: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 12)
                .strokeBorder(
                    isDragOver ? Color.accentColor : Color.secondary.opacity(0.4),
                    style: StrokeStyle(lineWidth: 2, dash: [6])
                )
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(isDragOver ? Color.accentColor.opacity(0.08) : Color.clear)
                )
                .frame(height: 110)

            VStack(spacing: 6) {
                Image(systemName: "doc.badge.arrow.up")
                    .font(.system(size: 32))
                    .foregroundColor(isDragOver ? .accentColor : .secondary)
                Text("Arraste PDFs e imagens aqui")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                Text("PDF · DOCX · DOC · PNG · JPG · TIFF · WEBP · BMP · HEIC")
                    .font(.caption2)
                    .foregroundColor(.secondary.opacity(0.6))
            }
        }
        .onDrop(of: [UTType.fileURL.identifier], isTargeted: $isDragOver) { providers in
            handleDrop(providers: providers)
            return true
        }
    }

    private var listaArquivos: some View {
        GroupBox {
            List(arquivosSelecionados, id: \.self) { url in
                HStack {
                    statusIcon(for: url)
                    Text(url.lastPathComponent)
                        .lineLimit(1)
                        .font(.system(.body, design: .monospaced))
                    Spacer()
                    if let prog = processador.progresso.first(where: { $0.id == url.path }) {
                        if let err = prog.erro {
                            Text(err)
                                .font(.caption)
                                .foregroundColor(.red)
                                .lineLimit(1)
                        } else if let d = prog.duracao, d > 0 {
                            Text(BatchProcessor.formatarDuracao(d))
                                .font(.caption.monospacedDigit())
                                .foregroundColor(.secondary)
                        }
                    }
                }
            }
            .listStyle(.plain)
            .frame(height: min(CGFloat(arquivosSelecionados.count) * 32, 160))
        }
    }

    private var campoCaminho: some View {
        GroupBox(labelCaminho) {
            HStack {
                Label(
                    caminho?.lastPathComponent ?? placeholderCaminho,
                    systemImage: modoObsidian ? "diamond" : "folder"
                )
                .foregroundColor(caminho == nil ? .secondary : .primary)
                .lineLimit(1)
                Spacer()
                Button("Escolher…") {
                    selecionarCaminho()
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
            }
        }
    }

    private var botoesAcao: some View {
        HStack(spacing: 12) {
            if processador.estaProcessando {
                // Botão Cancelar — visível apenas durante conversão
                Button(role: .destructive) {
                    cancelarConversao()
                } label: {
                    Label("Cancelar", systemImage: "xmark.circle")
                }
                .buttonStyle(.bordered)
                .controlSize(.large)
                .keyboardShortcut(.escape, modifiers: [])
            }

            Button("Converter") {
                iniciarConversao()
            }
            .disabled(
                arquivosSelecionados.isEmpty ||
                caminho == nil ||
                processador.estaProcessando
            )
            .buttonStyle(.borderedProminent)
            .controlSize(.large)

            if processador.concluido {
                Button("Limpar") {
                    limpar()
                }
                .buttonStyle(.bordered)
                .controlSize(.large)
            }
        }
    }

    private var barraProgresso: some View {
        let total = processador.progresso.count
        let terminados = processador.progresso.filter {
            $0.status == "concluido" || $0.status == "erro" ||
            $0.status == "cancelado" || $0.status == "ignorado"
        }.count
        return VStack(spacing: 4) {
            ProgressView(value: Double(terminados), total: Double(max(total, 1)))
                .progressViewStyle(.linear)
            Text("\(terminados) / \(total)")
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }

    // MARK: — Helpers

    private func statusIcon(for url: URL) -> some View {
        let progresso = processador.progresso.first { $0.id == url.path }
        switch progresso?.status {
        case "concluido":
            return Image(systemName: "checkmark.circle.fill").foregroundColor(.green)
        case "ignorado":
            return Image(systemName: "equal.circle.fill").foregroundColor(.secondary)
        case "erro":
            return Image(systemName: "xmark.circle.fill").foregroundColor(.red)
        case "cancelado":
            return Image(systemName: "minus.circle.fill").foregroundColor(.orange)
        case "processando":
            return Image(systemName: "arrow.2.circlepath").foregroundColor(.accentColor)
        default:
            return Image(systemName: "clock").foregroundColor(.secondary)
        }
    }

    // Adiciona URL à fila se ainda não estiver presente — dedup centralizado
    private func adicionarSeNovo(_ url: URL) {
        let seguro = url.resolvingSymlinksInPath()
        if !arquivosSelecionados.contains(seguro) {
            arquivosSelecionados.append(seguro)
        }
    }

    private func adicionarArquivos() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = true
        panel.message = "Selecione arquivos para converter"
        panel.allowedContentTypes = Self.tiposPermitidos
        // Garante que o panel apareça na frente em cenários multi-janela (macOS 14+)
        NSApp.activate(ignoringOtherApps: true)
        if panel.runModal() == .OK {
            panel.urls.forEach { adicionarSeNovo($0) }
        }
    }

    private func colarImagem() {
        erroColagem = nil  // reset garante re-disparo do alert em falhas consecutivas
        let pasteboard = NSPasteboard.general
        guard let items = pasteboard.readObjects(forClasses: [NSImage.self], options: nil) as? [NSImage],
              let imagem = items.first else {
            erroColagem = "Nenhuma imagem no clipboard."
            return
        }
        guard let cachesBase = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first else {
            erroColagem = "Diretório de cache não encontrado."
            return
        }
        let dir = cachesBase.appendingPathComponent("pdf2md/pastes")
        do {
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            // UUID garante unicidade — sem colisão por segundo-granularity
            let destino = dir.appendingPathComponent("paste-\(UUID().uuidString).png")
            // Tenta TIFF→PNG; fallback CGImage para formatos vetoriais (PDF, SVG no clipboard)
            let pngData: Data
            if let tiff = imagem.tiffRepresentation,
               let rep = NSBitmapImageRep(data: tiff),
               let png = rep.representation(using: .png, properties: [:]) {
                pngData = png
            } else if let cgImg = imagem.cgImage(forProposedRect: nil, context: nil, hints: nil) {
                let rep = NSBitmapImageRep(cgImage: cgImg)
                guard let png = rep.representation(using: .png, properties: [:]) else {
                    erroColagem = "Não foi possível converter a imagem do clipboard."
                    return
                }
                pngData = png
            } else {
                erroColagem = "Não foi possível converter a imagem do clipboard."
                return
            }
            try pngData.write(to: destino)
            arquivosSelecionados.append(destino)  // UUID = sempre único, sem contains check
        } catch {
            erroColagem = "Erro ao salvar imagem: \(error.localizedDescription)"
        }
    }

    private func handleDrop(providers: [NSItemProvider]) {
        for provider in providers {
            provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier, options: nil) { item, _ in
                if let data = item as? Data,
                   let url = URL(dataRepresentation: data, relativeTo: nil) {
                    DispatchQueue.main.async {
                        self.adicionarSeNovo(url)
                    }
                }
            }
        }
    }

    private func selecionarCaminho() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.message = mensagemPicker
        if panel.runModal() == .OK {
            caminho = panel.url?.resolvingSymlinksInPath()
        }
    }

    private func iniciarConversao() {
        guard let destino = caminho else { return }
        tarefaConversao = Task {
            await processador.iniciarConversao(
                arquivos: arquivosSelecionados,
                destino: modoObsidian ? nil : destino,
                vault: modoObsidian ? destino : nil,
                obsidian: modoObsidian
            )
        }
    }

    private func cancelarConversao() {
        tarefaConversao?.cancel()
        processador.cancelar()
    }

    private func limpar() {
        // Deleta arquivos temporários de paste antes de limpar a lista
        let dir = pasteDir.path + "/"
        for url in arquivosSelecionados where url.path.hasPrefix(dir) {
            try? FileManager.default.removeItem(at: url)
        }
        arquivosSelecionados.removeAll()
        caminho = nil
        modoObsidian = false
        processador.limpar()
        tarefaConversao = nil
    }
}
