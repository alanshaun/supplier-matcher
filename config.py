"""
配置文件 - 管理所有配置项
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class Config:
    """配置类"""

    # API Keys
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    SERPAPI_KEY = os.getenv("SERPAPI_KEY")

    # Gemini 模型配置
    GEMINI_MODEL = "gemini-2.5-flash"
    GEMINI_TEMPERATURE = 0.3

    # 搜索配置
    SEARCH_NUM_RESULTS = 10  # 搜索返回结果数
    TOP_N_SUPPLIERS = 3  # 最终推荐供应商数量

    # 路径配置
    DATA_DIR = "data"

    @classmethod
    def validate(cls):
        """验证配置是否完整"""
        if not cls.GOOGLE_API_KEY:
            raise ValueError("❌ 缺少 GOOGLE_API_KEY，请在 .env 文件中配置")
        if not cls.SERPAPI_KEY:
            raise ValueError("❌ 缺少 SERPAPI_KEY，请在 .env 文件中配置")
        return True


if __name__ == "__main__":
    # 测试配置
    try:
        Config.validate()
        print("✅ 配置验证成功！")
        print(f"Gemini Model: {Config.GEMINI_MODEL}")
        print(f"API Keys已配置")
    except Exception as e:
        print(f"❌ 配置错误: {e}")