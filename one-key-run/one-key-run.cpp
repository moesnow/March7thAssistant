#include <windows.h>

#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>

namespace fs = std::filesystem;

bool isInstalled(std::string command, std::string keyword) {
    std::string result = "";
    char buffer[128];

    // 执行命令并捕获输出
    FILE* pipe = _popen(command.c_str(), "r");
    if (!pipe) {
        return false;
    }

    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        result += buffer;
    }

    _pclose(pipe);

    // 检查输出是否包含版本信息
    return result.find(keyword) != std::string::npos;
}

int main() {
    setlocale(LC_ALL, "zh_CN.UTF-8");

    // Check if Python is installed
    if (!isInstalled("python -V", "Python")) {
        // Check if winget is available
        if (!isInstalled("winget -v", "v")) {
            std::cout << "Python is not installed and winget is not available." << std::endl;
            std::cout << "Please download Python from the official website: https://www.python.org/downloads/" << std::endl;
            ShellExecuteW(nullptr, L"open", L"https://www.python.org/downloads/", nullptr, nullptr, SW_SHOWNORMAL);
            return 1;
        }
        std::cout << "Python is not installed. Installing..." << std::endl;
        if (system("winget install --id Python.Python.3.11") == 0) {
            std::cout << "Python installation completed." << std::endl;
            std::cout << "Please run the program again to make Python available." << std::endl;
            system("pause");
            return 0;
        }
        return 1;
    } else if (!isInstalled("python -V", "Python 3.11")) {
        std::cout << "Python version error, please use Python 3.11" << std::endl;
        std::cout << "You can check it with \"python -V\"" << std::endl;
    }

    // Change current directory
    TCHAR programPathT[MAX_PATH];
    GetModuleFileName(NULL, programPathT, MAX_PATH);
    int programPathTCount = 1;
    for (int i = 0; i < MAX_PATH && programPathT[i] != '\0'; i++) {
        programPathTCount += 1;
    }
    char programPath[programPathTCount];
    for (int i = 0; i < programPathTCount; i++) {
        programPath[i] = programPathT[i];
    }

    int programDirTCount;
    TCHAR programDirT[programPathTCount];
    for (int i = programPathTCount - 1; i >= 0; i--) {
        if (programPathT[i] == '\\') {
            int j;
            for (j = 0; j <= i; j++) {
                programDirT[j] = programPathT[j];
            }
            programDirT[j] = '\0';
            programDirTCount = j;
            break;
        }
    }
    char programDir[programDirTCount];
    for (int i = 0; i < programDirTCount; i++) {
        programDir[i] = programDirT[i];
    }
    SetCurrentDirectory(programDirT);

    // Create virtual environment if not exist
    if (!fs::exists(".venv")) {
        std::cout << "Creating virtual environment..." << std::endl;
        system("python -m venv .venv");
    }

    // Install dependencies if not installed
    if (!fs::exists(".venv/pip_installed.txt")) {
        system(".venv\\Scripts\\activate && python -m pip install -i https://mirrors.aliyun.com/pypi/simple/ --upgrade pip && pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt && echo 1 > .venv\\pip_installed.txt && deactivate");
        if (!fs::exists(".venv/pip_installed.txt")) {
            system("pause");
            return 1;
        }
    }

    // Check for administrator privileges
    if (system("net session >nul 2>nul") != 0) {
        std::cout << "Requesting administrator privileges..." << std::endl;
        ShellExecuteA(nullptr, "runas", programPath, nullptr, nullptr, SW_SHOWNORMAL);
        return 0;
    }

    // Activate virtual environment and run GUI application
    system(".venv\\Scripts\\activate && python main.py && deactivate");

    system("pause");
    return 0;
}
