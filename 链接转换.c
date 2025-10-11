#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

// 函数声明
char *extract_text(const char *html);
char *extract_url(const char *html);
char *get_path_from_url(const char *full_url);
char *escape_json(const char *str);
int is_url(const char *str);
char *get_filename_from_url(const char *url);

int main()
{
    char input[1024];
    char format_choice;

    printf("请选择输出格式:\n");
    printf("1. 标准JSON格式（带转义）\n");
    printf("2. 简化格式（不带转义）\n");
    printf("请输入选择 (1/2): ");
    scanf("%c", &format_choice);
    getchar(); // 吸收换行符

    printf("\n请输入HTML链接或URL: ");
    fgets(input, sizeof(input), stdin);

    // 去除换行符
    size_t len = strlen(input);
    if (len > 0 && input[len - 1] == '\n')
    {
        input[len - 1] = '\0';
    }

    char *text, *full_url, *path;

    // 判断输入是HTML还是URL
    if (strstr(input, "<a ") && strstr(input, "</a>"))
    {
        // 输入是HTML链接
        text = extract_text(input);
        full_url = extract_url(input);

        if (!text)
        {
            fprintf(stderr, "无法从HTML中提取文本\n");
            return 1;
        }
        if (!full_url)
        {
            fprintf(stderr, "无法从HTML中提取URL\n");
            free(text);
            return 1;
        }

        // 从完整URL中提取路径部分
        path = get_path_from_url(full_url);
        free(full_url); // 释放完整URL的内存

        if (!path)
        {
            fprintf(stderr, "无法从URL中提取路径\n");
            free(text);
            return 1;
        }
    }
    else if (is_url(input))
    {
        // 输入是URL
        full_url = input;

        // 从完整URL中提取路径部分
        path = get_path_from_url(full_url);
        if (!path)
        {
            fprintf(stderr, "无法从URL中提取路径\n");
            return 1;
        }

        // 从路径中提取文件名作为默认文本
        text = get_filename_from_url(path);
        if (!text)
        {
            // 如果无法提取文件名，使用整个路径作为文本
            text = strdup(path);
            if (!text)
            {
                fprintf(stderr, "内存分配失败\n");
                free(path);
                return 1;
            }
        }
    }
    else
    {
        fprintf(stderr, "输入格式不正确，请输入HTML链接或URL\n");
        return 1;
    }

    // 生成输出
    if (format_choice == '1')
    {
        // 标准JSON格式（带转义）
        char *escaped_text = escape_json(text);
        char *escaped_path = escape_json(path);

        printf("{");
        printf(" \"text\": \"%s\",", escaped_text ? escaped_text : "");
        printf(" \"url\": \"%s\"", escaped_path ? escaped_path : "");
        printf("}\n");

        free(escaped_text);
        free(escaped_path);
    }
    else
    {
        // 简化格式（不带转义）
        printf("{");
        printf(" \"text\": \"%s\",", text);
        printf(" \"url\": \"%s\" ", path);
        printf("}\n");
    }

    // 释放内存
    free(text);
    free(path);

    system("pause");

    return 0;
}

// 提取链接文本
char *extract_text(const char *html)
{
    const char *start = strstr(html, ">");
    if (!start)
        return NULL;

    const char *end = strstr(start + 1, "</a>");
    if (!end)
        return NULL;

    size_t len = end - (start + 1);
    char *text = (char *)malloc(len + 1);
    if (!text)
        return NULL;

    strncpy(text, start + 1, len);
    text[len] = '\0';

    return text;
}

// 提取完整URL
char *extract_url(const char *html)
{
    const char *start = strstr(html, "location.href='");
    if (!start)
        return NULL;

    start += strlen("location.href='");

    const char *end = strchr(start, '\'');
    if (!end)
        return NULL;

    size_t len = end - start;
    char *url = (char *)malloc(len + 1);
    if (!url)
        return NULL;

    strncpy(url, start, len);
    url[len] = '\0';

    return url;
}

