"""
主程序 - 供应商智能匹配系统 v3.0 完整版
功能: PDF解析 + RAG知识库 + 混合检索 + 联系人挖掘
"""
import os
import sys
from config import Config
from rag_engine import process_pdf_to_retriever
from hybrid_search import HybridSearchEngine

# 导入联系人查找模块
sys.path.append(os.path.dirname(__file__))
from contact_finder.contact_scraper import batch_find_contacts


def print_header(text: str):
    """打印美化的标题"""
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60)


def print_product_info(product_info: dict):
    """打印产品信息"""
    print("\n📋 提取的产品信息:")
    print("-" * 60)
    for key, value in product_info.items():
        print(f"  • {key}: {value}")
    print("-" * 60)


def print_suppliers_with_contacts(suppliers: list):
    """打印供应商结果（含联系人和来源）"""
    print_header(f"🎯 最终结果: Top {len(suppliers)} 推荐供应商")

    for i, supplier in enumerate(suppliers, 1):
        print(f"\n┌─ 【第 {i} 名】" + "─" * 50)
        print(f"│ 🏢 公司名称: {supplier.get('title', 'N/A')}")

        # 显示来源标识
        source = supplier.get('source', 'Google搜索')
        source_emoji = "📚" if source == "本地知识库" else "🌐"
        print(f"│ {source_emoji} 数据来源: {source}")

        # 如果是本地知识库，显示额外信息
        if source == "本地知识库":
            similarity = supplier.get('similarity_score', 0)
            status = supplier.get('cooperation_status', '未联系')
            print(f"│ 📊 相似度: {similarity:.2f}")
            print(f"│ 🤝 合作状态: {status}")

        print(f"│ 🏭 公司类型: {supplier.get('match_type', 'N/A')}")
        print(f"│ ⭐ 匹配评分: {supplier.get('score', 0)}/100")
        print(f"│ 💡 推荐理由: {supplier.get('reason', 'N/A')}")
        print(f"│ 🔗 官网链接: {supplier.get('link', 'N/A')}")

        # 显示联系人信息
        if 'contact' in supplier and supplier['contact']:
            contact = supplier['contact']
            print(f"│")
            print(f"│ 👤 联系人信息:")

            name = contact.get('name', '未找到')
            title = contact.get('title', '未找到')
            email = contact.get('email', '未找到')

            print(f"│   • 姓名: {name}")
            print(f"│   • 职位: {title}")
            print(f"│   • 邮箱: {email}")

            if contact.get('phone') and contact.get('phone') != '未找到':
                print(f"│   • 电话: {contact.get('phone')}")

            if contact.get('linkedin') and contact.get('linkedin') != '未找到':
                print(f"│   • LinkedIn: {contact.get('linkedin')}")

            # 可信度指示
            if 'confidence' in contact:
                confidence = contact.get('confidence', 'low')
                confidence_emoji = "🟢" if confidence == "high" else "🟡" if confidence == "medium" else "🔴"
                print(f"│   • 信息可信度: {confidence_emoji} {confidence}")

        print(f"└" + "─" * 59)


