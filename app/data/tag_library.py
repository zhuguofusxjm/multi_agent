"""套餐设计标签库"""

TAG_LIBRARY = [
    {"id": "T001", "name": "高流量", "category": "流量", "description": "适合月均流量>10GB的用户"},
    {"id": "T002", "name": "无限流量", "category": "流量", "description": "不限量流量套餐"},
    {"id": "T003", "name": "视频场景", "category": "场景", "description": "视频观看为主要场景"},
    {"id": "T004", "name": "游戏场景", "category": "场景", "description": "手游为主要使用场景"},
    {"id": "T005", "name": "商务场景", "category": "场景", "description": "商务通话和数据使用"},
    {"id": "T006", "name": "年轻人群", "category": "人群", "description": "18-30岁目标人群"},
    {"id": "T007", "name": "家庭共享", "category": "人群", "description": "家庭多成员共享"},
    {"id": "T008", "name": "银发人群", "category": "人群", "description": "60岁以上老年用户"},
    {"id": "T009", "name": "低价策略", "category": "价格", "description": "月费<50元的低价位"},
    {"id": "T010", "name": "中端定价", "category": "价格", "description": "月费50-150元中价位"},
    {"id": "T011", "name": "高端定价", "category": "价格", "description": "月费>150元高价位"},
    {"id": "T012", "name": "5G专属", "category": "网络", "description": "5G网络专属权益"},
    {"id": "T013", "name": "宽带融合", "category": "融合", "description": "手机+宽带融合套餐"},
    {"id": "T014", "name": "会员权益", "category": "增值", "description": "视频/音乐等会员权益"},
    {"id": "T015", "name": "语音主导", "category": "通话", "description": "大量通话需求"},
]

TAG_LIBRARY_TEXT = "\n".join(
    f"- {t['id']} {t['name']}({t['category']}): {t['description']}"
    for t in TAG_LIBRARY
)
