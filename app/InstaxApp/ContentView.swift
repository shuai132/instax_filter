import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @EnvironmentObject private var model: AppModel

    var body: some View {
        HSplitView {
            presetSidebar
                .frame(minWidth: 190, idealWidth: 210, maxWidth: 240)
            canvas
                .frame(minWidth: 480)
            adjustmentPanel
                .frame(minWidth: 240, idealWidth: 270, maxWidth: 300)
        }
        .toolbar {
            ToolbarItemGroup {
                Button {
                    model.chooseImage()
                } label: {
                    Label("打开", systemImage: "photo.badge.plus")
                }
                Button {
                    model.showOriginal.toggle()
                } label: {
                    Label(
                        model.showOriginal ? "显示效果" : "显示原图",
                        systemImage: model.showOriginal ? "wand.and.stars" : "eye"
                    )
                }
                .disabled(!model.hasImage)
            }
            ToolbarItem(placement: .primaryAction) {
                Button {
                    model.chooseExportLocation()
                } label: {
                    if model.isExporting {
                        ProgressView().controlSize(.small)
                    } else {
                        Label("导出", systemImage: "square.and.arrow.up")
                    }
                }
                .disabled(!model.canExport)
            }
        }
        .alert(
            "操作失败",
            isPresented: Binding(
                get: { model.errorMessage != nil },
                set: { if !$0 { model.dismissError() } }
            )
        ) {
            Button("好", role: .cancel) { model.dismissError() }
        } message: {
            Text(model.errorMessage ?? "未知错误")
        }
    }

    private var presetSidebar: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("成像模式")
                .font(.headline)
                .padding(.horizontal, 14)
                .padding(.vertical, 12)
            Divider()
            ScrollView {
                LazyVStack(spacing: 5) {
                    ForEach(model.modes) { mode in
                        Button {
                            model.selectMode(mode.id)
                        } label: {
                            HStack(spacing: 10) {
                                RoundedRectangle(cornerRadius: 7)
                                    .fill(modeColor(mode.id).gradient)
                                    .frame(width: 34, height: 34)
                                    .overlay {
                                        Image(systemName: mode.id == "noir" ? "circle.lefthalf.filled" : "camera.filters")
                                            .foregroundStyle(.white.opacity(0.9))
                                    }
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(mode.title).fontWeight(.medium)
                                    Text(mode.subtitle)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                                Spacer()
                            }
                            .padding(.horizontal, 9)
                            .padding(.vertical, 7)
                            .background {
                                if model.selectedMode == mode.id {
                                    RoundedRectangle(cornerRadius: 8)
                                        .fill(Color.accentColor.opacity(0.16))
                                }
                            }
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(8)
            }
        }
        .background(.regularMaterial)
    }

    private var canvas: some View {
        ZStack {
            Color(nsColor: .windowBackgroundColor)
            if let image = model.visibleImage {
                GeometryReader { geometry in
                    Image(decorative: image, scale: 1)
                        .resizable()
                        .scaledToFit()
                        .frame(width: geometry.size.width, height: geometry.size.height)
                        .padding(24)
                }
                if model.isProcessing {
                    VStack(spacing: 8) {
                        ProgressView()
                        Text("正在生成预览…").font(.caption)
                    }
                    .padding(14)
                    .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
                }
                if model.showOriginal {
                    Text("原图")
                        .font(.caption.bold())
                        .padding(.horizontal, 10)
                        .padding(.vertical, 5)
                        .background(.ultraThickMaterial, in: Capsule())
                        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                        .padding(16)
                }
            } else {
                VStack(spacing: 14) {
                    Image(systemName: "photo.on.rectangle.angled")
                        .font(.system(size: 48, weight: .light))
                        .foregroundStyle(.secondary)
                    Text("打开一张照片")
                        .font(.title2.weight(.semibold))
                    Text("拖放 JPEG、PNG、HEIC 或 TIFF 到这里")
                        .foregroundStyle(.secondary)
                    Button("选择照片…") { model.chooseImage() }
                        .buttonStyle(.borderedProminent)
                }
            }
        }
        .onDrop(of: [UTType.fileURL.identifier], isTargeted: nil) { providers in
            guard let provider = providers.first else { return false }
            provider.loadDataRepresentation(forTypeIdentifier: UTType.fileURL.identifier) { data, _ in
                guard let data,
                      let text = String(data: data, encoding: .utf8),
                      let url = URL(string: text.trimmingCharacters(in: .whitespacesAndNewlines)) else { return }
                Task { @MainActor in model.open(url: url) }
            }
            return true
        }
    }

    private var adjustmentPanel: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text("调整")
                    .font(.headline)
                parameterSlider("成像强度", value: $model.strength, range: 0 ... 1.5)
                parameterSlider("颗粒", value: $model.grain, range: 0 ... 2)
                parameterSlider("闪光", value: $model.flash, range: 0 ... 2)
                Divider()
                Toggle("暗角", isOn: changedBinding($model.vignette))
                Toggle("Instax 相框", isOn: changedBinding($model.frame))
                Divider()
                VStack(alignment: .leading, spacing: 7) {
                    Text("随机纹理").font(.subheadline.weight(.medium))
                    Text(String(model.seed))
                        .font(.caption.monospacedDigit())
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                    Button {
                        model.randomizeSeed()
                    } label: {
                        Label("换一组纹理", systemImage: "dice")
                    }
                }
                Spacer(minLength: 20)
            }
            .padding(16)
        }
        .background(.regularMaterial)
        .disabled(!model.hasImage)
    }

    private func parameterSlider(
        _ title: String,
        value: Binding<Double>,
        range: ClosedRange<Double>
    ) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack {
                Text(title).font(.subheadline.weight(.medium))
                Spacer()
                Text(value.wrappedValue, format: .number.precision(.fractionLength(2)))
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
            }
            Slider(value: changedBinding(value), in: range)
        }
    }

    private func changedBinding<Value>(_ source: Binding<Value>) -> Binding<Value> {
        Binding(
            get: { source.wrappedValue },
            set: {
                source.wrappedValue = $0
                model.parametersDidChange()
            }
        )
    }

    private func modeColor(_ id: String) -> Color {
        switch id {
        case "ccd": return Color(red: 0.34, green: 0.54, blue: 0.68)
        case "lofi": return Color(red: 0.70, green: 0.38, blue: 0.55)
        case "disposable": return Color(red: 0.77, green: 0.54, blue: 0.25)
        case "chrome": return Color(red: 0.18, green: 0.55, blue: 0.50)
        case "dream": return Color(red: 0.66, green: 0.53, blue: 0.78)
        case "noir": return Color(white: 0.25)
        case "night": return Color(red: 0.19, green: 0.28, blue: 0.58)
        default: return Color(red: 0.42, green: 0.56, blue: 0.44)
        }
    }
}
