#!/usr/bin/env python3
"""
文档处理流程示例
演示文档处理流程和批量处理
"""

import asyncio
from pathlib import Path
from typing import Any

import httpx


async def upload_file(base_url: str, file_path: str) -> dict[str, Any]:
    """上传单个文件

    Args:
        base_url: API基础URL
        file_path: 文件路径

    Returns:
        dict[str, Any]: 上传结果
    """
    path = Path(file_path)

    if not path.exists():
        return {"error": f"文件不存在: {file_path}"}

    async with httpx.AsyncClient(timeout=300) as client:
        with open(path, "rb") as f:
            response = await client.post(
                f"{base_url}/documents/upload", files={"file": (path.name, f, "text/plain")}
            )
            return response.json()


async def batch_upload(base_url: str, file_paths: list[str]) -> list[dict[str, Any]]:
    """批量上传文件

    Args:
        base_url: API基础URL
        file_paths: 文件路径列表

    Returns:
        list[dict[str, Any]]: 上传结果列表
    """
    tasks = [upload_file(base_url, fp) for fp in file_paths]
    return await asyncio.gather(*tasks)


async def main():
    """主函数"""
    base_url = "http://localhost:8000/api/v1"

    print("=" * 60)
    print("x-GuanHai 文档处理示例")
    print("=" * 60)

    # 1. 创建示例文件
    print("\n[1] 创建示例文件...")

    examples_dir = Path("examples/sample_docs")
    examples_dir.mkdir(exist_ok=True)

    sample_docs = {
        "ai_intro.txt": """
人工智能（Artificial Intelligence，AI）是计算机科学的一个分支，
致力于创建能够执行通常需要人类智能的任务的系统。

AI的主要应用领域包括：
- 自然语言处理
- 计算机视觉
- 机器学习
- 深度学习
- 机器人技术

机器学习是AI的一个重要子领域，它使计算机能够从数据中学习，
而无需明确编程。深度学习是机器学习的一种方法，
使用多层神经网络来模拟人脑的工作方式。
        """.strip(),
        "web_frameworks.txt": """
Web框架是用于开发Web应用程序的软件框架。

流行的Python Web框架包括：

1. Django
   - 全功能框架
   - 内置ORM、模板引擎、用户认证
   - 适合快速开发大型应用

2. Flask
   - 轻量级微框架
   - 灵活可扩展
   - 适合小型到中型应用

3. FastAPI
   - 现代高性能框架
   - 支持异步
   - 自动生成API文档

选择框架时，应考虑项目需求、团队经验和性能要求。
        """.strip(),
        "data_science.txt": """
数据科学是一个跨学科领域，使用科学方法、流程和系统，
从结构化和非结构化数据中提取知识和洞察。

Python数据科学生态系统包括：

1. 数据处理
   - NumPy：数值计算
   - Pandas：数据分析
   - SciPy：科学计算

2. 数据可视化
   - Matplotlib：基础绘图
   - Seaborn：统计可视化
   - Plotly：交互式图表

3. 机器学习
   - Scikit-learn：传统机器学习
   - TensorFlow：深度学习
   - PyTorch：深度学习研究

数据科学流程通常包括：
数据收集 -> 数据清洗 -> 探索性分析 -> 建模 -> 可视化 -> 部署
        """.strip(),
    }

    file_paths = []
    for filename, content in sample_docs.items():
        file_path = examples_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        file_paths.append(str(file_path))
        print(f"  创建: {filename}")

    # 2. 批量上传
    print("\n[2] 批量上传文档...")
    print("-" * 60)

    results = await batch_upload(base_url, file_paths)

    document_ids = []
    for filename, result in zip(sample_docs.keys(), results, strict=False):
        if result.get("code") == 201:
            doc_id = result["data"]["document_id"]
            document_ids.append(doc_id)
            print(f"✓ {filename}: {doc_id}")
        else:
            print(f"✗ {filename}: {result.get('message', 'Failed')}")

    # 等待索引完成
    print("\n等待文档索引完成...")
    await asyncio.sleep(5)

    # 3. 检查文档状态
    print("\n[3] 检查文档状态...")
    print("-" * 60)

    for doc_id in document_ids:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/documents/{doc_id}/status")
            status = response.json()
            print(f"{doc_id[:8]}...: {status.get('data', {}).get('status', 'unknown')}")

    # 4. 查询测试
    print("\n[4] 查询测试...")
    print("-" * 60)

    test_queries = [
        ("AI", "什么是机器学习？"),
        ("AI", "深度学习和机器学习的区别是什么？"),
        ("Web", "Django和Flask有什么区别？"),
        ("Web", "FastAPI有什么特点？"),
        ("Data", "数据科学生态系统包括哪些库？"),
        ("Data", "数据科学的流程是什么？"),
    ]

    for category, query in test_queries:
        print(f"\n[{category}] {query}")

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{base_url}/rag/query",
                json={"query": query, "top_k": 3, "similarity_threshold": 0.4},
            )
            result = response.json()

            if result["code"] == 200:
                print(f"  答案: {result['data']['answer'][:150]}...")
            else:
                print(f"  查询失败: {result.get('message', 'Unknown error')}")

    # 5. 统计信息
    print("\n[5] 系统统计...")
    print("-" * 60)

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{base_url}/rag/stats")
        stats = response.json()
        print(f"向量总数: {stats.get('data', {}).get('vector_count', 0)}")

        response = await client.get(f"{base_url}/documents")
        docs = response.json()
        print(f"文档总数: {docs.get('data', {}).get('total', 0)}")

    # 6. 清理（可选）
    print("\n[6] 清理文档...")
    print("-" * 60)

    for doc_id in document_ids:
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{base_url}/documents/{doc_id}")
            result = response.json()
            if result.get("code") == 200:
                print(f"✓ 已删除: {doc_id[:8]}...")

    print("\n" + "=" * 60)
    print("示例完成！")
    print("=" * 60)


if __name__ == "__main__":
    print("请确保x-GuanHai服务已启动: python src/main.py")
    print("按Enter键继续或Ctrl+C取消...")

    try:
        input()
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n已取消。")
    except Exception as e:
        print(f"\n发生错误: {e}")
        print("\n请确保:")
        print("1. x-GuanHai服务已启动 (python src/main.py)")
        print("2. 所有依赖已安装 (pip install -r requirements.txt)")
        print("3. 端口8000未被占用")
