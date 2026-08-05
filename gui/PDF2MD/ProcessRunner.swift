// ProcessRunner.swift
// Execução de Process() com drenagem concorrente de stdout/stderr.
//
// Padrão único para os dois pontos que spawnam o binário pdf2md
// (BatchProcessor — conversão; LLMProbe/SettingsView — diagnóstico).
// Ler os pipes EM SEQUÊNCIA causa deadlock: o filho só fecha stderr ao
// sair, e só sai após escrever todo o stdout — se o stdout exceder o
// buffer do pipe (~64KB), o filho bloqueia em write() para sempre.
import Foundation

enum ProcessRunner {
    /// Executa o binário com env, drenando stdout e stderr concorrentemente.
    ///
    /// - Parameters:
    ///   - binario: URL do executável.
    ///   - args: Argumentos (a key do LLM NUNCA entra aqui — só via `env`).
    ///   - env: Environment a injetar (merges com o do processo pai).
    ///   - onProcesso: chamado após `run()` — usado para registrar o
    ///     processo ativo (cancelamento). Executa antes da primeira
    ///     suspensão, no contexto do chamador.
    /// - Returns: stdout (nil se o processo não iniciou).
    static func executar(
        binario: URL,
        args: [String],
        env: [String: String]? = nil,
        onProcesso: ((Process) -> Void)? = nil
    ) async -> Data? {
        let processo = Process()
        processo.executableURL = binario
        processo.arguments = args
        if let env {
            var ambiente = ProcessInfo.processInfo.environment
            for (chave, valor) in env {
                ambiente[chave] = valor
            }
            processo.environment = ambiente
        }

        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()
        processo.standardOutput = stdoutPipe
        processo.standardError = stderrPipe

        do {
            try processo.run()
        } catch {
            return nil
        }
        onProcesso?(processo)

        return await withCheckedContinuation { continuation in
            Task.detached {
                // Leitura concorrente dos dois pipes — sem isto, deadlock
                // quando o stdout enche o pipe (~64KB) antes do término.
                async let stderr: Data? = try? stderrPipe.fileHandleForReading.readToEnd()
                let dados = (try? stdoutPipe.fileHandleForReading.readToEnd()) ?? Data()
                _ = await stderr
                processo.waitUntilExit()
                continuation.resume(returning: dados.isEmpty ? nil : dados)
            }
        }
    }
}
