'''
Author: ansvver an5vv3r@outlook.com
Date: 2024-12-29 23:09:18
LastEditors: ansvver an5vv3r@outlook.com
LastEditTime: 2024-12-29 23:23:03
FilePath: \a-code-log\leetcode\000-start\852.山脉数组的峰顶索引.py
Description: 

Copyright (c) 2024 by ansvver, All Rights Reserved. 
'''
#
# @lc app=leetcode.cn id=852 lang=python3
#
# [852] 山脉数组的峰顶索引
#
# https://leetcode.cn/problems/peak-index-in-a-mountain-array/description/
#
# algorithms
# Medium (68.29%)
# Likes:    420
# Dislikes: 0
# Total Accepted:    174.3K
# Total Submissions: 255.2K
# Testcase Example:  '[0,1,0]'
#
# 给定一个长度为 n 的整数 山脉 数组 arr ，其中的值递增到一个 峰值元素 然后递减。
# 
# 返回峰值元素的下标。
# 
# 你必须设计并实现时间复杂度为 O(log(n)) 的解决方案。
# 
# 
# 
# 示例 1：
# 
# 
# 输入：arr = [0,1,0]
# 输出：1
# 
# 
# 示例 2：
# 
# 
# 输入：arr = [0,2,1,0]
# 输出：1
# 
# 
# 示例 3：
# 
# 
# 输入：arr = [0,10,5,2]
# 输出：1
# 
# 
# 
# 
# 提示：
# 
# 
# 3 <= arr.length <= 10^5
# 0 <= arr[i] <= 10^6
# 题目数据 保证 arr 是一个山脉数组
# 
# 
#

# @lc code=start
class Solution:
    def peakIndexInMountainArray(self, arr: List[int]) -> int:
        i, j = 0, len(arr) - 2
        while i  + 1 < j:
            mid = (i + j) // 2
            if arr[mid] > arr[mid + 1]:
                j = mid
            else:
                i = mid
        return j
# @lc code=end

