"""
引力拓扑 (Gravity Topology) 主程序
基于空间计量与 A2A 机制的社区暗网发掘系统
"""

import os
import sys
import json
import time
from datetime import datetime

from zhihu_api import ZhihuAPI
from data_collector import DataCollector
from similarity import GravityCalculator
from a2a_dialogue import A2ADialogue
from gravity_topology.config import ZHIHU_COMMUNITY_APP_KEY, ZHIHU_COMMUNITY_APP_SECRET


class GravityTopology:
    """引力拓扑系统主类"""

    def __init__(self, app_key: str, app_secret: str):
        """
        初始化系统

        Args:
            app_key: 知乎用户 token
            app_secret: 应用密钥
        """
        self.api = ZhihuAPI(app_key, app_secret)
        self.collector = DataCollector(self.api)
        self.calculator = None
        self.a2a = None

    def run_pipeline(self, collect_new: bool = True, max_pages: int = 3) -> None:
        """
        运行完整流程

        Args:
            collect_new: 是否采集新数据
            max_pages: 每个圈子最大采集页数
        """
        print("""
╔══════════════════════════════════════════════════════════════╗
║              引力拓扑 (Gravity Topology)                     ║
║      基于空间计量与 A2A 机制的社区暗网发掘系统                  ║
╚══════════════════════════════════════════════════════════════╝
        """)

        start_time = time.time()

        # Step 1: 数据采集
        print("\n" + "=" * 60)
        print("Step 1: 数据采集与清洗")
        print("=" * 60)

        if collect_new:
            self.collector.collect_all_rings(max_pages=max_pages)
            self.collector.save_data("zhihu_data.json")
        else:
            if not self.collector.load_data("zhihu_data.json"):
                print("错误: 无法加载数据文件")
                return

        # Step 2: 引力计算
        print("\n" + "=" * 60)
        print("Step 2: 引力测算")
        print("=" * 60)

        self.calculator = GravityCalculator(self.collector)
        self.calculator.compute_text_similarity()
        self.calculator.compute_behavior_score()
        hidden_pairs = self.calculator.find_hidden_pairs(top_n=10)
        self.calculator.print_hidden_pairs()
        self.calculator.save_results("gravity_results.json")

        # Step 3: A2A 对话
        print("\n" + "=" * 60)
        print("Step 3: A2A 对话生成")
        print("=" * 60)

        self.a2a = A2ADialogue(self.collector)

        # 选择最佳的一对进行对话演示
        if hidden_pairs:
            best_pair = hidden_pairs[0]
            user_a, user_b, gravity = best_pair

            print(f"\n为最佳匹配生成 A2A 对话:")
            print(f"  用户A: {self.a2a.get_user_info(user_a).get('name', user_a)}")
            print(f"  用户B: {self.a2a.get_user_info(user_b).get('name', user_b)}")
            print(f"  引力值: {gravity:.4f}")

            # 生成对话
            dialogue = self.a2a.generate_dialogue(user_a, user_b, rounds=3)

            # 生成报告
            report = self.a2a.generate_gravity_report(user_a, user_b, gravity, dialogue)

            # 打印报告
            print(report)

            # 保存结果
            self.a2a.save_dialogue(dialogue, report, "dialogue_result.json")
        else:
            print("\n未找到隐藏同好对，请尝试增加数据采集量")

        # 完成
        elapsed = time.time() - start_time
        print(f"\n{'=' * 60}")
        print(f"流程完成! 耗时: {elapsed:.2f} 秒")
        print(f"{'=' * 60}")

    def demo_static(self) -> None:
        """
        静态演示模式
        使用模拟数据展示系统能力
        """
        print("""
╔══════════════════════════════════════════════════════════════╗
║              引力拓扑 - 静态演示模式                          ║
╚══════════════════════════════════════════════════════════════╝
        """)

        # 模拟数据
        demo_users = {
            'tech_thinker_01': {
                'token': 'tech_thinker_01',
                'name': '技术思考者',
                'post_count': 15,
                'comment_count': 42,
                'total_likes': 328,
                'contents': [
                    'AI的发展离不开算法的优化和算力的提升',
                    '深度学习模型的可解释性研究至关重要',
                    '从技术角度看，大模型的涌现能力令人惊叹'
                ]
            },
            'human_observer_01': {
                'token': 'human_observer_01',
                'name': '人文观察员',
                'post_count': 23,
                'comment_count': 67,
                'total_likes': 512,
                'contents': [
                    '技术发展需要人文关怀的引导',
                    '数字时代的社交方式正在重塑人际关系',
                    '从哲学角度思考人工智能的伦理边界'
                ]
            },
            'cross_domain_01': {
                'token': 'cross_domain_01',
                'name': '跨界探索者',
                'post_count': 18,
                'comment_count': 55,
                'total_likes': 445,
                'contents': [
                    '创新往往发生在不同学科的交叉点',
                    '技术与人文的平衡是未来发展的关键',
                    '从系统论角度看社区生态的演化'
                ]
            }
        }

        # 创建模拟数据
        self.collector.users = demo_users
        self.a2a = A2ADialogue(self.collector)

        # 生成对话
        print("\n正在生成 Agent 对话...\n")
        dialogue = self.a2a.generate_dialogue(
            'tech_thinker_01',
            'human_observer_01',
            topic="人工智能的未来发展",
            rounds=4
        )

        # 生成报告
        report = self.a2a.generate_gravity_report(
            'tech_thinker_01',
            'human_observer_01',
            0.87,
            dialogue
        )

        print(report)

    def test_api(self) -> None:
        """测试 API 连接"""
        print("\n测试 API 连接...")

        result = self.api.get_ring_detail("2001009660925334090", page_num=1, page_size=5)

        if result.get('status') == 0:
            print("[OK] API 连接成功!")
            data = result.get('data', {})
            ring_info = data.get('ring_info', {})
            print(f"  圈子: {ring_info.get('ring_name')}")
            print(f"  成员: {ring_info.get('membership_num')}")
            print(f"  讨论: {ring_info.get('discussion_num')}")

            contents = data.get('contents', [])
            print(f"\n  最新内容预览:")
            for i, item in enumerate(contents[:3], 1):
                author = item.get('author_name', 'unknown')
                content = item.get('content', '')[:40]
                print(f"  {i}. {author}: {content}")
        else:
            print(f"[ERROR] API 错误: {result.get('msg')}")


