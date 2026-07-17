#pragma once

#include <opencv2/core.hpp>

#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

namespace instax {

struct ModeSummary {
    std::string name;
    float default_strength;
    float default_grain;
    float default_flash;
    bool default_frame;
};

struct ProcessingOptions {
    std::string mode = "instax";
    float strength = 1.0f;
    float grain = 0.3f;
    float flash = 0.35f;
    bool vignette = true;
    bool frame = false;
    std::uint64_t seed = 0;
};

class ImageProcessor {
public:
    [[nodiscard]] std::vector<ModeSummary> modes() const;
    [[nodiscard]] ModeSummary mode(std::string_view name) const;

    // Both input and output use 8-bit RGB channel order. The output may have a
    // different size when an Instax frame is requested.
    [[nodiscard]] cv::Mat3b process(
        const cv::Mat3b& input,
        const ProcessingOptions& options
    ) const;
};

}  // namespace instax
