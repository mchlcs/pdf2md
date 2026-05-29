// ContentView.swift
// Interface principal: drag-drop + configurações + progresso
import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @StateObject private var processador = BatchProcessor()
    @State private var arquivosSelecionados: [URL] = []
    @State private var pastaDestino: URL?
    @State private var modoObsidian: Bool = false
    @State private var vaultPath: URL?
    @State private var isDragOver: Bool = false

    var body: some View {
        VStack(spacing: 20) {
            // Zona drag-drop
            ZStack {
                RoundedRectangle(cornerRadius: 12)
                    .stroke(isDragOver ? Color.blue : Color.gray, lineWidth: 2)
                    .background(isDragOver ? Color.blue.opacity(0.1) : Color.clear)
                    .frame(height: 120)

                VStack {
                    Image(systemName: "doc.badge.arrow.up")
                        .font(.system(size: 40))
                        .foregroundColor(isDragOver ? .blue : .gray)
                    Text("Arraste PDFs e imagens aqui")
                        .foregroundColor(.secondary)
                }
            }
            .onDrop(of: [UTType.fileURL.identifier], isTargeted: $isDragOver) { providers in
                handleDrop(providers: providers)
                return true
            }

            // Lista de arquivos
            if !arquivosSelecionados.isEmpty {
                List(arquivosSelecionados, id: \.self) { url in
                    HStack {
                        statusIcon(for: url)
                        Text(url.lastPathComponent)
                            .lineLimit(1)
                        Spacer()
                    }
                }
                .frame(maxHeight: 200)
            }

            // Seção Saída
            GroupBox("Saída") {
                HStack {
                    Text(pastaDestino?.lastPathComponent ?? "Selecionar pasta…")
                        .foregroundColor(pastaDestino == nil ? .secondary : .primary)
                    Spacer()
                    Button("Escolher…") {
                        selecionarPastaDestino()
                    }
                }
            }

            // Seção Obsidian
            GroupBox("Obsidian") {
                VStack(alignment: .leading, spacing: 10) {
                    Toggle("Modo Obsidian", isOn: $modoObsidian)

                    if modoObsidian {
                        HStack {
                            Text(vaultPath?.lastPathComponent ?? "Selecionar vault…")
                                .foregroundColor(vaultPath == nil ? .secondary : .primary)
                            Spacer()
                            Button("Escolher…") {
                                selecionarVault()
                            }
                        }
                    }
                }
            }

            // Botão Converter
            Button("Converter") {
                iniciarConversao()
            }
            .disabled(arquivosSelecionados.isEmpty || (pastaDestino == nil && vaultPath == nil))
            .buttonStyle(.borderedProminent)
            .controlSize(.large)

            // Progresso — barra linear com contagem
            if processador.estaProcessando {
                let total = processador.progresso.count
                let concluidos = processador.progresso.filter {
                    $0.status == "concluido" || $0.status == "erro"
                }.count
                VStack(spacing: 4) {
                    ProgressView(value: Double(concluidos), total: Double(max(total, 1)))
                        .progressViewStyle(.linear)
                    Text("\(concluidos) / \(total)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            if processador.concluido {
                Button("Limpar") {
                    limpar()
                }
                .buttonStyle(.bordered)
            }

            Spacer()
        }
        .padding()
        .frame(minWidth: 500, minHeight: 400)
    }

    private func statusIcon(for url: URL) -> some View {
        let progresso = processador.progresso.first { $0.id == url.path }
        switch progresso?.status {
        case "concluido":
            return Image(systemName: "checkmark.circle.fill")
                .foregroundColor(.green)
        case "erro":
            return Image(systemName: "xmark.circle.fill")
                .foregroundColor(.red)
        case "processando":
            return Image(systemName: "arrow.2.circlepath")
                .foregroundColor(.blue)
        default:
            return Image(systemName: "clock")
                .foregroundColor(.gray)
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

    private func selecionarPastaDestino() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        if panel.runModal() == .OK {
            pastaDestino = panel.url?.resolvingSymlinksInPath()
        }
    }

    private func selecionarVault() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.message = "Selecione a raiz do vault Obsidian"
        if panel.runModal() == .OK {
            vaultPath = panel.url?.resolvingSymlinksInPath()
        }
    }

    private func iniciarConversao() {
        Task {
            await processador.iniciarConversao(
                arquivos: arquivosSelecionados,
                destino: pastaDestino,
                vault: vaultPath,
                obsidian: modoObsidian
            )
        }
    }

    private func limpar() {
        arquivosSelecionados.removeAll()
        pastaDestino = nil
        vaultPath = nil
        modoObsidian = false
        processador.limpar()
    }
}
