def point_in_fence(x: float, y: float, fence: list[tuple[float, float]]) -> bool:
    """判断点 (x, y) 是否在多边形 fence 内部。射线法，边界点视为外部。

    Args:
        x: 点的 x 坐标（经度）
        y: 点的 y 坐标（纬度）
        fence: 多边形顶点列表，每个顶点是 (x, y) 元组

    Returns:
        True 如果点在多边形内部
    """
    if not fence or len(fence) < 3:
        return False
    n = len(fence)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = fence[i]
        xj, yj = fence[j]
        # 射线法：判断水平射线是否穿过当前边
        if ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
        ):
            inside = not inside
        j = i
    return inside
