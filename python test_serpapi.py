"""
测试 SerpAPI 是否正常工作
"""
import os
from dotenv import load_dotenv
from serpapi import GoogleSearch
import json

load_dotenv()


def test_serpapi():
    """测试SerpAPI基本功能"""

    api_key = os.getenv("SERPAPI_KEY")

    if not api_key:
        print("❌ 错误: 未找到 SERPAPI_KEY")
        print("请在 .env 文件中配置 SERPAPI_KEY")
        return

    print(f"📌 API Key (前10位): {api_key[:10]}...")

    # 简单的测试查询
    print("\n" + "=" * 60)
    print("测试 1: 简单搜索")
    print("=" * 60)

    params = {
        "q": "coffee",
        "api_key": api_key,
        "engine": "google"
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()

        # 打印完整响应（用于调试）
        print("\n完整API响应:")
        print(json.dumps(results, indent=2, ensure_ascii=False)[:1000])

        # 检查是否有错误
        if "error" in results:
            print(f"\n❌ API错误: {results['error']}")
            return

        # 检查搜索结果
        if "organic_results" in results:
            print(f"\n✅ 找到 {len(results['organic_results'])} 个结果")
            print("\n前3个结果:")
            for i, result in enumerate(results["organic_results"][:3], 1):
                print(f"{i}. {result.get('title', 'N/A')}")
        else:
            print("\n⚠️  响应中没有 organic_results")
            print("可用的键:", list(results.keys()))

        # 检查配额
        if "search_metadata" in results:
            print(f"\n📊 搜索元数据:")
            print(f"  状态: {results['search_metadata'].get('status', 'N/A')}")
            print(f"  总耗时: {results['search_metadata'].get('total_time_taken', 'N/A')}s")

    except Exception as e:
        print(f"\n❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()

    # 测试2: 中文+英文混合搜索
    print("\n" + "=" * 60)
    print("测试 2: 中英文混合搜索")
    print("=" * 60)

    params2 = {
        "q": "bluetooth headphones manufacturer China",
        "api_key": api_key,
        "engine": "google",
        "num": 5
    }

    try:
        search2 = GoogleSearch(params2)
        results2 = search2.get_dict()

        if "organic_results" in results2:
            print(f"\n✅ 找到 {len(results2['organic_results'])} 个结果")
        else:
            print("\n⚠️  无结果")

    except Exception as e:
        print(f"\n❌ 请求失败: {e}")

    # 检查账户信息
    print("\n" + "=" * 60)
    print("检查账户信息")
    print("=" * 60)
    print("请访问: https://serpapi.com/account")
    print("查看:")
    print("  - API配额使用情况")
    print("  - 当前计划 (免费/付费)")
    print("  - 本月剩余搜索次数")


if __name__ == "__main__":
    test_serpapi()