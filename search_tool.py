"""
搜索工具 - 使用Google搜索供应商并评分 (增强调试版本)
"""
from serpapi import GoogleSearch
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from config import Config
import json


def create_google_search_tool(product_info: dict) -> list:
    """
    创建Google搜索工具并执行搜索

    Args:
        product_info: 产品信息字典

    Returns:
        list: 搜索到的供应商列表
    """
    # 1. 生成搜索查询词
    query = _generate_search_query(product_info)

    # 2. 执行搜索
    suppliers = _search_google(query)

    # 如果没结果，尝试简化搜索
    if not suppliers:
        print("\n⚠️  首次搜索无结果，尝试简化搜索词...")
        query_simple = _generate_simple_query(product_info)
        suppliers = _search_google(query_simple)

    # 3. 使用LLM评分排序
    if suppliers:
        ranked_suppliers = _rank_suppliers_with_llm(suppliers, product_info)
        return ranked_suppliers[:Config.TOP_N_SUPPLIERS]

    print("\n💡 建议:")
    print("  1. 检查SerpAPI配额: https://serpapi.com/account")
    print("  2. 确认API Key正确配置在 .env 文件中")
    print("  3. 尝试运行: python test_serpapi.py")

    return []


def _generate_search_query(product_info: dict) -> str:
    """生成优化的搜索查询词"""

    product_name = product_info.get('产品名称', '')
    category = product_info.get('产品类别', '')

    # 构建搜索词
    query_parts = []

    # 优先使用英文产品名（如果有）
    if product_name and product_name != '未提供':
        # 移除中文，只保留英文和数字
        english_part = ''.join(c for c in product_name if ord(c) < 128 or c.isspace())
        if english_part.strip():
            query_parts.append(english_part.strip())
        else:
            query_parts.append(product_name)

    if category and category != '未提供':
        # 移除中文
        english_cat = ''.join(c for c in category if ord(c) < 128 or c.isspace())
        if english_cat.strip():
            query_parts.append(english_cat.strip())

    # 添加供应商相关关键词
    query_parts.extend(['manufacturer', 'supplier', 'China'])

    query = ' '.join(query_parts)

    print(f"🔍 生成的搜索词: {query}")
    return query


def _generate_simple_query(product_info: dict) -> str:
    """生成简化的搜索查询词"""

    product_name = product_info.get('产品名称', '')

    # 只用产品名 + manufacturer
    english_name = ''.join(c for c in product_name if ord(c) < 128 or c.isspace()).strip()

    if english_name:
        query = f"{english_name} manufacturer"
    else:
        # 如果没有英文，用类别
        category = product_info.get('产品类别', '')
        english_cat = ''.join(c for c in category if ord(c) < 128 or c.isspace()).strip()
        query = f"{english_cat} manufacturer China" if english_cat else "manufacturer China"

    print(f"🔍 简化搜索词: {query}")
    return query


def _search_google(query: str) -> list:
    """使用SerpAPI搜索Google"""

    print(f"🌐 正在搜索Google...")

    try:
        params = {
            "q": query,
            "api_key": Config.SERPAPI_KEY,
            "engine": "google",
            "num": Config.SEARCH_NUM_RESULTS,
            "gl": "us",
            "hl": "en"
        }

        print(f"📋 搜索参数:")
        print(f"  查询词: {params['q']}")
        print(f"  结果数: {params['num']}")
        print(f"  地区: {params['gl']}")
        print(f"  语言: {params['hl']}")

        search = GoogleSearch(params)
        results = search.get_dict()

        # 调试信息：打印API响应的键
        print(f"\n📊 API响应包含的键: {list(results.keys())}")

        # 检查错误
        if "error" in results:
            print(f"\n❌ SerpAPI错误: {results['error']}")

            # 检查是否是配额问题
            if "credit" in results['error'].lower():
                print("\n💡 配额用完！解决方案:")
                print("  1. 等待每月1号配额重置")
                print("  2. 访问 https://serpapi.com/account 查看使用情况")
                print("  3. 升级付费计划")

            return []

        # 检查搜索元数据
        if "search_metadata" in results:
            status = results["search_metadata"].get("status", "unknown")
            print(f"  搜索状态: {status}")

            if status != "Success":
                print(f"⚠️  搜索状态异常: {status}")

        # 提取有机搜索结果
        suppliers = []

        if "organic_results" in results:
            for i, result in enumerate(results["organic_results"]):
                suppliers.append({
                    "position": i + 1,
                    "title": result.get("title", ""),
                    "link": result.get("link", ""),
                    "snippet": result.get("snippet", ""),
                    "displayed_link": result.get("displayed_link", "")
                })

            print(f"✅ 找到 {len(suppliers)} 个搜索结果")

            # 显示前3个结果标题
            if suppliers:
                print("\n前3个结果:")
                for i, s in enumerate(suppliers[:3], 1):
                    print(f"  {i}. {s['title'][:60]}...")
        else:
            print(f"⚠️  响应中没有 organic_results")
            print(f"   可用的键: {list(results.keys())}")

            # 尝试其他可能的结果字段
            if "related_searches" in results:
                print(f"   发现 {len(results['related_searches'])} 个相关搜索")

        return suppliers

    except Exception as e:
        print(f"❌ 搜索失败: {e}")
        print("\n详细错误:")
        import traceback
        traceback.print_exc()

        print("\n💡 排查建议:")
        print("  1. 检查网络连接")
        print("  2. 验证 SERPAPI_KEY 是否正确")
        print("  3. 运行 python test_serpapi.py 测试API")

        return []


