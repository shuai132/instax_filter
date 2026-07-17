import AppKit
import Foundation
import ImageIO
import UniformTypeIdentifiers

struct FilterMode: Identifiable, Hashable {
    let id: String
    let title: String
    let subtitle: String
    let defaultStrength: Double
    let defaultGrain: Double
    let defaultFlash: Double
    let defaultFrame: Bool
}

struct FilterParameters {
    var mode: String
    var strength: Double
    var grain: Double
    var flash: Double
    var vignette: Bool
    var frame: Bool
    var seed: UInt64

    func bridgeRequest() -> IFProcessingRequest {
        let request = IFProcessingRequest()
        request.mode = mode
        request.strength = Float(strength)
        request.grain = Float(grain)
        request.flash = Float(flash)
        request.vignette = vignette
        request.frame = frame
        request.seed = seed
        return request
    }
}

final class ProcessingService {
    private let processor = IFProcessor()
    private let queue = DispatchQueue(label: "com.ccforge.instax.processing", qos: .userInitiated)

    var modes: [IFModeInfo] { processor.availableModes }

    func process(
        image: CGImage,
        parameters: FilterParameters,
        completion: @escaping (Result<CGImage, Error>) -> Void
    ) {
        queue.async {
            autoreleasepool {
                do {
                    let output = try self.processor.processImage(
                        image,
                        request: parameters.bridgeRequest()
                    )
                    completion(.success(output))
                } catch {
                    completion(.failure(error))
                }
            }
        }
    }
}

@MainActor
final class AppModel: ObservableObject {
    @Published private(set) var modes: [FilterMode] = []
    @Published private(set) var sourceURL: URL?
    @Published private(set) var originalImage: CGImage?
    @Published private(set) var previewSourceImage: CGImage?
    @Published private(set) var processedImage: CGImage?
    @Published private(set) var isProcessing = false
    @Published private(set) var isExporting = false
    @Published var showOriginal = false
    @Published var selectedMode = "instax"
    @Published var strength = 1.0
    @Published var grain = 0.3
    @Published var flash = 0.35
    @Published var vignette = true
    @Published var frame = false
    @Published var seed: UInt64 = 0
    @Published var errorMessage: String?

    private let service = ProcessingService()
    private var generation = 0
    private var debounceWorkItem: DispatchWorkItem?

    var hasImage: Bool { originalImage != nil }
    var canExport: Bool { originalImage != nil && !isExporting }
    var visibleImage: CGImage? {
        showOriginal ? previewSourceImage : (processedImage ?? previewSourceImage)
    }

    init() {
        let presentation: [String: (String, String)] = [
            "instax": ("Instax", "自然暖调相纸"),
            "ccd": ("CCD", "千禧年卡片机"),
            "lofi": ("Lo-fi", "柔焦与粗颗粒"),
            "disposable": ("Disposable", "一次性胶片机"),
            "chrome": ("Chrome", "浓郁反转片"),
            "dream": ("Dream", "低反差梦境"),
            "noir": ("Noir", "高反差黑白"),
            "night": ("Night", "霓虹夜拍")
        ]
        let preferredOrder = ["instax", "ccd", "lofi", "disposable", "chrome", "dream", "noir", "night"]
        modes = service.modes.map { info in
            let copy = presentation[info.name] ?? (info.name.capitalized, "")
            return FilterMode(
                id: info.name,
                title: copy.0,
                subtitle: copy.1,
                defaultStrength: Double(info.defaultStrength),
                defaultGrain: Double(info.defaultGrain),
                defaultFlash: Double(info.defaultFlash),
                defaultFrame: info.defaultFrame
            )
        }
        .sorted {
            (preferredOrder.firstIndex(of: $0.id) ?? .max) <
                (preferredOrder.firstIndex(of: $1.id) ?? .max)
        }
        applyDefaults(for: "instax", refresh: false)
    }

    func chooseImage() {
        let panel = NSOpenPanel()
        panel.title = "选择一张照片"
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.allowedContentTypes = [.image]
        if panel.runModal() == .OK, let url = panel.url {
            open(url: url)
        }
    }

