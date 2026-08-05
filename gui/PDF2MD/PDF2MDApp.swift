// PDF2MDApp.swift
// Entrypoint do app — define cena principal com ContentView.
import SwiftUI

@main
struct PDF2MDApp: App {
    var body: some Scene {
        WindowGroup("pdf2md") {
            ContentView()
        }
        // Config do LLM fica em Preferências (Parte 5 do plano: o rodapé
        // é ancorado e o provider/modelo não é decisão por conversão).
        Settings {
            SettingsView()
        }
    }
}
