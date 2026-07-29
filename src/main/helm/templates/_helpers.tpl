{{- define "name" -}}
{{- if .Values.nameOverrides.release }}
    {{- .Values.nameOverrides.release }}
{{- else }}
    {{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{- define "labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{ include "selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "selectorLabels" -}}
app.kubernetes.io/name: {{ include "name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "configmap-name" -}}
{{- .Values.nameOverrides.configmap | default (include "name" .) -}}
{{- end }}
{{- define "machine-credentials-secret-name" -}}
{{- .Values.nameOverrides.crowdsecMachineCredentialsSecret | default (printf "%s-machine-credentials" (include "name" .)) -}}
{{- end }}
