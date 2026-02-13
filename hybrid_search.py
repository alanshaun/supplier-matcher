"""
混合检索引擎 - 结合本地知识库和Google搜索
"""
from typing import List, Dict, Tuple
from knowledge_base import SupplierKnowledgeBase
from search_tool import create_google_search_tool


class HybridSearchEngine:
    """混合检索引擎 - 本地优先，Google补充"""

    def __init__(self):
        """初始化混合检索引擎"""
        self.knowledge_base = SupplierKnowledgeBase()

    def search(
            self,
            product_info: Dict,
            local_k: int = 5,
            google_k: int = 3,
            min_similarity: float = 0.6
    ) -> Tuple[List[Dict], Dict]:
        """
        混合检索供应商

        Args:
            product_info: 产品信息字典
            local_k: 本地检索数量
            google_k: Google搜索数量
            min_similarity: 最小相似度阈值

        Returns:
            Tuple[List[Dict], Dict]: (合并后的供应商列表, 统计信息)
        """

        print("\n" + "=" * 60)
        print("🔍 混合检索模式")
        print("=" * 60)

        # Step 1: 本地知识库检索
        local_results = self._search_local(product_info, local_k, min_similarity)

        # Step 2: Google搜索补充
        google_results = []
        if len(local_results) < google_k:
            google_results = self._search_google(product_info, google_k)

        # Step 3: 合并去重
        merged_results = self._merge_results(local_results, google_results, google_k)

        # Step 4: 统计信息
        stats = {
            "local_count": len(local_results),
            "google_count": len(google_results),
            "total_count": len(merged_results),
            "sources": {
                "本地知识库": len(local_results),
                "Google搜索": len([r for r in merged_results if r.get("source") == "Google搜索"])
            }
        }

        return merged_results, stats

    def _search_local(
            self,
            product_info: Dict,
            k: int,
            min_similarity: float
    ) -> List[Dict]:
        """从本地知识库检索"""

        print("\n📚 Step 1: 搜索本地知识库...")

        # 构建查询语句
        query = self._build_search_query(product_info)
        print(f"   查询: {query}")

        # 执行搜索
        results = self.knowledge_base.search_suppliers(query, k=k)

        # 过滤低相似度结果
        filtered_results = [
            r for r in results
            if r.get("similarity_score", 0) >= min_similarity
        ]

        print(f"   找到 {len(results)} 个结果")
        print(f"   过滤后 {len(filtered_results)} 个（相似度 >= {min_similarity}）")

        # 显示本地匹配结果
        if filtered_results:
            print(f"\n   【本地匹配】")
            for i, supplier in enumerate(filtered_results[:3], 1):
                print(f"   {i}. {supplier['company_name'][:40]}")
                print(f"      相似度: {supplier['similarity_score']:.2f} | 状态: {supplier['cooperation_status']}")

        return filtered_results

    def _search_google(self, product_info: Dict, k: int) -> List[Dict]:
        """从Google搜索新供应商"""

        print(f"\n🌐 Step 2: Google搜索补充...")
        print(f"   目标: 补充 {k} 家新供应商")

        # 调用原有的Google搜索
        google_results = create_google_search_tool(product_info)

        # 标记来源
        for result in google_results:
            result["source"] = "Google搜索"
            result["similarity_score"] = None  # Google结果没有相似度

        print(f"   ✅ Google搜索完成")

        return google_results[:k]

    def _merge_results(
            self,
            local_results: List[Dict],
            google_results: List[Dict],
            target_count: int
    ) -> List[Dict]:
        """合并本地和Google结果，去重"""

        print(f"\n🔄 Step 3: 合并结果...")

        # 初始化结果列表
        merged = []

        # 添加本地结果（优先）
        for supplier in local_results:
            merged.append({
                "title": supplier.get("company_name"),
                "link": supplier.get("website"),
                "match_type": supplier.get("match_type"),
                "score": supplier.get("score", 0),
                "reason": f"本地知识库匹配（相似度: {supplier.get('similarity_score', 0):.2f}）",
                "contact": {
                    "name": supplier.get("contact_person", ""),
                    "email": supplier.get("email", ""),
                    "phone": supplier.get("phone", ""),
                },
                "source": "本地知识库",
                "cooperation_status": supplier.get("cooperation_status"),
                "similarity_score": supplier.get("similarity_score")
            })

        # 添加Google结果（去重）
        existing_companies = set(r["title"].lower() for r in merged)

        for supplier in google_results:
            company_name = supplier.get("title", "").lower()

            # 跳过重复
            if company_name in existing_companies:
                print(f"   ⏭️  跳过重复: {supplier.get('title')[:30]}...")
                continue

            merged.append(supplier)
            existing_companies.add(company_name)

            # 达到目标数量就停止
            if len(merged) >= target_count:
                break

        print(f"   合并后总数: {len(merged)}")

        return merged[:target_count]

    def _build_search_query(self, product_info: Dict) -> str:
        """构建搜索查询语句"""

        product_name = product_info.get("产品名称", "")
        category = product_info.get("产品类别", "")
        specs = product_info.get("核心规格", "")

        # 组合查询
        query_parts = []

        if product_name:
            query_parts.append(product_name)

        if category:
            query_parts.append(category)

        if specs:
            query_parts.append(specs)

        query = " ".join(query_parts)

        return query if query else "制造商 供应商"

    def save_to_knowledge_base(self, suppliers: List[Dict]) -> int:
        """将搜索结果保存到知识库"""

        print("\n" + "=" * 60)
        print("💾 保存到知识库")
        print("=" * 60)

        # 只保存Google新搜索的结果
        new_suppliers = [
            s for s in suppliers
            if s.get("source") == "Google搜索"
        ]

        if not new_suppliers:
            print("   没有新供应商需要保存")
            return 0

        print(f"   准备保存 {len(new_suppliers)} 家新供应商...")

        # 批量添加
        count = self.knowledge_base.add_suppliers_batch(new_suppliers)

        return count


# 测试代码
if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    print("=" * 60)
    print("测试混合检索引擎")
    print("=" * 60)

    # 测试产品
    test_product = {
        "产品名称": "Bluetooth Headphones",
        "产品类别": "Consumer Electronics",
        "核心规格": "TWS Wireless Bluetooth 5.0",
        "目标市场": "欧美市场",
        "特殊要求": "CE认证"
    }

    try:
        # 初始化引擎
        engine = HybridSearchEngine()

        # 执行混合检索
        results, stats = engine.search(
            product_info=test_product,
            local_k=5,
            google_k=3,
            min_similarity=0.5
        )

        # 显示结果
        print("\n" + "=" * 60)
        print("🎯 检索结果")
        print("=" * 60)

        print(f"\n统计:")
        print(f"  本地知识库: {stats['local_count']} 个")
        print(f"  Google搜索: {stats['google_count']} 个")
        print(f"  合并后总数: {stats['total_count']} 个")

        print(f"\n供应商列表:")
        for i, supplier in enumerate(results, 1):
            print(f"\n{i}. {supplier['title'][:50]}")
            print(f"   来源: {supplier['source']}")
            if supplier.get('similarity_score'):
                print(f"   相似度: {supplier['similarity_score']:.2f}")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()