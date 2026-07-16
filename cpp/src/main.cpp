#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/objdetect.hpp>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <limits>
#include <map>
#include <optional>
#include <random>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace fs = std::filesystem;

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

static const std::map<std::string, ModeConfig> kModes = {
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
};

struct Options {
    fs::path input;
    std::optional<fs::path> output;
    std::vector<std::string> modes{"instax"};
    std::optional<float> strength, grain, flash;
    std::optional<bool> frame;
    bool mode_all = false, vignette = true, debug = false;
    std::optional<std::uint64_t> seed;
    int quality = 95;
};

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

static cv::Mat3b add_frame(const cv::Mat3b& input, std::uint64_t seed) {
    const bool portrait=input.rows>=input.cols;
    const cv::Size image_size=portrait?cv::Size(920,1240):cv::Size(1240,920);
    const cv::Size paper_size=portrait?cv::Size(1080,1720):cv::Size(1720,1080);
    const float scale=std::max(image_size.width/static_cast<float>(input.cols),image_size.height/static_cast<float>(input.rows));
    cv::Mat3b resized; cv::resize(input,resized,{},scale,scale,cv::INTER_LANCZOS4);
    const int x=(resized.cols-image_size.width)/2,y=(resized.rows-image_size.height)/2;
    cv::Mat3b fitted=resized(cv::Rect(x,y,image_size.width,image_size.height));
    cv::Mat3b paper(paper_size,{250,249,246});
    std::mt19937_64 gen(seed^0x49A37B1D); std::normal_distribution<float> noise(0,.35f);
    for(auto& p:paper) for(int c=0;c<3;++c) p[c]=cv::saturate_cast<std::uint8_t>(p[c]+noise(gen));
    const cv::Point position=portrait?cv::Point(80,120):cv::Point(120,80);
    fitted.copyTo(paper(cv::Rect(position,image_size)));
    return paper;
}

static cv::Mat3f fit_frame_image(const cv::Mat3f& input) {
    const bool portrait = input.rows >= input.cols;
    const cv::Size target = portrait ? cv::Size(920, 1240) : cv::Size(1240, 920);
    const float scale = std::max(target.width / static_cast<float>(input.cols),
                                 target.height / static_cast<float>(input.rows));
    cv::Mat3f resized;
    cv::resize(input, resized, {}, scale, scale, cv::INTER_LANCZOS4);
    const int x = (resized.cols - target.width) / 2;
    const int y = (resized.rows - target.height) / 2;
    return resized(cv::Rect(x, y, target.width, target.height)).clone();
}

static void draw_debug(cv::Mat3b& image,const std::vector<cv::Rect>& faces,const ModeConfig& mode,
                       float strength,float grain,float flash,bool vignette,std::uint64_t seed){
    for(size_t i=0;i<faces.size();++i){ cv::rectangle(image,faces[i],{40,255,210},2);
        cv::putText(image,"FACE "+std::to_string(i+1),faces[i].tl()+cv::Point(0,-5),cv::FONT_HERSHEY_SIMPLEX,.55,{40,255,210},1,cv::LINE_AA); }
    std::vector<std::string> lines={"CAMERA FILTER / DEBUG","MODE "+mode.name,"FACES "+std::to_string(faces.size()),
        "STRENGTH "+std::to_string(strength),"GRAIN "+std::to_string(grain),"FLASH "+std::to_string(flash),
        std::string("VIGNETTE ")+(vignette?"ON":"OFF"),"SEED "+std::to_string(seed)};
    cv::rectangle(image,{12,12,330,28+static_cast<int>(lines.size())*25},{4,12,16},cv::FILLED);
    for(size_t i=0;i<lines.size();++i) cv::putText(image,lines[i],{25,40+static_cast<int>(i)*25},cv::FONT_HERSHEY_SIMPLEX,.5,
        i?cv::Scalar(238,245,242):cv::Scalar(40,255,210),1,cv::LINE_AA);
}

static std::uint64_t stable_seed(const fs::path& path){
    // Stable FNV-1a seed; deliberately independent from std::hash implementations.
    std::uint64_t value=1469598103934665603ULL;
    for(unsigned char c:path.string()){ value^=c; value*=1099511628211ULL; }
    return value;
}

