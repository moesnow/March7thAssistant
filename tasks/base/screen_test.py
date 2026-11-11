from collections import deque
from module.config.platform import get_ui_profile
from module.screen import screen
from module.logger import log


SKIP_SCREENS = {"incoming_message", "achievement"}


def run():
    """界面可切换性测试：以最短路径遍历所有可达界面"""
    switchable = screen.get_switchable_screens("main", include_start=False)
    touch = get_ui_profile().name == "touch_720"
    target_ids = [sid for sid, _ in switchable if touch or sid not in SKIP_SCREENS]

    log.info(f"共 {len(target_ids)} 个待测界面")

    # BFS 预计算从各节点到全图的最短步数
    all_nodes = ["main"] + target_ids
    dist_from = {node: _bfs_step_count(node) for node in all_nodes}

    # 贪心最近邻排序
    order = _greedy_nearest_neighbor(target_ids, dist_from)

    log.info(f"测试顺序：{' -> '.join(screen.get_name(sid) for sid in order)}")

    # 逐个切换并验证
    screen.change_to("main")
    log.info("已验证起点：主界面")
    success_count = 0
    fail_count = 0

    for i, target in enumerate(order):
        route = screen.find_shortest_path(screen.current_screen, target) or []
        route_names = " → ".join(screen.get_name(node) for node in route)
        name = screen.get_name(target)
        try:
            screen.change_to(target)
            log.info(f"[{i + 1}/{len(target_ids)}] {name} 成功（{route_names}）")
            success_count += 1
        except Exception as e:
            log.error(f"[{i + 1}/{len(target_ids)}] {name} 失败（{route_names}）：{e}")
            fail_count += 1
            # 尝试回到 main 继续
            try:
                screen.change_to("main")
            except Exception:
                log.error("无法回到主界面，测试终止")
                break

    if screen.current_screen != "main":
        try:
            screen.change_to("main")
            log.info("已验证返回主界面")
        except Exception as error:
            log.error(f"测试结束后无法返回主界面：{error}")
            return False
    pending = len(target_ids) - success_count - fail_count
    log.info(f"测试完成，成功 {success_count} 页，失败 {fail_count} 页，未测 {pending} 页")
    return fail_count == 0 and pending == 0


def _bfs_step_count(start):
    """从 start 出发，返回到所有可达节点的最短步数"""
    dist = {start: 0}
    queue = deque([start])
    while queue:
        cur = queue.popleft()
        for action in screen.screen_map[cur]['actions']:
            nxt = action["target_screen"]
            if nxt not in dist and nxt in screen.screen_map:
                dist[nxt] = dist[cur] + 1
                queue.append(nxt)
    return dist


def _greedy_nearest_neighbor(target_ids, dist_from):
    """贪心最近邻：每次选择从当前界面出发步数最少的未访问界面"""
    visited = set()
    order = []
    current = "main"
    visited.add(current)

    for _ in range(len(target_ids)):
        best_target = None
        best_dist = float('inf')
        for t in target_ids:
            if t in visited:
                continue
            d = dist_from[current].get(t, float('inf'))
            if d < best_dist:
                best_dist = d
                best_target = t
        if best_target is None:
            log.warning("存在不可达界面，跳过剩余")
            break
        visited.add(best_target)
        order.append(best_target)
        current = best_target

    return order
