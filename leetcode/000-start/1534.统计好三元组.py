'''
Author: ansvver an5vv3r@outlook.com
Date: 2024-12-25 23:04:59
LastEditors: ansvver an5vv3r@outlook.com
LastEditTime: 2024-12-25 23:57:54
FilePath: \a-code-log\leetcode\000-start\1534.统计好三元组.py
Description: 

Copyright (c) 2024 by ansvver, All Rights Reserved. 
'''
#
# @lc app=leetcode.cn id=1534 lang=python3
#
# [1534] 统计好三元组
#
# https://leetcode.cn/problems/count-good-triplets/description/
#
# algorithms
# Easy (75.54%)
# Likes:    89
# Dislikes: 0
# Total Accepted:    56.4K
# Total Submissions: 74.6K
# Testcase Example:  '[3,0,1,1,9,7]\n7\n2\n3'
#
# 给你一个整数数组 arr ，以及 a、b 、c 三个整数。请你统计其中好三元组的数量。
# 
# 如果三元组 (arr[i], arr[j], arr[k]) 满足下列全部条件，则认为它是一个 好三元组 。
# 
# 
# 0 <= i < j < k < arr.length
# |arr[i] - arr[j]| <= a
# |arr[j] - arr[k]| <= b
# |arr[i] - arr[k]| <= c
# 
# 
# 其中 |x| 表示 x 的绝对值。
# 
# 返回 好三元组的数量 。
# 
# 
# 
# 示例 1：
# 
# 输入：arr = [3,0,1,1,9,7], a = 7, b = 2, c = 3
# 输出：4
# 解释：一共有 4 个好三元组：[(3,0,1), (3,0,1), (3,1,1), (0,1,1)] 。
# 
# 
# 示例 2：
# 
# 输入：arr = [1,1,2,2,3], a = 0, b = 0, c = 1
# 输出：0
# 解释：不存在满足所有条件的三元组。
# 
# 
# 
# 
# 提示：
# 
# 
# 3 <= arr.length <= 100
# 0 <= arr[i] <= 1000
# 0 <= a, b, c <= 1000
# 
# 
#

# @lc code=start
class Solution:
    def countGoodTriplets(self, arr: List[int], a: int, b: int, c: int) -> int:
        ret = 0
        n = len(arr)

        for i in range(n):
            for j in range(i+1, n):
                if abs(arr[i] - arr[j]) <= a:
                    for k in range(j+1, n):
                        if abs(arr[j] - arr[k]) <= b and abs(arr[i] - arr[k]) <= c:
                            ret += 1


        return ret 
# @lc code=end

