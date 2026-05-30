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
    let duracao: Double?  // segundos da conversão (vem do JSON do core); nil até concluir
}

@MainActor
class BatchProcessor: ObservableObject {
    @Published var progresso: [ProgressoArquivo] = []
    @Published var estaProcessando: Bool = false
    @Published var concluido: Bool = false
    @Published var duracaoTotal: TimeInterval?   // duração total da última conversão

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

        // Evita reentrância: ignora novo início enquanto uma conversão corre.
        // Sem isto, cancelar+reconverter cria duas execuções que se atropelam
        // no MainActor (zerando estaProcessando/processoAtivo da nova).
        guard !estaProcessando else { return }

        estaProcessando = true
        concluido = false
        duracaoTotal = nil
        progresso.removeAll()  // cada execução exibe apenas seus próprios arquivos
        let inicioTotal = Date()

        // Sanitização: filtrar URLs fora do diretório home ANTES de processar
        let home = FileManager.default.homeDirectoryForCurrentUser
        let arquivosValidos: [URL] = arquivos.compactMap { url in
            let seguro = url.resolvingSymlinksInPath()
            // Confinamento com fronteira de componente: home.path sem "/" final
            // deixaria /Users/bob prefixar /Users/bobby. Exige igualdade ou "/".
            guard seguro.path == home.path || seguro.path.hasPrefix(home.path + "/") else {
                let rejeitado = ProgressoArquivo(
                    id: url.path,
                    status: "erro",
                    erro: "Path fora do diretório home",
                    duracao: nil
                )
                progresso.append(rejeitado)
                return nil
            }
            return seguro
        }

        // Inicializa progresso apenas para arquivos válidos
        let progressoInicial = arquivosValidos.map {
            ProgressoArquivo(id: $0.path, status: "aguardando", erro: nil, duracao: nil)
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

                // Drena stdout E stderr concorrentemente enquanto aguarda o
                // término. Ler só após waitUntilExit() causaria deadlock: se o
                // processo-filho enche um pipe não-drenado (~64KB), bloqueia em
                // write() e nunca sai. Os dois pipes são lidos em tasks separadas.
                let stdoutData: Data = await withTaskCancellationHandler {
                    await withCheckedContinuation { (continuation: CheckedContinuation<Data, Never>) in
                        Task.detached {
                            _ = try? stderrPipe.fileHandleForReading.readToEnd()
                        }
                        Task.detached {
                            let dados = (try? stdoutPipe.fileHandleForReading.readToEnd()) ?? Data()
                            processo.waitUntilExit()
                            continuation.resume(returning: dados)
                        }
                    }
                } onCancel: {
                    if processo.isRunning {
                        processo.terminate()
                    }
                }

                // Se foi cancelado durante a espera
                if Task.isCancelled {
                    atualizarProgresso(id: url.path, status: "cancelado", erro: nil)
                    continue
                }

                if let string = String(data: stdoutData, encoding: .utf8) {
                    for linha in string.split(separator: "\n") {
                        if let jsonData = String(linha).data(using: .utf8),
                           let item = try? JSONDecoder().decode(ProgressoArquivo.self, from: jsonData) {
                            atualizarProgresso(id: item.id, status: item.status, erro: item.erro, duracao: item.duracao)
                        }
                    }
                }
            } catch {
                atualizarProgresso(id: url.path, status: "erro", erro: "Falha ao executar processo")
            }
        }

        processoAtivo = nil
        estaProcessando = false
        concluido = true  // conversão terminou (concluída ou cancelada) → habilita "Limpar"
        duracaoTotal = Date().timeIntervalSince(inicioTotal)

        // Notifica só em término natural; cancelamento manual não dispara alerta.
        if !Task.isCancelled {
            emitirNotificacao()
        }
    }

    /// Cancela conversão em curso — termina o processo ativo para interromper
    /// o `await` imediatamente. O estado de UI (estaProcessando/concluido) é
    /// liquidado pelo loop em iniciarConversao, mantendo um único dono do estado
    /// e evitando a corrida de teardown ao reconverter.
    func cancelar() {
        if processoAtivo?.isRunning == true {
            processoAtivo?.terminate()
        }
    }

    private func atualizarProgresso(id: String, status: String, erro: String?, duracao: Double? = nil) {
        if let index = progresso.firstIndex(where: { $0.id == id }) {
            progresso[index] = ProgressoArquivo(id: id, status: status, erro: erro, duracao: duracao)
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
        var corpo = partes.joined(separator: " · ")
        if let t = duracaoTotal {
            corpo += " em \(Self.formatarDuracao(t))"
        }
        content.body = corpo
        content.sound = .default

        let request = UNNotificationRequest(
            identifier: UUID().uuidString,
            content: content,
            trigger: nil
        )
        center.add(request)
    }

    /// Formata segundos legível: "1.2s" (<1min) ou "1m02s" (>=1min).
    /// Estático para reuso no ContentView (tempo por-arquivo e total).
    static func formatarDuracao(_ seg: Double) -> String {
        if seg < 60 {
            return String(format: "%.1fs", seg)
        }
        let minutos = Int(seg) / 60
        let segundos = Int(seg) % 60
        return String(format: "%dm%02ds", minutos, segundos)
    }

    func limpar() {
        progresso.removeAll()
        estaProcessando = false
        concluido = false
        duracaoTotal = nil
        processoAtivo = nil
    }
}
