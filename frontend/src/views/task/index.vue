<template>
  <section class="page" data-module="task">
    <header class="page-head">
      <div>
        <h2>检测任务管理</h2>
        <p class="page-desc">任务编号建立后从待分配依次流转到待检测、检测中，最后完成；检测中可挂起恢复，更换执行人员须先退回待分配并写明原因。</p>
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
          <option v-for="status in STATUSES" :key="status" :value="status">{{ status }}</option>
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
          <td v-for="column in columns" :key="column">
            <RouterLink v-if="column === '任务编号'" :to="`/task/${row.id}`">{{ row[column] ?? '—' }}</RouterLink>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td class="row-actions">
            <button
              v-for="action in actionsFor(row.status)"
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

    <ActionDialog
      v-if="activeAction && activeRow"
      :action="activeAction"
      :task-label="String(activeRow.任务编号 ?? activeRow.id)"
      @cancel="closeAction"
      @submit="submitAction"
    />

    <div v-if="createVisible" class="dialog-mask" @click.self="createVisible = false">
      <div class="dialog-card">
        <h3 class="dialog-title">登记检测任务</h3>
        <p class="dialog-desc">登记后任务进入待分配，再依次流转。</p>
        <label v-for="field in createFields" :key="field.key" class="dialog-field">
          <span>
            {{ field.label }}
            <em v-if="field.required" class="required-mark">*</em>
          </span>
          <input v-model="createForm[field.key]" :placeholder="`请填写${field.label}`" />
        </label>
        <p v-if="createError" class="error-text">{{ createError }}</p>
        <div class="dialog-actions">
          <button class="btn primary" type="button" @click="submitCreate">确认登记</button>
          <button class="btn ghost" type="button" @click="createVisible = false">取消</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

import ActionDialog from './ActionDialog.vue'
import { STATUSES, actionsFor } from './taskFlow'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/task'
const columns = ["任务编号", "关联样品", "检测项目", "检测方法", "标准编号", "执行人员", "计划完成日", "任务状态"]
const createFields = [
  { key: '任务编号', label: '任务编号', required: true },
  { key: '关联样品', label: '关联样品', required: true },
  { key: '检测项目', label: '检测项目', required: true },
  { key: '检测方法', label: '检测方法', required: false },
  { key: '标准编号', label: '标准编号', required: false },
  { key: '计划完成日', label: '计划完成日', required: false },
]

const session = useSessionStore()

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')

const statusCounts = ref<Record<string, number>>({})
const stats = computed(() => STATUSES.map((status) => ({ label: `${status}任务`, value: statusCounts.value[status] ?? 0 })))

const activeAction = ref('')
const activeRow = ref<Row | null>(null)

const createVisible = ref(false)
const createForm = ref<Record<string, string>>({})
const createError = ref('')

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = {}
  createError.value = ''
  createVisible.value = true
}

function openAction(action: string, row: Row) {
  activeAction.value = action
  activeRow.value = row
}

function closeAction() {
  activeAction.value = ''
  activeRow.value = null
}

async function submitAction(payload: { values: Record<string, string>; remark: string }) {
  if (!activeRow.value) return
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${activeRow.value.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({
        values: { action: activeAction.value, 操作人: session.operator, ...payload.values },
        remark: payload.remark,
      }),
    })
    const result = await response.json()
    if (!response.ok || !result.ok) {
      throw new Error(result.message ?? result.detail ?? '检测任务动作未生效，请稍后重试')
    }
    closeAction()
    await Promise.all([reload(), loadStats()])
  } catch (error) {
    closeAction()
    errorMessage.value = error instanceof Error ? error.message : '检测任务操作失败'
  }
}

async function submitCreate() {
  createError.value = ''
  for (const field of createFields) {
    if (field.required && !(createForm.value[field.key] ?? '').trim()) {
      createError.value = `请先填写${field.label}`
      return
    }
  }
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { 操作人: session.operator, ...createForm.value } }),
    })
    const result = await response.json()
    if (!response.ok || !result.ok) {
      throw new Error(result.message ?? result.detail ?? '检测任务登记失败')
    }
    createVisible.value = false
    await Promise.all([reload(), loadStats()])
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '检测任务登记失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value.trim()) query.set('keyword', keyword.value.trim())
  if (statusFilter.value) query.set('status', statusFilter.value)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('检测任务列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检测任务列表读取失败'
  }
}

async function loadStats() {
  try {
    const response = await request(`${ENDPOINT}?size=200`)
    if (!response.ok) return
    const payload = await response.json()
    const counts: Record<string, number> = {}
    for (const item of payload.items ?? []) {
      const status = String(item.status ?? '')
      counts[status] = (counts[status] ?? 0) + 1
    }
    statusCounts.value = counts
  } catch {
    // 统计卡片加载失败不阻塞列表本身
  }
}

onMounted(() => {
  void reload()
  void loadStats()
})
</script>
