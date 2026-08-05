// KeychainHelper.swift
// Armazenamento da API key do LLM no Keychain (D7).
//
// UserDefaults seria um plist em claro dentro do container do app — a key
// precisa de kSecClassGenericPassword. A key é LIDA daqui no início da
// conversão e injetada no environment do processo Python (D8), nunca em
// argv (apareceria em `ps aux` para qualquer processo do mesmo usuário).
import Foundation
import Security

enum KeychainHelper {
    // Serviço fixo — independente do bundle id: ad-hoc signing invalida
    // itens keyed por código assinado a cada rebuild (ver ADR-0007).
    static let servico = "com.pdf2md.llm"
    static let conta = "api-key"

    @discardableResult
    static func salvar(_ valor: String) -> Bool {
        guard let dados = valor.data(using: .utf8) else { return false }

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: servico,
            kSecAttrAccount as String: conta,
        ]
        // Substitui item existente (delete + add é mais confiável que update
        // quando o item anterior foi criado com outra política de acesso).
        SecItemDelete(query as CFDictionary)

        let attrs: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: servico,
            kSecAttrAccount as String: conta,
            kSecValueData as String: dados,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock,
        ]
        return SecItemAdd(attrs as CFDictionary, nil) == errSecSuccess
    }

    static func ler() -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: servico,
            kSecAttrAccount as String: conta,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let dados = item as? Data else {
            return nil
        }
        return String(data: dados, encoding: .utf8)
    }

    static func apagar() {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: servico,
            kSecAttrAccount as String: conta,
        ]
        SecItemDelete(query as CFDictionary)
    }
}
