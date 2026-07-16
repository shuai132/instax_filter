#pragma once

#include <opencv2/core.hpp>

#include <cstdint>

namespace instax {

class FrameRenderer {
public:
    [[nodiscard]] cv::Mat3f fit(const cv::Mat3f& input) const;
    [[nodiscard]] cv::Mat3b add(const cv::Mat3b& input, std::uint64_t seed) const;
};

}  // namespace instax
