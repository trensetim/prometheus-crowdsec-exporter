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
{{- range $k, $v := .Values.labels }}
{{ $k }}: {{ $v | quote }}
{{- end }}
{{- end }}

{{- define "annotations" -}}
{{- /* we add the change-cause here such that this definition is never empty */ -}}
kubernetes.io/change-cause: {{ (printf "%s %s %s %s" .Release.Service .Release.Name (ternary "upgrade" "install" .Release.IsUpgrade) (now | date "2006-01-02 03:04:05")) | quote }}
{{- range $k, $v := .Values.annotations }}
{{ $k }}: {{ $v | quote }}
{{- end }}
{{- end }}

{{- define "selectorLabels" -}}
app.kubernetes.io/name: {{ include "name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "configmap-name" -}}
{{- .Values.configMap.name | default (include "name" .) -}}
{{- end }}
{{- define "machine-credentials-secret-name" -}}
{{- .Values.config.machineCredentials.secret.name | default (printf "%s-machine-credentials" (include "name" .)) -}}
{{- end }}

{{- define "port-name" -}}
{{- .Values.nameOverrides.port | default "metrics" -}}
{{- end }}