static Options parse_args(int argc,char** argv){
    if(argc<2) throw std::runtime_error("用法：instax-filter-cpp INPUT [选项]（使用 --help 查看帮助）");
    Options o;
    for(int i=1;i<argc;++i){ const std::string arg=argv[i];
        auto value=[&](){ if(++i>=argc) throw std::runtime_error(arg+" 缺少参数"); return std::string(argv[i]); };
        if(arg=="-h"||arg=="--help"){
            std::cout<<"用法：instax-filter-cpp INPUT [选项]\n\n"
                <<"  -o, --output PATH       输出路径\n  --mode MODE [...]      instax/ccd/lofi/disposable/chrome/dream/noir/night\n"
                <<"  --mode-all              生成全部模式\n  --strength FLOAT       0-1.5\n  --grain FLOAT          0-2\n"
                <<"  --flash [FLOAT]         0-2；省略数值时为 1\n  --frame / --no-frame   开关相纸边框\n"
                <<"  --no-vignette           关闭暗角\n  --debug                 绘制调试信息\n  --seed INTEGER          固定随机纹理\n"
                <<"  --quality INTEGER       输出质量 1-100\n"; std::exit(0);
        } else if(arg=="-o"||arg=="--output") o.output=value();
        else if(arg=="--mode"){
            o.modes.clear();
            while(i+1<argc&&argv[i+1][0]!='-') o.modes.emplace_back(argv[++i]);
            if(o.modes.empty()) throw std::runtime_error("--mode 至少需要一个模式");
        } else if(arg=="--mode-all") o.mode_all=true;
        else if(arg=="--strength") o.strength=std::stof(value());
        else if(arg=="--grain") o.grain=std::stof(value());
        else if(arg=="--flash"){
            if(i+1<argc&&argv[i+1][0]!='-') o.flash=std::stof(argv[++i]); else o.flash=1;
        } else if(arg=="--frame") o.frame=true;
        else if(arg=="--no-frame") o.frame=false;
        else if(arg=="--no-vignette") o.vignette=false;
        else if(arg=="--debug") o.debug=true;
        else if(arg=="--seed") o.seed=std::stoull(value());
        else if(arg=="--quality") o.quality=std::stoi(value());
        else if(arg.starts_with('-')) throw std::runtime_error("未知参数："+arg);
        else if(o.input.empty()) o.input=arg;
        else throw std::runtime_error("多余参数："+arg);
    }
    if(o.input.empty()) throw std::runtime_error("缺少输入图片路径");
    if(o.mode_all){ o.modes.clear(); for(const auto& [name,_]:kModes) o.modes.push_back(name); }
    for(const auto& name:o.modes) if(!kModes.contains(name)) throw std::runtime_error("不支持的模式："+name);
    if(o.output&&o.modes.size()>1) throw std::runtime_error("生成多个模式时不能指定 --output");
    if(o.strength&&(*o.strength<0||*o.strength>1.5f)) throw std::runtime_error("--strength 必须在 0-1.5 之间");
    if(o.grain&&(*o.grain<0||*o.grain>2)) throw std::runtime_error("--grain 必须在 0-2 之间");
    if(o.flash&&(*o.flash<0||*o.flash>2)) throw std::runtime_error("--flash 必须在 0-2 之间");
    if(o.quality<1||o.quality>100) throw std::runtime_error("--quality 必须在 1-100 之间");
    return o;
}

static fs::path default_output(const fs::path& input,const std::string& mode){
    return input.parent_path()/(input.stem().string()+"_"+mode+input.extension().string());
}

int main(int argc,char** argv){
    try{
        const Options options=parse_args(argc,argv);
        if(!fs::is_regular_file(options.input)) throw std::runtime_error("找不到输入文件："+options.input.string());
        const cv::Mat unchanged=cv::imread(options.input.string(),cv::IMREAD_UNCHANGED);
        if(unchanged.empty()) throw std::runtime_error("无法读取输入图片（OpenCV codec 可能不支持该格式）");
        cv::Mat3b bgr;
        cv::Mat1b alpha;
        if(unchanged.channels()==4){ std::vector<cv::Mat> channels; cv::split(unchanged,channels); alpha=channels[3];
            cv::cvtColor(unchanged,bgr,cv::COLOR_BGRA2BGR); }
        else if(unchanged.channels()==1) cv::cvtColor(unchanged,bgr,cv::COLOR_GRAY2BGR); else bgr=unchanged;
        cv::Mat3b rgb8; cv::cvtColor(bgr,rgb8,cv::COLOR_BGR2RGB);
        cv::Mat3f source; rgb8.convertTo(source,CV_32FC3,1.0/255.0);
        const std::uint64_t seed=options.seed.value_or(stable_seed(fs::absolute(options.input)));
        for(const auto& mode_name:options.modes){
            const ModeConfig& mode=kModes.at(mode_name);
            const float strength=options.strength.value_or(mode.default_strength);
            const float grain=options.grain.value_or(mode.default_grain);
            const float flash=options.flash.value_or(mode.default_flash);
            const bool frame=options.frame.value_or(mode.default_frame);
            const cv::Mat3f mode_source = frame ? fit_frame_image(source) : source;
            std::vector<cv::Rect> faces;
            cv::Mat3f result=apply_look(mode_source,mode,strength,grain,flash,options.vignette,seed,options.debug?&faces:nullptr);
            cv::Mat3b output; result.convertTo(output,CV_8UC3,255.0);
            if(options.debug) draw_debug(output,faces,mode,strength,grain,flash,options.vignette,seed);
            if(frame) output=add_frame(output,seed);
            const fs::path path=options.output.value_or(default_output(options.input,mode_name));
            if(fs::absolute(path)==fs::absolute(options.input)) throw std::runtime_error("输出路径不能与输入文件相同");
            cv::cvtColor(output,output,cv::COLOR_RGB2BGR);
            cv::Mat output_to_write = output;
            const std::string ext=path.extension().string();
            if(!alpha.empty()&&!frame&&(ext==".png"||ext==".webp"||ext==".tif"||ext==".tiff")){
                std::vector<cv::Mat> channels; cv::split(output,channels); channels.push_back(alpha);
                cv::merge(channels,output_to_write);
            }
            std::vector<int> params;
            if(ext==".jpg"||ext==".jpeg") params={cv::IMWRITE_JPEG_QUALITY,options.quality};
            else if(ext==".webp") params={cv::IMWRITE_WEBP_QUALITY,options.quality};
            else if(ext==".png") params={cv::IMWRITE_PNG_COMPRESSION,6};
            else if(ext==".tif"||ext==".tiff") params={cv::IMWRITE_TIFF_COMPRESSION,5};
            if(!cv::imwrite(path.string(),output_to_write,params)) throw std::runtime_error("无法写入输出图片："+path.string());
            std::cout<<"已输出："<<fs::absolute(path)<<'\n';
        }
        return 0;
    }catch(const std::exception& error){ std::cerr<<"处理失败："<<error.what()<<'\n'; return 1; }
}
