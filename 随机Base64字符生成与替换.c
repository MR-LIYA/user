#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

// Base64 �ַ���
const char BASE64_CHARS[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789+/";

// ������� Base64 �ַ�
char generateBase64Char()
{
    int index = rand() % (sizeof(BASE64_CHARS) - 1); // ���� 0 �� 63 ���������
    return BASE64_CHARS[index];
}

// �滻ָ�����ȵ��ַ�
void replaceRandomCharacters(char *buffer, int prefixLength, int replaceLength)
{
    for (int i = 0; i < replaceLength; i++)
    {
        int index = prefixLength + rand() % (strlen(buffer) - prefixLength); // ���ѡ��һ��λ��
        buffer[index] = generateBase64Char();                                // �滻Ϊ����� Base64 �ַ�
    }
}

int main()
{
    char filePath[256];
    int replaceLength;

    // ��ȡ�û�������ļ�·��
    printf("������ Base64 �ļ�·����");
    scanf("%s", filePath);

    // ��ȡ�û�������滻����
    printf("������Ҫ�滻���ַ����ȣ�");
    scanf("%d", &replaceLength);

    // ���ļ�
    FILE *file = fopen(filePath, "r+");
    if (file == NULL)
    {
        printf("�޷����ļ���%s\n", filePath);
        return 1;
    }

    // ��ȡ�ļ���С
    fseek(file, 0, SEEK_END);
    long fileSize = ftell(file);
    fseek(file, 0, SEEK_SET);

    // �����ڴ����ڴ洢�ļ�����
    char *buffer = (char *)malloc(fileSize + 1);
    if (buffer == NULL)
    {
        printf("�ڴ����ʧ�ܣ�\n");
        fclose(file);
        return 1;
    }

    // ��ȡ�ļ�����
    fread(buffer, 1, fileSize, file);
    buffer[fileSize] = '\0'; // ����ַ���������

    // ���� Base64 ���ݵ���ʼλ��
    char *base64Data = strstr(buffer, "base64,");
    if (base64Data == NULL)
    {
        printf("�ļ���δ�ҵ� Base64 ���ݲ��֣�\n");
        free(buffer);
        fclose(file);
        return 1;
    }

    // ���� Base64 ���ݵ���ʼλ��
    int prefixLength = base64Data - buffer + strlen("base64,");

    // �������������
    srand(time(0));

    // �滻ָ�����ȵ��ַ�
    replaceRandomCharacters(buffer, prefixLength, replaceLength);

    // ���޸ĺ������д���ļ�
    fseek(file, 0, SEEK_SET);
    fwrite(buffer, 1, fileSize, file);

    // �ر��ļ�
    fclose(file);

    // �ͷ��ڴ�
    free(buffer);

    printf("�ļ��ѳɹ��޸ģ�\n");

    system("pause");
    return 0;
}
