<template>
  <section class="page" data-module="task">
    <header class="page-head">
      <div>
        <h2>检测任务管理</h2>
        <p class="page-desc">状态沿 待分配 → 待检测 → 检测中 → 已完成 逐级流转；检测中可挂起并恢复，更换执行人员须回退待分配并写明原因，已完成只能由复核人退回。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记检测任务</button>
        <button class="btn" type="button" @click="exportRows">导出检测任务清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>任务编号</span>
        <input v-model="keyword" placeholder="按任务编号检索" />
      </label>
      <label class="filter-item">
        <span>任务状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
            <button
              v-for="action in rowActions(row)"
              :key="action"
              class="link"
              type="button"
              @click="openAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无检测任务数据，可先登记检测任务</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条检测任务记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="actionDialog" class="modal-mask" @click.self="closeAction">
      <div class="modal-box">
        <h3>{{ actionDialog.action }} · {{ actionDialog.row['任务编号'] }}</h3>
        <label v-for="field in actionFields(actionDialog.action)" :key="field.key" class="modal-field">
          <span>{{ field.label }}<em>*</em></span>
          <input v-model="actionDialog.values[field.key]" :placeholder="`请填写${field.label}`" />
        </label>
        <label class="modal-field">
          <span>操作人</span>
          <input v-model="actionDialog.values['操作人']" placeholder="留空则记为系统" />
        </label>
        <label class="modal-field">
          <span>备注</span>
          <input v-model="actionDialog.remark" placeholder="补充说明（可选）" />
        </label>
        <p v-if="actionDialog.error" class="error-text">{{ actionDialog.error }}</p>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="confirmAction">确认{{ actionDialog.action }}</button>
          <button class="btn ghost" type="button" @click="closeAction">取消</button>
        </div>
      </div>
    </div>

    <div v-if="createDialog" class="modal-mask" @click.self="createDialog = null">
      <div class="modal-box">
        <h3>登记检测任务</h3>
        <label v-for="field in createFields" :key="field.key" class="modal-field">
          <span>{{ field.label }}<em v-if="field.required">*</em></span>
          <input v-model="createDialog.values[field.key]" :placeholder="`请填写${field.label}`" />
        </label>
        <p class="modal-hint">登记后初始状态为「待分配」，分配执行人员后进入「待检测」。</p>
        <p v-if="createDialog.error" class="error-text">{{ createDialog.error }}</p>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="confirmCreate">确认登记</button>
          <button class="btn ghost" type="button" @click="createDialog = null">取消</button>
        </div>
      </div>
    </div>

    <div v-if="detail" class="modal-mask" @click.self="detail = null">
      <div class="modal-box wide">
        <h3>检测任务详情 · {{ detail.row['任务编号'] }}</h3>
        <dl class="detail-grid">
          <template v-for="column in columns" :key="column">
            <dt>{{ column }}</dt>
            <dd>{{ detail.row[column] ?? '—' }}</dd>
          </template>
        </dl>
        <h4>流转记录</h4>
        <table class="data-table">
          <thead>
            <tr><th>时间</th><th>动作</th><th>操作人</th><th>备注</th><th>结果状态</th></tr>
          </thead>
          <tbody>
            <tr v-for="(log, index) in detail.logs" :key="index">
              <td>{{ log['时间'] }}</td>
              <td>{{ log['动作'] }}</td>
              <td>{{ log['操作人'] }}</td>
              <td>{{ log['备注'] || '—' }}</td>
              <td>{{ log['结果状态'] }}</td>
            </tr>
            <tr v-if="!detail.logs.length">
              <td colspan="5" class="empty-state">暂无流转记录</td>
            </tr>
          </tbody>
        </table>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="detail = null">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, any>

const ENDPOINT = '/api/task'
const columns = ["任务编号", "关联样品", "检测项目", "检测方法", "标准编号", "执行人员", "计划完成日", "任务状态"]
const statuses = ["待分配", "待检测", "检测中", "已挂起", "已完成"]

// 各动作需要随附填写的必填信息，与后端 ACTION_RULES 的 inputs 对应。
const ACTION_FIELDS: Record<string, { key: string; label: string }[]> = {
  分配任务: [{ key: '执行人员', label: '执行人员' }],
  挂起: [{ key: '挂起原因', label: '挂起原因' }],
  更换执行人员: [
    { key: '新执行人员', label: '新执行人员' },
    { key: '更换原因', label: '更换原因' },
  ],
  复核退回: [
    { key: '复核人', label: '复核人' },
    { key: '退回原因', label: '退回原因' },
  ],
}

