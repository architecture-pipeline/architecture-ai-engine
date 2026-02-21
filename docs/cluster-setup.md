# Cluster Setup

## Machines

### Workstation — `ccil1s26m8hj6lws`
- **CPU**: AMD Ryzen Threadripper PRO 5955WX (16 cores / 32 threads)
- **RAM**: 251 GB
- **Storage**: 3.5 TB NVMe
- **OS**: Ubuntu 22.04.5 LTS
- **CUDA**: 12.8
- **GPUs**:
  | GPU | Model | VRAM | Status |
  |-----|-------|------|--------|
  | 0 | NVIDIA RTX A6000 | 48 GB | Occupied (vLLM — gpt-oss-120b) |
  | 1 | NVIDIA RTX A6000 | 48 GB | ComfyUI Docker (`avince1-comfyui`) |
  | 2 | NVIDIA RTX A6000 | 48 GB | ComfyUI Docker (`avince1-comfyui`) |
  | 3 | NVIDIA RTX A6000 | 48 GB | Occupied (vLLM — gpt-oss-120b) |

### Cluster — `cci-siscluster2`
- Hosts the vision model (Qwen3-VL-30B)
- Accessible from the workstation via internal network

## SSH Access

Requires UNC Charlotte VPN when off-campus.

```
Host cci-jump
    HostName cci-jump.charlotte.edu
    User <your-niner-username>
    Port 22
    PreferredAuthentications password
    PubkeyAuthentication no

Host lambda-fu
    HostName ccil1s26m8hj6lws
    User <your-niner-username>
    ProxyJump cci-jump
    Port 22
    LocalForward 8001 cci-siscluster2:8000
    LocalForward 8000 localhost:8000
    LocalForward 8188 localhost:8188
```

Connect: `ssh lambda-fu`

### SSH Tunnels (access everything from your local Mac)

Just run `ssh lambda-fu` and all tunnels open automatically:

| Local URL | Reaches |
|-----------|---------|
| `http://localhost:8000` | gpt-oss-120b (text, on workstation) |
| `http://localhost:8001` | Qwen3-VL-30B (vision, on cci-siscluster2) |
| `http://localhost:8188` | ComfyUI (Docker on GPUs 1&2) |

## Available Models

### gpt-oss-120b (text)
- **Machine**: `ccil1s26m8hj6lws`
- **Endpoint**: `http://localhost:8000/v1/`
- **Model ID**: `openai/gpt-oss-120b`
- **Context**: 65,536 tokens
- **GPUs**: 0 & 3 (tensor parallel)
- **Features**: Tool calling enabled

### Qwen3-VL-30B (vision)
- **Machine**: `cci-siscluster2`
- **Endpoint**: `http://cci-siscluster2:8000/v1/` (from workstation)
- **Model ID**: `cyankiwi/Qwen3-VL-30B-A3B-Thinking-AWQ-8bit`
- **Context**: 196,608 tokens
- **Use case**: Replaces GPT-4.1 vision for architectural descriptions

From your Mac (via tunnel):
```python
client = OpenAI(base_url="http://localhost:8001/v1", api_key="none")
```

## ComfyUI Docker Setup

- **Container**: `avince1-comfyui`
- **Image**: `avince1-comfyui` (based on `pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime`)
- **GPUs**: 1 & 2
- **Port**: 8188
- **Data mount**: `/home/avince1` -> `/workspace` inside container

### Managing the container
```bash
# Start
docker start avince1-comfyui

# Stop
docker stop avince1-comfyui

# Logs
docker logs avince1-comfyui

# Restart (needed after editing custom nodes)
docker restart avince1-comfyui

# Full rebuild (if Dockerfile or pip changes)
cd /home/avince1 && docker build -t avince1-comfyui .
docker rm avince1-comfyui
docker run -d --name avince1-comfyui --gpus '"device=1,2"' -v /home/avince1:/workspace -p 8188:8188 avince1-comfyui
```

### Important: files created by Docker are owned by root
To delete Dataset outputs from the host, use:
```bash
docker exec avince1-comfyui rm -rf /workspace/Dataset/*
```

## Pipeline

