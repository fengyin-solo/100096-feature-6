/** 检测任务状态流转的前端口径：每个状态能点哪些动作、每个动作要填什么，都收在这里，
 * 列表页与详情页共用同一份配置，保证两边看到的状态与可执行动作一致。 */

export interface ActionInput {
  key: string
  label: string
  required: boolean
  placeholder?: string
  /** 为 true 时该字段作为整条动作的备注提交，而不是塞进 values */
  isRemark?: boolean
}

export const STATUSES = ['待分配', '待检测', '检测中', '已挂起', '已完成']

export const ACTIONS_BY_STATUS: Record<string, string[]> = {
  待分配: ['分配任务'],
  待检测: ['开始检测', '退回重派'],
  检测中: ['提交结果', '挂起任务', '退回重派'],
  已挂起: ['恢复检测', '退回重派'],
  已完成: ['复核退回'],
}

export const ACTION_INPUTS: Record<string, ActionInput[]> = {
  分配任务: [
    { key: '执行人员', label: '执行人员', required: true, placeholder: '必填：填写接手检测的人员' },
    { key: 'remark', label: '分配备注', required: false, isRemark: true, placeholder: '可写明交接事项' },
  ],
  开始检测: [
    { key: 'remark', label: '备注', required: false, isRemark: true },
  ],
  提交结果: [
    { key: 'remark', label: '结果摘要', required: false, isRemark: true, placeholder: '可填写检测结果要点' },
  ],
  挂起任务: [
    { key: 'remark', label: '挂起原因', required: false, isRemark: true, placeholder: '说明挂起原因，恢复时便于衔接' },
  ],
  恢复检测: [
    { key: 'remark', label: '恢复说明', required: false, isRemark: true },
  ],
  退回重派: [
    { key: '更换原因', label: '更换原因', required: true, placeholder: '必填：说明更换执行人员的原因' },
  ],
  复核退回: [
    { key: '复核人', label: '复核人', required: true, placeholder: '必填：填写复核人姓名' },
    { key: 'remark', label: '退回原因', required: true, isRemark: true, placeholder: '必填：说明退回修改的原因' },
  ],
}

export function actionsFor(status: unknown): string[] {
  return ACTIONS_BY_STATUS[String(status ?? '')] ?? []
}
