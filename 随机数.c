#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <stdbool.h>

bool isDuplicate(int *arr, int len, int number);

int main()
{
    int min, max, num, n, i = 0;
    int *arr;            // ����һ��ָ�룬���ڴ洢�����������
    char allowDuplicate; // �Ƿ������ظ��ı�־

    do
    {
        printf("����������������ɷ�Χ����Сֵ ���ֵ����");
        scanf("%d %d", &min, &max);
        if (min > max)
        {
            printf("��Сֵ����С�ڵ������ֵ��\n");
        }

    } while (min > max);

    do
    {
        printf("���������������������");
        scanf("%d", &n);
    } while (n <= 0 || n > max);

    // Ϊ��������ڴ�
    arr = (int *)malloc(n * sizeof(int));
    if (arr == NULL)
    {
        printf("�ڴ����ʧ�ܣ�\n");
        return 1;
    }

    // �������������Ϊ��ǰʱ��
    srand(time(0));

    // ѯ���û��Ƿ������ظ�
    printf("�Ƿ�����������ظ���(y/n): ");
    scanf(" %c", &allowDuplicate); // ע��ǰ��Ŀո񣬷�ֹ��ȡ���з�

    printf("�����Ϊ��");
    while (i < n)
    {
        if (allowDuplicate == 'y' || allowDuplicate == 'Y') // ��������ظ�
        {
            num = min + rand() % (max - min + 1);
            arr[i++] = num;
            if (i < n)
            {
                printf("%d ", num); // ��ӡ���г������һ�����֣�����Ҫ���ţ�
            }
            else
            {
                printf("%d\n", num); // ��ӡ���һ������
            }
        }
        else if (allowDuplicate == 'n' || allowDuplicate == 'N') // ����������ظ�
        {
            do
            {
                // ����һ������min��max֮��������
                num = min + rand() % (max - min + 1);
            } while (isDuplicate(arr, i, num)); // ѭ��ֱ���ҵ�һ�����ظ�����

            arr[i++] = num; // ������ӵ����鲢����������

            if (i < n)
            {
                printf("%d ", num); // ��ӡ���г������һ�����֣�����Ҫ���ţ�
            }
            else
            {
                printf("%d\n", num); // ��ӡ���һ������
            }
        }
    }

    // �ͷŶ�̬������ڴ�
    free(arr);
    system("pause");

    return 0;
}

bool isDuplicate(int *arr, int len, int number)
{
    for (int i = 0; i < len; i++)
    {
        if (arr[i] == number)
        {
            return true; // ����ҵ��ظ������֣�����true
        }
    }
    return false; // ���û���ظ������֣�����false
}
