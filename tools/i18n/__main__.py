# coding:utf-8
"""i18n 工具命令行入口：python -m tools.i18n {extract,check,compile,prune}"""
import argparse
import sys

from . import extract, prune_dead_keys, run_checks


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.i18n", description="多语言翻译目录工具")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("extract", help="扫描源码/常量表/数据源，把新文案并入 .pot/.po")
    sub.add_parser("check", help="校验翻译目录（CI / pytest 使用同一套规则）")
    sub.add_parser("compile", help="编译 .po -> .mo（.mo 需随 .po 一起提交）")
    prune = sub.add_parser("prune", help="删除未登记进 .pot 的死条目（模板外历史遗留）")
    prune.add_argument("--dry-run", action="store_true", help="只统计不写入")
    args = parser.parse_args(argv)

    if args.command == "extract":
        stats = extract()
        print(f"新登记/升级条目: {stats['new_keys']} 个")
        for lang, n in stats["synced"].items():
            if n:
                print(f"[{lang}] 变更 {n} 个条目")
        print(f"动态 tr()/tn() 调用（无法静态提取）: {stats['dynamic_calls']} 处")
        return 0

    if args.command == "prune":
        removed = prune_dead_keys(dry_run=args.dry_run)
        total = sum(removed.values())
        detail = ", ".join(f"{lang}={n}" for lang, n in removed.items())
        print(f"{'将删除' if args.dry_run else '已删除'}死条目 {total} 条（{detail}）")
        if total and not args.dry_run:
            print("请运行 python -m tools.i18n compile 同步 .mo")
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
