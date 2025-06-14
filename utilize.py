import random


def get_random_money(total_money = 10, max_user = 5):
    """
        纯随机法
    """
    result = []
    left_money = total_money
    left_user = max_user
    for i in range(left_user):
        if left_user == 1:
            money = left_money
        else:
            min_money = 0.01
            max_money = left_money / left_user * 2
            money = round(random.uniform(min_money, max_money), 2)
        left_money -= money
        left_user -= 1
        result.append(money)
    return result


def get_double_mean_money(total_money, max_user):
    """
        二倍均值法
    """
    result = []
    left_money = total_money
    left_user = max_user
    for i in range(max_user):
        if left_user == 1:
            money = left_money
        else:
            mean_money = left_money / left_user
            double_mean_money = mean_money * 2
            min_money = 1
            max_money = min(left_money, double_mean_money)
            money = int(random.uniform(min_money, max_money))
        left_money -= money
        left_user -= 1
        result.append(money)
    return result



if __name__ == '__main__':
    result = get_double_mean_money(10, 5)
    print(result)
    my_ = result.pop()
    print(result, my_)