"""
RAG引擎 - PDF解析和信息提取 (Python 3.11兼容版本)
"""
from pypdf import PdfReader
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from config import Config


def process_pdf_to_retriever(pdf_path: str) -> dict:
    """
    处理PDF并提取产品信息

    Args:
        pdf_path: PDF文件路径

    Returns:
        dict: 提取的产品信息
    """
    print(f"📄 正在解析PDF: {pdf_path}")

    # 1. 读取PDF文本
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:  # 确保提取到了文本
                text += page_text + "\n"

        if not text.strip():
            raise Exception("PDF文本提取为空，可能是扫描件或加密文件")

        print(f"✅ PDF文本提取成功，共 {len(text)} 字符")

    except Exception as e:
        raise Exception(f"PDF读取失败: {str(e)}")

    # 2. 使用Gemini提取结构化信息
    print("🤖 使用Gemini提取产品信息...")

    try:
        llm = ChatGoogleGenerativeAI(
            model=Config.GEMINI_MODEL,
            google_api_key=Config.GOOGLE_API_KEY,
            temperature=Config.GEMINI_TEMPERATURE
        )
    except Exception as e:
        raise Exception(f"Gemini初始化失败: {str(e)}. 请检查API Key是否正确")

    # 创建提示模板
    prompt = PromptTemplate(
        input_variables=["pdf_text"],
        template="""你是一个专业的产品分析专家。请从以下PDF文本中提取关键产品信息。

PDF内容:
{pdf_text}

请仔细分析并提取以下信息（如果文本中没有明确提到，基于上下文推断或标注"未提供"）：

1. **产品名称**: 具体的产品名称
2. **产品类别**: 所属行业/类别（如：消费电子、家居用品、工业设备等）
3. **核心规格**: 主要技术参数、尺寸、材质等
4. **目标市场**: 销售地区、目标客户群
5. **特殊要求**: 认证需求（CE、FDA、FCC等）、特殊工艺、质量标准

请用以下格式返回，每行一个字段：
产品名称: xxx
产品类别: xxx
核心规格: xxx
目标市场: xxx
特殊要求: xxx

注意：请直接提取，不要添加额外解释。"""
    )

    # 限制文本长度避免超token
    truncated_text = text[:4000] if len(text) > 4000 else text

    try:
        # 格式化prompt
        formatted_prompt = prompt.format(pdf_text=truncated_text)

        # 调用LLM - 使用invoke方法
        response = llm.invoke(formatted_prompt)

        # 提取返回内容
        if hasattr(response, 'content'):
            llm_output = response.content
        else:
            llm_output = str(response)

    except Exception as e:
        raise Exception(f"Gemini API调用失败: {str(e)}")

    # 3. 解析LLM返回结果
    product_info = _parse_product_info(llm_output)

    if not product_info:
        raise Exception("未能从LLM响应中提取到产品信息")

    print("✅ 产品信息提取完成！")
    return product_info


def _parse_product_info(llm_response: str) -> dict:
    """
    解析LLM返回的文本为字典

    Args:
        llm_response: LLM返回的文本

    Returns:
        dict: 结构化的产品信息
    """
    info = {}
    lines = llm_response.strip().split('\n')

    for line in lines:
        # 跳过空行
        if not line.strip():
            continue

        # 处理中英文冒号
        if ':' in line or '：' in line:
            separator = ':' if ':' in line else '：'
            parts = line.split(separator, 1)

            if len(parts) == 2:
                key = parts[0].strip()
                # 移除可能的markdown标记
                key = key.replace('*', '').replace('#', '').replace('**', '')
                value = parts[1].strip()
                info[key] = value

    return info


if __name__ == "__main__":
    # 测试代码
    import os

    test_pdf = "data/product.pdf"

    print("=" * 60)
    print("测试 PDF 解析模块")
    print("=" * 60)

    if not os.path.exists(test_pdf):
        print(f"❌ 测试PDF不存在: {test_pdf}")
        print("请将产品PDF放到 data/product.pdf")
    else:
        try:
            # 验证配置
            Config.validate()

            # 解析PDF
            info = process_pdf_to_retriever(test_pdf)

            print("\n" + "=" * 60)
            print("📋 提取的产品信息:")
            print("=" * 60)
            for key, value in info.items():
                print(f"{key}: {value}")

        except Exception as e:
            print(f"❌ 错误: {e}")
            import traceback

            traceback.print_exc()