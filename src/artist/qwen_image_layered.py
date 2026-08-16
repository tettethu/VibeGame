"""
Qwen-Image-Layered API Server

API Endpoints:
- GET  /           Health check
- POST /submit     Submit processing task (image, name, config)
- GET  /query/{id} Query task status
- GET  /get/{id}   Download result (zip)
- GET  /list       List active tasks

Usage:
  python qwen_image_layered.py

Checkpoint:
  Download from HuggingFace (Qwen/Qwen-Image-Layered) or ModelScope.
  Place at ckpt/Qwen-Image-Layered/ under the repository root.

Extra dependencies (not in pyproject.toml):
  pip install torch diffusers transformers>=4.51.3
"""
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse
import asyncio
import os
import uuid
import socket
import json
import zipfile
from datetime import datetime
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from PIL import Image

ARTIST_DIR = Path(__file__).parent
CACHE_DIR = ARTIST_DIR / ".cache" / "tasks"

DEFAULT_CONFIG = {
    "seed": 777,
    "true_cfg_scale": 4.0,
    "negative_prompt": " ",
    "num_inference_steps": 50,
    "num_images_per_prompt": 1,
    "layers": 4,
    "resolution": 640,
    "cfg_normalize": True,
    "use_en_prompt": True,
}

pipeline = None


def _get_ckpt_path() -> Path:
    """Resolve checkpoint path: repo_root/ckpt/Qwen-Image-Layered/"""
    # repo root = git root of this project
    import subprocess
    result = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        capture_output=True, text=True,
        cwd=str(Path(__file__).resolve().parent),
    )
    if result.returncode != 0:
        print("Not inside a git repository")
        raise SystemExit(1)
    repo_root = Path(result.stdout.strip()).parent
    ckpt = repo_root / "ckpt" / "Qwen-Image-Layered"
    if not ckpt.exists():
        print(f"Checkpoint not found: {ckpt}")
        print("Download from: huggingface.co/Qwen/Qwen-Image-Layered")
        raise SystemExit(1)
    return ckpt


def load_pipeline():
    """Load model onto GPU"""
    global pipeline
    import torch
    from diffusers import QwenImageLayeredPipeline

    ckpt = _get_ckpt_path()
    print(f"Loading Qwen-Image-Layered pipeline from {ckpt}...")
    pipeline = QwenImageLayeredPipeline.from_pretrained(str(ckpt))
    pipeline = pipeline.to("cuda", torch.bfloat16)
    pipeline.set_progress_bar_config(disable=None)
    print("Pipeline loaded successfully!")


def process_image(image: Image.Image, config: dict) -> list:
    """Process image with pipeline"""
    import torch

    inputs = {
        "image": image,
        "generator": torch.Generator(device='cuda').manual_seed(config.get('seed', 777)),
        "true_cfg_scale": config.get('true_cfg_scale', 4.0),
        "negative_prompt": config.get('negative_prompt', ' '),
        "num_inference_steps": config.get('num_inference_steps', 50),
        "num_images_per_prompt": config.get('num_images_per_prompt', 1),
        "layers": config['layers'],
        "resolution": config.get('resolution', 640),
        "cfg_normalize": config.get('cfg_normalize', True),
        "use_en_prompt": config.get('use_en_prompt', True),
    }

    with torch.inference_mode():
        output = pipeline(**inputs)
        return output.images[0]


@asynccontextmanager
async def lifespan(app):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    load_pipeline()
    task = asyncio.create_task(process_queue())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)

tasks = {}
task_queue = deque()
is_processing = False


def run_pipeline(task_id: str):
    task_dir = CACHE_DIR / task_id
    config = json.loads((task_dir / "config.json").read_text())
    image = Image.open(task_dir / "input.png").convert("RGBA")

    output_images = process_image(image, config)
    for i, img in enumerate(output_images):
        img.save(task_dir / f"{i}.png")
    return len(output_images)


async def long_process(task_id: str):
    tasks[task_id]['status'] = 'processing'
    tasks[task_id]['start_time'] = datetime.now().isoformat()

    try:
        loop = asyncio.get_event_loop()
        layers_count = await loop.run_in_executor(None, run_pipeline, task_id)

        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['layers_count'] = layers_count
        tasks[task_id]['end_time'] = datetime.now().isoformat()

    except Exception as e:
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)
        tasks[task_id]['end_time'] = datetime.now().isoformat()


async def process_queue():
    global is_processing

    while True:
        if task_queue and not is_processing:
            task_id = task_queue.popleft()
            is_processing = True
            await long_process(task_id)
            is_processing = False
        await asyncio.sleep(0.1)


@app.get('/')
async def index():
    return {
        'status': 'ok',
        'message': 'Qwen-Image-Layered API is running',
        'hostname': socket.gethostname()
    }


@app.post('/submit')
async def process(
    image: UploadFile = File(..., description="Input image"),
    name: str = Form(..., description="Task name"),
    config: str = Form(None, description="Config JSON string")
):
    task_id = str(uuid.uuid4())

    user_config = json.loads(config) if config else {}
    final_config = {**DEFAULT_CONFIG, **user_config}

    if 'layers' not in final_config:
        return {'error': 'Missing required parameter: layers'}

    task_dir = CACHE_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    image_bytes = await image.read()
    (task_dir / "input.png").write_bytes(image_bytes)
    (task_dir / "config.json").write_text(json.dumps(final_config, indent=2))

    tasks[task_id] = {
        'name': name,
        'status': 'queued',
        'config': final_config,
        'created_at': datetime.now().isoformat()
    }

    task_queue.append(task_id)

    return {
        'task_id': task_id,
        'name': name,
        'status': 'queued',
        'position': len(task_queue),
        'message': 'Task queued successfully'
    }


@app.get('/query/{task_id}')
async def query(task_id: str):
    if task_id not in tasks:
        return {'task_id': task_id, 'status': 'not_found', 'message': 'Task not found'}
    return {'task_id': task_id, **tasks[task_id]}


@app.get('/get/{task_id}')
async def get_result(task_id: str):
    if task_id not in tasks:
        return {'error': 'Task not found'}

    if tasks[task_id]['status'] != 'completed':
        return {'error': 'Task not completed', 'status': tasks[task_id]['status']}

    task_dir = CACHE_DIR / task_id
    zip_path = task_dir / "result.zip"

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for png_file in sorted(task_dir.glob("*.png")):
            if png_file.name != "input.png":
                zf.write(png_file, png_file.name)

    task_name = tasks[task_id].get('name', task_id[:8])
    return FileResponse(zip_path, media_type="application/zip", filename=f"{task_name}.zip")


@app.get('/list')
async def list_tasks():
    queued_tasks = [
        {'task_id': tid, 'position': idx + 1, **tasks[tid]}
        for idx, tid in enumerate(task_queue)
    ]
    processing_tasks = [
        {'task_id': tid, **task_data}
        for tid, task_data in tasks.items()
        if task_data['status'] == 'processing'
    ]

    return {
        'processing': processing_tasks,
        'queued': queued_tasks,
        'total_queued': len(queued_tasks),
        'is_processing': is_processing
    }


if __name__ == '__main__':
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Qwen-Image-Layered API Server")
    parser.add_argument("--port", type=int, default=5001, help="Listen port (default: 5001)")
    args = parser.parse_args()
    uvicorn.run(app, host='0.0.0.0', port=args.port)
