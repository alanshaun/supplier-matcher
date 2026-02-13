"""
联系人信息挖掘模块 - 改进版 (更激进的提取策略)
"""
import sys
import os
# 将当前文件的上一级目录添加到 Python 路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from serpapi import GoogleSearch
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

from config import Config
import json
import re


def find_contact_info(company_name: str, company_website: str = None) -> dict:
    """
    为供应商查找联系人信息 - 改进版

    Args:
        company_name: 公司名称
        company_website: 公司网站（可选）

    Returns:
        dict: 联系人信息
    """
    print(f"\n🔍 正在查找 {company_name} 的联系人信息...")

    # 策略1: 搜索公司联系页面
    contact_info = _strategy_1_search_contact_page(company_name, company_website)

    if contact_info and contact_info.get('confidence') != 'low':
        return contact_info

    # 策略2: 搜索LinkedIn
    print("  尝试策略2: LinkedIn搜索...")
    linkedin_info = _strategy_2_linkedin_search(company_name)

    if linkedin_info and linkedin_info.get('confidence') != 'low':
        return linkedin_info

    # 策略3: 生成智能推测
    print("  尝试策略3: 智能推测...")
    return _strategy_3_smart_guess(company_name, company_website)


def _strategy_1_search_contact_page(company_name: str, website: str = None) -> dict:
    """策略1: 搜索公司联系页面"""

    # 多个搜索查询
    queries = [
        f'"{company_name}" contact email',
        f'"{company_name}" sales manager email',
        f'site:{_extract_domain(website)} contact' if website else None,
    ]

    queries = [q for q in queries if q]  # 移除None

    all_results = []

    for query in queries[:2]:  # 只用前2个
        results = _search_serp(query)
        all_results.extend(results)

        if len(all_results) >= 5:
            break

    if not all_results:
        return None

    # 用LLM提取
    return _extract_with_llm_v2(company_name, all_results, website)


def _strategy_2_linkedin_search(company_name: str) -> dict:
    """策略2: LinkedIn搜索"""

    query = f'site:linkedin.com "{company_name}" sales director OR export manager'

    results = _search_serp(query)

    if not results:
        return None

    # 从LinkedIn结果提取
    return _extract_linkedin_info(company_name, results)


def _strategy_3_smart_guess(company_name: str, website: str = None) -> dict:
    """策略3: 基于常见模式的智能推测"""

    domain = _extract_domain(website) if website else None

    # 生成可能的邮箱
    possible_emails = []

    if domain:
        possible_emails = [
            f"sales@{domain}",
            f"export@{domain}",
            f"info@{domain}",
            f"contact@{domain}"
        ]

    return {
        "name": "Sales Department",
        "title": "Sales Manager",
        "email": possible_emails[0] if possible_emails else "未找到",
        "phone": "未找到",
        "linkedin": "未找到",
        "department": "sales",
        "source": website if website else "推测",
        "confidence": "low",
        "note": "基于常见邮箱模式生成，建议验证"
    }


def _search_serp(query: str) -> list:
    """执行SerpAPI搜索"""

    try:
        params = {
            "q": query,
            "api_key": Config.SERPAPI_KEY,
            "engine": "google",
            "num": 5,
            "gl": "us",
            "hl": "en"
        }

        search = GoogleSearch(params)
        results = search.get_dict()

        if "error" in results:
            return []

        extracted = []
        if "organic_results" in results:
            for result in results["organic_results"]:
                extracted.append({
                    "title": result.get("title", ""),
                    "link": result.get("link", ""),
                    "snippet": result.get("snippet", "")
                })

        return extracted

    except Exception as e:
        print(f"    搜索错误: {e}")
        return []


def _extract_with_llm_v2(company_name: str, search_results: list, website: str = None) -> dict:
    """改进的LLM提取 - 更宽松的要求"""

    try:
        llm = ChatGoogleGenerativeAI(
            model=Config.GEMINI_MODEL,
            google_api_key=Config.GOOGLE_API_KEY,
            temperature=0.2
        )

        # 更详细的提示词
        prompt_text = f"""你是联系信息提取专家。从搜索结果中提取 {company_name} 的销售/出口联系方式。

**搜索结果**:
{json.dumps(search_results[:3], ensure_ascii=False, indent=2)}

**提取规则**:
1. 优先找销售、出口、商务相关的邮箱
2. 如果找不到具体人名，用部门名称（如 Sales Department）
3. 从snippet中识别邮箱格式（xxx@domain.com）
4. 如果有多个邮箱，选择最像销售/出口部门的

**输出JSON格式**（不要markdown标记）:
{{
  "name": "联系人姓名（找不到就用部门名）",
  "title": "职位（如Sales Manager）",
  "email": "邮箱地址（必须提取到）",
  "phone": "电话号码（如果有）",
  "confidence": "high/medium/low"
}}

重要: 
- 必须尽力从snippet中找出邮箱！
- 即使是info@或contact@这种通用邮箱也要提取
- 只返回JSON，不要其他文字"""

        response = llm.invoke(prompt_text)

        if hasattr(response, 'content'):
            content = response.content.strip()
        else:
            content = str(response).strip()

        # 清理JSON
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        content = content.strip()

        # 解析
        contact_info = json.loads(content)

        # 验证邮箱
        if "email" in contact_info and contact_info["email"]:
            email = contact_info["email"]
            # 基本邮箱格式验证
            if "@" in email and "." in email:
                print(f"  ✅ 找到邮箱: {email}")
                contact_info["source"] = search_results[0].get("link", "搜索结果")
                return contact_info

        # 如果LLM没找到，手动从snippet中提取
        print("  🔍 LLM未找到，尝试正则提取...")
        manual_extract = _manual_email_extraction(search_results)

        if manual_extract:
            return manual_extract

        return None

    except Exception as e:
        print(f"    LLM提取失败: {e}")

        # 降级到手动提取
        manual_extract = _manual_email_extraction(search_results)
        return manual_extract if manual_extract else None


