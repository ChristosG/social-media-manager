"""
Thin REST wrapper around a headless ComfyUI instance for FLUX.2-klein-4B.

POST /generate {"prompt", "seed"?, "width"?, "height"?, "steps"?, "cfg"?,
                "sampler_name"?, "return_base64"?}  -> image/png (or JSON if return_base64)
GET  /health    -> ComfyUI reachability + system stats
GET  /samplers  -> list of valid sampler_name values

It loads an API-format ComfyUI workflow once, then per request deep-copies the graph,
patches the positive-prompt text (and optionally seed / size / steps), submits it to
ComfyUI's /prompt endpoint, waits for completion, and streams back the rendered PNG.

Node lookup is by class_type with env-var overrides, so it survives workflow re-exports:
  POSITIVE_NODE   force the node id whose inputs.text holds the prompt
  SEED_NODE       force the node id whose inputs.{seed|noise_seed} is the seed
  LATENT_NODE     force the Empty*LatentImage node id (for width/height)
  STEPS_NODE      force the node id whose inputs.steps controls step count
"""
import base64
import copy
import json
import os
import random
import time
import uuid

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

COMFY_URL = os.environ.get("COMFY_URL", "http://comfyui:8188").rstrip("/")
WORKFLOW_PATH = os.environ.get("WORKFLOW", "/workflows/flux2_klein_t2i_api.json")
POLL_TIMEOUT_S = float(os.environ.get("POLL_TIMEOUT_S", "180"))

# class_type candidates used for auto-detection
TEXT_NODE_TYPES = ("CLIPTextEncode", "CLIPTextEncodeFlux", "T5TextEncode")
SAMPLER_SEED_TYPES = ("RandomNoise", "KSampler", "KSamplerAdvanced",
                      "SamplerCustom", "SamplerCustomAdvanced")
# Size lives on BOTH the latent node and the Flux2Scheduler (resolution-aware sigmas) —
# they must stay in sync, so width/height is applied to every node of these types.
SIZE_TYPES = ("EmptySD3LatentImage", "EmptyLatentImage", "EmptyFlux2LatentImage",
              "Flux2Scheduler")
# steps live on the scheduler node(s)
STEPS_TYPES = ("Flux2Scheduler", "BasicScheduler", "KSampler", "KSamplerAdvanced")
# cfg (guidance) lives on the guider/sampler
CFG_TYPES = ("CFGGuider", "KSampler", "KSamplerAdvanced", "SamplerCustom")
# the sampling algorithm name
SAMPLER_NAME_TYPES = ("KSamplerSelect", "KSampler", "KSamplerAdvanced")

app = FastAPI(title="FLUX.2-klein image API")


def load_workflow():
    with open(WORKFLOW_PATH) as f:
        return json.load(f)


def _find_node(graph, class_types, require_input=None):
    """Return (node_id, node) for the first node whose class_type is in class_types
    and (optionally) that has require_input in its inputs. None if not found."""
    for nid, node in graph.items():
        if node.get("class_type") in class_types:
            if require_input is None or require_input in node.get("inputs", {}):
                return nid, node
    return None, None


def _positive_text_node(graph):
    """Pick the prompt node. Override via POSITIVE_NODE; else the text node with the
    longest existing text (positive prompts in templates are descriptive, negatives empty)."""
    forced = os.environ.get("POSITIVE_NODE")
    if forced and forced in graph:
        return forced
    best_id, best_len = None, -1
    for nid, node in graph.items():
        if node.get("class_type") in TEXT_NODE_TYPES:
            txt = node.get("inputs", {}).get("text", "")
            if isinstance(txt, str) and len(txt) >= best_len:
                best_id, best_len = nid, len(txt)
    return best_id


def _set_on_types(graph, class_types, key, value):
    """Set inputs[key]=value on every node of the given class_types that has that input.
    Returns the number of nodes patched."""
    n = 0
    for node in graph.values():
        if node.get("class_type") in class_types and key in node.get("inputs", {}):
            node["inputs"][key] = value
            n += 1
    return n


