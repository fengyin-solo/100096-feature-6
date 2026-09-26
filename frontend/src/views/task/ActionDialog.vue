<template>
  <div class="dialog-mask" @click.self="cancel">
    <div class="dialog-card">
      <h3 class="dialog-title">{{ action }}</h3>
      <p class="dialog-desc">检测任务：{{ taskLabel }}</p>
      <label v-for="input in inputs" :key="input.key" class="dialog-field">
        <span>
          {{ input.label }}
          <em v-if="input.required" class="required-mark">*</em>
        </span>
        <input v-model="form[input.key]" :placeholder="input.placeholder ?? ''" />
      </label>
      <p v-if="error" class="error-text">{{ error }}</p>
      <div class="dialog-actions">
        <button class="btn primary" type="button" @click="submit">确认{{ action }}</button>
        <button class="btn ghost" type="button" @click="cancel">取消</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { ACTION_INPUTS } from './taskFlow'

const props = defineProps<{ action: string; taskLabel: string }>()
const emit = defineEmits<{
  (e: 'cancel'): void
  (e: 'submit', payload: { values: Record<string, string>; remark: string }): void
}>()

const form = ref<Record<string, string>>({})
const error = ref('')
const inputs = computed(() => ACTION_INPUTS[props.action] ?? [])

watch(
  () => props.action,
  () => {
    form.value = {}
    error.value = ''
  },
  { immediate: true },
)

function submit() {
  for (const input of inputs.value) {
    if (input.required && !(form.value[input.key] ?? '').trim()) {
      error.value = `请先填写${input.label}`
      return
    }
  }
  const values: Record<string, string> = {}
  let remark = ''
  for (const input of inputs.value) {
    const raw = (form.value[input.key] ?? '').trim()
    if (input.isRemark) {
      remark = raw
    } else if (raw) {
      values[input.key] = raw
    }
  }
  emit('submit', { values, remark })
}

function cancel() {
  emit('cancel')
}
</script>
