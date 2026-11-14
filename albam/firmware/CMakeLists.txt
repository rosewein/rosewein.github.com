cmake_minimum_required(VERSION 3.16)

# 화면 아래와 /info 에 나오는 판 번호. 무선으로 새 판을 보낼 때마다 올린다.
set(PROJECT_VER "0.1.0")

# sdkconfig.local 은 저장소에 올리지 않는다(집 와이파이 이름·비밀번호를 미리 넣어 구울 때만 쓴다).
set(SDKCONFIG_DEFAULTS "sdkconfig.defaults")
if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/sdkconfig.local")
    list(APPEND SDKCONFIG_DEFAULTS "sdkconfig.local")
endif()

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(albam_board)
