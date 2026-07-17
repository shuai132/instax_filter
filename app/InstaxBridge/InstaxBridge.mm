#import "InstaxBridge.h"

#include "instax/image_processor.hpp"

#include <opencv2/imgproc.hpp>

#include <algorithm>
#include <climits>
#include <cmath>
#include <cstdlib>
#include <exception>
#include <stdexcept>
#include <vector>

NSErrorDomain const IFProcessorErrorDomain = @"com.ccforge.instax.processor";

@interface IFModeInfo ()

- (instancetype)initWithSummary:(const instax::ModeSummary&)summary;

@end

@implementation IFModeInfo

- (instancetype)initWithSummary:(const instax::ModeSummary&)summary {
    self = [super init];
    if (self) {
        _name = [NSString stringWithUTF8String:summary.name.c_str()];
        _defaultStrength = summary.default_strength;
        _defaultGrain = summary.default_grain;
        _defaultFlash = summary.default_flash;
        _defaultFrame = summary.default_frame;
    }
    return self;
}

@end

@implementation IFProcessingRequest

- (instancetype)init {
    self = [super init];
    if (self) {
        _mode = @"instax";
        _strength = 1.0f;
        _grain = 0.3f;
        _flash = 0.35f;
        _vignette = YES;
        _frame = NO;
        _seed = 0;
    }
    return self;
}

@end

namespace {

struct DecodedImage {
    cv::Mat3b rgb;
    cv::Mat1b alpha;
};

DecodedImage decode_image(CGImageRef image) {
    const size_t width = CGImageGetWidth(image);
    const size_t height = CGImageGetHeight(image);
    if (width == 0 || height == 0 || width > static_cast<size_t>(INT_MAX) ||
        height > static_cast<size_t>(INT_MAX)) {
        throw std::invalid_argument("图片尺寸无效或过大");
    }

    const size_t bytes_per_row = width * 4;
    std::vector<std::uint8_t> pixels(bytes_per_row * height);
    CGColorSpaceRef color_space = CGColorSpaceCreateWithName(kCGColorSpaceSRGB);
    CGBitmapInfo info = static_cast<CGBitmapInfo>(
        kCGBitmapByteOrder32Big | static_cast<uint32_t>(kCGImageAlphaPremultipliedLast)
    );
    CGContextRef context = CGBitmapContextCreate(
        pixels.data(), width, height, 8, bytes_per_row, color_space, info
    );
    CGColorSpaceRelease(color_space);
    if (!context) throw std::runtime_error("无法创建图片解码缓冲区");

    CGContextSetBlendMode(context, kCGBlendModeCopy);
    CGContextDrawImage(context, CGRectMake(0, 0, width, height), image);
    CGContextRelease(context);

    cv::Mat4b rgba(
        static_cast<int>(height),
        static_cast<int>(width),
        reinterpret_cast<cv::Vec4b *>(pixels.data()),
        bytes_per_row
    );
    cv::Mat1b alpha(static_cast<int>(height), static_cast<int>(width));
    for (int y = 0; y < rgba.rows; ++y) {
        for (int x = 0; x < rgba.cols; ++x) {
            auto& pixel = rgba(y, x);
            const int a = pixel[3];
            alpha(y, x) = static_cast<std::uint8_t>(a);
            if (a > 0 && a < 255) {
                for (int channel = 0; channel < 3; ++channel) {
                    pixel[channel] = cv::saturate_cast<std::uint8_t>(static_cast<int>(
                        std::lround(pixel[channel] * 255.0 / a)
                    ));
                }
            }
        }
    }

    cv::Mat3b rgb;
    cv::cvtColor(rgba, rgb, cv::COLOR_RGBA2RGB);
    return {rgb, alpha.clone()};
}

CGImageRef encode_image(const cv::Mat3b& rgb, const cv::Mat1b& source_alpha) {
    if (rgb.empty()) throw std::invalid_argument("处理结果为空");

    cv::Mat4b rgba;
    cv::cvtColor(rgb, rgba, cv::COLOR_RGB2RGBA);
    const bool preserve_alpha = source_alpha.size() == rgb.size();
    for (int y = 0; y < rgba.rows; ++y) {
        for (int x = 0; x < rgba.cols; ++x) {
            auto& pixel = rgba(y, x);
            const int alpha = preserve_alpha ? source_alpha(y, x) : 255;
            pixel[3] = static_cast<std::uint8_t>(alpha);
            if (alpha < 255) {
                for (int channel = 0; channel < 3; ++channel) {
                    pixel[channel] = cv::saturate_cast<std::uint8_t>(static_cast<int>(
                        std::lround(pixel[channel] * alpha / 255.0)
                    ));
                }
            }
        }
    }

    const size_t byte_count = rgba.total() * rgba.elemSize();
    CFDataRef data = CFDataCreate(kCFAllocatorDefault, rgba.ptr(), byte_count);
    CGDataProviderRef provider = CGDataProviderCreateWithCFData(data);
    CGColorSpaceRef color_space = CGColorSpaceCreateWithName(kCGColorSpaceSRGB);
    CGBitmapInfo info = static_cast<CGBitmapInfo>(
        kCGBitmapByteOrder32Big | static_cast<uint32_t>(kCGImageAlphaPremultipliedLast)
    );
    CGImageRef image = CGImageCreate(
        static_cast<size_t>(rgba.cols),
        static_cast<size_t>(rgba.rows),
        8,
        32,
        static_cast<size_t>(rgba.step),
        color_space,
        info,
        provider,
        nullptr,
        false,
        kCGRenderingIntentDefault
    );
    CGColorSpaceRelease(color_space);
    CGDataProviderRelease(provider);
    CFRelease(data);
    if (!image) throw std::runtime_error("无法创建处理后的图片");
    return image;
}

void configure_cascades() {
    static dispatch_once_t once_token;
    dispatch_once(&once_token, ^{
        NSString *path = [[NSBundle mainBundle] pathForResource:@"haarcascade_frontalface_alt2"
                                                         ofType:@"xml"];
        if (path) setenv("OPENCV_HAAR_DIR", path.stringByDeletingLastPathComponent.UTF8String, 1);
    });
}

}  // namespace

