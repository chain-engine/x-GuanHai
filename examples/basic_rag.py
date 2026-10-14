#!/usr/bin/env python3
"""
基础RAG使用示例
演示如何使用x-GuanHai进行文档上传、索引构建、查询检索和生成回答
"""

import asyncio

import httpx


async def main():
    """主函数"""
    base_url = "http://localhost:8000/api/v1"

    print("=" * 60)
    print("x-GuanHai 基础示例")
    print("=" * 60)

    # 1. 健康检查
    print("\n[1] 健康检查...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{base_url}/health")
        print(f"健康状态: {response.json()}")

    # 2. 上传文档
    print("\n[2] 上传文档...")

    # 示例文档内容
    sample_text = """
    Python是一种高级编程语言，由Guido van Rossum于1991年首次发布。
    Python的设计哲学强调代码的可读性和简洁的语法。
    相比于C++或Java，Python让开发者能够用更少的代码表达概念。

    Python支持多种编程范式，包括面向对象、命令式、函数式和过程式编程。
    它拥有一个庞大而全面的标准库，常被称为"内置电池（batteries included）"。

    Python广泛应用于Web开发、数据分析、人工智能、科学计算、自动化等领域。
    Django、Flask是流行的Python Web框架。
    NumPy、Pandas、Matplotlib是数据科学领域常用的Python库。
    TensorFlow、PyTorch是深度学习领域的主流框架。
    """

    print("\n示例文档内容:")
    print("-" * 60)
    print(sample_text.strip())
    print("-" * 60)

    # 上传文档
    print("\n正在上传文档...")
    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.post(
            f"{base_url}/documents/upload",
            files={"file": ("python_intro.txt", sample_text.encode("utf-8"), "text/plain")}
        )
        result = response.json()
        print(f"上传结果: {result}")

        if result["code"] == 201:
            document_id = result["data"]["document_id"]
            print(f"文档ID: {document_id}")
            print(f"分块数量: {result['data']['message']}")

    # 等待文档索引完成
    print("\n等待文档索引完成...")
    await asyncio.sleep(2)

    # 3. 查询文档状态
    print("\n[3] 查询文档状态...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{base_url}/documents/{document_id}/status")
        print(f"文档状态: {response.json()}")

    # 4. RAG查询
    print("\n[4] RAG查询...")

    queries = [
        "Python是什么时候发布的？",
        "Python的设计哲学是什么？",
        "Python有哪些应用领域？",
        "什么是Python的'batteries included'特性？"
    ]

    for query in queries:
        print(f"\n查询: {query}")
        print("-" * 60)

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{base_url}/rag/query",
                json={
                    "query": query,
                    "top_k": 3,
                    "similarity_threshold": 0.5
                }
            )
            result = response.json()

            if result["code"] == 200:
                print(f"答案: {result['data']['answer']}")
                print(f"检索到 {len(result['data']['retrieved_docs'])} 个相关文档")

                print("\n相关文档:")
                for idx, doc in enumerate(result["data"]["retrieved_docs"], 1):
                    print(f"  [{idx}] 相似度: {doc['score']:.3f}")
                    print(f"      内容: {doc['text'][:100]}...")
            else:
                print(f"查询失败: {result}")

    # 5. 纯检索（不生成）
    print("\n[5] 纯检索示例...")
    print("查询: Python的应用领域")
    print("-" * 60)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url}/rag/retrieve",
            json={
                "query": "Python的应用领域",
                "top_k": 3,
                "similarity_threshold": 0.3
            }
        )
        result = response.json()

        if result["code"] == 200:
            print(f"检索到 {len(result['data']['documents'])} 个文档")

            for idx, doc in enumerate(result["data"]["documents"], 1):
                print(f"\n[{idx}] 相似度: {doc['score']:.3f}")
                print(f"内容: {doc['text']}")
        else:
            print(f"检索失败: {result}")

    # 6. 获取系统统计
    print("\n[6] 系统统计...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{base_url}/rag/stats")
        print(f"统计信息: {response.json()}")

    # 7. 列出所有文档
    print("\n[7] 列出所有文档...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{base_url}/documents")
        result = response.json()
        if result["code"] == 200:
            print(f"总文档数: {result['data']['total']}")
            for doc in result["data"]["items"]:
                print(f"  - {doc['document_id']}: {doc['file_name']} ({doc['status']})")

    print("\n" + "=" * 60)
    print("示例完成！")
    print("=" * 60)

    # 可选：删除文档
    # print("\n[8] 删除文档...")
    # async with httpx.AsyncClient() as client:
    #     response = await client.delete(f"{base_url}/documents/{document_id}")
    #     print(f"删除结果: {response.json()}")


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
