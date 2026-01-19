<script lang="ts" setup>
import { Form } from '@primevue/forms'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import { useToast } from 'primevue/usetoast'
import z from 'zod'
import { addServerDialog } from '@/status'

const emit = defineEmits<{
  (
    e: 'add',
    server: {
      server_id: string
      os_ip: string
      bmc_ip: string
      ssh_user: string
      ssh_password: string
    },
  ): void
}>()

const toast = useToast()

const resolver = zodResolver(
  z.object({
    server_id: z.string().min(1, { message: 'Server ID is required.' }),
    os_ip: z
      .string()
      .min(7, { message: 'OS IP is required.' })
      .regex(
        /^(25[0-5]|2[0-4]\d|[01]?\d{1,2})\.(25[0-5]|2[0-4]\d|[01]?\d{1,2})\.(25[0-5]|2[0-4]\d|[01]?\d{1,2})\.(25[0-5]|2[0-4]\d|[01]?\d{1,2})$/,
        { message: 'Invalid IP address format.' },
      ),
    bmc_ip: z
      .string()
      .min(7, { message: 'BMC IP is required.' })
      .regex(
        /^(25[0-5]|2[0-4]\d|[01]?\d{1,2})\.(25[0-5]|2[0-4]\d|[01]?\d{1,2})\.(25[0-5]|2[0-4]\d|[01]?\d{1,2})\.(25[0-5]|2[0-4]\d|[01]?\d{1,2})$/,
        { message: 'Invalid IP address format.' },
      ),
    ssh_user: z.string().min(1, { message: 'SSH User is required.' }).default('root'),
    ssh_password: z.string().min(1, { message: 'SSH Password is required.' }).default('1'),
  }),
)

function onFormSubmit({ valid, values }) {
  if (valid) {
    emit('add', values)

    toast.add({
      severity: 'success',
      summary: 'Form is submitted.',
      life: 3000,
    })
  }
}
</script>

<template>
  <Dialog v-model:visible="addServerDialog" modal header="添加测试机器" :style="{ width: '25rem' }">
    <Form v-slot="$form" :resolver class="flex flex-col gap-4 w-full" @submit="onFormSubmit">
      <FormField v-slot="$field" name="server_id" class="flex flex-col gap-1">
        <InputText name="server_id" type="text" placeholder="Server ID (e.g. S01)" fluid />
        <Message v-if="$field?.invalid" severity="error" size="small" variant="simple">
          {{
            $field.error?.message
          }}
        </Message>
      </FormField>
      <FormField v-slot="$field" name="os_ip" class="flex flex-col gap-1">
        <InputText name="os_ip" type="text" placeholder="OS IP (e.g. 192.168.1.100)" fluid />
        <Message v-if="$field?.invalid" severity="error" size="small" variant="simple">
          {{
            $field.error?.message
          }}
        </Message>
      </FormField>
      <FormField v-slot="$field" name="bmc_ip" class="flex flex-col gap-1">
        <InputText name="bmc_ip" type="text" placeholder="BMC IP (e.g. 192.168.1.101)" fluid />
        <Message v-if="$field?.invalid" severity="error" size="small" variant="simple">
          {{
            $field.error?.message
          }}
        </Message>
      </FormField>
      <FormField v-slot="$field" name="ssh_user" class="flex flex-col gap-1">
        <InputText name="ssh_user" type="text" placeholder="SSH User (e.g. root)" fluid />
        <Message v-if="$field?.invalid" severity="error" size="small" variant="simple">
          {{
            $field.error?.message
          }}
        </Message>
      </FormField>
      <FormField v-slot="$field" name="ssh_password" class="flex flex-col gap-1">
        <InputText
          name="ssh_password"
          type="password"
          placeholder="SSH Password (e.g. 123456)"
          fluid
        />
        <Message v-if="$field?.invalid" severity="error" size="small" variant="simple">
          {{
            $field.error?.message
          }}
        </Message>
      </FormField>
      <div class="flex justify-end gap-2">
        <Button label="取消" severity="secondary" @click="addServerDialog = false" />
        <Button type="submit" label="添加" :disabled="!$form.valid" />
      </div>
    </Form>
  </Dialog>
</template>
