#pragma once

#include <opencv2/core.hpp>

#include <map>
#include <string>
#include <string_view>

namespace instax {

struct ModeConfig {
    std::string name;
    float default_strength, default_grain, default_flash;
    bool default_frame;
    int processing_max_side;
    float exposure_ev, contrast_amount, gamma_lift, black_compression, black_lift;
    cv::Vec3f shadow_tint, midtone_tint, highlight_tint;
    cv::Matx33f color_matrix;
    float midtone_saturation, saturation_bias, soften_amount, local_detail_amount;
    float glow_amount, halo_amount, vignette_amount;
    cv::Vec3f vignette_tint, density_texture;
    float grain_fine_mix, grain_floor, grain_shadow, chroma_noise_floor, chroma_noise_shadow;
    float flash_gain;
    cv::Vec3f flash_bias;
    float flash_desaturation, flash_background_falloff;
    cv::Vec3f flash_hot_tint;
};

class ModeRegistry {
public:
    static const ModeRegistry& builtins();

    [[nodiscard]] const ModeConfig& get(std::string_view name) const;
    [[nodiscard]] bool contains(std::string_view name) const;
    [[nodiscard]] const std::map<std::string, ModeConfig>& all() const noexcept;

private:
    ModeRegistry();

    std::map<std::string, ModeConfig> modes_;
};

}  // namespace instax
