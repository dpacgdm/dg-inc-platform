# Linux First 15 Minutes Triage

Purpose: quickly separate CPU, memory, disk, network, process, and service-manager problems.

## 0-2 minutes: establish blast radius

```bash
hostnamectl
uptime
date -u
who
```

Questions:

- Is this one host or many?
- Is user impact confirmed or only an alert?
- Was there a recent deployment, patch, config change, or capacity event?

## 2-5 minutes: saturation scan

```bash
top -o %CPU
free -h
df -h
iostat -xz 1 3
vmstat 1 5
```

Look for:

- high load with low CPU: often IO wait, blocked tasks, storage, network filesystem
- low free memory with swap activity: memory pressure
- full filesystem or inode exhaustion
- disk await/svctm spikes

## 5-8 minutes: process and service state

```bash
ps aux --sort=-%cpu | head -20
ps aux --sort=-%mem | head -20
systemctl --failed
journalctl -p err -n 100 --no-pager
```

## 8-12 minutes: network and DNS

```bash
ss -s
ss -tulpn
ip addr
ip route
resolvectl status || cat /etc/resolv.conf
ping -c 3 8.8.8.8
curl -Iv https://example.com
```

## 12-15 minutes: decide

Pick one:

1. rollback recent change
2. scale/restart safely
3. isolate bad dependency
4. mitigate user impact
5. escalate with evidence

## Evidence required before escalation

- host
- time window UTC
- top symptom
- impact statement
- commands run
- one clear hypothesis
- one next action