// 从完整URL中提取路径部分（去掉协议、域名和端口）
char *get_path_from_url(const char *full_url)
{
    if (!full_url)
        return NULL;

    // 找到协议后的第一个 '/'
    const char *path_start = strstr(full_url, "//");
    if (path_start)
    {
        path_start += 2; // 跳过 "//"

        // 找到域名后的 '/'，处理有端口号和没有端口号的情况
        // 查找 '/'、'?' 或 '#'
        const char *slash_pos = strchr(path_start, '/');
        const char *query_pos = strchr(path_start, '?');
        const char *hash_pos = strchr(path_start, '#');

        // 找到最早出现的分隔符
        const char *first_sep = NULL;
        if (slash_pos)
            first_sep = slash_pos;
        if (query_pos && (!first_sep || query_pos < first_sep))
            first_sep = query_pos;
        if (hash_pos && (!first_sep || hash_pos < first_sep))
            first_sep = hash_pos;

        if (first_sep)
        {
            path_start = first_sep;
        }
        else
        {
            // 如果没有找到任何分隔符，返回 "/"
            return strdup("/");
        }
    }
    else
    {
        // 如果没有协议，直接从第一个 '/' 开始
        path_start = strchr(full_url, '/');
        if (!path_start)
        {
            // 如果没有路径，返回 "/"
            return strdup("/");
        }
    }

    // 提取从 path_start 到字符串结束的部分
    return strdup(path_start);
}

// JSON转义
char *escape_json(const char *str)
{
    if (!str)
        return NULL;

    size_t len = strlen(str);
    char *escaped = (char *)malloc(len * 2 + 1); // 最坏情况每个字符都需要转义
    if (!escaped)
        return NULL;

    char *ptr = escaped;

    for (size_t i = 0; i < len; i++)
    {
        switch (str[i])
        {
        case '"':
            *ptr++ = '\\';
            *ptr++ = '"';
            break;
        case '\\':
            *ptr++ = '\\';
            *ptr++ = '\\';
            break;
        case '/':
            *ptr++ = '\\';
            *ptr++ = '/';
            break;
        case '\b':
            *ptr++ = '\\';
            *ptr++ = 'b';
            break;
        case '\f':
            *ptr++ = '\\';
            *ptr++ = 'f';
            break;
        case '\n':
            *ptr++ = '\\';
            *ptr++ = 'n';
            break;
        case '\r':
            *ptr++ = '\\';
            *ptr++ = 'r';
            break;
        case '\t':
            *ptr++ = '\\';
            *ptr++ = 't';
            break;
        default:
            *ptr++ = str[i];
            break;
        }
    }

    *ptr = '\0';

    return escaped;
}

// 判断是否为URL
int is_url(const char *str)
{
    if (!str)
        return 0;

    // 简单的URL判断：包含http://或https://
    if (strstr(str, "http://") == str || strstr(str, "https://") == str)
    {
        return 1;
    }

    return 0;
}

// 从URL路径中提取文件名作为默认文本
char *get_filename_from_url(const char *url_path)
{
    if (!url_path)
        return NULL;

    // 找到最后一个 '/'
    const char *last_slash = strrchr(url_path, '/');
    if (!last_slash)
        return NULL;

    const char *filename = last_slash + 1;

    // 如果文件名是空的，返回NULL
    if (*filename == '\0')
        return NULL;

    // 找到文件名中的 '.'（如果有的话）
    const char *dot = strrchr(filename, '.');
    if (!dot)
    {
        // 没有扩展名，返回整个文件名
        return strdup(filename);
    }

    // 有扩展名，返回不包含扩展名的部分
    size_t len = dot - filename;
    char *result = (char *)malloc(len + 1);
    if (!result)
        return NULL;

    strncpy(result, filename, len);
    result[len] = '\0';

    return result;
}