@implementation IFProcessor

- (NSArray<IFModeInfo *> *)availableModes {
    try {
        NSMutableArray<IFModeInfo *> *result = [NSMutableArray array];
        for (const auto& summary : instax::ImageProcessor{}.modes()) {
            [result addObject:[[IFModeInfo alloc] initWithSummary:summary]];
        }
        return result;
    } catch (...) {
        return @[];
    }
}

- (CGImageRef)processImage:(CGImageRef)image
                   request:(IFProcessingRequest *)request
                     error:(NSError **)error {
    try {
        configure_cascades();
        auto decoded = decode_image(image);
        instax::ProcessingOptions options;
        options.mode = request.mode.UTF8String;
        options.strength = request.strength;
        options.grain = request.grain;
        options.flash = request.flash;
        options.vignette = request.vignette;
        options.frame = request.frame;
        options.seed = request.seed;
        auto output = instax::ImageProcessor{}.process(decoded.rgb, options);
        return encode_image(output, request.frame ? cv::Mat1b{} : decoded.alpha);
    } catch (const std::exception& exception) {
        if (error) {
            NSString *message = [NSString stringWithUTF8String:exception.what()];
            *error = [NSError errorWithDomain:IFProcessorErrorDomain
                                         code:1
                                     userInfo:@{NSLocalizedDescriptionKey: message}];
        }
        return nullptr;
    } catch (...) {
        if (error) {
            *error = [NSError errorWithDomain:IFProcessorErrorDomain
                                         code:2
                                     userInfo:@{NSLocalizedDescriptionKey: @"发生未知的图片处理错误"}];
        }
        return nullptr;
    }
}

@end
