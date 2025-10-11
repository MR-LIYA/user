#include <windows.h>
#include <commdlg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_PATH_LEN 256
#define path_to_iconfile "D:/HP/Pictures/图标/神里凌华.ico"

// 定义控件ID
#define ID_BTN_INPUT 5
#define ID_BTN_OUTPUT 6
#define ID_COMBO_FUNC 3
#define ID_BTN_CONVERT 4
#define ID_STATIC_STATUS 7 // 状态标签ID

typedef unsigned char u8;

const char *MAP_TABLE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
const u8 DECODE_TABLE[256] = {
    -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
    -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
    -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 62, -1, -1, -1, 63,
    52, 53, 54, 55, 56, 57, 58, 59, 60, 61, -1, -1, -1, -1, -1, -1,
    -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14,
    15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, -1, -1, -1, -1, -1,
    -1, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40,
    41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, -1, -1, -1, -1, -1};

// 全局变量：主窗口句柄和自定义字体
HWND g_hwnd;
HFONT g_hTitleFont;

// 函数声明
void encodeImageToBase64(const char *input_path, const char *output_path);
void decodeBase64ToImage(const char *input_path, const char *output_path);
void base64Encode(const u8 *input, int input_len, char *output);
void base64Decode(const char *input, int input_len, u8 *output, int *output_len);
char *selectFile(HWND hwnd, BOOL isOpenDialog, const char *filter, const char *defaultExt);
LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam);
int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow);
void OnConvertButtonClicked(HWND hwnd, int selection, const char *inputPath, const char *outputPath);
void updateStatus(const char *statusText); // 更新状态标签函数

// 更新状态标签文本
void updateStatus(const char *statusText)
{
    HWND hStatus = GetDlgItem(g_hwnd, ID_STATIC_STATUS);
    if (hStatus != NULL)
    {
        SetWindowText(hStatus, statusText);
    }
}

// 主函数
int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow)
{
    FreeConsole();
    WNDCLASS wc = {0};
    wc.lpfnWndProc = WndProc;
    wc.hInstance = hInstance;
    wc.lpszClassName = "Base64Converter";

    if (path_to_iconfile != NULL)
    {
        wc.hIcon = (HICON)LoadImage(NULL, path_to_iconfile, IMAGE_ICON, 0, 0, LR_LOADFROMFILE);
    }
    if (wc.hIcon == NULL)
    {
        wc.hIcon = LoadIcon(NULL, IDI_APPLICATION);
    }

    wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    wc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);

    if (!RegisterClass(&wc))
    {
        MessageBox(NULL, "窗口类注册失败！", "错误", MB_ICONEXCLAMATION | MB_OK);
        return 0;
    }

    HWND hwnd = CreateWindowEx(
        0,
        wc.lpszClassName,
        "Base64 图像转换器",
        WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT, CW_USEDEFAULT,
        540, 300, // 适当增加窗口高度
        NULL, NULL, hInstance, NULL);

    if (hwnd == NULL)
    {
        MessageBox(NULL, "窗口创建失败！", "错误", MB_ICONEXCLAMATION | MB_OK);
        return 0;
    }

    g_hwnd = hwnd; // 保存主窗口句柄到全局变量
    ShowWindow(hwnd, nCmdShow);
    UpdateWindow(hwnd);

    MSG msg;
    while (GetMessage(&msg, NULL, 0, 0) > 0)
    {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }

    // 释放字体资源
    if (g_hTitleFont)
        DeleteObject(g_hTitleFont);
    return (int)msg.wParam;
}

// 文件选择函数
char *selectFile(HWND hwnd, BOOL isOpenDialog, const char *filter, const char *defaultExt)
{
    static char filePath[MAX_PATH_LEN] = {0};
    OPENFILENAME ofn;

    ZeroMemory(&ofn, sizeof(OPENFILENAME));
    ofn.lStructSize = sizeof(OPENFILENAME);
    ofn.hwndOwner = hwnd;
    ofn.lpstrFile = filePath;
    ofn.lpstrFile[0] = '\0';
    ofn.nMaxFile = MAX_PATH_LEN;
    ofn.lpstrFilter = filter;
    ofn.nFilterIndex = 1;
    ofn.lpstrFileTitle = NULL;
    ofn.nMaxFileTitle = 0;
    ofn.lpstrInitialDir = NULL;
    ofn.lpstrDefExt = defaultExt;
    // 移除不存在的OFN_ADDEXT标志
    ofn.Flags = OFN_PATHMUSTEXIST | OFN_FILEMUSTEXIST | OFN_HIDEREADONLY | OFN_OVERWRITEPROMPT;

    BOOL success;
    if (isOpenDialog)
    {
        success = GetOpenFileName(&ofn);
    }
    else
    {
        success = GetSaveFileName(&ofn);
    }

    return success ? filePath : NULL;
}

