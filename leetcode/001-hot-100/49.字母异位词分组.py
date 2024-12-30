'''
Author: ansvver an5vv3r@outlook.com
Date: 2024-12-30 23:45:40
LastEditors: ansvver an5vv3r@outlook.com
LastEditTime: 2024-12-30 23:50:42
FilePath: \a-code-log\leetcode\001-hot-100\49.字母异位词分组.py
Description: 

Copyright (c) 2024 by ansvver, All Rights Reserved. 
'''
#
# @lc app=leetcode.cn id=49 lang=python3
#
# [49] 字母异位词分组
#
# https://leetcode.cn/problems/group-anagrams/description/
#
# algorithms
# Medium (69.15%)
# Likes:    2088
# Dislikes: 0
# Total Accepted:    911.6K
# Total Submissions: 1.3M
# Testcase Example:  '["eat","tea","tan","ate","nat","bat"]'
#
# 给你一个字符串数组，请你将 字母异位词 组合在一起。可以按任意顺序返回结果列表。
# 
# 字母异位词 是由重新排列源单词的所有字母得到的一个新单词。
# 
# 
# 
# 示例 1:
# 
# 
# 输入: strs = ["eat", "tea", "tan", "ate", "nat", "bat"]
# 输出: [["bat"],["nat","tan"],["ate","eat","tea"]]
# 
# 示例 2:
# 
# 
# 输入: strs = [""]
# 输出: [[""]]
# 
# 
# 示例 3:
# 
# 
# 输入: strs = ["a"]
# 输出: [["a"]]
# 
# 
# 
# 提示：
# 
# 
# 1 <= strs.length <= 10^4
# 0 <= strs[i].length <= 100
# strs[i] 仅包含小写字母
# 
# 
#

# @lc code=start
class Solution:
    def groupAnagrams(self, strs: List[str]) -> List[List[str]]:
        # cache = {}
        # for s in strs:
        #     _s = ''.join(sorted(s))
        #     if _s not in cache:
        #         cache[_s] = []
        #     cache[_s].append(s)
        # return [_ for _ in cache.values()]

        d = defaultdict(list)
        for s in strs:
            d[''.join(sorted(s))].append(s)
        
        return list(d.values())
        
# @lc code=end

