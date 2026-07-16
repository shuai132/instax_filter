#include "instax/frame_renderer.hpp"

#include <opencv2/imgproc.hpp>

#include <algorithm>
#include <random>

namespace instax {

cv::Mat3b FrameRenderer::add(const cv::Mat3b& input, std::uint64_t seed) const {
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

cv::Mat3f FrameRenderer::fit(const cv::Mat3f& input) const {
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

}  // namespace instax
