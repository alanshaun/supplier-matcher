"""
Streamlit Web界面 - 供应商智能匹配系统
"""
import streamlit as st
import sys
import os
from pathlib import Path
import tempfile
import pandas as pd
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from rag_engine import process_pdf_to_retriever
from hybrid_search import HybridSearchEngine
from contact_finder.contact_scraper import batch_find_contacts

# ============================================================
# 页面配置
# ============================================================
st.set_page_config(
    page_title="供应商智能匹配系统",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# 自定义CSS样式
# ============================================================
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
    }
    .supplier-card {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 5px solid #1f77b4;
    }
    .metric-card {
        background-color: #e8f4f8;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# Session State 初始化
# ============================================================
if 'product_info' not in st.session_state:
    st.session_state.product_info = None

if 'suppliers' not in st.session_state:
    st.session_state.suppliers = None

if 'search_stats' not in st.session_state:
    st.session_state.search_stats = None

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# ============================================================
# 主标题
# ============================================================
st.markdown('<h1 class="main-header">🚀 跨境电商供应商智能匹配系统</h1>', unsafe_allow_html=True)

st.markdown("""
<div style="text-align: center; color: #666; margin-bottom: 2rem;">
    <p>✨ 功能: PDF解析 | RAG知识库 | 混合检索 | 联系人挖掘</p>
</div>
""", unsafe_allow_html=True)

# ============================================================
# 侧边栏 - 配置和统计
# ============================================================
with st.sidebar:
    st.header("⚙️ 系统配置")

    # 验证API配置
    try:
        Config.validate()
        st.success("✅ API配置正常")
    except ValueError as e:
        st.error(f"❌ 配置错误: {e}")
        st.stop()

    st.divider()

    # 知识库统计
    st.header("📊 知识库统计")

    try:
        from knowledge_base import SupplierKnowledgeBase

        kb = SupplierKnowledgeBase()
        stats = kb.get_statistics()

        col1, col2 = st.columns(2)
        with col1:
            st.metric("总供应商", stats['total_count'])
        with col2:
            cooperation_count = stats['cooperation_status'].get('已合作', 0)
            st.metric("已合作", cooperation_count)

        if stats['categories']:
            st.write("**类别分布:**")
            for cat, count in list(stats['categories'].items())[:3]:
                st.write(f"• {cat}: {count}")

    except Exception as e:
        st.warning(f"无法加载统计: {e}")

    st.divider()

    # 高级设置
    with st.expander("🔧 高级设置"):
        enable_contact_search = st.checkbox("启用联系人查找", value=True)
        min_similarity = st.slider("最小相似度阈值", 0.0, 1.0, 0.5, 0.05)
        local_k = st.number_input("本地检索数量", 1, 10, 5)
        google_k = st.number_input("Google搜索数量", 1, 10, 3)

# ============================================================
# 主界面 - Tab布局
# ============================================================
tab1, tab2, tab3 = st.tabs(["📤 上传分析", "💬 对话追问", "📊 知识库浏览"])

# ============================================================
# Tab 1: 上传分析
# ============================================================
with tab1:
    st.header("📤 上传产品PDF")

    # 文件上传
    uploaded_file = st.file_uploader(
        "选择产品PDF文件",
        type=['pdf'],
        help="上传产品说明书、规格书等PDF文件"
    )

    if uploaded_file is not None:
        # 显示文件信息
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info(f"📄 文件名: {uploaded_file.name}")
        with col2:
            st.info(f"📊 大小: {uploaded_file.size / 1024:.1f} KB")
        with col3:
            st.info(f"📅 上传时间: {datetime.now().strftime('%H:%M:%S')}")

        # 开始分析按钮
        if st.button("🚀 开始分析", type="primary", use_container_width=True):

            # 保存上传的文件到临时目录
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name

            try:
                # ============================================================
                # 步骤1: 解析PDF
                # ============================================================
                with st.status("🔄 正在处理...", expanded=True) as status:
                    st.write("📄 第一步: 解析PDF...")

                    product_info = process_pdf_to_retriever(tmp_path)
                    st.session_state.product_info = product_info

                    st.success("✅ PDF解析完成")

                    # ============================================================
                    # 步骤2: 混合检索
                    # ============================================================
                    st.write("🔍 第二步: 智能检索供应商...")

                    search_engine = HybridSearchEngine()
                    suppliers, search_stats = search_engine.search(
                        product_info=product_info,
                        local_k=local_k,
                        google_k=google_k,
                        min_similarity=min_similarity
                    )

                    st.session_state.search_stats = search_stats

                    st.success(f"✅ 找到 {len(suppliers)} 个匹配供应商")

                    # ============================================================
                    # 步骤3: 联系人查找
                    # ============================================================
                    if enable_contact_search:
                        st.write("👤 第三步: 查找联系人...")

                        # 检查哪些需要查找
                        needs_contact = [
                            s for s in suppliers
                            if not s.get('contact') or not s['contact'].get('email') or s['contact']['email'] == '未找到'
                        ]

                        if needs_contact:
                            st.write(f"   需要查找 {len(needs_contact)} 家公司的联系人")
                            enriched = batch_find_contacts(needs_contact)

                            # 更新
                            enriched_dict = {s['title']: s for s in enriched}
                            for s in suppliers:
                                if s['title'] in enriched_dict:
                                    s['contact'] = enriched_dict[s['title']].get('contact', {})

                        st.success("✅ 联系人查找完成")

                    # ============================================================
                    # 步骤4: 保存到知识库
                    # ============================================================
                    st.write("💾 第四步: 保存到知识库...")

                    saved = search_engine.save_to_knowledge_base(suppliers)
                    if saved > 0:
                        st.success(f"✅ 已保存 {saved} 家新供应商")

                    st.session_state.suppliers = suppliers

                    status.update(label="✅ 分析完成！", state="complete")

                # 清理临时文件
                os.unlink(tmp_path)

            except Exception as e:
                st.error(f"❌ 分析失败: {e}")
                import traceback

                st.code(traceback.format_exc())

    # ============================================================
    # 显示结果
    # ============================================================
    if st.session_state.product_info:
        st.divider()
        st.subheader("📋 产品信息")

        # 产品信息卡片
        info_cols = st.columns(2)
        for i, (key, value) in enumerate(st.session_state.product_info.items()):
            with info_cols[i % 2]:
                st.markdown(f"**{key}:** {value}")

    if st.session_state.suppliers:
        st.divider()
        st.subheader("🏆 推荐供应商")

        # 统计信息
        if st.session_state.search_stats:
            cols = st.columns(3)
            with cols[0]:
                st.metric("本地知识库", st.session_state.search_stats['local_count'])
            with cols[1]:
                st.metric("Google搜索", st.session_state.search_stats['google_count'])
            with cols[2]:
                st.metric("总计", st.session_state.search_stats['total_count'])

        st.markdown("---")

        # 供应商卡片
        for i, supplier in enumerate(st.session_state.suppliers, 1):
            with st.container():
                col1, col2 = st.columns([3, 1])

                with col1:
                    # 公司名称和来源
                    source = supplier.get('source', 'Google搜索')
                    source_emoji = "📚" if source == "本地知识库" else "🌐"

                    st.markdown(f"### {i}. {source_emoji} {supplier.get('title', 'N/A')}")

                    # 基本信息
                    st.write(f"**类型:** {supplier.get('match_type', 'N/A')}")
                    st.write(f"**网站:** {supplier.get('link', 'N/A')}")
                    st.write(f"**理由:** {supplier.get('reason', 'N/A')}")

                    # 本地知识库额外信息
                    if source == "本地知识库":
                        st.write(f"**相似度:** {supplier.get('similarity_score', 0):.2f}")
                        st.write(f"**状态:** {supplier.get('cooperation_status', '未联系')}")

                with col2:
                    # 评分
                    score = supplier.get('score', 0)
                    st.metric("匹配度", f"{score}/100", delta=None)

                    # 联系人信息
                    if supplier.get('contact'):
                        contact = supplier['contact']
                        with st.expander("👤 联系人"):
                            st.write(f"**姓名:** {contact.get('name', '未找到')}")
                            st.write(f"**职位:** {contact.get('title', '未找到')}")
                            st.write(f"**邮箱:** {contact.get('email', '未找到')}")
                            if contact.get('phone'):
                                st.write(f"**电话:** {contact.get('phone')}")

                st.markdown("---")

        # 下载按钮
        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            # 生成Excel
            if st.button("📥 下载Excel报告", use_container_width=True):
                excel_file = generate_excel_report(
                    st.session_state.product_info,
                    st.session_state.suppliers
                )

                st.download_button(
                    label="💾 下载",
                    data=excel_file,
                    file_name=f"supplier_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        with col2:
            # 清空结果
            if st.button("🔄 开始新的分析", use_container_width=True):
                st.session_state.product_info = None
                st.session_state.suppliers = None
                st.session_state.search_stats = None
                st.rerun()

# ============================================================
# Tab 2: 对话追问
# ============================================================
with tab2:
    st.header("💬 智能对话")

    if not st.session_state.suppliers:
        st.info("💡 请先在「上传分析」标签页上传PDF并完成分析")

    else:
        st.write("基于当前结果，你可以追问：")


        # 快捷问题
        quick_questions = [
            "找更大的公司",
            "只要制造商，不要贸易商",
            "有CE认证的",
            "深圳的公司",
        ]

        cols = st.columns(4)
        for i, q in enumerate(quick_questions):
            with cols[i]:
                if st.button(q, use_container_width=True):
                    st.session_state.chat_history.append({
                        "role": "user",
                        "content": q
                    })

        # 聊天输入
        user_input = st.chat_input("输入你的问题...")

        if user_input:
            st.session_state.chat_history.append({
                "role": "user",
                "content": user_input
            })

            # 这里可以用LLM处理追问
            # 简化版：直接显示提示
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": f"收到你的问题：「{user_input}」\n\n💡 此功能正在开发中，将支持智能过滤和重新搜索。"
            })

        # 显示对话历史
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

