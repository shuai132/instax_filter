import CoreGraphics
import XCTest

final class ProcessingIntegrationTests: XCTestCase {
    func testListsAllModesAndProcessesPixels() throws {
        let processor = IFProcessor()
        XCTAssertEqual(processor.availableModes.count, 8)

        let input = try makeImage(width: 48, height: 64)
        let request = IFProcessingRequest()
        request.mode = "instax"
        request.strength = 1
        request.grain = 0
        request.flash = 0
        request.vignette = false
        request.frame = false
        request.seed = 42

        let output = try processor.processImage(input, request: request)
        XCTAssertEqual(output.width, 48)
        XCTAssertEqual(output.height, 64)
    }

    func testRendersPortraitFrame() throws {
        let processor = IFProcessor()
        let input = try makeImage(width: 48, height: 64)
        let request = IFProcessingRequest()
        request.mode = "instax"
        request.grain = 0
        request.flash = 0
        request.frame = true
        request.seed = 42

        let output = try processor.processImage(input, request: request)
        XCTAssertEqual(output.width, 1080)
        XCTAssertEqual(output.height, 1720)
    }

    func testRejectsInvalidParameters() throws {
        let processor = IFProcessor()
        let input = try makeImage(width: 16, height: 16)
        let request = IFProcessingRequest()
        request.strength = 3

        XCTAssertThrowsError(try processor.processImage(input, request: request))
    }

    private func makeImage(width: Int, height: Int) throws -> CGImage {
        let colorSpace = CGColorSpace(name: CGColorSpace.sRGB)!
        guard let context = CGContext(
            data: nil,
            width: width,
            height: height,
            bitsPerComponent: 8,
            bytesPerRow: width * 4,
            space: colorSpace,
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
        ) else {
            throw XCTSkip("无法创建测试图片")
        }
        context.setFillColor(CGColor(red: 0.32, green: 0.55, blue: 0.74, alpha: 1))
        context.fill(CGRect(x: 0, y: 0, width: width, height: height))
        guard let image = context.makeImage() else {
            throw XCTSkip("无法生成测试图片")
        }
        return image
    }
}