// 窗口过程
LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
    static HWND comboFunc, editInput, editOutput, btnConvert, btnInputBrowse, btnOutputBrowse;
    static int currentSelection = 0;

    switch (msg)
    {
    case WM_CREATE:
        // 输入文件标签
        CreateWindow("STATIC", "输入文件路径:",
                     WS_VISIBLE | WS_CHILD | SS_LEFT,
                     10, 30, 110, 25, hwnd, NULL, NULL, NULL);

        // 输入文件编辑框
        editInput = CreateWindow("EDIT", "",
                                 WS_CHILD | WS_VISIBLE | WS_BORDER | ES_AUTOHSCROLL,
                                 120, 30, 300, 25, hwnd, (HMENU)1, NULL, NULL);

        // 输入文件浏览按钮
        btnInputBrowse = CreateWindow("BUTTON", "...",
                                      WS_VISIBLE | WS_CHILD | BS_PUSHBUTTON,
                                      430, 30, 30, 25, hwnd, (HMENU)ID_BTN_INPUT, NULL, NULL);

        // 输出文件标签
        CreateWindow("STATIC", "输出文件路径:",
                     WS_VISIBLE | WS_CHILD | SS_LEFT,
                     10, 70, 110, 25, hwnd, NULL, NULL, NULL);

        // 输出文件编辑框
        editOutput = CreateWindow("EDIT", "",
                                  WS_CHILD | WS_VISIBLE | WS_BORDER | ES_AUTOHSCROLL,
                                  120, 70, 300, 25, hwnd, (HMENU)2, NULL, NULL);

        // 输出文件浏览按钮
        btnOutputBrowse = CreateWindow("BUTTON", "...",
                                       WS_VISIBLE | WS_CHILD | BS_PUSHBUTTON,
                                       430, 70, 30, 25, hwnd, (HMENU)ID_BTN_OUTPUT, NULL, NULL);

        // 功能选择下拉框
        comboFunc = CreateWindow("COMBOBOX", "",
                                 WS_VISIBLE | WS_CHILD | CBS_DROPDOWNLIST | CBS_HASSTRINGS,
                                 10, 110, 250, 200, hwnd, (HMENU)ID_COMBO_FUNC, NULL, NULL);
        SendMessage(comboFunc, CB_ADDSTRING, 0, (LPARAM) "图像转Base64");
        SendMessage(comboFunc, CB_ADDSTRING, 0, (LPARAM) "Base64转图像");
        SendMessage(comboFunc, CB_SETCURSEL, 0, 0);

        // 转换按钮
        btnConvert = CreateWindow(
            "BUTTON",
            "转换",
            WS_VISIBLE | WS_CHILD | BS_PUSHBUTTON,
            270, 110, 80, 25,
            hwnd, (HMENU)ID_BTN_CONVERT, NULL, NULL);

        // 状态标签（可动态更新）
        CreateWindow("STATIC", "状态: 就绪",
                     WS_VISIBLE | WS_CHILD | SS_LEFT,
                     10, 180, 400, 25, // 加宽标签宽度
                     hwnd, (HMENU)ID_STATIC_STATUS, NULL, NULL);
        break;

    case WM_COMMAND:
        // 处理输入文件浏览按钮
        if (LOWORD(wParam) == ID_BTN_INPUT && HIWORD(wParam) == BN_CLICKED)
        {
            const char *filter = currentSelection == 0 ? "图像文件 (*.bmp;*.jpg;*.png;*.gif)\0*.bmp;*.jpg;*.png;*.gif\0所有文件 (*.*)\0*.*\0\0" : "文本文件 (*.txt)\0*.txt\0所有文件 (*.*)\0*.*\0\0";
            const char *ext = currentSelection == 0 ? NULL : "txt";

            char *filePath = selectFile(hwnd, TRUE, filter, ext);
            if (filePath)
            {
                SetWindowText(editInput, filePath);
                updateStatus("状态: 已选择输入文件"); // 更新状态
            }
        }
        // 处理输出文件浏览按钮
        else if (LOWORD(wParam) == ID_BTN_OUTPUT && HIWORD(wParam) == BN_CLICKED)
        {
            const char *filter = currentSelection == 0 ? "文本文件 (*.txt)\0*.txt\0所有文件 (*.*)\0*.*\0\0" : "图像文件 (*.bmp;*.jpg;*.png;*.gif)\0*.bmp;*.jpg;*.png;*.gif\0所有文件 (*.*)\0*.*\0\0";
            const char *ext = currentSelection == 0 ? "txt" : NULL;

            char *filePath = selectFile(hwnd, FALSE, filter, ext);
            if (filePath)
            {
                SetWindowText(editOutput, filePath);
                updateStatus("状态: 已选择输出文件"); // 更新状态
            }
        }
        // 处理下拉框选择变化
        else if (HIWORD(wParam) == CBN_SELCHANGE && LOWORD(wParam) == ID_COMBO_FUNC)
        {
            currentSelection = SendMessage(comboFunc, CB_GETCURSEL, 0, 0);
            updateStatus(currentSelection == 0 ? "状态: 已选择功能 - 图像转Base64" : "状态: 已选择功能 - Base64转图像");
        }
        // 处理转换按钮
        else if (LOWORD(wParam) == ID_BTN_CONVERT && HIWORD(wParam) == BN_CLICKED)
        {
            char inputPath[MAX_PATH_LEN] = {0}, outputPath[MAX_PATH_LEN] = {0};
            GetWindowText(editInput, inputPath, MAX_PATH_LEN);
            GetWindowText(editOutput, outputPath, MAX_PATH_LEN);

            if (strlen(inputPath) == 0 || strlen(outputPath) == 0)
            {
                MessageBox(hwnd, "请选择输入和输出文件路径", "提示", MB_OK | MB_ICONINFORMATION);
                updateStatus("状态: 错误 - 未选择文件路径"); // 更新状态
                return 0;
            }

            OnConvertButtonClicked(hwnd, currentSelection, inputPath, outputPath);
        }
        break;

    case WM_CLOSE:
        DestroyWindow(hwnd);
        break;

    case WM_DESTROY:
        PostQuitMessage(0);
        break;

    default:
        return DefWindowProc(hwnd, msg, wParam, lParam);
    }

    return 0;
}

