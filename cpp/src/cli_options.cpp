#include "instax/cli_options.hpp"

#include "instax/mode_config.hpp"

#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>

namespace instax {

Options parse_options(int argc,char** argv){
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

}  // namespace instax
