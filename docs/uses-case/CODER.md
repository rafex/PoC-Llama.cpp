Sí, totalmente compatible — usa exactamente las mismas flags que necesitamos (`--host 0.0.0.0 --port --jinja --ctx-size 4096 -n 1024 -t threads`), solo que mejor: detecta los threads automáticamente y mata cualquier instancia previa antes de arrancar.

Para levantarlo con este script:

```bash
/opt/llama.cpp/current/scripts/start-server.sh /srv/models/gguf/qwen2.5-coder-3b-instruct-q4_k_m.gguf 8080
```

Un detalle importante: el script usa `exec`, así que **se queda en foreground** (bloquea tu terminal) — no hace `nohup`/`disown` por sí solo. Para que sobreviva a que cierres la sesión SSH (el problema que tuvimos antes), tienes dos opciones:

**Opción A — nohup manual:**
```bash
nohup /opt/llama.cpp/current/scripts/start-server.sh /srv/models/gguf/qwen2.5-coder-3b-instruct-q4_k_m.gguf 8080 > /tmp/llama-server.log 2>&1 &
disown
```

**Opción B — `tmux`/`screen`** si los tienes instalados (más cómodo para ver logs en vivo después):
```bash
tmux new -d -s llama '/opt/llama.cpp/current/scripts/start-server.sh /srv/models/gguf/qwen2.5-coder-3b-instruct-q4_k_m.gguf 8080'
```

Verificar que quedó arriba:
```bash
curl -s http://127.0.0.1:8080/health
```
