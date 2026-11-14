cmake_minimum_required(VERSION 3.16)

# 화면 아래와 /info 에 나오는 판 번호. 무선으로 새 판을 보낼 때마다 올린다.
set(PROJECT_VER "0.3.6")
# 깃허브 빌드는 커밋 번호를 붙인다("0.2.2+1a2b3c4"). 자동 업데이트가 이 글이 다르면 새 판으로 본다
if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/build_id.txt")
    file(STRINGS "${CMAKE_CURRENT_LIST_DIR}/build_id.txt" ALBAM_BUILD_ID LIMIT_COUNT 1)
    set(PROJECT_VER "${PROJECT_VER}+${ALBAM_BUILD_ID}")
endif()

# sdkconfig.local 은 저장소에 올리지 않는다(집 와이파이 이름·비밀번호를 미리 넣어 구울 때만 쓴다).
set(SDKCONFIG_DEFAULTS "sdkconfig.defaults")
if(EXISTS "${CMAKE_CURRENT_LIST_DIR}/sdkconfig.local")
    list(APPEND SDKCONFIG_DEFAULTS "sdkconfig.local")
endif()

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(albam_board)
