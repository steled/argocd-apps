{{- define "istio-gateways.listener" -}}
port: 443
protocol: HTTPS
allowedRoutes:
  namespaces:
    from: Selector
    selector:
      matchLabels:
        shared-gateway-access: "true"
tls:
  mode: Terminate
  certificateRefs:
    - group: ""
      kind: Secret
      name: domain-wildcard-certificate-tls
      namespace: istio-system
{{- end }}
