'''
Author: ansvver an5vv3r@outlook.com
Date: 2024-12-27 00:09:20
LastEditors: ansvver an5vv3r@outlook.com
LastEditTime: 2024-12-27 00:14:32
FilePath: \a-code-log\leetcode\000-start\1281.整数的各位积和之差.py
Description: 

Copyright (c) 2024 by ansvver, All Rights Reserved. 
'''
#
# @lc app=leetcode.cn id=1281 lang=python3
#
# [1281] 整数的各位积和之差
#
# https://leetcode.cn/problems/subtract-the-product-and-sum-of-digits-of-an-integer/description/
#
# algorithms
# Easy (82.54%)
# Likes:    178
# Dislikes: 0
# Total Accepted:    125.1K
# Total Submissions: 151.6K
# Testcase Example:  '234'
#
# 给你一个整数 n，请你帮忙计算并返回该整数「各位数字之积」与「各位数字之和」的差。
# 
# 
# 
# 示例 1：
# 
# 输入：n = 234
# 输出：15 
# 解释：
# 各位数之积 = 2 * 3 * 4 = 24 
# 各位数之和 = 2 + 3 + 4 = 9 
# 结果 = 24 - 9 = 15
# 
# 
# 示例 2：
# 
# 输入：n = 4421
# 输出：21
# 解释： 
# 各位数之积 = 4 * 4 * 2 * 1 = 32 
# 各位数之和 = 4 + 4 + 2 + 1 = 11 
# 结果 = 32 - 11 = 21
# 
# 
# 
# 
# 提示：
# 
# 
# 1 <= n <= 10^5
# 
# 
#

# @lc code=start
class Solution:
    def subtractProductAndSum(self, n: int) -> int:
        mul_res = 1
        sum_res = 0
        while n > 0:
            mul_res *= int(n % 10)
            sum_res += int(n % 10)
            n = int(n / 10)
        return mul_res - sum_res
# @lc code=end

