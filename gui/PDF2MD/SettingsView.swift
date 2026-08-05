// SettingsView.swift
// Janela de Preferências (scene `Settings`) — provedor, modelo e API key do LLM.
//
// A lista de modelos e o status vêm do binário (pdf2md llm modelos/testar
// --json), nunca reimplementados em Swift. Swift só faz parse do JSON —
// mesmo padrão do protocolo usado no BatchProcessor. A key é lida do
// Keychain (D7) e vai para o binário via environment (D8).
import AppKit
import SwiftUI

struct ModeloLLM: Identifiable, Codable {
    let id: String
    let visao: Bool?
}

private struct RespostaModelos: Codable {
    let ok: Bool
    let modelos: [ModeloLLM]
    let erro: String?
}

private struct RespostaTeste: Codable {
    let ok: Bool
    let latencia_ms: Int?
    let erro: String?
}

/// Executa o binário embarcado `pdf2md` com o environment do LLM.
/// A key viaja no environment — nunca em argv (CWE-522 / `ps aux`).
enum LLMProbe {
    static func executar(_ args: [String], url: String?, key: String?) async -> Data? {
        guard let binario = Bundle.main.url(forResource: "pdf2md", withExtension: nil) else {
            return nil  // modo dev sem binário embarcado → UI usa lista estática
        }
        let processo = Process()
        processo.executableURL = binario
        processo.arguments = args
        var env = ProcessInfo.processInfo.environment
        if let url { env["PDF2MD_LLM_URL"] = url }
        if let key { env["PDF2MD_LLM_KEY"] = key }
        processo.environment = env

        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()
        processo.standardOutput = stdoutPipe
        processo.standardError = stderrPipe

        do {
            try processo.run()
        } catch {
            return nil
        }

        // Drena stderr concorrentemente para evitar deadlock se o pipe
        // enche (mesmo padrão do BatchProcessor).
        return await withCheckedContinuation { continuation in
            Task.detached {
                _ = try? stderrPipe.fileHandleForReading.readToEnd()
                let dados = (try? stdoutPipe.fileHandleForReading.readToEnd()) ?? Data()
                processo.waitUntilExit()
                continuation.resume(returning: dados.isEmpty ? nil : dados)
            }
        }
    }
}

struct SettingsView: View {
    @AppStorage(LLMDefaultsKeys.provider) private var providerRaw = LLMProvider.ollama.rawValue
    @AppStorage(LLMDefaultsKeys.modelo) private var modelo = ""
    @AppStorage(LLMDefaultsKeys.urlPersonalizada) private var urlPersonalizada = ""

    @State private var modelos: [ModeloLLM] = []
    @State private var modelosEstaticos: Bool = true      // lista dinâmica falhou
    @State private var carregandoModelos: Bool = false
    @State private var status: String = "Verificando…"
    @State private var statusOk: Bool? = nil
    @State private var chave: String = KeychainHelper.ler() ?? ""

    private var provider: LLMProvider { LLMProvider(rawValue: providerRaw) ?? .ollama }
    private var urlResolvida: String? {
        LLMProvider.urlResolvida(providerRaw: providerRaw, urlPersonalizada: urlPersonalizada)
    }
    private var chaveTratada: String? {
        chave.trimmingCharacters(in: .whitespaces).isEmpty ? nil : chave
    }

    private var opcoesModelo: [String] {
        var ids = modelos.map(\.id)
        if modelosEstaticos { ids = provider.modelosPadrao }
        // Modelo digitado manualmente sempre permanece selecionável
        let modeloAtual = modelo.trimmingCharacters(in: .whitespaces)
        if !modeloAtual.isEmpty && !ids.contains(modeloAtual) {
            ids.append(modeloAtual)
        }
        return ids
    }

    private var avisoVisao: String? {
        if provider.visaoPadrao == false {
            return "\(provider.nome) não tem visão — OCR de imagem fica só no Tesseract"
        }
        if let m = modelos.first(where: { $0.id == modelo }), m.visao == false {
            return "\(modelo) não tem visão — OCR de imagem fica só no Tesseract"
        }
        return nil
    }

