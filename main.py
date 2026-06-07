#!/usr/bin/env python3
"""
Zotero 文献助手 - 主入口
提供命令行和 Web UI 两种使用方式
"""

import sys
import argparse
from pathlib import Path

# 确保项目根目录在 Python 路径中
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import get_settings
from utils import setup_logging, get_logger, print_info, print_success, print_error


def cmd_scan(args):
    """扫描集合命令"""
    from zotero import CollectionManager
    from indexer import DocumentScanner
    
    logger = get_logger(__name__)
    
    scanner = DocumentScanner()
    
    print_info(f"扫描集合: {args.collection}")
    
    try:
        documents = scanner.scan_collection(
            args.collection,
            include_subcollections=args.recursive,
            load_pdf_content=args.load_pdf
        )
        
        print_success(f"找到 {len(documents)} 篇文献")
        
        for doc in documents:
            pdf_status = "📑" if doc.has_pdf else "❌"
            print(f"  {pdf_status} {doc.title[:60]} - {doc.authors}")
        
        stats = scanner.get_statistics()
        print_info(f"\n统计: 总共 {stats['total_documents']} 篇, "
                   f"有PDF {stats['with_pdf']} 篇, "
                   f"已加载 {stats['pdf_loaded']} 篇")
        
    except Exception as e:
        print_error(f"扫描失败: {e}")
        sys.exit(1)


def cmd_list_collections(args):
    """列出所有集合"""
    from zotero import CollectionManager
    
    print_info("获取 Zotero 集合列表...")
    
    try:
        manager = CollectionManager()
        collections = manager.get_all_collections()
        
        print_success(f"找到 {len(collections)} 个集合:\n")
        
        for col in collections:
            parent_info = f" (父: {col.parent_key})" if col.parent_key else ""
            print(f"  📁 {col.name} ({col.num_items} 项){parent_info}")
        
    except Exception as e:
        print_error(f"获取失败: {e}")
        sys.exit(1)


def cmd_summarize(args):
    """总结文献命令"""
    from indexer import DocumentScanner
    from ai import AISummarizer
    
    scanner = DocumentScanner()
    
    print_info(f"扫描集合: {args.collection}")
    documents = scanner.scan_collection(
        args.collection,
        load_pdf_content=True
    )
    
    if not documents:
        print_error("未找到文献")
        sys.exit(1)
    
    print_success(f"找到 {len(documents)} 篇文献")
    
    # 选择要总结的文献
    if args.limit:
        documents = documents[:args.limit]
    
    print_info(f"正在总结 {len(documents)} 篇文献...")
    
    try:
        summarizer = AISummarizer()
        
        if len(documents) == 1:
            result = summarizer.summarize_document(documents[0])
            print(f"\n{'='*60}")
            print(f"📝 {result.title}")
            print(f"{'='*60}\n")
            print(result.summary)
        else:
            result = summarizer.summarize_multiple(documents)
            print(f"\n{'='*60}")
            print(f"📊 综合分析 ({len(documents)} 篇文献)")
            print(f"{'='*60}\n")
            print(result.summary)
        
    except Exception as e:
        print_error(f"总结失败: {e}")
        sys.exit(1)


def cmd_research(args):
    """深度研究命令"""
    from indexer import DocumentScanner
    from ai import AISummarizer
    
    scanner = DocumentScanner()
    
    print_info(f"扫描集合: {args.collection}")
    documents = scanner.scan_collection(
        args.collection,
        load_pdf_content=True
    )
    
    if not documents:
        print_error("未找到文献")
        sys.exit(1)
    
    print_info(f"对 {len(documents)} 篇文献进行深度研究...")
    print_info(f"研究问题: {args.question}")
    
    try:
        summarizer = AISummarizer()
        result = summarizer.deep_research(args.question, documents)
        
        print(f"\n{'='*60}")
        print("🔬 深度研究报告")
        print(f"{'='*60}\n")
        print(result.report)
        
    except Exception as e:
        print_error(f"研究失败: {e}")
        sys.exit(1)


def cmd_ui(args):
    """启动 Web API 服务器"""
    import uvicorn
    
    print_info("启动 Zotero 文献助手 API 服务器...")
    print_info(f"API 地址: http://localhost:{args.port}")
    print_info("请在 web/ 目录下运行 npm run dev 启动前端")
    
    # Run the FastAPI app
    uvicorn.run("api:app", host="0.0.0.0", port=args.port, reload=not args.prod)


def main():
    """主函数"""
    setup_logging()
    
    parser = argparse.ArgumentParser(
        description="Zotero 文献助手 - AI 驱动的文献管理和研究工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 启动 Web UI
  python main.py ui
  
  # 列出所有集合
  python main.py list
  
  # 扫描指定集合
  python main.py scan "My Collection"
  
  # 总结文献
  python main.py summarize "My Collection" --limit 5
  
  # 深度研究
  python main.py research "My Collection" -q "这些文献的主要发现是什么?"
"""
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # UI 命令
    ui_parser = subparsers.add_parser("ui", help="启动 Web API Server")
    ui_parser.add_argument("--port", type=int, default=8000, help="端口号")
    ui_parser.add_argument("--prod", action="store_true", help="生产模式")
    
    # 列出集合命令
    list_parser = subparsers.add_parser("list", help="列出所有 Zotero 集合")
    
    # 扫描命令
    scan_parser = subparsers.add_parser("scan", help="扫描指定集合")
    scan_parser.add_argument("collection", help="集合名称")
    scan_parser.add_argument("-r", "--recursive", action="store_true", help="包含子集合")
    scan_parser.add_argument("--load-pdf", action="store_true", help="加载 PDF 内容")
    
    # 总结命令
    summarize_parser = subparsers.add_parser("summarize", help="AI 总结文献")
    summarize_parser.add_argument("collection", help="集合名称")
    summarize_parser.add_argument("--limit", type=int, help="限制文献数量")
    
    # 研究命令
    research_parser = subparsers.add_parser("research", help="深度研究")
    research_parser.add_argument("collection", help="集合名称")
    research_parser.add_argument("-q", "--question", required=True, help="研究问题")
    
    args = parser.parse_args()
    
    if args.command == "ui":
        cmd_ui(args)
    elif args.command == "list":
        cmd_list_collections(args)
    elif args.command == "scan":
        cmd_scan(args)
    elif args.command == "summarize":
        cmd_summarize(args)
    elif args.command == "research":
        cmd_research(args)
    else:
        # 默认启动 UI
        parser.print_help()
        print("\n💡 提示: 使用 'python main.py ui' 启动 Web 界面")


if __name__ == "__main__":
    main()
