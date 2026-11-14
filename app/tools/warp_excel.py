"""Excel consumes the same five-star model as the HTML page, not another counter."""
from module.localization import tr
from .warp_manual import gold_rows, manual_data, pool_names, pool_summary


def export_excel(data, path):
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    detail = wb.active
    detail.title = tr('原始明细')
    detail.append([tr('时间'), tr('名称'), tr('类别'), tr('星级'), tr('卡池'), tr('总次数'), tr('保底内（明细）')])
    counters, seen = {}, set()
    names = pool_names()
    for total, record in enumerate(sorted(data['list'], key=lambda r: int(r['id'])), 1):
        pool = record['gacha_type']
        counters[pool] = counters.get(pool, 0) + 1
        pity = counters[pool] if pool in seen else '≥' + str(counters[pool])
        detail.append([record['time'], record['name'], record['item_type'], record['rank_type'], names[pool], total, pity])
        if record['rank_type'] == '5':
            counters[pool] = 0
            seen.add(pool)
        color = 'FFA500' if record['rank_type'] == '5' else '800080' if record['rank_type'] == '4' else '000000'
        for cell in detail[detail.max_row]:
            cell.font = Font(color=color)

    history = wb.create_sheet(tr('五星统计'))
    history.append([tr('卡池'), tr('名称'), tr('时间'), tr('原始抽数'), tr('统计抽数'), tr('来源')])
    for row in gold_rows(data, include_orphans=True):
        record = row['record']
        observed = None if row['orphan'] else ('≥' + str(row['observed']) if row['bounded'] else row['observed'])
        source = tr('原记录已变化（未统计）') if row['orphan'] else tr('手填更正') if row['corrected'] else tr('原始明细')
        history.append([names[record['gacha_type']], record['name'], record['time'], observed,
                        row['pity'] if not row['orphan'] else None, source])
    for entry in manual_data(data)['entries']:
        history.append([names[entry['pool']], entry['name'], entry['date'], None, entry['pity'], tr('手动补充')])

    summary = wb.create_sheet(tr('统计说明'))
    summary.append([tr('统计基于已保存的明细；历史可能不完整。每池首个五星的原始抽数仅为下限，不计入平均值。')])
    summary.append([tr('手填内容单独标注，不补造逐抽明细，也不计入明细总抽数和星级占比。找回明细后，请自行核对并删除重复的手填项。')])
    summary.append([tr('空白抽数或时间表示未知。Excel 用于查看，完整恢复请使用小助手备份。')])
    summary.append([tr('卡池'), tr('明细抽数'), tr('手填五星'), tr('已知抽数五星'), tr('抽数不明五星'), tr('五星平均出货次数为')])
    for pool, name in names.items():
        stats = pool_summary(data, pool)
        summary.append([name, len(stats['records']), len(stats['entries']), stats['known'], stats['unknown'], stats['average']])
    for sheet in wb:
        sheet.freeze_panes = 'A2'
        for row in sheet:
            for cell in row:
                # User-supplied item names must be text, not spreadsheet formulas.
                if isinstance(cell.value, str):
                    cell.data_type = 's'
        for column in sheet.columns:
            width = max(sum(2 if ord(c) > 255 else 1 for c in str(cell.value or '')) for cell in column)
            sheet.column_dimensions[get_column_letter(column[0].column)].width = min(width + 2, 60)
    for row in range(1, 4):
        summary.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        summary.cell(row, 1).alignment = Alignment(wrap_text=True, vertical='top')
        summary.row_dimensions[row].height = 45
    summary.freeze_panes = 'A5'
    wb.save(path)
