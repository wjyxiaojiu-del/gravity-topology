"""
引力计算引擎
实现 PCA 降维 + 空间权重矩阵 + 空间计量模型
"""

import json
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.metrics.pairwise import cosine_similarity
from scipy.spatial.distance import cdist
from gravity_topology.utils import calculate_entropy
import warnings
warnings.filterwarnings('ignore')


class GravityEngine:
    """引力计算引擎"""

    def __init__(self, data_file: str = "massive_data.json"):
        """初始化"""
        with open(data_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

        self.users = self.data.get('users', {})
        self.posts = self.data.get('posts', [])
        self.comments = self.data.get('comments', [])
        self.interaction_matrix = {
            k: set(v) for k, v in self.data.get('interaction_matrix', {}).items()
        }

        # 结果存储
        self.user_features: Optional[pd.DataFrame] = None
        self.pca_components: Optional[np.ndarray] = None
        self.spatial_weights: Optional[np.ndarray] = None
        self.gravity_matrix: Optional[np.ndarray] = None
        self.user_tokens: List[str] = []

    def build_feature_matrix(self, min_content: int = 3) -> pd.DataFrame:
        """
        构建用户特征矩阵

        特征维度：
        1. 内容特征：帖子数、评论数、内容长度、关键词分布
        2. 互动特征：获赞数、被评论数、互动广度
        3. 行为特征：发帖频率、活跃时段、圈子分布
        4. 文本特征：TF-IDF 主成分
        """
        print("=" * 60)
        print("Step 1: 构建用户特征矩阵")
        print("=" * 60)

        features = []

        for token, user in self.users.items():
            contents = user.get('contents', [])
            if len(contents) < min_content:
                continue

            # 1. 内容特征
            post_count = user.get('post_count', 0)
            comment_count = user.get('comment_count', 0)
            avg_content_len = np.mean([len(c) for c in contents]) if contents else 0
            total_content_len = sum(len(c) for c in contents)

            # 2. 互动特征
            total_likes = user.get('total_likes', 0)
            total_shares = user.get('total_shares', 0)
            total_favs = user.get('total_favs', 0)
            avg_likes = total_likes / max(post_count, 1)

            # 互动广度（与多少人互动过）
            interaction_breadth = len(self.interaction_matrix.get(token, set()))

            # 3. 行为特征
            post_times = user.get('post_times', [])
            if post_times:
                # 活跃时段（小时分布）
                hours = [t % 86400 // 3600 for t in post_times if t > 0]
                hour_entropy = self._calculate_entropy(hours) if hours else 0

                # 发帖间隔
                if len(post_times) > 1:
                    intervals = np.diff(sorted(post_times))
                    avg_interval = np.mean(intervals)
                    std_interval = np.std(intervals)
                else:
                    avg_interval = 0
                    std_interval = 0
            else:
                hour_entropy = 0
                avg_interval = 0
                std_interval = 0

            # 4. 圈子活跃度
            ring_activity = user.get('ring_activity', {})
            ring_count = len(ring_activity)
            ring_entropy = self._calculate_entropy(list(ring_activity.values())) if ring_activity else 0

            # 5. 内容关键词特征
            tech_keywords = ['AI', 'Agent', '算法', '模型', '数据', '技术', 'LLM', 'GPT', '智能']
            human_keywords = ['思考', '感受', '人文', '哲学', '意义', '价值', '伦理', '社会']
            question_keywords = ['?', '？', '为什么', '如何', '怎么', '什么']

            tech_score = sum(1 for c in contents for k in tech_keywords if k in c) / max(len(contents), 1)
            human_score = sum(1 for c in contents for k in human_keywords if k in c) / max(len(contents), 1)
            question_score = sum(1 for c in contents for k in question_keywords if k in c) / max(len(contents), 1)

            features.append({
                'token': token,
                'name': user.get('name', token),
                # 内容特征
                'post_count': post_count,
                'comment_count': comment_count,
                'avg_content_len': avg_content_len,
                'total_content_len': total_content_len,
                # 互动特征
                'total_likes': total_likes,
                'total_shares': total_shares,
                'total_favs': total_favs,
                'avg_likes': avg_likes,
                'interaction_breadth': interaction_breadth,
                # 行为特征
                'hour_entropy': hour_entropy,
                'avg_interval': avg_interval,
                'std_interval': std_interval,
                # 圈子特征
                'ring_count': ring_count,
                'ring_entropy': ring_entropy,
                # 内容特征
                'tech_score': tech_score,
                'human_score': human_score,
                'question_score': question_score
            })

        self.user_features = pd.DataFrame(features)
        self.user_tokens = [f['token'] for f in features]

        print(f"特征矩阵构建完成: {len(features)} 用户, 17 个特征维度")
        print(f"\n特征统计:")
        print(self.user_features.describe())

        return self.user_features

    def _calculate_entropy(self, values: list) -> float:
        """计算信息熵（委托给共享模块）"""
        return calculate_entropy(values)

    def apply_pca(self, n_components: int = 3) -> np.ndarray:
        """
        PCA 降维

        Args:
            n_components: 主成分数量

        Returns:
            降维后的特征矩阵
        """
        print("\n" + "=" * 60)
        print("Step 2: PCA 主成分分析")
        print("=" * 60)

        if self.user_features is None:
            raise ValueError("请先调用 build_feature_matrix()")

        # 选择数值特征
        feature_cols = [
            'post_count', 'comment_count', 'avg_content_len', 'total_content_len',
            'total_likes', 'total_shares', 'total_favs', 'avg_likes',
            'interaction_breadth', 'hour_entropy', 'avg_interval', 'std_interval',
            'ring_count', 'ring_entropy', 'tech_score', 'human_score', 'question_score'
        ]

        X = self.user_features[feature_cols].values

        # 标准化
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # PCA
        pca = PCA(n_components=n_components)
        self.pca_components = pca.fit_transform(X_scaled)

        # 解释方差
        explained_var = pca.explained_variance_ratio_
        print(f"\n主成分解释方差比例:")
        for i, var in enumerate(explained_var):
            print(f"  PC{i+1}: {var:.4f} ({var*100:.2f}%)")
        print(f"  累计: {sum(explained_var):.4f} ({sum(explained_var)*100:.2f}%)")

        # 主成分载荷
        print(f"\n主成分载荷 (Top 5):")
        for i in range(n_components):
            loadings = pca.components_[i]
            top_idx = np.argsort(np.abs(loadings))[-5:][::-1]
            top_features = [(feature_cols[idx], loadings[idx]) for idx in top_idx]
            print(f"  PC{i+1}: {', '.join([f'{f}({v:.2f})' for f, v in top_features])}")

        return self.pca_components

    def build_spatial_weights(self, method: str = 'knn', k: int = 10) -> np.ndarray:
        """
        构建空间权重矩阵

        Args:
            method: 方法 ('knn', 'distance', 'kernel')
            k: KNN 的 k 值

        Returns:
            空间权重矩阵
        """
        print("\n" + "=" * 60)
        print("Step 3: 构建空间权重矩阵")
        print("=" * 60)

        if self.pca_components is None:
            raise ValueError("请先调用 apply_pca()")

        n = len(self.pca_components)

        # 方法1: 基于特征空间距离
        if method == 'knn':
            # KNN 权重
            dist_matrix = cdist(self.pca_components, self.pca_components, metric='euclidean')
            self.spatial_weights = np.zeros((n, n))

            for i in range(n):
                # 找到最近的 k 个邻居
                neighbors = np.argsort(dist_matrix[i])[:k+1]
                for j in neighbors:
                    if i != j:
                        # 权重 = 1 / (1 + 距离)
                        self.spatial_weights[i][j] = 1.0 / (1.0 + dist_matrix[i][j])

        elif method == 'distance':
            # 距离权重
            dist_matrix = cdist(self.pca_components, self.pca_components, metric='euclidean')
            threshold = np.median(dist_matrix[dist_matrix > 0])
            self.spatial_weights = np.zeros((n, n))

            for i in range(n):
                for j in range(n):
                    if i != j and dist_matrix[i][j] < threshold:
                        self.spatial_weights[i][j] = 1.0 / (1.0 + dist_matrix[i][j])

        elif method == 'kernel':
            # 核函数权重
            dist_matrix = cdist(self.pca_components, self.pca_components, metric='euclidean')
            bandwidth = np.median(dist_matrix[dist_matrix > 0])
            self.spatial_weights = np.exp(-dist_matrix**2 / (2 * bandwidth**2))
            np.fill_diagonal(self.spatial_weights, 0)

        # 行标准化
        row_sums = self.spatial_weights.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1
        self.spatial_weights = self.spatial_weights / row_sums

        # 叠加真实互动关系
        self._overlay_real_interactions()

        # 统计
        non_zero = np.count_nonzero(self.spatial_weights)
        density = non_zero / (n * n)
        print(f"\n空间权重矩阵:")
        print(f"  维度: {n} x {n}")
        print(f"  非零元素: {non_zero}")
        print(f"  密度: {density:.4f}")
        print(f"  平均权重: {self.spatial_weights[self.spatial_weights > 0].mean():.4f}")

        return self.spatial_weights

    def _overlay_real_interactions(self) -> None:
        """叠加真实互动关系到权重矩阵"""
        token_to_idx = {token: i for i, token in enumerate(self.user_tokens)}

        for i, token_i in enumerate(self.user_tokens):
            interacted = self.interaction_matrix.get(token_i, set())
            for token_j in interacted:
                if token_j in token_to_idx:
                    j = token_to_idx[token_j]
                    # 增加真实互动的权重
                    self.spatial_weights[i][j] = max(self.spatial_weights[i][j], 0.5)

    def calculate_gravity(self) -> np.ndarray:
        """
        计算引力矩阵

        综合考虑：
        1. 特征空间相似度（PCA降维后）
        2. 空间权重（互动关系）
        3. 行为互补性

        Returns:
            引力矩阵
        """
        print("\n" + "=" * 60)
        print("Step 4: 计算引力矩阵")
        print("=" * 60)

        if self.pca_components is None or self.spatial_weights is None:
            raise ValueError("请先完成前面的步骤")

        n = len(self.pca_components)

        # 1. 特征相似度（余弦相似度）
        feature_sim = cosine_similarity(self.pca_components)

        # 2. 互动亲密度（来自空间权重）
        interaction_sim = self.spatial_weights

        # 3. 行为互补性
        behavior_sim = self._calculate_behavior_complementarity()

        # 综合引力 = 0.5 * 特征相似度 + 0.3 * 互动亲密度 + 0.2 * 行为互补性
        self.gravity_matrix = (
            0.5 * feature_sim +
            0.3 * interaction_sim +
            0.2 * behavior_sim
        )

        # 归一化到 [0, 1]
        self.gravity_matrix = (self.gravity_matrix - self.gravity_matrix.min()) / \
                              (self.gravity_matrix.max() - self.gravity_matrix.min() + 1e-10)

        print(f"\n引力矩阵:")
        print(f"  维度: {n} x {n}")
        print(f"  平均引力: {self.gravity_matrix.mean():.4f}")
        print(f"  最大引力: {self.gravity_matrix.max():.4f}")
        print(f"  最小引力: {self.gravity_matrix.min():.4f}")

        return self.gravity_matrix

    def _calculate_behavior_complementarity(self) -> np.ndarray:
        """计算行为互补性（向量化版本）"""
        tech = self.user_features['tech_score'].values
        human = self.user_features['human_score'].values

        # 广播计算互补性矩阵
        complementarity = (
            np.abs(tech[:, None] - human[None, :]) +
            np.abs(human[:, None] - tech[None, :])
        ) / 2.0
        np.fill_diagonal(complementarity, 0)

        # 归一化
        max_val = complementarity.max()
        if max_val > 0:
            complementarity /= max_val

        return complementarity

    def find_hidden_pairs(self, top_n: int = 20) -> List[Dict]:
        """
        发现隐藏的高潜同好对

        特征空间上极度贴近，但现实中没有任何交互

        Args:
            top_n: 返回前 N 对

        Returns:
            隐藏同好对列表
        """
        print("\n" + "=" * 60)
        print("Step 5: 发现隐藏同好对")
        print("=" * 60)

        if self.gravity_matrix is None:
            raise ValueError("请先调用 calculate_gravity()")

        candidates = []
        n = len(self.user_tokens)

        for i in range(n):
            for j in range(i+1, n):
                token_i = self.user_tokens[i]
                token_j = self.user_tokens[j]

                # 检查是否有现实交互
                has_interaction = (
                    token_j in self.interaction_matrix.get(token_i, set()) or
                    token_i in self.interaction_matrix.get(token_j, set())
                )

                if not has_interaction:
                    gravity = self.gravity_matrix[i][j]
                    if gravity > 0.3:  # 阈值
                        candidates.append({
                            'user_a': token_i,
                            'user_a_name': self.user_features.iloc[i]['name'],
                            'user_b': token_j,
                            'user_b_name': self.user_features.iloc[j]['name'],
                            'gravity': float(gravity),
                            'feature_sim': float(cosine_similarity(
                                self.pca_components[i:i+1],
                                self.pca_components[j:j+1]
                            )[0][0])
                        })

        # 排序
        candidates.sort(key=lambda x: x['gravity'], reverse=True)
        self.hidden_pairs = candidates[:top_n]

        print(f"\n找到 {len(candidates)} 对隐藏同好 (引力 > 0.3)")
        print(f"返回 Top {top_n} 对")

        return self.hidden_pairs

    def print_results(self) -> None:
        """打印结果"""
        if not hasattr(self, 'hidden_pairs') or not self.hidden_pairs:
            print("没有找到隐藏同好对")
            return

        print("\n" + "=" * 60)
        print("隐藏的高潜同好对 (Hidden Gravity Pairs)")
        print("=" * 60)

        for i, pair in enumerate(self.hidden_pairs[:15], 1):
            print(f"\n{i}. 引力值: {pair['gravity']:.4f} | 特征相似度: {pair['feature_sim']:.4f}")
            print(f"   用户A: {pair['user_a_name']}")
            print(f"   用户B: {pair['user_b_name']}")
            print(f"   现实交互: 无")

    def save_results(self, filename: str = "gravity_engine_results.json") -> None:
        """保存结果"""
        results = {
            'hidden_pairs': self.hidden_pairs,
            'user_count': len(self.user_tokens),
            'pca_explained_variance': self.pca_components.shape[1] if self.pca_components is not None else 0,
            'gravity_matrix_stats': {
                'mean': float(self.gravity_matrix.mean()) if self.gravity_matrix is not None else 0,
                'max': float(self.gravity_matrix.max()) if self.gravity_matrix is not None else 0,
                'min': float(self.gravity_matrix.min()) if self.gravity_matrix is not None else 0
            }
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n结果已保存到: {filename}")

    def run_full_pipeline(self) -> None:
        """运行完整流程"""
        self.build_feature_matrix(min_content=3)
        self.apply_pca(n_components=3)
        self.build_spatial_weights(method='knn', k=10)
        self.calculate_gravity()
        self.find_hidden_pairs(top_n=30)
        self.print_results()
        self.save_results()


if __name__ == "__main__":
    engine = GravityEngine("massive_data.json")
    engine.run_full_pipeline()