    var body: some View {
        Form {
            Section("Provedor") {
                Picker("Provedor", selection: $providerRaw) {
                    ForEach(LLMProvider.allCases) { p in
                        Text(p.nome).tag(p.rawValue)
                    }
                }
                .onChange(of: providerRaw) { _ in
                    // Trocar provider atualiza a URL e limpa o modelo selecionado
                    modelo = ""
                    recarregar()
                }

                if provider == .personalizado {
                    TextField("URL base da API (compatível com OpenAI)", text: $urlPersonalizada)
                        .onChange(of: urlPersonalizada) { _ in recarregar() }
                }

                if provider.requerKey {
                    SecureField("API key", text: $chave)
                        .onChange(of: chave) { _ in
                            // Persiste no Keychain (D7) — nunca em UserDefaults
                            if chave.trimmingCharacters(in: .whitespaces).isEmpty {
                                KeychainHelper.apagar()
                            } else {
                                KeychainHelper.salvar(chave)
                            }
                            verificarConexao()
                        }
                }
            }

            Section("Modelo") {
                if carregandoModelos {
                    HStack(spacing: 8) {
                        ProgressView().controlSize(.small)
                        Text("Carregando modelos…")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }

                Picker("Modelo", selection: $modelo) {
                    ForEach(opcoesModelo, id: \.self) { id in
                        Text(id).tag(id)
                    }
                }
                .disabled(opcoesModelo.isEmpty)

                TextField("Ou digite outro modelo…", text: $modelo)

                if modelosEstaticos && !carregandoModelos && urlResolvida != nil {
                    Text("Servidor não respondeu — lista estática. Confirme se o provedor está rodando.")
                        .font(.caption2)
                        .foregroundColor(.orange)
                }

                if let aviso = avisoVisao {
                    Text(aviso)
                        .font(.caption2)
                        .foregroundColor(.orange)
                }
            }

            Section("Conexão") {
                HStack(spacing: 8) {
                    Circle()
                        .fill(corStatus)
                        .frame(width: 8, height: 8)
                    Text(status)
                        .font(.callout)
                    Spacer()
                    Button("Testar") { verificarConexao() }
                        .controlSize(.small)
                        .disabled(!configurado)
                }
                if !configurado {
                    Text("Configure um provedor para habilitar o LLM.")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
            }
        }
        .formStyle(.grouped)
        .frame(width: 460)
        .padding(12)
        .task { recarregar() }
    }

    private var configurado: Bool {
        LLMProvider.configurado(
            providerRaw: providerRaw,
            urlPersonalizada: urlPersonalizada,
            chave: chaveTratada
        )
    }

    private var corStatus: Color {
        switch statusOk {
        case true: return .green
        case false: return .red
        case nil: return .gray
        }
    }

    /// Recarrega lista de modelos + status de conexão em paralelo.
    private func recarregar() {
        carregandoModelos = true
        carregarModelos()
        verificarConexao()
    }

    private func carregarModelos() {
        guard let url = urlResolvida, configurado else {
            modelos = []
            modelosEstaticos = true
            carregandoModelos = false
            return
        }
        Task {
            let dados = await LLMProbe.executar(["llm", "modelos", "--json"], url: url, key: chaveTratada)
            if let dados,
               let resposta = try? JSONDecoder().decode(RespostaModelos.self, from: dados),
               resposta.ok {
                await MainActor.run {
                    modelos = resposta.modelos
                    modelosEstaticos = false
                    carregandoModelos = false
                }
            } else {
                await MainActor.run {
                    modelos = []
                    modelosEstaticos = true
                    carregandoModelos = false
                }
            }
        }
    }

    private func verificarConexao() {
        guard let url = urlResolvida, configurado else {
            status = "Sem configuração"
            statusOk = nil
            return
        }
        status = "Verificando…"
        statusOk = nil
        Task {
            let dados = await LLMProbe.executar(["llm", "testar", "--json"], url: url, key: chaveTratada)
            if let dados,
               let resposta = try? JSONDecoder().decode(RespostaTeste.self, from: dados),
               resposta.ok,
               let latencia = resposta.latencia_ms {
                await MainActor.run {
                    status = "Conectado (\(latencia)ms)"
                    statusOk = true
                }
            } else {
                let detalhe = (try? JSONDecoder().decode(RespostaTeste.self, from: dados ?? Data()))?.erro
                await MainActor.run {
                    status = "Inacessível\(detalhe.map { " — \($0)" } ?? "")"
                    statusOk = false
                }
            }
        }
    }
}
