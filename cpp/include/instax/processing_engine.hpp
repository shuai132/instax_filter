#pragma once

#include "instax/mode_config.hpp"

#include <opencv2/core.hpp>

#include <cstdint>
#include <vector>

namespace instax {

struct FilterSettings {
    float strength;
    float grain;
    float flash;
    bool vignette;
    std::uint64_t seed;
    bool collect_debug_faces = false;
};

struct FilterResult {
    cv::Mat3f image;
    std::vector<cv::Rect> faces;
};

class FilterEngine {
public:
    [[nodiscard]] FilterResult apply(
        const cv::Mat3f& input,
        const ModeConfig& mode,
        const FilterSettings& settings
    ) const;
};

}  // namespace instax
