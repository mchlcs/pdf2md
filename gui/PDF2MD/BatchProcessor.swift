// BatchProcessor.swift
// Bridge entre SwiftUI e binário Python pdf2md.
// Executa Process(), captura stdout JSON, publica progresso via @Published.
import Foundation
import Combine
import UserNotifications

/// Container do processo ativo atravessando closures @Sendable (cancelamento).
final class ProcessoBox: @unchecked Sendable {
    var processo: Process?
}

struct ProgressoArquivo: Identifiable, Codable {
    let id: String       // path do arquivo origem
    let status: String   // "aguardando" | "processando" | "concluido" | "erro" | "cancelado" | "ignorado"
    let erro: String?
    let avisos: [String] // avisos de qualidade; [] = output limpo

    // Decoder customizado: aceita JSON sem "avisos" (versões anteriores do binário)
    private enum CodingKeys: String, CodingKey {
        case id, status, erro, avisos
    }

    init(id: String, status: String, erro: String?, avisos: [String] = []) {
        self.id = id
        self.status = status
        self.erro = erro
        self.avisos = avisos
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        status = try c.decode(String.self, forKey: .status)
        erro = try c.decodeIfPresent(String.self, forKey: .erro)
        avisos = (try? c.decode([String].self, forKey: .avisos)) ?? []
    }
}

@MainActor
class BatchProcessor: ObservableObject {
    @Published var progresso: [ProgressoArquivo] = []
    @Published var estaProcessando: Bool = false
    @Published var concluido: Bool = false
    @Published var duracaoTotal: TimeInterval?   // duração total da última conversão

    // Processo ativo — referência para cancelamento imediato (M2b: o box
    // vive na classe para o cancelar() terminar o processo de verdade).
    private var processoBox: ProcessoBox?

    // Localiza binário Python embarcado no bundle
    private var caminhoBinario: URL? {
        Bundle.main.url(forResource: "pdf2md", withExtension: nil)
    }

    func iniciarConversao(
        arquivos: [URL],
        destino: URL?,
        vault: URL?,
        obsidian: Bool,
        llmFallback: Bool = false,
        llmURL: String? = nil,
        llmModelo: String? = nil,
        llmKey: String? = nil
    ) async {
        guard let binario = caminhoBinario else {
            print("Binário pdf2md não encontrado no bundle")
            return
        }

        // Evita reentrância: ignora novo início enquanto uma conversão corre.
        // Sem isto, cancelar+reconverter cria duas execuções que se atropelam
        // no MainActor (zerando estaProcessando/processoBox da nova).
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

            if llmFallback {
                args.append("--llm-fallback")
            }

            // --json ao final (posição correta para Typer)
            args.append("--json")

            // Config do LLM entra no environment do processo (D8) — NUNCA em
            // argv, que aparece em `ps aux` para qualquer processo do mesmo
            // usuário (CWE-522). O binário aplica precedência env > default.
            var envLLM: [String: String] = [:]
            if llmFallback {
                if let url = llmURL { envLLM["PDF2MD_LLM_URL"] = url }
                if let modelo = llmModelo { envLLM["PDF2MD_LLM_MODEL"] = modelo }
                if let key = llmKey { envLLM["PDF2MD_LLM_KEY"] = key }
            }

            // Guarda referência para cancelamento imediato. O callback roda
            // antes da primeira suspensão (contexto do chamador); o box
            // atravessa a fronteira Sendable sem isolamento de actor.
            let box = ProcessoBox()
            processoBox = box
            let stdoutData: Data? = await withTaskCancellationHandler {
                await ProcessRunner.executar(
                    binario: binario,
                    args: args,
                    env: envLLM.isEmpty ? nil : envLLM,
                    onProcesso: { box.processo = $0 }
                )
            } onCancel: {
                if let ativo = box.processo, ativo.isRunning {
                    ativo.terminate()
                }
            }

            // Se foi cancelado durante a espera
            if Task.isCancelled {
                atualizarProgresso(id: url.path, status: "cancelado", erro: nil)
                continue
            }

            // ProcessRunner devolve nil quando o binário não iniciou
            // (ex.: não encontrado no bundle) — conversão sempre emite JSON.
            guard let stdoutData = stdoutData else {
                atualizarProgresso(id: url.path, status: "erro", erro: "Falha ao executar processo")
                continue
            }

            if let string = String(data: stdoutData, encoding: .utf8) {
                for linha in string.split(separator: "\n") {
                    if let jsonData = String(linha).data(using: .utf8),
                       let item = try? JSONDecoder().decode(ProgressoArquivo.self, from: jsonData) {
                        atualizarProgresso(id: item.id, status: item.status, erro: item.erro)
                    }
                }
            }
        }

        processoBox = nil
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
        if let ativo = processoBox?.processo, ativo.isRunning {
            ativo.terminate()
        }
    }

    private func atualizarProgresso(id: String, status: String, erro: String?, avisos: [String] = []) {
        if let index = progresso.firstIndex(where: { $0.id == id }) {
            progresso[index] = ProgressoArquivo(id: id, status: status, erro: erro, avisos: avisos)
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
    /// Estático para reuso no ContentView (tempo total da conversão).
    static func formatarDuracao(_ seg: Double) -> String {
        if seg < 1 {
            return String(format: "%.0fms", seg * 1000)  // ms: conversão leva ms, não "0.0s"
        }
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
        processoBox = nil
    }
}
