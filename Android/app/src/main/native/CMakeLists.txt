cmake_minimum_required(VERSION 3.22.1)
project(m7a_launcher C)

add_executable(m7a_launcher launcher.c)
set_target_properties(m7a_launcher PROPERTIES OUTPUT_NAME "libm7a_launcher.so")
target_compile_options(m7a_launcher PRIVATE -Wall -Wextra -Werror)
