"""
RAG知识库管理模块 - 基于FAISS向量数据库 (轻量级方案)
"""
import os
import json
import pickle
from datetime import datetime
from typing import List, Dict, Optional
import numpy as np

try:
    import faiss
except ImportError:
    print("❌ 请先安装 faiss: pip install faiss-cpu")
    exit(1)

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from config import Config


class SupplierKnowledgeBase:
    """供应商知识库 - 基于FAISS向量数据库"""

    def __init__(self, persist_directory: str = "data/knowledge_base"):
        """
        初始化知识库

        Args:
            persist_directory: 数据库持久化目录
        """
        self.persist_directory = persist_directory
        self.index_path = os.path.join(persist_directory, "faiss.index")
        self.metadata_path = os.path.join(persist_directory, "metadata.json")

        # 确保目录存在
        os.makedirs(persist_directory, exist_ok=True)

        # 初始化Google Embeddings
        # 使用text-embedding-004（最新稳定版本）
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=Config.GOOGLE_API_KEY
        )

        # 向量维度（text-embedding-004 是 768维）
        self.dimension = 768

        # 加载或创建索引
        self._load_or_create_index()

        print(f"✅ 知识库初始化成功")
        print(f"   存储位置: {persist_directory}")
        print(f"   当前供应商数: {len(self.suppliers)}")

    def _load_or_create_index(self):
        """加载或创建FAISS索引"""

        if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
            # 加载现有索引
            self.index = faiss.read_index(self.index_path)

            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                self.suppliers = json.load(f)

            print(f"   ✅ 加载现有索引: {len(self.suppliers)} 个供应商")
        else:
            # 创建新索引
            self.index = faiss.IndexFlatL2(self.dimension)  # L2距离
            self.suppliers = []

            print(f"   ✅ 创建新索引")

    def add_supplier(self, supplier: Dict) -> bool:
        """
        添加供应商到知识库

        Args:
            supplier: 供应商信息字典

        Returns:
            bool: 是否添加成功
        """
        try:
            # 构建文档内容（用于向量化）
            content = self._build_document_content(supplier)

            # 向量化
            embedding = self.embeddings.embed_query(content)
            embedding_array = np.array([embedding]).astype('float32')

            # 添加到FAISS索引
            self.index.add(embedding_array)

            # 保存元数据
            metadata = self._build_metadata(supplier)
            self.suppliers.append(metadata)

            print(f"  ✅ 已添加: {supplier.get('title', 'Unknown')[:50]}")

            # 持久化
            self._save_index()

            return True

        except Exception as e:
            print(f"  ❌ 添加失败: {e}")
            return False

    def add_suppliers_batch(self, suppliers: List[Dict]) -> int:
        """
        批量添加供应商（优化版）

        Args:
            suppliers: 供应商列表

        Returns:
            int: 成功添加的数量
        """
        print(f"\n📚 批量添加供应商到知识库...")

        success_count = 0
        embeddings_to_add = []
        metadata_to_add = []

        for i, supplier in enumerate(suppliers, 1):
            print(f"  [{i}/{len(suppliers)}]", end=" ")

            try:
                # 构建文档内容
                content = self._build_document_content(supplier)

                # 向量化
                embedding = self.embeddings.embed_query(content)
                embeddings_to_add.append(embedding)

                # 元数据
                metadata = self._build_metadata(supplier)
                metadata_to_add.append(metadata)

                print(f"✅ {supplier.get('title', 'Unknown')[:30]}")
                success_count += 1

            except Exception as e:
                print(f"❌ 失败: {e}")

        # 批量添加到FAISS
        if embeddings_to_add:
            embeddings_array = np.array(embeddings_to_add).astype('float32')
            self.index.add(embeddings_array)
            self.suppliers.extend(metadata_to_add)

            # 持久化
            self._save_index()

        print(f"\n✅ 批量添加完成: {success_count}/{len(suppliers)}")

        return success_count

    def search_suppliers(
            self,
            query: str,
            k: int = 5,
            min_similarity: float = 0.5
    ) -> List[Dict]:
        """
        语义搜索供应商

        Args:
            query: 搜索查询（自然语言）
            k: 返回结果数量
            min_similarity: 最小相似度阈值（0-1，距离转换后）

        Returns:
            List[Dict]: 匹配的供应商列表
        """
        try:
            if len(self.suppliers) == 0:
                return []

            # 查询向量化
            query_embedding = self.embeddings.embed_query(query)
            query_array = np.array([query_embedding]).astype('float32')

            # FAISS搜索（返回距离，不是相似度）
            # L2距离：越小越相似
            distances, indices = self.index.search(query_array, min(k, len(self.suppliers)))

            # 转换为供应商列表
            results = []
            for distance, idx in zip(distances[0], indices[0]):
                if idx < len(self.suppliers):
                    supplier = self.suppliers[idx].copy()

                    # 距离转换为相似度 (0-1)
                    # 使用exp(-distance/10)作为相似度，距离越小相似度越高
                    similarity = np.exp(-distance / 10)
                    supplier["similarity_score"] = round(float(similarity), 3)
                    supplier["distance"] = round(float(distance), 3)

                    # 过滤低相似度
                    if similarity >= min_similarity:
                        results.append(supplier)

            return results

        except Exception as e:
            print(f"❌ 搜索失败: {e}")
            return []

    def get_all_suppliers(self) -> List[Dict]:
        """获取所有供应商"""
        return self.suppliers.copy()

    def get_statistics(self) -> Dict:
        """获取知识库统计信息"""

        # 统计各类别数量
        categories = {}
        statuses = {}

        for supplier in self.suppliers:
            category = supplier.get("category", "未分类")
            status = supplier.get("cooperation_status", "未联系")

            categories[category] = categories.get(category, 0) + 1
            statuses[status] = statuses.get(status, 0) + 1

        return {
            "total_count": len(self.suppliers),
            "categories": categories,
            "cooperation_status": statuses,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def _save_index(self):
        """保存索引到磁盘"""
        try:
            faiss.write_index(self.index, self.index_path)

            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(self.suppliers, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"⚠️  保存索引失败: {e}")

    def _build_document_content(self, supplier: Dict) -> str:
        """构建用于向量化的文档内容"""

        # 提取关键信息
        company_name = supplier.get("title", "")
        category = supplier.get("category", "")
        snippet = supplier.get("snippet", "")
        reason = supplier.get("reason", "")
        match_type = supplier.get("match_type", "")

        # 拼接成自然语言描述
        content_parts = [
            f"公司名称: {company_name}",
            f"类别: {category}",
            f"类型: {match_type}",
            f"描述: {snippet}",
            f"评价: {reason}"
        ]

        content = "\n".join([p for p in content_parts if p])

        return content

    def _build_metadata(self, supplier: Dict) -> Dict:
        """构建元数据"""

        contact = supplier.get("contact", {})

        metadata = {
            "company_name": supplier.get("title", "Unknown"),
            "category": supplier.get("category", "电子产品"),
            "website": supplier.get("link", ""),
            "match_type": supplier.get("match_type", ""),
            "supplier_score": supplier.get("score", 0),
            "contact_person": contact.get("name", ""),
            "email": contact.get("email", ""),
            "phone": contact.get("phone", ""),
            "linkedin": contact.get("linkedin", ""),
            "cooperation_status": "未联系",
            "add_date": datetime.now().strftime("%Y-%m-%d"),
            "source": supplier.get("source", "Google搜索")
        }

        return metadata


# 测试代码
if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    print("=" * 60)
    print("测试供应商知识库 (FAISS版本)")
    print("=" * 60)

    try:
        # 初始化知识库
        kb = SupplierKnowledgeBase()

        # 测试数据
        test_supplier = {
            "title": "Shenzhen Test Electronics Co., Ltd.",
            "link": "https://www.test.com",
            "snippet": "Professional Bluetooth headphone manufacturer with CE certification",
            "match_type": "制造商",
            "score": 90,
            "reason": "专业TWS耳机工厂",
            "category": "消费电子",
            "contact": {
                "name": "John Zhang",
                "title": "Sales Director",
                "email": "john@test.com",
                "phone": "+86-123-4567"
            }
        }

        # 测试添加
        print("\n【测试1: 添加供应商】")
        kb.add_supplier(test_supplier)

        # 测试搜索
        print("\n【测试2: 语义搜索】")
        results = kb.search_suppliers("蓝牙耳机制造商", k=3, min_similarity=0.3)

        print(f"\n找到 {len(results)} 个结果:")
        for i, supplier in enumerate(results, 1):
            print(f"\n{i}. {supplier['company_name']}")
            print(f"   相似度: {supplier['similarity_score']}")
            print(f"   距离: {supplier['distance']}")
            print(f"   邮箱: {supplier['email']}")

        # 测试统计
        print("\n【测试3: 统计信息】")
        stats = kb.get_statistics()
        print(f"\n总供应商数: {stats['total_count']}")
        print(f"类别分布: {stats['categories']}")

        print("\n✅ 所有测试通过！")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()