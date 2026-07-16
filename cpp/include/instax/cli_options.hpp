#pragma once

#include <cstdint>
#include <filesystem>
#include <optional>
#include <string>
#include <vector>

namespace instax {

struct Options {
    std::filesystem::path input;
    std::optional<std::filesystem::path> output;
    std::vector<std::string> modes{"instax"};
    std::optional<float> strength, grain, flash;
    std::optional<bool> frame;
    bool mode_all = false, vignette = true, debug = false;
    std::optional<std::uint64_t> seed;
    int quality = 95;
};

[[nodiscard]] Options parse_options(int argc, char** argv);

}  // namespace instax
