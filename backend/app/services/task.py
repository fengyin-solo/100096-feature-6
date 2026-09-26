"""检测任务业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "task"
REQUIRED_FIELDS = ["任务编号", "关联样品", "检测项目"]
ENTRY_FIELDS = ["任务编号", "关联样品", "检测项目", "检测方法", "标准编号", "执行人员", "计划完成日"]
STATUS_ORDER = ["待分配", "待检测", "检测中", "已完成"]
SUSPENDED_STATUS = "已挂起"
STATUSES = STATUS_ORDER + [SUSPENDED_STATUS]

# 主线依次流转：待分配 → 待检测 → 检测中 → 已完成，不允许跳级；
# 挂起/恢复是检测中的旁路，退回重派与复核退回是仅有的两条回退入口。
ACTION_RULES: dict[str, dict[str, Any]] = {
    "分配任务": {"from": {"待分配"}, "to": "待检测"},
    "开始检测": {"from": {"待检测"}, "to": "检测中"},
    "提交结果": {"from": {"检测中"}, "to": "已完成"},
    "挂起任务": {"from": {"检测中"}, "to": SUSPENDED_STATUS},
    "恢复检测": {"from": {SUSPENDED_STATUS}, "to": "检测中"},
    "退回重派": {"from": {"待检测", "检测中", SUSPENDED_STATUS}, "to": "待分配"},
    "复核退回": {"from": {"已完成"}, "to": "检测中"},
}
ACTION_MESSAGES = {
    "分配任务": "任务已分配，进入待检测",
    "开始检测": "检测已开始",
    "提交结果": "结果已提交，检测任务完成",
    "挂起任务": "任务已挂起，可通过「恢复检测」继续",
    "恢复检测": "任务已恢复，回到检测中",
    "退回重派": "已退回待分配，重新分配时请填写执行人员",
    "复核退回": "复核人已退回，任务回到检测中",
}
ABNORMAL_STATUSES = {SUSPENDED_STATUS}
DEFAULT_OPERATOR = "值班管理员"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class TaskService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        for row in rows:
            self._sync_status_field(row)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("任务编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is not None:
            self._sync_status_field(entry)
        return entry

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in ENTRY_FIELDS:
            value = values.get(field)
            if value is not None and str(value).strip():
                entry[field] = str(value).strip()
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["history"] = []
        self._sync_status_field(entry)
        operator = str(values.get("操作人") or "").strip() or DEFAULT_OPERATOR
        self._append_history(
            entry,
            action="登记任务",
            operator=operator,
            from_status="—",
            to_status=STATUS_ORDER[0],
            remark="任务编号建立，等待分配",
        )
        rows.append(entry)
        return entry, []

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
        remark: str | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"检测任务 {entry_id} 不存在或已归档"
        rule = ACTION_RULES.get(action)
        if rule is None:
            return None, f"动作「{action}」不属于检测任务可执行范围"
        current = str(entry.get("status") or STATUS_ORDER[0])
        if current not in rule["from"]:
            allowed = "、".join(sorted(rule["from"], key=lambda s: STATUSES.index(s)))
            return None, f"当前状态为「{current}」，只有在「{allowed}」状态下才能执行「{action}」"

        values = values or {}
        note = str(remark or "").strip()
        operator = str(values.get("操作人") or "").strip() or DEFAULT_OPERATOR

        if action == "分配任务":
            assignee = str(values.get("执行人员") or "").strip()
            if not assignee:
                return None, "分配任务前请先填写执行人员"
            previous = str(entry.get("执行人员") or "").strip()
            entry["执行人员"] = assignee
            if previous and previous != assignee and not note:
                note = f"由 {previous} 交接给 {assignee}"
        elif action == "退回重派":
            reason = str(values.get("更换原因") or "").strip() or note
            if not reason:
                return None, "更换执行人员必须先退回待分配，并填写更换原因"
            note = f"更换原因：{reason}"
        elif action == "复核退回":
            reviewer = str(values.get("复核人") or "").strip()
            if not reviewer:
                return None, "已完成的检测任务须由复核人退回，请填写复核人"
            if not note:
                return None, "复核退回必须填写退回原因"
            entry["复核人"] = reviewer
            note = f"复核人 {reviewer} 退回：{note}"
            # 复核退回只回退状态：计划完成日与检测方法保持原值，不在此动作里改动。

        target = rule["to"]
        self._append_history(
            entry,
            action=action,
            operator=operator,
            from_status=current,
            to_status=target,
            remark=note,
        )
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = target in ABNORMAL_STATUSES
        self._sync_status_field(entry)
        return entry, ACTION_MESSAGES.get(action, f"检测任务已{action}")

    def _append_history(
        self,
        entry: dict[str, Any],
        *,
        action: str,
        operator: str,
        from_status: str,
        to_status: str,
        remark: str,
    ) -> None:
        history = entry.setdefault("history", [])
        history.append({
            "时间": _now(),
            "操作人": operator,
            "动作": action,
            "从状态": from_status,
            "到状态": to_status,
            "备注": remark or "—",
        })

    def _sync_status_field(self, entry: dict[str, Any]) -> None:
        """让「任务状态」字段始终等于内部 status，列表页与详情页看到的才是同一个状态。"""
        entry["任务状态"] = str(entry.get("status") or STATUS_ORDER[0])
