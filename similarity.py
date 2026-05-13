"""
用户相似度计算模块
基于文本内容和互动行为计算用户间的"引力值"
"""

import json
import numpy as np
from typing import Dict, List, Tuple, Set
from collections import defaultdict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from data_collector import DataCollector


class GravityCalculator:
    """引力计算器 - 基于多维度相似度"""

    def __init__(self, collector: DataCollector):
        """
        初始化引力计算器

        Args:
            collector: 数据采集器实例
        """
        self.collector = collector
        self.users = collector.users
        self.interaction_matrix = collector.interaction_matrix

        # 计算结果
        self.user_vectors: Dict[str, np.ndarray] = {}
        self.gravity_matrix: Dict[str, Dict[str, float]] = defaultdict(dict)
        self.hidden_pairs: List[Tuple[str, str, float]] = []  # 隐藏的高潜同好对

    def compute_text_similarity(self) -> None:
        """
        计算基于文本内容的相似度
        使用 TF-IDF + Cosine Similarity
        """
        print("\n计算文本相似度...")

        # 准备用户文本
        user_tokens = []
        user_texts = []

        for token, user_info in self.users.items():
            texts = self.collector.get_user_texts(token)
            if texts:
                user_tokens.append(token)
                user_texts.append(' '.join(texts))

        if not user_texts:
            print("没有足够的文本数据")
            return

        # TF-IDF 向量化
        vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words=None,  # 中文需要自定义停用词
            analyzer='char_wb',  # 字符级别分析，适合中文
            ngram_range=(2, 4)
        )

        try:
            tfidf_matrix = vectorizer.fit_transform(user_texts)
        except Exception as e:
            print(f"TF-IDF 计算失败: {e}")
            # 备用方案：使用简单的词频
            self._compute_simple_similarity(user_tokens, user_texts)
            return

        # 计算余弦相似度
        sim_matrix = cosine_similarity(tfidf_matrix)

        # 存储结果
        for i, token_i in enumerate(user_tokens):
            self.user_vectors[token_i] = tfidf_matrix[i].toarray()[0]
            for j, token_j in enumerate(user_tokens):
                if i != j:
                    self.gravity_matrix[token_i][token_j] = sim_matrix[i][j]

        print(f"文本相似度计算完成，共 {len(user_tokens)} 个用户")

    def _compute_simple_similarity(self, user_tokens: List[str], user_texts: List[str]) -> None:
        """简单的字符频率相似度计算"""
        print("使用简化相似度计算...")

        def char_freq(text: str, n: int = 2) -> Dict[str, int]:
            freq = defaultdict(int)
            for i in range(len(text) - n + 1):
                freq[text[i:i+n]] += 1
            return freq

        # 计算每个用户的字符频率
        user_freqs = []
        for text in user_texts:
            freq = char_freq(text)
            # 转换为向量
            all_chars = set()
            for f in [char_freq(t) for t in user_texts]:
                all_chars.update(f.keys())

            vector = [freq.get(c, 0) for c in sorted(all_chars)]
            user_freqs.append(vector)

        # 计算余弦相似度
        for i, token_i in enumerate(user_tokens):
            for j, token_j in enumerate(user_tokens):
                if i != j:
                    v1 = np.array(user_freqs[i])
                    v2 = np.array(user_freqs[j])
                    if np.linalg.norm(v1) > 0 and np.linalg.norm(v2) > 0:
                        sim = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
                        self.gravity_matrix[token_i][token_j] = sim

    def compute_behavior_score(self) -> None:
        """
        计算行为互动得分
        基于评论、点赞等互动行为
        """
        print("\n计算行为互动得分...")

        for user_a in self.users:
            for user_b in self.users:
                if user_a == user_b:
                    continue

                score = 0.0

                # A 在 B 的帖子下评论过
                if user_b in self.interaction_matrix.get(user_a, set()):
                    score += 0.5

                # B 在 A 的帖子下评论过
                if user_a in self.interaction_matrix.get(user_b, set()):
                    score += 0.5

                # 叠加到引力矩阵
                if user_a in self.gravity_matrix:
                    if user_b in self.gravity_matrix[user_a]:
                        self.gravity_matrix[user_a][user_b] += score
                    else:
                        self.gravity_matrix[user_a][user_b] = score

        print("行为互动得分计算完成")

    def find_hidden_pairs(self, top_n: int = 20) -> List[Tuple[str, str, float]]:
        """
        发现隐藏的高潜同好对
        特征空间上极度贴近，但现实中没有任何交互

        Args:
            top_n: 返回前 N 对

        Returns:
            [(用户A, 用户B, 引力值), ...]
        """
        print("\n寻找隐藏的高潜同好对...")

        candidates = []

        for user_a in self.gravity_matrix:
            for user_b, gravity in self.gravity_matrix[user_a].items():
                # 检查是否有现实交互
                has_interaction = (
                    user_b in self.interaction_matrix.get(user_a, set()) or
                    user_a in self.interaction_matrix.get(user_b, set())
                )

                # 只选择没有现实交互的高引力对
                if not has_interaction and gravity > 0.1:
                    candidates.append((user_a, user_b, gravity))

        # 按引力值排序
        candidates.sort(key=lambda x: x[2], reverse=True)

        # 去重（A-B 和 B-A 只保留一个）
        seen = set()
        unique_pairs = []
        for a, b, g in candidates:
            pair_key = tuple(sorted([a, b]))
            if pair_key not in seen:
                seen.add(pair_key)
                unique_pairs.append((a, b, g))

        self.hidden_pairs = unique_pairs[:top_n]

        print(f"找到 {len(self.hidden_pairs)} 对隐藏同好")
        return self.hidden_pairs

    def get_user_info(self, user_token: str) -> Dict:
        """获取用户信息"""
        return self.users.get(user_token, {'token': user_token, 'name': 'Unknown'})

    def print_hidden_pairs(self) -> None:
        """打印隐藏同好对"""
        print("\n" + "=" * 60)
        print("隐藏的高潜同好对 (Hidden Gravity Pairs)")
        print("=" * 60)

        for i, (a, b, gravity) in enumerate(self.hidden_pairs, 1):
            user_a = self.get_user_info(a)
            user_b = self.get_user_info(b)
            print(f"\n{i}. 引力值: {gravity:.4f}")
            print(f"   用户A: {user_a.get('name', a)}")
            print(f"   用户B: {user_b.get('name', b)}")
            print(f"   现实交互: 无")

    def save_results(self, filename: str = "gravity_results.json") -> None:
        """保存计算结果"""
        results = {
            'hidden_pairs': [
                {
                    'user_a': a,
                    'user_a_name': self.get_user_info(a).get('name', a),
                    'user_b': b,
                    'user_b_name': self.get_user_info(b).get('name', b),
                    'gravity': g
                }
                for a, b, g in self.hidden_pairs
            ],
            'user_count': len(self.users),
            'gravity_matrix_size': sum(len(v) for v in self.gravity_matrix.values())
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n结果已保存到: {filename}")


# 测试代码
if __name__ == "__main__":
    # 加载已有数据
    collector = DataCollector(None)
    if collector.load_data("zhihu_data.json"):
        calculator = GravityCalculator(collector)
        calculator.compute_text_similarity()
        calculator.compute_behavior_score()
        calculator.find_hidden_pairs()
        calculator.print_hidden_pairs()
        calculator.save_results()
