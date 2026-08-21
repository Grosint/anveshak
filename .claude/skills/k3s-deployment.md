# k3s Deployment Patterns

## When to load: any task involving production deployment, Kubernetes, k3s, or Docker container restarts

> See also: `.claude/skills/learned/dotenv-inline-comment-int-fields.md` — inline comments on integer .env vars cause pydantic ValidationError at startup

---

### Namespace convention
anveshak-api | anveshak-workers | anveshak-storage | anveshak-frontend | anveshak-ops

### Every Deployment needs
- resource limits (CPU + memory)
- liveness and readiness probes
- env vars from ConfigMap (non-secret) and Secret (credentials)

### GPU node affinity (for vision service on GPU hardware)
```yaml
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
      - matchExpressions:
        - key: accelerator
          operator: In
          values: [nvidia-gpu]
```

### Ollama deployment with GPU
```yaml
resources:
  limits:
    nvidia.com/gpu: 1
    memory: "20Gi"
  requests:
    memory: "16Gi"
env:
  - name: OLLAMA_KEEP_ALIVE
    value: "-1"  # Never evict model from VRAM
```

### Health check pattern
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
```
