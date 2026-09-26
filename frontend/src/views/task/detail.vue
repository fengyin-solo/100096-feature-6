<template>
  <section class="page" data-module="task-detail">
    <header class="page-head">
      <div>
        <h2>检测任务详情</h2>
        <p class="page-desc">任务状态与列表页同源一致；每次流转都记录操作人、时间与备注，交接后可直接查看上一步操作。</p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn ghost" to="/task">返回任务列表</RouterLink>
      </div>
    </header>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <template v-if="entry">
      <div class="detail-status">
        <span class="status-badge">{{ entry.status }}</span>
        <span v-if="lastHistory" class="last-op">
          上一步：{{ lastHistory.时间 }} · {{ lastHistory.操作人 }} · {{ lastHistory.动作 }}
          <template v-if="lastHistory.备注 && lastHistory.备注 !== '—'">（{{ lastHistory.备注 }}）</template>
        </span>
      </div>

      <div class="detail-grid">
        <div v-for="field in displayFields" :key="field" class="detail-item">
          <span class="detail-label">{{ field }}</span>
          <span class="detail-value">{{ entry[field] ?? '—' }}</span>
        </div>
      </div>

      <div class="action-bar">
        <button
          v-for="action in actionsFor(entry.status)"
          :key="action"
          class="btn"
          type="button"
          @click="activeAction = action"
        >
          {{ action }}
        </button>
        <span v-if="!actionsFor(entry.status).length" class="page-desc">当前状态无可执行动作</span>
      </div>

      <h3 class="history-title">流转记录</h3>
      <table class="data-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>操作人</th>
            <th>动作</th>
            <th>状态变化</th>
            <th>备注</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, index) in historyDesc" :key="index">
            <td>{{ item.时间 }}</td>
            <td>{{ item.操作人 }}</td>
            <td>{{ item.动作 }}</td>
            <td>{{ item.从状态 }} → {{ item.到状态 }}</td>
            <td>{{ item.备注 }}</td>
          </tr>
          <tr v-if="!historyDesc.length">
            <td colspan="5" class="empty-state">暂无流转记录</td>
          </tr>
        </tbody>
      </table>
    </template>

    <ActionDialog
      v-if="activeAction && entry"
      :action="activeAction"
      :task-label="String(entry.任务编号 ?? entry.id)"
      @cancel="activeAction = ''"
      @submit="submitAction"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

import ActionDialog from './ActionDialog.vue'
import { actionsFor } from './taskFlow'

interface HistoryItem {
  时间: string
  操作人: string
  动作: string
  从状态: string
  到状态: string
  备注: string
}

type Entry = Record<string, unknown> & { id: number; status: string; history?: HistoryItem[] }

const ENDPOINT = '/api/task'
const baseFields = ["任务编号", "关联样品", "检测项目", "检测方法", "标准编号", "执行人员", "计划完成日", "任务状态"]

const route = useRoute()
const session = useSessionStore()

const entry = ref<Entry | null>(null)
const errorMessage = ref('')
const activeAction = ref('')

const displayFields = computed(() => {
  const fields = [...baseFields]
  if (entry.value?.复核人) fields.push('复核人')
  return fields
})

const historyDesc = computed<HistoryItem[]>(() => [...(entry.value?.history ?? [])].reverse())
const lastHistory = computed<HistoryItem | null>(() => {
  const history = entry.value?.history ?? []
  return history.length ? history[history.length - 1] : null
})

async function submitAction(payload: { values: Record<string, string>; remark: string }) {
  if (!entry.value) return
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${entry.value.id}/actions`, {
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
    activeAction.value = ''
    await reload()
  } catch (error) {
    activeAction.value = ''
    errorMessage.value = error instanceof Error ? error.message : '检测任务操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${route.params.id}`)
    const result = await response.json()
    if (!response.ok) {
      throw new Error(result.detail ?? '检测任务详情读取失败')
    }
    entry.value = result as Entry
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检测任务详情读取失败'
  }
}

onMounted(reload)
</script>