// 转换按钮点击事件处理
void OnConvertButtonClicked(HWND hwnd, int selection, const char *inputPath, const char *outputPath)
{
    updateStatus("状态: 开始转换..."); // 更新状态为转换中

    if (selection == 0)
    {
        FILE *file = fopen(inputPath, "rb");
        if (!file)
        {
            MessageBox(hwnd, "输入文件不存在或无法打开", "错误", MB_OK | MB_ICONERROR);
            updateStatus("状态: 转换失败 - 输入文件错误"); // 更新错误状态
            return;
        }
        fclose(file);
    }

    if (selection == 0)
    {
        encodeImageToBase64(inputPath, outputPath);
        MessageBox(hwnd, "图像转Base64成功", "成功", MB_OK | MB_ICONINFORMATION);
        updateStatus("状态: 转换成功 - 图像已转为Base64"); // 更新成功状态
    }
    else if (selection == 1)
    {
        decodeBase64ToImage(inputPath, outputPath);
        MessageBox(hwnd, "Base64转图像成功", "成功", MB_OK | MB_ICONINFORMATION);
        updateStatus("状态: 转换成功 - Base64已转为图像"); // 更新成功状态
    }
}

// 图像编码为Base64
void encodeImageToBase64(const char *input_path, const char *output_path)
{
    FILE *file = fopen(input_path, "rb");
    if (!file)
    {
        MessageBox(NULL, "无法打开输入文件", "错误", MB_OK | MB_ICONERROR);
        updateStatus("状态: 编码失败 - 无法打开输入文件");
        return;
    }

    fseek(file, 0, SEEK_END);
    long file_size = ftell(file);
    fseek(file, 0, SEEK_SET);

    u8 *buf = (u8 *)malloc(file_size);
    if (!buf)
    {
        MessageBox(NULL, "内存分配失败", "错误", MB_OK | MB_ICONERROR);
        updateStatus("状态: 编码失败 - 内存分配错误");
        fclose(file);
        return;
    }

    fread(buf, sizeof(u8), file_size, file);
    fclose(file);

    int base64_size = ((file_size + 2) / 3) * 4;
    char *base64 = (char *)malloc(base64_size + 1);
    if (!base64)
    {
        MessageBox(NULL, "内存分配失败", "错误", MB_OK | MB_ICONERROR);
        updateStatus("状态: 编码失败 - 内存分配错误");
        free(buf);
        return;
    }

    base64Encode(buf, file_size, base64);
    base64[base64_size] = '\0';

    FILE *output_file = fopen(output_path, "w");
    if (!output_file)
    {
        MessageBox(NULL, "无法打开输出文件", "错误", MB_OK | MB_ICONERROR);
        updateStatus("状态: 编码失败 - 无法打开输出文件");
        free(buf);
        free(base64);
        return;
    }

    char *ext = strrchr(input_path, '.');
    if (ext)
    {
        ext++;
        fprintf(output_file, "data:image/%s;base64,", ext);
    }
    else
    {
        fprintf(output_file, "data:image/jpg;base64,");
    }

    fprintf(output_file, "%s", base64);
    fclose(output_file);

    free(buf);
    free(base64);
}