def _rank_suppliers_with_llm(suppliers: list, product_info: dict) -> list:
    """使用Gemini对供应商进行智能评分"""

    print("\n🤖 使用Gemini进行智能评分...")

    try:
        llm = ChatGoogleGenerativeAI(
            model=Config.GEMINI_MODEL,
            google_api_key=Config.GOOGLE_API_KEY,
            temperature=0.2
        )
    except Exception as e:
        print(f"❌ Gemini初始化失败: {e}")
        return _fallback_ranking(suppliers)

    prompt = PromptTemplate(
        input_variables=["product_info", "suppliers"],
        template="""你是一个专业的B2B供应商评估专家，擅长为跨境电商匹配最佳供应商。

**产品需求:**
{product_info}

**候选供应商列表:**
{suppliers}

**评估任务:**
请根据以下标准对每个供应商进行评分（0-100分）：

1. **类型匹配** (30分): 是否是制造商/工厂（而非贸易公司、平台）
2. **产品相关性** (30分): 产品类别、专业领域是否匹配
3. **可信度** (20分): 公司规模、品牌知名度、网站专业度
4. **合作潜力** (20分): 是否有出口经验、认证、响应能力

**输出格式要求:**
请只返回JSON数组，不要其他文字。格式如下：

[
  {{
    "title": "公司完整名称",
    "link": "网站链接",
    "score": 85,
    "reason": "简短的评分理由（1-2句话）",
    "match_type": "制造商/贸易商/平台"
  }}
]

重要：只返回JSON，不要markdown标记，不要其他解释。"""
    )

    # 准备数据
    product_str = json.dumps(product_info, ensure_ascii=False, indent=2)
    suppliers_str = json.dumps(suppliers, ensure_ascii=False, indent=2)

    try:
        # 格式化prompt
        formatted_prompt = prompt.format(
            product_info=product_str,
            suppliers=suppliers_str
        )

        print("  正在调用Gemini API...")

        # 调用LLM
        response = llm.invoke(formatted_prompt)

        # 提取内容
        if hasattr(response, 'content'):
            content = response.content.strip()
        else:
            content = str(response).strip()

        print("  ✓ API调用成功")

        # 清理JSON
        content = _clean_json_response(content)

        # 解析JSON
        ranked = json.loads(content)

        # 验证并排序
        if isinstance(ranked, list) and len(ranked) > 0:
            ranked.sort(key=lambda x: x.get('score', 0), reverse=True)
            print(f"✅ 评分完成，共评估 {len(ranked)} 个供应商")
            return ranked
        else:
            print("⚠️  返回格式不正确，使用降级方案")
            return _fallback_ranking(suppliers)

    except json.JSONDecodeError as e:
        print(f"⚠️  JSON解析失败: {e}")
        if 'content' in locals():
            print(f"原始返回前200字符: {content[:200]}...")
        return _fallback_ranking(suppliers)

    except Exception as e:
        print(f"❌ 评分过程出错: {e}")
        import traceback
        traceback.print_exc()
        return _fallback_ranking(suppliers)


def _clean_json_response(content: str) -> str:
    """清理LLM返回的JSON内容"""

    # 移除markdown代码块标记
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]

    if content.endswith("```"):
        content = content[:-3]

    # 移除前后空白
    content = content.strip()

    return content


def _fallback_ranking(suppliers: list) -> list:
    """降级方案：简单返回前3个结果"""

    print("  使用降级排序方案...")
    return [{
        "title": s["title"],
        "link": s["link"],
        "score": 60 - i * 5,
        "reason": "基于搜索排名",
        "match_type": "待确认"
    } for i, s in enumerate(suppliers[:3])]


if __name__ == "__main__":
    # 测试搜索功能

    test_product = {
        "产品名称": "Bluetooth Headphones",
        "产品类别": "Consumer Electronics",
        "核心规格": "TWS Wireless Bluetooth 5.0",
        "目标市场": "欧美市场",
        "特殊要求": "需要CE认证"
    }

    try:
        print("=" * 60)
        print("测试搜索工具")
        print("=" * 60)

        # 验证配置
        Config.validate()

        # 执行搜索
        top_suppliers = create_google_search_tool(test_product)

        if top_suppliers:
            print("\n" + "=" * 60)
            print(f"🏆 Top {len(top_suppliers)} 推荐供应商:")
            print("=" * 60)

            for i, supplier in enumerate(top_suppliers, 1):
                print(f"\n【第 {i} 名】")
                print(f"公司: {supplier.get('title', 'N/A')}")
                print(f"类型: {supplier.get('match_type', 'N/A')}")
                print(f"评分: {supplier.get('score', 0)}/100")
                print(f"理由: {supplier.get('reason', 'N/A')}")
                print(f"链接: {supplier.get('link', 'N/A')}")
        else:
            print("\n❌ 未找到供应商")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()