# ============================================================
# Tab 3: 知识库浏览
# ============================================================
with tab3:
    st.header("📊 知识库浏览")

    try:
        from knowledge_base import SupplierKnowledgeBase

        kb = SupplierKnowledgeBase()

        all_suppliers = kb.get_all_suppliers()

        if all_suppliers:
            # 转换为DataFrame
            df = pd.DataFrame(all_suppliers)

            # 筛选器
            col1, col2 = st.columns(2)
            with col1:
                categories = df['category'].unique().tolist()
                selected_cat = st.multiselect("筛选类别", categories, default=categories)

            with col2:
                statuses = df['cooperation_status'].unique().tolist()
                selected_status = st.multiselect("筛选状态", statuses, default=statuses)

            # 过滤
            filtered_df = df[
                (df['category'].isin(selected_cat)) &
                (df['cooperation_status'].isin(selected_status))
                ]

            st.write(f"显示 {len(filtered_df)} / {len(df)} 个供应商")

            # 显示表格
            st.dataframe(
                filtered_df[['company_name', 'category', 'email', 'cooperation_status', 'add_date']],
                use_container_width=True
            )
        else:
            st.info("知识库为空，请先分析一些产品")

    except Exception as e:
        st.error(f"加载失败: {e}")


# ============================================================
# 辅助函数
# ============================================================
def generate_excel_report(product_info: dict, suppliers: list) -> bytes:
    """生成Excel报告"""
    import io

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # 产品信息表
        product_df = pd.DataFrame([product_info])
        product_df.to_excel(writer, sheet_name='产品信息', index=False)

        # 供应商表
        suppliers_data = []
        for s in suppliers:
            contact = s.get('contact', {})
            suppliers_data.append({
                '公司名称': s.get('title'),
                '数据来源': s.get('source'),
                '公司类型': s.get('match_type'),
                '匹配评分': s.get('score'),
                '网站': s.get('link'),
                '联系人': contact.get('name', ''),
                '邮箱': contact.get('email', ''),
                '电话': contact.get('phone', ''),
                '推荐理由': s.get('reason'),
            })

        suppliers_df = pd.DataFrame(suppliers_data)
        suppliers_df.to_excel(writer, sheet_name='推荐供应商', index=False)

    output.seek(0)
    return output.getvalue()


# ============================================================
# 页脚
# ============================================================
st.divider()
st.markdown("""
<div style="text-align: center; color: #999; padding: 1rem;">
    <p>🚀 跨境电商供应商智能匹配系统 v3.0 | Powered by LangChain + FAISS + Gemini</p>
</div>
""", unsafe_allow_html=True)