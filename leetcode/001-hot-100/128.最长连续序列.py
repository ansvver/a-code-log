'''
Author: ansvver an5vv3r@outlook.com
Date: 2024-12-31 23:16:20
LastEditors: ansvver an5vv3r@outlook.com
LastEditTime: 2024-12-31 23:18:43
FilePath: \a-code-log\leetcode\001-hot-100\128.最长连续序列.py
Description: 

Copyright (c) 2024 by ansvver, All Rights Reserved. 
'''
#
# @lc app=leetcode.cn id=128 lang=python3
#
# [128] 最长连续序列
#
# https://leetcode.cn/problems/longest-consecutive-sequence/description/
#
# algorithms
# Medium (51.31%)
# Likes:    2314
# Dislikes: 0
# Total Accepted:    859.2K
# Total Submissions: 1.7M
# Testcase Example:  '[100,4,200,1,3,2]'
#
# 给定一个未排序的整数数组 nums ，找出数字连续的最长序列（不要求序列元素在原数组中连续）的长度。
# 
# 请你设计并实现时间复杂度为 O(n) 的算法解决此问题。
# 
# 
# 
# 示例 1：
# 
# 
# 输入：nums = [100,4,200,1,3,2]
# 输出：4
# 解释：最长数字连续序列是 [1, 2, 3, 4]。它的长度为 4。
# 
# 示例 2：
# 
# 
# 输入：nums = [0,3,7,2,5,8,4,6,0,1]
# 输出：9
# 
# 
# 
# 
# 提示：
# 
# 
# 0 <= nums.length <= 10^5
# -10^9 <= nums[i] <= 10^9
# 
# 
#

# @lc code=start
class Solution:
    def longestConsecutive(self, nums: List[int]) -> int:
        ans = 0
        n_set = set(nums)
        for x in nums:
            if x - 1 in n_set:
                continue
            y = x + 1
            while y in n_set:
                y += 1
            ans = max(ans, y - x)
        return ans
        
# @lc code=end

