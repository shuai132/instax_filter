#include "instax/application.hpp"

#include "instax/cli_options.hpp"
#include "instax/frame_renderer.hpp"
#include "instax/mode_config.hpp"
#include "instax/processing_engine.hpp"

#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace instax {
namespace {

namespace fs = std::filesystem;

static void draw_debug(cv::Mat3b& image,const std::vector<cv::Rect>& faces,const ModeConfig& mode,
                       float strength,float grain,float flash,bool vignette,std::uint64_t seed){
    for(std::size_t i=0;i<faces.size();++i){ cv::rectangle(image,faces[i],{40,255,210},2);
        cv::putText(image,"FACE "+std::to_string(i+1),faces[i].tl()+cv::Point(0,-5),cv::FONT_HERSHEY_SIMPLEX,.55,{40,255,210},1,cv::LINE_AA); }
    std::vector<std::string> lines={"CAMERA FILTER / DEBUG","MODE "+mode.name,"FACES "+std::to_string(faces.size()),
        "STRENGTH "+std::to_string(strength),"GRAIN "+std::to_string(grain),"FLASH "+std::to_string(flash),
        std::string("VIGNETTE ")+(vignette?"ON":"OFF"),"SEED "+std::to_string(seed)};
    cv::rectangle(image,{12,12,330,28+static_cast<int>(lines.size())*25},{4,12,16},cv::FILLED);
    for(std::size_t i=0;i<lines.size();++i) cv::putText(image,lines[i],{25,40+static_cast<int>(i)*25},cv::FONT_HERSHEY_SIMPLEX,.5,
        i?cv::Scalar(238,245,242):cv::Scalar(40,255,210),1,cv::LINE_AA);
}

static std::uint64_t stable_seed(const fs::path& path){
    // Stable FNV-1a seed; deliberately independent from std::hash implementations.
    std::uint64_t value=1469598103934665603ULL;
    for(unsigned char c:path.string()){ value^=c; value*=1099511628211ULL; }
    return value;
}

static fs::path default_output(const fs::path& input,const std::string& mode){
    return input.parent_path()/(input.stem().string()+"_"+mode+input.extension().string());
}

}  // namespace

int Application::run(int argc, char** argv) const {
    try{
        const Options options=parse_options(argc,argv);
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

}  // namespace instax