def _manual_email_extraction(search_results: list) -> dict:
    """手动从搜索结果中提取邮箱"""

    # 邮箱正则表达式
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

    found_emails = []

    for result in search_results:
        snippet = result.get("snippet", "")
        title = result.get("title", "")

        # 在snippet中查找
        emails_in_snippet = re.findall(email_pattern, snippet)
        found_emails.extend(emails_in_snippet)

        # 在title中查找
        emails_in_title = re.findall(email_pattern, title)
        found_emails.extend(emails_in_title)

    if found_emails:
        # 优先选择sales/export/info相关的邮箱
        priority_emails = [e for e in found_emails if any(kw in e.lower() for kw in ['sales', 'export', 'business'])]

        selected_email = priority_emails[0] if priority_emails else found_emails[0]

        print(f"  ✅ 正则提取到邮箱: {selected_email}")

        return {
            "name": "Contact Person",
            "title": "Sales Department",
            "email": selected_email,
            "phone": "未找到",
            "linkedin": "未找到",
            "confidence": "medium",
            "source": "搜索结果提取"
        }

    return None


def _extract_linkedin_info(company_name: str, results: list) -> dict:
    """从LinkedIn搜索结果提取信息"""

    if not results:
        return None

    # 提取LinkedIn链接
    linkedin_links = []
    for result in results:
        link = result.get("link", "")
        if "linkedin.com/in/" in link:
            linkedin_links.append(link)

    if linkedin_links:
        # 从title中提取姓名和职位
        first_result = results[0]
        title = first_result.get("title", "")

        # LinkedIn标题格式: "姓名 - 职位 - 公司 | LinkedIn"
        parts = title.split("-")

        name = parts[0].strip() if len(parts) > 0 else "未找到"
        position = parts[1].strip() if len(parts) > 1 else "Sales Manager"

        return {
            "name": name,
            "title": position,
            "email": "未找到",
            "linkedin": linkedin_links[0],
            "confidence": "medium",
            "source": "LinkedIn"
        }

    return None


def _extract_domain(url: str) -> str:
    """从URL提取域名"""
    if not url:
        return None

    match = re.search(r'https?://(?:www\.)?([^/]+)', url)
    return match.group(1) if match else None


def batch_find_contacts(suppliers: list) -> list:
    """批量查找联系人 - 改进版"""

    print("\n" + "=" * 60)
    print("👥 开始批量查找联系人信息")
    print("=" * 60)

    enriched_suppliers = []

    for i, supplier in enumerate(suppliers, 1):
        print(f"\n[{i}/{len(suppliers)}] 处理: {supplier.get('title', 'N/A')[:50]}")

        company_name = supplier.get('title', '')
        company_website = supplier.get('link', '')

        # 查找联系人
        contact_info = find_contact_info(company_name, company_website)

        # 添加到供应商信息中
        supplier['contact'] = contact_info
        enriched_suppliers.append(supplier)

        # 显示结果
        if contact_info.get('email') and contact_info['email'] != '未找到':
            print(f"  ✅ 成功: {contact_info['email']}")
        else:
            print(f"  ⚠️  未找到有效邮箱")

        # 避免请求过快
        import time
        time.sleep(2)

    # 统计
    success_count = sum(1 for s in enriched_suppliers
                        if s.get('contact', {}).get('email', '') != '未找到')

    print("\n" + "=" * 60)
    print(f"✅ 联系人查找完成！")
    print(f"   成功找到邮箱: {success_count}/{len(enriched_suppliers)}")
    print("=" * 60)

    return enriched_suppliers


if __name__ == "__main__":
    # 测试代码
    import os
    from dotenv import load_dotenv

    load_dotenv()

    test_companies = [
        ("Shenzhen Anker Technology Co., Ltd.", "https://www.anker.com"),
        ("Foxconn", "https://www.foxconn.com"),
    ]

    try:
        Config.validate()

        for company_name, website in test_companies:
            print("\n" + "=" * 60)
            contact = find_contact_info(company_name, website)

            print(f"\n📋 结果:")
            print(f"  姓名: {contact.get('name', 'N/A')}")
            print(f"  邮箱: {contact.get('email', 'N/A')}")
            print(f"  可信度: {contact.get('confidence', 'N/A')}")

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback

        traceback.print_exc()