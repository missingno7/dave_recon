# Native Dangerous Dave (docs/PORT_ROADMAP.md). Plain C11, no DOS, no original
# machine code. Layers: game/ (pure simulation), present/ (original logical
# presentation), platform/ (SDL3 + headless). tests/bridge/ is TEST-ONLY:
# the single place that knows the original DGROUP layout, used to verify
# native code against the oracle (tools/oracle.py).
cmake_minimum_required(VERSION 3.20)
project(dave C)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
  add_compile_options(-Wall -Wextra -Wconversion -Wno-sign-conversion)
endif()

add_library(dave_game STATIC game/anim.c)
target_include_directories(dave_game PUBLIC game)

add_executable(dave_bridge tests/bridge/bridge.c)
target_link_libraries(dave_bridge PRIVATE dave_game)
