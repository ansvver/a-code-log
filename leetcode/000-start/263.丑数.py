'''
Author: ansvver an5vv3r@outlook.com
Date: 2024-12-28 23:21:46
LastEditors: ansvver an5vv3r@outlook.com
LastEditTime: 2024-12-28 23:25:03
FilePath: \a-code-log\leetcode\000-start\263.丑数.py
Description: 

Copyright (c) 2024 by ansvver, All Rights Reserved. 
'''
#
# @lc app=leetcode.cn id=263 lang=python3
#
# [263] 丑数
#
# https://leetcode.cn/problems/ugly-number/description/
#
# algorithms
# Easy (50.13%)
# Likes:    466
# Dislikes: 0
# Total Accepted:    200.8K
# Total Submissions: 400.6K
# Testcase Example:  '6'
#
# 丑数 就是只包含质因数 2、3 和 5 的 正 整数。
# 
# 给你一个整数 n ，请你判断 n 是否为 丑数 。如果是，返回 true ；否则，返回 false 。
# 
# 
# 
# 示例 1：
# 
# 
# 输入：n = 6
# 输出：true
# 解释：6 = 2 × 3
# 
# 示例 2：
# 
# 
# 输入：n = 1
# 输出：true
# 解释：1 没有质因数。
# 
# 示例 3：
# 
# 
# 输入：n = 14
# 输出：false
# 解释：14 不是丑数，因为它包含了另外一个质因数 7 。
# 
# 
# 
# 
# 提示：
# 
# 
# -2^31 <= n <= 2^31 - 1
# 
# 
#

# @lc code=start
class Solution:
    def isUgly(self, n: int) -> bool:
        if n <= 0:
            return False

        for i in [2, 3, 5]:
            while n % i == 0:
                n = n / i
        return True if n == 1 else False
        
# @lc code=end

