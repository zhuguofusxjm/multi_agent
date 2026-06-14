"""套餐设计案例库"""

CASE_LIBRARY = [
    {
        "id": "C001",
        "name": "5G青春版畅享套餐",
        "tags": ["T006", "T001", "T012", "T010", "T003"],
        "monthly_fee": 99,
        "data_gb": 30,
        "voice_min": 200,
        "highlights": "针对年轻人的5G入门套餐，含视频会员权益",
        "province": "广东",
    },
    {
        "id": "C002",
        "name": "5G畅享199套餐",
        "tags": ["T002", "T012", "T011", "T005"],
        "monthly_fee": 199,
        "data_gb": 60,
        "voice_min": 1000,
        "highlights": "商务人士首选，流量充足+通话无忧",
        "province": "全国",
    },
    {
        "id": "C003",
        "name": "家庭融合399套餐",
        "tags": ["T007", "T013", "T002", "T011"],
        "monthly_fee": 399,
        "data_gb": 100,
        "voice_min": 2000,
        "highlights": "全家共享，含千兆宽带+IPTV",
        "province": "全国",
    },
    {
        "id": "C004",
        "name": "银发关怀套餐",
        "tags": ["T008", "T009", "T015"],
        "monthly_fee": 29,
        "data_gb": 2,
        "voice_min": 500,
        "highlights": "老年人专属，大字体界面+亲情通话",
        "province": "北京",
    },
    {
        "id": "C005",
        "name": "电竞畅玩套餐",
        "tags": ["T004", "T006", "T001", "T012", "T010"],
        "monthly_fee": 129,
        "data_gb": 40,
        "voice_min": 100,
        "highlights": "游戏专属加速+电竞赛事权益",
        "province": "上海",
    },
]


def search_cases(tags: list[str], top_k: int = 3) -> list[dict]:
    """根据标签列表检索最匹配的案例"""
    scored = []
    for case in CASE_LIBRARY:
        overlap = len(set(tags) & set(case["tags"]))
        if overlap > 0:
            scored.append((overlap, case))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [case for _, case in scored[:top_k]]
