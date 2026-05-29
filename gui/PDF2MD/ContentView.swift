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
                    // Zona drag-drop
                    zonaArrastar
                        .padding(.top, 16)

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
                    }

                    // Botões de ação
                    botoesAcao

                    // Progresso
                    if processador.estaProcessando {
                        barraProgresso
                    }

                    Spacer(minLength: 16)
                }
                .padding(.horizontal, 16)
            }
        }
        .frame(minWidth: 480, minHeight: 420)
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
                Text("PDF · PNG · JPG · TIFF · WEBP · BMP · HEIC")
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
                    if let prog = processador.progresso.first(where: { $0.id == url.path }),
                       let err = prog.erro {
                        Text(err)
                            .font(.caption)
                            .foregroundColor(.red)
                            .lineLimit(1)
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
        let concluidos = processador.progresso.filter {
            $0.status == "concluido" || $0.status == "erro" || $0.status == "cancelado"
        }.count
        return VStack(spacing: 4) {
            ProgressView(value: Double(concluidos), total: Double(max(total, 1)))
                .progressViewStyle(.linear)
            Text("\(concluidos) / \(total)")
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

    private func handleDrop(providers: [NSItemProvider]) {
        for provider in providers {
            provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier, options: nil) { item, _ in
                if let data = item as? Data,
                   let url = URL(dataRepresentation: data, relativeTo: nil) {
                    DispatchQueue.main.async {
                        let seguro = url.resolvingSymlinksInPath()
                        if !self.arquivosSelecionados.contains(seguro) {
                            self.arquivosSelecionados.append(seguro)
                        }
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
        arquivosSelecionados.removeAll()
        caminho = nil
        modoObsidian = false
        processador.limpar()
        tarefaConversao = nil
    }
}
