#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

// ��������
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

    printf("��ѡ�������ʽ:\n");
    printf("1. ��׼JSON��ʽ����ת�壩\n");
    printf("2. �򻯸�ʽ������ת�壩\n");
    printf("������ѡ�� (1/2): ");
    scanf("%c", &format_choice);
    getchar(); // ���ջ��з�

    printf("\n������HTML���ӻ�URL: ");
    fgets(input, sizeof(input), stdin);

    // ȥ�����з�
    size_t len = strlen(input);
    if (len > 0 && input[len - 1] == '\n')
    {
        input[len - 1] = '\0';
    }

    char *text, *full_url, *path;

    // �ж�������HTML����URL
    if (strstr(input, "<a ") && strstr(input, "</a>"))
    {
        // ������HTML����
        text = extract_text(input);
        full_url = extract_url(input);

        if (!text)
        {
            fprintf(stderr, "�޷���HTML����ȡ�ı�\n");
            return 1;
        }
        if (!full_url)
        {
            fprintf(stderr, "�޷���HTML����ȡURL\n");
            free(text);
            return 1;
        }

        // ������URL����ȡ·������
        path = get_path_from_url(full_url);
        free(full_url); // �ͷ�����URL���ڴ�

        if (!path)
        {
            fprintf(stderr, "�޷���URL����ȡ·��\n");
            free(text);
            return 1;
        }
    }
    else if (is_url(input))
    {
        // ������URL
        full_url = input;

        // ������URL����ȡ·������
        path = get_path_from_url(full_url);
        if (!path)
        {
            fprintf(stderr, "�޷���URL����ȡ·��\n");
            return 1;
        }

        // ��·������ȡ�ļ�����ΪĬ���ı�
        text = get_filename_from_url(path);
        if (!text)
        {
            // ����޷���ȡ�ļ�����ʹ������·����Ϊ�ı�
            text = strdup(path);
            if (!text)
            {
                fprintf(stderr, "�ڴ����ʧ��\n");
                free(path);
                return 1;
            }
        }
    }
    else
    {
        fprintf(stderr, "�����ʽ����ȷ��������HTML���ӻ�URL\n");
        return 1;
    }

    // �������
    if (format_choice == '1')
    {
        // ��׼JSON��ʽ����ת�壩
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
        // �򻯸�ʽ������ת�壩
        printf("{");
        printf(" \"text\": \"%s\",", text);
        printf(" \"url\": \"%s\" ", path);
        printf("}\n");
    }

    // �ͷ��ڴ�
    free(text);
    free(path);

    system("pause");

    return 0;
}

// ��ȡ�����ı�
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

// ��ȡ����URL
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

// ������URL����ȡ·�����֣�ȥ��Э�顢�����Ͷ˿ڣ�
char *get_path_from_url(const char *full_url)
{
    if (!full_url)
        return NULL;

    // �ҵ�Э���ĵ�һ�� '/'
    const char *path_start = strstr(full_url, "//");
    if (path_start)
    {
        path_start += 2; // ���� "//"

        // �ҵ�������� '/'�������ж˿ںź�û�ж˿ںŵ����
        // ���� '/'��'?' �� '#'
        const char *slash_pos = strchr(path_start, '/');
        const char *query_pos = strchr(path_start, '?');
        const char *hash_pos = strchr(path_start, '#');

        // �ҵ�������ֵķָ���
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
            // ���û���ҵ��κηָ��������� "/"
            return strdup("/");
        }
    }
    else
    {
        // ���û��Э�飬ֱ�Ӵӵ�һ�� '/' ��ʼ
        path_start = strchr(full_url, '/');
        if (!path_start)
        {
            // ���û��·�������� "/"
            return strdup("/");
        }
    }

    // ��ȡ�� path_start ���ַ��������Ĳ���
    return strdup(path_start);
}

// JSONת��
char *escape_json(const char *str)
{
    if (!str)
        return NULL;

    size_t len = strlen(str);
    char *escaped = (char *)malloc(len * 2 + 1); // ����ÿ���ַ�����Ҫת��
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

// �ж��Ƿ�ΪURL
int is_url(const char *str)
{
    if (!str)
        return 0;

    // �򵥵�URL�жϣ�����http://��https://
    if (strstr(str, "http://") == str || strstr(str, "https://") == str)
    {
        return 1;
    }

    return 0;
}

// ��URL·������ȡ�ļ�����ΪĬ���ı�
char *get_filename_from_url(const char *url_path)
{
    if (!url_path)
        return NULL;

    // �ҵ����һ�� '/'
    const char *last_slash = strrchr(url_path, '/');
    if (!last_slash)
        return NULL;

    const char *filename = last_slash + 1;

    // ����ļ����ǿյģ�����NULL
    if (*filename == '\0')
        return NULL;

    // �ҵ��ļ����е� '.'������еĻ���
    const char *dot = strrchr(filename, '.');
    if (!dot)
    {
        // û����չ�������������ļ���
        return strdup(filename);
    }

    // ����չ�������ز�������չ���Ĳ���
    size_t len = dot - filename;
    char *result = (char *)malloc(len + 1);
    if (!result)
        return NULL;

    strncpy(result, filename, len);
    result[len] = '\0';

    return result;
}