def main():
    """主函数"""

    # 解析命令行参数
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    else:
        mode = "demo"

    # 配置：从共享配置模块读取
    APP_KEY = ZHIHU_COMMUNITY_APP_KEY
    APP_SECRET = ZHIHU_COMMUNITY_APP_SECRET

    if mode in {"collect", "test"} and (not APP_KEY or not APP_SECRET):
        print("错误: 请先设置 ZHIHU_COMMUNITY_APP_KEY 和 ZHIHU_COMMUNITY_APP_SECRET 环境变量")
        print("PowerShell 示例:")
        print("  $env:ZHIHU_COMMUNITY_APP_KEY='你的知乎用户token'")
        print("  $env:ZHIHU_COMMUNITY_APP_SECRET='你的知乎应用密钥'")
        return

    # demo/analyze 不需要实时访问知乎 API，可以无凭证运行。
    system = GravityTopology(APP_KEY, APP_SECRET)

    if mode == "collect":
        # 采集模式
        print("运行数据采集模式...")
        system.run_pipeline(collect_new=True, max_pages=3)

    elif mode == "analyze":
        # 分析模式（使用已有数据）
        print("运行分析模式...")
        system.run_pipeline(collect_new=False)

    elif mode == "test":
        # 测试模式
        print("运行测试模式...")
        system.test_api()

    elif mode == "demo":
        # 演示模式
        print("运行演示模式...")
        system.demo_static()

    else:
        print(f"未知模式: {mode}")
        print("可用模式: collect, analyze, test, demo")


if __name__ == "__main__":
    main()