    func open(url: URL) {
        do {
            let images = try Self.loadImages(at: url)
            sourceURL = url
            originalImage = images.original
            previewSourceImage = images.preview
            processedImage = nil
            showOriginal = false
            seed = Self.stableSeed(for: url)
            schedulePreview(immediate: true)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func selectMode(_ id: String) {
        selectedMode = id
        applyDefaults(for: id, refresh: true)
    }

    func parametersDidChange() {
        schedulePreview(immediate: false)
    }

    func randomizeSeed() {
        seed = UInt64.random(in: UInt64.min ... UInt64.max)
        schedulePreview(immediate: true)
    }

    func chooseExportLocation() {
        guard let sourceURL else { return }
        let panel = NSSavePanel()
        panel.title = "导出处理后的照片"
        panel.allowedContentTypes = [.jpeg, .png, .heic, .tiff]
        panel.canCreateDirectories = true
        panel.nameFieldStringValue = "\(sourceURL.deletingPathExtension().lastPathComponent)_\(selectedMode).jpg"
        if panel.runModal() == .OK, let url = panel.url {
            export(to: url)
        }
    }

    func dismissError() {
        errorMessage = nil
    }

    private func applyDefaults(for id: String, refresh: Bool) {
        guard let mode = modes.first(where: { $0.id == id }) else { return }
        strength = mode.defaultStrength
        grain = mode.defaultGrain
        flash = mode.defaultFlash
        frame = mode.defaultFrame
        vignette = true
        if refresh { schedulePreview(immediate: true) }
    }

    private var parameters: FilterParameters {
        FilterParameters(
            mode: selectedMode,
            strength: strength,
            grain: grain,
            flash: flash,
            vignette: vignette,
            frame: frame,
            seed: seed
        )
    }

    private func schedulePreview(immediate: Bool) {
        guard let previewSourceImage else { return }
        generation += 1
        let requestGeneration = generation
        debounceWorkItem?.cancel()
        let parameters = parameters
        let work = DispatchWorkItem { [weak self] in
            guard let self else { return }
            Task { @MainActor in self.isProcessing = true }
            self.service.process(image: previewSourceImage, parameters: parameters) { result in
                Task { @MainActor [weak self] in
                    guard let self, requestGeneration == self.generation else { return }
                    self.isProcessing = false
                    switch result {
                    case .success(let image): self.processedImage = image
                    case .failure(let error): self.errorMessage = error.localizedDescription
                    }
                }
            }
        }
        debounceWorkItem = work
        DispatchQueue.main.asyncAfter(deadline: .now() + (immediate ? 0 : 0.12), execute: work)
    }

    private func export(to url: URL) {
        guard let originalImage else { return }
        isExporting = true
        let parameters = parameters
        service.process(image: originalImage, parameters: parameters) { result in
            do {
                let image = try result.get()
                try Self.write(image: image, to: url)
                Task { @MainActor [weak self] in
                    self?.isExporting = false
                    NSWorkspace.shared.activateFileViewerSelecting([url])
                }
            } catch {
                Task { @MainActor [weak self] in
                    self?.isExporting = false
                    self?.errorMessage = error.localizedDescription
                }
            }
        }
    }

    private static func loadImages(at url: URL) throws -> (original: CGImage, preview: CGImage) {
        guard let source = CGImageSourceCreateWithURL(url as CFURL, nil) else {
            throw CocoaError(.fileReadCorruptFile, userInfo: [NSLocalizedDescriptionKey: "无法读取这张图片"])
        }
        let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any]
        let width = properties?[kCGImagePropertyPixelWidth] as? Int ?? 0
        let height = properties?[kCGImagePropertyPixelHeight] as? Int ?? 0
        let longestSide = max(width, height)
        guard longestSide > 0 else {
            throw CocoaError(.fileReadCorruptFile, userInfo: [NSLocalizedDescriptionKey: "图片尺寸无效"])
        }

        func thumbnail(maxPixelSize: Int) -> CGImage? {
            let options: [CFString: Any] = [
                kCGImageSourceCreateThumbnailFromImageAlways: true,
                kCGImageSourceCreateThumbnailWithTransform: true,
                kCGImageSourceThumbnailMaxPixelSize: maxPixelSize,
                kCGImageSourceShouldCacheImmediately: true
            ]
            return CGImageSourceCreateThumbnailAtIndex(source, 0, options as CFDictionary)
        }

        guard let original = thumbnail(maxPixelSize: longestSide),
              let preview = thumbnail(maxPixelSize: min(longestSide, 1600)) else {
            throw CocoaError(.fileReadCorruptFile, userInfo: [NSLocalizedDescriptionKey: "无法解码这张图片"])
        }
        return (original, preview)
    }

    private static func write(image: CGImage, to url: URL) throws {
        let type: UTType
        switch url.pathExtension.lowercased() {
        case "png": type = .png
        case "heic", "heif": type = .heic
        case "tif", "tiff": type = .tiff
        default: type = .jpeg
        }
        guard let destination = CGImageDestinationCreateWithURL(
            url as CFURL,
            type.identifier as CFString,
            1,
            nil
        ) else {
            throw CocoaError(.fileWriteUnknown, userInfo: [NSLocalizedDescriptionKey: "无法创建导出文件"])
        }
        let options: [CFString: Any] = [
            kCGImageDestinationLossyCompressionQuality: 0.95,
            kCGImagePropertyOrientation: 1
        ]
        CGImageDestinationAddImage(destination, image, options as CFDictionary)
        guard CGImageDestinationFinalize(destination) else {
            throw CocoaError(.fileWriteUnknown, userInfo: [NSLocalizedDescriptionKey: "图片导出失败"])
        }
    }

    private static func stableSeed(for url: URL) -> UInt64 {
        var value: UInt64 = 1_469_598_103_934_665_603
        for byte in url.standardizedFileURL.path.utf8 {
            value ^= UInt64(byte)
            value &*= 1_099_511_628_211
        }
        return value
    }
}
