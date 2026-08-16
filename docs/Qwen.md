# Qwen Decompose

Layer decomposition powered by [Qwen-Image-Layered](https://github.com/QwenLM/Qwen-Image-Layered). Splits a single image into multiple RGBA layers for sprite extraction.

> **Optional:** VibeGame's default asset pipeline does not require Qwen. Use `vibegame art rmbg <image> --agent -o <output>` for normal background removal. Deploy Qwen only when a task explicitly needs semantic multi-layer decomposition; it requires a separate GPU service and is not part of standard setup.

## Deploy (GPU Server)

1. Download weights from [HuggingFace](https://huggingface.co/Qwen/Qwen-Image-Layered) or [ModelScope](https://modelscope.cn/models/Qwen/Qwen-Image-Layered):

```sh
huggingface-cli download Qwen/Qwen-Image-Layered --local-dir ckpt/Qwen-Image-Layered
```

2. Install extra dependencies (not in pyproject.toml):

```sh
pip install torch diffusers "transformers>=4.51.3"
```

3. Start server:

```sh
python src/artist/qwen_image_layered.py --port 5001
```

Server listens on `0.0.0.0:5001`. Single GPU, serial task processing.

## Configure (Client)

Set `QWEN_SERVER_URL` in your project `.env`:

```
QWEN_SERVER_URL=http://127.0.0.1:<port>
```

If the server is behind SSH, use port forwarding first:

```sh
ssh -L <port>:localhost:<port> <user>@<server>
```

## Usage

```sh
vibegame art decompose <image_path> --layers 2
```

## Parameters

| Param | Default | Description |
|-------|---------|-------------|
| `--layers` | 2 | Number of layers (2-10) |
| `--save-path` | `decomposed/` next to input | Output directory |
| `--name` | image filename | Output subdirectory name |
| `--timeout` | 600 | Timeout in seconds |
