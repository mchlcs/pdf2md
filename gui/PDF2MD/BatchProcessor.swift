// BatchProcessor.swift
// Bridge entre SwiftUI e binário Python pdf2md.
// Executa Process(), captura stdout JSON, publica progresso via @Published.
import Foundation
import Combine
import UserNotifications

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
    @Published var inicioConversao: Date?        // início da conversão em curso (feedback de tempo)
    @Published var erroFatal: String?            // falha de execução inteira (FIX 2): alerta no ContentView

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
        erroFatal = nil  // limpa alerta anterior (FIX 2)

        guard let binario = caminhoBinario else {
            // FIX 2: antes, binário ausente era só print no console e a UI
            // ficava sem feedback — agora vira alerta visível.
            erroFatal = "Binário pdf2md não encontrado no bundle"
            return
        }

        // Evita reentrância: ignora novo início enquanto uma conversão corre.
        // Sem isto, cancelar+reconverter cria duas execuções que se atropelam
        // no MainActor (zerando estaProcessando da nova).
        guard !estaProcessando else { return }

        // Confinamento ao home para DESTINO/VAULT (FIX 3): antes só a origem
        // era validada aqui — destino/vault fora do home eram rejeitados pelo
        // CLI com erro genérico sem explicação. Falha rápida com alerta claro.
        let home = FileManager.default.homeDirectoryForCurrentUser
        if let v = vault {
            let vSeguro = v.resolvingSymlinksInPath()
            guard Self.dentroDoHome(vSeguro.path, home: home) else {
                erroFatal = "Vault fora do diretório home"
                return
            }
        } else if let dest = destino {
            let destSeguro = dest.resolvingSymlinksInPath()
            guard Self.dentroDoHome(destSeguro.path, home: home) else {
                erroFatal = "Pasta de saída fora do diretório home"
                return
            }
        }

        estaProcessando = true
        concluido = false
        duracaoTotal = nil
        inicioConversao = Date()
        progresso.removeAll()  // cada execução exibe apenas seus próprios arquivos
        let inicioTotal = Date()

        // Sanitização: filtrar URLs fora do diretório home ANTES de processar
        let arquivosValidos: [URL] = arquivos.compactMap { url in
            let seguro = url.resolvingSymlinksInPath()
            // Confinamento com fronteira de componente (ver dentroDoHome):
            // home.path sem "/" final deixaria /Users/bob prefixar /Users/bobby.
            guard Self.dentroDoHome(seguro.path, home: home) else {
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

            // Cancelamento é responsabilidade do ProcessRunner: SIGTERM +
            // fechar pipes + SIGKILL em graça. A task cancelada retorna
            // AQUI imediatamente, sem depender do processo morrer.
            let resultado = await ProcessRunner.executar(
                binario: binario,
                args: args,
                env: envLLM.isEmpty ? nil : envLLM
            )

            // Se foi cancelado durante a espera
            if Task.isCancelled {
                atualizarProgresso(id: url.path, status: "cancelado", erro: nil)
                continue
            }

            // Exit != 0: o CLI rejeitou a conversão (validação de path,
            // Tesseract ausente, vault inválido…). A mensagem real vai no
            // stderr (rich Console(stderr=True)); antes, drenada e
            // descartada, tudo virava o erro genérico abaixo (FIX 1).
            if resultado.exitCode != 0 {
                atualizarProgresso(
                    id: url.path,
                    status: "erro",
                    erro: Self.mensagemErro(resultado.stderr)
                )
                continue
            }

            // Exit 0 sem stdout: contrato quebrado — conversão sempre emite JSON.
            guard let stdoutData = resultado.stdout else {
                atualizarProgresso(id: url.path, status: "erro", erro: "Falha ao executar processo")
                continue
            }

            if let string = String(data: stdoutData, encoding: .utf8) {
                for linha in string.split(separator: "\n") {
                    if let jsonData = String(linha).data(using: .utf8),
                       var item = try? JSONDecoder().decode(ProgressoArquivo.self, from: jsonData) {
                        // FIX 6: o JSON do CLI não distingue "destino já existe"
                        // de extensão não suportada — infere pelo filesystem.
                        if item.status == "ignorado" && item.avisos.isEmpty {
                            item = anexarMotivoIgnorado(item, base: vault ?? destino)
                        }
                        // Avisos de qualidade acompanham o resultado (ADR-0005):
                        // o âmbar no statusIcon depende deles chegarem até aqui.
                        atualizarProgresso(id: item.id, status: item.status, erro: item.erro, avisos: item.avisos)
                    }
                }
            }
        }

        estaProcessando = false
        concluido = true  // conversão terminou (concluída ou cancelada) → habilita "Limpar"
        duracaoTotal = Date().timeIntervalSince(inicioTotal)
        inicioConversao = nil

        // Notifica só em término natural; cancelamento manual não dispara alerta.
        if !Task.isCancelled {
            emitirNotificacao()
        }
    }

    private func atualizarProgresso(id: String, status: String, erro: String?, avisos: [String] = []) {
        if let index = progresso.firstIndex(where: { $0.id == id }) {
            progresso[index] = ProgressoArquivo(id: id, status: status, erro: erro, avisos: avisos)
        }
    }

    /// Confinamento ao diretório home com fronteira de componente (FIX 3):
    /// home.path sem "/" final deixaria /Users/bob prefixar /Users/bobby.
    private static func dentroDoHome(_ path: String, home: URL) -> Bool {
        path == home.path || path.hasPrefix(home.path + "/")
    }

    /// Mensagem legível do stderr do CLI, truncada para o alerta/linha da
    /// lista. Fallback para o erro genérico quando não há stderr (FIX 1).
    static func mensagemErro(_ stderr: Data?) -> String {
        guard let stderr,
              let texto = String(data: stderr, encoding: .utf8)?
                  .trimmingCharacters(in: .whitespacesAndNewlines),
              !texto.isEmpty else {
            return "Falha ao executar processo"
        }
        return String(texto.prefix(300))
    }

    /// FIX 6: reconversão de arquivo existente chega como "ignorado" sem
    /// motivo (a GUI nunca passa --sobrescrever). A GUI chama o binário por
    /// arquivo, então o destino esperado é sempre `<base>/<stem>.md` — sem o
    /// dedup de nomes do batch. Se o .md já existe, anexa aviso explicativo.
    private func anexarMotivoIgnorado(_ item: ProgressoArquivo, base: URL?) -> ProgressoArquivo {
        guard let base else { return item }
        let origem = URL(fileURLWithPath: item.id)
        let nomeMD = origem.deletingPathExtension().lastPathComponent + ".md"
        if FileManager.default.fileExists(atPath: base.appendingPathComponent(nomeMD).path) {
            return ProgressoArquivo(id: item.id, status: item.status, erro: nil, avisos: ["destino já existe"])
        }
        return item
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
        inicioConversao = nil
        erroFatal = nil
    }
}
