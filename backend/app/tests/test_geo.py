from app.services.geo import point_in_fence


def test_point_inside_square_fence():
    fence = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_fence(5, 5, fence) is True


def test_point_outside_square_fence():
    fence = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_fence(15, 5, fence) is False
    assert point_in_fence(-1, 5, fence) is False
    assert point_in_fence(5, 11, fence) is False


def test_point_near_edge_outside():
    """明确在边界外的点（不是恰好在线上，避免边界歧义）。"""
    fence = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_fence(5, -0.5, fence) is False  # 底边下方
    assert point_in_fence(-0.5, 5, fence) is False  # 左边左侧


def test_point_inside_triangle():
    """三角形顶点 (0,0)(10,0)(5,10)，y=1 时覆盖 x∈[0.5, 9.5]。"""
    fence = [(0, 0), (10, 0), (5, 10)]
    assert point_in_fence(5, 3, fence) is True
    assert point_in_fence(5, 8, fence) is True
    assert point_in_fence(8, 1, fence) is True  # 在内部（x∈[0.5,9.5]）
    assert point_in_fence(0.1, 1, fence) is False  # 左外（x<0.5）
    assert point_in_fence(9.9, 1, fence) is False  # 右外（x>9.5）
    assert point_in_fence(5, 10.5, fence) is False  # 顶点上方


def test_empty_fence():
    assert point_in_fence(5, 5, []) is False


def test_fence_too_small():
    assert point_in_fence(5, 5, [(0, 0), (1, 1)]) is False


def test_real_geo_fence():
    """模拟国家博物馆围栏（经纬度）。注意 point_in_fence(x=lng, y=lat)。"""
    fence = [
        (116.404, 39.904),  # (lng, lat)
        (116.410, 39.904),
        (116.410, 39.908),
        (116.404, 39.908),
    ]
    assert point_in_fence(116.407, 39.906, fence) is True  # 馆内
    assert point_in_fence(116.420, 39.906, fence) is False  # 馆外东侧
    assert point_in_fence(116.407, 39.900, fence) is False  # 馆外南侧
