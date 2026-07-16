cmake_minimum_required(VERSION 3.20)
project(instax_filter_cpp VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(OpenCV 4 REQUIRED COMPONENTS core imgproc imgcodecs objdetect)

add_executable(instax-filter-cpp
    src/main.cpp
    src/mode_config.cpp
    src/processing_engine.cpp
)
target_link_libraries(instax-filter-cpp PRIVATE ${OpenCV_LIBS})
target_include_directories(instax-filter-cpp PRIVATE include ${OpenCV_INCLUDE_DIRS})
target_compile_options(instax-filter-cpp PRIVATE
    $<$<CXX_COMPILER_ID:AppleClang,Clang,GNU>:-Wall;-Wextra;-Wpedantic>
)

get_filename_component(OPENCV_PREFIX_FROM_CONFIG "${OpenCV_DIR}/../../.." ABSOLUTE)
if(EXISTS "${OPENCV_PREFIX_FROM_CONFIG}/share/opencv4/haarcascades/haarcascade_frontalface_alt2.xml")
    target_compile_definitions(instax-filter-cpp PRIVATE
        INSTAX_CASCADE_DIR="${OPENCV_PREFIX_FROM_CONFIG}/share/opencv4/haarcascades"
    )
elseif(APPLE)
    # Homebrew installs the cascade XML files outside OpenCV's library directory.
    execute_process(
        COMMAND brew --prefix opencv
        OUTPUT_VARIABLE HOMEBREW_OPENCV_PREFIX
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_QUIET
    )
    if(HOMEBREW_OPENCV_PREFIX)
        target_compile_definitions(instax-filter-cpp PRIVATE
            INSTAX_CASCADE_DIR="${HOMEBREW_OPENCV_PREFIX}/share/opencv4/haarcascades"
        )
    endif()
endif()
