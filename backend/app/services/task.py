"""检测任务业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "task"
REQUIRED_FIELDS = ["任务编号", "关联样品", "检测项目"]
PROFILE_FIELDS = ["任务编号", "关联样品", "检测项目", "检测方法", "标准编号", "执行人员", "计划完成日"]

STATUS_ORDER = ["待分配", "待检测", "检测中", "已完成"]
SUSPENDED_STATUS = "已挂起"
FINAL_STATUS = STATUS_ORDER[-1]

# 每个动作声明允许的起始状态、目标状态与随附必填信息：
# 正向动作只能沿 待分配→待检测→检测中→已完成 逐级推进，不允许跳级；
# 挂起/恢复是检测中的旁路；更换执行人员一律回退到待分配；复核退回把已完成打回检测中。
ACTION_RULES: dict[str, dict[str, Any]] = {
    "分配任务": {"from": ["待分配"], "to": "待检测", "inputs": {"执行人员": "分配任务时要写明执行人员"}},
    "开始检测": {"from": ["待检测"], "to": "检测中", "inputs": {}},
    "提交结果": {"from": ["检测中"], "to": "已完成", "inputs": {}},
    "挂起": {"from": ["检测中"], "to": SUSPENDED_STATUS, "inputs": {"挂起原因": "挂起时要写明挂起原因"}},
    "恢复检测": {"from": [SUSPENDED_STATUS], "to": "检测中", "inputs": {}},
    "更换执行人员": {
        "from": ["待检测", "检测中", SUSPENDED_STATUS],
        "to": "待分配",
        "inputs": {"新执行人员": "更换执行人员时要写清新执行人员", "更换原因": "更换执行人员时要写清更换原因"},
    },
    "复核退回": {
        "from": ["已完成"],
        "to": "检测中",
        "inputs": {"复核人": "退回时要写明复核人", "退回原因": "退回时要写明退回原因"},
    },
}

# 会让任务被标记为异常、需要跟进的动作。
NEGATIVE_ACTIONS = ["挂起", "复核退回"]

# 复核退回时保持不变的字段：计划完成日与检测方法沿用原计划。
RETURN_FROZEN_FIELDS = ["计划完成日", "检测方法"]

# 备注取值优先级：专属原因字段 > 随附备注。
REASON_FIELDS = ["更换原因", "挂起原因", "退回原因"]


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
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("任务编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._with_actions(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        return self._with_actions(row) if row is not None else None

    def create_entry(self, values: dict[str, Any], remark: str | None = None) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in PROFILE_FIELDS:
            text = str(values.get(field) or "").strip()
            if text:
                entry[field] = text
        entry["status"] = STATUS_ORDER[0]
        entry["任务状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["流转记录"] = [self._log("登记任务", values, remark, STATUS_ORDER[0])]
        rows.append(entry)
        return self._with_actions(entry), []

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
        remark: str | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        values = dict(values or {})
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"检测任务 {entry_id} 不存在或已归档"
        rule = ACTION_RULES.get(action)
        if rule is None:
            return None, f"动作「{action}」不属于检测任务可执行范围"
        current = str(entry.get("status") or "")
        if current not in rule["from"]:
            allowed = "、".join(self._allowed_actions(current)) or "无"
            return None, f"当前状态为「{current}」，不能执行「{action}」，可执行动作：{allowed}"
        missing = [label for field, label in rule["inputs"].items() if not str(values.get(field) or "").strip()]
        if missing:
            return None, "；".join(missing)

        if action == "分配任务":
            entry["执行人员"] = str(values["执行人员"]).strip()
        elif action == "更换执行人员":
            # 更换执行人员必须先回退到待分配，更换原因随流转记录留痕。
            entry["执行人员"] = str(values["新执行人员"]).strip()

        target = rule["to"]
        if action == "复核退回":
            # 退回只改状态，计划完成日与检测方法沿用原计划。
            for field in RETURN_FROZEN_FIELDS:
                values.pop(field, None)
        entry["status"] = target
        entry["任务状态"] = target  # 列表页与详情页都读这个展示字段，保持一致
        entry["pending"] = target != FINAL_STATUS
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        entry.setdefault("流转记录", []).append(self._log(action, values, remark, target))
        return self._with_actions(entry), f"检测任务已{action}"

    @staticmethod
    def _allowed_actions(status: str) -> list[str]:
        return [name for name, rule in ACTION_RULES.items() if status in rule["from"]]

    def _with_actions(self, row: dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        data["可执行动作"] = self._allowed_actions(str(row.get("status") or ""))
        return data

    @staticmethod
    def _log(action: str, values: dict[str, Any], remark: str | None, status: str) -> dict[str, Any]:
        note = ""
        for field in REASON_FIELDS:
            if str(values.get(field) or "").strip():
                note = str(values[field]).strip()
                break
        if not note and remark:
            note = str(remark).strip()
        operator = str(values.get("操作人") or values.get("复核人") or "").strip() or "系统"
        return {
            "时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "动作": action,
            "操作人": operator,
            "备注": note,
            "结果状态": status,
        }
