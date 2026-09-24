# coding:utf-8
"""i18n 工具命令行入口：python -m tools.i18n {extract,check,compile}"""
import argparse
import sys

from . import extract, run_checks


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.i18n", description="多语言翻译目录工具")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("extract", help="扫描源码/数据源，把新文案并入 .pot/.po")
    sub.add_parser("check", help="校验翻译目录（CI / pytest 使用同一套规则）")
    sub.add_parser("compile", help="编译 .po -> .mo（.mo 需随 .po 一起提交）")
    args = parser.parse_args(argv)

    if args.command == "extract":
        stats = extract()
        print(f"新登记/升级条目: {stats['new_keys']} 个")
        for lang, n in stats["synced"].items():
            if n:
                print(f"[{lang}] 变更 {n} 个条目")
        print(f"动态 tr()/tn() 调用（无法静态提取）: {stats['dynamic_calls']} 处")
        return 0

    if args.command == "compile":
        from .po import compile_po
        from . import LOCALES as PO_LOCALES
        for lang in PO_LOCALES:
            size = compile_po(lang)
            print(f"[{lang}] march7th.mo 编译完成（{size} 字节）")
        return 0

    # check
    errors, warnings = run_checks()
    for w in warnings:
        print(f"警告: {w}")
    for e in errors:
        print(f"错误: {e}", file=sys.stderr)
    if errors:
        print(f"校验失败: {len(errors)} 个错误、{len(warnings)} 个警告", file=sys.stderr)
        return 1
    print(f"校验通过（{len(warnings)} 个警告）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
