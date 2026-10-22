<!--
  MappingConfirm.vue — AI 映射确认卡片
  =======================================
  当 AI 将用户自由文本映射到某个已有选项后，展示此确认卡片。
  用户必须明确确认或否认，AI 映射结果不会静默写入业务状态。

  展示内容：
    - "我理解您的情况属于：「映射结果」"
    - [确认，继续] → 确认映射，等同按钮点击
    - [不对，重新选择] → 否认映射，回到固定按钮

  设计依据：system-design.md §12（自由文本映射契约）
-->
<template>
  <div class="mapping-confirm">
    <div class="confirm-card">
      <p class="confirm-label">根据您的描述，我理解您的问题为：</p>
      <p class="confirm-value">{{ store.mappingMessage || '正在识别...' }}</p>
      <div class="confirm-actions">
        <!-- 确认映射：等同于用户主动点击该选项 -->
        <button class="btn-confirm" @click="store.confirmMappingResult(true)" :disabled="store.loading">
          确认，继续
        </button>
        <!-- 否认映射：回到当前节点的固定按钮 -->
        <button class="btn-reject" @click="store.confirmMappingResult(false)" :disabled="store.loading">
          不对，重新选择
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useCaseStore } from '../stores/case.js'
const store = useCaseStore()
</script>

<style scoped>
.mapping-confirm { margin: 16px 0; }
.confirm-card {
  background: #e3f2fd;      /* 浅蓝色背景，与普通消息区分 */
  border: 1px solid #90caf9;
  border-radius: 10px;
  padding: 20px;
  text-align: center;
}
.confirm-label { font-size: 14px; color: #555; margin-bottom: 8px; }
.confirm-value { font-size: 18px; font-weight: 600; color: #0e7c7b; margin-bottom: 16px; }
.confirm-actions { display: flex; justify-content: center; gap: 12px; }
.btn-confirm { background: #0e7c7b; color: #fff; border: none; padding: 10px 24px; border-radius: 8px; cursor: pointer; font-size: 14px; }
.btn-confirm:hover { background: #0a5b5a; }
.btn-reject { background: #fff; border: 1px solid #999; color: #666; padding: 10px 24px; border-radius: 8px; cursor: pointer; font-size: 14px; }
.btn-reject:hover { border-color: #333; color: #333; }
</style>