def patch_graph(graph, req):
    g = copy.deepcopy(graph)

    pid = _positive_text_node(g)
    if pid is None:
        raise HTTPException(500, "No text-encode node found in workflow to inject the prompt.")
    g[pid]["inputs"]["text"] = req.prompt

    # The workflow has a fixed noise_seed, so over the API the same prompt would always
    # return the same image. Randomize when the caller doesn't pin a seed.
    seed = int(req.seed) if req.seed is not None else random.randint(0, 2**32 - 1)
    sid = os.environ.get("SEED_NODE")
    node = g.get(sid) if sid else None
    if node is None:
        sid, node = _find_node(g, SAMPLER_SEED_TYPES, require_input="noise_seed")
        if node is None:
            sid, node = _find_node(g, SAMPLER_SEED_TYPES, require_input="seed")
    if node is not None:
        key = "noise_seed" if "noise_seed" in node["inputs"] else "seed"
        node["inputs"][key] = seed

    # Size lives on the latent node AND the Flux2Scheduler — keep them in sync.
    if req.width is not None:
        _set_on_types(g, SIZE_TYPES, "width", int(req.width))
    if req.height is not None:
        _set_on_types(g, SIZE_TYPES, "height", int(req.height))

    if req.steps is not None:
        if _set_on_types(g, STEPS_TYPES, "steps", int(req.steps)) == 0:
            raise HTTPException(500, "Requested steps but no node has a 'steps' input.")

    if req.cfg is not None:
        if _set_on_types(g, CFG_TYPES, "cfg", float(req.cfg)) == 0:
            raise HTTPException(500, "Requested cfg but no node has a 'cfg' input.")

    if req.sampler_name is not None:
        if _set_on_types(g, SAMPLER_NAME_TYPES, "sampler_name", req.sampler_name) == 0:
            raise HTTPException(500, "Requested sampler_name but no node has a 'sampler_name' input.")

    return g


def submit_and_wait(graph):
    client_id = uuid.uuid4().hex
    r = requests.post(f"{COMFY_URL}/prompt",
                      json={"prompt": graph, "client_id": client_id}, timeout=30)
    if r.status_code != 200:
        raise HTTPException(502, f"ComfyUI /prompt rejected the graph: {r.text}")
    prompt_id = r.json()["prompt_id"]

    deadline = time.time() + POLL_TIMEOUT_S
    while time.time() < deadline:
        h = requests.get(f"{COMFY_URL}/history/{prompt_id}", timeout=30)
        hist = h.json().get(prompt_id)
        if hist:
            status = hist.get("status", {})
            if status.get("status_str") == "error":
                raise HTTPException(500, f"ComfyUI execution error: {json.dumps(status)}")
            for node_out in hist.get("outputs", {}).values():
                imgs = node_out.get("images")
                if imgs:
                    return imgs[0]  # {filename, subfolder, type}
        time.sleep(0.4)
    raise HTTPException(504, "Timed out waiting for ComfyUI to render the image.")


def fetch_image(img):
    r = requests.get(f"{COMFY_URL}/view", params={
        "filename": img["filename"],
        "subfolder": img.get("subfolder", ""),
        "type": img.get("type", "output"),
    }, timeout=60)
    r.raise_for_status()
    return r.content


class GenRequest(BaseModel):
    prompt: str
    seed: int | None = None
    width: int | None = None
    height: int | None = None
    steps: int | None = None
    cfg: float | None = None
    sampler_name: str | None = None
    return_base64: bool = False


@app.get("/health")
def health():
    try:
        s = requests.get(f"{COMFY_URL}/system_stats", timeout=10).json()
        return {"ok": True, "comfyui": s.get("system", {})}
    except Exception as e:
        raise HTTPException(503, f"ComfyUI not reachable at {COMFY_URL}: {e}")


@app.get("/samplers")
def samplers():
    try:
        d = requests.get(f"{COMFY_URL}/object_info/KSamplerSelect", timeout=10).json()
        spec = d["KSamplerSelect"]["input"]["required"]["sampler_name"]
        # Old ComfyUI: spec[0] is the list of names. New: ["COMBO", {"options": [...]}].
        names = spec[0] if isinstance(spec[0], list) else spec[1].get("options", [])
        return {"samplers": names}
    except Exception as e:
        raise HTTPException(503, f"Could not fetch sampler list: {e}")


@app.post("/generate")
def generate(req: GenRequest):
    if not req.prompt.strip():
        raise HTTPException(400, "prompt must not be empty")
    graph = patch_graph(load_workflow(), req)
    img_ref = submit_and_wait(graph)
    png = fetch_image(img_ref)
    if req.return_base64:
        return {"filename": img_ref["filename"],
                "image_base64": base64.b64encode(png).decode()}
    return Response(content=png, media_type="image/png")