### Overview
```
Local (Rhino)          Cluster (ComfyUI)              Cluster (Qwen)
     |                       |                              |
  generate.py          batch_submit_multiview.py       generate_prompt.py
     |                       |                              |
  4 views per tower    4 renders per tower             architectural description
  (NE, NW, SE, SW)    ({view}_realistic.png)           per rendered image
```

### Input format (from Rhino)
Each tower folder in `GeometryImagesRhino/` contains:
```
tower_000/
  northeast.png
  northwest.png
  southeast.png
  southwest.png
  params.json
```

### Output format (from ComfyUI)
Each tower folder in `Dataset/` contains:
```
tower_000/
  northeast_realistic.png
  northwest_realistic.png
  southeast_realistic.png
  southwest_realistic.png
  params.json
```

### Workflows

| Workflow | File | Use case |
|----------|------|----------|
| **Multi-view (default)** | `prompt_multiview.json` | 4 views per tower, no AI description |
| Single-view (no AI) | `prompt_no_openai.json` | 1 view (northeast) per tower, no AI description |
| Single-view (with AI) | `prompt.json` | 1 view + GPT-4.1 architectural description |

### Scripts

| Script | What it does |
|--------|-------------|
| `batch_submit_multiview.py` | **Default.** Processes all 4 views per tower with shared seed for visual consistency |
| `describe_towers.py` | **Post-render.** Sends all 4 rendered views to Qwen3-VL-30B for architectural descriptions |
| `batch_submit.py` | Single-view batch processing |
| `verify_dataset.py` | Validates Dataset outputs (checks files, sizes, prompts) |
| `register_batch.py` | Recovery tool: rebuilds progress log from existing Dataset |

### Custom ComfyUI Nodes

| Node | File | What it does |
|------|------|-------------|
| Load Multi-View Image | `image_loader_multiview.py` | Loads `{view_name}.png` from tower folder |
| Load Project Sub-Folder | `image_loader.py` | Loads `northeast.png` (single-view) |
| Generate Architectural Prompt | `generate_prompt.py` | Sends image to vision API for description |
| Update params.json (Multi-View) | `save_JSON_multiview.py` | Saves `{view_name}_realistic.png` + params |
| Update params.json | `save_JSON.py` | Saves `realistic.png` + params (single-view) |

### Running a batch (default: multi-view)

```bash
# 1. Upload towers from local Mac to cluster
rsync -avz --progress -e "ssh lambda-fu" \
  ~/Desktop/architecture-ai-engine/GeometryImagesRhino.nosync/ \
  lambda-fu:/home/avince1/comfyui/GeometryImagesRhino/

# 2. SSH into workstation
ssh lambda-fu

# 3. Run multi-view batch (4 renders per tower)
docker exec avince1-comfyui python3 /workspace/batch_submit_multiview.py <start> <end>

# Example: process towers 0-49
docker exec avince1-comfyui python3 /workspace/batch_submit_multiview.py 0 49

# 4. Generate architectural descriptions (Qwen3-VL-30B sees all 4 views)
docker exec avince1-comfyui python3 /workspace/describe_towers.py <start> <end>

# Use --force to overwrite existing descriptions
docker exec avince1-comfyui python3 /workspace/describe_towers.py 0 49 --force

# 5. Pull results back to Mac
rsync -avz --progress -e "ssh lambda-fu" \
  lambda-fu:/home/avince1/Dataset/ \
  ~/Desktop/cluster_output/
```

### Pipeline migration status

| Step | Before (paid) | Cluster (free) | Status |
|------|--------------|----------------|--------|
| 1. Generate towers | Rhino (local) | Rhino (local) — no change | Done |
| 2. Photorealistic render | Stability AI API | ComfyUI multi-view on GPUs 1&2 | Done |
| 3. Vision descriptions | GPT-4.1 API | Qwen3-VL-30B via `describe_towers.py` | Done |

## Docker Guidelines

- **Use GPUs 1 & 2 only**: `docker run --gpus '"device=1,2"' ...`
- **Name your containers**: `docker run --name avince1-<service> ...`
- **Keep data in your home dir**: `/home/avince1/`
- **Don't touch existing containers** (especially `vllm-120b-0and3-tool`)
- **Restart container after editing custom nodes** (ComfyUI caches them in memory)
