# Deploying the quant-loop daemon (Hetzner / any Linux box)

A Hetzner Cloud VM is just a Linux machine — the steps below work on any of
them, or on a bare-metal box. Two ways to keep the loop running forever:
**systemd** (simplest) or **Docker**.

> ⚠️ Out of the box the daemon trades a **simulated** market with a **mock**
> broker — it's safe to leave running but it isn't trading anything real. See
> `../CONNECTORS.md` to wire a real data feed and broker before it matters.

## Option A — systemd (recommended)

```bash
# 1. On the server, as root:
adduser --system --group quant
mkdir -p /opt/quant-loop && chown quant:quant /opt/quant-loop

# 2. Copy the code there (from your machine):
#    rsync -a quant-loop/ root@<server-ip>:/opt/quant-loop/
#    or: git clone <repo> /opt/quant-loop && cd /opt/quant-loop/quant-loop

# 3. (Optional) real models — put your key in an env file:
echo 'ANTHROPIC_API_KEY=sk-ant-...' > /opt/quant-loop/.env
chmod 600 /opt/quant-loop/.env
#    then add --claude to ExecStart in the unit file.

# 4. Install and start the service:
cp deploy/quant-loop.service /etc/systemd/system/quant-loop.service
systemctl daemon-reload
systemctl enable --now quant-loop
```

Operate it:

```bash
systemctl status quant-loop      # is it running?
journalctl -u quant-loop -f      # live engine log
tail -f /opt/quant-loop/state/STATE.md   # the loop's durable journal (the real record)
systemctl restart quant-loop     # picks up where it left off — state persists
systemctl stop quant-loop        # clean SIGTERM shutdown (finishes the current cycle)
```

`Restart=always` brings it back after a crash or reboot. State (`state/STATE.md`
and the evolved skills) lives on disk, so a restart keeps the loop's memory.

## Option B — Docker

```bash
docker build -f deploy/Dockerfile -t quant-loop .
docker run -d --name quant-loop --restart always \
  -v quant-loop-state:/app/state \
  -e ANTHROPIC_API_KEY=sk-ant-...  quant-loop

docker logs -f quant-loop        # live log
docker stop quant-loop           # clean SIGTERM shutdown
```

The named volume `quant-loop-state` persists the journal and skills across
container restarts.

## Cadence

The unit and Dockerfile use the article's production cadence — `--ingest-every
1h --risk-every 1m`. For a quick local smoke test use a fast clock instead:

```bash
python3 run.py --serve --tick 1s --ingest-every 3s --risk-every 1s
```

## Sizing

The reference is tiny — the smallest Hetzner shared-vCPU box (CX22) is plenty.
With the `--claude` backend, cost is dominated by API calls, not the VM: one
maker call + one checker call per symbol per ingest. At `--ingest-every 1h` over
3 symbols that's ~6 calls/hour. Tune the cadence to your budget.
