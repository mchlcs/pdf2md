// BatchProcessor.swift
// Bridge entre SwiftUI e binário Python pdf2md.
// Executa Process(), captura stdout JSON, publica progresso via @Published.
import Foundation
import Combine
import UserNotifications

struct ProgressoArquivo: Identifiable, Codable {
    let id: String      // path do arquivo origem
    let status: String  // "aguardando" | "processando" | "concluido" | "erro" | "cancelado"
    let erro: String?
}

@MainActor
class BatchProcessor: ObservableObject {
    @Published var progresso: [ProgressoArquivo] = []
    @Published var estaProcessando: Bool = false
    @Published var concluido: Bool = false

    // Processo ativo — referência para cancelamento imediato
    private var processoAtivo: Process?

    // Localiza binário Python embarcado no bundle
    private var caminhoBinario: URL? {
        Bundle.main.url(forResource: "pdf2md", withExtension: nil)
    }

    func iniciarConversao(
        arquivos: [URL],
        destino: URL?,
        vault: URL?,
        obsidian: Bool
    ) async {
        guard let binario = caminhoBinario else {
            print("Binário pdf2md não encontrado no bundle")
            return
        }

        estaProcessando = true
        concluido = false

        // Sanitização: filtrar URLs fora do diretório home ANTES de processar
        let home = FileManager.default.homeDirectoryForCurrentUser
        let arquivosValidos: [URL] = arquivos.compactMap { url in
            let seguro = url.resolvingSymlinksInPath()
            guard seguro.path.hasPrefix(home.path) else {
                let rejeitado = ProgressoArquivo(
                    id: url.path,
                    status: "erro",
                    erro: "Path fora do diretório home"
                )
                progresso.append(rejeitado)
                return nil
            }
            return seguro
        }

        // Inicializa progresso apenas para arquivos válidos
        let progressoInicial = arquivosValidos.map {
            ProgressoArquivo(id: $0.path, status: "aguardando", erro: nil)
        }
        progresso.append(contentsOf: progressoInicial)

        // Processa cada arquivo válido com suporte a cancelamento
        for url in arquivosValidos {
            // Verifica cancelamento antes de cada arquivo
            if Task.isCancelled {
                atualizarProgresso(id: url.path, status: "cancelado", erro: nil)
                continue
            }

            atualizarProgresso(id: url.path, status: "processando", erro: nil)

            // Monta args: ORIGEM [DESTINO] [--vault PATH] [--obsidian] --json
            var args: [String] = [url.path]

            if let v = vault {
                let vSeguro = v.resolvingSymlinksInPath()
                args.append("--vault")
                args.append(vSeguro.path)
            } else if let dest = destino {
                let destSeguro = dest.resolvingSymlinksInPath()
                args.append(destSeguro.path)
            }

            if obsidian {
                args.append("--obsidian")
            }

            // --json ao final (posição correta para Typer)
            args.append("--json")

            let processo = Process()
            processo.executableURL = binario
            processo.arguments = args

            let stdoutPipe = Pipe()
            let stderrPipe = Pipe()
            processo.standardOutput = stdoutPipe
            processo.standardError = stderrPipe

            // Guarda referência para cancelamento imediato
            processoAtivo = processo

            do {
                try processo.run()

                // Aguarda sem bloquear MainActor
                await withTaskCancellationHandler {
                    await withCheckedContinuation { continuation in
                        Task.detached {
                            processo.waitUntilExit()
                            continuation.resume()
                        }
                    }
                } onCancel: {
                    processo.terminate()
                }

                // Se foi cancelado durante a espera
                if Task.isCancelled {
                    atualizarProgresso(id: url.path, status: "cancelado", erro: nil)
                    continue
                }

                if let data = try? stdoutPipe.fileHandleForReading.readDataToEndOfFile(),
                   let string = String(data: data, encoding: .utf8) {
                    for linha in string.split(separator: "\n") {
                        if let jsonData = String(linha).data(using: .utf8),
                           let item = try? JSONDecoder().decode(ProgressoArquivo.self, from: jsonData) {
                            atualizarProgresso(id: item.id, status: item.status, erro: item.erro)
                        }
                    }
                }
            } catch {
                atualizarProgresso(id: url.path, status: "erro", erro: "Falha ao executar processo")
            }
        }

        processoAtivo = nil
        estaProcessando = false
        concluido = !Task.isCancelled

        if concluido {
            emitirNotificacao()
        }
    }

    /// Cancela conversão em curso — termina processo ativo imediatamente.
    func cancelar() {
        processoAtivo?.terminate()
        processoAtivo = nil
        estaProcessando = false
        concluido = false
    }

    private func atualizarProgresso(id: String, status: String, erro: String?) {
        if let index = progresso.firstIndex(where: { $0.id == id }) {
            progresso[index] = ProgressoArquivo(id: id, status: status, erro: erro)
        }
    }

    private func emitirNotificacao() {
        let center = UNUserNotificationCenter.current()
        center.requestAuthorization(options: [.alert, .sound]) { _, _ in }

        let content = UNMutableNotificationContent()
        content.title = "pdf2md"
        let sucessos = progresso.filter { $0.status == "concluido" }.count
        let erros = progresso.filter { $0.status == "erro" }.count
        let cancelados = progresso.filter { $0.status == "cancelado" }.count
        var partes: [String] = []
        if sucessos > 0 { partes.append("\(sucessos) concluídos") }
        if erros > 0 { partes.append("\(erros) erros") }
        if cancelados > 0 { partes.append("\(cancelados) cancelados") }
        content.body = partes.joined(separator: " · ")
        content.sound = .default

        let request = UNNotificationRequest(
            identifier: UUID().uuidString,
            content: content,
            trigger: nil
        )
        center.add(request)
    }

    func limpar() {
        progresso.removeAll()
        estaProcessando = false
        concluido = false
        processoAtivo = nil
    }
}
