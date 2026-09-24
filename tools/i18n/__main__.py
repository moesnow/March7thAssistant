# coding:utf-8
"""i18n 工具命令行入口：python -m tools.i18n {extract,sync,check,migrate-po,update-po,compile}"""
import argparse
import sys

from . import extract, run_checks, sync_catalogs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.i18n", description="多语言翻译目录工具")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("extract", help="扫描源码，登记新文案并补齐各语言骨架")
    sub.add_parser("sync", help="把 zh_CN 的 key 补齐到其它语言（已有条目不覆盖）")
    sub.add_parser("check", help="校验翻译目录（CI / pytest 使用同一套规则）")
    sub.add_parser("migrate-po", help="JSON 目录一次性迁移为 gettext .po/.pot")
    sub.add_parser("update-po", help="把源码提取结果并入 .pot 与各 .po（已有译文不覆盖）")
    sub.add_parser("compile", help="编译 .po -> .mo（.mo 需随 .po 一起提交）")
    args = parser.parse_args(argv)

    if args.command == "extract":
        stats = extract()
        print(f"新登记 key: {stats['new_keys']} 个")
        for lang, n in stats["synced"].items():
            if n:
                print(f"[{lang}] 补齐 {n} 个 key")
        print(f"动态 tr()/tn() 调用（无法静态提取）: {stats['dynamic_calls']} 处")
        return 0

    if args.command == "sync":
        added = sync_catalogs()
        for lang, n in added.items():
            if n:
                print(f"[{lang}] 补齐 {n} 个 key")
        return 0

    if args.command == "migrate-po":
        from . import load_catalogs
        from .po import migrate_po
        catalogs, errors = load_catalogs()
        if errors:
            for e in errors:
                print(f"错误: {e}", file=sys.stderr)
            return 1
        stats = migrate_po(catalogs)
        for lang, n in stats.items():
            print(f"[{lang}] 生成 po 条目 {n} 个")
        return 0

    if args.command == "update-po":
        from .po import update_po
        added = update_po()
        for lang, n in added.items():
            print(f"[{lang}] 新并入 {n} 个条目")
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
