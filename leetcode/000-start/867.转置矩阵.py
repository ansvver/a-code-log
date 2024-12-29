'''
Author: ansvver an5vv3r@outlook.com
Date: 2024-12-29 22:22:34
LastEditors: ansvver an5vv3r@outlook.com
LastEditTime: 2024-12-29 22:37:12
FilePath: \a-code-log\leetcode\000-start\867.转置矩阵.py
Description: 

Copyright (c) 2024 by ansvver, All Rights Reserved. 
'''
#
# @lc app=leetcode.cn id=867 lang=python3
#
# [867] 转置矩阵
#
# https://leetcode.cn/problems/transpose-matrix/description/
#
# algorithms
# Easy (68.10%)
# Likes:    276
# Dislikes: 0
# Total Accepted:    120.4K
# Total Submissions: 176.8K
# Testcase Example:  '[[1,2,3],[4,5,6],[7,8,9]]'
#
# 给你一个二维整数数组 matrix， 返回 matrix 的 转置矩阵 。
# 
# 矩阵的 转置 是指将矩阵的主对角线翻转，交换矩阵的行索引与列索引。
# 
# 
# 
# 
# 
# 示例 1：
# 
# 
# 输入：matrix = [[1,2,3],[4,5,6],[7,8,9]]
# 输出：[[1,4,7],[2,5,8],[3,6,9]]
# 
# 
# 示例 2：
# 
# 
# 输入：matrix = [[1,2,3],[4,5,6]]
# 输出：[[1,4],[2,5],[3,6]]
# 
# 
# 
# 
# 提示：
# 
# 
# m == matrix.length
# n == matrix[i].length
# 1 
# 1 
# -10^9 
# 
# 
#

# @lc code=start
class Solution:
    def transpose(self, matrix: List[List[int]]) -> List[List[int]]:
        # ret = [[0] * len(matrix) for _ in matrix[0]]
        # #print(ret)
        # for i in range(len(matrix)):
        #     for j in range(len(matrix[0])):
        #         ret[j][i] = matrix[i][j]
        # return ret

        return [list(row) for row in zip(*matrix)]
# @lc code=end

