#include "instax/processing_engine.hpp"

#include <opencv2/imgproc.hpp>
#include <opencv2/objdetect.hpp>

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <random>
#include <string>
#include <vector>

namespace instax {
namespace {

namespace fs = std::filesystem;

static float clamp01(float x) { return std::clamp(x, 0.0f, 1.0f); }
static float smoothstep(float a, float b, float x) {
    x = clamp01((x - a) / (b - a));
    return x * x * (3.0f - 2.0f * x);
}
static float luminance(const cv::Vec3f& p) { return p.dot({.2126f, .7152f, .0722f}); }
static cv::Vec3f clamp_pixel(cv::Vec3f p) {
    for (float& value : p.val) value = clamp01(value);
    return p;
}

template<class Function>
static void for_each_pixel(cv::Mat3f& image, Function function) {
    cv::parallel_for_(cv::Range(0, image.rows), [&](const cv::Range& range) {
        for (int y = range.start; y < range.end; ++y) {
            auto* row = image.ptr<cv::Vec3f>(y);
            for (int x = 0; x < image.cols; ++x) row[x] = function(row[x], x, y);
        }
    });
}

static cv::Mat3f gaussian_blur(const cv::Mat3f& source, float radius) {
    cv::Mat3f result;
    const double sigma = std::max(.01f, radius);
    cv::GaussianBlur(source, result, {}, sigma, sigma, cv::BORDER_REFLECT_101);
    return result;
}

static std::string cascade_dir() {
    if (const char* env = std::getenv("OPENCV_HAAR_DIR")) return env;
#ifdef INSTAX_CASCADE_DIR
    return INSTAX_CASCADE_DIR;
#else
    return {};
#endif
}

static std::vector<cv::Rect> detect_faces(const cv::Mat3f& rgb) {
    cv::Mat3b bytes;
    rgb.convertTo(bytes, CV_8UC3, 255.0);
    cv::Mat1b gray;
    cv::cvtColor(bytes, gray, cv::COLOR_RGB2GRAY);
    cv::equalizeHist(gray, gray);
    const int minimum = std::max(28, static_cast<int>(std::lround(std::min(gray.rows, gray.cols) * .055)));
    std::vector<cv::Rect> candidates;
    const auto directory = cascade_dir();
    for (const std::string name : {"haarcascade_frontalface_alt2.xml", "haarcascade_profileface.xml"}) {
        cv::CascadeClassifier classifier;
        if (directory.empty() || !classifier.load((fs::path(directory) / name).string())) continue;
        std::vector<cv::Rect> found;
        classifier.detectMultiScale(gray, found, 1.08, 6, cv::CASCADE_SCALE_IMAGE, {minimum, minimum});
        candidates.insert(candidates.end(), found.begin(), found.end());
        if (name.find("profile") != std::string::npos) {
            cv::Mat1b mirrored;
            cv::flip(gray, mirrored, 1);
            classifier.detectMultiScale(mirrored, found, 1.08, 6, cv::CASCADE_SCALE_IMAGE, {minimum, minimum});
            for (const auto& face : found) candidates.emplace_back(gray.cols - face.x - face.width, face.y, face.width, face.height);
        }
    }
    std::sort(candidates.begin(), candidates.end(), [](auto a, auto b) { return a.area() > b.area(); });
    std::vector<cv::Rect> faces;
    for (const auto& candidate : candidates) {
        bool duplicate = false;
        for (const auto& kept : faces) {
            const float overlap = static_cast<float>((candidate & kept).area());
            const float iou = overlap / static_cast<float>(candidate.area() + kept.area() - overlap);
            if (iou >= .28f) { duplicate = true; break; }
        }
        if (!duplicate) faces.push_back(candidate);
    }
    return faces;
}

static cv::Mat1f flash_mask(cv::Size size, const std::vector<cv::Rect>& faces) {
    cv::Mat1f mask(size, 0.0f);
    cv::parallel_for_(cv::Range(0, size.height), [&](const cv::Range& range) {
        for (int y = range.start; y < range.end; ++y) for (int x = 0; x < size.width; ++x) {
            if (faces.empty()) {
                const float nx = (x / static_cast<float>(std::max(size.width - 1, 1)) - .5f) / .58f;
                const float ny = (y / static_cast<float>(std::max(size.height - 1, 1)) - .43f) / .68f;
                mask(y, x) = std::exp(-2.15f * (nx * nx + ny * ny));
                continue;
            }
            float combined = 0;
            for (const auto& face : faces) {
                const float cx = face.x + face.width * .5f, cy = face.y + face.height * 1.05f;
                const float rx = std::max(face.width * 1.65f, size.width * .1f);
                const float ry = std::max(face.height * 2.25f, size.height * .13f);
                const float halo = std::exp(-1.35f * (std::pow((x-cx)/rx,2) + std::pow((y-cy)/ry,2)));
                const float fy = face.y + face.height * .5f;
                const float core = std::exp(-1.8f * (std::pow((x-cx)/std::max(face.width*.72f,1.0f),2)
                    + std::pow((y-fy)/std::max(face.height*.82f,1.0f),2)));
                const float person = std::max(halo * .88f, core);
                combined = 1 - (1 - combined) * (1 - person);
            }
            mask(y, x) = clamp01(combined);
        }
    });
    return mask;
}

static void apply_flash(cv::Mat3f& rgb, float intensity, const std::vector<cv::Rect>& faces, const ModeConfig& mode) {
    const cv::Mat1f mask = flash_mask(rgb.size(), faces);
    cv::parallel_for_(cv::Range(0, rgb.rows), [&](const cv::Range& range) {
        for (int y = range.start; y < range.end; ++y) for (int x = 0; x < rgb.cols; ++x) {
            cv::Vec3f p = rgb(y,x);
            const float original_lum = luminance(p), amount = mask(y,x) * intensity;
            p = clamp_pixel(p * (1 + mode.flash_gain * amount) + mode.flash_bias * amount);
            const float flashed_lum = luminance(p);
            p += (cv::Vec3f::all(flashed_lum) - p) * std::clamp(amount * mode.flash_desaturation, 0.0f, .45f);
            p *= 1 - (1 - mask(y,x)) * mode.flash_background_falloff * intensity;
            p += mode.flash_hot_tint * (smoothstep(.62f,.94f,flashed_lum) * amount);
            p -= cv::Vec3f::all((1-smoothstep(.08f,.42f,original_lum)) * amount * .018f);
            rgb(y,x) = clamp_pixel(p);
        }
    });
}

static cv::Mat3f apply_look(const cv::Mat3f& input, const ModeConfig& mode, float strength,
                            float grain, float flash, bool vignette, std::uint64_t seed,
                            std::vector<cv::Rect>* debug_faces = nullptr) {
    const cv::Size original_size = input.size();
    cv::Mat3f rgb;
    float scale = 1;
    if (std::max(input.cols, input.rows) > mode.processing_max_side) {
        scale = mode.processing_max_side / static_cast<float>(std::max(input.cols, input.rows));
        cv::resize(input, rgb, {}, scale, scale, cv::INTER_LANCZOS4);
    } else input.copyTo(rgb);
    const auto faces = flash > 0 || debug_faces ? detect_faces(rgb) : std::vector<cv::Rect>{};

    const float exposure = std::pow(2.0f, mode.exposure_ev * strength);
    for_each_pixel(rgb, [&](cv::Vec3f p, int, int) {
        for (int c=0;c<3;++c) {
            p[c] = clamp01(p[c] * exposure);
            const float film = p[c]*p[c]*(3-2*p[c]);
            p[c] += (film-p[c])*mode.contrast_amount*strength;
            p[c] = std::pow(clamp01(p[c]), 1-mode.gamma_lift*strength);
            p[c] = p[c]*(1-mode.black_compression*strength)+mode.black_lift*strength;
        }
        const float lum=luminance(p), shadows=1-smoothstep(.08f,.52f,lum), highlights=smoothstep(.52f,.96f,lum);
        const float mid=clamp01(1-shadows-highlights);
        p += (mode.shadow_tint*shadows + mode.midtone_tint*mid + mode.highlight_tint*highlights)*strength;
        const cv::Vec3f graded=mode.color_matrix*p;
        p += (graded-p)*strength;
        const float lum2=luminance(p), midtone=1-clamp01(std::abs(lum2-.52f)/.52f);
        const float saturation=1+(mode.midtone_saturation*midtone+mode.saturation_bias)*strength;
        return cv::Vec3f::all(lum2)+(p-cv::Vec3f::all(lum2))*saturation;
    });

    if (flash > 0) apply_flash(rgb, flash, faces, mode);
    const float radius=std::max(rgb.cols,rgb.rows)/850.0f;
    const cv::Mat3f softened=gaussian_blur(rgb,std::max(1.15f,radius*1.55f));
    rgb += (softened-rgb)*(mode.soften_amount*strength);
    const cv::Mat3f broad=gaussian_blur(rgb,std::max(2.4f,radius*4.2f));
    rgb -= (rgb-broad)*(mode.local_detail_amount*strength);

    cv::Mat3f glow_source(rgb.size());
    cv::parallel_for_(cv::Range(0,rgb.rows),[&](const cv::Range& range){
        for(int y=range.start;y<range.end;++y) for(int x=0;x<rgb.cols;++x){
            const float bright=std::pow(clamp01((luminance(rgb(y,x))-.72f)/.28f),2);
            glow_source(y,x)=rgb(y,x)*bright;
        }
    });
    const cv::Mat3f glow=gaussian_blur(glow_source,std::max(1.2f,radius*2.8f));
    const cv::Mat3f halo=gaussian_blur(glow_source,std::max(2.0f,radius*5.5f));
    for_each_pixel(rgb,[&](cv::Vec3f p,int x,int y){
        const cv::Vec3f g=glow(y,x)*(mode.glow_amount*strength);
        p=cv::Vec3f::all(1)-(cv::Vec3f::all(1)-p).mul(cv::Vec3f::all(1)-g);
        p+=halo(y,x).mul({.065f,.025f,.006f})*(strength*mode.halo_amount);
        if(vignette){
            const float nx=2*x/static_cast<float>(std::max(rgb.cols-1,1))-1;
            const float ny=2*y/static_cast<float>(std::max(rgb.rows-1,1))-1;
            const float edge=smoothstep(.52f,1.38f,std::sqrt(nx*nx+ny*ny));
            p=p*(1-edge*mode.vignette_amount*strength)+mode.vignette_tint*(edge*strength);
        }
        return p;
    });

    std::mt19937_64 generator(seed);
    std::normal_distribution<float> normal(0,1);
    const cv::Size texture_size(std::max(2,rgb.cols/180),std::max(2,rgb.rows/180));
    cv::Mat1f texture(texture_size);
    for(float& v: cv::Mat_<float>(texture)) v=normal(generator);
    cv::resize(texture,texture,rgb.size(),0,0,cv::INTER_CUBIC);

    cv::Mat1f fine, coarse;
    cv::Mat3f chroma;
    if(grain>0){
        fine.create(rgb.size());
        for(float& v: cv::Mat_<float>(fine)) v=normal(generator);
        coarse.create(std::max(2,rgb.rows/3),std::max(2,rgb.cols/3));
        for(float& v: cv::Mat_<float>(coarse)) v=normal(generator);
        cv::resize(coarse,coarse,rgb.size(),0,0,cv::INTER_CUBIC);
        chroma.create(rgb.size());
        for(cv::Vec3f& v: chroma){
            v={normal(generator),normal(generator),normal(generator)};
            v-=cv::Vec3f::all((v[0]+v[1]+v[2])/3);
        }
    }
    cv::parallel_for_(cv::Range(0,rgb.rows),[&](const cv::Range& range){
        for(int y=range.start;y<range.end;++y) for(int x=0;x<rgb.cols;++x){
            cv::Vec3f p=rgb(y,x)+mode.density_texture*(texture(y,x)*strength);
            if(grain>0){
                const float inverse=1-clamp01(luminance(p));
                const float pattern=fine(y,x)*mode.grain_fine_mix+coarse(y,x)*(1-mode.grain_fine_mix);
                p+=cv::Vec3f::all(pattern*(mode.grain_floor+mode.grain_shadow*inverse)*grain);
                p+=chroma(y,x)*((mode.chroma_noise_floor+mode.chroma_noise_shadow*inverse)*grain);
            }
            rgb(y,x)=clamp_pixel(p);
        }
    });
    if(scale!=1) cv::resize(rgb,rgb,original_size,0,0,cv::INTER_LANCZOS4);
    if(debug_faces){
        debug_faces->clear();
        for(auto face:faces){ face.x=std::lround(face.x/scale); face.y=std::lround(face.y/scale);
            face.width=std::lround(face.width/scale); face.height=std::lround(face.height/scale); debug_faces->push_back(face); }
    }
    return rgb;
}

}  // namespace

FilterResult FilterEngine::apply(
    const cv::Mat3f& input,
    const ModeConfig& mode,
    const FilterSettings& settings
) const {
    FilterResult result;
    result.image = apply_look(
        input,
        mode,
        settings.strength,
        settings.grain,
        settings.flash,
        settings.vignette,
        settings.seed,
        settings.collect_debug_faces ? &result.faces : nullptr
    );
    return result;
}

}  // namespace instax
