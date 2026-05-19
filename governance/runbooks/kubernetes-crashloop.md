# Kubernetes CrashLoopBackOff Triage

Purpose: diagnose a pod restarting repeatedly without flailing around like a caffeinated penguin.

## Confirm scope

```bash
kubectl get pods -A | grep -E 'CrashLoopBackOff|Error|ImagePullBackOff'
kubectl get deploy,rs,pods -n <namespace>
```

## Inspect the pod

```bash
kubectl describe pod <pod> -n <namespace>
kubectl logs <pod> -n <namespace> --previous
kubectl logs <pod> -n <namespace>
```

## Common causes

- bad image or entrypoint
- missing config or secret
- failed dependency
- bad liveness probe
- resource limit too low
- application panic/exception
- permission or filesystem issue

## Check rollout context

```bash
kubectl rollout history deployment/<deployment> -n <namespace>
kubectl rollout status deployment/<deployment> -n <namespace>
kubectl get events -n <namespace> --sort-by=.metadata.creationTimestamp | tail -50
```

## Mitigation options

Rollback:

```bash
kubectl rollout undo deployment/<deployment> -n <namespace>
```

Scale down risky workload:

```bash
kubectl scale deployment/<deployment> -n <namespace> --replicas=0
```

Patch probe only after evidence:

```bash
kubectl edit deployment/<deployment> -n <namespace>
```

## Escalation packet

- namespace
- deployment
- image tag
- restart count
- previous logs
- events
- recent changes
- current user impact