def run_complete_pipeline(pdf_path: str, enable_contact_search: bool = True):
    """
    运行完整的销售线索生成流程

    Args:
        pdf_path: 产品PDF路径
        enable_contact_search: 是否启用联系人查找
    """

    print_header("🚀 跨境电商供应商智能匹配系统 v3.0")
    print("✨ 功能: RAG知识库 + 混合检索 + 联系人挖掘")

    # ============================================================
    # 步骤1: 解析PDF
    # ============================================================
    print_header("第一步: 解析产品PDF")

    try:
        product_info = process_pdf_to_retriever(pdf_path)
        print_product_info(product_info)
    except Exception as e:
        print(f"❌ PDF解析失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # ============================================================
    # 步骤2: 混合检索（RAG + Google）
    # ============================================================
    print_header("第二步: 混合检索供应商（本地知识库 + Google）")

    try:
        # 初始化混合检索引擎
        search_engine = HybridSearchEngine()

        # 执行混合检索
        top_suppliers, search_stats = search_engine.search(
            product_info=product_info,
            local_k=5,  # 本地检索5个
            google_k=3,  # Google补充3个，最终Top 3
            min_similarity=0.5  # 最小相似度0.5
        )

        if not top_suppliers:
            print("❌ 未找到合适的供应商")
            return

        # 显示检索统计
        print(f"\n✅ 检索完成")
        print(f"   📚 本地知识库: {search_stats['local_count']} 个")
        print(f"   🌐 Google搜索: {search_stats['google_count']} 个")
        print(f"   📊 合并后总数: {search_stats['total_count']} 个")

    except Exception as e:
        print(f"❌ 供应商检索失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # ============================================================
    # 步骤3: 查找联系人（可选）
    # ============================================================
    if enable_contact_search:
        print_header("第三步: 查找联系人信息")

        # 检查哪些供应商需要查找联系人
        suppliers_need_contact = []
        for s in top_suppliers:
            # 检查是否已有有效联系人
            has_valid_contact = False
            if s.get('contact'):
                contact = s['contact']
                email = contact.get('email', '')
                if email and email != '未找到' and '@' in email:
                    has_valid_contact = True

            if not has_valid_contact:
                suppliers_need_contact.append(s)

        if suppliers_need_contact:
            print(f"\n💡 发现 {len(suppliers_need_contact)} 家公司需要查找联系人")
            print(f"   预计消耗: {len(suppliers_need_contact) * 2} 次SerpAPI搜索")

            choice = input("\n是否继续查找联系人？(y/n，默认y): ").strip().lower()

            if choice == '' or choice == 'y':
                try:
                    # 只对需要的供应商查找联系人
                    enriched = batch_find_contacts(suppliers_need_contact)

                    # 更新原列表
                    enriched_dict = {s['title']: s for s in enriched}
                    for s in top_suppliers:
                        if s['title'] in enriched_dict:
                            s['contact'] = enriched_dict[s['title']].get('contact', {})

                except Exception as e:
                    print(f"⚠️  联系人查找失败: {e}")
                    print("将继续显示供应商信息（部分可能缺少联系人）")
            else:
                print("⏭️  跳过联系人查找")
        else:
            print("\n✅ 所有供应商已有联系信息（来自知识库）")

    # ============================================================
    # 步骤4: 展示结果
    # ============================================================
    print_suppliers_with_contacts(top_suppliers)

    # ============================================================
    # 步骤5: 保存到知识库
    # ============================================================
    print_header("第四步: 保存到知识库")

    try:
        saved_count = search_engine.save_to_knowledge_base(top_suppliers)

        if saved_count > 0:
            print(f"\n✅ 已保存 {saved_count} 家新供应商到知识库")
            print(f"   💡 下次搜索相似产品时会优先推荐")
        else:
            print(f"\n💡 本次无新供应商需要保存（都已在知识库中）")

    except Exception as e:
        print(f"⚠️  保存失败: {e}")

    print("\n" + "=" * 60)
    print("✅ 分析完成！")
    print("=" * 60)

    # ============================================================
    # 可选: 保存结果到文件
    # ============================================================
    save = input("\n是否保存结果到文件？(y/n): ").strip().lower()
    if save == 'y':
        save_results(product_info, top_suppliers)


def save_results(product_info: dict, suppliers: list):
    """保存结果到文本文件"""

    filename = "data/supplier_results.txt"

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("供应商匹配结果报告\n")
            f.write("功能: RAG知识库 + 混合检索 + 联系人挖掘\n")
            f.write("=" * 60 + "\n\n")

            # 产品信息
            f.write("【产品信息】\n")
            for key, value in product_info.items():
                f.write(f"{key}: {value}\n")

            # 推荐供应商
            f.write("\n" + "=" * 60 + "\n")
            f.write("【推荐供应商】\n")
            f.write("=" * 60 + "\n\n")

            for i, supplier in enumerate(suppliers, 1):
                f.write(f"第 {i} 名:\n")
                f.write(f"  公司名称: {supplier.get('title', 'N/A')}\n")
                f.write(f"  数据来源: {supplier.get('source', 'N/A')}\n")
                f.write(f"  公司类型: {supplier.get('match_type', 'N/A')}\n")
                f.write(f"  匹配评分: {supplier.get('score', 0)}/100\n")
                f.write(f"  推荐理由: {supplier.get('reason', 'N/A')}\n")
                f.write(f"  官网链接: {supplier.get('link', 'N/A')}\n")

                # 本地知识库额外信息
                if supplier.get('source') == "本地知识库":
                    f.write(f"  相似度: {supplier.get('similarity_score', 0):.2f}\n")
                    f.write(f"  合作状态: {supplier.get('cooperation_status', '未联系')}\n")

                # 联系人信息
                if 'contact' in supplier and supplier['contact']:
                    contact = supplier['contact']
                    f.write(f"\n  联系人信息:\n")
                    f.write(f"    姓名: {contact.get('name', '未找到')}\n")
                    f.write(f"    职位: {contact.get('title', '未找到')}\n")
                    f.write(f"    邮箱: {contact.get('email', '未找到')}\n")
                    f.write(f"    电话: {contact.get('phone', '未找到')}\n")
                    if contact.get('linkedin'):
                        f.write(f"    LinkedIn: {contact.get('linkedin')}\n")
                    if contact.get('confidence'):
                        f.write(f"    可信度: {contact.get('confidence')}\n")

                f.write("\n" + "-" * 60 + "\n\n")

        print(f"✅ 结果已保存到: {filename}")

    except Exception as e:
        print(f"⚠️  保存失败: {e}")


def show_knowledge_base_stats():
    """显示知识库统计信息"""

    try:
        from knowledge_base import SupplierKnowledgeBase

        kb = SupplierKnowledgeBase()
        stats = kb.get_statistics()

        print_header("📊 知识库统计")

        print(f"\n📚 总供应商数: {stats['total_count']}")

        if stats['categories']:
            print(f"\n📂 类别分布:")
            for category, count in sorted(stats['categories'].items(), key=lambda x: x[1], reverse=True):
                print(f"  • {category}: {count} 家")

        if stats['cooperation_status']:
            print(f"\n🤝 合作状态:")
            for status, count in stats['cooperation_status'].items():
                print(f"  • {status}: {count} 家")

        print(f"\n⏰ 最后更新: {stats['last_updated']}")

        # 显示最近添加的供应商
        all_suppliers = kb.get_all_suppliers()
        if all_suppliers:
            print(f"\n📋 最近添加的供应商 (前5个):")
            for i, s in enumerate(all_suppliers[-5:][::-1], 1):
                print(f"  {i}. {s['company_name'][:40]}")
                print(f"     日期: {s['add_date']} | 状态: {s['cooperation_status']}")

    except Exception as e:
        print(f"❌ 获取统计失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主函数"""

    # 验证配置
    try:
        Config.validate()
    except ValueError as e:
        print("❌ 配置错误:")
        print(e)
        print("\n请检查 .env 文件中的API Keys配置")
        return

    # 显示菜单
    print("\n" + "=" * 60)
    print("🚀 跨境电商供应商智能匹配系统 v3.0")
    print("=" * 60)
    print("\n功能清单:")
    print("  ✅ PDF解析 - 自动提取产品信息")
    print("  ✅ RAG知识库 - 记住历史供应商")
    print("  ✅ 混合检索 - 本地优先，Google补充")
    print("  ✅ 联系人挖掘 - 自动查找邮箱/电话")

    print("\n请选择功能:")
    print("  1. 分析新产品（完整流程）")
    print("  2. 查看知识库统计")
    print("  3. 退出")

    choice = input("\n请输入选项 (1-3): ").strip()

    if choice == "2":
        show_knowledge_base_stats()
        return

    elif choice == "3":
        print("👋 再见！")
        return

    # 默认选项1：分析产品
    default_pdf = "data/product.pdf"

    print("\n" + "=" * 60)
    print("📁 请输入产品PDF路径")
    pdf_path = input(f"   (直接回车使用默认: {default_pdf}): ").strip()

    if not pdf_path:
        pdf_path = default_pdf

    # 检查文件是否存在
    if not os.path.exists(pdf_path):
        print(f"\n❌ 文件不存在: {pdf_path}")
        print("\n💡 提示:")
        print("  1. 请将产品PDF放到 data/ 文件夹")
        print("  2. 或者输入完整的文件路径")
        return

    # 运行完整流程
    run_complete_pipeline(pdf_path, enable_contact_search=True)


if __name__ == "__main__":
    main()