'''
Author: ansvver an5vv3r@outlook.com
Date: 2024-12-26 23:56:38
LastEditors: ansvver an5vv3r@outlook.com
LastEditTime: 2024-12-26 23:58:33
FilePath: \a-code-log\leetcode\000-start\258.各位相加.py
Description: 

Copyright (c) 2024 by ansvver, All Rights Reserved. 
'''
#
# @lc app=leetcode.cn id=258 lang=python3
#
# [258] 各位相加
#
# https://leetcode.cn/problems/add-digits/description/
#
# algorithms
# Easy (70.28%)
# Likes:    706
# Dislikes: 0
# Total Accepted:    216.3K
# Total Submissions: 307.7K
# Testcase Example:  '38'
#
# 给定一个非负整数 num，反复将各个位上的数字相加，直到结果为一位数。返回这个结果。
# 
# 
# 
# 示例 1:
# 
# 
# 输入: num = 38
# 输出: 2 
# 解释: 各位相加的过程为：
# 38 --> 3 + 8 --> 11
# 11 --> 1 + 1 --> 2
# 由于 2 是一位数，所以返回 2。
# 
# 
# 示例 2:
# 
# 
# 输入: num = 0
# 输出: 0
# 
# 
# 
# 提示：
# 
# 
# 0 <= num <= 2^31 - 1
# 
# 
# 
# 
# 进阶：你可以不使用循环或者递归，在 O(1) 时间复杂度内解决这个问题吗？
# 
#

# @lc code=start
class Solution:
    def addDigits(self, num: int) -> int:
        while num >= 10:
            a = int(num / 10)
            b = int(num % 10)
            num = a + b
        return num
# @lc code=end

