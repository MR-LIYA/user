#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

// Base64 字符表
const char BASE64_CHARS[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789+/";

// 随机生成 Base64 字符
char generateBase64Char()
{
    int index = rand() % (sizeof(BASE64_CHARS) - 1); // 生成 0 到 63 的随机索引
    return BASE64_CHARS[index];
}

// 替换指定长度的字符
void replaceRandomCharacters(char *buffer, int prefixLength, int replaceLength)
{
    for (int i = 0; i < replaceLength; i++)
    {
        int index = prefixLength + rand() % (strlen(buffer) - prefixLength); // 随机选择一个位置
        buffer[index] = generateBase64Char();                                // 替换为随机的 Base64 字符
    }
}

int main()
{
    char filePath[256];
    int replaceLength;

    // 获取用户输入的文件路径
    printf("请输入 Base64 文件路径：");
    scanf("%s", filePath);

    // 获取用户输入的替换长度
    printf("请输入要替换的字符长度：");
    scanf("%d", &replaceLength);

    // 打开文件
    FILE *file = fopen(filePath, "r+");
    if (file == NULL)
    {
        printf("无法打开文件：%s\n", filePath);
        return 1;
    }

    // 获取文件大小
    fseek(file, 0, SEEK_END);
    long fileSize = ftell(file);
    fseek(file, 0, SEEK_SET);

    // 分配内存用于存储文件内容
    char *buffer = (char *)malloc(fileSize + 1);
    if (buffer == NULL)
    {
        printf("内存分配失败！\n");
        fclose(file);
        return 1;
    }

    // 读取文件内容
    fread(buffer, 1, fileSize, file);
    buffer[fileSize] = '\0'; // 添加字符串结束符

    // 查找 Base64 数据的起始位置
    char *base64Data = strstr(buffer, "base64,");
    if (base64Data == NULL)
    {
        printf("文件中未找到 Base64 数据部分！\n");
        free(buffer);
        fclose(file);
        return 1;
    }

    // 计算 Base64 数据的起始位置
    int prefixLength = base64Data - buffer + strlen("base64,");

    // 设置随机数种子
    srand(time(0));

    // 替换指定长度的字符
    replaceRandomCharacters(buffer, prefixLength, replaceLength);

    // 将修改后的内容写回文件
    fseek(file, 0, SEEK_SET);
    fwrite(buffer, 1, fileSize, file);

    // 关闭文件
    fclose(file);

    // 释放内存
    free(buffer);

    printf("文件已成功修改！\n");

    system("pause");
    return 0;
}
