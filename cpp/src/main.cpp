#include "instax/mode_config.hpp"
#include "instax/processing_engine.hpp"
#include "instax/frame_renderer.hpp"

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
using instax::ModeConfig;
using instax::ModeRegistry;
using instax::FilterEngine;
using instax::FilterSettings;
using instax::FrameRenderer;


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
    if(o.mode_all){ o.modes.clear(); for(const auto& [name,_]:ModeRegistry::builtins().all()) o.modes.push_back(name); }
    for(const auto& name:o.modes) if(!ModeRegistry::builtins().contains(name)) throw std::runtime_error("不支持的模式："+name);
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
            const ModeConfig& mode=ModeRegistry::builtins().get(mode_name);
            const float strength=options.strength.value_or(mode.default_strength);
            const float grain=options.grain.value_or(mode.default_grain);
            const float flash=options.flash.value_or(mode.default_flash);
            const bool frame=options.frame.value_or(mode.default_frame);
            const cv::Mat3f mode_source = frame ? FrameRenderer{}.fit(source) : source;
            const FilterSettings settings{strength, grain, flash, options.vignette, seed, options.debug};
            const auto filtered=FilterEngine{}.apply(mode_source,mode,settings);
            cv::Mat3b output; filtered.image.convertTo(output,CV_8UC3,255.0);
            if(options.debug) draw_debug(output,filtered.faces,mode,strength,grain,flash,options.vignette,seed);
            if(frame) output=FrameRenderer{}.add(output,seed);
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
