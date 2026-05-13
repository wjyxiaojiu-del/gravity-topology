"""
社交网络图谱模块
可视化用户之间的互动关系
"""

import json
import networkx as nx
import matplotlib.pyplot as plt
from collections import defaultdict
from typing import Dict, List, Tuple
import matplotlib

# 设置中文字体
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False


class SocialGraph:
    """社交网络图谱"""

    def __init__(self, data_file: str = "zhihu_data_massive.json"):
        """初始化"""
        with open(data_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

        self.users = self.data.get('users', {})
        self.posts = self.data.get('posts', [])
        self.comments = self.data.get('comments', [])
        self.interaction_matrix = {
            k: set(v) for k, v in self.data.get('interaction_matrix', {}).items()
        }

        # 构建 NetworkX 图
        self.G = nx.DiGraph()

    def build_graph(self, min_content: int = 1) -> None:
        """
        构建社交网络图

        Args:
            min_content: 最小内容数量过滤
        """
        print("构建社交网络图...")

        # 添加节点
        for token, user in self.users.items():
            content_count = len(user.get('contents', []))
            if content_count >= min_content:
                self.G.add_node(token, **{
                    'name': user.get('name', token),
                    'post_count': user.get('post_count', 0),
                    'comment_count': user.get('comment_count', 0),
                    'total_likes': user.get('total_likes', 0),
                    'content_count': content_count
                })

        # 添加边（互动关系）
        for user_a, interacted in self.interaction_matrix.items():
            if user_a in self.G:
                for user_b in interacted:
                    if user_b in self.G:
                        self.G.add_edge(user_a, user_b, weight=1)

        print(f"图构建完成: {self.G.number_of_nodes()} 节点, {self.G.number_of_edges()} 边")

    def analyze_community(self) -> Dict:
        """社区分析"""
        print("\n分析社区结构...")

        # 转为无向图进行社区检测
        G_undirected = self.G.to_undirected()

        # 使用 Louvain 算法检测社区
        try:
            from networkx.algorithms.community import louvain_communities
            communities = louvain_communities(G_undirected, seed=42)
        except:
            # 备用：连通分量
            communities = list(nx.connected_components(G_undirected))

        result = {
            'community_count': len(communities),
            'communities': []
        }

        for i, comm in enumerate(communities[:10]):  # 只显示前10个社区
            members = list(comm)
            member_info = []
            for token in members[:5]:  # 每个社区显示前5个成员
                user = self.users.get(token, {})
                member_info.append({
                    'token': token,
                    'name': user.get('name', token),
                    'content_count': len(user.get('contents', []))
                })

            result['communities'].append({
                'id': i,
                'size': len(members),
                'members': member_info
            })

        return result

    def find_influencers(self, top_n: int = 10) -> List[Tuple[str, float]]:
        """找到关键影响者（基于 PageRank）"""
        print("\n计算 PageRank 找关键影响者...")

        if self.G.number_of_nodes() == 0:
            return []

        pagerank = nx.pagerank(self.G, alpha=0.85)
        sorted_users = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)

        return sorted_users[:top_n]

    def visualize(self, output_file: str = "social_graph.png", max_nodes: int = 100) -> None:
        """可视化社交网络"""
        print(f"\n生成可视化图 ({output_file})...")

        if self.G.number_of_nodes() == 0:
            print("图为空，无法可视化")
            return

        # 如果节点太多，只显示重要的节点
        if self.G.number_of_nodes() > max_nodes:
            pagerank = nx.pagerank(self.G, alpha=0.85)
            top_nodes = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:max_nodes]
            subgraph = self.G.subgraph([n for n, _ in top_nodes])
        else:
            subgraph = self.G

        plt.figure(figsize=(16, 12))

        # 布局
        pos = nx.spring_layout(subgraph, k=2, iterations=50, seed=42)

        # 节点大小基于 PageRank
        pagerank = nx.pagerank(subgraph, alpha=0.85)
        node_sizes = [pagerank.get(n, 0.001) * 10000 for n in subgraph.nodes()]

        # 节点颜色基于内容数量
        content_counts = [len(self.users.get(n, {}).get('contents', [])) for n in subgraph.nodes()]

        # 绘制边
        nx.draw_networkx_edges(subgraph, pos, alpha=0.2, arrows=True, arrowsize=10)

        # 绘制节点
        nodes = nx.draw_networkx_nodes(subgraph, pos,
                                        node_size=node_sizes,
                                        node_color=content_counts,
                                        cmap=plt.cm.YlOrRd,
                                        alpha=0.8)

        # 标签
        labels = {}
        for node in subgraph.nodes():
            user = self.users.get(node, {})
            labels[node] = user.get('name', node)[:6]  # 只显示前6个字符

        nx.draw_networkx_labels(subgraph, pos, labels, font_size=8)

        plt.title("知乎圈子社交网络图谱\n(节点大小=影响力, 颜色深浅=内容数量)", fontsize=14)
        plt.colorbar(nodes, label="内容数量")
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()

        print(f"可视化已保存到: {output_file}")

    def generate_html(self, output_file: str = "social_graph.html", max_nodes: int = 80) -> None:
        """生成交互式 HTML 图谱"""
        print(f"\n生成交互式图谱 ({output_file})...")

        try:
            from pyvis.network import Network
        except ImportError:
            print("请安装 pyvis: pip install pyvis")
            return

        if self.G.number_of_nodes() == 0:
            print("图为空")
            return

        # 限制节点数量
        if self.G.number_of_nodes() > max_nodes:
            pagerank = nx.pagerank(self.G, alpha=0.85)
            top_nodes = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:max_nodes]
            subgraph = self.G.subgraph([n for n, _ in top_nodes])
        else:
            subgraph = self.G

        # 创建 pyvis 网络
        net = Network(height="800px", width="100%", directed=True, notebook=False)
        net.barnes_hut()

        # 添加节点
        pagerank = nx.pagerank(subgraph, alpha=0.85)
        for node in subgraph.nodes():
            user = self.users.get(node, {})
            pr = pagerank.get(node, 0)
            content_count = len(user.get('contents', []))

            # 节点大小和颜色
            size = max(10, pr * 500)
            color = f"rgb({min(255, content_count * 10)}, {max(0, 255 - content_count * 5)}, 100)"

            net.add_node(node,
                        label=user.get('name', node)[:10],
                        title=f"{user.get('name', node)}\n内容: {content_count}\n影响力: {pr:.4f}",
                        size=size,
                        color=color)

        # 添加边
        for u, v in subgraph.edges():
            net.add_edge(u, v, arrows='to')

        # 保存
        net.save_graph(output_file)
        print(f"交互式图谱已保存到: {output_file}")

    def get_stats(self) -> Dict:
        """获取图统计信息"""
        if self.G.number_of_nodes() == 0:
            return {'error': '图为空'}

        return {
            'nodes': self.G.number_of_nodes(),
            'edges': self.G.number_of_edges(),
            'density': nx.density(self.G),
            'avg_clustering': nx.average_clustering(self.G.to_undirected()),
            'components': nx.number_weakly_connected_components(self.G)
        }


# 测试
if __name__ == "__main__":
    graph = SocialGraph("zhihu_data_massive.json")
    graph.build_graph(min_content=2)

    stats = graph.get_stats()
    print(f"\n图统计: {json.dumps(stats, indent=2)}")

    # 关键影响者
    influencers = graph.find_influencers(10)
    print("\nTop 10 关键影响者:")
    for token, score in influencers:
        user = graph.users.get(token, {})
        print(f"  {user.get('name', token)}: {score:.4f}")

    # 社区分析
    communities = graph.analyze_community()
    print(f"\n社区数量: {communities['community_count']}")
    for comm in communities['communities'][:5]:
        print(f"  社区 {comm['id']}: {comm['size']} 人")

    # 生成可视化
    graph.visualize("social_graph.png")
    graph.generate_html("social_graph.html")