// 后端没下发「可执行动作」时按状态兜底，保证两个页面口径一致。
const STATUS_ACTIONS: Record<string, string[]> = {
  待分配: ['分配任务'],
  待检测: ['开始检测', '更换执行人员'],
  检测中: ['提交结果', '挂起', '更换执行人员'],
  已挂起: ['恢复检测', '更换执行人员'],
  已完成: ['复核退回'],
}

const createFields = [
  { key: '任务编号', label: '任务编号', required: true },
  { key: '关联样品', label: '关联样品', required: true },
  { key: '检测项目', label: '检测项目', required: true },
  { key: '检测方法', label: '检测方法', required: false },
  { key: '标准编号', label: '标准编号', required: false },
  { key: '执行人员', label: '执行人员', required: false },
  { key: '计划完成日', label: '计划完成日', required: false },
]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')
const stats = ref([
  { label: '待分配任务', status: '待分配', value: 0 },
  { label: '检测中任务', status: '检测中', value: 0 },
  { label: '已完成任务', status: '已完成', value: 0 },
])

const actionDialog = ref<{ action: string; row: Row; values: Record<string, string>; remark: string; error: string } | null>(null)
const createDialog = ref<{ values: Record<string, string>; error: string } | null>(null)
const detail = ref<{ row: Row; logs: Row[] } | null>(null)

function rowActions(row: Row): string[] {
  const fromBackend = row['可执行动作']
  if (Array.isArray(fromBackend)) {
    return fromBackend
  }
  return STATUS_ACTIONS[String(row['任务状态'] ?? '')] ?? []
}

function actionFields(action: string) {
  return ACTION_FIELDS[action] ?? []
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createDialog.value = { values: {}, error: '' }
}

function openAction(action: string, row: Row) {
  actionDialog.value = { action, row, values: {}, remark: '', error: '' }
}

function closeAction() {
  actionDialog.value = null
}

async function confirmAction() {
  const dialog = actionDialog.value
  if (!dialog) {
    return
  }
  const missing = actionFields(dialog.action).filter((field) => !String(dialog.values[field.key] ?? '').trim())
  if (missing.length) {
    dialog.error = `请先填写：${missing.map((field) => field.label).join('、')}`
    return
  }
  try {
    const response = await request(`${ENDPOINT}/${dialog.row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({
        values: { action: dialog.action, ...dialog.values },
        remark: dialog.remark || null,
      }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? payload.detail ?? '检测任务动作未生效，请稍后重试')
    }
    closeAction()
    await reload()
    if (detail.value && detail.value.row.id === dialog.row.id) {
      await openDetail(dialog.row)
    }
  } catch (error) {
    dialog.error = error instanceof Error ? error.message : '检测任务操作失败'
  }
}

async function confirmCreate() {
  const dialog = createDialog.value
  if (!dialog) {
    return
  }
  const missing = createFields.filter((field) => field.required && !String(dialog.values[field.key] ?? '').trim())
  if (missing.length) {
    dialog.error = `请先填写：${missing.map((field) => field.label).join('、')}`
    return
  }
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: dialog.values }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? payload.detail ?? '检测任务登记失败')
    }
    createDialog.value = null
    await reload()
  } catch (error) {
    dialog.error = error instanceof Error ? error.message : '检测任务登记失败'
  }
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('检测任务详情读取失败')
    }
    const payload = await response.json()
    detail.value = { row: payload, logs: payload['流转记录'] ?? [] }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检测任务详情读取失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value.trim()) {
    query.set('keyword', keyword.value.trim())
  }
  if (statusFilter.value) {
    query.set('status', statusFilter.value)
  }
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('检测任务列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    for (const stat of stats.value) {
      stat.value = rows.value.filter((row) => row['任务状态'] === stat.status).length
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检测任务列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
}
.modal-box {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px;
  width: 420px;
  max-width: 92vw;
  max-height: 85vh;
  overflow: auto;
}
.modal-box.wide {
  width: 680px;
}
.modal-box h3 {
  margin: 0 0 12px;
  font-size: 15px;
}
.modal-box h4 {
  margin: 12px 0 8px;
  font-size: 13px;
}
.modal-field {
  display: block;
  margin-bottom: 10px;
  font-size: 13px;
}
.modal-field span {
  display: block;
  color: var(--muted);
  margin-bottom: 4px;
}
.modal-field em {
  color: #b42318;
  font-style: normal;
}
.modal-field input {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
}
.modal-hint {
  color: var(--muted);
  font-size: 12px;
}
.modal-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 12px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 96px 1fr 96px 1fr;
  gap: 6px 10px;
  font-size: 13px;
  margin: 0;
}
.detail-grid dt {
  color: var(--muted);
}
.detail-grid dd {
  margin: 0;
}
.filter-item select {
  padding: 5px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
}
</style>
