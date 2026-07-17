import SwiftUI

@main
struct InstaxApp: App {
    @StateObject private var model = AppModel()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(model)
                .frame(minWidth: 980, minHeight: 640)
        }
        .windowStyle(.titleBar)
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("打开图片…") {
                    model.chooseImage()
                }
                .keyboardShortcut("o")
            }
            CommandGroup(after: .saveItem) {
                Button("导出…") {
                    model.chooseExportLocation()
                }
                .keyboardShortcut("e")
                .disabled(!model.canExport)
            }
            CommandMenu("查看") {
                Button(model.showOriginal ? "显示处理效果" : "显示原图") {
                    model.showOriginal.toggle()
                }
                .keyboardShortcut("\\", modifiers: [.command])
                .disabled(!model.hasImage)
            }
        }
    }
}