// Base64解码为图像
void decodeBase64ToImage(const char *input_path, const char *output_path)
{
    FILE *file = fopen(input_path, "r");
    if (!file)
    {
        MessageBox(NULL, "无法打开输入文件", "错误", MB_OK | MB_ICONERROR);
        updateStatus("状态: 解码失败 - 无法打开输入文件");
        return;
    }

    fseek(file, 0, SEEK_END);
    long file_size = ftell(file);
    fseek(file, 0, SEEK_SET);

    char *base64 = (char *)malloc(file_size + 1);
    if (!base64)
    {
        MessageBox(NULL, "内存分配失败", "错误", MB_OK | MB_ICONERROR);
        updateStatus("状态: 解码失败 - 内存分配错误");
        fclose(file);
        return;
    }

    fread(base64, 1, file_size, file);
    base64[file_size] = '\0';
    fclose(file);

    char *data_header = strstr(base64, "data:image/");
    char *base64_data = base64;
    if (data_header)
    {
        char *comma = strstr(data_header, ",");
        if (comma)
        {
            base64_data = comma + 1;
        }
    }

    int base64_len = strlen(base64_data);
    int padding = 0;
    if (base64_len >= 1 && base64_data[base64_len - 1] == '=')
        padding++;
    if (base64_len >= 2 && base64_data[base64_len - 2] == '=')
        padding++;

    int decoded_size = ((base64_len * 3) / 4) - padding;
    u8 *decoded_data = (u8 *)malloc(decoded_size);
    if (!decoded_data)
    {
        MessageBox(NULL, "内存分配失败", "错误", MB_OK | MB_ICONERROR);
        updateStatus("状态: 解码失败 - 内存分配错误");
        free(base64);
        return;
    }

    base64Decode(base64_data, base64_len, decoded_data, &decoded_size);

    FILE *output_file = fopen(output_path, "wb");
    if (!output_file)
    {
        MessageBox(NULL, "无法打开输出文件", "错误", MB_OK | MB_ICONERROR);
        updateStatus("状态: 解码失败 - 无法打开输出文件");
        free(base64);
        free(decoded_data);
        return;
    }

    fwrite(decoded_data, 1, decoded_size, output_file);
    fclose(output_file);

    free(base64);
    free(decoded_data);
}

// Base64编码实现
void base64Encode(const u8 *input, int input_len, char *output)
{
    int i, j;
    for (i = 0, j = 0; i < input_len; i += 3, j += 4)
    {
        u8 b0 = input[i];
        u8 b1 = (i + 1 < input_len) ? input[i + 1] : 0;
        u8 b2 = (i + 2 < input_len) ? input[i + 2] : 0;

        output[j] = MAP_TABLE[b0 >> 2];
        output[j + 1] = MAP_TABLE[((b0 & 0x03) << 4) | (b1 >> 4)];
        output[j + 2] = (i + 1 < input_len) ? MAP_TABLE[((b1 & 0x0F) << 2) | (b2 >> 6)] : '=';
        output[j + 3] = (i + 2 < input_len) ? MAP_TABLE[b2 & 0x3F] : '=';
    }
    output[j] = '\0';
}

// Base64解码实现
void base64Decode(const char *input, int input_len, u8 *output, int *output_len)
{
    int i, j = 0;
    *output_len = 0;

    for (i = 0; i < input_len; i += 4)
    {
        u8 c0 = DECODE_TABLE[(u8)input[i]];
        u8 c1 = (i + 1 < input_len) ? DECODE_TABLE[(u8)input[i + 1]] : 0;
        u8 c2 = (i + 2 < input_len) ? DECODE_TABLE[(u8)input[i + 2]] : 0;
        u8 c3 = (i + 3 < input_len) ? DECODE_TABLE[(u8)input[i + 3]] : 0;

        if (c0 == (u8)-1 || c1 == (u8)-1 ||
            (input[i + 2] != '=' && c2 == (u8)-1) ||
            (input[i + 3] != '=' && c3 == (u8)-1))
        {
            continue;
        }

        output[j++] = (c0 << 2) | (c1 >> 4);
        if (input[i + 2] != '=')
            output[j++] = ((c1 & 0x0F) << 4) | (c2 >> 2);
        if (input[i + 3] != '=')
            output[j++] = ((c2 & 0x03) << 6) | c3;
    }
    *output_len = j;
}
