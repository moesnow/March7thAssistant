# coding:utf-8
"""i18n 工具命令行入口：python -m tools.i18n {extract,sync,check}"""
import argparse
import sys

from . import extract, run_checks, sync_catalogs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.i18n", description="多语言翻译目录工具")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("extract", help="扫描源码，登记新文案并补齐各语言骨架")
    sub.add_parser("sync", help="把 zh_CN 的 key 补齐到其它语言（已有条目不覆盖）")
    sub.add_parser("check", help="校验翻译目录（CI / pytest 使用同一套规则）")
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
            print(f"[{lang}] 补齐 {n} 个 key")
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
