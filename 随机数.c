#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <stdbool.h>

bool isDuplicate(int *arr, int len, int number);

int main()
{
    int min, max, num, n, i = 0;
    int *arr;            // 定义一个指针，用于存储随机数的数组
    char allowDuplicate; // 是否允许重复的标志

    do
    {
        printf("请输入随机数的生成范围（最小值 最大值）：");
        scanf("%d %d", &min, &max);
        if (min > max)
        {
            printf("最小值必须小于等于最大值！\n");
        }

    } while (min > max);

    do
    {
        printf("请输入随机数生成数量：");
        scanf("%d", &n);
    } while (n <= 0 || n > max);

    // 为数组分配内存
    arr = (int *)malloc(n * sizeof(int));
    if (arr == NULL)
    {
        printf("内存分配失败！\n");
        return 1;
    }

    // 设置随机数种子为当前时间
    srand(time(0));

    // 询问用户是否允许重复
    printf("是否允许随机数重复？(y/n): ");
    scanf(" %c", &allowDuplicate); // 注意前面的空格，防止读取换行符

    printf("随机数为：");
    while (i < n)
    {
        if (allowDuplicate == 'y' || allowDuplicate == 'Y') // 如果允许重复
        {
            num = min + rand() % (max - min + 1);
            arr[i++] = num;
            if (i < n)
            {
                printf("%d ", num); // 打印所有除了最后一个数字（不需要逗号）
            }
            else
            {
                printf("%d\n", num); // 打印最后一个数字
            }
        }
        else if (allowDuplicate == 'n' || allowDuplicate == 'N') // 如果不允许重复
        {
            do
            {
                // 生成一个介于min和max之间的随机数
                num = min + rand() % (max - min + 1);
            } while (isDuplicate(arr, i, num)); // 循环直到找到一个不重复的数

            arr[i++] = num; // 将数添加到数组并将索引递增

            if (i < n)
            {
                printf("%d ", num); // 打印所有除了最后一个数字（不需要逗号）
            }
            else
            {
                printf("%d\n", num); // 打印最后一个数字
            }
        }
    }

    // 释放动态分配的内存
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
            return true; // 如果找到重复的数字，返回true
        }
    }
    return false; // 如果没有重复的数字，返回false
}
