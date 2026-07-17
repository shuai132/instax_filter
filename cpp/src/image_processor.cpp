#include "instax/image_processor.hpp"

#include "instax/frame_renderer.hpp"
#include "instax/mode_config.hpp"
#include "instax/processing_engine.hpp"

#include <opencv2/imgproc.hpp>

#include <stdexcept>

namespace instax {
namespace {

ModeSummary summarize(const ModeConfig& mode) {
    return {
        mode.name,
        mode.default_strength,
        mode.default_grain,
        mode.default_flash,
        mode.default_frame,
    };
}

}  // namespace

std::vector<ModeSummary> ImageProcessor::modes() const {
    std::vector<ModeSummary> result;
    result.reserve(ModeRegistry::builtins().all().size());
    for (const auto& [name, config] : ModeRegistry::builtins().all()) {
        (void)name;
        result.push_back(summarize(config));
    }
    return result;
}

ModeSummary ImageProcessor::mode(std::string_view name) const {
    return summarize(ModeRegistry::builtins().get(name));
}

cv::Mat3b ImageProcessor::process(
    const cv::Mat3b& input,
    const ProcessingOptions& options
) const {
    if (input.empty()) throw std::invalid_argument("输入图片不能为空");
    if (options.strength < 0.0f || options.strength > 1.5f) {
        throw std::invalid_argument("滤镜强度必须在 0 到 1.5 之间");
    }
    if (options.grain < 0.0f || options.grain > 2.0f) {
        throw std::invalid_argument("颗粒强度必须在 0 到 2 之间");
    }
    if (options.flash < 0.0f || options.flash > 2.0f) {
        throw std::invalid_argument("闪光强度必须在 0 到 2 之间");
    }

    const auto& mode = ModeRegistry::builtins().get(options.mode);
    cv::Mat3f source;
    input.convertTo(source, CV_32FC3, 1.0 / 255.0);
    if (options.frame) source = FrameRenderer{}.fit(source);

    const FilterSettings settings{
        options.strength,
        options.grain,
        options.flash,
        options.vignette,
        options.seed,
        false,
    };
    auto result = FilterEngine{}.apply(source, mode, settings);
    cv::Mat3b output;
    result.image.convertTo(output, CV_8UC3, 255.0);
    if (options.frame) output = FrameRenderer{}.add(output, options.seed);
    return output;
}

}  // namespace instax
