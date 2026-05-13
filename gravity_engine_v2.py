"""
引力计算引擎 V2
深度优化版 - 基于空间计量经济学的严谨算法
"""

import json
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.decomposition import PCA
from sklearn.metrics.pairwise import cosine_similarity, euclidean_distances
from sklearn.cluster import KMeans, DBSCAN
from scipy.spatial.distance import cdist
from scipy.stats import pearsonr, spearmanr
from gravity_topology.utils import calculate_entropy
import warnings
warnings.filterwarnings('ignore')


class GravityEngineV2:
    """引力计算引擎 V2 - 深度优化版"""

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
        self.clusters: Optional[np.ndarray] = None

    def build_advanced_features(self, min_content: int = 3) -> pd.DataFrame:
        """
        构建高级用户特征矩阵

        特征维度（25维）：
        1-5: 内容特征
        6-10: 互动特征
        11-15: 行为特征
        16-20: 语义特征
        21-25: 网络特征
        """
        print("=" * 70)
        print("Step 1: 构建高级用户特征矩阵 (25维)")
        print("=" * 70)

        features = []

        for token, user in self.users.items():
            contents = user.get('contents', [])
            if len(contents) < min_content:
                continue

            # ========== 1. 内容特征 (5维) ==========
            post_count = user.get('post_count', 0)
            comment_count = user.get('comment_count', 0)
            avg_content_len = np.mean([len(c) for c in contents]) if contents else 0
            content_len_std = np.std([len(c) for c in contents]) if len(contents) > 1 else 0
            unique_words = len(set(''.join(contents).split()))

            # ========== 2. 互动特征 (5维) ==========
            total_likes = user.get('total_likes', 0)
            total_shares = user.get('total_shares', 0)
            total_favs = user.get('total_favs', 0)
            avg_likes = total_likes / max(post_count, 1)
            interaction_breadth = len(self.interaction_matrix.get(token, set()))

            # ========== 3. 行为特征 (5维) ==========
            post_times = user.get('post_times', [])
            if post_times and len(post_times) > 1:
                # 活跃时段分布
                hours = [t % 86400 // 3600 for t in post_times if t > 0]
                hour_entropy = self._calculate_entropy(hours) if hours else 0

                # 发帖规律性
                intervals = np.diff(sorted(post_times))
                interval_cv = np.std(intervals) / max(np.mean(intervals), 1)  # 变异系数

                # 活跃度趋势
                mid = len(post_times) // 2
                early_count = mid
                late_count = len(post_times) - mid
                activity_trend = (late_count - early_count) / max(len(post_times), 1)
            else:
                hour_entropy = 0
                interval_cv = 0
                activity_trend = 0

            # 圈子活跃度
            ring_activity = user.get('ring_activity', {})
            ring_count = len(ring_activity)
            ring_entropy = self._calculate_entropy(list(ring_activity.values())) if ring_activity else 0

            # ========== 4. 语义特征 (5维) ==========
            # 领域关键词
            tech_keywords = ['AI', 'Agent', '算法', '模型', '数据', '技术', 'LLM', 'GPT', '智能', '机器']
            human_keywords = ['思考', '感受', '人文', '哲学', '意义', '价值', '伦理', '社会', '文化']
            creative_keywords = ['创意', '艺术', '设计', '美学', '灵感', '想象', '表达', '风格']
            question_keywords = ['?', '？', '为什么', '如何', '怎么', '什么', '是否']
            emotion_keywords = ['喜欢', '讨厌', '开心', '难过', '焦虑', '期待', '失望', '感动']

            tech_score = sum(1 for c in contents for k in tech_keywords if k in c) / max(len(contents), 1)
            human_score = sum(1 for c in contents for k in human_keywords if k in c) / max(len(contents), 1)
            creative_score = sum(1 for c in contents for k in creative_keywords if k in c) / max(len(contents), 1)
            question_score = sum(1 for c in contents for k in question_keywords if k in c) / max(len(contents), 1)
            emotion_score = sum(1 for c in contents for k in emotion_keywords if k in c) / max(len(contents), 1)

            # ========== 5. 网络特征 (5维) ==========
            # 被互动次数
            being_interacted = sum(1 for others in self.interaction_matrix.values() if token in others)

            # 互动 reciprocity
            interacted = self.interaction_matrix.get(token, set())
            if interacted:
                reciprocal = sum(1 for u in interacted if token in self.interaction_matrix.get(u, set()))
                reciprocity = reciprocal / len(interacted)
            else:
                reciprocity = 0

            # 网络中心度（简化版）
            degree_centrality = (len(interacted) + being_interacted) / max(len(self.users), 1)

            # 内容影响力
            content_impact = (total_likes + total_shares * 2 + total_favs * 3) / max(post_count, 1)

            # 社交资本
            social_capital = being_interacted * reciprocity

            features.append({
                'token': token,
                'name': user.get('name', token),
                # 内容特征
                'post_count': post_count,
                'comment_count': comment_count,
                'avg_content_len': avg_content_len,
                'content_len_std': content_len_std,
                'unique_words': unique_words,
                # 互动特征
                'total_likes': total_likes,
                'total_shares': total_shares,
                'total_favs': total_favs,
                'avg_likes': avg_likes,
                'interaction_breadth': interaction_breadth,
                # 行为特征
                'hour_entropy': hour_entropy,
                'interval_cv': interval_cv,
                'activity_trend': activity_trend,
                'ring_count': ring_count,
                'ring_entropy': ring_entropy,
                # 语义特征
                'tech_score': tech_score,
                'human_score': human_score,
                'creative_score': creative_score,
                'question_score': question_score,
                'emotion_score': emotion_score,
                # 网络特征
                'being_interacted': being_interacted,
                'reciprocity': reciprocity,
                'degree_centrality': degree_centrality,
                'content_impact': content_impact,
                'social_capital': social_capital
            })

        self.user_features = pd.DataFrame(features)
        self.user_tokens = [f['token'] for f in features]

        print(f"特征矩阵构建完成: {len(features)} 用户, 25 个特征维度")
        print(f"\n特征统计摘要:")
        print(f"  用户数: {len(features)}")
        print(f"  平均帖子数: {self.user_features['post_count'].mean():.1f}")
        print(f"  平均评论数: {self.user_features['comment_count'].mean():.1f}")
        print(f"  平均获赞: {self.user_features['total_likes'].mean():.1f}")

        return self.user_features

    def _calculate_entropy(self, values: list) -> float:
        """计算信息熵（委托给共享模块）"""
        return calculate_entropy(values)

    def apply_pca_optimized(self, n_components: int = 5, variance_threshold: float = 0.85) -> np.ndarray:
        """
        优化的 PCA 降维

        Args:
            n_components: 最大主成分数量
            variance_threshold: 累计方差阈值

        Returns:
            降维后的特征矩阵
        """
        print("\n" + "=" * 70)
        print("Step 2: PCA 主成分分析 (优化版)")
        print("=" * 70)

        if self.user_features is None:
            raise ValueError("请先调用 build_advanced_features()")

        # 选择数值特征
        feature_cols = [
            'post_count', 'comment_count', 'avg_content_len', 'content_len_std', 'unique_words',
            'total_likes', 'total_shares', 'total_favs', 'avg_likes', 'interaction_breadth',
            'hour_entropy', 'interval_cv', 'activity_trend', 'ring_count', 'ring_entropy',
            'tech_score', 'human_score', 'creative_score', 'question_score', 'emotion_score',
            'being_interacted', 'reciprocity', 'degree_centrality', 'content_impact', 'social_capital'
        ]

        X = self.user_features[feature_cols].values

        # 处理 NaN 和 Inf
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        # 标准化
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # 自动确定主成分数量
        pca_full = PCA()
        pca_full.fit(X_scaled)

        # 找到满足方差阈值的最小主成分数
        cumulative_var = np.cumsum(pca_full.explained_variance_ratio_)
        optimal_n = np.argmax(cumulative_var >= variance_threshold) + 1
        optimal_n = min(optimal_n, n_components)

        print(f"\n自动确定主成分数量:")
        print(f"  方差阈值: {variance_threshold:.0%}")
        print(f"  最优主成分数: {optimal_n}")

        # 使用最优主成分数进行 PCA
        pca = PCA(n_components=optimal_n)
        self.pca_components = pca.fit_transform(X_scaled)

        # 解释方差
        explained_var = pca.explained_variance_ratio_
        print(f"\n主成分解释方差比例:")
        for i, var in enumerate(explained_var):
            print(f"  PC{i+1}: {var:.4f} ({var*100:.2f}%)")
        print(f"  累计: {sum(explained_var):.4f} ({sum(explained_var)*100:.2f}%)")

        # 主成分载荷分析
        print(f"\n主成分载荷分析:")
        for i in range(optimal_n):
            loadings = pca.components_[i]
            top_idx = np.argsort(np.abs(loadings))[-5:][::-1]
            top_features = [(feature_cols[idx], loadings[idx]) for idx in top_idx]
            print(f"  PC{i+1}: {', '.join([f'{f}({v:.2f})' for f, v in top_features])}")

        return self.pca_components

    def build_spatial_weights_advanced(self, method: str = 'adaptive', k: int = 15) -> np.ndarray:
        """
        高级空间权重矩阵构建

        Args:
            method: 方法 ('adaptive', 'knn', 'kernel', 'hybrid')
            k: KNN 的 k 值

        Returns:
            空间权重矩阵
        """
        print("\n" + "=" * 70)
        print("Step 3: 构建高级空间权重矩阵")
        print("=" * 70)

        if self.pca_components is None:
            raise ValueError("请先调用 apply_pca_optimized()")

        n = len(self.pca_components)

        # 计算特征空间距离
        dist_matrix = euclidean_distances(self.pca_components)

        if method == 'adaptive':
            # 自适应权重：根据局部密度调整
            self.spatial_weights = np.zeros((n, n))

            for i in range(n):
                # 找到最近的 k 个邻居
                neighbors = np.argsort(dist_matrix[i])[:k+1]

                # 计算局部密度
                local_density = k / (np.mean(dist_matrix[i][neighbors[1:]]) + 1e-10)

                for j in neighbors:
                    if i != j:
                        # 权重 = 密度归一化的距离权重
                        weight = np.exp(-dist_matrix[i][j] * local_density / 10)
                        self.spatial_weights[i][j] = weight

        elif method == 'knn':
            # KNN 权重
            self.spatial_weights = np.zeros((n, n))
            for i in range(n):
                neighbors = np.argsort(dist_matrix[i])[:k+1]
                for j in neighbors:
                    if i != j:
                        self.spatial_weights[i][j] = 1.0 / (1.0 + dist_matrix[i][j])

        elif method == 'kernel':
            # 核函数权重（高斯核）
            bandwidth = np.median(dist_matrix[dist_matrix > 0])
            self.spatial_weights = np.exp(-dist_matrix**2 / (2 * bandwidth**2))
            np.fill_diagonal(self.spatial_weights, 0)

        elif method == 'hybrid':
            # 混合方法：结合距离和互动关系
            self.spatial_weights = np.zeros((n, n))

            # 特征空间权重
            feature_weights = np.exp(-dist_matrix / np.median(dist_matrix))

            # 互动关系权重
            token_to_idx = {token: i for i, token in enumerate(self.user_tokens)}
            interaction_weights = np.zeros((n, n))

            for i, token_i in enumerate(self.user_tokens):
                interacted = self.interaction_matrix.get(token_i, set())
                for token_j in interacted:
                    if token_j in token_to_idx:
                        j = token_to_idx[token_j]
                        interaction_weights[i][j] = 1.0

            # 混合权重 = 0.6 * 特征权重 + 0.4 * 互动权重
            self.spatial_weights = 0.6 * feature_weights + 0.4 * interaction_weights
            np.fill_diagonal(self.spatial_weights, 0)

        # 行标准化
        row_sums = self.spatial_weights.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1
        self.spatial_weights = self.spatial_weights / row_sums

        # 叠加真实互动关系（增强）
        self._overlay_real_interactions_enhanced()

        # 统计
        non_zero = np.count_nonzero(self.spatial_weights)
        density = non_zero / (n * n)
        print(f"\n空间权重矩阵:")
        print(f"  方法: {method}")
        print(f"  维度: {n} x {n}")
        print(f"  非零元素: {non_zero}")
        print(f"  密度: {density:.4f}")
        print(f"  平均权重: {self.spatial_weights[self.spatial_weights > 0].mean():.4f}")

        return self.spatial_weights

    def _overlay_real_interactions_enhanced(self) -> None:
        """增强的真实互动关系叠加（预构建索引优化）"""
        token_to_idx = {token: i for i, token in enumerate(self.user_tokens)}

        # 预构建互动计数索引：(user_a, user_b) -> interaction_count
        interaction_counts = defaultdict(int)
        for c in self.comments:
            a = c.get('author_token')
            b = c.get('post_author')
            if a and b and a != b:
                key = (a, b) if a < b else (b, a)
                interaction_counts[key] += 1

        for i, token_i in enumerate(self.user_tokens):
            interacted = self.interaction_matrix.get(token_i, set())
            for token_j in interacted:
                if token_j in token_to_idx:
                    j = token_to_idx[token_j]
                    key = (token_i, token_j) if token_i < token_j else (token_j, token_i)
                    count = interaction_counts.get(key, 0)
                    weight = min(0.8, 0.3 + count * 0.05)
                    self.spatial_weights[i][j] = max(self.spatial_weights[i][j], weight)

    def calculate_gravity_enhanced(self) -> np.ndarray:
        """
        增强的引力计算

        综合考虑：
        1. 特征相似度（PCA降维后）- 40%
        2. 空间权重（互动关系）- 30%
        3. 行为互补性 - 15%
        4. 网络同配性 - 15%

        Returns:
            引力矩阵
        """
        print("\n" + "=" * 70)
        print("Step 4: 计算增强引力矩阵")
        print("=" * 70)

        if self.pca_components is None or self.spatial_weights is None:
            raise ValueError("请先完成前面的步骤")

        n = len(self.pca_components)

        # 1. 特征相似度（余弦相似度）
        feature_sim = cosine_similarity(self.pca_components)
        feature_sim = (feature_sim - feature_sim.min()) / (feature_sim.max() - feature_sim.min() + 1e-10)

        # 2. 互动亲密度（来自空间权重）
        interaction_sim = self.spatial_weights

        # 3. 行为互补性
        behavior_sim = self._calculate_behavior_complementarity_enhanced()

        # 4. 网络同配性（相似用户倾向于连接）
        assortativity_sim = self._calculate_assortativity()

        # 综合引力
        self.gravity_matrix = (
            0.40 * feature_sim +
            0.30 * interaction_sim +
            0.15 * behavior_sim +
            0.15 * assortativity_sim
        )

        # 归一化到 [0, 1]
        self.gravity_matrix = (self.gravity_matrix - self.gravity_matrix.min()) / \
                              (self.gravity_matrix.max() - self.gravity_matrix.min() + 1e-10)

        # 统计
        print(f"\n引力矩阵:")
        print(f"  维度: {n} x {n}")
        print(f"  平均引力: {self.gravity_matrix.mean():.4f}")
        print(f"  最大引力: {self.gravity_matrix.max():.4f}")
        print(f"  最小引力: {self.gravity_matrix.min():.4f}")
        print(f"  标准差: {self.gravity_matrix.std():.4f}")

        return self.gravity_matrix

    def _calculate_behavior_complementarity_enhanced(self) -> np.ndarray:
        """增强的行为互补性计算（向量化版本）"""
        tech = self.user_features['tech_score'].values
        human = self.user_features['human_score'].values
        creative = self.user_features['creative_score'].values

        # 广播计算：|tech[i] - human[j]| + |human[i] - tech[j]| + |creative[i] - creative[j]|
        complementarity = (
            np.abs(tech[:, None] - human[None, :]) +
            np.abs(human[:, None] - tech[None, :]) +
            np.abs(creative[:, None] - creative[None, :])
        ) / 3.0

        np.fill_diagonal(complementarity, 0)

        # 归一化
        max_val = complementarity.max()
        if max_val > 0:
            complementarity /= max_val

        return complementarity

    def _calculate_assortativity(self) -> np.ndarray:
        """计算网络同配性（向量化版本）"""
        degrees = np.array([len(self.interaction_matrix.get(token, set())) for token in self.user_tokens])
        max_degree = max(degrees.max(), 1)

        # 广播计算度数相似性矩阵
        assortativity = 1.0 - np.abs(degrees[:, None] - degrees[None, :]) / max_degree
        np.fill_diagonal(assortativity, 0)

        return assortativity

    def perform_clustering(self, n_clusters: int = 5) -> np.ndarray:
        """
        用户聚类分析

        Args:
            n_clusters: 聚类数量

        Returns:
            聚类标签
        """
        print("\n" + "=" * 70)
        print("Step 5: 用户聚类分析")
        print("=" * 70)

        if self.pca_components is None:
            raise ValueError("请先调用 apply_pca_optimized()")

        # K-Means 聚类
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        self.clusters = kmeans.fit_predict(self.pca_components)

        # 统计
        total_users = len(self.clusters)
        print(f"\n聚类结果:")
        for i in range(n_clusters):
            cluster_size = np.sum(self.clusters == i)
            print(f"  簇 {i}: {cluster_size} 用户 ({cluster_size/total_users*100:.1f}%)")

        return self.clusters

    def find_hidden_pairs_enhanced(self, top_n: int = 20) -> List[Dict]:
        """
        增强的隐藏同好对发现

        Args:
            top_n: 返回前 N 对

        Returns:
            隐藏同好对列表
        """
        print("\n" + "=" * 70)
        print("Step 6: 发现隐藏同好对 (增强版)")
        print("=" * 70)

        if self.gravity_matrix is None:
            raise ValueError("请先调用 calculate_gravity_enhanced()")

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
                    if gravity > 0.3:
                        # 计算匹配理由
                        match_reasons = self._analyze_match_reasons(i, j)

                        candidates.append({
                            'user_a': token_i,
                            'user_a_name': self.user_features.iloc[i]['name'],
                            'user_b': token_j,
                            'user_b_name': self.user_features.iloc[j]['name'],
                            'gravity': float(gravity),
                            'feature_sim': float(cosine_similarity(
                                self.pca_components[i:i+1],
                                self.pca_components[j:j+1]
                            )[0][0]),
                            'match_reasons': match_reasons,
                            'same_cluster': int(self.clusters[i]) == int(self.clusters[j]) if self.clusters is not None else False
                        })

        # 排序
        candidates.sort(key=lambda x: x['gravity'], reverse=True)
        self.hidden_pairs = candidates[:top_n]

        print(f"\n找到 {len(candidates)} 对隐藏同好 (引力 > 0.3)")
        print(f"返回 Top {top_n} 对")

        return self.hidden_pairs

    def _analyze_match_reasons(self, i: int, j: int) -> List[str]:
        """分析匹配理由"""
        reasons = []

        # 语义相似度
        if abs(self.user_features.iloc[i]['tech_score'] - self.user_features.iloc[j]['tech_score']) < 0.2:
            reasons.append("技术兴趣相近")

        if abs(self.user_features.iloc[i]['human_score'] - self.user_features.iloc[j]['human_score']) < 0.2:
            reasons.append("人文关怀相似")

        # 行为相似度
        if abs(self.user_features.iloc[i]['question_score'] - self.user_features.iloc[j]['question_score']) < 0.2:
            reasons.append("提问习惯相似")

        # 活跃度相似
        if abs(self.user_features.iloc[i]['activity_trend'] - self.user_features.iloc[j]['activity_trend']) < 0.3:
            reasons.append("活跃趋势相近")

        # 聚类相同
        if self.clusters is not None and self.clusters[i] == self.clusters[j]:
            reasons.append("属于同一用户群")

        return reasons if reasons else ["综合特征相似"]

    def print_results_enhanced(self) -> None:
        """打印增强的结果"""
        if not hasattr(self, 'hidden_pairs') or not self.hidden_pairs:
            print("没有找到隐藏同好对")
            return

        print("\n" + "=" * 70)
        print("隐藏的高潜同好对 (Hidden Gravity Pairs) - 增强版")
        print("=" * 70)

        for i, pair in enumerate(self.hidden_pairs[:15], 1):
            print(f"\n{i}. 引力值: {pair['gravity']:.4f} | 特征相似度: {pair['feature_sim']:.4f}")
            print(f"   用户A: {pair['user_a_name']}")
            print(f"   用户B: {pair['user_b_name']}")
            print(f"   现实交互: 无")
            print(f"   同一聚类: {'是' if pair['same_cluster'] else '否'}")
            print(f"   匹配理由: {', '.join(pair['match_reasons'])}")

    def save_results(self, filename: str = "gravity_engine_v2_results.json") -> None:
        """保存结果"""
        results = {
            'hidden_pairs': self.hidden_pairs,
            'user_count': len(self.user_tokens),
            'pca_components': self.pca_components.shape[1] if self.pca_components is not None else 0,
            'clusters': int(self.clusters.max() + 1) if self.clusters is not None else 0,
            'gravity_matrix_stats': {
                'mean': float(self.gravity_matrix.mean()) if self.gravity_matrix is not None else 0,
                'max': float(self.gravity_matrix.max()) if self.gravity_matrix is not None else 0,
                'min': float(self.gravity_matrix.min()) if self.gravity_matrix is not None else 0,
                'std': float(self.gravity_matrix.std()) if self.gravity_matrix is not None else 0
            }
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n结果已保存到: {filename}")

    def run_full_pipeline(self) -> None:
        """运行完整流程"""
        self.build_advanced_features(min_content=3)
        self.apply_pca_optimized(n_components=5, variance_threshold=0.85)
        self.build_spatial_weights_advanced(method='hybrid', k=15)
        self.calculate_gravity_enhanced()
        self.perform_clustering(n_clusters=5)
        self.find_hidden_pairs_enhanced(top_n=30)
        self.print_results_enhanced()
        self.save_results()


if __name__ == "__main__":
    engine = GravityEngineV2("massive_data.json")
    engine.run_full_pipeline()
