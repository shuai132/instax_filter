#include "instax/mode_config.hpp"

#include <stdexcept>

namespace instax {

ModeRegistry::ModeRegistry() : modes_{
    {"instax", {"instax",1,.3f,.35f,false,3600,.1f,.2f,.035f,.035f,.012f,
        {-.014f,.007f,.016f},{.002f,.005f,-.003f},{.025f,.012f,-.018f},
        {1.04f,-.02f,-.02f,-.012f,1.032f,-.02f,-.018f,.012f,1.006f},
        .09f,-.025f,.12f,.03f,.08f,.3f,.09f,{.008f,.003f,-.005f},{.004f,.0045f,.0035f},
        .62f,.006f,.012f,.0005f,.0008f,1,{.085f,.08f,.07f},.16f,.13f,{.05f,.035f,.015f}}},
    {"ccd", {"ccd",1,.65f,0,false,2300,.03f,.15f,.01f,0,0,
        {-.003f,0,.007f},{.003f,.001f,-.002f},{.006f,.002f,-.004f},
        {1.035f,-.018f,-.017f,-.01f,1.028f,-.018f,-.014f,-.002f,1.016f},
        .14f,0,.02f,-.09f,.015f,.04f,.025f,{0,0,0},{0,0,0},
        .92f,.003f,.016f,.0015f,.006f,1.12f,{.075f,.082f,.095f},.08f,.17f,{.025f,.03f,.038f}}},
    {"lofi", {"lofi",1.5f,2,0,false,3600,.18f,.18f,.055f,.045f,.024f,
        {-.03f,.018f,.038f},{.002f,.01f,-.005f},{.05f,.024f,-.038f},
        {1.06f,-.03f,-.03f,-.018f,1.048f,-.03f,-.028f,.02f,1.008f},
        .18f,-.055f,.52f,.16f,.17f,1,.155f,{.012f,.004f,-.008f},{.007f,.008f,.006f},
        .72f,.015f,.027f,.0032f,0,1.22f,{.105f,.1f,.09f},.2f,.16f,{.08f,.058f,.028f}}},
    {"disposable", {"disposable",1,.9f,.22f,false,3000,.12f,.24f,.02f,0,.006f,
        {-.008f,.018f,.003f},{.003f,.004f,-.004f},{.03f,.016f,-.02f},
        {1.05f,-.025f,-.025f,-.012f,1.035f,-.023f,-.02f,.006f,1.014f},
        .12f,-.02f,.08f,.02f,.05f,.22f,.14f,{.012f,.004f,-.01f},{.004f,.0045f,.0035f},
        .58f,.009f,.018f,.0008f,.0012f,1.18f,{.1f,.092f,.075f},.22f,.2f,{.075f,.048f,.02f}}},
    {"chrome", {"chrome",1,.22f,0,false,3600,.02f,.32f,-.005f,.01f,0,
        {-.018f,.006f,.022f},{.002f,.003f,-.004f},{.026f,.018f,-.018f},
        {1.075f,-.036f,-.039f,-.02f,1.06f,-.04f,-.03f,-.005f,1.035f},
        .28f,.04f,.03f,-.05f,.04f,.12f,.06f,{-.003f,0,.004f},{.002f,.002f,.0015f},
        .82f,.004f,.008f,.0003f,.0005f,1.05f,{.07f,.07f,.068f},.1f,.12f,{.04f,.032f,.02f}}},
    {"dream", {"dream",1,.18f,0,false,3600,0,-.12f,.04f,.06f,.03f,
        {.012f,.004f,.025f},{.01f,.004f,.008f},{.03f,.012f,.018f},
        {1.025f,-.01f,-.015f,-.008f,1.02f,-.012f,-.004f,-.006f,1.01f},
        .04f,-.1f,.26f,.08f,.18f,1.05f,.035f,{.006f,0,.008f},{.003f,.0025f,.0035f},
        .68f,.003f,.006f,.0004f,.0004f,.78f,{.075f,.065f,.078f},.24f,.07f,{.055f,.03f,.045f}}},
    {"noir", {"noir",1,1.1f,0,false,2800,-.03f,.38f,-.015f,0,0,
        {0,0,0},{0,0,0},{0,0,0},
        {.2126f,.7152f,.0722f,.2126f,.7152f,.0722f,.2126f,.7152f,.0722f},
        0,0,.04f,-.04f,.03f,.08f,.18f,{0,0,0},{.004f,.004f,.004f},
        .6f,.012f,.024f,0,0,1.15f,{.085f,.085f,.085f},0,.18f,{.045f,.045f,.045f}}},
    {"night", {"night",1,.85f,.3f,false,2300,.05f,.28f,.02f,0,0,
        {-.025f,.008f,.035f},{.014f,-.005f,.018f},{.03f,-.006f,.025f},
        {1.05f,-.024f,-.026f,-.018f,1.05f,-.032f,-.012f,-.02f,1.032f},
        .24f,.03f,.03f,-.08f,.12f,.5f,.15f,{-.008f,0,.012f},{0,0,0},
        .9f,.005f,.022f,.002f,.01f,1.25f,{.07f,.085f,.115f},.06f,.24f,{.025f,.04f,.065f}}},
} {}

const ModeRegistry& ModeRegistry::builtins() {
    static const ModeRegistry registry;
    return registry;
}

const ModeConfig& ModeRegistry::get(std::string_view name) const {
    const auto found = modes_.find(std::string(name));
    if (found == modes_.end()) throw std::invalid_argument("不支持的模式：" + std::string(name));
    return found->second;
}

bool ModeRegistry::contains(std::string_view name) const {
    return modes_.contains(std::string(name));
}

const std::map<std::string, ModeConfig>& ModeRegistry::all() const noexcept {
    return modes_;
}

}  // namespace instax
